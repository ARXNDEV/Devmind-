import { AuthenticatedUser } from './auth.types';

/**
 * Default identity used when AUTH_DISABLED=true. This does NOT remove the
 * identity layer (org scoping, roles, audit all still function) — it removes
 * the login *gate* by auto-authenticating every request as this seeded admin.
 * Intended for single-tenant internal deployments; leave AUTH_DISABLED unset
 * (false) for any multi-tenant or externally-reachable deployment.
 */
export const DEFAULT_ORG_ID = '00000000-0000-4000-8000-000000000001';
export const DEFAULT_USER_ID = '00000000-0000-4000-8000-000000000002';

export const DEFAULT_CLAIMS: AuthenticatedUser = {
  sub: DEFAULT_USER_ID,
  org: DEFAULT_ORG_ID,
  role: 'owner',
  email: 'admin@devmind.local',
  name: 'DevMind Admin',
};

export const DEFAULT_ORG_NAME = 'DevMind';
export const DEFAULT_ORG_SLUG = 'devmind';
