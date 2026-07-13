import {
  Controller,
  Get,
  Inject,
  MessageEvent,
  Param,
  ParseUUIDPipe,
  Sse,
} from '@nestjs/common';
import { ApiBearerAuth, ApiTags } from '@nestjs/swagger';
import Redis from 'ioredis';
import { Observable } from 'rxjs';
import { AuthenticatedUser } from '@/common/auth/auth.types';
import { CurrentUser, RequireRole } from '@/common/auth/decorators';
import { REDIS } from '@/common/redis/redis.module';
import { JobsService, JobView } from './jobs.service';

@ApiTags('jobs')
@ApiBearerAuth()
@Controller('jobs')
export class JobsController {
  constructor(
    private readonly jobsService: JobsService,
    @Inject(REDIS) private readonly redis: Redis,
  ) {}

  @Get(':id')
  @RequireRole('viewer')
  get(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
  ): Promise<JobView> {
    return this.jobsService.get(user.org, id);
  }

  /**
   * Streams progress events for a job. Emits the current status immediately,
   * then relays worker progress from Redis pub/sub, closing on a terminal
   * event. A dedicated subscriber connection is used and torn down on unsubscribe.
   */
  @Sse(':id/events')
  @RequireRole('viewer')
  events(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
  ): Observable<MessageEvent> {
    return new Observable<MessageEvent>((subscriber) => {
      const channel = `events:job:${id}`;
      const sub = this.redis.duplicate();
      let closed = false;

      const close = () => {
        if (closed) return;
        closed = true;
        void sub.unsubscribe(channel).catch(() => undefined);
        void sub.quit().catch(() => undefined);
      };

      // Authorize + send the current state before streaming live events.
      this.jobsService
        .get(user.org, id)
        .then((job) => {
          subscriber.next({ type: 'job.status', data: job });
          if (job.status === 'succeeded' || job.status === 'failed') {
            subscriber.complete();
            close();
            return;
          }
          sub.on('message', (_ch, message) => {
            try {
              const event = JSON.parse(message) as {
                type: string;
                data: string | object;
              };
              subscriber.next({ type: event.type, data: event.data });
            } catch {
              /* ignore malformed messages */
            }
          });
          void sub.subscribe(channel);
        })
        .catch((err) => subscriber.error(err));

      return close;
    });
  }
}
