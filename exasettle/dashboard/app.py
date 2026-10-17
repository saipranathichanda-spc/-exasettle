"""
ExaSettle Interactive Live Dashboard Server (FastAPI).
Implements PRD Section 9.6:
- Run control: scenario selection, seed choice, run execution
- Service health: Exasol, MiroFish, LLM provider, Zep Cloud, App API with real timestamps
- Run timeline: timestamped events for generation, ingestion, Exasol reconciliation, MiroFish
- Financial results: totals and counts from actual query output, ground truth validation
- Evidence drilldown: gateway and bank source rows, applied rule, priority score
- Simulation panel: distinct simulation timeline and persistent disclosure badges
- Export endpoints: CSV and JSON
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from exasettle.core.config import Settings, run_preflight
from exasettle.core.models import (
    ReconciliationResult,
    SimulationEvent,
    LedgerRecord,
    GroundTruthRecord
)
from exasettle.generator.dataset_generator import generate_synthetic_dataset, SyntheticDatasetPackage
from exasettle.engine.fallback_reconciler import LocalFallbackReconciler
from exasettle.engine.exasol_reconciler import ExasolReconciler
from exasettle.simulation.mirofish_connector import MiroFishConnector
from exasettle.audit.logger import AuditLogStore, global_audit_store
from exasettle.audit.exporter import generate_reconciliation_csv, generate_run_summary_json

app = FastAPI(
    title="ExaSettle Dashboard API",
    description="Explainable Settlement-Reconciliation Prototype - ExaThon India 2026",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory run store
runs_cache: Dict[str, Dict[str, Any]] = {}
active_subscribers: List[asyncio.Queue] = []


class RunRequest(BaseModel):
    scenario_id: str = "SCN_CORE_8PACK"
    seed: int = 42
    extra_matched_count: int = 0
    settlement_delay_threshold_hours: int = 24
    engine_preference: str = "AUTO"  # AUTO, EXASOL, FALLBACK
    simulation_mode: str = "AUTO"    # AUTO, LIVE, PRERECORDED, BLOCKED


async def emit_event(event_type: str, data: Dict[str, Any]):
    """Broadcast SSE event to connected dashboard clients."""
    payload = {
        "event_type": event_type,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "data": data
    }
    for q in active_subscribers:
        await q.put(payload)


@app.get("/api/health")
def get_service_health():
    """Retrieve live service health for all components without secret leakage."""
    return run_preflight()


@app.post("/api/run")
async def execute_run(req: RunRequest):
    """Execute end-to-end reconciliation run with real event streaming."""
    run_id = f"run_{int(time.time())}_{req.seed}"
    await emit_event("RUN_INITIALIZING", {"run_id": run_id, "scenario_id": req.scenario_id, "seed": req.seed})

    # Step 1: Generate synthetic dataset
    await emit_event("STATUS_TRANSITION", {"stage": "SCENARIO_CREATED", "message": "Creating synthetic scenario..."})
    pkg: SyntheticDatasetPackage = generate_synthetic_dataset(
        run_id=run_id,
        scenario_id=req.scenario_id,
        seed=req.seed,
        extra_matched_count=req.extra_matched_count,
        settlement_delay_threshold_hours=req.settlement_delay_threshold_hours
    )
    global_audit_store.record_event(
        run_id, req.scenario_id, "DATASET_GENERATED", "SUCCESS", "PYTHON_RNG",
        {"dataset_hash": pkg.dataset_hash, "records_count": pkg.total_records}
    )
    await emit_event("STATUS_TRANSITION", {
        "stage": "SOURCE_RECORDS_GENERATED",
        "message": f"Generated {pkg.total_records} synthetic records ({len(pkg.gateway_records)} gateway, {len(pkg.bank_records)} bank)",
        "dataset_hash": pkg.dataset_hash
    })

    # Step 2: Ingest & Reconcile
    await emit_event("STATUS_TRANSITION", {"stage": "RECORDS_LOADING", "message": "Staging records in analytical database..."})
    use_exasol = False
    if req.engine_preference == "EXASOL":
        use_exasol = True
    elif req.engine_preference == "AUTO":
        # Check if Exasol is available
        preflight = run_preflight()
        use_exasol = preflight.ready_for_exasol

    results: List[ReconciliationResult] = []
    engine_metrics: Dict[str, Any] = {}
    if use_exasol:
        try:
            exasol_engine = ExasolReconciler()
            await emit_event("STATUS_TRANSITION", {"stage": "RECONCILIATION_RUNNING", "message": "Executing CTE analytical SQL on Exasol Personal..."})
            results, engine_metrics = exasol_engine.reconcile(
                pkg.gateway_records,
                pkg.bank_records,
                pkg.ground_truth,
                settlement_delay_threshold_hours=req.settlement_delay_threshold_hours
            )
        except Exception as e:
            # Fallback gracefully and notify client transparently
            local_engine = LocalFallbackReconciler()
            results, engine_metrics = local_engine.reconcile(
                pkg.gateway_records,
                pkg.bank_records,
                pkg.ground_truth,
                settlement_delay_threshold_hours=req.settlement_delay_threshold_hours
            )
            engine_metrics["engine_mode"] = "LOCAL_FALLBACK"
            engine_metrics["notice"] = f"Exasol container at localhost:8563 is offline ({type(e).__name__}). Automatically executed on Local Deterministic Engine."
    else:
        local_engine = LocalFallbackReconciler()
        await emit_event("STATUS_TRANSITION", {"stage": "RECONCILIATION_RUNNING", "message": "Executing deterministic SQL on local fallback engine..."})
        results, engine_metrics = local_engine.reconcile(
            pkg.gateway_records,
            pkg.bank_records,
            pkg.ground_truth,
            settlement_delay_threshold_hours=req.settlement_delay_threshold_hours
        )

    global_audit_store.record_event(
        run_id, req.scenario_id, "RECONCILIATION_COMPLETED", "SUCCESS", engine_metrics["engine"],
        {"results_count": len(results), "timings_ms": engine_metrics["timings_ms"]}
    )
    await emit_event("STATUS_TRANSITION", {
        "stage": "RECONCILIATION_COMPLETED",
        "message": f"Reconciliation executed in {engine_metrics['timings_ms']['total_time_ms']}ms using {engine_metrics['engine']}",
        "metrics": engine_metrics
    })

    # Step 3: Run MiroFish Simulation
    await emit_event("STATUS_TRANSITION", {"stage": "AGENT_SIMULATION_RUNNING", "message": "Simulating participant perspectives (Customer, Merchant, Gateway)..."})
    miro_connector = MiroFishConnector()
    sim_events: List[SimulationEvent] = []
    gw_map = {r.transaction_id: r for r in pkg.gateway_records}
    bk_map = {r.transaction_id: r for r in pkg.bank_records}
    gt_map = {g.transaction_id: g for g in pkg.ground_truth}

    for res in results:
        evs, _ = miro_connector.run_simulation_for_case(
            result=res,
            ground_truth=gt_map.get(res.transaction_id),
            gw_record=gw_map.get(res.transaction_id),
            bk_record=bk_map.get(res.transaction_id),
            mode=req.simulation_mode
        )
        sim_events.extend(evs)

    global_audit_store.record_event(
        run_id, req.scenario_id, "SIMULATION_COMPLETED", "SUCCESS", "MIROFISH_CONNECTOR",
        {"events_count": len(sim_events)}
    )
    await emit_event("STATUS_TRANSITION", {
        "stage": "RESULTS_AVAILABLE",
        "message": "Reconciliation run and simulation completed successfully."
    })

    # Cache run in memory
    run_data = {
        "run_id": run_id,
        "scenario_id": req.scenario_id,
        "seed": req.seed,
        "dataset_package": pkg,
        "engine_metrics": engine_metrics,
        "results": results,
        "simulation_events": sim_events,
        "created_at_utc": datetime.now(timezone.utc).isoformat()
    }
    runs_cache[run_id] = run_data

    # Return summary
    summary_report = generate_run_summary_json(
        run_id=run_id,
        scenario_id=req.scenario_id,
        seed=req.seed,
        dataset_hash=pkg.dataset_hash,
        engine_metrics=engine_metrics,
        results=results,
        simulation_events=sim_events,
        audit_events=[e.model_dump() for e in global_audit_store.get_run_events(run_id)]
    )
    return summary_report


@app.get("/api/results/{run_id}")
def get_run_results(run_id: str):
    """Retrieve full cached run results."""
    if run_id not in runs_cache:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    data = runs_cache[run_id]
    return generate_run_summary_json(
        run_id=run_id,
        scenario_id=data["scenario_id"],
        seed=data["seed"],
        dataset_hash=data["dataset_package"].dataset_hash,
        engine_metrics=data["engine_metrics"],
        results=data["results"],
        simulation_events=data["simulation_events"],
        audit_events=[e.model_dump() for e in global_audit_store.get_run_events(run_id)]
    )


@app.get("/api/evidence/{run_id}/{transaction_id}")
def get_case_evidence(run_id: str, transaction_id: str):
    """Retrieve deep evidence comparison for a single transaction case."""
    if run_id not in runs_cache:
        raise HTTPException(status_code=404, detail="Run not found")
    data = runs_cache[run_id]
    pkg: SyntheticDatasetPackage = data["dataset_package"]
    res = next((r for r in data["results"] if r.transaction_id == transaction_id), None)
    if not res:
        raise HTTPException(status_code=404, detail="Transaction not found in run")

    gw_records = [r.model_dump() for r in pkg.gateway_records if r.transaction_id == transaction_id]
    bk_records = [r.model_dump() for r in pkg.bank_records if r.transaction_id == transaction_id]
    gt = next((g.model_dump() for g in pkg.ground_truth if g.transaction_id == transaction_id), None)
    sim_evs = [e.model_dump() for e in data["simulation_events"] if e.transaction_id == transaction_id]

    return {
        "run_id": run_id,
        "transaction_id": transaction_id,
        "reconciliation_result": res.model_dump(),
        "ground_truth": gt,
        "gateway_records": gw_records,
        "bank_records": bk_records,
        "simulation_events": sim_evs,
        "synthetic_disclosure": "Synthetic demo transaction",
        "simulation_disclosure": "AI-simulated scenario — not real customer feedback"
    }


@app.get("/api/export/csv/{run_id}")
def export_csv(run_id: str):
    """Download CSV reconciliation report."""
    if run_id not in runs_cache:
        raise HTTPException(status_code=404, detail="Run not found")
    data = runs_cache[run_id]
    csv_str = generate_reconciliation_csv(
        results=data["results"],
        run_id=run_id,
        scenario_id=data["scenario_id"],
        engine_name=data["engine_metrics"]["engine"]
    )
    return Response(
        content=csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=exasettle_reconciliation_{run_id}.csv"}
    )


@app.get("/api/export/json/{run_id}")
def export_json(run_id: str):
    """Download JSON run report."""
    if run_id not in runs_cache:
        raise HTTPException(status_code=404, detail="Run not found")
    data = runs_cache[run_id]
    summary = generate_run_summary_json(
        run_id=run_id,
        scenario_id=data["scenario_id"],
        seed=data["seed"],
        dataset_hash=data["dataset_package"].dataset_hash,
        engine_metrics=data["engine_metrics"],
        results=data["results"],
        simulation_events=data["simulation_events"],
        audit_events=[e.model_dump() for e in global_audit_store.get_run_events(run_id)]
    )
    return Response(
        content=json.dumps(summary, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=exasettle_summary_{run_id}.json"}
    )


@app.get("/api/events")
async def sse_events():
    """Server-Sent Events endpoint for real-time live run updates."""
    q: asyncio.Queue = asyncio.Queue()
    active_subscribers.append(q)

    async def event_generator():
        try:
            while True:
                msg = await q.get()
                yield f"data: {json.dumps(msg)}\n\n"
        except asyncio.CancelledError:
            active_subscribers.remove(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Mount static web frontend files
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
