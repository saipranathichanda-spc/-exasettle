"""
Core deterministic reconciliation logic for ExaSettle.
Implements PRD Section 9.4 & Stage Gate G3:
- Logical transaction-level aggregation and reconciliation
- In-database SQL classification via CASE statement
- Separates logical transaction classification from source-row anomalies
- Eliminates row overwrites in dictionaries
- Deterministic operational triage priority scoring
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from exasettle.core.models import (
    LedgerRecord,
    GroundTruthRecord,
    ReconciliationResult,
    ReconciliationClassification
)
from exasettle.engine.priority_score import calculate_priority_score


# ANSI SQL query with CTE aggregation, FULL OUTER JOIN, and in-database SQL classification
RECONCILIATION_SQL = """
WITH gw_agg AS (
    SELECT 
        transaction_id,
        run_id,
        scenario_id,
        COUNT(*) as gw_count,
        SUM(amount_paise) as gw_amount_paise,
        SUM(fee_paise) as gw_fee_paise,
        MIN(event_timestamp_utc) as gw_timestamp,
        MAX(status) as gw_status,
        MAX(reversal_status) as gw_reversal,
        GROUP_CONCAT(source_record_id, ', ') as gw_record_ids,
        GROUP_CONCAT(gateway_reference, ', ') as gw_references,
        GROUP_CONCAT(bank_reference, ', ') as gw_bank_references
    FROM gateway_records
    WHERE run_id = ?
    GROUP BY transaction_id, run_id, scenario_id
),
bk_agg AS (
    SELECT 
        transaction_id,
        run_id,
        scenario_id,
        COUNT(*) as bk_count,
        SUM(amount_paise) as bk_amount_paise,
        SUM(fee_paise) as bk_fee_paise,
        MAX(settlement_timestamp_utc) as bk_timestamp,
        MAX(status) as bk_status,
        MAX(reversal_status) as bk_reversal,
        GROUP_CONCAT(source_record_id, ', ') as bk_record_ids,
        GROUP_CONCAT(gateway_reference, ', ') as bk_gw_references,
        GROUP_CONCAT(bank_reference, ', ') as bk_references
    FROM bank_records
    WHERE run_id = ?
    GROUP BY transaction_id, run_id, scenario_id
),
joined AS (
    SELECT 
        COALESCE(gw.transaction_id, bk.transaction_id) as transaction_id,
        COALESCE(gw.run_id, bk.run_id) as run_id,
        COALESCE(gw.scenario_id, bk.scenario_id) as scenario_id,
        COALESCE(gw.gw_count, 0) as gw_count,
        COALESCE(bk.bk_count, 0) as bk_count,
        gw.gw_record_ids,
        bk.bk_record_ids,
        gw.gw_references,
        bk.bk_references,
        gw.gw_bank_references,
        bk.bk_gw_references,
        gw.gw_amount_paise,
        bk.bk_amount_paise,
        gw.gw_fee_paise,
        bk.bk_fee_paise,
        gw.gw_timestamp,
        bk.bk_timestamp,
        gw.gw_status,
        bk.bk_status,
        gw.gw_reversal
    FROM gw_agg gw
    FULL OUTER JOIN bk_agg bk 
        ON gw.transaction_id = bk.transaction_id
)
SELECT 
    *,
    CASE 
        WHEN gw_count > 1 OR bk_count > 1 THEN 'DUPLICATE'
        WHEN gw_count > 0 AND bk_count = 0 THEN 'MISSING_IN_BANK'
        WHEN gw_count = 0 AND bk_count > 0 THEN 'MISSING_IN_GATEWAY'
        WHEN (gw_status = 'REVERSED' AND bk_status = 'SETTLED') OR (gw_reversal IS NOT NULL AND gw_reversal != 'NONE') THEN 'AMBIGUOUS_REVIEW'
        WHEN gw_amount_paise != bk_amount_paise THEN 'AMOUNT_MISMATCH'
        WHEN gw_fee_paise != bk_fee_paise THEN 'FEE_VARIANCE_MDR'
        ELSE 'CANDIDATE_MATCH'
    END as preliminary_sql_classification,
    ABS(COALESCE(gw_amount_paise, 0) - COALESCE(bk_amount_paise, 0)) as diff_amount_paise,
    ABS(COALESCE(gw_fee_paise, 0) - COALESCE(bk_fee_paise, 0)) as diff_fee_paise
FROM joined
ORDER BY transaction_id ASC
"""


def parse_iso_datetime(ts_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO timestamp safely."""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


def classify_matched_row(
    row: Dict[str, Any],
    settlement_delay_threshold_hours: float = 24.0
) -> Tuple[ReconciliationClassification, str, int, bool, float, bool]:
    """
    Classify a joined gateway/bank record row.
    Returns:
    (classification, applied_rule, difference_paise, is_duplicate, settlement_delay_hours, status_conflict)
    """
    gw_id = row.get("gw_record_id")
    bk_id = row.get("bk_record_id")
    gw_amt = row.get("gw_amount_paise")
    bk_amt = row.get("bk_amount_paise")
    gw_fee = row.get("gw_fee_paise")
    bk_fee = row.get("bk_fee_paise")
    gw_status = row.get("gw_status")
    bk_status = row.get("bk_status")
    gw_rev = row.get("gw_reversal")
    gw_dup = row.get("gw_dup_count", row.get("gw_count", 0))
    bk_dup = row.get("bk_dup_count", row.get("bk_count", 0))
    rn = row.get("rn", 1)

    is_duplicate = (gw_dup > 1 or bk_dup > 1 or rn > 1)

    gw_time = parse_iso_datetime(row.get("gw_timestamp"))
    bk_time = parse_iso_datetime(row.get("bk_timestamp"))
    delay_hours = 0.0
    if gw_time and bk_time:
        delta = bk_time - gw_time
        delay_hours = max(0.0, delta.total_seconds() / 3600.0)

    if is_duplicate:
        rule = f"RULE_DUPLICATE_CHECK: Duplicate submissions detected (Gateway copies: {gw_dup}, Bank copies: {bk_dup})."
        return (ReconciliationClassification.DUPLICATE, rule, 0, True, delay_hours, False)

    if gw_id is not None and bk_id is None:
        diff = gw_amt if gw_amt is not None else 0
        rule = "RULE_MISSING_BANK: Gateway captured payment but no corresponding bank settlement record found."
        return (ReconciliationClassification.MISSING_IN_BANK, rule, diff, is_duplicate, delay_hours, False)

    if gw_id is None and bk_id is not None:
        diff = bk_amt if bk_amt is not None else 0
        rule = "RULE_MISSING_GATEWAY: Bank settlement record exists without originating gateway capture record."
        return (ReconciliationClassification.MISSING_IN_GATEWAY, rule, diff, is_duplicate, delay_hours, False)

    status_conflict = False
    if (gw_status == "REVERSED" and bk_status == "SETTLED") or (gw_rev and gw_rev != "NONE"):
        status_conflict = True
        rule = f"RULE_STATUS_CONFLICT: Gateway status '{gw_status}' (Reversal: {gw_rev}) conflicts with Bank status '{bk_status}'."
        return (ReconciliationClassification.AMBIGUOUS_REVIEW, rule, 0, False, delay_hours, True)

    diff_amount = abs((gw_amt or 0) - (bk_amt or 0))
    if diff_amount != 0:
        rule = f"RULE_AMOUNT_MISMATCH: Gateway principal amount (₹{(gw_amt or 0)/100:.2f}) does not match Bank settled amount (₹{(bk_amt or 0)/100:.2f})."
        return (ReconciliationClassification.AMOUNT_MISMATCH, rule, diff_amount, False, delay_hours, False)

    if delay_hours > settlement_delay_threshold_hours:
        rule = f"RULE_SETTLEMENT_DELAY: Settlement elapsed time ({delay_hours:.1f}h) exceeds configured scenario threshold ({settlement_delay_threshold_hours:.1f}h)."
        return (ReconciliationClassification.SETTLEMENT_DELAY, rule, 0, False, delay_hours, False)

    if gw_fee != bk_fee:
        diff_fee = abs((gw_fee or 0) - (bk_fee or 0))
        rule = f"RULE_FEE_VARIANCE: Gateway fee schedule (₹{(gw_fee or 0)/100:.2f}) differs from Bank deducted fee (₹{(bk_fee or 0)/100:.2f}) by ₹{diff_fee/100:.2f}."
        return (ReconciliationClassification.FEE_VARIANCE_MDR, rule, diff_fee, False, delay_hours, False)

    rule = "RULE_CLEAN_MATCH: All identifiers, principal amount, fee schedule, and settlement time windows verified."
    return (ReconciliationClassification.MATCHED, rule, 0, False, delay_hours, False)


def resolve_reconciliation_results(
    joined_rows: List[Dict[str, Any]],
    ground_truth_map: Dict[str, GroundTruthRecord],
    settlement_delay_threshold_hours: float = 24.0
) -> List[ReconciliationResult]:
    """
    Resolve joined database rows into structured logical ReconciliationResults.
    Each logical transaction receives exactly ONE classification.
    """
    results: List[ReconciliationResult] = []

    for row in joined_rows:
        txn_id = row["transaction_id"]
        run_id = row["run_id"]
        scenario_id = row["scenario_id"]

        gw_count = row.get("gw_count", 0)
        bk_count = row.get("bk_count", 0)
        gw_amt = row.get("gw_amount_paise")
        bk_amt = row.get("bk_amount_paise")
        gw_fee = row.get("gw_fee_paise")
        bk_fee = row.get("bk_fee_paise")
        sql_cls = row.get("preliminary_sql_classification", "CANDIDATE_MATCH")

        gw_rec_ids = [s.strip() for s in (row.get("gw_record_ids") or "").split(",") if s.strip()]
        bk_rec_ids = [s.strip() for s in (row.get("bk_record_ids") or "").split(",") if s.strip()]

        # Compute source row anomalies
        anomalies: List[str] = []
        is_duplicate = False
        if gw_count > 1:
            anomalies.append(f"DUPLICATE_GATEWAY_SUBMISSION: {gw_count} physical gateway rows for 1 logical transaction")
            is_duplicate = True
        if bk_count > 1:
            anomalies.append(f"DUPLICATE_BANK_SETTLEMENT: {bk_count} physical bank settlement rows for 1 logical transaction")
            is_duplicate = True

        # Calculate timestamps & settlement delay
        gw_time = parse_iso_datetime(row.get("gw_timestamp"))
        bk_time = parse_iso_datetime(row.get("bk_timestamp"))
        delay_hours = 0.0
        if gw_time and bk_time:
            delta = bk_time - gw_time
            delay_hours = max(0.0, delta.total_seconds() / 3600.0)

        # Final classification resolution
        status_conflict = False
        if sql_cls == "DUPLICATE":
            classification = ReconciliationClassification.DUPLICATE
            diff_paise = 0
            rule = f"RULE_DUPLICATE_CHECK: Duplicate submissions detected in SQL aggregation (Gateway rows: {gw_count}, Bank rows: {bk_count})."
        elif sql_cls == "MISSING_IN_BANK":
            classification = ReconciliationClassification.MISSING_IN_BANK
            diff_paise = gw_amt if gw_amt is not None else 0
            rule = "RULE_MISSING_BANK: Gateway captured payment but no corresponding bank settlement record found."
            anomalies.append("MISSING_SETTLEMENT_ROW: Zero bank settlement records in feed")
        elif sql_cls == "MISSING_IN_GATEWAY":
            classification = ReconciliationClassification.MISSING_IN_GATEWAY
            diff_paise = bk_amt if bk_amt is not None else 0
            rule = "RULE_MISSING_GATEWAY: Bank settlement record exists without originating gateway capture record."
            anomalies.append("ORPHANED_BANK_CREDIT: Bank credit without originating gateway event")
        elif sql_cls == "AMBIGUOUS_REVIEW":
            classification = ReconciliationClassification.AMBIGUOUS_REVIEW
            diff_paise = 0
            status_conflict = True
            rule = f"RULE_STATUS_CONFLICT: Gateway status '{row.get('gw_status')}' conflicts with Bank status '{row.get('bk_status')}'."
            anomalies.append(f"STATUS_CONFLICT: Gateway={row.get('gw_status')} vs Bank={row.get('bk_status')}")
        elif sql_cls == "AMOUNT_MISMATCH":
            classification = ReconciliationClassification.AMOUNT_MISMATCH
            diff_paise = abs((gw_amt or 0) - (bk_amt or 0))
            rule = f"RULE_AMOUNT_MISMATCH: Gateway principal (₹{(gw_amt or 0)/100:.2f}) does not match Bank settled (₹{(bk_amt or 0)/100:.2f})."
            anomalies.append(f"AMOUNT_VARIANCE: ₹{diff_paise/100:.2f}")
        elif sql_cls == "FEE_VARIANCE_MDR":
            classification = ReconciliationClassification.FEE_VARIANCE_MDR
            diff_paise = abs((gw_fee or 0) - (bk_fee or 0))
            rule = f"RULE_FEE_VARIANCE: Gateway fee (₹{(gw_fee or 0)/100:.2f}) differs from Bank fee (₹{(bk_fee or 0)/100:.2f}) by ₹{diff_paise/100:.2f}."
            anomalies.append(f"MDR_FEE_SCHEDULE_VARIANCE: ₹{diff_paise/100:.2f}")
        else:
            # Candidate match: check settlement timing threshold
            if delay_hours > settlement_delay_threshold_hours:
                classification = ReconciliationClassification.SETTLEMENT_DELAY
                diff_paise = 0
                rule = f"RULE_SETTLEMENT_DELAY: Settlement elapsed time ({delay_hours:.1f}h) exceeds scenario threshold ({settlement_delay_threshold_hours:.1f}h)."
                anomalies.append(f"SETTLEMENT_LATENCY_EXCEEDED: {delay_hours:.1f}h elapsed")
            else:
                classification = ReconciliationClassification.MATCHED
                diff_paise = 0
                rule = "RULE_CLEAN_MATCH: All identifiers, principal amount, fee schedule, and settlement time windows verified."

        # Compute deterministic priority score
        score, explanation, breakdown = calculate_priority_score(
            classification=classification,
            difference_paise=diff_paise,
            gateway_amount_paise=gw_amt,
            bank_amount_paise=bk_amt,
            is_duplicate=is_duplicate,
            settlement_delay_hours=delay_hours,
            delay_threshold_hours=settlement_delay_threshold_hours,
            status_conflict=status_conflict
        )

        # Ground truth comparison
        gt = ground_truth_map.get(txn_id)
        gt_label = gt.expected_classification.value if gt else None
        if gt:
            validation_status = "VALIDATED_CORRECT" if gt.expected_classification == classification else "MISMATCH"
        else:
            validation_status = "UNVALIDATED"

        evidence = {
            "logical_transaction_id": txn_id,
            "source_records": {
                "gateway_record_ids": gw_rec_ids,
                "bank_record_ids": bk_rec_ids,
                "gateway_count": gw_count,
                "bank_count": bk_count
            },
            "financial_values": {
                "gateway_amount_paise": gw_amt,
                "bank_amount_paise": bk_amt,
                "difference_paise": diff_paise,
                "gateway_fee_paise": gw_fee,
                "bank_fee_paise": bk_fee
            },
            "timing": {
                "gateway_timestamp": row.get("gw_timestamp"),
                "bank_timestamp": row.get("bk_timestamp"),
                "elapsed_settlement_hours": round(delay_hours, 2),
                "threshold_hours": settlement_delay_threshold_hours
            },
            "state": {
                "gateway_status": row.get("gw_status"),
                "bank_status": row.get("bk_status"),
                "reversal_status": row.get("gw_reversal")
            },
            "source_row_anomalies": anomalies,
            "priority_breakdown": breakdown
        }

        rec_result = ReconciliationResult(
            run_id=run_id,
            scenario_id=scenario_id,
            transaction_id=txn_id,
            classification=classification,
            match_method="SQL_CTE_AGGREGATION_FULL_OUTER_JOIN",
            ambiguity_flag=(classification in [ReconciliationClassification.AMBIGUOUS_REVIEW, ReconciliationClassification.DUPLICATE]),
            gateway_record_id=gw_rec_ids[0] if gw_rec_ids else None,
            bank_record_id=bk_rec_ids[0] if bk_rec_ids else None,
            gateway_rows_count=gw_count,
            bank_rows_count=bk_count,
            gateway_record_ids=gw_rec_ids,
            bank_record_ids=bk_rec_ids,
            source_row_anomalies=anomalies,
            gateway_amount_paise=gw_amt,
            bank_amount_paise=bk_amt,
            difference_paise=diff_paise,
            applied_rule=rule,
            priority_score=score,
            priority_explanation=explanation,
            evidence_json=evidence,
            ground_truth_label=gt_label,
            validation_status=validation_status
        )
        results.append(rec_result)

    return results
