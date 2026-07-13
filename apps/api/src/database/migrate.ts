/**
 * Migration runner — executed as a release step (one-shot container or CI),
 * never at application boot (09-deployment-and-operations.md).
 *
 *   pnpm --filter @devmind/api db:migrate
 */
import { drizzle } from 'drizzle-orm/node-postgres';
import { migrate } from 'drizzle-orm/node-postgres/migrator';
import { Pool } from 'pg';

async function main(): Promise<void> {
  // Migrations run as the privileged migrator role, never the runtime role.
  const url =
    process.env.API_MIGRATION_DATABASE_URL ?? process.env.API_DATABASE_URL;
  if (!url) {
    throw new Error('API_MIGRATION_DATABASE_URL (or API_DATABASE_URL) is required');
  }

  const pool = new Pool({ connectionString: url, max: 1 });
  try {
    await migrate(drizzle(pool), {
      migrationsFolder: `${__dirname}/migrations`,
      migrationsSchema: 'product',
      migrationsTable: '__migrations',
    });
    console.log('migrations applied');
  } finally {
    await pool.end();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
