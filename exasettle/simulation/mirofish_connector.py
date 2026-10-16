"""
Controlled MiroFish Simulation Connector.
Implements PRD Section 9.2:
- Integrates with pinned MiroFish revision 7657031ac01184afe2cb220f5ee3545573b5e843
- Formats prompts from Section 10 template
- Connects three roles: Customer, Merchant, Gateway (System Actor)
- Explicitly handles BLOCKED state when credentials/services are missing
- Strict truth boundary: agent output NEVER touches or mutates reconciliation results
"""

import os
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from exasettle.core.config import Settings
from exasettle.core.models import (
    ReconciliationResult,
    GroundTruthRecord,
    LedgerRecord,
    SimulationEvent,
    ServiceHealth
)
from exasettle.simulation.prompt_templates import format_mirofish_prompt
from exasettle.simulation.prerecorded_store import get_prerecorded_events


class MiroFishConnector:
    PINNED_REVISION = "7657031ac01184afe2cb220f5ee3545573b5e843"

    def __init__(
        self,
        service_url: Optional[str] = None,
        llm_api_key: Optional[str] = None,
        zep_api_key: Optional[str] = None
    ):
        self.service_url = service_url or Settings.MIROFISH_SERVICE_URL
        self.llm_api_key = llm_api_key or Settings.LLM_API_KEY
        self.zep_api_key = zep_api_key or Settings.ZEP_API_KEY

    def get_readiness_status(self) -> Dict[str, Any]:
        """Check whether live simulation can run or is blocked."""
        has_llm = bool(self.llm_api_key)
        has_zep = bool(self.zep_api_key)
        is_ready = has_llm and has_zep

        return {
            "is_ready_for_live": is_ready,
            "has_llm_credentials": has_llm,
            "has_zep_credentials": has_zep,
            "pinned_revision": self.PINNED_REVISION,
            "status": "READY" if is_ready else "BLOCKED",
            "setup_instructions": (
                "To enable live agent simulation, configure LLM_API_KEY and ZEP_API_KEY in your private .env file. "
                "Alternatively, select PRERECORDED simulation mode for the hackathon demonstration."
                if not is_ready else None
            )
        }

    def run_simulation_for_case(
        self,
        result: ReconciliationResult,
        ground_truth: Optional[GroundTruthRecord],
        gw_record: Optional[LedgerRecord],
        bk_record: Optional[LedgerRecord],
        mode: str = "AUTO"  # AUTO, LIVE, PRERECORDED, BLOCKED
    ) -> Tuple[List[SimulationEvent], Dict[str, Any]]:
        """
        Execute simulation for a single case.
        Returns: (events, run_metadata)
        """
        readiness = self.get_readiness_status()
        selected_mode = mode

        if mode == "AUTO":
            selected_mode = "LIVE" if readiness["is_ready_for_live"] else "PRERECORDED"

        if selected_mode == "LIVE":
            if not readiness["is_ready_for_live"]:
                raise RuntimeError(
                    f"Live simulation blocked: {readiness['setup_instructions']}"
                )
            return self._run_live_simulation(result, ground_truth, gw_record, bk_record)
        elif selected_mode == "PRERECORDED":
            events = get_prerecorded_events(
                scenario_id=result.scenario_id,
                transaction_id=result.transaction_id,
                run_id=result.run_id
            )
            meta = {
                "simulation_status": "PRERECORDED",
                "is_live": False,
                "events_count": len(events),
                "model_name": "prerecorded_qwen-plus",
                "pinned_revision": self.PINNED_REVISION,
                "disclosure": "AI-simulated scenario — not real customer feedback"
            }
            return events, meta
        else:  # BLOCKED
            return [], {
                "simulation_status": "BLOCKED",
                "is_live": False,
                "events_count": 0,
                "pinned_revision": self.PINNED_REVISION,
                "reason": readiness["setup_instructions"]
            }

    def _run_live_simulation(
        self,
        result: ReconciliationResult,
        ground_truth: Optional[GroundTruthRecord],
        gw_record: Optional[LedgerRecord],
        bk_record: Optional[LedgerRecord]
    ) -> Tuple[List[SimulationEvent], Dict[str, Any]]:
        """Run live LLM queries with Section 10 prompts for Customer, Merchant, and Gateway."""
        from openai import OpenAI
        client = OpenAI(
            api_key=self.llm_api_key,
            base_url=Settings.LLM_BASE_URL
        )

        roles = [
            ("CUSTOMER", ground_truth.synthetic_customer_name if ground_truth else "Fictional Customer"),
            ("MERCHANT", ground_truth.synthetic_merchant_name if ground_truth else "Fictional Merchant"),
            ("GATEWAY", "Synthetic Gateway Telemetry Actor")
        ]

        events: List[SimulationEvent] = []
        now = datetime.now(timezone.utc).isoformat()

        for role_name, persona in roles:
            prompt = format_mirofish_prompt(
                result=result,
                ground_truth=ground_truth,
                gw_record=gw_record,
                bk_record=bk_record,
                assigned_role=role_name
            )

            try:
                response = client.chat.completions.create(
                    model=Settings.LLM_MODEL_NAME,
                    messages=[
                        {"role": "system", "content": "You are role-playing in an offline, synthetic settlement reconciliation simulator. Follow the prompt format strictly."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.4,
                    max_tokens=250
                )
                text = response.choices[0].message.content or ""
            except Exception as e:
                text = f"[SIMULATION ERROR] Provider call failed: {str(e)[:100]}"

            events.append(SimulationEvent(
                simulation_run_id=f"live_sim_{result.run_id}_{result.transaction_id}",
                scenario_id=result.scenario_id,
                transaction_id=result.transaction_id,
                agent_role=role_name,
                agent_id=f"LIVE_{role_name}_{result.transaction_id}",
                persona_name=persona,
                event_type="LIVE_SYNTHETIC_REACTION",
                event_timestamp=now,
                observation=text,
                question_or_feedback="Live persona reaction generated via MiroFish prompt specification.",
                evidence_reference=f"RECON_EVIDENCE_FOR_{result.transaction_id}",
                simulation_label="AI-simulated scenario — not real customer feedback",
                model_name=Settings.LLM_MODEL_NAME,
                repository_revision=self.PINNED_REVISION,
                status="LIVE"
            ))

        meta = {
            "simulation_status": "LIVE",
            "is_live": True,
            "events_count": len(events),
            "model_name": Settings.LLM_MODEL_NAME,
            "pinned_revision": self.PINNED_REVISION,
            "disclosure": "AI-simulated scenario — not real customer feedback"
        }
        return events, meta
