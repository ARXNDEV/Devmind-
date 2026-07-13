import {
  CallHandler,
  ExecutionContext,
  Injectable,
  NestInterceptor,
} from '@nestjs/common';
import { Observable, tap } from 'rxjs';
import { AuthenticatedUser } from '@/common/auth/auth.types';
import { AuditService } from './audit.service';

const MUTATING_METHODS = new Set(['POST', 'PATCH', 'PUT', 'DELETE']);
/** Auth flows are audited explicitly by AuthService with richer context. */
const EXCLUDED_PREFIXES = ['/api/v1/auth'];

/**
 * Global interceptor: every successful mutating request produces an audit
 * row. Request/response bodies are deliberately never recorded — route,
 * params, and status only (08-security.md).
 */
@Injectable()
export class AuditInterceptor implements NestInterceptor {
  constructor(private readonly auditService: AuditService) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const request = context.switchToHttp().getRequest();
    const method: string = request.method;
    const url: string = request.url ?? '';

    if (
      !MUTATING_METHODS.has(method) ||
      EXCLUDED_PREFIXES.some((p) => url.startsWith(p))
    ) {
      return next.handle();
    }

    return next.handle().pipe(
      tap(() => {
        const user: AuthenticatedUser | undefined = request.user;
        if (!user) return; // public mutating routes handle their own auditing
        const response = context.switchToHttp().getResponse();
        const resourceType = url
          .replace(/^\/api\/v1\//, '')
          .split('/')[0]
          ?.split('?')[0];
        void this.auditService.record({
          orgId: user.org,
          actorType: 'user',
          actorId: user.sub,
          action: `${method} ${request.route?.path ?? url}`,
          resourceType: resourceType || 'unknown',
          resourceId: request.params?.id,
          metadata: { statusCode: response.statusCode },
        });
      }),
    );
  }
}
