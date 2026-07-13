"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";
import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/projects", label: "Projects" },
  { href: "/settings", label: "Settings" },
];

export default function AppLayout({ children }: { children: ReactNode }) {
  const { status, user, organization, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
  }, [status, router]);

  if (status !== "authenticated") {
    return (
      <div className="flex flex-1 items-center justify-center text-ink-500">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex flex-1">
      <aside className="flex w-60 shrink-0 flex-col border-r border-line bg-surface-900">
        <div className="px-5 py-5 text-lg font-semibold tracking-tight">
          DevMind <span className="text-accent-400">AI</span>
        </div>
        <nav className="flex-1 space-y-0.5 px-3">
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-md px-3 py-2 text-sm transition-colors ${
                  active
                    ? "bg-surface-700 text-ink-100"
                    : "text-ink-500 hover:bg-surface-800 hover:text-ink-300"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-line px-5 py-4 text-sm">
          {user && (
            <div className="mb-2">
              <div className="text-ink-300">{user.name}</div>
              <div className="text-xs text-ink-500">
                {organization?.name ?? user.email}
              </div>
            </div>
          )}
          <button
            onClick={() => void logout().then(() => router.replace("/login"))}
            className="text-xs text-ink-500 hover:text-danger-500"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto px-8 py-8">{children}</main>
    </div>
  );
}
