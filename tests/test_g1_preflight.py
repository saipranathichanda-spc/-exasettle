"""
Gate G1 Verification Tests: Architecture, Preflight & Credential Safety
"""

import os
from exasettle.core.config import mask_secret, run_preflight, check_exasol, check_model_api, check_zep_memory, check_mirofish_service, check_app_api
from exasettle.core.money import rupees_to_paise, paise_to_rupees, format_inr


def test_secret_masking():
    """Verify secrets are redacted safely."""
    assert mask_secret("") == "[NOT SET]"
    assert mask_secret(None) == "[NOT SET]"
    assert mask_secret("12345") == "***"
    assert mask_secret("sk-proj-1234567890abcdef") == "sk-...def"
    assert "1234567890" not in mask_secret("sk-proj-1234567890abcdef")


def test_preflight_checks_execute_without_crashing():
    """Verify preflight runs across all services and returns structured health models."""
    summary = run_preflight()
    assert summary.timestamp_utc is not None
    assert len(summary.services) == 5

    names = [s.service_name for s in summary.services]
    assert "Exasol Personal Analytical Database" in names
    assert "LLM Model Provider API" in names
    assert "Zep Cloud Agent Memory Graph" in names
    assert "MiroFish Swarm Intelligence Engine" in names
    assert "ExaSettle API & Orchestrator" in names


def test_setup_instructions_present_when_unconfigured():
    """Verify missing dependencies return explicit, actionable instructions."""
    exa_health = check_exasol()
    if exa_health.status in ["NOT_CONFIGURED", "OFFLINE"]:
        assert exa_health.setup_instructions is not None
        assert "docker run" in exa_health.setup_instructions or "8563" in exa_health.setup_instructions

    llm_health = check_model_api()
    if llm_health.status == "NOT_CONFIGURED":
        assert llm_health.setup_instructions is not None
        assert "LLM_API_KEY" in llm_health.setup_instructions

    zep_health = check_zep_memory()
    if zep_health.status == "NOT_CONFIGURED":
        assert zep_health.setup_instructions is not None
        assert "ZEP_API_KEY" in zep_health.setup_instructions


def test_monetary_arithmetic_exactness():
    """Verify integer paise calculations have zero floating point rounding errors."""
    assert rupees_to_paise(100) == 10000
    assert rupees_to_paise(1250.50) == 125050
    assert rupees_to_paise("99.99") == 9999
    assert rupees_to_paise("0.01") == 1
    assert rupees_to_paise(0) == 0

    from decimal import Decimal
    assert paise_to_rupees(125050) == Decimal("1250.50")
    assert paise_to_rupees(99) == Decimal("0.99")

    assert format_inr(125050) == "₹1,250.50"
    assert format_inr(10000000) == "₹1,00,000.00"
    assert format_inr(-5000) == "-₹50.00"
