import { Inject, Injectable, NotFoundException } from '@nestjs/common';
import { and, eq } from 'drizzle-orm';
import { uuidv7 } from 'uuidv7';
import { Database, DB } from '@/database/database.module';
import { jobs } from '@/database/schema';

type JobKind = (typeof jobs.kind.enumValues)[number];
type JobStatus = (typeof jobs.status.enumValues)[number];

export interface JobView {
  id: string;
  kind: JobKind;
  status: JobStatus;
  subjectType: string;
  subjectId: string;
  progress: unknown;
  error: unknown;
  createdAt: Date;
  finishedAt: Date | null;
}

@Injectable()
export class JobsService {
  constructor(@Inject(DB) private readonly db: Database) {}

  async create(input: {
    orgId: string;
    kind: JobKind;
    subjectType: string;
    subjectId: string;
  }): Promise<JobView> {
    const [row] = await this.db
      .insert(jobs)
      .values({
        id: uuidv7(),
        orgId: input.orgId,
        kind: input.kind,
        subjectType: input.subjectType,
        subjectId: input.subjectId,
        status: 'queued',
      })
      .returning();
    return this.toView(row);
  }

  async get(orgId: string, id: string): Promise<JobView> {
    const [row] = await this.db
      .select()
      .from(jobs)
      .where(and(eq(jobs.orgId, orgId), eq(jobs.id, id)))
      .limit(1);
    if (!row) throw new NotFoundException('Job not found');
    return this.toView(row);
  }

  /** Called from the code-intel callback; keyed by job id (org-agnostic). */
  async applyStatus(input: {
    id: string;
    status: JobStatus;
    result?: unknown;
    error?: unknown;
    externalTaskId?: string;
  }): Promise<JobView | null> {
    const terminal = input.status === 'succeeded' || input.status === 'failed';
    const [row] = await this.db
      .update(jobs)
      .set({
        status: input.status,
        ...(input.result !== undefined ? { progress: input.result as object } : {}),
        ...(input.error !== undefined ? { error: input.error as object } : {}),
        ...(input.externalTaskId ? { externalTaskId: input.externalTaskId } : {}),
        ...(input.status === 'running' ? { startedAt: new Date() } : {}),
        ...(terminal ? { finishedAt: new Date() } : {}),
      })
      .where(eq(jobs.id, input.id))
      .returning();
    return row ? this.toView(row) : null;
  }

  private toView(row: typeof jobs.$inferSelect): JobView {
    return {
      id: row.id,
      kind: row.kind,
      status: row.status,
      subjectType: row.subjectType,
      subjectId: row.subjectId,
      progress: row.progress,
      error: row.error,
      createdAt: row.createdAt,
      finishedAt: row.finishedAt,
    };
  }
}
