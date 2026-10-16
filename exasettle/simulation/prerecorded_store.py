"""
Prerecorded Simulation Store for Offline Demonstration.
Implements PRD Section 9.2:
- Transparently labeled as 'PRERECORDED'
- Fictional personas for Customer, Merchant, and Gateway system actor
- Persistent disclosure: 'AI-simulated scenario — not real customer feedback'
"""

from typing import Dict, List, Optional
from exasettle.core.models import SimulationEvent, ReconciliationClassification


PRERECORDED_EVENTS: Dict[str, List[Dict[str, str]]] = {
    # TXN_SYN_101: MATCHED
    "TXN_SYN_101": [
        {
            "role": "CUSTOMER",
            "agent_id": "SIM_CUST_101",
            "persona_name": "Aarav Sharma (Fictional Persona)",
            "observation": "My order status shows confirmed and ₹1,500.00 was debited smoothly via UPI.",
            "question_or_feedback": "Payment went through quickly; invoice and receipt match.",
            "event_type": "PURCHASE_SATISFACTION"
        },
        {
            "role": "MERCHANT",
            "agent_id": "SIM_MERCH_001",
            "persona_name": "Kirana Express (Fictional Merchant)",
            "observation": "Settlement of ₹1,500.00 less standard 2% MDR (₹30.00) received in settlement account within normal 15 minutes.",
            "question_or_feedback": "Clean match, batch settled automatically.",
            "event_type": "SETTLEMENT_ACCEPTED"
        },
        {
            "role": "GATEWAY",
            "agent_id": "SYS_GATEWAY_NODE",
            "persona_name": "Synthetic Gateway Orchestrator (System Actor)",
            "observation": "PG_REF_101 received 200 OK from acquiring bank. UTR_101 generated and webhook emitted.",
            "question_or_feedback": "Standard happy-path transaction lifecycle closed.",
            "event_type": "TELEMETRY_CLOSED"
        }
    ],

    # TXN_SYN_102: FEE_VARIANCE_MDR
    "TXN_SYN_102": [
        {
            "role": "CUSTOMER",
            "agent_id": "SIM_CUST_102",
            "persona_name": "Priya Patel (Fictional Persona)",
            "observation": "My account was billed ₹2,000.00 as expected on the checkout page.",
            "question_or_feedback": "Transaction shows successful in my bank app.",
            "event_type": "CUSTOMER_CONFIRMATION"
        },
        {
            "role": "MERCHANT",
            "agent_id": "SIM_MERCH_002",
            "persona_name": "Bharat Retailers (Fictional Merchant)",
            "observation": "Expected fee was ₹40.00 per contracted 2% rate, but bank statement reflects ₹55.00 deduction (₹15.00 variance).",
            "question_or_feedback": "Why was a higher MDR tier applied to this debit card transaction?",
            "event_type": "FEE_SCHEDULE_QUERY"
        },
        {
            "role": "GATEWAY",
            "agent_id": "SYS_GATEWAY_NODE",
            "persona_name": "Synthetic Gateway Orchestrator (System Actor)",
            "observation": "Gateway fee engine calculated fee=4000 paise. Bank clearing file returned fee=5500 paise.",
            "question_or_feedback": "Flagged MDR rate card mismatch with acquiring bank feed.",
            "event_type": "FEE_DISCREPANCY_FLAG"
        }
    ],

    # TXN_SYN_103: AMOUNT_MISMATCH
    "TXN_SYN_103": [
        {
            "role": "CUSTOMER",
            "agent_id": "SIM_CUST_103",
            "persona_name": "Rohan Gupta (Fictional Persona)",
            "observation": "I initiated a purchase for ₹3,500.00 on the retailer site.",
            "question_or_feedback": "Was my card charged ₹3,500.00 or ₹3,000.00?",
            "event_type": "AMOUNT_CONFUSION"
        },
        {
            "role": "MERCHANT",
            "agent_id": "SIM_MERCH_003",
            "persona_name": "Deccan Electronics (Fictional Merchant)",
            "observation": "Cart total was ₹3,500.00 but our bank settlement credit is only ₹3,000.00. We have a ₹500.00 deficit.",
            "question_or_feedback": "Holding order shipment until the ₹500.00 principal variance is reconciled.",
            "event_type": "MERCHANT_HOLDOFF"
        },
        {
            "role": "GATEWAY",
            "agent_id": "SYS_GATEWAY_NODE",
            "persona_name": "Synthetic Gateway Orchestrator (System Actor)",
            "observation": "Gateway capture authorized at 350000 paise. Bank clearing file reported 300000 paise settled.",
            "question_or_feedback": "Amount delta = 50000 paise. Triggering high-priority settlement investigation.",
            "event_type": "SYSTEM_MISMATCH_ALARM"
        }
    ],

    # TXN_SYN_104: MISSING_IN_BANK
    "TXN_SYN_104": [
        {
            "role": "CUSTOMER",
            "agent_id": "SIM_CUST_104",
            "persona_name": "Ananya Iyer (Fictional Persona)",
            "observation": "Gateway screen indicated payment successful, but I have not received order confirmation.",
            "question_or_feedback": "Can you verify if money actually reached the seller?",
            "event_type": "CUSTOMER_ENQUIRY"
        },
        {
            "role": "MERCHANT",
            "agent_id": "SIM_MERCH_004",
            "persona_name": "Himalayan Goods (Fictional Merchant)",
            "observation": "Gateway reports customer completed payment for ₹1,200.00, but no settlement row appears in bank ledger.",
            "question_or_feedback": "Where is the payout for TXN_SYN_104? Bank has not credited our account.",
            "event_type": "PAYOUT_MISSING_ALARM"
        },
        {
            "role": "GATEWAY",
            "agent_id": "SYS_GATEWAY_NODE",
            "persona_name": "Synthetic Gateway Orchestrator (System Actor)",
            "observation": "GW_REC_104 committed in database as SUCCESS. Bank settlement file contains zero entries with UTR_104.",
            "question_or_feedback": "Record is un-settled at bank side. Payout pending bank settlement cycle.",
            "event_type": "UNSETTLED_AUDIT_LOG"
        }
    ],

    # TXN_SYN_105: MISSING_IN_GATEWAY
    "TXN_SYN_105": [
        {
            "role": "CUSTOMER",
            "agent_id": "SIM_CUST_105",
            "persona_name": "Vikram Verma (Fictional Persona)",
            "observation": "I see a direct bank transfer of ₹850.00 on my statement but no checkout screen session.",
            "question_or_feedback": "Is this an automated recurring charge or direct transfer?",
            "event_type": "UNRECOGNIZED_CHARGE"
        },
        {
            "role": "MERCHANT",
            "agent_id": "SIM_MERCH_001",
            "persona_name": "Kirana Express (Fictional Merchant)",
            "observation": "Our bank account shows an unexpected credit of ₹850.00 with reference UTR_105 not tied to an order ID.",
            "question_or_feedback": "Need to match this orphaned deposit with customer order records.",
            "event_type": "UNLINKED_DEPOSIT"
        },
        {
            "role": "GATEWAY",
            "agent_id": "SYS_GATEWAY_NODE",
            "persona_name": "Synthetic Gateway Orchestrator (System Actor)",
            "observation": "Bank settlement row BK_REC_105 arrived with no matching gateway capture record in table.",
            "question_or_feedback": "Orphaned bank record detected. Possible direct NEFT/IMPS or out-of-band settlement.",
            "event_type": "ORPHANED_CREDIT_FLAG"
        }
    ],

    # TXN_SYN_106: DUPLICATE
    "TXN_SYN_106": [
        {
            "role": "CUSTOMER",
            "agent_id": "SIM_CUST_106",
            "persona_name": "Kavita Rao (Fictional Persona)",
            "observation": "The payment page refreshed twice when clicking Pay Now.",
            "question_or_feedback": "Please ensure I am not billed twice for ₹4,500.00.",
            "event_type": "DOUBLE_PAY_CONCERN"
        },
        {
            "role": "MERCHANT",
            "agent_id": "SIM_MERCH_002",
            "persona_name": "Bharat Retailers (Fictional Merchant)",
            "observation": "We received two identical gateway notifications for order TXN_SYN_106 spaced 1 minute apart.",
            "question_or_feedback": "Need confirmation before processing shipment whether two units were ordered.",
            "event_type": "DUPLICATE_ORDER_HOLD"
        },
        {
            "role": "GATEWAY",
            "agent_id": "SYS_GATEWAY_NODE",
            "persona_name": "Synthetic Gateway Orchestrator (System Actor)",
            "observation": "Duplicate records GW_REC_106_A and GW_REC_106_B identified by ROW_NUMBER() window function.",
            "question_or_feedback": "Idempotency key failure or network retry. Duplicate flagged for deduplication.",
            "event_type": "IDEMPOTENCY_TRIP"
        }
    ],

    # TXN_SYN_107: SETTLEMENT_DELAY
    "TXN_SYN_107": [
        {
            "role": "CUSTOMER",
            "agent_id": "SIM_CUST_107",
            "persona_name": "Suresh Nair (Fictional Persona)",
            "observation": "Transaction was deducted 3 days ago from my savings account.",
            "question_or_feedback": "Merchant claimed payment had not arrived until today.",
            "event_type": "DELAY_COMPLAINT"
        },
        {
            "role": "MERCHANT",
            "agent_id": "SIM_MERCH_003",
            "persona_name": "Deccan Electronics (Fictional Merchant)",
            "observation": "Funds for ₹5,000.00 took 74 hours to settle into our operational account (threshold: 24h).",
            "question_or_feedback": "Why was the settlement cycle delayed over the weekend?",
            "event_type": "SLA_BREACH_INQUIRY"
        },
        {
            "role": "GATEWAY",
            "agent_id": "SYS_GATEWAY_NODE",
            "persona_name": "Synthetic Gateway Orchestrator (System Actor)",
            "observation": "Settlement time delta = 72 hours, exceeding scenario setting of 24 hours.",
            "question_or_feedback": "Flagged for acquiring bank batch latency review. Note: Scenario setting, not RBI legal rule.",
            "event_type": "SLA_MONITOR_ALERT"
        }
    ],

    # TXN_SYN_108: AMBIGUOUS_REVIEW
    "TXN_SYN_108": [
        {
            "role": "CUSTOMER",
            "agent_id": "SIM_CUST_108",
            "persona_name": "Deepika Sen (Fictional Persona)",
            "observation": "I requested a cancellation immediately after initiating the payment of ₹2,200.00.",
            "question_or_feedback": "Gateway marked cancelled, but my bank statement shows money settled.",
            "event_type": "REVERSAL_CONFUSION"
        },
        {
            "role": "MERCHANT",
            "agent_id": "SIM_MERCH_004",
            "persona_name": "Himalayan Goods (Fictional Merchant)",
            "observation": "Order shows REVERSED in merchant dashboard, yet bank settled ₹2,200.00 to our balance.",
            "question_or_feedback": "Should we issue a manual refund or will the bank auto-reverse this chargeback?",
            "event_type": "REFUND_TRIAGE"
        },
        {
            "role": "GATEWAY",
            "agent_id": "SYS_GATEWAY_NODE",
            "persona_name": "Synthetic Gateway Orchestrator (System Actor)",
            "observation": "Conflicting status: Gateway=REVERSED (Customer Request) vs Bank=SETTLED. Ambiguity flag tripped.",
            "question_or_feedback": "Escalated to operations investigation queue. No automated fund movement permitted.",
            "event_type": "DISPUTE_ESCALATION"
        }
    ]
}


def get_prerecorded_events(
    scenario_id: str,
    transaction_id: str,
    run_id: str = "run_demo_001"
) -> List[SimulationEvent]:
    """Retrieve pre-recorded simulated participant perspectives with immutable disclosure."""
    events_raw = PRERECORDED_EVENTS.get(transaction_id, [])
    sim_events: List[SimulationEvent] = []

    for item in events_raw:
        sim_events.append(SimulationEvent(
            simulation_run_id=f"sim_{run_id}_{transaction_id}",
            scenario_id=scenario_id,
            transaction_id=transaction_id,
            agent_role=item["role"],
            agent_id=item["agent_id"],
            persona_name=item["persona_name"],
            event_type=item["event_type"],
            event_timestamp="2026-10-16T12:00:00Z",
            observation=item["observation"],
            question_or_feedback=item["question_or_feedback"],
            evidence_reference=f"RECON_EVIDENCE_FOR_{transaction_id}",
            simulation_label="AI-simulated scenario — not real customer feedback",
            model_name="qwen-plus/gpt-4o-mini (simulated)",
            repository_revision="7657031ac01184afe2cb220f5ee3545573b5e843",
            status="PRERECORDED"
        ))

    return sim_events
