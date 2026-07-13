import {
  index,
  integer,
  jsonb,
  pgSchema,
  text,
  timestamp,
  uniqueIndex,
  uuid,
} from 'drizzle-orm/pg-core';

/**
 * Product schema — owned exclusively by apps/api (ADR-0003).
 * Conventions: UUIDv7 ids generated app-side; org_id denormalized onto every
 * tenant-scoped table so tenancy filters never require joins (02-domain-model).
 */
export const product = pgSchema('product');

export const memberRole = product.enum('member_role', [
  'owner',
  'admin',
  'engineer',
  'viewer',
]);

export const jobKind = product.enum('job_kind', [
  'index',
  'agent_run',
  'patch_gen',
  'verification',
  'log_import',
]);

export const repoProvider = product.enum('repo_provider', [
  'github',
  'gitlab',
  'bitbucket',
  'generic_git',
  'local',
]);

export const repoIndexStatus = product.enum('repo_index_status', [
  'pending',
  'indexing',
  'ready',
  'failed',
  'stale',
]);

export const jobStatus = product.enum('job_status', [
  'queued',
  'running',
  'succeeded',
  'failed',
  'cancelled',
]);

export const actorType = product.enum('actor_type', [
  'user',
  'api_key',
  'agent',
  'system',
]);

export const organizations = product.table('organizations', {
  id: uuid('id').primaryKey(),
  name: text('name').notNull(),
  slug: text('slug').notNull().unique(),
  settings: jsonb('settings').notNull().default({}),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
});

export const users = product.table(
  'users',
  {
    id: uuid('id').primaryKey(),
    orgId: uuid('org_id')
      .notNull()
      .references(() => organizations.id),
    email: text('email').notNull(),
    name: text('name').notNull(),
    passwordHash: text('password_hash'),
    ssoSubject: text('sso_subject'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [uniqueIndex('users_org_email_uq').on(t.orgId, t.email)],
);

export const memberships = product.table(
  'memberships',
  {
    userId: uuid('user_id')
      .notNull()
      .references(() => users.id),
    orgId: uuid('org_id')
      .notNull()
      .references(() => organizations.id),
    role: memberRole('role').notNull(),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [uniqueIndex('memberships_user_org_uq').on(t.userId, t.orgId)],
);

/** Refresh-token sessions; tokens stored as SHA-256 hashes only. */
export const sessions = product.table(
  'sessions',
  {
    id: uuid('id').primaryKey(),
    userId: uuid('user_id')
      .notNull()
      .references(() => users.id),
    orgId: uuid('org_id').notNull(),
    refreshTokenHash: text('refresh_token_hash').notNull(),
    expiresAt: timestamp('expires_at', { withTimezone: true }).notNull(),
    revokedAt: timestamp('revoked_at', { withTimezone: true }),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [index('sessions_user_idx').on(t.userId)],
);

export const projects = product.table(
  'projects',
  {
    id: uuid('id').primaryKey(),
    orgId: uuid('org_id')
      .notNull()
      .references(() => organizations.id),
    name: text('name').notNull(),
    slug: text('slug').notNull(),
    description: text('description'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [uniqueIndex('projects_org_slug_uq').on(t.orgId, t.slug)],
);

export const repositories = product.table(
  'repositories',
  {
    id: uuid('id').primaryKey(),
    orgId: uuid('org_id')
      .notNull()
      .references(() => organizations.id),
    projectId: uuid('project_id')
      .notNull()
      .references(() => projects.id),
    name: text('name').notNull(),
    provider: repoProvider('provider').notNull(),
    cloneUrl: text('clone_url').notNull(),
    defaultBranch: text('default_branch').notNull().default('main'),
    // AES-256-GCM ciphertext of the clone credential; write-only via the API,
    // decrypted only inside code-intel at clone time (08-security.md).
    encryptedCredentials: text('encrypted_credentials'),
    indexedCommitSha: text('indexed_commit_sha'),
    indexStatus: repoIndexStatus('index_status').notNull().default('pending'),
    lastIndexedAt: timestamp('last_indexed_at', { withTimezone: true }),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [index('repositories_project_idx').on(t.projectId)],
);

/** Source of truth for all async work, including tasks executed by code-intel. */
export const jobs = product.table(
  'jobs',
  {
    id: uuid('id').primaryKey(),
    orgId: uuid('org_id').notNull(),
    kind: jobKind('kind').notNull(),
    subjectType: text('subject_type').notNull(),
    subjectId: uuid('subject_id').notNull(),
    status: jobStatus('status').notNull().default('queued'),
    progress: jsonb('progress').notNull().default({}),
    error: jsonb('error'),
    externalTaskId: text('external_task_id'),
    attempt: integer('attempt').notNull().default(0),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    startedAt: timestamp('started_at', { withTimezone: true }),
    finishedAt: timestamp('finished_at', { withTimezone: true }),
  },
  (t) => [index('jobs_org_status_idx').on(t.orgId, t.status)],
);

export const auditLog = product.table(
  'audit_log',
  {
    id: uuid('id').primaryKey(),
    orgId: uuid('org_id').notNull(),
    actorType: actorType('actor_type').notNull(),
    actorId: text('actor_id').notNull(),
    action: text('action').notNull(),
    resourceType: text('resource_type').notNull(),
    resourceId: text('resource_id'),
    metadata: jsonb('metadata').notNull().default({}),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [index('audit_org_created_idx').on(t.orgId, t.createdAt)],
);
