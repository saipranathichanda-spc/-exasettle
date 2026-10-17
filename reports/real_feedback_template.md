# ExaSettle — Real Evaluator Feedback Template

> **ExaThon India 2026 • Track 01 (Money, Risk & Regulation)**  
> **Target Audience**: Real Financial Operations Testers, Bank Settlement Teams, & Hackathon Evaluators  
> **Instructions**: Please test ExaSettle via `make demo` or the interactive dashboard (`http://127.0.0.1:8000`), then answer the 3 evaluation questions below.

---

## Evaluator Information (Optional)
- **Name / Organization**:
- **Role / Domain** (e.g., Finance Ops, Merchant Risk, Auditor, Engineer):
- **Date Tested**:

---

## Three Core Evaluation Questions

### Question 1: Explainability & Operational Clarity
> *When reviewing a flagged settlement exception (e.g. `FEE_VARIANCE_MDR`, `SETTLEMENT_DELAY`, or `MISSING_IN_BANK`), does the combination of Reason Code, Structured Evidence Fields, Designated Owner, SLA, and Recommended Action give you sufficient clarity to resolve the exception without inspecting raw database tables?*

- **Rating (1 to 5)**: `[ ]` (1 = Completely Unclear, 5 = Production Ready & Actionable)
- **Observations & Feedback**:
  ```text
  [Your observations here...]
  ```

---

### Question 2: Trust, Accounting Integrity & Auditability
> *Does ExaSettle's strict integer paise fixed-precision math, daily accounting identity check ($\text{Gateway} = \text{Bank} + \text{Fees} + \text{Exceptions}$ exact to 0 paise), and tamper-evident SHA-256 cryptographic audit chain provide sufficient evidentiary trust for regulatory compliance (RBI guidelines, statutory audit)?*

- **Rating (1 to 5)**: `[ ]` (1 = Untrusted / Incomplete, 5 = Highly Verifiable & Compliant)
- **Observations & Feedback**:
  ```text
  [Your observations here...]
  ```

---

### Question 3: Production Usability & Workflow Gap
> *What is the single most critical integration or capability (e.g. Core Banking / NPCI UPI switch webhook, ERP general ledger export, automated chargeback filing, or real-time alert dispatch) needed before deploying ExaSettle into a live merchant aggregator workflow?*

- **Priority Need**:
  ```text
  [Describe the feature / integration needed...]
  ```

---

## Submission
To submit your feedback, commit this file or open an issue at:  
[https://github.com/saipranathichanda-spc/-exasettle/issues](https://github.com/saipranathichanda-spc/-exasettle/issues)
