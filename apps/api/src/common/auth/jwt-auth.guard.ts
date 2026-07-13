import {
  CanActivate,
  ExecutionContext,
  Inject,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { JwtService } from '@nestjs/jwt';
import { APP_CONFIG, AppConfig } from '@/config/app-config';
import { AuthenticatedUser } from './auth.types';
import { DEFAULT_CLAIMS } from './dev-auth';
import { IS_PUBLIC_KEY } from './decorators';

/**
 * Registered as a global APP_GUARD: every route requires a valid access
 * token unless explicitly marked @Public(). Default-deny by construction.
 */
@Injectable()
export class JwtAuthGuard implements CanActivate {
  constructor(
    private readonly jwtService: JwtService,
    private readonly reflector: Reflector,
    @Inject(APP_CONFIG) private readonly config: AppConfig,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest();

    // Login-gate bypass: auth is off, so run as the seeded default admin.
    if (this.config.AUTH_DISABLED) {
      request.user = DEFAULT_CLAIMS;
      return true;
    }

    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);
    if (isPublic) return true;
    const header: string | undefined = request.headers?.authorization;
    // EventSource (SSE) cannot set headers, so a token may arrive as a query
    // param on those routes; the header remains the norm everywhere else.
    const token = header?.startsWith('Bearer ')
      ? header.slice(7)
      : (request.query?.access_token as string | undefined);
    if (!token) throw new UnauthorizedException('Missing bearer token');

    try {
      request.user = await this.jwtService.verifyAsync<AuthenticatedUser>(token);
    } catch {
      throw new UnauthorizedException('Invalid or expired token');
    }
    return true;
  }
}
