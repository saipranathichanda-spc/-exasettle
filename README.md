# ExaSettle

> **Tagline**: Reconcile Faster. Explain Every Exception.  
> **Competition**: ExaThon India 2026 — The Exasol Open Build Challenge  
> **Track**: Track 01 — Money, Risk & Regulation  
> **Version**: 2.0 (Stage-Gated Architecture Prototype)  
> **Repository**: [https://github.com/saipranathichanda-spc/-exasettle](https://github.com/saipranathichanda-spc/-exasettle)  

---

> [!IMPORTANT]
> **SIMULATION & PROTOTYPE DISCLOSURE**  
> All customer identities, merchant names, payment gateway transactions, bank settlement records, and participant feedback in this demonstration are **strictly synthetic**.  
> Persistent simulation disclosure: **`AI-simulated scenario — not real customer feedback`**.  
> This prototype demonstrates explainable settlement reconciliation for financial operations. It does **not** process real payments, move real funds, or claim official Government of India accreditation or production regulatory readiness.

---

## 📑 Table of Contents

- [1. Overview & Operational Value](#1-overview--operational-value)
- [2. System Architecture & Truth Boundaries](#2-system-architecture--truth-boundaries)
- [3. Setup & Installation](#3-setup--installation)
  - [Prerequisites](#prerequisites)
  - [Backend Setup (Python)](#backend-setup-python)
  - [Frontend Setup (React + Tailwind + shadcn)](#frontend-setup-react--tailwind--shadcn)
  - [Environment Configuration](#environment-configuration)
- [4. Usage Guide](#4-usage-guide)
  - [Preflight Health Inspection](#preflight-health-inspection)
  - [Deterministic Batch CLI Run](#deterministic-batch-cli-run)
  - [Interactive Web Dashboard](#interactive-web-dashboard)
  - [Audit Exports (CSV & JSON)](#audit-exports-csv--json)
- [5. Run Guide & Deployment Instructions](#5-run-guide--deployment-instructions)
  - [Local Development Mode](#local-development-mode)
  - [Production Server Run](#production-server-run)
  - [Deploying Exasol Personal (Docker)](#deploying-exasol-personal-docker)
  - [Deploying MiroFish Multi-Agent Swarm (Optional)](#deploying-mirofish-multi-agent-swarm-optional)
- [6. Verification & Test Suite](#6-verification--test-suite)
- [7. Track 01 Submission Checklist](#7-track-01-submission-checklist)
- [8. Licensing & Third-Party Notices](#8-licensing--third-party-notices)

---

## 1. Overview & Operational Value

Merchants and finance operations teams spend hours manually cross-referencing payment gateway transaction feeds against bank settlement files. Discrepancies arise from missing records, settlement batch delays, MDR fee schedule variances, duplicate transmissions, and amount mismatches.

**ExaSettle** delivers an explainable, automated settlement-reconciliation engine combining high-speed analytical database queries with multi-perspective agent simulation:

1. **Logical Transaction Integrity**: Aggregates records at the logical transaction level using SQL Common Table Expressions (CTEs), capturing single-side duplicate anomalies without conflating row counts or overwriting records.
2. **Deterministic Database Classification**: Evaluates multi-tier exception logic in-database using ANSI SQL `CASE` statements across 8 standardized financial states (`MATCHED`, `AMOUNT_MISMATCH`, `FEE_VARIANCE_MDR`, `MISSING_IN_BANK`, `MISSING_IN_GATEWAY`, `DUPLICATE_SUBMISSION`, `DELAYED_SETTLEMENT`, `AMBIGUOUS_REVIEW`).
3. **Integer Fixed-Precision Math**: Enforces strict integer paise arithmetic (1 INR = 100 paise) preventing floating-point rounding discrepancies.
4. **Honest Multi-Perspective Simulation**: Evaluates how exception explanations are received by simulating Customer, Merchant, and Gateway actors with strict ground-truth isolation. Simulation is read-only and cannot alter financial truth.
5. **Interactive UI & Audit**: Dark-themed hero section, live execution stepper, financial KPI cards, deep evidence drill-down drawer, and tamper-evident SHA-256 CSV and JSON audit exports.

---

## 2. System Architecture & Truth Boundaries

```
                              [ Synthetic Dataset Generator ]
                                (Seed-driven, Known Answers)
                                              |
                                              v
                              [ Gateway / Bank Feeds ]
                               (Integer Paise Precision)
                                              |
                                              v
                          [ Primary: Exasol Personal Engine ]
                          [ Fallback: Local SQLite 3.50.4   ]
                            (CTE Aggregation + Outer Join)
                                              |
                                              v
                          [ Deterministic Reconciliation ]
                          (MATCHED, FEE_VARIANCE, etc.)
                                        /           \
                                       /             \
                                      v               v
                       [ Financial Truth & Evidence ]   [ Simulation Layer ]
                       - 1 result per logical txn       - TRUE_MIROFISH / DIRECT_LLM / PRERECORDED
                       - Explainable Priority (0-100)   - Read-only simulation layer
                       - Tamper-Evident SHA-256 Hash    - Persistent AI-Sim Label
                                      \               /
                                       \             /
                                        v           v
                          [ Live Interactive Web Dashboard ]
                          - Local Loopback Binding (127.0.0.1)
                          - Modern React 18 + Tailwind + shadcn
                          - Evidence Drill-down Drawer & Exports
```

---

## 3. Setup & Installation

### Prerequisites
- **Python**: Version 3.10 to 3.14 (tested on Python 3.14.7 on Windows and 3.10–3.12 on Linux CI).
- **Node.js**: Version 18+ (tested with Node v24.19.0 / npm 11.17.0).
- **Git**: With submodule support enabled.
- **Docker Desktop** (Optional, for live Exasol container): With WSL 2 enabled on Windows.

### Backend Setup (Python)
Clone repository with submodules:
```bash
git clone --recurse-submodules https://github.com/saipranathichanda-spc/-exasettle.git
cd -exasettle
```

Create and activate a virtual environment:
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

Install backend dependencies:
```bash
pip install -e .
# or:
pip install -r requirements.txt
```

### Frontend Setup (React + Tailwind + shadcn)
The frontend source code is located in `frontend/` and compiles into `exasettle/dashboard/static/`:
```bash
cd frontend
npm install
npm run build
cd ..
```

### Environment Configuration
Copy the template configuration file:
```bash
cp .env.example .env
```
Key settings in `.env`:
```ini
APP_HOST=127.0.0.1
APP_PORT=8000
EXASOL_HOST=localhost
EXASOL_PORT=8563
EXASOL_USER=sys
EXASOL_PASSWORD=exasol

# Optional: Google AI Studio Gemini API key for live Direct LLM persona roleplay
LLM_API_KEY=your_gemini_api_key_here
LLM_PROVIDER=google
LLM_MODEL=gemini-2.5-flash

# Optional: Zep Cloud key for MiroFish multi-agent memory graph
ZEP_API_KEY=
```

---

## 4. Usage Guide

### Preflight Health Inspection
Check connectivity to all services without leaking secrets:
```bash
python -m exasettle.cli preflight
```
Displays real-time statuses for:
- `ExaSettle API & Orchestrator`: `ONLINE`
- `Exasol Personal Analytical Database`: `ONLINE` or `OFFLINE` (with setup instructions)
- `MiroFish Swarm Intelligence Engine`: `ONLINE` or `BLOCKED` (with actionable instructions)
- `LLM Model Provider API`: `CONFIGURED` (masked credentials) or `NOT_CONFIGURED`
- `Zep Cloud Agent Memory Graph`: `CONFIGURED` or `NOT_CONFIGURED`

### Deterministic Batch CLI Run
Run reconciliation on the known-answer 8-pack test dataset:
```bash
python -m exasettle.cli run --seed 42 --scenario SCN_CORE_8PACK
```
Output features:
- Ingestion and query timing in milliseconds.
- Logical transaction counts (zero duplicate overwrites).
- Full classification distribution and priority triage scores.

### Interactive Web Dashboard
Launch the server on secure loopback:
```bash
python -m exasettle.cli server --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser:
1. **Hero Section**: Dark themed introduction with retro grid and quick action CTA.
2. **System Health Bar**: Live preflight polling with latency badges.
3. **Run Configuration**: Select scenario (`SCN_CORE_8PACK` or `SCN_EXPANDED_20`), seed, settlement threshold, and engine preference (`AUTO`, `FALLBACK`, `EXASOL`).
4. **Execution Stepper**: Real-time SSE status progression across 6 stages.
5. **Results Table**: Filter by Clean Matches, Exceptions, or High Priority.
6. **Evidence Drawer**: Click "Evidence" on any transaction to inspect raw feeds, timestamps, and SQL rules.
7. **Simulation Panel**: Persona dialogue for Customers, Merchants, and Gateway operators.

### Audit Exports (CSV & JSON)
From the dashboard or via API endpoints:
- **RFC-4180 CSV**: `GET /api/export/csv/{run_id}`
- **Full JSON Summary**: `GET /api/export/json/{run_id}`
Includes SHA-256 hash chains verifying dataset generation and query integrity.

---

## 5. Run Guide & Deployment Instructions

### Local Development Mode
To run backend with live reload and frontend with Vite hot-module-replacement (HMR):

1. **Terminal 1 (Backend API)**:
   ```bash
   uvicorn exasettle.dashboard.app:app --host 127.0.0.1 --port 8000 --reload
   ```
2. **Terminal 2 (Frontend Dev Server)**:
   ```bash
   cd frontend
   npm run dev
   ```
   Open **[http://localhost:3000](http://localhost:3000)**. Requests to `/api/*` are proxied to port 8000.

### Production Server Run
To run the self-contained production bundle:
```bash
cd frontend
npm run build
cd ..
python -m exasettle.cli server --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

### Deploying Exasol Personal (Docker)
To run the primary Exasol analytical database container:

1. **Ensure Virtualization & WSL 2 are active** (Windows):
   - Run `optionalfeatures` -> enable **Virtual Machine Platform** & **Windows Subsystem for Linux** -> Restart PC.
2. **Launch Exasol Personal container**:
   ```bash
   docker run -d --name exasoldb -p 8563:8563 exasol/docker-db:latest
   ```
3. **Verify connectivity**:
   - Run `python -m exasettle.cli preflight`. Exasol will report `ONLINE`.
   - On the web dashboard, select **Engine: Exasol Personal** to run queries on Exasol.

> **Rule 4 Compliance**: If Exasol is explicitly selected and unreachable, the system raises HTTP 503 rather than silently falling back.

### Deploying MiroFish Multi-Agent Swarm (Optional)
To run the full MiroFish multi-agent graph service:

1. Obtain a free API key at [https://app.getzep.com](https://app.getzep.com).
2. Set `ZEP_API_KEY=your_key` in `.env`.
3. Start the MiroFish microservice:
   ```bash
   python vendor/MiroFish/backend/run.py
   ```
   Listens on `http://localhost:5001`.

---

## 6. Verification & Test Suite

Run the full automated test suite:
```bash
pytest -v -rs
```

### Stage Gate Coverage (38 Tests)
- **G0 Baseline**: Worktree integrity and submodule pinned to revision `7657031ac01184afe2cb220f5ee3545573b5e843`.
- **G1 Preflight**: Secret masking, configuration validation, integer paise arithmetic.
- **G2 Generator**: Deterministic seed reproducibility, 8 planted known-answer cases, independent ground truth.
- **G3 Reconciliation**: CTE aggregation, 1 result per logical transaction, adversarial duplicate handling.
- **G4 MiroFish**: Section 10 prompt isolation, honest simulation mode separation (`TRUE_MIROFISH` vs. `DIRECT_LLM` vs. `PRERECORDED`).
- **G5 Dashboard**: Health endpoint, loopback binding (`127.0.0.1`), bounded SSE queues, explicit Exasol failure.
- **G6 Export Security**: Tamper-evident SHA-256 hash chains, CSV/JSON downloads, zero secret leaks.
- **G7 End-to-End**: 100% confusion matrix diagonal accuracy against known ground truth.
- **G8 Regression**: Zero credentials in tracked repository files, licensing notices, stability.

---

## 7. Track 01 Submission Checklist

| Requirement | Repository Evidence | Status |
|:---|:---|:---:|
| **Analytical Database Core** | `exasettle/engine/exasol_reconciler.py` & `reconciliation_core.py` (SQL CTE aggregation and CASE classification) | **Verified** |
| **No Silent Engine Fallback** | `exasettle/dashboard/app.py` & `cli.py` (EXASOL mode raises HTTP 503 on failure) | **Verified** |
| **Logical Transaction Integrity** | 1 result per logical transaction; duplicate rows tracked in `source_row_anomalies` | **Verified** |
| **Ground-Truth Isolation** | `exasettle/simulation/prompt_templates.py` (expected answers excluded from personas) | **Verified** |
| **Simulation Attribution** | Separation of `TRUE_MIROFISH`, `DIRECT_LLM_ROLEPLAY`, and `PRERECORDED` | **Verified** |
| **Security & Redaction** | Loopback binding (`127.0.0.1`), bounded SSE queues, zero secrets in tracked files | **Verified** |
| **Public Repository & Guide** | https://github.com/saipranathichanda-spc/-exasettle with `README.md` and `RUNBOOK.md` | **Verified** |
| **Pitch Deck** | Prepared for hackathon portal upload | *Ready* |
| **Demo Video (3 min)** | Walkthrough runbook in `RUNBOOK.md` ready for screen recording | *Ready* |

---

## 8. Licensing & Third-Party Notices

- **ExaSettle**: Licensed under the **MIT License**. See `LICENSE`.
- **MiroFish**: Pinned revision `7657031ac01184afe2cb220f5ee3545573b5e843`. Licensed under **GNU AGPL-3.0**. Retained in `vendor/MiroFish/LICENSE` and documented in `NOTICE.md`. ExaSettle communicates with MiroFish strictly across process and HTTP boundaries and does not modify or relicense upstream code.
- **PyExasol**: Official Python client by Exasol AG under MIT License.
