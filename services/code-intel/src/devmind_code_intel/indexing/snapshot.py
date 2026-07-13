"""Best-effort snapshot of the checked-out tree to MinIO/S3.

A snapshot makes an index run reproducible (later stages can re-read without a
re-clone). Failure to snapshot is logged but does not fail indexing in dev; a
pilot deployment can promote this to a hard requirement via config.
"""

from __future__ import annotations

import asyncio
import io
import tarfile
from typing import Any

import boto3
import structlog
from botocore.config import Config

from ..config import Settings

logger = structlog.get_logger(__name__)


def _s3_client(settings: Settings) -> Any:  # boto3 client type is dynamic
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def _tar_dir(local_dir: str) -> bytes:
    # Exclude the same heavy/vendored directories the indexer skips; snapshotting
    # node_modules/.git/.venv would dominate runtime and bloat storage.
    from .fileset import _IGNORED_DIRS

    def _filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
        parts = set(info.name.split("/"))
        return None if parts & _IGNORED_DIRS else info

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(local_dir, arcname=".", filter=_filter)
    return buf.getvalue()


async def snapshot_tree(
    settings: Settings, *, repo_id: str, commit_sha: str, local_dir: str
) -> str | None:
    """Upload a gzip tarball; returns the object key, or None on failure."""
    key = f"{repo_id}/{commit_sha}.tar.gz"
    try:
        data = await asyncio.to_thread(_tar_dir, local_dir)
        client = _s3_client(settings)
        await asyncio.to_thread(
            client.put_object,
            Bucket=settings.s3_bucket_snapshots,
            Key=key,
            Body=data,
        )
        logger.info("snapshot uploaded", key=key, bytes=len(data))
        return key
    except Exception:  # noqa: BLE001 - snapshot is best-effort in dev
        logger.warning("snapshot upload failed", key=key, exc_info=True)
        return None
