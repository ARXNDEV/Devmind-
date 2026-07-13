import {
  BadRequestException,
  Inject,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { and, desc, eq } from 'drizzle-orm';
import { uuidv7 } from 'uuidv7';
import { CodeIntelClient } from '@/common/code-intel/code-intel.client';
import { CredentialVault } from '@/common/crypto/credential-vault';
import { Database, DB } from '@/database/database.module';
import { projects, repositories } from '@/database/schema';
import { JobsService } from '@/modules/jobs/jobs.service';
import { CreateRepositoryDto, RepositoryDto } from './dto/repository.dto';

@Injectable()
export class RepositoriesService {
  constructor(
    @Inject(DB) private readonly db: Database,
    private readonly vault: CredentialVault,
    private readonly codeIntel: CodeIntelClient,
    private readonly jobs: JobsService,
  ) {}

  async list(orgId: string, projectId: string): Promise<RepositoryDto[]> {
    const rows = await this.db
      .select()
      .from(repositories)
      .where(
        and(
          eq(repositories.orgId, orgId),
          eq(repositories.projectId, projectId),
        ),
      )
      .orderBy(desc(repositories.createdAt));
    return rows.map((r) => this.toDto(r));
  }

  async get(orgId: string, id: string): Promise<RepositoryDto> {
    return this.toDto(await this.getRow(orgId, id));
  }

  async create(
    orgId: string,
    projectId: string,
    dto: CreateRepositoryDto,
  ): Promise<RepositoryDto> {
    // Verify the project belongs to the org before attaching a repository.
    const [project] = await this.db
      .select({ id: projects.id })
      .from(projects)
      .where(and(eq(projects.orgId, orgId), eq(projects.id, projectId)))
      .limit(1);
    if (!project) throw new NotFoundException('Project not found');

    const [row] = await this.db
      .insert(repositories)
      .values({
        id: uuidv7(),
        orgId,
        projectId,
        name: dto.name,
        provider: dto.provider,
        cloneUrl: dto.cloneUrl,
        defaultBranch: dto.defaultBranch ?? 'main',
        encryptedCredentials: dto.credentials
          ? this.vault.encrypt(dto.credentials)
          : null,
      })
      .returning();
    return this.toDto(row);
  }

  async remove(orgId: string, id: string): Promise<void> {
    const deleted = await this.db
      .delete(repositories)
      .where(and(eq(repositories.orgId, orgId), eq(repositories.id, id)))
      .returning({ id: repositories.id });
    if (deleted.length === 0) throw new NotFoundException('Repository not found');
  }

  /** Kicks off indexing: creates a Job, commands code-intel, returns the job id. */
  async triggerIndex(orgId: string, id: string): Promise<{ jobId: string }> {
    const repo = await this.getRow(orgId, id);
    const job = await this.jobs.create({
      orgId,
      kind: 'index',
      subjectType: 'repository',
      subjectId: repo.id,
    });

    const token = repo.encryptedCredentials
      ? this.vault.decrypt(repo.encryptedCredentials)
      : undefined;

    try {
      const { taskId } = await this.codeIntel.startIndexRun({
        jobId: job.id,
        repoId: repo.id,
        orgId,
        source: repo.cloneUrl,
        ref: repo.defaultBranch,
        token,
        mode: 'auto',
      });
      await this.jobs.applyStatus({
        id: job.id,
        status: 'running',
        externalTaskId: taskId,
      });
      await this.db
        .update(repositories)
        .set({ indexStatus: 'indexing' })
        .where(eq(repositories.id, repo.id));
    } catch {
      await this.jobs.applyStatus({
        id: job.id,
        status: 'failed',
        error: { message: 'Failed to reach code-intel' },
      });
      await this.db
        .update(repositories)
        .set({ indexStatus: 'failed' })
        .where(eq(repositories.id, repo.id));
      throw new BadRequestException('Failed to start indexing');
    }
    return { jobId: job.id };
  }

  private async getRow(
    orgId: string,
    id: string,
  ): Promise<typeof repositories.$inferSelect> {
    const [row] = await this.db
      .select()
      .from(repositories)
      .where(and(eq(repositories.orgId, orgId), eq(repositories.id, id)))
      .limit(1);
    if (!row) throw new NotFoundException('Repository not found');
    return row;
  }

  private toDto(row: typeof repositories.$inferSelect): RepositoryDto {
    return {
      id: row.id,
      name: row.name,
      provider: row.provider,
      cloneUrl: row.cloneUrl,
      defaultBranch: row.defaultBranch,
      indexStatus: row.indexStatus,
      indexedCommitSha: row.indexedCommitSha,
      hasCredentials: row.encryptedCredentials !== null,
      lastIndexedAt: row.lastIndexedAt,
      createdAt: row.createdAt,
    };
  }
}
