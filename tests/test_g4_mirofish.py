"""
Gate G4 Verification Tests: MiroFish Integration, Prompt Template & Isolation
"""

import copy
import pytest
from exasettle.generator.dataset_generator import generate_synthetic_dataset
from exasettle.engine.fallback_reconciler import LocalFallbackReconciler
from exasettle.simulation.prompt_templates import format_mirofish_prompt
from exasettle.simulation.mirofish_connector import MiroFishConnector
from exasettle.simulation.prerecorded_store import get_prerecorded_events


def test_prompt_template_exact_conformance():
    """Verify Section 10 prompt template fields and strict guidelines."""
    pkg = generate_synthetic_dataset(seed=42)
    reconciler = LocalFallbackReconciler()
    results, _ = reconciler.reconcile(
        pkg.gateway_records,
        pkg.bank_records,
        pkg.ground_truth
    )

    sample_result = results[0]
    gt = next(g for g in pkg.ground_truth if g.transaction_id == sample_result.transaction_id)
    gw_rec = next((r for r in pkg.gateway_records if r.transaction_id == sample_result.transaction_id), None)
    bk_rec = next((r for r in pkg.bank_records if r.transaction_id == sample_result.transaction_id), None)

    prompt = format_mirofish_prompt(sample_result, gt, gw_rec, bk_rec, assigned_role="CUSTOMER")

    # Verify PRD Section 10 required tokens
    assert "SIMULATION NOTICE" in prompt
    assert "This is a fictional, offline prototype scenario" in prompt
    assert "SCENARIO" in prompt
    assert "Scenario ID:" in prompt
    assert "Synthetic transaction ID:" in prompt
    assert "Synthetic customer persona:" in prompt
    assert "Synthetic merchant persona:" in prompt
    assert "Synthetic gateway role/context:" in prompt
    assert "Deterministic reconciliation classification:" in prompt
    assert "Evidence explanation:" in prompt
    assert "Known-answer expected result" in prompt
    assert "TASK" in prompt
    assert "RULES" in prompt
    assert "PURPOSE" in prompt
    assert "ASSIGNED ROLE TO SIMULATE: CUSTOMER" in prompt


def test_distinct_roles_and_gateway_is_system_actor():
    """Verify Customer, Merchant, and Gateway roles are separated and Gateway is a system actor."""
    connector = MiroFishConnector()
    events = get_prerecorded_events(scenario_id="SCN_TEST", transaction_id="TXN_SYN_101")

    roles = {e.agent_role for e in events}
    assert roles == {"CUSTOMER", "MERCHANT", "GATEWAY"}

    gw_event = next(e for e in events if e.agent_role == "GATEWAY")
    assert "System Actor" in gw_event.persona_name or "System" in gw_event.persona_name
    assert "customer" not in gw_event.persona_name.lower() or "not a customer" in gw_event.persona_name.lower()


def test_simulation_cannot_modify_financial_classification():
    """
    CRITICAL ARCHITECTURAL BOUNDARY:
    Prove that running MiroFish simulation leaves deterministic reconciliation results,
    financial amounts, and classifications completely unchanged.
    """
    pkg = generate_synthetic_dataset(seed=42)
    reconciler = LocalFallbackReconciler()
    results_before, _ = reconciler.reconcile(
        pkg.gateway_records,
        pkg.bank_records,
        pkg.ground_truth
    )

    # Deep copy before simulation
    frozen_before = copy.deepcopy(results_before)

    # Run simulation for every single result
    connector = MiroFishConnector()
    for res in results_before:
        gt = next((g for g in pkg.ground_truth if g.transaction_id == res.transaction_id), None)
        gw_rec = next((r for r in pkg.gateway_records if r.transaction_id == res.transaction_id), None)
        bk_rec = next((r for r in pkg.bank_records if r.transaction_id == res.transaction_id), None)
        events, _ = connector.run_simulation_for_case(res, gt, gw_rec, bk_rec, mode="PRERECORDED")
        assert len(events) == 3

    # Verify reconciliation result is bit-for-bit unchanged
    for r_orig, r_post in zip(frozen_before, results_before):
        assert r_orig.classification == r_post.classification
        assert r_orig.difference_paise == r_post.difference_paise
        assert r_orig.priority_score == r_post.priority_score
        assert r_orig.validation_status == r_post.validation_status
        assert r_orig.applied_rule == r_post.applied_rule


def test_unconfigured_credentials_produce_honest_blocked_state():
    """Verify that when credentials are missing, system returns honest BLOCKED state with setup instructions."""
    connector = MiroFishConnector(llm_api_key="", zep_api_key="")
    readiness = connector.get_readiness_status()
    assert readiness["is_ready_for_live"] is False
    assert readiness["status"] == "BLOCKED"
    assert readiness["setup_instructions"] is not None
    assert "LLM_API_KEY" in readiness["setup_instructions"]

    # Attempting to force LIVE mode without credentials must raise explicit error
    pkg = generate_synthetic_dataset(seed=42)
    reconciler = LocalFallbackReconciler()
    results, _ = reconciler.reconcile(pkg.gateway_records, pkg.bank_records, pkg.ground_truth)
    with pytest.raises(RuntimeError) as exc_info:
        connector.run_simulation_for_case(results[0], None, None, None, mode="LIVE")
    assert "Live simulation blocked" in str(exc_info.value)


def test_simulation_disclosure_persistent():
    """Verify persistent disclosure appears on all simulated output."""
    events = get_prerecorded_events(scenario_id="SCN_TEST", transaction_id="TXN_SYN_101")
    for event in events:
        assert event.simulation_label == "AI-simulated scenario — not real customer feedback"
        assert event.status == "PRERECORDED"
