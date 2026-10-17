"""
Tamper-Evident Audit Logger for ExaSettle.
Implements PRD Section 9.7:
- Append-oriented event log
- Computes SHA-256 verification hash chains
- Records operational execution timestamps and engine metadata
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class AuditEvent(BaseModel):
    event_id: str
    run_id: str
    scenario_id: str
    timestamp_utc: str
    stage: str
    status: str
    engine: str
    details: Dict[str, Any]
    prev_event_hash: Optional[str] = None
    event_hash: str


class AuditLogStore:
    def __init__(self):
        self._events: List[AuditEvent] = []
        self._last_hash: str = "GENESIS_EXASETTLE_2026"

    def record_event(
        self,
        run_id: str,
        scenario_id: str,
        stage: str,
        status: str,
        engine: str,
        details: Dict[str, Any]
    ) -> AuditEvent:
        now = datetime.now(timezone.utc).isoformat()
        event_id = f"EVT_{len(self._events) + 1:04d}_{stage}"

        prev = self._last_hash
        payload = {
            "event_id": event_id,
            "run_id": run_id,
            "scenario_id": scenario_id,
            "timestamp_utc": now,
            "stage": stage,
            "status": status,
            "engine": engine,
            "prev_hash": prev,
            "details": details
        }

        raw_str = json.dumps(payload, sort_keys=True)
        cur_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
        self._last_hash = cur_hash

        evt = AuditEvent(
            event_id=event_id,
            run_id=run_id,
            scenario_id=scenario_id,
            timestamp_utc=now,
            stage=stage,
            status=status,
            engine=engine,
            details=details,
            prev_event_hash=prev,
            event_hash=cur_hash
        )
        self._events.append(evt)
        return evt

    def get_run_events(self, run_id: str) -> List[AuditEvent]:
        return [e for e in self._events if e.run_id == run_id]

    def verify_chain_integrity(self) -> bool:
        """Verify unbroken hash chain across recorded audit events."""
        current_prev = "GENESIS_EXASETTLE_2026"
        for evt in self._events:
            payload = {
                "event_id": evt.event_id,
                "run_id": evt.run_id,
                "scenario_id": evt.scenario_id,
                "timestamp_utc": evt.timestamp_utc,
                "stage": evt.stage,
                "status": evt.status,
                "engine": evt.engine,
                "prev_hash": current_prev,
                "details": evt.details
            }
            expected = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
            if evt.event_hash != expected:
                return False
            current_prev = evt.event_hash
        return True


# Global shared audit instance
global_audit_store = AuditLogStore()
