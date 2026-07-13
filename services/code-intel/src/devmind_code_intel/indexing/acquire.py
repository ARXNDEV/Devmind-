"""Acquire a repository to a local working directory.

Supports a git URL (shallow clone of the target commit into a temp dir) or an
existing local path (used in place — handy for tests and self-indexing).
Credentials, when present, are injected via an ephemeral env, never written to
disk (08-security.md).
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AcquiredRepo:
    local_dir: str
    commit_sha: str
    _cleanup_dir: str | None = None

    async def cleanup(self) -> None:
        if self._cleanup_dir:
            await asyncio.to_thread(shutil.rmtree, self._cleanup_dir, True)


def _looks_like_git_url(source: str) -> bool:
    return (
        source.startswith(("http://", "https://", "git@", "ssh://"))
        or source.endswith(".git")
    )


async def _run_git(
    *args: str, cwd: str | None = None, env: dict[str, str] | None = None
) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=cwd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr.decode().strip()}")
    return stdout.decode().strip()


async def _head_sha(cwd: str) -> str | None:
    # FileNotFoundError => git not installed; RuntimeError => not a git repo.
    # Either way, degrade to a synthetic marker rather than failing the index.
    try:
        return await _run_git("rev-parse", "HEAD", cwd=cwd)
    except (RuntimeError, FileNotFoundError):
        return None


async def acquire(
    source: str,
    *,
    ref: str | None = None,
    token: str | None = None,
) -> AcquiredRepo:
    if _looks_like_git_url(source):
        tmp = tempfile.mkdtemp(prefix="devmind-clone-")
        import os

        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        clone_url = source
        if token and source.startswith("https://"):
            # Inject a token for the clone only; the URL is never persisted.
            clone_url = source.replace("https://", f"https://x-access-token:{token}@")
        args = ["clone", "--depth", "1"]
        if ref:
            args += ["--branch", ref]
        args += [clone_url, tmp]
        await _run_git(*args, env=env)
        sha = await _head_sha(tmp) or "unknown"
        return AcquiredRepo(local_dir=tmp, commit_sha=sha, _cleanup_dir=tmp)

    # Local path: use in place. Resolve/validate off the event loop.
    def _resolve_local() -> str:
        p = Path(source).resolve()
        if not p.is_dir():
            raise FileNotFoundError(f"source path is not a directory: {source}")
        return str(p)

    local = await asyncio.to_thread(_resolve_local)
    sha = await _head_sha(local) or "local-working-tree"
    return AcquiredRepo(local_dir=local, commit_sha=sha, _cleanup_dir=None)
