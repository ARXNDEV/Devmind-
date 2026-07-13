import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
} from '@nestjs/common';
import { ApiBearerAuth, ApiOkResponse, ApiTags } from '@nestjs/swagger';
import { AuthenticatedUser } from '@/common/auth/auth.types';
import { CurrentUser, RequireRole } from '@/common/auth/decorators';
import { CreateProjectDto, ProjectDto, UpdateProjectDto } from './dto/project.dto';
import { ProjectsService } from './projects.service';

@ApiTags('projects')
@ApiBearerAuth()
@Controller('projects')
export class ProjectsController {
  constructor(private readonly projectsService: ProjectsService) {}

  @Get()
  @RequireRole('viewer')
  @ApiOkResponse({ type: [ProjectDto] })
  list(@CurrentUser() user: AuthenticatedUser): Promise<ProjectDto[]> {
    return this.projectsService.list(user.org);
  }

  @Get(':id')
  @RequireRole('viewer')
  @ApiOkResponse({ type: ProjectDto })
  get(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
  ): Promise<ProjectDto> {
    return this.projectsService.get(user.org, id);
  }

  @Post()
  @RequireRole('engineer')
  @ApiOkResponse({ type: ProjectDto })
  create(
    @CurrentUser() user: AuthenticatedUser,
    @Body() dto: CreateProjectDto,
  ): Promise<ProjectDto> {
    return this.projectsService.create(user.org, dto);
  }

  @Patch(':id')
  @RequireRole('engineer')
  @ApiOkResponse({ type: ProjectDto })
  update(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateProjectDto,
  ): Promise<ProjectDto> {
    return this.projectsService.update(user.org, id, dto);
  }

  @Delete(':id')
  @RequireRole('admin')
  @HttpCode(HttpStatus.NO_CONTENT)
  remove(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
  ): Promise<void> {
    return this.projectsService.remove(user.org, id);
  }
}
