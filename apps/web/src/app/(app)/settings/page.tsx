"use client";

import { useAuth } from "@/lib/auth";

export default function SettingsPage() {
  const { user, organization } = useAuth();

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
      <p className="mt-1 text-sm text-ink-500">
        Organization and account settings.
      </p>

      <div className="mt-6 space-y-4">
        <section className="rounded-xl border border-line bg-surface-800 p-6">
          <h2 className="font-medium">Organization</h2>
          <dl className="mt-3 grid grid-cols-[8rem_1fr] gap-y-2 text-sm">
            <dt className="text-ink-500">Name</dt>
            <dd>{organization?.name ?? "—"}</dd>
            <dt className="text-ink-500">Slug</dt>
            <dd className="font-mono text-xs">{organization?.slug ?? "—"}</dd>
          </dl>
        </section>

        <section className="rounded-xl border border-line bg-surface-800 p-6">
          <h2 className="font-medium">Account</h2>
          <dl className="mt-3 grid grid-cols-[8rem_1fr] gap-y-2 text-sm">
            <dt className="text-ink-500">Name</dt>
            <dd>{user?.name ?? "—"}</dd>
            <dt className="text-ink-500">Email</dt>
            <dd>{user?.email ?? "—"}</dd>
            <dt className="text-ink-500">Role</dt>
            <dd className="capitalize">{user?.role ?? "—"}</dd>
          </dl>
        </section>

        <section className="rounded-xl border border-line bg-surface-800 p-6">
          <h2 className="font-medium">Members & API keys</h2>
          <p className="mt-1 text-sm text-ink-500">
            Member management and scoped API keys arrive with the admin surface
            (Phase 7).
          </p>
        </section>
      </div>
    </div>
  );
}
