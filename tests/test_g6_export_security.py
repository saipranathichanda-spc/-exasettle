"""
Gate G6 Verification Tests: Export Integrity, Audit Trail & Secret Redaction
"""

import json
from exasettle.generator.dataset_generator import generate_synthetic_dataset
from exasettle.engine.fallback_reconciler import LocalFallbackReconciler
from exasettle.simulation.prerecorded_store import get_prerecorded_events
from exasettle.audit.logger import AuditLogStore
from exasettle.audit.exporter import generate_reconciliation_csv, generate_run_summary_json


def test_csv_export_structure_and_disclosure():
    """Verify CSV export contains all rows, correct totals, and synthetic disclosures."""
    pkg = generate_synthetic_dataset(seed=42)
    reconciler = LocalFallbackReconciler()
    results, metrics = reconciler.reconcile(pkg.gateway_records, pkg.bank_records, pkg.ground_truth)

    csv_data = generate_reconciliation_csv(
        results=results,
        run_id=pkg.run_id,
        scenario_id=pkg.scenario_id,
        engine_name=metrics["engine"]
    )

    assert "EXASETTLE RECONCILIATION AUDIT EXPORT" in csv_data
    assert "Synthetic demo transaction" in csv_data
    assert "TXN_SYN_101" in csv_data
    assert "MATCHED" in csv_data
    assert "FEE_VARIANCE_MDR" in csv_data
    assert "AMOUNT_MISMATCH" in csv_data

    # Count rows in CSV
    lines = [l.strip() for l in csv_data.splitlines() if l.strip() and not l.strip().startswith("#")]
    # First row is header, rest are results
    assert len(lines) - 1 == len(results)


def test_json_summary_and_audit_hash_chain():
    """Verify JSON export integrity and unbroken audit hash chain."""
    pkg = generate_synthetic_dataset(seed=42)
    reconciler = LocalFallbackReconciler()
    results, metrics = reconciler.reconcile(pkg.gateway_records, pkg.bank_records, pkg.ground_truth)

    audit = AuditLogStore()
    e1 = audit.record_event(pkg.run_id, pkg.scenario_id, "GENERATION", "SUCCESS", "PYTHON", {"seed": 42})
    e2 = audit.record_event(pkg.run_id, pkg.scenario_id, "RECONCILIATION", "SUCCESS", metrics["engine"], metrics["timings_ms"])

    assert audit.verify_chain_integrity() is True

    sim_events = []
    for r in results:
        sim_events.extend(get_prerecorded_events(pkg.scenario_id, r.transaction_id, pkg.run_id))

    json_report = generate_run_summary_json(
        run_id=pkg.run_id,
        scenario_id=pkg.scenario_id,
        seed=pkg.seed,
        dataset_hash=pkg.dataset_hash,
        engine_metrics=metrics,
        results=results,
        simulation_events=sim_events,
        audit_events=[e.model_dump() for e in [e1, e2]]
    )

    assert json_report["report_metadata"]["run_id"] == pkg.run_id
    assert json_report["report_metadata"]["dataset_hash"] == pkg.dataset_hash
    assert json_report["reconciliation_summary"]["ground_truth_accuracy"]["accuracy_percent"] == 100.0
    assert "AI-simulated scenario" in json_report["report_metadata"]["simulation_disclosure"]


def test_zero_credential_leakage_in_exports():
    """Verify that no sensitive credential strings ever appear in exports."""
    pkg = generate_synthetic_dataset(seed=42)
    reconciler = LocalFallbackReconciler()
    results, metrics = reconciler.reconcile(pkg.gateway_records, pkg.bank_records, pkg.ground_truth)

    csv_data = generate_reconciliation_csv(results, pkg.run_id, pkg.scenario_id, metrics["engine"])
    json_data = json.dumps(generate_run_summary_json(
        pkg.run_id, pkg.scenario_id, pkg.seed, pkg.dataset_hash, metrics, results, [], []
    ))

    sensitive_patterns = ["password", "secret_key", "sk-proj-", "token=", "bearer "]
    for pat in sensitive_patterns:
        assert pat not in csv_data.lower()
        assert pat not in json_data.lower()
