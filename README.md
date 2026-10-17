# ExaSettle

> **Tagline**: Reconcile Faster. Explain Every Exception.  
> **Competition**: ExaThon India 2026 — The Exasol Open Build Challenge  
> **Track**: Track 01 — Money, Risk & Regulation  
> **Version**: 2.0 (Stage-Gated Architecture Prototype)  

---

> [!IMPORTANT]
> **SIMULATION & PROTOTYPE DISCLOSURE**  
> All customer identities, merchant names, gateway events, bank records, and participant feedback in this demonstration are **strictly synthetic**.  
> Persistent simulation disclosure: **`AI-simulated scenario — not real customer feedback`**.  
> This prototype demonstrates explainable settlement reconciliation for financial operations. It does **not** process real payments, move real funds, or claim official Government of India accreditation or production readiness.

---

## ⚡ Problem & Operational Value

Merchants and finance operations teams spend hours manually cross-referencing payment gateway transaction feeds against bank settlement files. Discrepancies arise from missing records, settlement delays, MDR fee schedule variances, duplicate transmissions, and amount mismatches.

**ExaSettle** provides an explainable, automated reconciliation workflow:
1. **Logical Transaction Integrity**: Aggregates records at the logical transaction level using SQL Common Table Expressions (CTEs), capturing single-side duplicate anomalies without conflating row counts or overwriting records.
2. **Deterministic Database Classification**: Evaluates multi-tier exception logic in-database using ANSI SQL `CASE` statements across 8 standardized financial states.
3. **Fixed-Precision Math**: Enforces strict integer paise arithmetic (1 INR = 100 paise) preventing floating-point rounding errors.
4. **Honest Multi-Perspective Simulation**: Explores how exception explanations are received by simulating Customer, Merchant, and Gateway actors with strict ground-truth isolation. Simulation is read-only and cannot alter financial truth.
5. **Interactive Dashboard & Audit**: Live status progression, financial KPI cards, deep evidence drill-down drawer, and tamper-evident SHA-256 CSV and JSON audit exports.

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
                         - Evidence Drill-down Drawer
                         - One-Click CSV / JSON Exporters
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.14.7 on Windows and Python 3.10–3.12 in CI).
- Install dependencies:
  ```bash
  pip install -e '.[dev]'
  # or:
  pip install -r requirements.txt
  ```

### 2. Run Preflight Health Check
Inspect service connectivity without secret leakage:
```bash
python -m exasettle.cli preflight
```

### 3. Run Reconciliation via CLI
Execute a deterministic reconciliation run on the core 8-pack known-answer testpack:
```bash
python -m exasettle.cli run --seed 42
```

### 4. Launch Interactive Live Dashboard
Launch the web dashboard on secure loopback:
```bash
python -m exasettle.cli server --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your web browser.

---

## ⚙️ Engine Modes & Simulation Modes

### Analytical Engine Modes
- **`AUTO`**: Automatically checks for a live Exasol Personal database at `EXASOL_HOST:EXASOL_PORT`. If online, runs analytical CTE queries in Exasol; if offline, transparently falls back to the deterministic local SQLite engine labeled as `LOCAL_FALLBACK`.
- **`EXASOL`**: Exclusively uses Exasol Personal. If Exasol is unreachable or offline, the operation **fails visibly with HTTP 503** (silent fallback to SQLite is strictly forbidden under working rules).
- **`FALLBACK`**: Explicitly runs the local deterministic SQLite CTE engine.

### Simulation Modes
- **`PRERECORDED`**: Offline high-fidelity dialogue generated from Section 10 prompts, clearly labeled `PRERECORDED`.
- **`DIRECT_LLM_ROLEPLAY`**: Directly queries configured model provider (OpenAI / Google AI Studio Gemini), labeled as direct LLM role-play (never called MiroFish).
- **`TRUE_MIROFISH`**: Connects to the pinned MiroFish backend microservice via documented REST API (`/api/simulation/create`). Reports `BLOCKED` if microservice is offline.

---

## 🧪 Testing & Verification

Run the full automated test suite:
```bash
pytest -v -rs
```

**Results**: 37 passed, 1 skipped (`test_exasol_personal_integration_or_explicit_skip`: Exasol container offline), 0 failed across all stage gates G0–G8:
- **G0**: Repository baseline & pinned MiroFish submodule (`7657031ac01184afe2cb220f5ee3545573b5e843`).
- **G1**: Clean installation, dependency declarations, and CI workflow.
- **G2**: Synthetic generator reproducibility and 8 planted known answers.
- **G3**: Reconciliation core, logical transaction aggregation, and adversarial cases.
- **G4**: Section 10 prompt template, ground-truth isolation, and honest simulation labels.
- **G5**: Dashboard health, loopback binding, bounded SSE queues, and explicit Exasol failure.
- **G6**: Tamper-evident SHA-256 hash chains, CSV/JSON exports, zero credential leakage.
- **G7**: Full end-to-end demo journey and 100% confusion matrix validation.
- **G8**: Security audit, licensing boundaries, and regression stability.

---

## 📋 Track 01 Submission Checklist

| Requirement | Repository Evidence | Status |
|:---|:---|:---:|
| **Analytical Database Core** | `exasettle/engine/exasol_reconciler.py` & `reconciliation_core.py` (SQL CTE aggregation and CASE classification) | **Verified** |
| **No Silent Engine Fallback** | `exasettle/dashboard/app.py` & `cli.py` (EXASOL mode raises HTTP 503 on failure) | **Verified** |
| **Logical Transaction Integrity** | 1 result per logical transaction; duplicate rows tracked in `source_row_anomalies` | **Verified** |
| **Ground-Truth Isolation** | `exasettle/simulation/prompt_templates.py` (expected answers excluded from personas) | **Verified** |
| **Simulation Attribution** | Separation of `TRUE_MIROFISH`, `DIRECT_LLM_ROLEPLAY`, and `PRERECORDED` | **Verified** |
| **Security & Redaction** | Loopback binding (`127.0.0.1`), bounded SSE queues, zero secrets in tracked files | **Verified** |
| **Public Repository & Guide** | https://github.com/saipranathichanda-spc/-exasettle with `README.md` and `RUNBOOK.md` | **Verified** |
| **Pitch Deck** | To be submitted separately by team prior to deadline | *Pending Submission* |
| **Demo Video (3 min)** | Walkthrough runbook documented in `RUNBOOK.md` and `README.md` | *Ready for Recording* |

---

## 📜 Licensing & Third-Party Notices

- **ExaSettle**: Licensed under the **MIT License**. See `LICENSE`.
- **MiroFish**: Pinned revision `7657031ac01184afe2cb220f5ee3545573b5e843`. Licensed under **GNU AGPL-3.0**. Retained in `vendor/MiroFish/LICENSE` and documented in `NOTICE.md`. ExaSettle communicates with MiroFish over process/API boundaries and does not relicense MiroFish code.
- **PyExasol**: Official Python client by Exasol AG under MIT License.
