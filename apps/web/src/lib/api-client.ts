/**
 * Minimal typed API client for the DevMind API.
 *
 * Access tokens live in memory only (never localStorage — XSS posture per
 * 08-security.md); the refresh token is an httpOnly cookie managed by the
 * API. On a 401 the client attempts one silent refresh, then surfaces the
 * failure so the auth provider can route to login.
 *
 * Replaced by the generated client from packages/shared-types once the CI
 * codegen pipeline runs against a stable spec.
 */

// Empty = same-origin relative calls (/api/...), proxied to the api service by
// the Next server (see next.config rewrites). Set an absolute URL only for
// split-origin dev. This removes CORS and any baked absolute host.
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: string;
}

export interface AuthOrganization {
  id: string;
  name: string;
  slug: string;
}

export interface AuthResponse {
  accessToken: string;
  expiresIn: number;
  user: AuthUser;
  organization: AuthOrganization;
}

export interface Project {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  createdAt: string;
}

export interface Repository {
  id: string;
  name: string;
  provider: string;
  cloneUrl: string;
  defaultBranch: string;
  indexStatus: string;
  indexedCommitSha: string | null;
  hasCredentials: boolean;
  lastIndexedAt: string | null;
  createdAt: string;
}

export interface Job {
  id: string;
  kind: string;
  status: string;
  progress: Record<string, unknown>;
  error: Record<string, unknown> | null;
  createdAt: string;
  finishedAt: string | null;
}

export interface TreeFile {
  path: string;
  language: string;
  symbol_count: number;
}

export interface FileSymbol {
  fqn: string;
  name: string;
  kind: string;
  signature: string | null;
  start_line: number;
  end_line: number;
}

export interface ImpactResult {
  found: boolean;
  symbol?: { fqn: string; name: string; kind: string; path: string };
  dependent_count?: number;
  cross_file_count?: number;
  risk_score?: number;
  dependents?: { fqn: string; name: string; kind: string; path: string }[];
}

export interface ProblemDetails {
  title: string;
  status: number;
  detail: string;
  code: string;
  errors?: string[];
}

export class ApiError extends Error {
  constructor(public readonly problem: ProblemDetails) {
    super(problem.detail);
    this.name = 'ApiError';
  }
}

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

async function parseError(response: Response): Promise<never> {
  let problem: ProblemDetails;
  try {
    problem = (await response.json()) as ProblemDetails;
  } catch {
    problem = {
      title: response.statusText,
      status: response.status,
      detail: response.statusText,
      code: 'unknown_error',
    };
  }
  throw new ApiError(problem);
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  retryOn401 = true,
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    credentials: 'include',
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 401 && retryOn401 && !path.startsWith('/api/v1/auth')) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(method, path, body, false);
  }
  if (!response.ok) await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function tryRefresh(): Promise<boolean> {
  try {
    const auth = await request<AuthResponse>(
      'POST',
      '/api/v1/auth/refresh',
      undefined,
      false,
    );
    setAccessToken(auth.accessToken);
    return true;
  } catch {
    setAccessToken(null);
    return false;
  }
}

export const api = {
  register: (input: {
    organizationName: string;
    name: string;
    email: string;
    password: string;
  }) => request<AuthResponse>('POST', '/api/v1/auth/register', input),
  login: (input: { email: string; password: string }) =>
    request<AuthResponse>('POST', '/api/v1/auth/login', input),
  refresh: tryRefresh,
  logout: () => request<void>('POST', '/api/v1/auth/logout'),

  listProjects: () => request<Project[]>('GET', '/api/v1/projects'),
  createProject: (input: { name: string; description?: string }) =>
    request<Project>('POST', '/api/v1/projects', input),
  deleteProject: (id: string) => request<void>('DELETE', `/api/v1/projects/${id}`),

  getProject: (id: string) => request<Project>('GET', `/api/v1/projects/${id}`),
  listRepositories: (projectId: string) =>
    request<Repository[]>('GET', `/api/v1/projects/${projectId}/repositories`),
  createRepository: (
    projectId: string,
    input: {
      name: string;
      provider: string;
      cloneUrl: string;
      defaultBranch?: string;
      credentials?: string;
    },
  ) =>
    request<Repository>(
      'POST',
      `/api/v1/projects/${projectId}/repositories`,
      input,
    ),
  getRepository: (id: string) =>
    request<Repository>('GET', `/api/v1/repositories/${id}`),
  indexRepository: (id: string) =>
    request<{ jobId: string }>('POST', `/api/v1/repositories/${id}/index`),
  getJob: (id: string) => request<Job>('GET', `/api/v1/jobs/${id}`),
  repositoryTree: (id: string) =>
    request<{ files: TreeFile[] }>('GET', `/api/v1/repositories/${id}/tree`),
  fileSymbols: (id: string, path: string) =>
    request<{ path: string; symbols: FileSymbol[] }>(
      'GET',
      `/api/v1/repositories/${id}/symbols?path=${encodeURIComponent(path)}`,
    ),
  impact: (id: string, fqn: string, path: string) =>
    request<ImpactResult>(
      'GET',
      `/api/v1/repositories/${id}/impact?fqn=${encodeURIComponent(
        fqn,
      )}&path=${encodeURIComponent(path)}`,
    ),
};
