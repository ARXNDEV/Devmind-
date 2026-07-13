import { memberRole } from '@/database/schema';

export type MemberRole = (typeof memberRole.enumValues)[number];

/** Verified JWT claims attached to every authenticated request. */
export interface AuthenticatedUser {
  /** user id */
  sub: string;
  org: string;
  role: MemberRole;
  email: string;
  name: string;
}

export interface RequestWithUser extends Express.Request {
  user?: AuthenticatedUser;
}

/** Hierarchy used by RolesGuard: a role satisfies any requirement at or below it. */
export const ROLE_RANK: Record<MemberRole, number> = {
  owner: 3,
  admin: 2,
  engineer: 1,
  viewer: 0,
};
