/**
 * Exports the OpenAPI spec to stdout or a file — consumed by CI to generate
 * the TypeScript client in packages/shared-types (ADR-0001: the contract is
 * the artifact; clients are generated, never hand-written).
 *
 *   pnpm --filter @devmind/api openapi:export -- openapi.json
 */
import { NestFactory } from '@nestjs/core';
import { writeFileSync } from 'fs';
import { AppModule } from '../app.module';
import { buildOpenApiDocument } from './setup';

async function main(): Promise<void> {
  // Provide harmless values for boot-time validation; no server is started
  // and nothing connects until a request arrives.
  process.env.API_DATABASE_URL ??= 'postgres://export:export@localhost:5432/export';
  process.env.API_REDIS_URL ??= 'redis://localhost:6379';
  process.env.API_JWT_SECRET ??= 'openapi-export-only-not-a-real-secret-value';
  process.env.INTERNAL_SERVICE_TOKEN ??= 'openapi-export-only';
  process.env.CODE_INTEL_BASE_URL ??= 'http://localhost:8000';
  process.env.WEB_ORIGIN ??= 'http://localhost:3000';
  process.env.API_CREDENTIAL_KEY ??= Buffer.alloc(32).toString('base64');

  const app = await NestFactory.create(AppModule, { logger: false });
  // Mirror main.ts routing so the spec matches the deployed surface.
  app.setGlobalPrefix('api/v1', { exclude: ['healthz', 'readyz'] });
  const document = buildOpenApiDocument(app);
  const out = process.argv[2];
  const json = JSON.stringify(document, null, 2);
  if (out) {
    writeFileSync(out, json);
    console.error(`OpenAPI spec written to ${out}`);
  } else {
    console.log(json);
  }
  await app.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
