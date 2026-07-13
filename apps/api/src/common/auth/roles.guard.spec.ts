import { ExecutionContext, ForbiddenException } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { AuthenticatedUser } from './auth.types';
import { REQUIRED_ROLE_KEY } from './decorators';
import { RolesGuard } from './roles.guard';

function contextWithUser(user?: Partial<AuthenticatedUser>): ExecutionContext {
  return {
    getHandler: () => ({}),
    getClass: () => ({}),
    switchToHttp: () => ({ getRequest: () => ({ user }) }),
  } as unknown as ExecutionContext;
}

describe('RolesGuard', () => {
  let reflector: Reflector;
  let guard: RolesGuard;

  beforeEach(() => {
    reflector = new Reflector();
    guard = new RolesGuard(reflector);
  });

  function requireRole(role: string | undefined): void {
    jest
      .spyOn(reflector, 'getAllAndOverride')
      .mockImplementation((key) =>
        key === REQUIRED_ROLE_KEY ? role : undefined,
      );
  }

  it('allows routes without a role requirement', () => {
    requireRole(undefined);
    expect(guard.canActivate(contextWithUser({ role: 'viewer' }))).toBe(true);
  });

  it('allows an exact role match', () => {
    requireRole('engineer');
    expect(guard.canActivate(contextWithUser({ role: 'engineer' }))).toBe(true);
  });

  it('allows a higher role in the hierarchy', () => {
    requireRole('engineer');
    expect(guard.canActivate(contextWithUser({ role: 'owner' }))).toBe(true);
  });

  it('rejects a lower role', () => {
    requireRole('admin');
    expect(() => guard.canActivate(contextWithUser({ role: 'engineer' }))).toThrow(
      ForbiddenException,
    );
  });

  it('rejects when no user is present', () => {
    requireRole('viewer');
    expect(() => guard.canActivate(contextWithUser(undefined))).toThrow(
      ForbiddenException,
    );
  });
});
