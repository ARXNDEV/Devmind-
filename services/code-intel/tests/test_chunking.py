"""Chunking is pure: parsing IR + bytes in, deterministic chunks out."""

from devmind_code_intel.indexing.chunking import chunk_file, chunk_id
from devmind_code_intel.parsing import extract_file

REPO = "11111111-1111-1111-1111-111111111111"

PY_SOURCE = b'''"""Payments module."""

import decimal


class PaymentService:
    """Settles invoices."""

    retries = 3

    def settle(self, invoice_id: str) -> bool:
        """Settle one invoice."""
        return invoice_id != ""

    def refund(self, invoice_id: str) -> bool:
        return not self.settle(invoice_id)


def audit(event: str) -> None:
    print(event)
'''


def _chunks(source: bytes, path: str = "payments.py"):
    ir = extract_file(path, source)
    assert ir is not None
    return chunk_file(REPO, path, ir.language, source, ir)


def test_emits_preamble_leaf_and_container_chunks() -> None:
    chunks = _chunks(PY_SOURCE)
    by_fqn = {c.fqn: c for c in chunks}

    preamble = by_fqn[None]
    assert preamble.start_line == 1
    assert "import decimal" in preamble.text

    assert "def settle" in by_fqn["PaymentService.settle"].text
    assert "def refund" in by_fqn["PaymentService.refund"].text
    assert "def audit" in by_fqn["audit"].text

    # The class header covers docstring and fields but not method bodies —
    # those belong to the method chunks alone.
    header = by_fqn["PaymentService"]
    assert "Settles invoices" in header.text
    assert "retries = 3" in header.text
    assert "def settle" not in header.text


def test_chunk_text_carries_citation_header() -> None:
    settle = next(c for c in _chunks(PY_SOURCE) if c.fqn == "PaymentService.settle")
    first_line = settle.text.splitlines()[0]
    assert first_line.startswith(f"payments.py:{settle.start_line}-{settle.end_line}")
    assert "PaymentService.settle" in first_line


def test_ids_are_deterministic_and_unique() -> None:
    first = _chunks(PY_SOURCE)
    second = _chunks(PY_SOURCE)
    assert [c.id for c in first] == [c.id for c in second]
    assert len({c.id for c in first}) == len(first)
    assert chunk_id(REPO, "payments.py", "audit", 0) != chunk_id(
        REPO, "other.py", "audit", 0
    )


def test_long_function_is_windowed_with_overlap() -> None:
    body = "\n".join(f"    x{i} = {i}" for i in range(400))
    source = f"def huge() -> None:\n{body}\n".encode()
    chunks = _chunks(source, path="huge.py")

    windows = [c for c in chunks if c.fqn == "huge"]
    assert len(windows) > 1
    # Consecutive windows overlap so no statement is lost at a boundary.
    for prev, nxt in zip(windows, windows[1:], strict=False):
        assert nxt.start_line < prev.end_line
    assert windows[-1].end_line >= 400


def test_empty_file_yields_no_chunks() -> None:
    ir = extract_file("empty.py", b"")
    assert ir is not None
    assert chunk_file(REPO, "empty.py", ir.language, b"", ir) == []
