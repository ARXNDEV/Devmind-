import { RequestMethod, ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { NestExpressApplication } from '@nestjs/platform-express';
import cookieParser from 'cookie-parser';
import helmet from 'helmet';
import { Logger, LoggerErrorInterceptor } from 'nestjs-pino';
import { AppModule } from './app.module';
import { APP_CONFIG, AppConfig } from './config/app-config';
import { setupOpenApi } from './openapi/setup';

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create<NestExpressApplication>(AppModule, {
    bufferLogs: true,
  });
  const config = app.get<AppConfig>(APP_CONFIG);

  app.useLogger(app.get(Logger));
  app.useGlobalInterceptors(new LoggerErrorInterceptor());
  app.use(helmet());
  app.use(cookieParser());
  app.enableCors({
    origin: config.WEB_ORIGIN,
    credentials: true,
  });
  // The internal service plane (callbacks from code-intel) and health probes
  // live outside the public /api/v1 namespace (07-api-contracts.md).
  app.setGlobalPrefix('api/v1', {
    exclude: [
      { path: 'healthz', method: RequestMethod.GET },
      { path: 'readyz', method: RequestMethod.GET },
      {
        path: 'internal/v1/callbacks/job-status',
        method: RequestMethod.POST,
      },
    ],
  });
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );
  app.enableShutdownHooks();

  if (config.NODE_ENV !== 'production') {
    setupOpenApi(app);
  }

  await app.listen(config.API_PORT);
}

void bootstrap();
