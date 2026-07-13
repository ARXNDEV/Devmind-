import { z } from 'zod';

/**
 * All configuration enters through this schema. A missing or malformed
 * variable stops the process at boot — services must never limp along on
 * defaults in production, so defaults exist only where they are safe in
 * every environment.
 */
const appConfigSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  API_PORT: z.coerce.number().int().min(1).max(65535).default(4000),
  API_DATABASE_URL: z.string().url().startsWith('postgres'),
  API_REDIS_URL: z.string().url().startsWith('redis'),
  API_JWT_SECRET: z.string().min(32, 'JWT secret must be at least 32 chars'),
  API_JWT_ACCESS_TTL: z.coerce.number().int().positive().default(900),
  API_JWT_REFRESH_TTL: z.coerce.number().int().positive().default(1209600),
  INTERNAL_SERVICE_TOKEN: z.string().min(16),
  CODE_INTEL_BASE_URL: z.string().url(),
  WEB_ORIGIN: z.string().url(),
  // When true, the login gate is bypassed and every request runs as a seeded
  // default admin (single-tenant internal use only). See common/auth/dev-auth.
  AUTH_DISABLED: z
    .enum(['true', 'false'])
    .default('false')
    .transform((v) => v === 'true'),
  // AES-256-GCM key for encrypting integration credentials at rest
  // (08-security.md). Must base64-decode to exactly 32 bytes.
  API_CREDENTIAL_KEY: z
    .string()
    .refine(
      (v) => {
        try {
          return Buffer.from(v, 'base64').length === 32;
        } catch {
          return false;
        }
      },
      { message: 'API_CREDENTIAL_KEY must be base64 for 32 bytes' },
    ),
});

export type AppConfig = Readonly<z.infer<typeof appConfigSchema>>;

export const APP_CONFIG = Symbol('APP_CONFIG');

export function loadAppConfig(env: NodeJS.ProcessEnv = process.env): AppConfig {
  const result = appConfigSchema.safeParse(env);
  if (!result.success) {
    const details = result.error.issues
      .map((i) => `  ${i.path.join('.')}: ${i.message}`)
      .join('\n');
    throw new Error(`Invalid configuration:\n${details}`);
  }
  return Object.freeze(result.data);
}
