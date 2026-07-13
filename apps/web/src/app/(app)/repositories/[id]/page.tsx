"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  ApiError,
  FileSymbol,
  ImpactResult,
  Repository,
  TreeFile,
} from "@/lib/api-client";

const KIND_BADGE: Record<string, string> = {
  class: "bg-accent-600",
  interface: "bg-accent-500",
  method: "bg-surface-700",
  function: "bg-surface-700",
  variable: "bg-surface-700",
  enum: "bg-accent-600",
  type: "bg-surface-700",
};

export default function RepositoryExplorerPage() {
  const { id } = useParams<{ id: string }>();
  const [repo, setRepo] = useState<Repository | null>(null);
  const [files, setFiles] = useState<TreeFile[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [symbols, setSymbols] = useState<FileSymbol[]>([]);
  const [impact, setImpact] = useState<ImpactResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getRepository(id), api.repositoryTree(id)])
      .then(([r, tree]) => {
        setRepo(r);
        setFiles(tree.files);
      })
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.problem.detail : "Failed to load"),
      );
  }, [id]);

  const openFile = useCallback(
    (path: string) => {
      setSelected(path);
      setImpact(null);
      api
        .fileSymbols(id, path)
        .then((res) => setSymbols(res.symbols))
        .catch(() => setSymbols([]));
    },
    [id],
  );

  const runImpact = useCallback(
    (fqn: string, path: string) => {
      api
        .impact(id, fqn, path)
        .then(setImpact)
        .catch((err: unknown) =>
          setError(err instanceof ApiError ? err.problem.detail : "Impact failed"),
        );
    },
    [id],
  );

  if (repo && repo.indexStatus !== "ready") {
    return (
      <div className="mx-auto max-w-3xl">
        <Header repo={repo} />
        <div className="mt-6 rounded-xl border border-line bg-surface-800 p-6 text-sm text-ink-300">
          This repository is <span className="font-medium">{repo.indexStatus}</span>.
          Index it from the project page to explore its code graph.
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl">
      <Header repo={repo} />
      {error && <p className="mt-3 text-sm text-danger-500">{error}</p>}

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        {/* File tree */}
        <section className="rounded-xl border border-line bg-surface-800">
          <div className="border-b border-line px-4 py-2 text-xs uppercase tracking-wide text-ink-500">
            Files {files ? `(${files.length})` : ""}
          </div>
          <ul className="max-h-[60vh] overflow-y-auto p-2 font-mono text-sm">
            {files?.map((file) => (
              <li key={file.path}>
                <button
                  onClick={() => openFile(file.path)}
                  className={`flex w-full items-center justify-between rounded px-2 py-1 text-left hover:bg-surface-700 ${
                    selected === file.path ? "bg-surface-700 text-ink-100" : "text-ink-300"
                  }`}
                >
                  <span className="truncate">{file.path}</span>
                  <span className="ml-2 shrink-0 text-xs text-ink-500">
                    {file.symbol_count}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>

        {/* Symbol outline + impact */}
        <section className="space-y-4">
          <div className="rounded-xl border border-line bg-surface-800">
            <div className="border-b border-line px-4 py-2 text-xs uppercase tracking-wide text-ink-500">
              {selected ? `Symbols · ${selected}` : "Select a file"}
            </div>
            <ul className="max-h-[36vh] overflow-y-auto p-2 text-sm">
              {symbols.map((sym) => (
                <li
                  key={sym.fqn}
                  className="flex items-center justify-between rounded px-2 py-1 hover:bg-surface-700"
                >
                  <span className="flex items-center gap-2 truncate">
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] uppercase ${
                        KIND_BADGE[sym.kind] ?? "bg-surface-700"
                      }`}
                    >
                      {sym.kind}
                    </span>
                    <span className="truncate font-mono text-ink-200">
                      {sym.signature ?? sym.name}
                    </span>
                  </span>
                  <button
                    onClick={() => selected && runImpact(sym.fqn, selected)}
                    className="ml-2 shrink-0 text-xs text-accent-400 hover:underline"
                  >
                    impact
                  </button>
                </li>
              ))}
              {selected && symbols.length === 0 && (
                <li className="px-2 py-3 text-ink-500">No symbols in this file.</li>
              )}
            </ul>
          </div>

          {impact && impact.found && (
            <div className="rounded-xl border border-line bg-surface-800 p-4">
              <div className="flex items-center justify-between">
                <div className="font-mono text-sm">{impact.symbol?.fqn}</div>
                <RiskBadge score={impact.risk_score ?? 0} />
              </div>
              <div className="mt-2 grid grid-cols-2 gap-3 text-sm">
                <Stat label="Dependents" value={impact.dependent_count ?? 0} />
                <Stat label="Cross-file" value={impact.cross_file_count ?? 0} />
              </div>
              {impact.dependents && impact.dependents.length > 0 && (
                <ul className="mt-3 max-h-40 overflow-y-auto font-mono text-xs text-ink-300">
                  {impact.dependents.map((d) => (
                    <li key={`${d.path}:${d.fqn}`} className="truncate py-0.5">
                      {d.fqn} <span className="text-ink-500">· {d.path}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function Header({ repo }: { repo: Repository | null }) {
  return (
    <div>
      <Link href="/projects" className="text-sm text-ink-500 hover:text-ink-300">
        ← Projects
      </Link>
      <h1 className="mt-2 text-xl font-semibold tracking-tight">
        {repo?.name ?? "Repository"}{" "}
        <span className="text-sm font-normal text-ink-500">Explorer</span>
      </h1>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-surface-900 p-3">
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-xs text-ink-500">{label}</div>
    </div>
  );
}

function RiskBadge({ score }: { score: number }) {
  const level = score >= 0.66 ? "high" : score >= 0.33 ? "medium" : "low";
  const color =
    level === "high"
      ? "bg-danger-500"
      : level === "medium"
        ? "bg-accent-500"
        : "bg-success-500";
  return (
    <span className={`rounded px-2 py-0.5 text-xs text-white ${color}`}>
      risk {score.toFixed(2)} · {level}
    </span>
  );
}
