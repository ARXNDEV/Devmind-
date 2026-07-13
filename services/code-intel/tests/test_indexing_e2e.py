"""End-to-end indexing test against live Neo4j + Postgres.

Indexes a synthetic multi-file repo, asserts the graph, then mutates a file and
re-indexes incrementally, asserting only the changed file is touched and stale
edges are gone. Self-skips if the data stores are unreachable so CI without
infra stays green.
"""

import os
from pathlib import Path
from uuid import uuid4

import pytest

from devmind_code_intel.graph.neo4j_graph import Neo4jCodeGraph
from devmind_code_intel.indexing import IndexingPipeline, IndexRequest
from devmind_code_intel.store.db import Database


async def _stores_available() -> bool:
    try:
        db = await Database.connect()
        await db.close()
        graph = Neo4jCodeGraph()
        await graph.ensure_constraints()
        await graph.close()
        return True
    except Exception:
        return False


def _write_repo(root: Path) -> None:
    (root / "billing").mkdir(parents=True)
    (root / "billing" / "core.py").write_text(
        "class Ledger:\n"
        "    def post(self, amount):\n"
        "        return record(amount)\n\n"
        "def record(amount):\n"
        "    return amount\n"
    )
    (root / "billing" / "payment.py").write_text(
        "from billing.core import Ledger\n\n"
        "class PaymentService(Ledger):\n"
        "    def settle(self, invoice):\n"
        "        return self.post(invoice.total)\n"
    )
    (root / "app.py").write_text(
        "from billing.payment import PaymentService\n\n"
        "def main():\n"
        "    svc = PaymentService()\n"
        "    return svc.settle(None)\n"
    )


@pytest.mark.asyncio
async def test_index_and_incremental(tmp_path: Path) -> None:
    if not await _stores_available():
        pytest.skip("Neo4j/Postgres not available")

    repo_id = uuid4()
    org_id = uuid4()
    repo_dir = tmp_path / "repo"
    _write_repo(repo_dir)

    db = await Database.connect()
    await db.migrate()
    graph = Neo4jCodeGraph()
    pipeline = IndexingPipeline(db=db, graph=graph)

    try:
        # ── Full index ────────────────────────────────────────────────────
        result = await pipeline.run(
            IndexRequest(repo_id=repo_id, org_id=org_id, source=str(repo_dir))
        )
        assert result.mode == "full"
        assert result.files_indexed == 3
        stats = result.stats
        # 3 module symbols + Ledger, post, record, PaymentService, settle, main
        assert stats["symbols"] >= 9
        assert stats["files"] == 3

        # settle() calls post(); resolves to Ledger.post across files.
        neigh = await graph.neighborhood(
            str(repo_id), ("PaymentService.settle", "billing/payment.py"), depth=2
        )
        assert neigh["found"] is True
        callee_names = {c["name"] for c in neigh["callees"]}
        assert "post" in callee_names

        # Impact of Ledger.post: settle (and transitively main) depend on it.
        impact = await graph.impact_analysis(
            str(repo_id), ("Ledger.post", "billing/core.py"), depth=3
        )
        assert impact["found"] is True
        assert impact["dependent_count"] >= 1
        assert 0.0 <= impact["risk_score"] <= 1.0

        # ── Incremental re-index: change one file only ────────────────────
        (repo_dir / "app.py").write_text(
            "from billing.payment import PaymentService\n\n"
            "def main():\n"
            "    return PaymentService()\n"  # no longer calls settle()
        )
        inc = await pipeline.run(
            IndexRequest(repo_id=repo_id, org_id=org_id, source=str(repo_dir))
        )
        assert inc.mode == "incremental"
        assert inc.files_indexed == 1  # only app.py re-parsed
        assert inc.files_deleted == 0

        # main() no longer calls settle → that edge must be gone.
        main_neigh = await graph.neighborhood(
            str(repo_id), ("main", "app.py"), depth=1
        )
        assert "settle" not in {c["name"] for c in main_neigh["callees"]}

        # ── Incremental re-index: delete a file ───────────────────────────
        os.remove(repo_dir / "app.py")
        deleted_run = await pipeline.run(
            IndexRequest(repo_id=repo_id, org_id=org_id, source=str(repo_dir))
        )
        assert deleted_run.files_deleted == 1
        gone = await graph.neighborhood(str(repo_id), ("main", "app.py"), depth=1)
        assert gone["found"] is False
    finally:
        await graph.purge_repo(str(repo_id))
        await graph.close()
        await db.close()
