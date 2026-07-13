import {
  createParamDecorator,
  ExecutionContext,
  SetMetadata,
} from '@nestjs/common';
import { AuthenticatedUser, MemberRole } from './auth.types';

export const IS_PUBLIC_KEY = 'devmind:is_public';
/** Opts a route out of the default-deny auth guard. Use sparingly. */
export const Public = () => SetMetadata(IS_PUBLIC_KEY, true);

export const REQUIRED_ROLE_KEY = 'devmind:required_role';
/** Minimum org role required for the route (hierarchy in ROLE_RANK). */
export const RequireRole = (role: MemberRole) =>
  SetMetadata(REQUIRED_ROLE_KEY, role);

export const CurrentUser = createParamDecorator(
  (_data: unknown, ctx: ExecutionContext): AuthenticatedUser => {
    const request = ctx.switchToHttp().getRequest();
    return request.user as AuthenticatedUser;
  },
);
