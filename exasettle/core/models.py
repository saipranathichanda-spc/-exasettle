"""
Core data models for ExaSettle.
Adheres strictly to PRD Section 12 data model with synthetic transaction labels.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ReconciliationClassification(str, Enum):
    MATCHED = "MATCHED"
    FEE_VARIANCE_MDR = "FEE_VARIANCE_MDR"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_IN_BANK = "MISSING_IN_BANK"
    MISSING_IN_GATEWAY = "MISSING_IN_GATEWAY"
    DUPLICATE = "DUPLICATE"
    SETTLEMENT_DELAY = "SETTLEMENT_DELAY"
    AMBIGUOUS_REVIEW = "AMBIGUOUS_REVIEW"


class SourceSystem(str, Enum):
    GATEWAY = "GATEWAY"
    BANK = "BANK"


class LedgerRecord(BaseModel):
    """Synthetic gateway or bank ledger record."""
    run_id: str
    scenario_id: str
    transaction_id: str
    synthetic_customer_id: str
    synthetic_merchant_id: str
    source_system: SourceSystem
    source_record_id: str
    gateway_reference: Optional[str] = None
    bank_reference: Optional[str] = None
    amount_paise: int
    fee_paise: int = 0
    currency: str = "INR"
    event_timestamp_utc: str
    settlement_timestamp_utc: Optional[str] = None
    status: str
    reversal_status: Optional[str] = None
    settlement_reference: Optional[str] = None
    row_hash: str
    dataset_hash: str
    generation_seed: int
    synthetic_label: str = "Synthetic demo transaction"


class GroundTruthRecord(BaseModel):
    """Independent ground truth for validating reconciliation accuracy."""
    scenario_id: str
    transaction_id: str
    expected_classification: ReconciliationClassification
    expected_difference_paise: int = 0
    planted_reason: str
    synthetic_customer_name: str
    synthetic_merchant_name: str


class ReconciliationResult(BaseModel):
    """Result of deterministic reconciliation execution."""
    run_id: str
    scenario_id: str
    transaction_id: str
    classification: ReconciliationClassification
    match_method: str
    ambiguity_flag: bool = False
    gateway_record_id: Optional[str] = None
    bank_record_id: Optional[str] = None
    gateway_rows_count: int = 1
    bank_rows_count: int = 1
    gateway_record_ids: List[str] = []
    bank_record_ids: List[str] = []
    source_row_anomalies: List[str] = []
    gateway_amount_paise: Optional[int] = None
    bank_amount_paise: Optional[int] = None
    difference_paise: int = 0
    applied_rule: str
    priority_score: int = Field(ge=0, le=100)
    priority_explanation: str
    evidence_json: Dict[str, Any]
    reason_code: str = "RC_CLEAN_MATCH"
    evidence_fields: Dict[str, Any] = Field(default_factory=dict)
    recommended_action: str = "Auto-reconciled: No manual action required."
    owner: str = "Automated Engine"
    sla: str = "Instant / Closed"
    sla_hours: int = 0
    ground_truth_label: Optional[str] = None
    validation_status: str = "UNVALIDATED"  # VALIDATED_CORRECT | MISMATCH | UNVALIDATED


class SimulationEvent(BaseModel):
    """Synthetic persona simulation output generated via MiroFish or offline template."""
    simulation_run_id: str
    scenario_id: str
    transaction_id: str
    agent_role: str  # CUSTOMER, MERCHANT, GATEWAY
    agent_id: str
    persona_name: str
    event_type: str
    event_timestamp: str
    observation: str
    question_or_feedback: str
    evidence_reference: str
    simulation_label: str = "AI-simulated scenario — not real customer feedback"
    model_name: str
    repository_revision: str
    status: str  # LIVE, BLOCKED, PRERECORDED


class ServiceHealth(BaseModel):
    service_name: str
    status: str  # ONLINE, OFFLINE, NOT_CONFIGURED, BLOCKED
    latency_ms: Optional[float] = None
    version_or_info: Optional[str] = None
    details: str
    setup_instructions: Optional[str] = None
    last_checked_utc: str


class PreflightSummary(BaseModel):
    timestamp_utc: str
    ready_for_exasol: bool
    ready_for_mirofish: bool
    services: List[ServiceHealth]
    environment: str
