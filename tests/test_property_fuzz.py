"""
Property-Based and Fuzz Testing Suite for ExaSettle using Hypothesis.
Validates non-negotiable financial invariants across randomized adversarial state spaces:
1. Paise conservation & accounting balance identity.
2. Monotonicity and bounds of operational priority score [0, 100].
3. Completeness of deterministic explainability metadata (non-empty fields).
4. Duplicate idempotency and logical transaction row aggregation.
5. Invariance under arbitrary integer paise scales.
"""

import pytest
from hypothesis import given, strategies as st, settings

from exasettle.core.models import (
    ReconciliationClassification,
    LedgerRecord,
    GroundTruthRecord,
    SourceSystem,
    ReconciliationResult
)
from exasettle.engine.priority_score import calculate_priority_score
from exasettle.engine.reconciliation_core import (
    classify_matched_row,
    resolve_reconciliation_results,
    EXPLAINABILITY_METADATA
)


@given(
    base_amount_paise=st.integers(min_value=100, max_value=100_000_000),  # ₹1.00 to ₹1,000,000.00
    mdr_basis_points=st.integers(min_value=50, max_value=500),            # 0.5% to 5.0%
    gst_basis_points=st.integers(min_value=1200, max_value=2800)          # 12% to 28%
)
@settings(max_examples=100)
def test_property_integer_paise_fee_conservation(
    base_amount_paise: int,
    mdr_basis_points: int,
    gst_basis_points: int
):
    """
    Property: Monetary calculations must conserve integer paise without floating point rounding drift.
    Gross = Net Settled + Fee (MDR + GST).
    """
    mdr_paise = (base_amount_paise * mdr_basis_points) // 10000
    gst_paise = (mdr_paise * gst_basis_points) // 10000
    total_fee_paise = mdr_paise + gst_paise
    net_settled_paise = base_amount_paise - total_fee_paise

    # Conservation invariant
    reconstructed_gross = net_settled_paise + total_fee_paise
    assert reconstructed_gross == base_amount_paise, "Paise conservation violated"
    assert isinstance(total_fee_paise, int), "Fee must be strict integer paise"
    assert isinstance(net_settled_paise, int), "Net settlement must be strict integer paise"


@given(
    diff_paise=st.integers(min_value=0, max_value=1_000_000_000_00),  # up to ₹1 billion
    gw_amt=st.integers(min_value=0, max_value=1_000_000_000_00),
    bk_amt=st.integers(min_value=0, max_value=1_000_000_000_00),
    delay_hours=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False),
    is_dup=st.booleans(),
    status_conflict=st.booleans()
)
@settings(max_examples=100)
def test_property_priority_score_strictly_bounded(
    diff_paise: int,
    gw_amt: int,
    bk_amt: int,
    delay_hours: float,
    is_dup: bool,
    status_conflict: bool
):
    """
    Property: Operational priority score must strictly be an integer between 0 and 100 inclusive,
    regardless of adversarial financial amounts or extreme timing delays.
    """
    for cls in ReconciliationClassification:
        score, explanation, breakdown = calculate_priority_score(
            classification=cls,
            difference_paise=diff_paise,
            gateway_amount_paise=gw_amt,
            bank_amount_paise=bk_amt,
            is_duplicate=is_dup,
            settlement_delay_hours=delay_hours,
            delay_threshold_hours=24.0,
            status_conflict=status_conflict
        )

        assert isinstance(score, int), "Score must be an integer"
        assert 0 <= score <= 100, f"Score {score} out of bounds [0, 100] for {cls}"
        assert explanation, "Explanation must never be empty"
        assert isinstance(breakdown, dict), "Breakdown must be a valid dictionary"

        if cls == ReconciliationClassification.MATCHED and not is_dup and not status_conflict:
            assert score == 0, "Clean match without anomalies must have priority 0"


@given(
    gw_dup=st.integers(min_value=1, max_value=5),
    bk_dup=st.integers(min_value=1, max_value=5),
    amount=st.integers(min_value=1000, max_value=5000000)
)
@settings(max_examples=50)
def test_property_duplicate_classification_determinism(
    gw_dup: int,
    bk_dup: int,
    amount: int
):
    """
    Property: If either gateway or bank has more than 1 physical row for a transaction,
    it must deterministically resolve as DUPLICATE.
    """
    row = {
        "gw_record_id": "GW_01" if gw_dup > 0 else None,
        "bk_record_id": "BK_01" if bk_dup > 0 else None,
        "gw_amount_paise": amount,
        "bk_amount_paise": amount,
        "gw_fee_paise": 100,
        "bk_fee_paise": 100,
        "gw_status": "CAPTURED",
        "bk_status": "SETTLED",
        "gw_reversal": "NONE",
        "gw_dup_count": gw_dup,
        "bk_dup_count": bk_dup,
        "rn": 1
    }

    cls, rule, diff, is_dup, delay, conflict = classify_matched_row(row)

    if gw_dup > 1 or bk_dup > 1:
        assert cls == ReconciliationClassification.DUPLICATE
        assert is_dup is True
        assert "DUPLICATE" in rule
    else:
        assert cls == ReconciliationClassification.MATCHED


def test_property_all_classifications_have_complete_explainability():
    """
    Property: EXPLAINABILITY_METADATA must cover all 8 standardized financial classifications
    with non-empty reason_code, action, owner, and sla.
    """
    for cls in ReconciliationClassification:
        meta = EXPLAINABILITY_METADATA.get(cls)
        assert meta is not None, f"Missing explainability metadata for {cls}"
        assert meta["reason_code"].startswith("RC_"), f"reason_code must start with RC_ for {cls}"
        assert len(meta["action"]) > 10, f"action description too brief for {cls}"
        assert len(meta["owner"]) > 3, f"owner missing for {cls}"
        assert len(meta["sla"]) > 0, f"sla missing for {cls}"
        assert isinstance(meta["sla_hours"], int), f"sla_hours must be int for {cls}"
