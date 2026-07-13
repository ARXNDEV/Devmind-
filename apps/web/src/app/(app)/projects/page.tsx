"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, ApiError, Project } from "@/lib/api-client";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(
    () =>
      api
        .listProjects()
        .then(setProjects)
        .catch((err: unknown) => {
          setError(
            err instanceof ApiError ? err.problem.detail : "Failed to load",
          );
        }),
    [],
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
      await api.createProject({
        name: String(data.get("name")),
        description: String(data.get("description") || "") || undefined,
      });
      form.reset();
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.problem.detail : "Failed to create");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-xl font-semibold tracking-tight">Projects</h1>
      <p className="mt-1 text-sm text-ink-500">
        A project groups the repositories, incidents, and knowledge of one
        system.
      </p>

      <form
        onSubmit={onCreate}
        className="mt-6 flex flex-wrap gap-3 rounded-xl border border-line bg-surface-800 p-4"
      >
        <input
          name="name"
          required
          minLength={2}
          placeholder="Project name"
          className="flex-1 min-w-48 rounded-md border border-line bg-surface-900
                     px-3 py-2 text-sm placeholder:text-ink-500
                     focus:border-accent-500 focus:outline-none"
        />
        <input
          name="description"
          placeholder="Description (optional)"
          className="flex-[2] min-w-64 rounded-md border border-line bg-surface-900
                     px-3 py-2 text-sm placeholder:text-ink-500
                     focus:border-accent-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={creating}
          className="rounded-md bg-accent-500 px-4 py-2 text-sm font-medium
                     text-white hover:bg-accent-600 disabled:opacity-60"
        >
          {creating ? "Creating…" : "Create project"}
        </button>
      </form>

      {error && (
        <p role="alert" className="mt-3 text-sm text-danger-500">
          {error}
        </p>
      )}

      <div className="mt-6 overflow-hidden rounded-xl border border-line">
        <table className="w-full text-left text-sm">
          <thead className="bg-surface-800 text-xs uppercase tracking-wide text-ink-500">
            <tr>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Slug</th>
              <th className="px-4 py-3 font-medium">Description</th>
              <th className="px-4 py-3 font-medium">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line bg-surface-900">
            {projects === null ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-ink-500">
                  Loading…
                </td>
              </tr>
            ) : projects.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-ink-500">
                  No projects yet — create the first one above.
                </td>
              </tr>
            ) : (
              projects.map((project) => (
                <tr key={project.id} className="hover:bg-surface-800">
                  <td className="px-4 py-3 font-medium">
                    <Link
                      href={`/projects/${project.id}`}
                      className="text-accent-400 hover:underline"
                    >
                      {project.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-ink-300">
                    {project.slug}
                  </td>
                  <td className="px-4 py-3 text-ink-300">
                    {project.description ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-ink-500">
                    {new Date(project.createdAt).toLocaleDateString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
