# ExaSettle

> **Tagline**: Reconcile Faster. Explain Every Exception.  
> **Competition**: ExaThon India 2026 — The Exasol Open Build Challenge  
> **Track**: Track 01 — Money, Risk & Regulation  
> **Version**: 2.0  

---

> [!IMPORTANT]
> **SIMULATION & PROTOTYPE DISCLOSURE**  
> All people, payment events, merchant records, gateway events, and participant feedback in this demonstration are **strictly synthetic**.  
> Persistent label: **`AI-simulated scenario — not real customer feedback`**.  
> This is a truthful demo of an explainable reconciliation prototype, not an actual payment connection, a government-approved service, or a production financial system.

---

## ⚡ Overview

Merchants and finance operations teams compare payment gateway records with bank settlement records. Discrepancies arise from missing records, settlement delays, MDR fee variances, duplicate submissions, and amount mismatches. Manual investigation is slow and error-prone.

**ExaSettle** delivers an explainable settlement-reconciliation workflow:
1. **Analytical SQL Engine**: Executes deterministic reconciliation using CTEs, `ROW_NUMBER()`, and `FULL OUTER JOIN` on **Exasol Personal** (with a local fallback engine).
2. **Fixed-Precision Math**: Enforces integer paise arithmetic (1 INR = 100 paise) preventing IEEE-754 floating-point errors.
3. **MiroFish Agent Simulation**: Instantiates synthetic role perspectives for Customer, Merchant, and Gateway actors to explore how exception explanations are experienced.
4. **Strict Truth Boundaries**: Agent opinions **cannot alter** financial classifications, ledger rows, or ground truth.
5. **Interactive Dashboard & Audit**: Live status progression, KPI metrics, deep evidence drill-down drawer, visual distribution charts, and exportable CSV/JSON audit packages.

---

## 🏛️ Architecture & Truth Boundaries

```
                              [ Synthetic Dataset Generator ]
                               (Seed-driven, Known Answers)
                                             |
                                             v
                              [ Gateway / Bank Records ]
                               (Integer Paise Precision)
                                             |
                                             v
                         [ Primary: Exasol Personal Engine ]
                         [ Fallback: Local SQLite 3.50.4   ]
                           (CTE + Window + Full Outer Join)
                                             |
                                             v
                         [ Deterministic Reconciliation ]
                         (MATCHED, FEE_VARIANCE, etc.)
                                       /           \
                                      /             \
                                     v               v
                      [ Financial Truth & Evidence ]   [ MiroFish Swarm Simulation ]
                      - 100% Ground Truth Accuracy     - Customer / Merchant / Gateway
                      - Explainable Priority (0-100)   - Read-only simulation layer
                      - SHA-256 Tamper-Evident Hash    - Persistent AI-Sim Label
                                     \               /
                                      \             /
                                       v           v
                         [ Live Interactive Web Dashboard ]
                         - Real-time SSE Execution Stepper
                         - Evidence Drill-down Drawer
                         - One-Click CSV / JSON Exporters
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.11+ (Python 3.14 recommended)
- `pip install -r requirements.txt` (or install dependencies: `fastapi`, `uvicorn`, `pyexasol`, `pydantic`, `pytest`)

### 2. Run Preflight Health Check
Verify dependency statuses without leaking credentials:
```bash
python -m exasettle.cli preflight
```

### 3. Run Reconciliation via CLI
Execute a deterministic reconciliation run on the core 8-pack known-answer testpack:
```bash
python -m exasettle.cli run --seed 42
```

### 4. Launch Interactive Live Dashboard
Launch the web dashboard on port 8000:
```bash
python -m exasettle.cli server --host 0.0.0.0 --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 🧪 Testing & Verification

Run the comprehensive stage-gate verification suite:
```bash
pytest -v -rs
```

All 30 tests pass across all MVP gates (G0 to G8):
- **G0**: Repository & Dependency Discovery
- **G1**: Architecture, Preflight & Credential Redaction
- **G2**: Synthetic Data & 8 Planted Known Answers
- **G3**: Exasol Reconciliation Core & Fallback Engine
- **G4**: MiroFish Prompt Conformance & Strict Truth Boundary
- **G5**: Live Dashboard API & Real-Time Events
- **G6**: Tamper-Evident Export & Security Audit
- **G7**: End-to-End Demo Journey & Confusion Matrix
- **G8**: Final Regression, License & Code Cleanliness

---

## ⏱️ 3-Minute Hackathon Demo Script

| Time | Stage | Screen Action | Talking Points |
| :---: | :--- | :--- | :--- |
| **0:00 - 0:20** | **The Problem** | Show landing page & disclosure banner | *"Finance and merchant operations lose hundreds of hours reconciling gateway feeds with bank settlement files. Missing legs, MDR fee disputes, and settlement delays slow down closing."* |
| **0:20 - 0:40** | **Preflight & Scenario** | Show Health Badges & Seed Selector | *"Here is our dependency preflight. ExaSettle operates on synthetic data with deterministic seed 42. It plants all 8 known payment exceptions with independent ground truth."* |
| **0:40 - 1:10** | **Execution & Speed** | Click 'Start Reconciliation Run', watch Stepper | *"We start the run. In under 2 milliseconds, our SQL CTE with `ROW_NUMBER()` and `FULL OUTER JOIN` processes both feeds, captures unmatched rows from both sides, and computes an explainable 0-100 triage score."* |
| **1:10 - 2:00** | **Evidence Drill-down** | Click 'Evidence' on `TXN_SYN_103` (Amount Mismatch) | *"Drilling into TXN 103: Gateway shows ₹3,500.00, Bank settled ₹3,000.00. The drawer shows side-by-side feeds, applied SQL rule, exact ₹500.00 variance, and mathematical priority factor breakdown."* |
| **2:00 - 2:30** | **Simulation Separation** | Scroll to MiroFish Simulation Panel | *"Notice the distinct MiroFish panel with the persistent notice: 'AI-simulated scenario — not real customer feedback'. Our tests prove agent dialogue can never mutate financial truth."* |
| **2:30 - 3:00** | **Charts, Export & Limits** | Click 'Download CSV' and show report | *"We export tamper-evident CSV and JSON reports with SHA-256 hashes. Limits: Exasol Personal is a single-user demo edition, data is synthetic, and no real money was moved."* |

---

## 📜 Licensing & Notices

- **ExaSettle**: Licensed under the **MIT License**. See `LICENSE`.
- **MiroFish**: Pinned commit `7657031ac01184afe2cb220f5ee3545573b5e843`. Licensed under **GNU AGPL-3.0**. Retained in `vendor/MiroFish/LICENSE` and documented in `NOTICE.md`. ExaSettle code interfaces with MiroFish across process boundaries and does not relicense MiroFish code.
- **PyExasol**: Official Python client by Exasol AG under MIT License.
