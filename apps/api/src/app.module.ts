import { Module } from '@nestjs/common';
import { APP_FILTER, APP_GUARD } from '@nestjs/core';
import { LoggerModule } from 'nestjs-pino';
import { JwtAuthGuard } from './common/auth/jwt-auth.guard';
import { RolesGuard } from './common/auth/roles.guard';
import { ProblemDetailsFilter } from './common/filters/problem-details.filter';
import { CodeIntelModule } from './common/code-intel/code-intel.module';
import { CryptoModule } from './common/crypto/crypto.module';
import { RedisModule } from './common/redis/redis.module';
import { AppConfigModule } from './config/app-config.module';
import { DatabaseModule } from './database/database.module';
import { AuditModule } from './modules/audit/audit.module';
import { HealthModule } from './modules/health/health.module';
import { IdentityModule } from './modules/identity/identity.module';
import { InternalModule } from './modules/internal/internal.module';
import { JobsModule } from './modules/jobs/jobs.module';
import { ProjectsModule } from './modules/projects/projects.module';
import { RepositoriesModule } from './modules/repositories/repositories.module';

@Module({
  imports: [
    AppConfigModule,
    LoggerModule.forRoot({
      pinoHttp: {
        level: process.env.NODE_ENV === 'production' ? 'info' : 'debug',
        // Never log credentials or session material (08-security.md).
        redact: {
          paths: [
            'req.headers.authorization',
            'req.headers.cookie',
            'res.headers["set-cookie"]',
          ],
          censor: '[REDACTED]',
        },
        autoLogging: {
          ignore: (req) => req.url === '/healthz' || req.url === '/readyz',
        },
      },
    }),
    DatabaseModule,
    RedisModule,
    CryptoModule,
    CodeIntelModule,
    AuditModule,
    JobsModule,
    HealthModule,
    IdentityModule,
    ProjectsModule,
    RepositoriesModule,
    InternalModule,
  ],
  providers: [
    // Order matters: authentication before role checks.
    { provide: APP_GUARD, useClass: JwtAuthGuard },
    { provide: APP_GUARD, useClass: RolesGuard },
    { provide: APP_FILTER, useClass: ProblemDetailsFilter },
  ],
})
export class AppModule {}
