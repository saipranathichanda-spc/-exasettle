"""
Core deterministic reconciliation logic for ExaSettle.
Implements PRD Section 9.4:
- Identifiers, amounts, fees, and timestamps normalized
- Deterministic tie-breaking using ROW_NUMBER()
- Full Outer Join capturing unmatched rows from both sides
- Classifies all 8 mandatory states
- Fully explainable priority scoring
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


RECONCILIATION_SQL = """
WITH gw_ranked AS (
    SELECT 
        run_id,
        scenario_id,
        transaction_id,
        source_record_id,
        synthetic_customer_id,
        synthetic_merchant_id,
        gateway_reference,
        bank_reference,
        amount_paise,
        fee_paise,
        currency,
        event_timestamp_utc,
        status,
        reversal_status,
        ROW_NUMBER() OVER (
            PARTITION BY transaction_id 
            ORDER BY event_timestamp_utc ASC, source_record_id ASC
        ) as rn,
        COUNT(*) OVER (PARTITION BY transaction_id) as dup_count
    FROM gateway_records
    WHERE run_id = ?
),
bk_ranked AS (
    SELECT 
        run_id,
        scenario_id,
        transaction_id,
        source_record_id,
        synthetic_customer_id,
        synthetic_merchant_id,
        gateway_reference,
        bank_reference,
        amount_paise,
        fee_paise,
        currency,
        event_timestamp_utc,
        settlement_timestamp_utc,
        status,
        reversal_status,
        ROW_NUMBER() OVER (
            PARTITION BY transaction_id 
            ORDER BY event_timestamp_utc ASC, source_record_id ASC
        ) as rn,
        COUNT(*) OVER (PARTITION BY transaction_id) as dup_count
    FROM bank_records
    WHERE run_id = ?
)
SELECT 
    COALESCE(gw.transaction_id, bk.transaction_id) as transaction_id,
    COALESCE(gw.run_id, bk.run_id) as run_id,
    COALESCE(gw.scenario_id, bk.scenario_id) as scenario_id,
    gw.source_record_id as gw_record_id,
    bk.source_record_id as bk_record_id,
    gw.amount_paise as gw_amount_paise,
    bk.amount_paise as bk_amount_paise,
    gw.fee_paise as gw_fee_paise,
    bk.fee_paise as bk_fee_paise,
    gw.status as gw_status,
    bk.status as bk_status,
    gw.reversal_status as gw_reversal,
    bk.reversal_status as bk_reversal,
    gw.event_timestamp_utc as gw_timestamp,
    bk.settlement_timestamp_utc as bk_timestamp,
    COALESCE(gw.dup_count, 0) as gw_dup_count,
    COALESCE(bk.dup_count, 0) as bk_dup_count,
    COALESCE(gw.rn, bk.rn) as rn
FROM gw_ranked gw
FULL OUTER JOIN bk_ranked bk 
    ON gw.transaction_id = bk.transaction_id 
    AND gw.rn = bk.rn
ORDER BY transaction_id ASC, rn ASC
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
    Classify a joined gateway/bank record.
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
    gw_dup = row.get("gw_dup_count", 0)
    bk_dup = row.get("bk_dup_count", 0)
    rn = row.get("rn", 1)

    is_duplicate = (gw_dup > 1 or bk_dup > 1 or rn > 1)

    # Calculate timestamps & settlement delay
    gw_time = parse_iso_datetime(row.get("gw_timestamp"))
    bk_time = parse_iso_datetime(row.get("bk_timestamp"))
    delay_hours = 0.0
    if gw_time and bk_time:
        delta = bk_time - gw_time
        delay_hours = max(0.0, delta.total_seconds() / 3600.0)

    # 1. Duplicate submission check (takes precedence over orphaned second row)
    if is_duplicate:
        rule = f"RULE_DUPLICATE_CHECK: Duplicate submissions detected (Gateway copies: {gw_dup}, Bank copies: {bk_dup}, Row index: {rn})."
        return (ReconciliationClassification.DUPLICATE, rule, 0, True, delay_hours, False)

    # 2. Missing side checks
    if gw_id is not None and bk_id is None:
        diff = gw_amt if gw_amt is not None else 0
        rule = "RULE_MISSING_BANK: Gateway captured payment but no corresponding bank settlement record found."
        return (ReconciliationClassification.MISSING_IN_BANK, rule, diff, is_duplicate, delay_hours, False)

    if gw_id is None and bk_id is not None:
        diff = bk_amt if bk_amt is not None else 0
        rule = "RULE_MISSING_GATEWAY: Bank settlement record exists without originating gateway capture record."
        return (ReconciliationClassification.MISSING_IN_GATEWAY, rule, diff, is_duplicate, delay_hours, False)

    # 3. Status conflict / Ambiguity check
    status_conflict = False
    if (gw_status == "REVERSED" and bk_status == "SETTLED") or (gw_rev and gw_rev != "NONE"):
        status_conflict = True
        rule = f"RULE_STATUS_CONFLICT: Gateway status '{gw_status}' (Reversal: {gw_rev}) conflicts with Bank status '{bk_status}'."
        return (ReconciliationClassification.AMBIGUOUS_REVIEW, rule, 0, False, delay_hours, True)

    # 4. Amount mismatch check
    diff_amount = abs((gw_amt or 0) - (bk_amt or 0))
    if diff_amount != 0:
        rule = f"RULE_AMOUNT_MISMATCH: Gateway principal amount (₹{(gw_amt or 0)/100:.2f}) does not match Bank settled amount (₹{(bk_amt or 0)/100:.2f})."
        return (ReconciliationClassification.AMOUNT_MISMATCH, rule, diff_amount, False, delay_hours, False)

    # 5. Settlement delay check
    if delay_hours > settlement_delay_threshold_hours:
        rule = f"RULE_SETTLEMENT_DELAY: Settlement elapsed time ({delay_hours:.1f}h) exceeds configured scenario threshold ({settlement_delay_threshold_hours:.1f}h)."
        return (ReconciliationClassification.SETTLEMENT_DELAY, rule, 0, False, delay_hours, False)

    # 6. Fee variance check
    if gw_fee != bk_fee:
        diff_fee = abs((gw_fee or 0) - (bk_fee or 0))
        rule = f"RULE_FEE_VARIANCE: Gateway fee schedule (₹{(gw_fee or 0)/100:.2f}) differs from Bank deducted fee (₹{(bk_fee or 0)/100:.2f}) by ₹{diff_fee/100:.2f}."
        return (ReconciliationClassification.FEE_VARIANCE_MDR, rule, diff_fee, False, delay_hours, False)

    # 7. Clean match
    rule = "RULE_CLEAN_MATCH: All identifiers, principal amount, fee schedule, and settlement time windows verified."
    return (ReconciliationClassification.MATCHED, rule, 0, False, delay_hours, False)


def resolve_reconciliation_results(
    joined_rows: List[Dict[str, Any]],
    ground_truth_map: Dict[str, GroundTruthRecord],
    settlement_delay_threshold_hours: float = 24.0
) -> List[ReconciliationResult]:
    """
    Resolve joined database rows into structured ReconciliationResults.
    Validates each result against independent ground truth.
    """
    results: List[ReconciliationResult] = []

    for row in joined_rows:
        txn_id = row["transaction_id"]
        run_id = row["run_id"]
        scenario_id = row["scenario_id"]

        classification, rule, diff_paise, is_dup, delay_hrs, status_conf = classify_matched_row(
            row, settlement_delay_threshold_hours=settlement_delay_threshold_hours
        )

        # Compute deterministic priority score
        score, explanation, breakdown = calculate_priority_score(
            classification=classification,
            difference_paise=diff_paise,
            gateway_amount_paise=row.get("gw_amount_paise"),
            bank_amount_paise=row.get("bk_amount_paise"),
            is_duplicate=is_dup,
            settlement_delay_hours=delay_hrs,
            delay_threshold_hours=settlement_delay_threshold_hours,
            status_conflict=status_conf
        )

        # Ground truth comparison
        gt = ground_truth_map.get(txn_id)
        gt_label = gt.expected_classification.value if gt else None
        if gt:
            validation_status = "VALIDATED_CORRECT" if gt.expected_classification == classification else "MISMATCH"
        else:
            validation_status = "UNVALIDATED"

        evidence = {
            "source_records": {
                "gateway_record_id": row.get("gw_record_id"),
                "bank_record_id": row.get("bk_record_id")
            },
            "financial_values": {
                "gateway_amount_paise": row.get("gw_amount_paise"),
                "bank_amount_paise": row.get("bk_amount_paise"),
                "difference_paise": diff_paise,
                "gateway_fee_paise": row.get("gw_fee_paise"),
                "bank_fee_paise": row.get("bk_fee_paise")
            },
            "timing": {
                "gateway_timestamp": row.get("gw_timestamp"),
                "bank_timestamp": row.get("bk_timestamp"),
                "elapsed_settlement_hours": round(delay_hrs, 2),
                "threshold_hours": settlement_delay_threshold_hours
            },
            "state": {
                "gateway_status": row.get("gw_status"),
                "bank_status": row.get("bk_status"),
                "reversal_status": row.get("gw_reversal")
            },
            "priority_breakdown": breakdown
        }

        rec_result = ReconciliationResult(
            run_id=run_id,
            scenario_id=scenario_id,
            transaction_id=txn_id,
            classification=classification,
            match_method="CTE_ROW_NUMBER_FULL_OUTER_JOIN",
            ambiguity_flag=(classification in [ReconciliationClassification.AMBIGUOUS_REVIEW, ReconciliationClassification.DUPLICATE]),
            gateway_record_id=row.get("gw_record_id"),
            bank_record_id=row.get("bk_record_id"),
            gateway_amount_paise=row.get("gw_amount_paise"),
            bank_amount_paise=row.get("bk_amount_paise"),
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
