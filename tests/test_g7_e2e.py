"""
Gate G7 Verification Tests: Full End-to-End Demo Journey & Confusion Matrix Evaluation
"""

from typing import Dict, List
from exasettle.core.config import run_preflight
from exasettle.generator.dataset_generator import generate_synthetic_dataset
from exasettle.engine.fallback_reconciler import LocalFallbackReconciler
from exasettle.simulation.mirofish_connector import MiroFishConnector
from exasettle.audit.logger import AuditLogStore
from exasettle.audit.exporter import generate_reconciliation_csv, generate_run_summary_json


def test_full_end_to_end_journey_and_confusion_matrix():
    """
    Execute full end-to-end demo workflow:
    Preflight -> Generator -> Reconciliation -> Simulation -> Audit -> Confusion Matrix -> Export
    """
    # 1. Preflight
    preflight = run_preflight()
    assert preflight.timestamp_utc is not None
    assert len(preflight.services) == 5

    # 2. Generator
    pkg = generate_synthetic_dataset(seed=42, run_id="e2e_demo_run_001")
    assert pkg.total_records >= 15
    assert len(pkg.ground_truth) == 8

    # 3. Reconciliation
    reconciler = LocalFallbackReconciler()
    results, metrics = reconciler.reconcile(
        pkg.gateway_records,
        pkg.bank_records,
        pkg.ground_truth,
        settlement_delay_threshold_hours=pkg.metadata["settlement_delay_threshold_hours"]
    )
    assert len(results) >= 8

    # 4. Simulation
    connector = MiroFishConnector()
    sim_events = []
    gw_map = {r.transaction_id: r for r in pkg.gateway_records}
    bk_map = {r.transaction_id: r for r in pkg.bank_records}
    gt_map = {g.transaction_id: g for g in pkg.ground_truth}

    for res in results:
        evs, _ = connector.run_simulation_for_case(
            result=res,
            ground_truth=gt_map.get(res.transaction_id),
            gw_record=gw_map.get(res.transaction_id),
            bk_record=bk_map.get(res.transaction_id),
            mode="PRERECORDED"
        )
        sim_events.extend(evs)
    assert len(sim_events) == len(results) * 3

    # 5. Audit
    audit = AuditLogStore()
    audit.record_event(pkg.run_id, pkg.scenario_id, "DATASET_GENERATION", "SUCCESS", "PYTHON", {"seed": 42})
    audit.record_event(pkg.run_id, pkg.scenario_id, "RECONCILIATION", "SUCCESS", metrics["engine"], metrics["timings_ms"])
    audit.record_event(pkg.run_id, pkg.scenario_id, "SIMULATION", "SUCCESS", "MIROFISH", {"events": len(sim_events)})
    assert audit.verify_chain_integrity() is True

    # 6. Evaluation: Confusion Matrix & Metrics Calculation
    classes = [
        "MATCHED", "FEE_VARIANCE_MDR", "AMOUNT_MISMATCH", "MISSING_IN_BANK",
        "MISSING_IN_GATEWAY", "DUPLICATE", "SETTLEMENT_DELAY", "AMBIGUOUS_REVIEW"
    ]
    confusion_matrix: Dict[str, Dict[str, int]] = {c: {p: 0 for p in classes} for c in classes}

    res_map = {r.transaction_id: r for r in results}
    for gt in pkg.ground_truth:
        res = res_map.get(gt.transaction_id)
        assert res is not None
        actual = gt.expected_classification.value
        predicted = res.classification.value
        confusion_matrix[actual][predicted] += 1

    # Verify 100% diagonal match on known answers
    for c in classes:
        assert confusion_matrix[c][c] >= 1, f"Expected known case for {c} to be identified"
        for other in classes:
            if other != c:
                assert confusion_matrix[c][other] == 0, f"False positive in known case: {c} misclassified as {other}"

    # 7. Export verification
    csv_out = generate_reconciliation_csv(results, pkg.run_id, pkg.scenario_id, metrics["engine"])
    assert "TXN_SYN_101" in csv_out
    assert "Synthetic demo transaction" in csv_out

    json_report = generate_run_summary_json(
        pkg.run_id, pkg.scenario_id, pkg.seed, pkg.dataset_hash, metrics, results, sim_events,
        [e.model_dump() for e in audit.get_run_events(pkg.run_id)]
    )
    assert json_report["reconciliation_summary"]["ground_truth_accuracy"]["accuracy_percent"] == 100.0
    assert "AI-simulated scenario — not real customer feedback" in json_report["report_metadata"]["simulation_disclosure"]
