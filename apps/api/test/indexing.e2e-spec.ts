/**
 * Full async-job flow across services:
 *   register → create project → create repository → POST /index (202, jobId)
 *   → code-intel runs the pipeline → signed callback → job succeeds.
 *
 * Requires the code-intel service (API + worker) running against the same
 * infra. Self-skips if code-intel is unreachable so the core suite stays
 * independent.
 */
import { INestApplication, ValidationPipe } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import cookieParser from 'cookie-parser';
import request from 'supertest';
import { AppModule } from '@/app.module';

const unique = `idx-${Date.now()}`;
const CODE_INTEL = process.env.CODE_INTEL_BASE_URL ?? 'http://localhost:8000';

async function codeIntelUp(): Promise<boolean> {
  try {
    const res = await fetch(`${CODE_INTEL}/healthz`);
    return res.ok;
  } catch {
    return false;
  }
}

describe('Repository indexing (e2e)', () => {
  let app: INestApplication;
  let token: string;
  let repoId: string;
  let available = false;

  beforeAll(async () => {
    available = await codeIntelUp();
    if (!available) return;

    // Match the running services' config; run with `.env` sourced so tokens
    // align with the live code-intel + api on :4000 that receives callbacks.
    process.env.API_DATABASE_URL ??=
      'postgres://api_service:api_dev_password@localhost:5432/devmind';
    process.env.API_REDIS_URL ??= 'redis://localhost:6379';
    process.env.API_JWT_SECRET ??= 'e2e-test-secret-at-least-32-characters!!';
    process.env.INTERNAL_SERVICE_TOKEN ??= 'e2e-internal-token';
    process.env.API_CREDENTIAL_KEY ??= Buffer.alloc(32).toString('base64');
    process.env.CODE_INTEL_BASE_URL ??= 'http://localhost:8000';
    process.env.WEB_ORIGIN ??= 'http://localhost:3000';

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

    const reg = await request(app.getHttpServer())
      .post('/api/v1/auth/register')
      .send({
        organizationName: `Idx ${unique}`,
        name: 'Indexer',
        email: `${unique}@example.com`,
        password: 'correct-horse-battery-staple',
      })
      .expect(201);
    token = reg.body.accessToken;

    const project = await request(app.getHttpServer())
      .post('/api/v1/projects')
      .set('Authorization', `Bearer ${token}`)
      .send({ name: 'Engine Repo' })
      .expect(201);

    // Index this very repository from its local checkout.
    const repo = await request(app.getHttpServer())
      .post(`/api/v1/projects/${project.body.id}/repositories`)
      .set('Authorization', `Bearer ${token}`)
      .send({
        name: 'devmind',
        provider: 'local',
        cloneUrl: process.env.INDEX_SOURCE_PATH ?? process.cwd(),
      })
      .expect(201);
    repoId = repo.body.id;
    expect(repo.body.hasCredentials).toBe(false);
  });

  afterAll(async () => {
    if (app) await app.close();
  });

  it('runs an index job to completion via callback', async () => {
    if (!available) {
      console.warn('code-intel unavailable — skipping');
      return;
    }

    const res = await request(app.getHttpServer())
      .post(`/api/v1/repositories/${repoId}/index`)
      .set('Authorization', `Bearer ${token}`)
      .expect(202);
    const jobId = res.body.jobId;
    expect(jobId).toBeDefined();

    // Poll the job until terminal (callback-driven), up to ~60s.
    let status = 'queued';
    for (let i = 0; i < 60; i++) {
      const job = await request(app.getHttpServer())
        .get(`/api/v1/jobs/${jobId}`)
        .set('Authorization', `Bearer ${token}`)
        .expect(200);
      status = job.body.status;
      if (status === 'succeeded' || status === 'failed') break;
      await new Promise((r) => setTimeout(r, 1000));
    }
    expect(status).toBe('succeeded');

    // Repository row reflects the terminal state.
    const repo = await request(app.getHttpServer())
      .get(`/api/v1/repositories/${repoId}`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    expect(repo.body.indexStatus).toBe('ready');
  }, 90_000);
});
