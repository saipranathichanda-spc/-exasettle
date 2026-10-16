"""
MiroFish Scenario Prompt Template Generator.
Implements exact specification from PRD Section 10:
- Explicit simulation notice
- Structured scenario fields: ID, transaction, customer, merchant, gateway context
- Concrete guidelines forbidding real-world claims or modification of financial truth
- Structured output: role, scenario_id, observation, question_or_feedback
"""

from typing import Dict, Any, Optional
from exasettle.core.models import ReconciliationResult, GroundTruthRecord, LedgerRecord
from exasettle.core.money import format_inr


PROMPT_TEMPLATE = """SIMULATION NOTICE
This is a fictional, offline prototype scenario. All named entities, customers, merchants, and transactions are synthetic.

SCENARIO
Scenario ID: {scenario_id}
Synthetic transaction ID: {transaction_id}
Synthetic customer persona: {customer_persona}
Synthetic merchant persona: {merchant_persona}
Synthetic gateway role/context: {gateway_context}
Gateway record: {gateway_record_summary}
Bank settlement record: {bank_record_summary_or_missing}
Deterministic reconciliation classification: {reconciliation_classification}
Evidence explanation: {evidence_summary}
Known-answer expected result (demo validation only): {ground_truth_label}

ASSIGNED ROLE TO SIMULATE: {assigned_role}

TASK
Role-play the assigned fictional perspective only. Explain what that role might observe, experience, or need clarified.

RULES
- Use only the scenario fields above. Do not invent a real payment, actual money, or legal claims.
- Do not change the deterministic classification or ground truth.
- If the evidence does not establish whether money was actually deducted, say that clearly.
- Do not imitate a real person or create personal sensitive attributes.
- Keep each response concise and specific to the scenario. Distinguish observed data from speculation.
- Output structured items: role, scenario_id, observation, question_or_feedback.

PURPOSE
Help the demo team identify whether the dashboard explanation is understandable to finance and merchant operations.
"""


def format_mirofish_prompt(
    result: ReconciliationResult,
    ground_truth: Optional[GroundTruthRecord],
    gw_record: Optional[LedgerRecord],
    bk_record: Optional[LedgerRecord],
    assigned_role: str = "CUSTOMER"
) -> str:
    """Format PRD Section 10 prompt template for a specific case and role."""
    cust_persona = ground_truth.synthetic_customer_name if ground_truth else "Fictional Shopper Persona"
    merch_persona = ground_truth.synthetic_merchant_name if ground_truth else "Fictional Retailer Persona"
    gw_context = "Synthetic Payment Gateway Engine (System Actor - not a customer)"

    if gw_record:
        gw_summary = (
            f"Record ID: {gw_record.source_record_id}, Amount: {format_inr(gw_record.amount_paise)}, "
            f"Fee: {format_inr(gw_record.fee_paise)}, Timestamp: {gw_record.event_timestamp_utc}, Status: {gw_record.status}"
        )
    else:
        gw_summary = "[MISSING - No gateway capture record found]"

    if bk_record:
        bk_summary = (
            f"Record ID: {bk_record.source_record_id}, Settled: {format_inr(bk_record.amount_paise)}, "
            f"Fee: {format_inr(bk_record.fee_paise)}, Timestamp: {bk_record.settlement_timestamp_utc}, Status: {bk_record.status}"
        )
    else:
        bk_summary = "[MISSING - No bank settlement record found]"

    evidence_summary = result.applied_rule + " " + result.priority_explanation
    gt_label = ground_truth.expected_classification.value if ground_truth else "N/A"

    return PROMPT_TEMPLATE.format(
        scenario_id=result.scenario_id,
        transaction_id=result.transaction_id,
        customer_persona=cust_persona,
        merchant_persona=merch_persona,
        gateway_context=gw_context,
        gateway_record_summary=gw_summary,
        bank_record_summary_or_missing=bk_summary,
        reconciliation_classification=result.classification.value,
        evidence_summary=evidence_summary,
        ground_truth_label=gt_label,
        assigned_role=assigned_role
    )
