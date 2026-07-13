import { INestApplication } from '@nestjs/common';
import { DocumentBuilder, OpenAPIObject, SwaggerModule } from '@nestjs/swagger';

export function buildOpenApiDocument(app: INestApplication): OpenAPIObject {
  const config = new DocumentBuilder()
    .setTitle('DevMind API')
    .setDescription('DevMind AI — public product API')
    .setVersion('1')
    .addBearerAuth()
    .build();
  return SwaggerModule.createDocument(app, config);
}

/** Serves interactive docs at /api/docs (non-production only). */
export function setupOpenApi(app: INestApplication): void {
  SwaggerModule.setup('api/docs', app, buildOpenApiDocument(app));
}
