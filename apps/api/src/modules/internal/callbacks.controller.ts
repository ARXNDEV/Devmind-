import {
  Body,
  Controller,
  HttpCode,
  HttpStatus,
  Inject,
  Post,
  UseGuards,
} from '@nestjs/common';
import { ApiExcludeController } from '@nestjs/swagger';
import { eq } from 'drizzle-orm';
import Redis from 'ioredis';
import { Public } from '@/common/auth/decorators';
import { InternalTokenGuard } from '@/common/auth/internal-token.guard';
import { REDIS } from '@/common/redis/redis.module';
import { Database, DB } from '@/database/database.module';
import { repositories } from '@/database/schema';
import { JobsService } from '@/modules/jobs/jobs.service';
import { JobStatusCallbackDto } from './dto/callback.dto';

/**
 * The inbound half of the internal contract (07-api-contracts.md): code-intel
 * reports durable job status here. Public to the JWT guard, but gated by the
 * shared service token.
 */
@ApiExcludeController()
@Public()
@UseGuards(InternalTokenGuard)
@Controller('internal/v1/callbacks')
export class CallbacksController {
  constructor(
    private readonly jobs: JobsService,
    @Inject(DB) private readonly db: Database,
    @Inject(REDIS) private readonly redis: Redis,
  ) {}

  @Post('job-status')
  @HttpCode(HttpStatus.NO_CONTENT)
  async jobStatus(@Body() dto: JobStatusCallbackDto): Promise<void> {
    const job = await this.jobs.applyStatus({
      id: dto.jobId,
      status: dto.status,
      result: dto.result ?? undefined,
      error: dto.error ?? undefined,
      externalTaskId: dto.externalTaskId,
    });
    if (!job) return;

    // Reflect terminal index outcomes onto the repository row.
    if (job.kind === 'index' && job.subjectType === 'repository') {
      if (dto.status === 'succeeded') {
        const commitSha =
          (dto.result?.commitSha as string | undefined) ?? null;
        await this.db
          .update(repositories)
          .set({
            indexStatus: 'ready',
            indexedCommitSha: commitSha,
            lastIndexedAt: new Date(),
          })
          .where(eq(repositories.id, job.subjectId));
      } else if (dto.status === 'failed') {
        await this.db
          .update(repositories)
          .set({ indexStatus: 'failed' })
          .where(eq(repositories.id, job.subjectId));
      }
    }

    // Nudge any live SSE subscribers with the terminal status.
    if (dto.status === 'succeeded' || dto.status === 'failed') {
      await this.redis.publish(
        `events:job:${dto.jobId}`,
        JSON.stringify({ type: 'job.status', data: job }),
      );
    }
  }
}
