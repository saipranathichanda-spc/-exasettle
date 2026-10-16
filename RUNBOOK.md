# ExaSettle — Judge & Operator Runbook

**Competition**: ExaThon India 2026 — The Exasol Open Build Challenge  
**Track**: Track 01 — Money, Risk & Regulation  

---

## 🎯 Purpose of this Runbook

This document provides step-by-step instructions for hackathon judges and operators to inspect, execute, and verify **ExaSettle** end-to-end.

---

## 🛠️ Step 1: Environment & Preflight Check

Run the preflight health check to inspect service connectivity and ensure credentials are never leaked:

```bash
python -m exasettle.cli preflight
```

**Expected Output**:
- Displays real status for:
  - `ExaSettle API & Orchestrator`: `ONLINE`
  - `Exasol Personal Analytical Database`: `ONLINE` (if Docker container is running) or `NOT_CONFIGURED` / `OFFLINE` (with exact setup instructions)
  - `MiroFish Swarm Intelligence Engine`: `ONLINE` (if microservice running) or `BLOCKED` (with actionable instructions)
  - `LLM Model Provider API`: `CONFIGURED` or `NOT_CONFIGURED`
  - `Zep Cloud Agent Memory Graph`: `CONFIGURED` or `NOT_CONFIGURED`

---

## ⚡ Step 2: Deterministic Batch Execution (CLI)

Run a deterministic reconciliation run directly from the command line:

```bash
python -m exasettle.cli run --seed 42
```

**What to Observe**:
1. **Deterministic Dataset Generation**: 15 records generated with SHA-256 hash `27a14b7a703b...`
2. **Reconciliation Speed**: Sub-2ms execution using CTEs with `ROW_NUMBER()` and `FULL OUTER JOIN`.
3. **Planted Exception Coverage**:
   - `TXN_SYN_101`: `MATCHED` (Priority 0)
   - `TXN_SYN_102`: `FEE_VARIANCE_MDR` (Gateway ₹40 vs Bank ₹55)
   - `TXN_SYN_103`: `AMOUNT_MISMATCH` (Gateway ₹3,500 vs Bank ₹3,000)
   - `TXN_SYN_104`: `MISSING_IN_BANK` (Gateway captured, bank row absent)
   - `TXN_SYN_105`: `MISSING_IN_GATEWAY` (Bank credit, gateway row absent)
   - `TXN_SYN_106`: `DUPLICATE` (Duplicate submission)
   - `TXN_SYN_107`: `SETTLEMENT_DELAY` (72h elapsed vs 24h threshold)
   - `TXN_SYN_108`: `AMBIGUOUS_REVIEW` (Gateway reversed vs Bank settled)
4. **MiroFish Simulation**: 27 participant perspectives created with persistent disclosure: `AI-simulated scenario — not real customer feedback`.

---

## 🖥️ Step 3: Interactive Live Dashboard & Visual Walkthrough

Start the dashboard server:

```bash
python -m exasettle.cli server --host 0.0.0.0 --port 8000
```

1. Open your web browser to **[http://localhost:8000](http://localhost:8000)**.
2. Note the persistent top disclosure banner: **`AI-simulated scenario — not real customer feedback`**.
3. Click **"Check Health"** to view real-time latency and status of all dependencies.
4. Click **"▶️ Start Reconciliation Run"**:
   - Watch the live execution stepper transition across all 6 stages.
   - Inspect the KPI summary cards: Clean Matches, Exceptions, and Total Amount at Issue (with exact Indian numbering and paise precision).
5. Click **"Evidence"** on any transaction (e.g. `TXN_SYN_103`):
   - Inspect the deep evidence drawer showing side-by-side Gateway and Bank records.
   - Review the applied SQL rule and the mathematical factor breakdown of the operational triage score.
6. Scroll down to the **MiroFish Swarm Simulation Panel**:
   - View separate feedback cards for Customer, Merchant, and Gateway actors.
   - Observe how agent feedback is kept distinct from financial records.
7. Click **"Download CSV"** and **"Download JSON Report"** to inspect export artifacts containing tamper-evident SHA-256 hashes.

---

## 🧪 Step 4: Automated Verification Test Suite

Run the full automated test suite covering all gates:

```bash
pytest -v -rs
```

**Verification Results**:
- 30 Passed tests.
- 1 Honest Skip (`test_exasol_personal_integration_or_explicit_skip`) explaining that Exasol Personal is offline without faking mocks as a pass.
- Zero failures. Zero secret leaks.

---

## 🔒 Security & Data Boundaries

- **Synthetic Only**: No real customer, bank, or citizen data is used.
- **Credential Protection**: `.env` is ignored by git; secrets are strictly masked in logs, API outputs, and UI.
- **Licensing Notice**: ExaSettle code is MIT. MiroFish code is retained under GNU AGPL-3.0 in `vendor/MiroFish/LICENSE`.
