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
load_dotenv(override=True)


def mask_secret(val: Optional[str]) -> str:
    """Safely mask secret strings so credentials never leak into logs or UI."""
    if not val:
        return "[NOT SET]"
    if len(val) <= 6:
        return "***"
    return f"{val[:3]}...{val[-3:]}"


class Settings:
    @classmethod
    def reload(cls):
        load_dotenv(override=True)

    @property
    def EXASOL_HOST(self) -> str:
        return os.environ.get("EXASOL_HOST", "localhost")

    @property
    def EXASOL_PORT(self) -> int:
        return int(os.environ.get("EXASOL_PORT", "8563"))

    @property
    def EXASOL_USER(self) -> str:
        return os.environ.get("EXASOL_USER", "sys")

    @property
    def EXASOL_PASSWORD(self) -> str:
        return os.environ.get("EXASOL_PASSWORD", "")

    @property
    def EXASOL_SCHEMA(self) -> str:
        return os.environ.get("EXASOL_SCHEMA", "EXA_SETTLE")

    @property
    def EXASOL_ENCRYPTION(self) -> bool:
        return os.environ.get("EXASOL_ENCRYPTION", "True").lower() == "true"

    @property
    def APP_HOST(self) -> str:
        return os.environ.get("APP_HOST", "127.0.0.1")

    @property
    def APP_PORT(self) -> int:
        return int(os.environ.get("APP_PORT", "8000"))

    @property
    def APP_DEBUG(self) -> bool:
        return os.environ.get("APP_DEBUG", "False").lower() == "true"

    @property
    def LLM_API_KEY(self) -> str:
        return os.environ.get("LLM_API_KEY", "")

    @property
    def LLM_BASE_URL(self) -> str:
        return os.environ.get("LLM_BASE_URL", "")

    @property
    def LLM_MODEL_NAME(self) -> str:
        return os.environ.get("LLM_MODEL_NAME", "")

    @property
    def ZEP_API_KEY(self) -> str:
        return os.environ.get("ZEP_API_KEY", "")

    @property
    def MIROFISH_SERVICE_URL(self) -> str:
        return os.environ.get("MIROFISH_SERVICE_URL", "http://localhost:5001")

    PINNED_MIROFISH_REVISION: str = "7657031ac01184afe2cb220f5ee3545573b5e843"

    # Also support class attribute access
    @classmethod
    def get_llm_api_key(cls) -> str:
        return os.environ.get("LLM_API_KEY", "")

    @classmethod
    def get_llm_base_url(cls) -> str:
        """Resolve LLM API base URL, auto-detecting Google AI Studio Gemini."""
        url = os.environ.get("LLM_BASE_URL")
        if url:
            return url
        key = cls.get_llm_api_key()
        if key and (key.startswith("AIza") or key.startswith("AQ.")):
            return "https://generativelanguage.googleapis.com/v1beta/openai/"
        return "https://api.openai.com/v1"

    @classmethod
    def get_llm_model_name(cls) -> str:
        """Resolve LLM model name, defaulting to gemini-2.5-flash for Google AI Studio."""
        model = os.environ.get("LLM_MODEL_NAME")
        if model:
            return model
        key = cls.get_llm_api_key()
        if key and (key.startswith("AIza") or key.startswith("AQ.")):
            return "gemini-2.5-flash"
        return "gpt-4o-mini"


# Module-level instance for attribute access
Settings = Settings()


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


def check_model_api(test_connectivity: bool = False) -> ServiceHealth:
    """Check LLM provider configuration and functional readiness."""
    now = datetime.now(timezone.utc).isoformat()
    if not Settings.LLM_API_KEY:
        return ServiceHealth(
            service_name="LLM Model Provider API",
            status="NOT_CONFIGURED",
            details="LLM_API_KEY is not configured.",
            setup_instructions=(
                "To enable live multi-agent simulation:\n"
                "1. Provide LLM_API_KEY in .env (OpenAI or Google AI Studio Gemini endpoint)\n"
                "2. Optionally set LLM_BASE_URL and LLM_MODEL_NAME."
            ),
            last_checked_utc=now
        )

    endpoint = Settings.get_llm_base_url()
    model = Settings.get_llm_model_name()
    provider = "Google AI Studio Gemini" if "generativelanguage.googleapis.com" in endpoint else "OpenAI Compatible"

    if test_connectivity:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=Settings.LLM_API_KEY, base_url=endpoint, timeout=2.0)
            client.models.list()
            return ServiceHealth(
                service_name="LLM Model Provider API",
                status="FUNCTIONAL",
                version_or_info=f"{provider} ({model})",
                details=f"LLM API verified functional ({mask_secret(Settings.LLM_API_KEY)}), Endpoint: {endpoint}",
                last_checked_utc=now
            )
        except Exception as e:
            return ServiceHealth(
                service_name="LLM Model Provider API",
                status="REACHABLE" if "401" in str(e) or "authentication" in str(e).lower() else "CONFIGURED",
                version_or_info=f"{provider} ({model})",
                details=f"Configured but live ping failed: {type(e).__name__} ({mask_secret(Settings.LLM_API_KEY)})",
                last_checked_utc=now
            )

    return ServiceHealth(
        service_name="LLM Model Provider API",
        status="CONFIGURED",
        version_or_info=f"{provider} ({model})",
        details=f"LLM_API_KEY is configured ({mask_secret(Settings.LLM_API_KEY)}), Endpoint: {endpoint}",
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
