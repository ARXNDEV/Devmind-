import { defineConfig } from 'drizzle-kit';

export default defineConfig({
  schema: './src/database/schema.ts',
  out: './src/database/migrations',
  dialect: 'postgresql',
  migrations: {
    schema: 'product',
    table: '__migrations',
  },
  dbCredentials: {
    // Only used by drizzle-kit CLI (generate/migrate in dev); services read
    // validated env at boot instead.
    url:
      process.env.API_DATABASE_URL ??
      'postgres://api_service:api_dev_password@localhost:5432/devmind',
  },
});
