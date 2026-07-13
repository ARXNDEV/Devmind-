import { loadAppConfig } from './app-config';

const VALID_ENV = {
  API_DATABASE_URL: 'postgres://u:p@localhost:5432/devmind',
  API_REDIS_URL: 'redis://localhost:6379',
  API_JWT_SECRET: 'a-secret-that-is-definitely-32-chars!!',
  INTERNAL_SERVICE_TOKEN: 'internal-token-16chars',
  CODE_INTEL_BASE_URL: 'http://localhost:8000',
  WEB_ORIGIN: 'http://localhost:3000',
  API_CREDENTIAL_KEY: Buffer.alloc(32).toString('base64'),
};

describe('loadAppConfig', () => {
  it('parses a valid environment with defaults applied', () => {
    const config = loadAppConfig(VALID_ENV as NodeJS.ProcessEnv);
    expect(config.API_PORT).toBe(4000);
    expect(config.API_JWT_ACCESS_TTL).toBe(900);
    expect(config.NODE_ENV).toBe('development');
  });

  it('fails fast on a missing required variable', () => {
    const { API_JWT_SECRET: _omitted, ...rest } = VALID_ENV;
    expect(() => loadAppConfig(rest as NodeJS.ProcessEnv)).toThrow(
      /API_JWT_SECRET/,
    );
  });

  it('rejects a weak JWT secret', () => {
    expect(() =>
      loadAppConfig({ ...VALID_ENV, API_JWT_SECRET: 'short' } as NodeJS.ProcessEnv),
    ).toThrow(/32 chars/);
  });

  it('rejects a non-postgres database URL', () => {
    expect(() =>
      loadAppConfig({
        ...VALID_ENV,
        API_DATABASE_URL: 'mysql://u:p@localhost/x',
      } as NodeJS.ProcessEnv),
    ).toThrow(/Invalid configuration/);
  });
});
