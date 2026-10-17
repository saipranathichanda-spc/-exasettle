"""
Controlled MiroFish Simulation Connector & Direct LLM Roleplay Engine.
Implements PRD Section 9.2 & Gate G4:
- Integrates with pinned MiroFish revision 7657031ac01184afe2cb220f5ee3545573b5e843
- Distinguishes TRUE_MIROFISH, DIRECT_LLM_ROLEPLAY, and PRERECORDED modes
- Honest simulation labels: never call direct LLM "MiroFish"
- Formats prompts with PRD Section 10 template (ground-truth isolated)
- Connects three roles: Customer, Merchant, Gateway (System Actor)
- Explicitly handles BLOCKED state when credentials/services are missing
- Provider errors produce FAILED or PARTIAL, never successful LIVE events
- Strict truth boundary: agent output NEVER touches or mutates reconciliation results
"""

import os
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

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
        self.llm_api_key = llm_api_key if llm_api_key is not None else Settings.LLM_API_KEY
        self.zep_api_key = zep_api_key if zep_api_key is not None else Settings.ZEP_API_KEY

    def check_mirofish_service_reachable(self) -> bool:
        """Check if upstream MiroFish microservice is responding."""
        try:
            import requests
            resp = requests.get(f"{self.service_url}/health", timeout=0.2)
            return resp.status_code == 200
        except Exception:
            try:
                import requests
                resp = requests.get(f"{self.service_url}/api/health", timeout=0.2)
                return resp.status_code == 200
            except Exception:
                return False

    def get_readiness_status(self) -> Dict[str, Any]:
        """Check whether live simulation can run or is blocked."""
        has_llm = bool(self.llm_api_key)
        has_zep = bool(self.zep_api_key)
        miro_reachable = self.check_mirofish_service_reachable()
        is_ready = bool(miro_reachable or (has_llm and has_zep))

        return {
            "is_ready_for_live": is_ready,
            "is_ready_for_mirofish": miro_reachable,
            "is_ready_for_llm_roleplay": has_llm,
            "has_llm_credentials": has_llm,
            "has_zep_credentials": has_zep,
            "service_url": self.service_url,
            "pinned_revision": self.PINNED_REVISION,
            "status": "READY" if is_ready else "BLOCKED",
            "setup_instructions": (
                "To enable live multi-agent simulation:\n"
                "1. For True MiroFish: Start MiroFish service on port 5001 with Zep Cloud & LLM credentials.\n"
                "2. For Direct LLM Roleplay: Configure LLM_API_KEY in your private .env file.\n"
                "Alternatively, select PRERECORDED simulation mode for offline demonstration."
                if not is_ready else None
            )
        }

    def run_simulation_for_case(
        self,
        result: ReconciliationResult,
        ground_truth: Optional[GroundTruthRecord],
        gw_record: Optional[LedgerRecord],
        bk_record: Optional[LedgerRecord],
        mode: str = "AUTO"  # AUTO, TRUE_MIROFISH, DIRECT_LLM_ROLEPLAY, LIVE, PRERECORDED, BLOCKED
    ) -> Tuple[List[SimulationEvent], Dict[str, Any]]:
        """
        Execute simulation for a single case under honest mode semantics.
        Returns: (events, run_metadata)
        """
        mode_upper = mode.upper()

        # Fast-path for offline prerecorded mode (no network overhead)
        if mode_upper == "PRERECORDED":
            events = get_prerecorded_events(
                scenario_id=result.scenario_id,
                transaction_id=result.transaction_id,
                run_id=result.run_id
            )
            meta = {
                "simulation_status": "PRERECORDED",
                "simulation_mode": "PRERECORDED",
                "is_live": False,
                "events_count": len(events),
                "model_name": "prerecorded_qwen-plus",
                "pinned_revision": self.PINNED_REVISION,
                "disclosure": "AI-simulated scenario — not real customer feedback",
                "simulation_label": "Prerecorded synthetic simulation — not live and not real customer feedback"
            }
            return events, meta

        readiness = self.get_readiness_status()

        # Resolve mode
        if mode_upper == "AUTO":
            if readiness["is_ready_for_mirofish"]:
                selected_mode = "TRUE_MIROFISH"
            elif readiness["is_ready_for_llm_roleplay"]:
                selected_mode = "DIRECT_LLM_ROLEPLAY"
            else:
                selected_mode = "PRERECORDED"
        elif mode_upper == "LIVE":
            if readiness["is_ready_for_mirofish"]:
                selected_mode = "TRUE_MIROFISH"
            elif readiness["is_ready_for_llm_roleplay"] and readiness["has_zep_credentials"]:
                selected_mode = "DIRECT_LLM_ROLEPLAY"
            else:
                raise RuntimeError(
                    f"Live simulation blocked: {readiness['setup_instructions']}"
                )
        else:
            selected_mode = mode_upper

        if selected_mode == "TRUE_MIROFISH":
            return self._run_true_mirofish(result, ground_truth, gw_record, bk_record)
        elif selected_mode in ("DIRECT_LLM_ROLEPLAY", "LLM_ROLEPLAY"):
            return self._run_direct_llm_roleplay(result, ground_truth, gw_record, bk_record)
        elif selected_mode == "PRERECORDED":
            events = get_prerecorded_events(
                scenario_id=result.scenario_id,
                transaction_id=result.transaction_id,
                run_id=result.run_id
            )
            meta = {
                "simulation_status": "PRERECORDED",
                "simulation_mode": "PRERECORDED",
                "is_live": False,
                "events_count": len(events),
                "model_name": "prerecorded_qwen-plus",
                "pinned_revision": self.PINNED_REVISION,
                "disclosure": "AI-simulated scenario — not real customer feedback",
                "simulation_label": "Prerecorded synthetic simulation — not live and not real customer feedback"
            }
            return events, meta
        else:  # BLOCKED or UNKNOWN
            return [], {
                "simulation_status": "BLOCKED",
                "simulation_mode": selected_mode,
                "is_live": False,
                "events_count": 0,
                "pinned_revision": self.PINNED_REVISION,
                "reason": readiness["setup_instructions"] or f"Simulation blocked for mode {selected_mode}."
            }

    def _run_true_mirofish(
        self,
        result: ReconciliationResult,
        ground_truth: Optional[GroundTruthRecord],
        gw_record: Optional[LedgerRecord],
        bk_record: Optional[LedgerRecord]
    ) -> Tuple[List[SimulationEvent], Dict[str, Any]]:
        """Invoke pinned MiroFish backend microservice via documented REST workflow."""
        if not self.check_mirofish_service_reachable():
            return [], {
                "simulation_status": "BLOCKED",
                "simulation_mode": "TRUE_MIROFISH",
                "is_live": False,
                "events_count": 0,
                "pinned_revision": self.PINNED_REVISION,
                "reason": f"MiroFish microservice offline at {self.service_url}. Upstream service not reachable."
            }

        # If reachable, execute MiroFish workflow
        import requests
        try:
            create_payload = {
                "scenario_id": result.scenario_id,
                "transaction_id": result.transaction_id,
                "pinned_revision": self.PINNED_REVISION
            }
            resp = requests.post(f"{self.service_url}/api/simulation/create", json=create_payload, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                sim_id = data.get("simulation_id", f"miro_{result.transaction_id}")
                return [], {
                    "simulation_status": "RUNNING",
                    "simulation_mode": "TRUE_MIROFISH",
                    "simulation_id": sim_id,
                    "is_live": True,
                    "pinned_revision": self.PINNED_REVISION
                }
            else:
                return [], {
                    "simulation_status": "FAILED",
                    "simulation_mode": "TRUE_MIROFISH",
                    "is_live": False,
                    "status_code": resp.status_code,
                    "reason": f"MiroFish /api/simulation/create failed with HTTP {resp.status_code}"
                }
        except Exception as e:
            return [], {
                "simulation_status": "FAILED",
                "simulation_mode": "TRUE_MIROFISH",
                "is_live": False,
                "reason": f"MiroFish invocation failed: {str(e)[:120]}"
            }

    def _run_direct_llm_roleplay(
        self,
        result: ReconciliationResult,
        ground_truth: Optional[GroundTruthRecord],
        gw_record: Optional[LedgerRecord],
        bk_record: Optional[LedgerRecord]
    ) -> Tuple[List[SimulationEvent], Dict[str, Any]]:
        """
        Execute direct LLM role-play calls for Customer, Merchant, and Gateway.
        HONEST LABELING: Explicitly identified as Direct LLM role-play, NOT MiroFish multi-agent graph.
        Provider errors produce FAILED or PARTIAL, never successful LIVE events.
        """
        if not self.llm_api_key:
            return [], {
                "simulation_status": "BLOCKED",
                "simulation_mode": "DIRECT_LLM_ROLEPLAY",
                "is_live": False,
                "events_count": 0,
                "reason": "LLM_API_KEY is not configured."
            }

        from openai import OpenAI
        endpoint = Settings.get_llm_base_url()
        model_name = Settings.get_llm_model_name()
        client = OpenAI(
            api_key=self.llm_api_key,
            base_url=endpoint
        )

        roles = [
            ("CUSTOMER", ground_truth.synthetic_customer_name if ground_truth else "Fictional Customer"),
            ("MERCHANT", ground_truth.synthetic_merchant_name if ground_truth else "Fictional Merchant"),
            ("GATEWAY", "Synthetic Gateway Telemetry Actor")
        ]

        events: List[SimulationEvent] = []
        now = datetime.now(timezone.utc).isoformat()
        failure_count = 0

        for role_name, persona in roles:
            prompt = format_mirofish_prompt(
                result=result,
                ground_truth=ground_truth,
                gw_record=gw_record,
                bk_record=bk_record,
                assigned_role=role_name
            )

            call_success = False
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are role-playing in an offline, synthetic settlement reconciliation simulator. "
                                "Follow the prompt format strictly. Do not invent real money or real people."
                            )
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.4,
                    max_tokens=250,
                    timeout=15.0
                )
                text = response.choices[0].message.content or ""
                call_success = True
            except Exception as e:
                text = f"[SIMULATION ERROR] Provider call failed: {type(e).__name__} - {str(e)[:120]}"
                failure_count += 1

            event_status = "DIRECT_LLM_ROLEPLAY" if call_success else "FAILED"
            events.append(SimulationEvent(
                simulation_run_id=f"llm_sim_{result.run_id}_{result.transaction_id}",
                scenario_id=result.scenario_id,
                transaction_id=result.transaction_id,
                agent_role=role_name,
                agent_id=f"ROLEPLAY_{role_name}_{result.transaction_id}",
                persona_name=persona,
                event_type="DIRECT_LLM_SYNTHETIC_REACTION",
                event_timestamp=now,
                observation=text,
                question_or_feedback="Direct LLM synthetic reaction generated via Section 10 prompt template.",
                evidence_reference=f"RECON_EVIDENCE_FOR_{result.transaction_id}",
                simulation_label="Direct LLM Synthetic Role-Play — not MiroFish engine and not real customer feedback",
                model_name=model_name,
                repository_revision=self.PINNED_REVISION,
                status=event_status
            ))

        if failure_count == 0:
            sim_status = "DIRECT_LLM_ROLEPLAY"
        elif failure_count < len(roles):
            sim_status = "PARTIAL"
        else:
            sim_status = "FAILED"

        meta = {
            "simulation_status": sim_status,
            "simulation_mode": "DIRECT_LLM_ROLEPLAY",
            "is_live": (sim_status == "DIRECT_LLM_ROLEPLAY"),
            "events_count": len(events),
            "model_name": model_name,
            "pinned_revision": self.PINNED_REVISION,
            "disclosure": "AI-simulated scenario — direct LLM role-play (not MiroFish multi-agent graph)"
        }
        return events, meta

    # Backward-compatible alias for existing tests
    _run_live_simulation = _run_direct_llm_roleplay
