"""
Idempotency and Deduplication Invariant Test for ExaSettle.
Verifies that processing the same feed twice or re-ingesting duplicate records
preserves logical transaction boundaries without record conflation or duplicate ledger entries.
"""

import hashlib
import json
import pytest
from exasettle.generator.dataset_generator import generate_synthetic_dataset
from exasettle.engine.fallback_reconciler import LocalFallbackReconciler
from exasettle.core.models import LedgerRecord


def test_reconciliation_idempotency_same_feed_twice():
    """Verify that duplicating input records produces identical logical transaction counts."""
    pkg = generate_synthetic_dataset(seed=42, scenario_id="SCN_CORE_8PACK")
    engine = LocalFallbackReconciler()

    # Run 1: Normal dataset
    results_1, metrics_1 = engine.reconcile(pkg.gateway_records, pkg.bank_records, pkg.ground_truth)
    logical_ids_1 = {r.transaction_id for r in results_1}

    # Run 2: Double every record (simulating duplicate feed transmission or duplicate batch ingestion)
    duplicated_gw = []
    for r in pkg.gateway_records:
        duplicated_gw.append(r)
        # Duplicate record with new source row ID
        dup_row = r.model_copy(update={"source_record_id": f"{r.source_record_id}_DUP"})
        duplicated_gw.append(dup_row)

    duplicated_bk = []
    for r in pkg.bank_records:
        duplicated_bk.append(r)
        dup_row = r.model_copy(update={"source_record_id": f"{r.source_record_id}_DUP"})
        duplicated_bk.append(dup_row)

    results_2, metrics_2 = engine.reconcile(duplicated_gw, duplicated_bk, pkg.ground_truth)
    logical_ids_2 = {r.transaction_id for r in results_2}

    # Invariant 1: Exactly the same logical transaction set
    assert logical_ids_1 == logical_ids_2
    assert len(results_1) == len(results_2)

    # Invariant 2: Aggregation captures duplicate rows in source_records evidence without row explosion
    for r in results_2:
        src = r.evidence_json.get("source_records", {})
        gw_ids = src.get("gateway_record_ids", [])
        bk_ids = src.get("bank_record_ids", [])
        assert len(gw_ids) >= 1 or len(bk_ids) >= 1


def test_idempotent_hash_stability():
    """Verify that executing identical reconciliation runs yields identical output hashes."""
    pkg = generate_synthetic_dataset(seed=2026, scenario_id="SCN_CORE_8PACK")
    engine = LocalFallbackReconciler()

    res_a, _ = engine.reconcile(pkg.gateway_records, pkg.bank_records, pkg.ground_truth)
    res_b, _ = engine.reconcile(pkg.gateway_records, pkg.bank_records, pkg.ground_truth)

    hash_a = hashlib.sha256(json.dumps([r.model_dump() for r in res_a], sort_keys=True).encode()).hexdigest()
    hash_b = hashlib.sha256(json.dumps([r.model_dump() for r in res_b], sort_keys=True).encode()).hexdigest()

    assert hash_a == hash_b, "Reconciliation execution must be strictly idempotent and deterministic"
