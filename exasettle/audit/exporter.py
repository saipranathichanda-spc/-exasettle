"""
Export and reporting engine for ExaSettle.
Implements PRD Section 9.7:
- Generates downloadable CSV exception and reconciliation reports
- Generates JSON run summaries with hashes and audit metadata
- Enforces strict zero-credential-leakage policy
- Retains persistent synthetic transaction and simulation disclosures
"""

import csv
import io
import json
from typing import List, Dict, Any, Optional

from exasettle.core.models import ReconciliationResult, SimulationEvent, LedgerRecord
from exasettle.core.money import format_inr, paise_to_rupees


def generate_reconciliation_csv(
    results: List[ReconciliationResult],
    run_id: str,
    scenario_id: str,
    engine_name: str
) -> str:
    """Generate RFC-4180 compliant CSV export containing all reconciliation evidence."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header metadata comment rows
    writer.writerow(["# EXASETTLE RECONCILIATION AUDIT EXPORT"])
    writer.writerow([f"# Run ID: {run_id}"])
    writer.writerow([f"# Scenario ID: {scenario_id}"])
    writer.writerow([f"# Reconciliation Engine: {engine_name}"])
    writer.writerow(["# NOTICE: All transaction data is synthetic. Not for production financial use."])
    writer.writerow([])

    # Table header
    headers = [
        "Transaction ID",
        "Classification",
        "Priority Score (0-100)",
        "Validation Status",
        "Ground Truth Label",
        "Gateway Record ID",
        "Bank Record ID",
        "Gateway Amount (INR)",
        "Bank Amount (INR)",
        "Difference (INR)",
        "Applied Rule",
        "Priority Explanation",
        "Disclosure Notice"
    ]
    writer.writerow(headers)

    for r in results:
        gw_amt_str = f"{paise_to_rupees(r.gateway_amount_paise):.2f}" if r.gateway_amount_paise is not None else "N/A"
        bk_amt_str = f"{paise_to_rupees(r.bank_amount_paise):.2f}" if r.bank_amount_paise is not None else "N/A"
        diff_str = f"{paise_to_rupees(r.difference_paise):.2f}"

        writer.writerow([
            r.transaction_id,
            r.classification.value,
            r.priority_score,
            r.validation_status,
            r.ground_truth_label or "N/A",
            r.gateway_record_id or "[MISSING]",
            r.bank_record_id or "[MISSING]",
            gw_amt_str,
            bk_amt_str,
            diff_str,
            r.applied_rule,
            r.priority_explanation,
            "Synthetic demo transaction"
        ])

    return output.getvalue()


def generate_run_summary_json(
    run_id: str,
    scenario_id: str,
    seed: int,
    dataset_hash: str,
    engine_metrics: Dict[str, Any],
    results: List[ReconciliationResult],
    simulation_events: List[SimulationEvent],
    audit_events: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Generate comprehensive JSON report containing all run metadata and audit hashes."""
    # Compute accuracy metrics against ground truth
    total_evaluated = sum(1 for r in results if r.validation_status != "UNVALIDATED")
    total_correct = sum(1 for r in results if r.validation_status == "VALIDATED_CORRECT")
    accuracy_pct = round((total_correct / total_evaluated * 100), 2) if total_evaluated > 0 else 100.0

    # Count by classification
    class_counts: Dict[str, int] = {}
    for r in results:
        c_val = r.classification.value
        class_counts[c_val] = class_counts.get(c_val, 0) + 1

    total_amount_at_issue_paise = sum(r.difference_paise for r in results if r.classification.value != "MATCHED")

    report = {
        "report_metadata": {
            "title": "ExaSettle Settlement Reconciliation Run Report",
            "competition": "ExaThon India 2026 - Track 01: Money, Risk & Regulation",
            "run_id": run_id,
            "scenario_id": scenario_id,
            "seed": seed,
            "dataset_hash": dataset_hash,
            "synthetic_disclosure": "All data generated synthetically for hackathon demonstration. No real money or citizens.",
            "simulation_disclosure": "AI-simulated scenario — not real customer feedback"
        },
        "engine_execution": {
            "engine": engine_metrics.get("engine", "UNKNOWN"),
            "engine_mode": engine_metrics.get("engine_mode", "LOCAL_FALLBACK"),
            "is_fallback": engine_metrics.get("is_fallback", True),
            "sql_query_type": engine_metrics.get("sql_query_type", "CTE_WINDOW_FULL_OUTER_JOIN"),
            "timings_ms": engine_metrics.get("timings_ms", {}),
            "counts": engine_metrics.get("counts", {})
        },
        "reconciliation_summary": {
            "total_transactions": len(results),
            "clean_matches": class_counts.get("MATCHED", 0),
            "total_exceptions": len(results) - class_counts.get("MATCHED", 0),
            "total_amount_at_issue": format_inr(total_amount_at_issue_paise),
            "amount_at_issue_paise": total_amount_at_issue_paise,
            "classification_breakdown": class_counts,
            "ground_truth_accuracy": {
                "evaluated_known_cases": total_evaluated,
                "correctly_classified": total_correct,
                "accuracy_percent": accuracy_pct
            }
        },
        "results": [r.model_dump() for r in results],
        "simulation_events": [e.model_dump() for e in simulation_events],
        "audit_trail": audit_events
    }
    return report
