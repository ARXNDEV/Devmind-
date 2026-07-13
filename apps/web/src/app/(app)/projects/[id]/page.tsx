"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, ApiError, Project, Repository } from "@/lib/api-client";

const STATUS_STYLES: Record<string, string> = {
  ready: "text-success-500",
  indexing: "text-accent-400",
  failed: "text-danger-500",
  pending: "text-ink-500",
  stale: "text-ink-300",
};

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [repos, setRepos] = useState<Repository[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [indexing, setIndexing] = useState<Record<string, boolean>>({});

  const refresh = useCallback(
    () =>
      Promise.all([api.getProject(id), api.listRepositories(id)])
        .then(([p, r]) => {
          setProject(p);
          setRepos(r);
        })
        .catch((err: unknown) =>
          setError(err instanceof ApiError ? err.problem.detail : "Failed to load"),
        ),
    [id],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setCreating(true);
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await api.createRepository(id, {
        name: String(data.get("name")),
        provider: String(data.get("provider")),
        cloneUrl: String(data.get("cloneUrl")),
        credentials: String(data.get("credentials") || "") || undefined,
      });
      form.reset();
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.problem.detail : "Failed to add repo");
    } finally {
      setCreating(false);
    }
  }

  async function onIndex(repoId: string) {
    setIndexing((s) => ({ ...s, [repoId]: true }));
    try {
      const { jobId } = await api.indexRepository(repoId);
      // Poll the job to completion (SSE is also available at /jobs/:id/events).
      for (let i = 0; i < 120; i++) {
        const job = await api.getJob(jobId);
        if (job.status === "succeeded" || job.status === "failed") break;
        await new Promise((r) => setTimeout(r, 1500));
      }
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.problem.detail : "Indexing failed");
    } finally {
      setIndexing((s) => ({ ...s, [repoId]: false }));
    }
  }

  const inputClass =
    "rounded-md border border-line bg-surface-900 px-3 py-2 text-sm " +
    "placeholder:text-ink-500 focus:border-accent-500 focus:outline-none";

  return (
    <div className="mx-auto max-w-5xl">
      <Link href="/projects" className="text-sm text-ink-500 hover:text-ink-300">
        ← Projects
      </Link>
      <h1 className="mt-2 text-xl font-semibold tracking-tight">
        {project?.name ?? "Project"}
      </h1>
      <p className="mt-1 text-sm text-ink-500">
        Repositories in this project. Index a repository to build its code graph.
      </p>

      <form
        onSubmit={onCreate}
        className="mt-6 grid grid-cols-1 gap-3 rounded-xl border border-line bg-surface-800 p-4 sm:grid-cols-2"
      >
        <input name="name" required placeholder="Repository name" className={inputClass} />
        <select name="provider" defaultValue="local" className={inputClass}>
          <option value="local">local (path on server)</option>
          <option value="github">github</option>
          <option value="gitlab">gitlab</option>
          <option value="bitbucket">bitbucket</option>
          <option value="generic_git">generic_git</option>
        </select>
        <input
          name="cloneUrl"
          required
          placeholder="Clone URL or absolute path"
          className={`${inputClass} sm:col-span-2`}
        />
        <input
          name="credentials"
          type="password"
          placeholder="Access token (optional, stored encrypted)"
          className={`${inputClass} sm:col-span-2`}
        />
        <button
          type="submit"
          disabled={creating}
          className="justify-self-start rounded-md bg-accent-500 px-4 py-2 text-sm font-medium text-white hover:bg-accent-600 disabled:opacity-60"
        >
          {creating ? "Adding…" : "Add repository"}
        </button>
      </form>

      {error && (
        <p role="alert" className="mt-3 text-sm text-danger-500">
          {error}
        </p>
      )}

      <div className="mt-6 space-y-3">
        {repos === null ? (
          <p className="text-sm text-ink-500">Loading…</p>
        ) : repos.length === 0 ? (
          <p className="text-sm text-ink-500">No repositories yet.</p>
        ) : (
          repos.map((repo) => (
            <div
              key={repo.id}
              className="flex items-center justify-between rounded-xl border border-line bg-surface-800 p-4"
            >
              <div>
                <div className="font-medium">
                  {repo.name}{" "}
                  <span className="text-xs text-ink-500">({repo.provider})</span>
                </div>
                <div className="font-mono text-xs text-ink-500">{repo.cloneUrl}</div>
                <div className="mt-1 text-xs">
                  status:{" "}
                  <span className={STATUS_STYLES[repo.indexStatus] ?? "text-ink-300"}>
                    {repo.indexStatus}
                  </span>
                  {repo.hasCredentials && (
                    <span className="ml-2 text-ink-500">· 🔒 credentials set</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => void onIndex(repo.id)}
                  disabled={indexing[repo.id]}
                  className="rounded-md border border-line px-3 py-1.5 text-sm hover:bg-surface-700 disabled:opacity-60"
                >
                  {indexing[repo.id] ? "Indexing…" : "Index"}
                </button>
                <Link
                  href={`/repositories/${repo.id}`}
                  className="rounded-md bg-accent-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-600"
                >
                  Explore
                </Link>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
