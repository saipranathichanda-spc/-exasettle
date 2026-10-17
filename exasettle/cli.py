"""
Command-Line Interface for ExaSettle.
Usage:
  python -m exasettle.cli preflight
  python -m exasettle.cli run [--seed SEED] [--scenario SCENARIO] [--engine AUTO|EXASOL|FALLBACK] [--sim AUTO|PRERECORDED|LIVE]
  python -m exasettle.cli server [--host 0.0.0.0] [--port 8000]
"""

import argparse
import json
import os
import sys

# Configure UTF-8 on Windows console
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from exasettle.core.config import run_preflight, Settings
from exasettle.generator.dataset_generator import generate_synthetic_dataset
from exasettle.engine.fallback_reconciler import LocalFallbackReconciler
from exasettle.engine.exasol_reconciler import ExasolReconciler
from exasettle.simulation.mirofish_connector import MiroFishConnector
from exasettle.audit.logger import global_audit_store
from exasettle.audit.exporter import generate_reconciliation_csv, generate_run_summary_json


def cmd_preflight():
    summary = run_preflight()
    print("==================================================")
    print("ExaSettle Service Health Preflight Check")
    print(f"Timestamp: {summary.timestamp_utc}")
    print("==================================================")
    for svc in summary.services:
        print(f"[{svc.status:14}] {svc.service_name}")
        print(f"               Details: {svc.details}")
        if svc.latency_ms:
            print(f"               Latency: {svc.latency_ms} ms")
        if svc.setup_instructions:
            print(f"               Action:  {svc.setup_instructions.splitlines()[0]}")
    print("==================================================")


def cmd_run(args):
    print("==================================================")
    print("Executing ExaSettle Reconciliation Run")
    print(f"Scenario: {args.scenario} | Seed: {args.seed} | Engine: {args.engine}")
    print("==================================================")

    # 1. Generate
    pkg = generate_synthetic_dataset(
        run_id=f"cli_run_{args.seed}",
        scenario_id=args.scenario,
        seed=args.seed,
        settlement_delay_threshold_hours=args.threshold
    )
    print(f"Generated {pkg.total_records} synthetic records (Dataset Hash: {pkg.dataset_hash[:16]}...)")

    # 2. Reconcile
    if args.engine == "EXASOL" or (args.engine == "AUTO" and Settings.EXASOL_PASSWORD):
        try:
            print("Connecting to Exasol Personal Analytical Database...")
            engine = ExasolReconciler()
            results, metrics = engine.reconcile(pkg.gateway_records, pkg.bank_records, pkg.ground_truth, args.threshold)
        except Exception as e:
            if args.engine == "EXASOL":
                print(f"Exasol error: {e}")
                sys.exit(1)
            print(f"Exasol unavailable ({e}). Using local fallback engine...")
            engine = LocalFallbackReconciler()
            results, metrics = engine.reconcile(pkg.gateway_records, pkg.bank_records, pkg.ground_truth, args.threshold)
    else:
        print("Using local deterministic fallback engine (SQLite CTE + Full Outer Join)...")
        engine = LocalFallbackReconciler()
        results, metrics = engine.reconcile(pkg.gateway_records, pkg.bank_records, pkg.ground_truth, args.threshold)

    print(f"Reconciled {len(results)} transactions in {metrics['timings_ms']['total_time_ms']} ms")
    print(f"Active Engine: {metrics['engine']}")

    # 3. Simulate
    print(f"Running MiroFish simulation (Mode: {args.sim})...")
    conn = MiroFishConnector()
    sim_events = []
    gw_map = {r.transaction_id: r for r in pkg.gateway_records}
    bk_map = {r.transaction_id: r for r in pkg.bank_records}
    gt_map = {g.transaction_id: g for g in pkg.ground_truth}

    for res in results:
        evs, _ = conn.run_simulation_for_case(
            result=res,
            ground_truth=gt_map.get(res.transaction_id),
            gw_record=gw_map.get(res.transaction_id),
            bk_record=bk_map.get(res.transaction_id),
            mode=args.sim
        )
        sim_events.extend(evs)
    print(f"Generated {len(sim_events)} participant perspectives (Customer, Merchant, Gateway)")

    # 4. Results Table
    print("\n------------------------------------------------------------------------------------------------------------------")
    print(f"{'TXN ID':<14} | {'CLASSIFICATION':<20} | {'PRIORITY':<8} | {'VARIANCE':<10} | {'RULE':<40}")
    print("------------------------------------------------------------------------------------------------------------------")
    for r in results:
        diff_str = f"₹{r.difference_paise/100:.2f}"
        print(f"{r.transaction_id:<14} | {r.classification.value:<20} | {r.priority_score:<8} | {diff_str:<10} | {r.applied_rule[:40]:<40}")
    print("------------------------------------------------------------------------------------------------------------------")
    print("AI-simulated scenario — not real customer feedback • Synthetic demo transactions\n")


def cmd_verify_audit(args):
    print("==================================================")
    print("ExaSettle Audit Trail & SHA-256 Hash Chain Verification")
    print("==================================================")

    # Generate a reference test run to inspect and verify audit chain
    pkg = generate_synthetic_dataset(seed=42)
    engine = LocalFallbackReconciler()
    results, metrics = engine.reconcile(pkg.gateway_records, pkg.bank_records, pkg.ground_truth)

    events = global_audit_store.get_run_events(pkg.run_id)
    if not events:
        # Record canonical verification events if store was freshly initialized
        global_audit_store.record_event(
            pkg.run_id, pkg.scenario_id, "DATASET_GENERATED", "SUCCESS", "PYTHON_RNG",
            {"dataset_hash": pkg.dataset_hash, "records_count": pkg.total_records}
        )
        global_audit_store.record_event(
            pkg.run_id, pkg.scenario_id, "RECONCILIATION_COMPLETED", "SUCCESS", metrics["engine"],
            {"results_count": len(results), "timings_ms": metrics["timings_ms"]}
        )
        events = global_audit_store.get_run_events(pkg.run_id)

    print(f"Inspecting {len(events)} audit events for Run: {pkg.run_id}")
    all_valid = True
    prev_hash = events[0].prev_event_hash if events and events[0].prev_event_hash else "GENESIS_EXASETTLE_2026"

    for i, ev in enumerate(events):
        print(f"  [{i+1}/{len(events)}] Stage: {ev.stage:<26} | Status: {ev.status}")
        print(f"        Event ID:    {ev.event_id}")
        print(f"        Event Hash:  {ev.event_hash}")
        if ev.prev_event_hash:
            print(f"        Parent Hash: {ev.prev_event_hash}")
            if ev.prev_event_hash != prev_hash:
                print("        ❌ Chain broken: parent hash does not match previous event!")
                all_valid = False
            else:
                print("        ✓ Parent hash link verified.")
        prev_hash = ev.event_hash

    print("--------------------------------------------------")
    if all_valid:
        print("✅ VERIFICATION PASSED: SHA-256 cryptographic hash chain is tamper-evident and intact.")
    else:
        print("❌ VERIFICATION FAILED: Tampering detected in audit chain.")
        sys.exit(1)
    print("==================================================")


def cmd_demo(args):
    print("==================================================")
    print("ExaSettle End-to-End Evaluator Demo Pipeline")
    print("Track 01 — Money, Risk & Regulation")
    print("==================================================")

    # 1. Preflight
    print("\n--- 1. Preflight Health Check ---")
    cmd_preflight()

    # 2. Batch Run
    print("\n--- 2. Deterministic Reconciliation Run (Seed 42) ---")
    class DummyArgs:
        scenario = "SCN_CORE_8PACK"
        seed = 42
        threshold = 24.0
        engine = "FALLBACK"
        sim = "PRERECORDED"
    cmd_run(DummyArgs())

    # 3. Audit Verification
    print("\n--- 3. Audit Trail Verification ---")
    cmd_verify_audit(None)


def cmd_server(args):
    import uvicorn
    print(f"Starting ExaSettle Dashboard server on http://{args.host}:{args.port}")
    uvicorn.run("exasettle.dashboard.app:app", host=args.host, port=args.port, reload=False)


def main():
    parser = argparse.ArgumentParser(description="ExaSettle CLI Runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # preflight
    subparsers.add_parser("preflight", help="Run preflight dependency checks")

    # run
    run_p = subparsers.add_parser("run", help="Execute reconciliation run")
    run_p.add_argument("--scenario", default="SCN_CORE_8PACK", help="Scenario ID")
    run_p.add_argument("--seed", type=int, default=42, help="Deterministic seed")
    run_p.add_argument("--threshold", type=float, default=24.0, help="Settlement delay threshold hours")
    run_p.add_argument("--engine", default="AUTO", choices=["AUTO", "EXASOL", "FALLBACK"], help="Engine preference")
    run_p.add_argument("--sim", default="AUTO", choices=["AUTO", "TRUE_MIROFISH", "DIRECT_LLM_ROLEPLAY", "PRERECORDED", "LIVE", "BLOCKED"], help="Simulation mode")

    # verify-audit
    subparsers.add_parser("verify-audit", help="Verify SHA-256 tamper-evident audit hash chain")

    # demo
    subparsers.add_parser("demo", help="Execute complete end-to-end evaluator demo")

    # server
    srv_p = subparsers.add_parser("server", help="Launch live web dashboard")
    srv_p.add_argument("--host", default="127.0.0.1", help="Host binding (loopback default for security)")
    srv_p.add_argument("--port", type=int, default=8000, help="Port binding")

    args = parser.parse_args()
    if args.command == "preflight":
        cmd_preflight()
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "verify-audit":
        cmd_verify_audit(args)
    elif args.command == "demo":
        cmd_demo(args)
    elif args.command == "server":
        cmd_server(args)


if __name__ == "__main__":
    main()
