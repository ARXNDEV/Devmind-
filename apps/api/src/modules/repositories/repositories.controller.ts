import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseUUIDPipe,
  Post,
  Query,
} from '@nestjs/common';
import { ApiBearerAuth, ApiTags } from '@nestjs/swagger';
import { AuthenticatedUser } from '@/common/auth/auth.types';
import { CurrentUser, RequireRole } from '@/common/auth/decorators';
import { CodeIntelClient } from '@/common/code-intel/code-intel.client';
import { CreateRepositoryDto, RepositoryDto } from './dto/repository.dto';
import { RepositoriesService } from './repositories.service';

@ApiTags('repositories')
@ApiBearerAuth()
@Controller()
export class RepositoriesController {
  constructor(
    private readonly repositories: RepositoriesService,
    private readonly codeIntel: CodeIntelClient,
  ) {}

  @Get('projects/:projectId/repositories')
  @RequireRole('viewer')
  list(
    @CurrentUser() user: AuthenticatedUser,
    @Param('projectId', ParseUUIDPipe) projectId: string,
  ): Promise<RepositoryDto[]> {
    return this.repositories.list(user.org, projectId);
  }

  @Post('projects/:projectId/repositories')
  @RequireRole('engineer')
  create(
    @CurrentUser() user: AuthenticatedUser,
    @Param('projectId', ParseUUIDPipe) projectId: string,
    @Body() dto: CreateRepositoryDto,
  ): Promise<RepositoryDto> {
    return this.repositories.create(user.org, projectId, dto);
  }

  @Get('repositories/:id')
  @RequireRole('viewer')
  get(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
  ): Promise<RepositoryDto> {
    return this.repositories.get(user.org, id);
  }

  @Delete('repositories/:id')
  @RequireRole('admin')
  @HttpCode(HttpStatus.NO_CONTENT)
  remove(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
  ): Promise<void> {
    return this.repositories.remove(user.org, id);
  }

  @Post('repositories/:id/index')
  @RequireRole('engineer')
  @HttpCode(HttpStatus.ACCEPTED)
  index(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
  ): Promise<{ jobId: string }> {
    return this.repositories.triggerIndex(user.org, id);
  }

  @Get('repositories/:id/tree')
  @RequireRole('viewer')
  async tree(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
  ): Promise<unknown> {
    await this.repositories.get(user.org, id); // authorize + existence
    return this.codeIntel.tree(id, user.org);
  }

  @Get('repositories/:id/symbols')
  @RequireRole('viewer')
  async symbols(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Query('path') path: string,
  ): Promise<unknown> {
    await this.repositories.get(user.org, id);
    return this.codeIntel.fileSymbols(id, path, user.org);
  }

  @Get('repositories/:id/impact')
  @RequireRole('viewer')
  async impact(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Query('fqn') fqn: string,
    @Query('path') path: string,
  ): Promise<unknown> {
    await this.repositories.get(user.org, id);
    return this.codeIntel.impact({ repoId: id, fqn, path }, user.org);
  }
}
