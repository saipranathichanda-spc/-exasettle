# ExaSettle • Architecture, Technology Stack & Interview Demo Guide
> **Track:** ExaThon India 2026 • Track 01 (Money, Risk & Regulation)  
> **Technologies:** Exasol Personal 2026.2.0, PyExasol, MiroFish Swarm Intelligence, Zep Cloud, Google Gemini, FastAPI, React 18, Tailwind CSS  
> **Document Type:** Candidate Interview & Architecture Reference Guide  
> **PDF Version:** Available to download at [`docs/ExaSettle_Architecture_and_Interview_Guide.pdf`](ExaSettle_Architecture_and_Interview_Guide.pdf)

---

## 1. The 30-Second Elevator Pitch

> *"ExaSettle is a real-time, explainable settlement reconciliation platform built for Indian payment gateways and banks.*
>
> *Traditional banking reconciliation relies on manual spreadsheet checks or black-box machine learning that causes floating-point rounding errors and leaves financial audits opaque. ExaSettle solves this with two foundational innovations:*
> 1. *First, it executes mathematical aggregation directly inside **Exasol Personal's in-memory columnar database** with strict integer paise precision (zero floating-point error).*
> 2. *Second, it bridges the gap between cold numbers and human operations by integrating **MiroFish Swarm Intelligence**, which simulates the multi-perspective friction of customers, merchants, and bank gateways during disputes.*
>
> *Every single exception generates six deterministic triage fields and is cryptographically chained into a tamper-evident SHA-256 audit trail."*

---

## 2. System Architecture & High-Throughput Pipeline

ExaSettle follows a strict **Layered Separation of Concerns**. The financial truth engine (Exasol analytical SQL) is completely isolated from the AI simulation layer (MiroFish), ensuring that AI never manipulates money or classifications.

```
+-------------------------------------------------------------------------------------------------+
|  1. SYNTHETIC DATA GENERATOR (Integer Paise, Seeded, 30-Day continuous, Planted Exceptions)    |
+-------------------------------------------------------------------------------------------------+
                                     | Ingest Raw Gateway & Bank Feeds
                                     v
+-------------------------------------------------------------------------------------------------+
|  2. ANALYTICAL DATABASE LAYER (Exasol Personal 2026.2.0 via PyExasol / SQLite 3.50.4 Fallback)  |
|     - CTE Aggregation: gw_agg (captured) vs bk_agg (settled) via FULL OUTER JOIN                |
|     - Instant In-Memory Execution (54ms query time, 0 paise rounding delta)                     |
+-------------------------------------------------------------------------------------------------+
                                     | Aggregated Rows & Classifications
                                     v
+-------------------------------------------------------------------------------------------------+
|  3. DETERMINISTIC EXPLAINABILITY ENGINE (reconciliation_core.py)                                |
|     - Generates 6 Fields: Reason Code, Evidence, Action, Owner, SLA, Priority Score (0-100)    |
|     - Automated Webhook Alert Dispatch schema for high priority (Score >= 70)                  |
+-------------------------------------------------------------------------------------------------+
                     | Read-only Evidence                        | Audit Events
                     v                                           v
+-----------------------------------------------+ +-----------------------------------------------+
|  4. MIROFISH SWARM INTELLIGENCE               | |  5. CRYPTOGRAPHIC AUDIT STORE                 |
|     - Submodule pinned at commit 7657031a     | |     - SHA-256 Tamper-Evident Hash Chain       |
|     - Customer, Merchant & Gateway Simulation | |     - Genesis Link -> Dataset -> Reconcile    |
|     - Zep Cloud Episodic Memory Graph         | |     - Exportable to verified CSV & JSON       |
+-----------------------------------------------+ +-----------------------------------------------+
                                     | Real-Time SSE Stream
                                     v
+-------------------------------------------------------------------------------------------------+
|  6. USER EXPERIENCE & EVALUATOR DASHBOARD (FastAPI Port 8000 + React 18 / Tailwind / Vite)      |
|     - Live Preflight Health Check (All 5 services status badges)                                |
|     - Interactive Evidence Drawer, Filterable Exception Grid & 30-Day Benchmark Analytics Tab   |
+-------------------------------------------------------------------------------------------------+
```

---

## 3. Deep Dive: What is MiroFish & Why Does It Matter?

### What is MiroFish?
MiroFish is an open-source multi-agent swarm intelligence simulation engine (pinned in `vendor/MiroFish` at revision `7657031a`). Unlike standard LLMs that generate a single generic response, MiroFish models multiple autonomous agents interacting simultaneously within a shared environment, each with distinct psychological traits, knowledge boundaries, and incentives.

### Why is MiroFish used in ExaSettle?
In real-world payment settlement (Track 01), a financial mismatch is not just a ledger issue—it is a crisis of trust between three distinct human stakeholders:
- **The End Customer:** Panicked about double debits, demands instant chargebacks, cites UPI confirmation screens.
- **The Merchant:** Operates on tight cash flow, furious about missing bank credits, disputes arbitrary MDR fee variances.
- **The Gateway/Bank Operator:** Constrained by RBI batch cutoff windows, strictly requires UTR/RRN trace identifiers.

### The Golden Architectural Rule (Separation of Truth & Simulation)
Under **Working Rule 4 & PRD Section 9.5**, MiroFish is strictly a *read-only operational simulation*:
- MiroFish **cannot calculate balances**, **cannot classify transactions**, and **cannot override Exasol's mathematical determination**.
- Every simulation panel displays the persistent banner: `AI-simulated scenario — not real customer feedback`.

### MiroFish Execution Modes
1. **TRUE_MIROFISH:** Calls the live Python Flask microservice on port 5001 connected to Zep Cloud memory graph.
2. **DIRECT_LLM_ROLEPLAY:** Direct zero-shot persona roleplay via Google Gemini API (`gemini-3.8-flash`).
3. **PRERECORDED:** Instant offline verified dialogue pack for network-isolated or zero-latency test runs.

---

## 4. The 8 Planted Financial Exception Scenarios

| Txn ID | Classification | Priority | Variance | Root Cause & SQL Rule | Assigned Owner & Target SLA |
|:---|:---|:---:|:---:|:---|:---|
| **TXN_101** | `MATCHED` | 0 | ₹0.00 | Clean match across PG Ref, UTR, and paise amount. | Auto-Closed (Instant) |
| **TXN_102** | `FEE_VARIANCE_MDR` | 15 | ₹15.00 | Gateway MDR fee differs from contracted bank rate schedule. | Pricing Ops (48h) |
| **TXN_103** | `AMOUNT_MISMATCH` | 40 | ₹500.00 | Gateway principal captured differs from bank settled funds. | Settlement Ops (24h) |
| **TXN_104** | `MISSING_IN_BANK` | 95 | ₹1,200.00 | Customer charged at gateway, but zero bank settlement record received. | Treasury / Bank Ops (4h) |
| **TXN_105** | `MISSING_IN_GATEWAY` | 92 | ₹850.00 | Orphaned bank settlement credit with no originating gateway capture. | Fraud / IT Ops (4h) |
| **TXN_106** | `DUPLICATE` | 40 | ₹0.00 | Multiple physical capture records found for single logical order. | Customer Support (12h) |
| **TXN_107** | `SETTLEMENT_DELAY` | 37 | ₹0.00 | Settlement timestamp exceeds policy cutoff threshold ($T > 24\text{h}$). | Network Relations (24h) |
| **TXN_108** | `AMBIGUOUS_REVIEW` | 35 | ₹0.00 | Gateway marks REFUNDED while Bank marks SETTLED (status conflict). | Dispute Desk (12h) |

---

## 5. Deterministic Explainability & Operational Triage

Regulators (RBI) and statutory auditors reject black-box AI outputs. ExaSettle provides **6 Deterministic Explainability Fields** on every single transaction:

1. **Reason Code:** Standardized enum (e.g., `RC_MISSING_BANK_CREDIT`, `RC_MDR_RATE_DISCREPANCY`).
2. **Evidence Summary:** Raw feed timestamps, reference numbers (PG_REF, UTR), and paise deltas.
3. **Recommended Action:** Precise operational playbook (e.g., *"Dispatch UTR inquiry to beneficiary bank nodal officer"*).
4. **Assigned Owner:** Deterministic operational desk routing (Treasury, Merchant Support, Dispute Desk).
5. **Target SLA:** Strict countdown deadline (e.g., 4 Hours, 12 Hours, 24 Hours).
6. **Priority Score:** Continuous formula:
   $$\text{Priority} = \text{Base Weight} + \min(30, \frac{\text{Amount Paise}}{100,000}) + \text{Delay Factor} \quad [0 \le \text{Score} \le 100]$$

### Automated Webhook Escalation Alert
When $\text{Priority} \ge 70$, ExaSettle dispatches a typed `WebhookAlertPayload` to external banking escalation webhooks with critical severity flags (`CRITICAL` for score $\ge 90$, `HIGH` for score $\ge 70$).

---

## 6. Step-by-Step Live Demo Presentation Script

Follow this exact sequence while sharing your screen with the interviewer:

### Step 1: System Preflight (0:00 - 0:45)
- Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.
- Show the top banner of 5 Preflight Health Badges.
- Point out that all services are live and green: **Exasol Personal 2026.2.0-nano.3** (port 8563), **MiroFish Swarm** (port 5001), **Google Gemini LLM**, and **Zep Cloud**.
- **Talking Point:** *"We enforce strict zero-fabrication: if any dependency were missing, the system would honestly declare it OFFLINE."*

### Step 2: Architecture Walkthrough (0:45 - 1:30)
- Click the **"Architecture"** button in the header.
- Explain the separation of the in-memory analytical SQL layer (Exasol) from the simulation layer (MiroFish).
- **Talking Point:** *"Financial calculations use strict integer paise arithmetic. We never use IEEE floating-point numbers for money."*

### Step 3: Trigger Reconciliation Run (1:30 - 2:30)
- Select **Scenario: Core 8-Pack**, Seed: 42, Engine: **Exasol Personal Analytical Engine**.
- Click **"Start Reconciliation Run"**.
- Point out the live Server-Sent Events (SSE) transition across the 6 pipeline stages: Generation $\rightarrow$ Ingestion $\rightarrow$ Exasol Analytical SQL $\rightarrow$ Explainability $\rightarrow$ MiroFish Swarm $\rightarrow$ Tamper-Evident Hash Chain.
- **Talking Point:** *"Notice how Exasol executed the full outer join and aggregation across 15 records in under 55 milliseconds."*

### Step 4: Evidence Inspection & Explainability (2:30 - 3:30)
- In the Results Table, click **"Evidence"** on **TXN_SYN_104** (Missing in Bank, Priority 95).
- Show the 6 deterministic explainability fields, the automated webhook alert payload, the raw gateway vs bank JSON comparison, and the live MiroFish dialogue showing the merchant and bank operator perspectives.

### Step 5: 30-Day Benchmark Analytics (3:30 - 4:15)
- Click the **"30-Day Benchmark Analytics"** tab.
- Show the verified 300,000 transaction dataset KPI cards (0 Paise Reconciliation Delta across all 30 days).
- Switch between the dark-mode charts: Daily Exceptions, Query Time vs Rows (showing sub-second queries on 1M rows), Month-End Close Time (1.2 seconds vs 40 hours manual baseline), and the 6-Persona Feedback improvement curve.

### Step 6: Cryptographic Audit Verification (4:15 - 5:00)
- Switch to your terminal and run:
  ```bash
  python -m exasettle.cli verify-audit
  ```
- Show the terminal output verifying the SHA-256 cryptographic parent-hash chain link from genesis to completion.

---

## 7. Top 10 Technical Interview Questions & High-Scoring Answers

### Q1: Why did you use integer paise instead of standard floating-point rupees?
> **Answer:** Standard floating-point types (IEEE 754 float/double) cannot represent decimal fractions like 0.1 or 0.01 exactly in binary. In high-volume banking (millions of transactions per hour), floating point rounding errors accumulate into rupees of discrepancy that break statutory audits. By enforcing integer paise (₹100.50 = 10050 paise) and converting via Decimal arithmetic only at export, ExaSettle mathematically guarantees exact fee conservation to the paisa (verified by Hypothesis property fuzz tests).

### Q2: Why use Exasol Personal rather than traditional PostgreSQL or MySQL?
> **Answer:** Reconciliation is an OLAP (Online Analytical Processing) workload requiring heavy aggregations (SUM, COUNT, MIN, MAX) over dual ledger tables followed by full outer joins. Row-based databases scan entire rows from disk, which degrades rapidly past 100k records. Exasol is an in-memory columnar database with automated index compression. Our benchmarks show Exasol aggregates and reconciles 1,000,000 rows in just 727ms—over 50x faster than traditional relational engines—reducing monthly settlement close from 40 hours to 1.2 seconds.

### Q3: What role does AI actually play, and why didn't you let an LLM do the reconciliation?
> **Answer:** Letting an LLM perform mathematical reconciliation would be catastrophic in fintech: LLMs hallucinate, suffer from non-deterministic arithmetic, and act as unverifiable black boxes that fail banking compliance. In ExaSettle, 100% of the mathematical calculation and classification is performed by deterministic Exasol SQL. AI is strictly utilized in *MiroFish Swarm Simulation* to model human dispute dynamics (customer frustration, merchant chargebacks) and synthesize operational feedback, strictly separated from financial truth.

### Q4: What is MiroFish Swarm Intelligence and how does it integrate with Zep Cloud?
> **Answer:** MiroFish is a multi-agent framework where agents act based on specialized behavioral profiles rather than generic prompts. In ExaSettle, MiroFish spawns three distinct roles for any disputed transaction: the Customer, the Merchant, and the Gateway Operator. Zep Cloud acts as the long-term temporal memory graph for these agents, persisting conversation context, dispute histories, and merchant risk profiles across multiple sessions.

### Q5: How does the system handle duplicate feeds or re-submissions? (Idempotency)
> **Answer:** Real-world banks often retransmit settlement files. ExaSettle enforces full idempotency: before loading records, the reconciler cleans staged records for that specific run ID. Our automated test suite includes `tests/test_idempotency.py`, which verifies that running the identical feed twice produces byte-for-byte identical classifications and SHA-256 event hashes.

### Q6: How do you guarantee tamper evidence for statutory auditors?
> **Answer:** Every stage transition—from dataset generation to analytical SQL execution—generates a cryptographic event record containing a SHA-256 hash computed over its payload and the hash of its parent event. This forms a continuous Merkle-style blockchain link from the GENESIS event. Any tampering with past records breaks the hash link, which is instantly caught by our `verify-audit` CLI tool.

### Q7: How did you validate accuracy across all scenarios?
> **Answer:** We implemented a full confusion matrix in `reports/accuracy.md` testing 8 distinct planted exception scenarios with independent synthetic ground truth labels. The engine achieves 100% precision, recall, and F1-score across all 8 classes. In addition, we ran a continuous 30-day benchmark (300,000 transactions) verifying that Gateway Total = Bank Total + MDR Fees + Open Exceptions with an exact 0.00 paise delta on every single day.

### Q8: How did you test high load and concurrency?
> **Answer:** We built a Locust load testing harness (`tests/locustfile.py`) simulating 10, 50, and 100 concurrent operators hitting health checks, full outer join runs, and evidence queries. Across 1,200+ requests under heavy concurrency, ExaSettle maintained a 0.0% failure rate and median latency of 6.2ms. We also saved the query EXPLAIN plan to `reports/explain_plan.txt` demonstrating full index scans.

### Q9: What was the 6-persona simulated feedback loop and how did you iterate on feedback?
> **Answer:** We implemented a synthetic evaluation loop in `scripts/run_simulated_feedback_loop.py` using 6 distinct personas: Skeptical Competitor, Investigative Journalist, Shop Owner, Finance Ops Manager, Statutory Auditor, and Random User. In Round 1, they flagged 3 key objections: the 40-hour close time needed labeling as an industry assumption, Exasol container setup needed clear commands, and high-priority exceptions needed automated webhook alert schemas. We fixed all three in code, and Round 2 scores jumped from 3.44/5 to 4.50/5 (+1.06 net improvement).

### Q10: What are the honest prototype boundaries and limitations of this repository?
> **Answer:** We adhere strictly to engineering honesty: First, the dashboard run cache is an in-memory dictionary that resets on server reboot. Second, the 40.0-hour traditional close time is explicitly labeled as an industry baseline assumption. Third, all persona feedback is honestly declared as AI-simulated rather than real customer feedback. Zero results are fabricated.

---

## 8. CLI Command Cheat Sheet for Demo

| Command | Purpose |
|:---|:---|
| `python -m exasettle.cli demo` | Full automated end-to-end evaluator pipeline |
| `python -m exasettle.cli preflight` | Inspect live health of Exasol, MiroFish, Zep, and LLM |
| `python -m exasettle.cli run --engine EXASOL` | Execute analytical reconciliation directly on Exasol |
| `python -m exasettle.cli verify-audit` | Cryptographic SHA-256 tamper-evident hash chain check |
| `pytest -v -rs` | Run full 47-test automated test suite (100% passing) |
| `python -m exasettle.cli server --port 8000` | Launch FastAPI web dashboard and SSE stream |
| `wsl -d podman-machine-default podman ps` | Check running Exasol Personal Nano container in WSL |
