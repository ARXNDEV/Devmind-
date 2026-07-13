/**
 * End-to-end: real Nest app against real Postgres/Redis (docker compose infra).
 * Covers the Phase 1 exit criteria: register org → login → create project,
 * with tenancy isolation and audit trail asserted.
 */
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import cookieParser from 'cookie-parser';
import { eq } from 'drizzle-orm';
import request from 'supertest';
import { AppModule } from '@/app.module';
import { Database, DB } from '@/database/database.module';
import { auditLog } from '@/database/schema';

const unique = `e2e-${Date.now()}`;

describe('DevMind API (e2e)', () => {
  let app: INestApplication;
  let db: Database;
  let accessToken: string;
  let orgId: string;
  let projectId: string;

  beforeAll(async () => {
    process.env.API_JWT_SECRET ??= 'e2e-test-secret-at-least-32-characters!!';
    process.env.INTERNAL_SERVICE_TOKEN ??= 'e2e-internal-token';
    process.env.API_CREDENTIAL_KEY ??= Buffer.alloc(32).toString('base64');
    process.env.CODE_INTEL_BASE_URL ??= 'http://localhost:8000';
    process.env.WEB_ORIGIN ??= 'http://localhost:3000';
    process.env.API_DATABASE_URL ??=
      'postgres://api_service:api_dev_password@localhost:5432/devmind';
    process.env.API_REDIS_URL ??= 'redis://localhost:6379';

    const moduleRef = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleRef.createNestApplication();
    app.use(cookieParser());
    app.setGlobalPrefix('api/v1', { exclude: ['healthz', 'readyz'] });
    app.useGlobalPipes(
      new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }),
    );
    await app.init();
    db = app.get<Database>(DB);
  });

  afterAll(async () => {
    await app.close();
  });

  it('GET /readyz reports healthy dependencies', async () => {
    const res = await request(app.getHttpServer()).get('/readyz').expect(200);
    expect(res.body.checks.postgres).toBe('ok');
    expect(res.body.checks.redis).toBe('ok');
  });

  it('rejects registration with a weak password', async () => {
    await request(app.getHttpServer())
      .post('/api/v1/auth/register')
      .send({
        organizationName: 'Acme',
        name: 'Ada',
        email: `${unique}@example.com`,
        password: 'short',
      })
      .expect(400);
  });

  it('registers an organization and owner', async () => {
    const res = await request(app.getHttpServer())
      .post('/api/v1/auth/register')
      .send({
        organizationName: `Acme ${unique}`,
        name: 'Ada Lovelace',
        email: `${unique}@example.com`,
        password: 'correct-horse-battery-staple',
      })
      .expect(201);

    expect(res.body.accessToken).toBeDefined();
    expect(res.body.user.role).toBe('owner');
    const cookies = ([] as string[]).concat(res.headers['set-cookie'] ?? []);
    expect(cookies.join(';')).toContain('dm_refresh');
    orgId = res.body.organization.id;
  });

  it('logs in with the registered credentials', async () => {
    const res = await request(app.getHttpServer())
      .post('/api/v1/auth/login')
      .send({
        email: `${unique}@example.com`,
        password: 'correct-horse-battery-staple',
      })
      .expect(200);
    accessToken = res.body.accessToken;
  });

  it('rejects login with a wrong password', async () => {
    await request(app.getHttpServer())
      .post('/api/v1/auth/login')
      .send({ email: `${unique}@example.com`, password: 'wrong-password-value' })
      .expect(401);
  });

  it('rejects unauthenticated access to projects (default-deny)', async () => {
    await request(app.getHttpServer()).get('/api/v1/projects').expect(401);
  });

  it('creates a project', async () => {
    const res = await request(app.getHttpServer())
      .post('/api/v1/projects')
      .set('Authorization', `Bearer ${accessToken}`)
      .send({ name: 'Legacy Billing System', description: 'Pilot project' })
      .expect(201);
    projectId = res.body.id;
    expect(res.body.slug).toBe('legacy-billing-system');
  });

  it('lists only this org’s projects', async () => {
    const res = await request(app.getHttpServer())
      .get('/api/v1/projects')
      .set('Authorization', `Bearer ${accessToken}`)
      .expect(200);
    expect(res.body).toHaveLength(1);
    expect(res.body[0].id).toBe(projectId);
  });

  it('a second org cannot see the first org’s project (tenancy)', async () => {
    const other = await request(app.getHttpServer())
      .post('/api/v1/auth/register')
      .send({
        organizationName: `Rival ${unique}`,
        name: 'Grace Hopper',
        email: `${unique}-rival@example.com`,
        password: 'correct-horse-battery-staple',
      })
      .expect(201);

    const list = await request(app.getHttpServer())
      .get('/api/v1/projects')
      .set('Authorization', `Bearer ${other.body.accessToken}`)
      .expect(200);
    expect(list.body).toHaveLength(0);

    await request(app.getHttpServer())
      .get(`/api/v1/projects/${projectId}`)
      .set('Authorization', `Bearer ${other.body.accessToken}`)
      .expect(404);
  });

  it('wrote audit entries for register, login, and project creation', async () => {
    const entries = await db
      .select()
      .from(auditLog)
      .where(eq(auditLog.orgId, orgId));
    const actions = entries.map((e) => e.action);
    expect(actions).toContain('auth.register');
    expect(actions).toContain('auth.login');
    expect(actions.some((a) => a.startsWith('POST') && a.includes('projects'))).toBe(true);
  });
});
