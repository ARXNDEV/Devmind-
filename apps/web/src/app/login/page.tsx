"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";

type Mode = "login" | "register";

export default function LoginPage() {
  const { applyAuth } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    const form = new FormData(event.currentTarget);
    try {
      const auth =
        mode === "login"
          ? await api.login({
              email: String(form.get("email")),
              password: String(form.get("password")),
            })
          : await api.register({
              organizationName: String(form.get("organizationName")),
              name: String(form.get("name")),
              email: String(form.get("email")),
              password: String(form.get("password")),
            });
      applyAuth(auth);
      router.replace("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.problem.detail : "Something went wrong",
      );
    } finally {
      setPending(false);
    }
  }

  const inputClass =
    "w-full rounded-md border border-line bg-surface-900 px-3 py-2 text-sm " +
    "placeholder:text-ink-500 focus:border-accent-500 focus:outline-none";

  return (
    <main className="flex flex-1 items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="text-2xl font-semibold tracking-tight">
            DevMind <span className="text-accent-400">AI</span>
          </div>
          <p className="mt-1 text-sm text-ink-500">
            The AI Software Engineer for Legacy Enterprise Systems
          </p>
        </div>

        <div className="rounded-xl border border-line bg-surface-800 p-6 shadow-xl">
          <div className="mb-5 grid grid-cols-2 rounded-lg bg-surface-900 p-1 text-sm">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`rounded-md py-1.5 capitalize transition-colors ${
                  mode === m
                    ? "bg-surface-700 text-ink-100"
                    : "text-ink-500 hover:text-ink-300"
                }`}
              >
                {m === "login" ? "Sign in" : "Create org"}
              </button>
            ))}
          </div>

          <form onSubmit={onSubmit} className="space-y-3">
            {mode === "register" && (
              <>
                <input
                  name="organizationName"
                  required
                  minLength={2}
                  placeholder="Organization name"
                  className={inputClass}
                />
                <input
                  name="name"
                  required
                  placeholder="Your name"
                  className={inputClass}
                />
              </>
            )}
            <input
              name="email"
              type="email"
              required
              placeholder="Work email"
              className={inputClass}
            />
            <input
              name="password"
              type="password"
              required
              minLength={mode === "register" ? 12 : 1}
              placeholder={
                mode === "register" ? "Password (12+ characters)" : "Password"
              }
              className={inputClass}
            />

            {error && (
              <p role="alert" className="text-sm text-danger-500">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={pending}
              className="w-full rounded-md bg-accent-500 py-2 text-sm font-medium
                         text-white transition-colors hover:bg-accent-600
                         disabled:opacity-60"
            >
              {pending
                ? "Please wait…"
                : mode === "login"
                  ? "Sign in"
                  : "Create organization"}
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
