import {
  CanActivate,
  ExecutionContext,
  Inject,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { timingSafeEqual } from 'crypto';
import { APP_CONFIG, AppConfig } from '@/config/app-config';

/**
 * Guards the internal callback plane: requests from code-intel must present the
 * shared service token. Constant-time comparison avoids leaking it via timing.
 * Routes using this guard must also be marked @Public to bypass the JWT guard.
 */
@Injectable()
export class InternalTokenGuard implements CanActivate {
  constructor(@Inject(APP_CONFIG) private readonly config: AppConfig) {}

  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest();
    const presented: string = request.headers?.['x-internal-token'] ?? '';
    const expected = this.config.INTERNAL_SERVICE_TOKEN;
    const a = Buffer.from(presented);
    const b = Buffer.from(expected);
    if (a.length !== b.length || !timingSafeEqual(a, b)) {
      throw new UnauthorizedException('Invalid internal service token');
    }
    return true;
  }
}
