import { Controller, Get, Inject, ServiceUnavailableException } from '@nestjs/common';
import { ApiExcludeController } from '@nestjs/swagger';
import Redis from 'ioredis';
import { Pool } from 'pg';
import { Public } from '@/common/auth/decorators';
import { REDIS } from '@/common/redis/redis.module';
import { PG_POOL } from '@/database/database.module';

@ApiExcludeController()
@Controller()
export class HealthController {
  constructor(
    @Inject(PG_POOL) private readonly pool: Pool,
    @Inject(REDIS) private readonly redis: Redis,
  ) {}

  /** Liveness: the process is up. Must not touch dependencies. */
  @Public()
  @Get('healthz')
  healthz(): { status: string } {
    return { status: 'ok' };
  }

  /** Readiness: dependencies reachable; used for traffic gating. */
  @Public()
  @Get('readyz')
  async readyz(): Promise<{ status: string; checks: Record<string, string> }> {
    const checks: Record<string, string> = {};
    let healthy = true;

    try {
      await this.pool.query('SELECT 1');
      checks.postgres = 'ok';
    } catch {
      checks.postgres = 'unreachable';
      healthy = false;
    }

    try {
      await this.redis.ping();
      checks.redis = 'ok';
    } catch {
      checks.redis = 'unreachable';
      healthy = false;
    }

    if (!healthy) {
      throw new ServiceUnavailableException({ status: 'degraded', checks });
    }
    return { status: 'ok', checks };
  }
}
