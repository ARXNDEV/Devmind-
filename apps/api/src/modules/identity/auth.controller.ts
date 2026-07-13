import {
  Body,
  Controller,
  HttpCode,
  HttpStatus,
  Inject,
  Post,
  Req,
  Res,
} from '@nestjs/common';
import { ApiOkResponse, ApiTags } from '@nestjs/swagger';
import { Request, Response } from 'express';
import { Public } from '@/common/auth/decorators';
import { APP_CONFIG, AppConfig } from '@/config/app-config';
import { AuthService, IssuedAuth } from './auth.service';
import { AuthResponseDto, LoginDto, RegisterDto } from './dto/auth.dto';

export const REFRESH_COOKIE = 'dm_refresh';

@ApiTags('auth')
@Controller('auth')
export class AuthController {
  constructor(
    private readonly authService: AuthService,
    @Inject(APP_CONFIG) private readonly config: AppConfig,
  ) {}

  @Public()
  @Post('register')
  @ApiOkResponse({ type: AuthResponseDto })
  async register(
    @Body() dto: RegisterDto,
    @Res({ passthrough: true }) res: Response,
  ): Promise<AuthResponseDto> {
    return this.finish(await this.authService.register(dto), res);
  }

  @Public()
  @HttpCode(HttpStatus.OK)
  @Post('login')
  @ApiOkResponse({ type: AuthResponseDto })
  async login(
    @Body() dto: LoginDto,
    @Res({ passthrough: true }) res: Response,
  ): Promise<AuthResponseDto> {
    return this.finish(await this.authService.login(dto), res);
  }

  @Public()
  @HttpCode(HttpStatus.OK)
  @Post('refresh')
  @ApiOkResponse({ type: AuthResponseDto })
  async refresh(
    @Req() req: Request,
    @Res({ passthrough: true }) res: Response,
  ): Promise<AuthResponseDto> {
    // Login-gate bypass: hand the web a valid session for the default admin so
    // it authenticates on load and never shows the login page.
    if (this.config.AUTH_DISABLED) {
      return this.finish(await this.authService.devAuth(), res);
    }
    const token: string | undefined = req.cookies?.[REFRESH_COOKIE];
    return this.finish(await this.authService.refresh(token ?? ''), res);
  }

  @Public()
  @HttpCode(HttpStatus.NO_CONTENT)
  @Post('logout')
  async logout(
    @Req() req: Request,
    @Res({ passthrough: true }) res: Response,
  ): Promise<void> {
    await this.authService.logout(req.cookies?.[REFRESH_COOKIE]);
    res.clearCookie(REFRESH_COOKIE, { path: '/api/v1/auth' });
  }

  /** Sets the rotating refresh cookie; the body carries only the access token. */
  private finish(issued: IssuedAuth, res: Response): AuthResponseDto {
    res.cookie(REFRESH_COOKIE, issued.refreshToken, {
      httpOnly: true,
      sameSite: 'strict',
      secure: this.config.NODE_ENV === 'production',
      path: '/api/v1/auth',
      expires: issued.refreshExpiresAt,
    });
    return issued.response;
  }
}
