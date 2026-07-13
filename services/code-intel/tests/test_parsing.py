"""Extractor tests — assert IR against hand-verified fixtures."""

from devmind_code_intel.parsing import extract_file
from devmind_code_intel.parsing.ir import SymbolKind

PYTHON_SOURCE = b'''import os
from billing.core import Ledger, settle

TAX_RATE = 0.2


class PaymentService(BaseService):
    """Handles settlement."""

    def settle(self, invoice):
        total = compute(invoice)
        return self.ledger.post(total)


def compute(invoice):
    return invoice.amount * TAX_RATE
'''

TYPESCRIPT_SOURCE = b'''import { Ledger, settle } from "./billing/core";
import React from "react";

export const TAX_RATE = 0.2;

interface Invoice { amount: number; }

export class PaymentService extends BaseService implements Billable {
  settle(invoice: Invoice): number {
    const total = compute(invoice);
    return this.ledger.post(total);
  }
}

function compute(invoice: Invoice): number {
  return invoice.amount * TAX_RATE;
}

const helper = (x: number) => compute(x);
'''


def _by_kind(ir, kind):
    return {s.fqn for s in ir.symbols if s.kind == kind}


def test_python_symbols_and_edges() -> None:
    ir = extract_file("billing/payment.py", PYTHON_SOURCE)
    assert ir is not None
    assert ir.parse_errors == 0

    assert _by_kind(ir, SymbolKind.CLASS) == {"PaymentService"}
    assert _by_kind(ir, SymbolKind.METHOD) == {"PaymentService.settle"}
    assert _by_kind(ir, SymbolKind.FUNCTION) == {"compute"}
    assert _by_kind(ir, SymbolKind.VARIABLE) == {"TAX_RATE"}  # no duplicates

    settle = next(s for s in ir.symbols if s.fqn == "PaymentService.settle")
    assert settle.signature == "settle(self, invoice)"
    cls = next(s for s in ir.symbols if s.fqn == "PaymentService")
    assert cls.docstring == '"""Handles settlement."""'

    imports = {i.module: i.symbols for i in ir.imports}
    assert imports["os"] == ()
    assert imports["billing.core"] == ("Ledger", "settle")  # module not leaked

    calls = {(c.caller_fqn, c.callee_name) for c in ir.calls}
    assert ("PaymentService.settle", "compute") in calls
    assert ("PaymentService.settle", "post") in calls

    inh = {(h.subclass_fqn, h.kind, h.base_name) for h in ir.inheritance}
    assert ("PaymentService", "inherits", "BaseService") in inh


def test_typescript_symbols_and_edges() -> None:
    ir = extract_file("billing/payment.ts", TYPESCRIPT_SOURCE)
    assert ir is not None
    assert ir.parse_errors == 0

    assert "PaymentService" in _by_kind(ir, SymbolKind.CLASS)
    assert "PaymentService.settle" in _by_kind(ir, SymbolKind.METHOD)
    assert {"compute", "helper"} <= _by_kind(ir, SymbolKind.FUNCTION)
    assert "Invoice" in _by_kind(ir, SymbolKind.INTERFACE)
    assert "TAX_RATE" in _by_kind(ir, SymbolKind.VARIABLE)

    calls = {(c.caller_fqn, c.callee_name) for c in ir.calls}
    # The initializer-call bug: compute() inside settle and helper must appear.
    assert ("PaymentService.settle", "compute") in calls
    assert ("PaymentService.settle", "post") in calls
    assert ("helper", "compute") in calls

    inh = {(h.subclass_fqn, h.kind, h.base_name) for h in ir.inheritance}
    assert ("PaymentService", "inherits", "BaseService") in inh
    assert ("PaymentService", "implements", "Billable") in inh

    modules = {i.module for i in ir.imports}
    assert "./billing/core" in modules
    assert "react" in modules


JAVA_SOURCE = b"""package com.acme.billing;
import com.acme.core.Ledger;

public class PaymentService extends BaseService implements Billable {
    private int taxRate;
    public int settle(Invoice invoice) {
        int total = compute(invoice);
        return this.ledger.post(total);
    }
}
"""

GO_SOURCE = b"""package billing
import "fmt"

type Ledger struct { balance int }
type Billable interface { Settle() int }

func (l *Ledger) Post(amount int) int {
    return record(amount)
}
func record(amount int) int { return amount }
"""


def test_java_symbols_and_edges() -> None:
    ir = extract_file("PaymentService.java", JAVA_SOURCE)
    assert ir is not None and ir.parse_errors == 0
    assert "PaymentService" in _by_kind(ir, SymbolKind.CLASS)
    assert "PaymentService.settle" in _by_kind(ir, SymbolKind.METHOD)
    calls = {(c.caller_fqn, c.callee_name) for c in ir.calls}
    assert ("PaymentService.settle", "compute") in calls
    assert ("PaymentService.settle", "post") in calls
    inh = {(h.subclass_fqn, h.kind, h.base_name) for h in ir.inheritance}
    assert ("PaymentService", "inherits", "BaseService") in inh
    assert ("PaymentService", "implements", "Billable") in inh
    assert "com.acme.core.Ledger" in {i.module for i in ir.imports}


def test_go_symbols_and_edges() -> None:
    ir = extract_file("ledger.go", GO_SOURCE)
    assert ir is not None and ir.parse_errors == 0
    assert "Ledger" in _by_kind(ir, SymbolKind.CLASS)
    assert "Billable" in _by_kind(ir, SymbolKind.INTERFACE)
    # Method qualified by its receiver type.
    assert "Ledger.Post" in _by_kind(ir, SymbolKind.METHOD)
    assert "record" in _by_kind(ir, SymbolKind.FUNCTION)
    assert ("Ledger.Post", "record") in {
        (c.caller_fqn, c.callee_name) for c in ir.calls
    }


def test_unsupported_language_returns_none() -> None:
    assert extract_file("data/config.toml", b"[x]\ny = 1\n") is None


def test_malformed_source_does_not_raise() -> None:
    ir = extract_file("broken.py", b"def (:\n  pass\n  return")
    assert ir is not None
    assert ir.parse_errors > 0
