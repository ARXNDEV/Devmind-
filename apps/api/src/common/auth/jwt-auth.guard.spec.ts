import { ExecutionContext, UnauthorizedException } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { JwtService } from '@nestjs/jwt';
import { IS_PUBLIC_KEY } from './decorators';
import { JwtAuthGuard } from './jwt-auth.guard';

function contextWithAuthHeader(header?: string): ExecutionContext {
  const request: Record<string, unknown> = {
    headers: header ? { authorization: header } : {},
  };
  return {
    getHandler: () => ({}),
    getClass: () => ({}),
    switchToHttp: () => ({ getRequest: () => request }),
  } as unknown as ExecutionContext;
}

describe('JwtAuthGuard', () => {
  let jwtService: JwtService;
  let reflector: Reflector;
  let guard: JwtAuthGuard;

  beforeEach(() => {
    jwtService = new JwtService({ secret: 'unit-test-secret-at-least-32-chars!!' });
    reflector = new Reflector();
    guard = new JwtAuthGuard(jwtService, reflector, {
      AUTH_DISABLED: false,
    } as never);
  });

  function markPublic(isPublic: boolean): void {
    jest
      .spyOn(reflector, 'getAllAndOverride')
      .mockImplementation((key) => (key === IS_PUBLIC_KEY ? isPublic : undefined));
  }

  it('allows @Public routes without a token', async () => {
    markPublic(true);
    await expect(guard.canActivate(contextWithAuthHeader())).resolves.toBe(true);
  });

  it('rejects missing bearer token (default-deny)', async () => {
    markPublic(false);
    await expect(guard.canActivate(contextWithAuthHeader())).rejects.toThrow(
      UnauthorizedException,
    );
  });

  it('rejects a malformed token', async () => {
    markPublic(false);
    await expect(
      guard.canActivate(contextWithAuthHeader('Bearer not-a-jwt')),
    ).rejects.toThrow(UnauthorizedException);
  });

  it('accepts a valid token and attaches claims', async () => {
    markPublic(false);
    const token = await jwtService.signAsync({ sub: 'u1', org: 'o1', role: 'owner' });
    const ctx = contextWithAuthHeader(`Bearer ${token}`);
    await expect(guard.canActivate(ctx)).resolves.toBe(true);
    const request = ctx.switchToHttp().getRequest() as { user?: { sub: string } };
    expect(request.user?.sub).toBe('u1');
  });
});
