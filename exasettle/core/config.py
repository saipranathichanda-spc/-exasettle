"""
Configuration manager and service preflight verifier for ExaSettle.
Ensures secret redaction and safe setup instructions per PRD Sections 9.2, 9.3, 13.
"""

import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from exasettle.core.models import ServiceHealth, PreflightSummary

# Load local .env if present
load_dotenv(override=False)


def mask_secret(val: Optional[str]) -> str:
    """Safely mask secret strings so credentials never leak into logs or UI."""
    if not val:
        return "[NOT SET]"
    if len(val) <= 6:
        return "***"
    return f"{val[:3]}...{val[-3:]}"


class Settings:
    # Exasol Personal Analytical Database
    EXASOL_HOST: str = os.environ.get("EXASOL_HOST", "localhost")
    EXASOL_PORT: int = int(os.environ.get("EXASOL_PORT", "8563"))
    EXASOL_USER: str = os.environ.get("EXASOL_USER", "sys")
    EXASOL_PASSWORD: str = os.environ.get("EXASOL_PASSWORD", "")
    EXASOL_SCHEMA: str = os.environ.get("EXASOL_SCHEMA", "EXA_SETTLE")
    EXASOL_ENCRYPTION: bool = os.environ.get("EXASOL_ENCRYPTION", "True").lower() == "true"

    # Application Configuration
    APP_HOST: str = os.environ.get("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.environ.get("APP_PORT", "8000"))
    APP_DEBUG: bool = os.environ.get("APP_DEBUG", "False").lower() == "true"

    # MiroFish and LLM Provider
    LLM_API_KEY: str = os.environ.get("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL_NAME: str = os.environ.get("LLM_MODEL_NAME", "gpt-4o-mini")
    ZEP_API_KEY: str = os.environ.get("ZEP_API_KEY", "")
    MIROFISH_SERVICE_URL: str = os.environ.get("MIROFISH_SERVICE_URL", "http://localhost:5001")

    # Pinned Revisions
    PINNED_MIROFISH_REVISION: str = "7657031ac01184afe2cb220f5ee3545573b5e843"


def check_exasol() -> ServiceHealth:
    """Check connectivity to Exasol Personal database."""
    now = datetime.now(timezone.utc).isoformat()
    if not Settings.EXASOL_PASSWORD:
        return ServiceHealth(
            service_name="Exasol Personal Analytical Database",
            status="NOT_CONFIGURED",
            details="EXASOL_PASSWORD is empty or unset in environment.",
            setup_instructions=(
                "To connect Exasol Personal:\n"
                "1. Start Exasol Personal container: docker run --name exasoldb -p 8563:8563 -d exasol/docker-db:latest\n"
                "2. Set EXASOL_HOST, EXASOL_PORT, EXASOL_USER, and EXASOL_PASSWORD in your private .env\n"
                "3. ExaSettle will automatically use Exasol for high-speed analytical reconciliation.\n"
                "Note: A local deterministic fallback engine is available if Exasol is not running."
            ),
            last_checked_utc=now
        )

    t0 = time.perf_counter()
    try:
        import pyexasol
        con = pyexasol.connect(
            dsn=f"{Settings.EXASOL_HOST}:{Settings.EXASOL_PORT}",
            user=Settings.EXASOL_USER,
            password=Settings.EXASOL_PASSWORD,
            schema=Settings.EXASOL_SCHEMA,
            encryption=Settings.EXASOL_ENCRYPTION,
            connection_timeout=3
        )
        version_info = con.meta.sql_type()
        con.close()
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return ServiceHealth(
            service_name="Exasol Personal Analytical Database",
            status="ONLINE",
            latency_ms=elapsed_ms,
            version_or_info=str(version_info),
            details=f"Connected to {Settings.EXASOL_HOST}:{Settings.EXASOL_PORT} as {Settings.EXASOL_USER}",
            last_checked_utc=now
        )
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return ServiceHealth(
            service_name="Exasol Personal Analytical Database",
            status="OFFLINE",
            latency_ms=elapsed_ms,
            details=f"Connection failed: {type(e).__name__} - {str(e)[:120]}",
            setup_instructions=(
                f"Cannot reach Exasol at {Settings.EXASOL_HOST}:{Settings.EXASOL_PORT}. "
                "Verify database process is running and network port 8563 is accessible. "
                "Local fallback engine will be used until Exasol is reachable."
            ),
            last_checked_utc=now
        )


def check_model_api() -> ServiceHealth:
    """Check LLM provider configuration for MiroFish."""
    now = datetime.now(timezone.utc).isoformat()
    if not Settings.LLM_API_KEY:
        return ServiceHealth(
            service_name="LLM Model Provider API",
            status="NOT_CONFIGURED",
            details="LLM_API_KEY is not configured.",
            setup_instructions=(
                "To enable live multi-agent simulation:\n"
                "1. Provide LLM_API_KEY in .env (OpenAI or DashScope/Qwen compatible endpoint)\n"
                "2. Optionally set LLM_BASE_URL and LLM_MODEL_NAME."
            ),
            last_checked_utc=now
        )

    return ServiceHealth(
        service_name="LLM Model Provider API",
        status="CONFIGURED",
        version_or_info=f"Endpoint: {Settings.LLM_BASE_URL}, Model: {Settings.LLM_MODEL_NAME}",
        details=f"LLM_API_KEY is configured ({mask_secret(Settings.LLM_API_KEY)})",
        last_checked_utc=now
    )


def check_zep_memory() -> ServiceHealth:
    """Check Zep Cloud agent-memory backend required by MiroFish."""
    now = datetime.now(timezone.utc).isoformat()
    if not Settings.ZEP_API_KEY:
        return ServiceHealth(
            service_name="Zep Cloud Agent Memory Graph",
            status="NOT_CONFIGURED",
            details="ZEP_API_KEY is not configured.",
            setup_instructions=(
                "MiroFish requires Zep Cloud for long-term agent memory and graph updates:\n"
                "1. Obtain a free Zep Cloud API key at https://app.getzep.com/\n"
                "2. Add ZEP_API_KEY to your .env file.\n"
                "Note: MiroFish does not support local ZEP_API_URL."
            ),
            last_checked_utc=now
        )

    return ServiceHealth(
        service_name="Zep Cloud Agent Memory Graph",
        status="CONFIGURED",
        details=f"ZEP_API_KEY is configured ({mask_secret(Settings.ZEP_API_KEY)})",
        last_checked_utc=now
    )


def check_mirofish_service() -> ServiceHealth:
    """Check MiroFish microservice connectivity."""
    now = datetime.now(timezone.utc).isoformat()
    import requests
    t0 = time.perf_counter()
    try:
        resp = requests.get(f"{Settings.MIROFISH_SERVICE_URL}/api/health", timeout=1.5)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        if resp.status_code == 200:
            return ServiceHealth(
                service_name="MiroFish Swarm Intelligence Engine",
                status="ONLINE",
                latency_ms=elapsed_ms,
                version_or_info=f"Revision: {Settings.PINNED_MIROFISH_REVISION[:8]}",
                details=f"Service reachable at {Settings.MIROFISH_SERVICE_URL}",
                last_checked_utc=now
            )
        else:
            return ServiceHealth(
                service_name="MiroFish Swarm Intelligence Engine",
                status="UNHEALTHY",
                latency_ms=elapsed_ms,
                details=f"Received HTTP {resp.status_code} from {Settings.MIROFISH_SERVICE_URL}",
                last_checked_utc=now
            )
    except Exception:
        # Check if code exists locally in vendor
        vendor_exists = os.path.exists(os.path.join(os.path.dirname(__file__), "../../vendor/MiroFish/backend/run.py"))
        details = (
            f"Service offline at {Settings.MIROFISH_SERVICE_URL}. "
            + ("Local vendor repository present." if vendor_exists else "Vendor repository missing.")
        )
        return ServiceHealth(
            service_name="MiroFish Swarm Intelligence Engine",
            status="BLOCKED" if not (Settings.LLM_API_KEY and Settings.ZEP_API_KEY) else "OFFLINE",
            details=details,
            setup_instructions=(
                "To start MiroFish microservice:\n"
                "1. Ensure LLM_API_KEY and ZEP_API_KEY are configured in vendor/MiroFish/.env\n"
                "2. Run: python vendor/MiroFish/backend/run.py\n"
                "3. Server will listen on port 5001.\n"
                "Note: When MiroFish is offline or unconfigured, ExaSettle displays an honest BLOCKED/OFFLINE indicator or uses clearly labeled PRERECORDED simulation material."
            ),
            last_checked_utc=now
        )


def check_app_api() -> ServiceHealth:
    """Check local ExaSettle API runtime health."""
    now = datetime.now(timezone.utc).isoformat()
    return ServiceHealth(
        service_name="ExaSettle API & Orchestrator",
        status="ONLINE",
        version_or_info="Version 2.0 (ExaThon India 2026)",
        details=f"Listening configuration: {Settings.APP_HOST}:{Settings.APP_PORT}",
        last_checked_utc=now
    )


def run_preflight() -> PreflightSummary:
    """Run comprehensive preflight checks across all components."""
    exa_health = check_exasol()
    llm_health = check_model_api()
    zep_health = check_zep_memory()
    miro_health = check_mirofish_service()
    app_health = check_app_api()

    return PreflightSummary(
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        ready_for_exasol=(exa_health.status == "ONLINE"),
        ready_for_mirofish=(miro_health.status == "ONLINE"),
        services=[app_health, exa_health, miro_health, llm_health, zep_health],
        environment="Local / Hackathon Testbed"
    )
