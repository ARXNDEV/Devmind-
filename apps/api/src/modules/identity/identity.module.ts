import { Module } from '@nestjs/common';
import { JwtModule } from '@nestjs/jwt';
import { APP_CONFIG, AppConfig } from '@/config/app-config';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';

@Module({
  imports: [
    // global: JwtService is needed by the app-wide JwtAuthGuard.
    JwtModule.registerAsync({
      global: true,
      inject: [APP_CONFIG],
      useFactory: (config: AppConfig) => ({
        secret: config.API_JWT_SECRET,
        signOptions: { issuer: 'devmind-api' },
        verifyOptions: { issuer: 'devmind-api' },
      }),
    }),
  ],
  controllers: [AuthController],
  providers: [AuthService],
})
export class IdentityModule {}
