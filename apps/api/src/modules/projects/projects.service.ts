import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { and, desc, eq } from 'drizzle-orm';
import { randomBytes } from 'crypto';
import { uuidv7 } from 'uuidv7';
import { Database, DB } from '@/database/database.module';
import { projects } from '@/database/schema';
import { CreateProjectDto, ProjectDto, UpdateProjectDto } from './dto/project.dto';

/**
 * Every query is org-scoped at the WHERE clause — orgId comes from verified
 * JWT claims, never from client input (08-security.md tenancy rules).
 */
@Injectable()
export class ProjectsService {
  constructor(@Inject(DB) private readonly db: Database) {}

  async list(orgId: string): Promise<ProjectDto[]> {
    const rows = await this.db
      .select()
      .from(projects)
      .where(eq(projects.orgId, orgId))
      .orderBy(desc(projects.createdAt));
    return rows.map((r) => this.toDto(r));
  }

  async get(orgId: string, id: string): Promise<ProjectDto> {
    const [row] = await this.db
      .select()
      .from(projects)
      .where(and(eq(projects.orgId, orgId), eq(projects.id, id)))
      .limit(1);
    if (!row) throw new NotFoundException('Project not found');
    return this.toDto(row);
  }

  async create(orgId: string, dto: CreateProjectDto): Promise<ProjectDto> {
    const id = uuidv7();
    const [row] = await this.db
      .insert(projects)
      .values({
        id,
        orgId,
        name: dto.name,
        slug: await this.uniqueSlug(orgId, dto.name),
        description: dto.description,
      })
      .returning();
    return this.toDto(row);
  }

  async update(orgId: string, id: string, dto: UpdateProjectDto): Promise<ProjectDto> {
    const [row] = await this.db
      .update(projects)
      .set({
        ...(dto.name !== undefined ? { name: dto.name } : {}),
        ...(dto.description !== undefined ? { description: dto.description } : {}),
      })
      .where(and(eq(projects.orgId, orgId), eq(projects.id, id)))
      .returning();
    if (!row) throw new NotFoundException('Project not found');
    return this.toDto(row);
  }

  async remove(orgId: string, id: string): Promise<void> {
    const deleted = await this.db
      .delete(projects)
      .where(and(eq(projects.orgId, orgId), eq(projects.id, id)))
      .returning({ id: projects.id });
    if (deleted.length === 0) throw new NotFoundException('Project not found');
  }

  private async uniqueSlug(orgId: string, name: string): Promise<string> {
    const base =
      name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .slice(0, 48) || 'project';
    const [existing] = await this.db
      .select({ id: projects.id })
      .from(projects)
      .where(and(eq(projects.orgId, orgId), eq(projects.slug, base)))
      .limit(1);
    return existing ? `${base}-${randomBytes(3).toString('hex')}` : base;
  }

  private toDto(row: typeof projects.$inferSelect): ProjectDto {
    return {
      id: row.id,
      name: row.name,
      slug: row.slug,
      description: row.description,
      createdAt: row.createdAt,
    };
  }
}
