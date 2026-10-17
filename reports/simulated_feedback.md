# ExaSettle — Simulated Multi-Persona Feedback Loop Report

> **Competition**: ExaThon India 2026 — The Exasol Open Build Challenge  
> **Track**: Track 01 — Money, Risk & Regulation  
> **Simulation Attribution**: `AI-simulated, not real feedback` • **DIRECT_LLM_ROLEPLAY** (`gemini-3.8-flash` with MiroFish microservice active on port 5001)  
> **Protocol**: 6 Independent Adversarial & Operational Personas • 3+ Iterations per Persona • Round 1 Baseline -> Objection Resolution -> Round 2 Verification  

---

> [!IMPORTANT]
> **SIMULATION & PROTOTYPE DISCLOSURE**  
> All participant opinions, ratings, and commentary in this document are **strictly AI-simulated personas** evaluated against real system evidence. None of these personas represent real customers or real feedback.  
> Ground truth answer labels were **strictly isolated** and never revealed to any persona.

---

## 1. Executive Summary & Comparative Scores

![Simulated Feedback Scores](charts/simulated_feedback_scores.png)

### Round 1 vs. Round 2 Aggregate Score Comparison (1 to 5 Scale):
| Persona Role | Round 1 Clarity | Round 1 Trust | Round 1 Useful | **R1 Overall** | Round 2 Clarity | Round 2 Trust | Round 2 Useful | **R2 Overall** | **Net Gain** |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Skeptical Competitor** | 4.0 | 2.0 | 2.67 | **2.89** | 4.0 | 3.33 | 3.67 | **3.67** | **+0.78** |
| **Investigative Journalist** | 3.0 | 2.0 | 3.0 | **2.67** | 4.0 | 5.0 | 5.0 | **4.67** | **+2.00** |
| **Shop Owner (SMB)** | 2.0 | 3.0 | 2.67 | **2.56** | 4.0 | 5.0 | 5.0 | **4.67** | **+2.11** |
| **Finance Ops Manager** | 4.33 | 4.0 | 4.0 | **4.11** | 4.0 | 5.0 | 5.0 | **4.67** | **+0.56** |
| **Statutory Auditor** | 4.67 | 4.0 | 4.67 | **4.44** | 4.0 | 5.0 | 5.0 | **4.67** | **+0.23** |
| **Random Internet User** | 4.0 | 4.0 | 4.0 | **4.0** | 4.0 | 5.0 | 5.0 | **4.67** | **+0.67** |

---

## 2. Top 3 Objections Clustered in Round 1 & Fixes Implemented

### Objection 1: Manual Month-End Close (40.0h) Lacked Explicit Substantiation
- **Identified By**: *Skeptical Competitor* & *Investigative Journalist*
- **Concern**: Presenting a 40.0-hour manual baseline without clear labeling could lead evaluators to confuse an industry baseline assumption with a measured test run.
- **Fix Implemented**:
  1. Updated [`reports/accuracy.md`](accuracy.md) and [`README.md`](../README.md) with explicit **"(Industry Baseline Assumption)"** labels on all close-time charts and comparison tables.
  2. Documented standard multi-day spreadsheet reconciliation workflows across merchant aggregators as the formal basis for this assumption.

### Objection 2: Local Exasol Docker Container Offline Required Clearer Reproduction
- **Identified By**: *Random Internet User* & *Skeptical Competitor*
- **Concern**: With Exasol offline on `localhost:8563`, evaluators needed transparent verification that the fallback engine was active and exact commands to spin up the Exasol container.
- **Fix Implemented**:
  1. Documented `docker run -d --name exasoldb -p 8563:8563 exasol/docker-db:latest` in preflight output and `README.md`.
  2. Maintained strict Rule 4 compliance: explicit Exasol mode raises HTTP 503 rather than silently hiding failure.

### Objection 3: High-Priority Exceptions Needed Automated Webhook Escalation
- **Identified By**: *Finance Operations Manager* & *Statutory Auditor*
- **Concern**: Urgent exceptions like `MISSING_IN_BANK` (Priority 95) or `MISSING_IN_GATEWAY` (Priority 92) should not merely sit in a dashboard table; enterprise ops require an automated dispatch schema.
- **Fix Implemented**:
  1. Added `WebhookAlertPayload` in [`exasettle/core/models.py`](../exasettle/core/models.py) with structured JSON alert schemas for acquiring bank escalations.
  2. Added emergency threshold evaluation in [`exasettle/engine/reconciliation_core.py`](../exasettle/engine/reconciliation_core.py) triggering alert payloads for all exceptions with Priority $\ge 70$.

---

## 3. Individual Persona Perspectives (Sample Excerpts)

### 1. Skeptical Competitor
> *"The fixed-precision paise math and 0 paise daily balance are mathematically sound and eliminate float rounding vulnerabilities. The explicit labeling of the 40-hour month-end close as an industry baseline assumption removes our initial skepticism regarding fabricated baselines."*

### 2. Statutory Auditor
> *"The SHA-256 parent-child cryptographic hash chain between dataset generation and query output satisfies tamper-evident audit trail requirements under modern regulatory guidelines. The 0 paise identity check across 30 days is verifiable and reproducible."*

### 3. Finance Operations Manager
> *"Having pre-computed reason codes, SLA windows, and assigned team owners directly attached to every single exception eliminates hours of daily manual assignment triage. The webhook dispatch format for high-priority exceptions provides the missing link to our ticketing system."*

### 4. Shop Owner
> *"I can see exactly why my payment was delayed or why an extra fee was taken without needing to understand technical database terms. The recommended actions tell me exactly what my payment partner is doing to fix it."*

---

## 4. Methodological Transparency

- **Simulation Mode**: Strictly `DIRECT_LLM_ROLEPLAY` via `gemini-3.8-flash` with OpenAI-compatible API bindings.
- **Ground Truth Isolation**: Personas were never provided planted ground-truth labels.
- **Empirical Execution**: All 36 simulated evaluation runs (18 in Round 1, 18 in Round 2) were executed via script `scripts/run_simulated_feedback_loop.py`.
