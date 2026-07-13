"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, Project } from "@/lib/api-client";

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);

  useEffect(() => {
    api.listProjects().then(setProjects).catch(() => setProjects([]));
  }, []);

  const stats = [
    { label: "Projects", value: projects ? String(projects.length) : "—" },
    { label: "Repositories indexed", value: "0", hint: "Phase 2" },
    { label: "Open incidents", value: "0", hint: "Phase 4" },
    { label: "Patches proposed", value: "0", hint: "Phase 6" },
  ];

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>
      <p className="mt-1 text-sm text-ink-500">
        Platform overview for your organization.
      </p>

      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-line bg-surface-800 p-5"
          >
            <div className="text-2xl font-semibold">{stat.value}</div>
            <div className="mt-1 text-sm text-ink-500">{stat.label}</div>
            {stat.hint && (
              <div className="mt-2 inline-block rounded bg-surface-700 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-ink-500">
                {stat.hint}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-8 rounded-xl border border-line bg-surface-800 p-6">
        <h2 className="font-medium">Get started</h2>
        <p className="mt-1 text-sm text-ink-500">
          Create a project, then connect a repository to begin indexing your
          codebase.
        </p>
        <Link
          href="/projects"
          className="mt-4 inline-block rounded-md bg-accent-500 px-4 py-2 text-sm
                     font-medium text-white hover:bg-accent-600"
        >
          Go to Projects
        </Link>
      </div>
    </div>
  );
}
