"""
Explainable Deterministic Operational Priority Score (0-100)
Implements PRD Section 9.5:
- Deterministic score calculated from documented formula
- Shows step-by-step mathematical breakdown
- Strictly labeled as operational investigation triage priority
- NEVER described as credit risk, customer risk, or regulatory risk
- NEVER set or modified by LLM / MiroFish
"""

from typing import Tuple, Dict, Any, Optional
from exasettle.core.models import ReconciliationClassification


def calculate_priority_score(
    classification: ReconciliationClassification,
    difference_paise: int,
    gateway_amount_paise: Optional[int],
    bank_amount_paise: Optional[int],
    is_duplicate: bool,
    settlement_delay_hours: float,
    delay_threshold_hours: float,
    status_conflict: bool
) -> Tuple[int, str, Dict[str, Any]]:
    """
    Compute explainable operational priority score between 0 and 100.
    Returns: (score, human_readable_explanation, factor_breakdown)
    """
    if classification == ReconciliationClassification.MATCHED:
        return (
            0,
            "Priority 0/100: Transaction cleanly matched. Zero discrepancies detected.",
            {"base_points": 0, "discrepancy_points": 0, "delay_points": 0, "risk_factors": []}
        )

    score = 0
    factors = []
    breakdown: Dict[str, Any] = {"components": []}

    # 1. Unmatched / Missing ledger leg (Base +40)
    if classification in [ReconciliationClassification.MISSING_IN_BANK, ReconciliationClassification.MISSING_IN_GATEWAY]:
        points = 45
        score += points
        side = "Bank settlement" if classification == ReconciliationClassification.MISSING_IN_BANK else "Gateway capture"
        factors.append(f"Missing ledger leg: {side} missing completely (+{points} pts)")
        breakdown["components"].append({"factor": "Missing Ledger Leg", "points": points})

    # 2. Duplicate submission (Base +35)
    if is_duplicate or classification == ReconciliationClassification.DUPLICATE:
        points = 40
        score += points
        factors.append(f"Duplicate submission detected in transaction records (+{points} pts)")
        breakdown["components"].append({"factor": "Duplicate Submission", "points": points})

    # 3. Status conflict / Ambiguity (Base +35)
    if status_conflict or classification == ReconciliationClassification.AMBIGUOUS_REVIEW:
        points = 35
        score += points
        factors.append(f"Conflicting or reversed transaction state requiring manual investigation (+{points} pts)")
        breakdown["components"].append({"factor": "Status Conflict", "points": points})

    # 4. Amount discrepancy (Base +30 + proportional magnitude)
    if classification == ReconciliationClassification.AMOUNT_MISMATCH or (difference_paise > 0 and classification != ReconciliationClassification.FEE_VARIANCE_MDR):
        base_pts = 30
        # Discrepancy magnitude bonus (up to 20 pts for larger amounts)
        rupees_diff = difference_paise / 100.0
        magnitude_bonus = min(20, int(rupees_diff / 50.0))
        pts = base_pts + magnitude_bonus
        score += pts
        factors.append(f"Principal amount mismatch of ₹{rupees_diff:.2f} (+{pts} pts)")
        breakdown["components"].append({"factor": "Amount Mismatch", "points": pts, "difference_rupees": rupees_diff})

    # 5. Settlement delay beyond threshold (+20 + hours bonus)
    if classification == ReconciliationClassification.SETTLEMENT_DELAY:
        delay_pts = 25
        excess_hours = max(0.0, settlement_delay_hours - delay_threshold_hours)
        excess_pts = min(15, int(excess_hours / 4.0))
        pts = delay_pts + excess_pts
        score += pts
        factors.append(f"Settlement delayed by {settlement_delay_hours:.1f}h (threshold: {delay_threshold_hours}h) (+{pts} pts)")
        breakdown["components"].append({"factor": "Settlement Delay", "points": pts, "settlement_delay_hours": settlement_delay_hours})

    # 6. Fee variance (Base +15)
    if classification == ReconciliationClassification.FEE_VARIANCE_MDR:
        points = 15
        score += points
        factors.append(f"Merchant discount rate / fee schedule variance (+{points} pts)")
        breakdown["components"].append({"factor": "Fee Variance", "points": points})

    final_score = min(100, max(0, score))
    explanation = f"Operational Triage Score {final_score}/100: " + "; ".join(factors)

    return final_score, explanation, breakdown
