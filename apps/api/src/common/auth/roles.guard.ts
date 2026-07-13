import {
  CanActivate,
  ExecutionContext,
  ForbiddenException,
  Injectable,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { AuthenticatedUser, MemberRole, ROLE_RANK } from './auth.types';
import { REQUIRED_ROLE_KEY } from './decorators';

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private readonly reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const required = this.reflector.getAllAndOverride<MemberRole | undefined>(
      REQUIRED_ROLE_KEY,
      [context.getHandler(), context.getClass()],
    );
    if (!required) return true;

    const user: AuthenticatedUser | undefined = context
      .switchToHttp()
      .getRequest().user;
    // Public routes have no user; a role requirement on a public route is a bug.
    if (!user) throw new ForbiddenException('Insufficient role');

    if (ROLE_RANK[user.role] < ROLE_RANK[required]) {
      throw new ForbiddenException(`Requires ${required} role or above`);
    }
    return true;
  }
}
