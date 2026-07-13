import { Inject, Injectable, Logger } from '@nestjs/common';
import { APP_CONFIG, AppConfig } from '@/config/app-config';

export interface StartIndexRunInput {
  jobId: string;
  repoId: string;
  orgId: string;
  source: string;
  ref?: string;
  token?: string;
  mode?: 'auto' | 'full' | 'incremental';
}

export interface GraphNeighborhoodQuery {
  repoId: string;
  fqn: string;
  path: string;
  depth?: number;
}

/**
 * Typed client for the internal code-intel contract (07-api-contracts.md).
 * Every request carries the shared service token and the acting org id;
 * code-intel is never exposed publicly.
 */
@Injectable()
export class CodeIntelClient {
  private readonly logger = new Logger(CodeIntelClient.name);
  private readonly baseUrl: string;
  private readonly token: string;

  constructor(@Inject(APP_CONFIG) config: AppConfig) {
    this.baseUrl = config.CODE_INTEL_BASE_URL.replace(/\/$/, '');
    this.token = config.INTERNAL_SERVICE_TOKEN;
  }

  async startIndexRun(input: StartIndexRunInput): Promise<{ taskId: string }> {
    return this.post('/internal/v1/index-runs', {
      jobId: input.jobId,
      repoId: input.repoId,
      orgId: input.orgId,
      source: input.source,
      ref: input.ref,
      token: input.token,
      mode: input.mode ?? 'auto',
    });
  }

  async neighborhood(
    query: GraphNeighborhoodQuery,
    orgId: string,
  ): Promise<unknown> {
    const params = new URLSearchParams({
      repoId: query.repoId,
      fqn: query.fqn,
      path: query.path,
      depth: String(query.depth ?? 2),
    });
    return this.get(`/internal/v1/graph/neighborhood?${params}`, orgId);
  }

  async impact(query: GraphNeighborhoodQuery, orgId: string): Promise<unknown> {
    const params = new URLSearchParams({
      repoId: query.repoId,
      fqn: query.fqn,
      path: query.path,
      depth: String(query.depth ?? 3),
    });
    return this.get(`/internal/v1/graph/impact?${params}`, orgId);
  }

  async tree(repoId: string, orgId: string): Promise<unknown> {
    return this.get(`/internal/v1/repositories/${repoId}/tree`, orgId);
  }

  async fileSymbols(
    repoId: string,
    path: string,
    orgId: string,
  ): Promise<unknown> {
    const params = new URLSearchParams({ path });
    return this.get(
      `/internal/v1/repositories/${repoId}/symbols?${params}`,
      orgId,
    );
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-internal-token': this.token,
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const text = await response.text().catch(() => '');
      this.logger.error(`code-intel POST ${path} → ${response.status}: ${text}`);
      throw new Error(`code-intel request failed (${response.status})`);
    }
    return (await response.json()) as T;
  }

  private async get<T>(path: string, orgId: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      headers: { 'x-internal-token': this.token, 'x-devmind-org-id': orgId },
    });
    if (!response.ok) {
      throw new Error(`code-intel request failed (${response.status})`);
    }
    return (await response.json()) as T;
  }
}
