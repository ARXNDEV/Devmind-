import {
  ConflictException,
  Inject,
  Injectable,
  OnApplicationBootstrap,
  UnauthorizedException,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import * as argon2 from 'argon2';
import { createHash, randomBytes } from 'crypto';
import { and, eq, isNull } from 'drizzle-orm';
import { uuidv7 } from 'uuidv7';
import { AuthenticatedUser, MemberRole } from '@/common/auth/auth.types';
import {
  DEFAULT_CLAIMS,
  DEFAULT_ORG_ID,
  DEFAULT_ORG_NAME,
  DEFAULT_ORG_SLUG,
  DEFAULT_USER_ID,
} from '@/common/auth/dev-auth';
import { APP_CONFIG, AppConfig } from '@/config/app-config';
import { Database, DB } from '@/database/database.module';
import { memberships, organizations, sessions, users } from '@/database/schema';
import { AuditService } from '@/modules/audit/audit.service';
import { AuthResponseDto, LoginDto, RegisterDto } from './dto/auth.dto';

export interface IssuedAuth {
  response: AuthResponseDto;
  refreshToken: string;
  refreshExpiresAt: Date;
}

const ARGON2_OPTIONS: argon2.Options = {
  type: argon2.argon2id,
  memoryCost: 19456, // 19 MiB — OWASP recommended argon2id baseline
  timeCost: 2,
  parallelism: 1,
};

@Injectable()
export class AuthService implements OnApplicationBootstrap {
  constructor(
    @Inject(DB) private readonly db: Database,
    @Inject(APP_CONFIG) private readonly config: AppConfig,
    private readonly jwtService: JwtService,
    private readonly auditService: AuditService,
  ) {}

  /** When AUTH_DISABLED, ensure the seeded default org + admin user exist. */
  async onApplicationBootstrap(): Promise<void> {
    if (!this.config.AUTH_DISABLED) return;
    await this.db
      .insert(organizations)
      .values({ id: DEFAULT_ORG_ID, name: DEFAULT_ORG_NAME, slug: DEFAULT_ORG_SLUG })
      .onConflictDoNothing();
    await this.db
      .insert(users)
      .values({
        id: DEFAULT_USER_ID,
        orgId: DEFAULT_ORG_ID,
        email: DEFAULT_CLAIMS.email,
        name: DEFAULT_CLAIMS.name,
      })
      .onConflictDoNothing();
    await this.db
      .insert(memberships)
      .values({ userId: DEFAULT_USER_ID, orgId: DEFAULT_ORG_ID, role: 'owner' })
      .onConflictDoNothing();
  }

  /** Issues a session for the seeded default admin (AUTH_DISABLED mode). */
  async devAuth(): Promise<IssuedAuth> {
    return this.issueAuth(
      DEFAULT_USER_ID,
      DEFAULT_ORG_ID,
      'owner',
      DEFAULT_CLAIMS.email,
      DEFAULT_CLAIMS.name,
      { id: DEFAULT_ORG_ID, name: DEFAULT_ORG_NAME, slug: DEFAULT_ORG_SLUG },
    );
  }

  /** Creates organization + owner user atomically. */
  async register(dto: RegisterDto): Promise<IssuedAuth> {
    const passwordHash = await argon2.hash(dto.password, ARGON2_OPTIONS);
    const orgId = uuidv7();
    const userId = uuidv7();
    const email = dto.email.toLowerCase();

    try {
      await this.db.transaction(async (tx) => {
        await tx.insert(organizations).values({
          id: orgId,
          name: dto.organizationName,
          slug: await this.uniqueOrgSlug(dto.organizationName),
        });
        await tx.insert(users).values({
          id: userId,
          orgId,
          email,
          name: dto.name,
          passwordHash,
        });
        await tx.insert(memberships).values({ userId, orgId, role: 'owner' });
      });
    } catch (err: unknown) {
      if (this.isUniqueViolation(err)) {
        throw new ConflictException('A user with this email already exists');
      }
      throw err;
    }

    await this.auditService.record({
      orgId,
      actorType: 'user',
      actorId: userId,
      action: 'auth.register',
      resourceType: 'organization',
      resourceId: orgId,
    });

    return this.issueAuth(userId, orgId, 'owner', email, dto.name, {
      id: orgId,
      name: dto.organizationName,
      slug: await this.orgSlug(orgId),
    });
  }

  async login(dto: LoginDto): Promise<IssuedAuth> {
    const email = dto.email.toLowerCase();
    const row = await this.db
      .select({
        user: users,
        role: memberships.role,
        org: organizations,
      })
      .from(users)
      .innerJoin(memberships, eq(memberships.userId, users.id))
      .innerJoin(organizations, eq(organizations.id, users.orgId))
      .where(eq(users.email, email))
      .limit(1);

    const match = row[0];
    // Constant-shape flow: always run an argon2 verification so a missing
    // user is timing-indistinguishable from a wrong password.
    const hash =
      match?.user.passwordHash ??
      '$argon2id$v=19$m=19456,t=2,p=1$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA';
    const valid = await argon2
      .verify(hash, dto.password, ARGON2_OPTIONS)
      .catch(() => false);

    if (!match || !match.user.passwordHash || !valid) {
      throw new UnauthorizedException('Invalid email or password');
    }

    await this.auditService.record({
      orgId: match.org.id,
      actorType: 'user',
      actorId: match.user.id,
      action: 'auth.login',
      resourceType: 'session',
    });

    return this.issueAuth(
      match.user.id,
      match.org.id,
      match.role,
      match.user.email,
      match.user.name,
      { id: match.org.id, name: match.org.name, slug: match.org.slug },
    );
  }

  /** Rotates the refresh token: the presented token is revoked, a new one issued. */
  async refresh(presentedToken: string): Promise<IssuedAuth> {
    const tokenHash = this.hashToken(presentedToken);
    const now = new Date();

    const row = await this.db
      .select({ session: sessions, user: users, role: memberships.role, org: organizations })
      .from(sessions)
      .innerJoin(users, eq(users.id, sessions.userId))
      .innerJoin(memberships, eq(memberships.userId, users.id))
      .innerJoin(organizations, eq(organizations.id, users.orgId))
      .where(
        and(eq(sessions.refreshTokenHash, tokenHash), isNull(sessions.revokedAt)),
      )
      .limit(1);

    const match = row[0];
    if (!match || match.session.expiresAt < now) {
      throw new UnauthorizedException('Invalid or expired refresh token');
    }

    await this.db
      .update(sessions)
      .set({ revokedAt: now })
      .where(eq(sessions.id, match.session.id));

    return this.issueAuth(
      match.user.id,
      match.org.id,
      match.role,
      match.user.email,
      match.user.name,
      { id: match.org.id, name: match.org.name, slug: match.org.slug },
    );
  }

  async logout(presentedToken: string | undefined): Promise<void> {
    if (!presentedToken) return;
    await this.db
      .update(sessions)
      .set({ revokedAt: new Date() })
      .where(eq(sessions.refreshTokenHash, this.hashToken(presentedToken)));
  }

  private async issueAuth(
    userId: string,
    orgId: string,
    role: MemberRole,
    email: string,
    name: string,
    org: { id: string; name: string; slug: string },
  ): Promise<IssuedAuth> {
    const claims: AuthenticatedUser = { sub: userId, org: orgId, role, email, name };
    const accessToken = await this.jwtService.signAsync(claims, {
      expiresIn: this.config.API_JWT_ACCESS_TTL,
    });

    const refreshToken = randomBytes(48).toString('base64url');
    const refreshExpiresAt = new Date(
      Date.now() + this.config.API_JWT_REFRESH_TTL * 1000,
    );
    await this.db.insert(sessions).values({
      id: uuidv7(),
      userId,
      orgId,
      refreshTokenHash: this.hashToken(refreshToken),
      expiresAt: refreshExpiresAt,
    });

    return {
      refreshToken,
      refreshExpiresAt,
      response: {
        accessToken,
        expiresIn: this.config.API_JWT_ACCESS_TTL,
        user: { id: userId, email, name, role },
        organization: org,
      },
    };
  }

  private hashToken(token: string): string {
    return createHash('sha256').update(token).digest('hex');
  }

  private async orgSlug(orgId: string): Promise<string> {
    const [org] = await this.db
      .select({ slug: organizations.slug })
      .from(organizations)
      .where(eq(organizations.id, orgId))
      .limit(1);
    return org?.slug ?? '';
  }

  private async uniqueOrgSlug(name: string): Promise<string> {
    const base =
      name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .slice(0, 48) || 'org';
    const [existing] = await this.db
      .select({ id: organizations.id })
      .from(organizations)
      .where(eq(organizations.slug, base))
      .limit(1);
    return existing ? `${base}-${randomBytes(3).toString('hex')}` : base;
  }

  private isUniqueViolation(err: unknown): boolean {
    return (
      typeof err === 'object' &&
      err !== null &&
      'cause' in err &&
      typeof (err as { cause?: { code?: string } }).cause === 'object' &&
      (err as { cause?: { code?: string } }).cause?.code === '23505'
    ) || (typeof err === 'object' && err !== null && (err as { code?: string }).code === '23505');
  }
}
