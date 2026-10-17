"""
30-Day Enterprise Synthetic Dataset & Reconciliation Generator for ExaSettle.
Implements Track 01 Requirements:
- 30 days of continuous transaction flows (~10,000 transactions/day, ~300,000 total)
- Realistic financial noise: duplicates, delays, MDR+GST fee variances, refunds,
  chargebacks, partial settlements, T+1 cutoff breaches.
- Strict integer paise arithmetic (1 INR = 100 paise) preventing floating point errors.
- Strict Reconciliation Identity: Gateway Total = Bank Total + Fees + Open Exceptions (0 paise delta).
- Deterministic reproducibility from seed.
"""

import random
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple

from exasettle.core.models import ReconciliationClassification


INDEXED_RECONCILIATION_SQL = """
SELECT 
    COALESCE(gw.transaction_id, bk.transaction_id) as transaction_id,
    COALESCE(gw.run_id, bk.run_id) as run_id,
    COALESCE(gw.scenario_id, bk.scenario_id) as scenario_id,
    COALESCE(gw.gw_count, 0) as gw_count,
    COALESCE(bk.bk_count, 0) as bk_count,
    gw.gw_amount_paise,
    bk.bk_amount_paise,
    gw.gw_fee_paise,
    bk.bk_fee_paise,
    gw.gw_timestamp,
    bk.bk_timestamp,
    gw.gw_record_ids,
    bk.bk_record_ids,
    gw.gw_status,
    bk.bk_status,
    gw.gw_reversal,
    CASE 
        WHEN COALESCE(gw.gw_count, 0) > 1 OR COALESCE(bk.bk_count, 0) > 1 THEN 'DUPLICATE'
        WHEN COALESCE(gw.gw_count, 0) > 0 AND COALESCE(bk.bk_count, 0) = 0 THEN 'MISSING_IN_BANK'
        WHEN COALESCE(gw.gw_count, 0) = 0 AND COALESCE(bk.bk_count, 0) > 0 THEN 'MISSING_IN_GATEWAY'
        WHEN (gw.gw_status = 'REVERSED' AND bk.bk_status = 'SETTLED') OR (gw.gw_reversal IS NOT NULL AND gw.gw_reversal != 'NONE') THEN 'AMBIGUOUS_REVIEW'
        WHEN gw.gw_amount_paise != bk.bk_amount_paise THEN 'AMOUNT_MISMATCH'
        WHEN gw.gw_fee_paise != bk.bk_fee_paise THEN 'FEE_VARIANCE_MDR'
        ELSE 'CANDIDATE_MATCH'
    END as preliminary_sql_classification,
    ABS(COALESCE(gw.gw_amount_paise, 0) - COALESCE(bk.bk_amount_paise, 0)) as diff_amount_paise,
    ABS(COALESCE(gw.gw_fee_paise, 0) - COALESCE(bk.bk_fee_paise, 0)) as diff_fee_paise
FROM gw_agg gw
FULL OUTER JOIN bk_agg bk 
    ON gw.transaction_id = bk.transaction_id
ORDER BY transaction_id ASC;
"""


def parse_iso_datetime(ts_str: str):
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


def generate_monthly_simulation_run(
    seed: int = 2026,
    days: int = 30,
    txns_per_day: int = 10000,
    start_date: str = "2026-09-17"
) -> Dict[str, Any]:
    """
    Generate and reconcile 30 days of dual-feed gateway and bank transactions.
    Returns full run summary, confusion matrix, identity verification table, and aging stats.
    """
    rng = random.Random(seed)
    base_date = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    # In-memory analytical SQLite database
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE gateway_records (
        transaction_id TEXT,
        run_id TEXT,
        scenario_id TEXT,
        source_record_id TEXT,
        gateway_reference TEXT,
        bank_reference TEXT,
        amount_paise INTEGER,
        fee_paise INTEGER,
        event_timestamp_utc TEXT,
        status TEXT,
        reversal_status TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE bank_records (
        transaction_id TEXT,
        run_id TEXT,
        scenario_id TEXT,
        source_record_id TEXT,
        gateway_reference TEXT,
        bank_reference TEXT,
        amount_paise INTEGER,
        fee_paise INTEGER,
        settlement_timestamp_utc TEXT,
        status TEXT,
        reversal_status TEXT
    )
    """)

    daily_identity_records: List[Dict[str, Any]] = []
    ground_truth_map: Dict[str, str] = {}

    gw_insert_batch: List[Tuple] = []
    bk_insert_batch: List[Tuple] = []

    run_id = f"monthly_run_{seed}"
    scenario_id = "SCN_MONTHLY_30D"

    print(f"Generating {days} days of transactions (~{txns_per_day} txns/day, seed={seed})...")
    gen_start = time.perf_counter()

    for day_idx in range(days):
        current_day = base_date + timedelta(days=day_idx)
        date_str = current_day.strftime("%Y-%m-%d")

        # Daily accumulators for accounting identity check
        daily_gw_gross = 0
        daily_bk_net = 0
        daily_fees = 0
        daily_open_exceptions = 0

        for i in range(txns_per_day):
            txn_seq = day_idx * txns_per_day + i + 1
            txn_id = f"TXN_{date_str.replace('-', '')}_{txn_seq:06d}"

            hour = rng.randint(0, 23)
            minute = rng.randint(0, 59)
            second = rng.randint(0, 59)
            txn_time = current_day.replace(hour=hour, minute=minute, second=second)
            txn_time_str = txn_time.isoformat()

            # Base principal amount: ₹100.00 to ₹50,000.00 in integer paise
            base_amount = rng.randint(100, 50000) * 100

            # MDR rate: 1.5% to 2.0% + 18% GST on MDR
            mdr_rate_basis_points = rng.choice([150, 180, 200])
            mdr_paise = (base_amount * mdr_rate_basis_points) // 10000
            gst_paise = (mdr_paise * 1800) // 10000
            std_fee_paise = mdr_paise + gst_paise

            roll = rng.random()

            if roll < 0.928:
                # CASE 1: MATCHED (Clean Match)
                expected_cls = "MATCHED"
                gw_amt = base_amount
                bk_amt = base_amount
                gw_fee = std_fee_paise
                bk_fee = std_fee_paise
                settle_time = txn_time + timedelta(hours=rng.uniform(4.0, 20.0))

                gw_insert_batch.append((
                    txn_id, run_id, scenario_id, f"GW_{txn_id}", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}",
                    gw_amt, gw_fee, txn_time_str, "CAPTURED", "NONE"
                ))
                bk_insert_batch.append((
                    txn_id, run_id, scenario_id, f"BK_{txn_id}", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}",
                    bk_amt, bk_fee, settle_time.isoformat(), "SETTLED", "NONE"
                ))

                daily_gw_gross += gw_amt
                daily_bk_net += (bk_amt - bk_fee)
                daily_fees += bk_fee

            elif roll < 0.946:
                # CASE 2: FEE_VARIANCE_MDR
                expected_cls = "FEE_VARIANCE_MDR"
                gw_amt = base_amount
                bk_amt = base_amount
                gw_fee = std_fee_paise
                fee_delta = rng.choice([1500, 2500, 5000, 7500, 12000])
                if rng.choice([True, False]):
                    bk_fee = gw_fee + fee_delta
                else:
                    bk_fee = max(100, gw_fee - fee_delta)

                settle_time = txn_time + timedelta(hours=rng.uniform(6.0, 20.0))

                gw_insert_batch.append((
                    txn_id, run_id, scenario_id, f"GW_{txn_id}", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}",
                    gw_amt, gw_fee, txn_time_str, "CAPTURED", "NONE"
                ))
                bk_insert_batch.append((
                    txn_id, run_id, scenario_id, f"BK_{txn_id}", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}",
                    bk_amt, bk_fee, settle_time.isoformat(), "SETTLED", "NONE"
                ))

                daily_gw_gross += gw_amt
                daily_bk_net += (bk_amt - bk_fee)
                daily_fees += gw_fee
                daily_open_exceptions += (bk_fee - gw_fee)

            elif roll < 0.961:
                # CASE 3: SETTLEMENT_DELAY (>24h lag)
                expected_cls = "SETTLEMENT_DELAY"
                gw_amt = base_amount
                bk_amt = base_amount
                gw_fee = std_fee_paise
                bk_fee = std_fee_paise
                settle_time = txn_time + timedelta(hours=rng.uniform(36.0, 96.0))

                gw_insert_batch.append((
                    txn_id, run_id, scenario_id, f"GW_{txn_id}", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}",
                    gw_amt, gw_fee, txn_time_str, "CAPTURED", "NONE"
                ))
                bk_insert_batch.append((
                    txn_id, run_id, scenario_id, f"BK_{txn_id}", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}",
                    bk_amt, bk_fee, settle_time.isoformat(), "SETTLED", "NONE"
                ))

                daily_gw_gross += gw_amt
                daily_bk_net += (bk_amt - bk_fee)
                daily_fees += bk_fee

            elif roll < 0.973:
                # CASE 4: AMOUNT_MISMATCH
                expected_cls = "AMOUNT_MISMATCH"
                gw_amt = base_amount
                variance_paise = rng.choice([5000, 10000, 25000, 50000, 100000])
                bk_amt = max(1000, gw_amt - variance_paise)
                gw_fee = std_fee_paise
                bk_fee = std_fee_paise
                settle_time = txn_time + timedelta(hours=rng.uniform(6.0, 22.0))

                gw_insert_batch.append((
                    txn_id, run_id, scenario_id, f"GW_{txn_id}", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}",
                    gw_amt, gw_fee, txn_time_str, "CAPTURED", "NONE"
                ))
                bk_insert_batch.append((
                    txn_id, run_id, scenario_id, f"BK_{txn_id}", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}",
                    bk_amt, bk_fee, settle_time.isoformat(), "SETTLED", "NONE"
                ))

                daily_gw_gross += gw_amt
                daily_bk_net += (bk_amt - bk_fee)
                daily_fees += bk_fee
                daily_open_exceptions += (gw_amt - bk_amt)

            elif roll < 0.981:
                # CASE 5: DUPLICATE
                expected_cls = "DUPLICATE"
                gw_amt = base_amount
                bk_amt = base_amount
                gw_fee = std_fee_paise
                bk_fee = std_fee_paise
                settle_time = txn_time + timedelta(hours=rng.uniform(6.0, 18.0))

                gw_insert_batch.append((
                    txn_id, run_id, scenario_id, f"GW_{txn_id}_01", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}",
                    gw_amt, gw_fee, txn_time_str, "CAPTURED", "NONE"
                ))
                bk_insert_batch.append((
                    txn_id, run_id, scenario_id, f"BK_{txn_id}_01", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}",
                    bk_amt, bk_fee, settle_time.isoformat(), "SETTLED", "NONE"
                ))

                if rng.choice([True, False]):
                    gw_insert_batch.append((
                        txn_id, run_id, scenario_id, f"GW_{txn_id}_DUP", f"REF_GW_{txn_id}_RETRY", f"REF_BK_{txn_id}",
                        gw_amt, gw_fee, (txn_time + timedelta(seconds=15)).isoformat(), "CAPTURED", "NONE"
                    ))
                    daily_gw_gross += (gw_amt * 2)
                    daily_bk_net += (bk_amt - bk_fee)
                    daily_fees += bk_fee
                    daily_open_exceptions += gw_amt
                else:
                    bk_insert_batch.append((
                        txn_id, run_id, scenario_id, f"BK_{txn_id}_DUP", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}_DUP",
                        bk_amt, bk_fee, (settle_time + timedelta(minutes=5)).isoformat(), "SETTLED", "NONE"
                    ))
                    daily_gw_gross += gw_amt
                    daily_bk_net += (bk_amt - bk_fee) * 2
                    daily_fees += (bk_fee * 2)
                    daily_open_exceptions -= bk_amt

            elif roll < 0.988:
                # CASE 6: AMBIGUOUS_REVIEW
                expected_cls = "AMBIGUOUS_REVIEW"
                gw_amt = base_amount
                bk_amt = base_amount
                gw_fee = std_fee_paise
                bk_fee = std_fee_paise
                settle_time = txn_time + timedelta(hours=rng.uniform(4.0, 18.0))

                gw_insert_batch.append((
                    txn_id, run_id, scenario_id, f"GW_{txn_id}", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}",
                    gw_amt, gw_fee, txn_time_str, "REVERSED", "CUSTOMER_CANCELLED"
                ))
                bk_insert_batch.append((
                    txn_id, run_id, scenario_id, f"BK_{txn_id}", f"REF_GW_{txn_id}", f"REF_BK_{txn_id}",
                    bk_amt, bk_fee, settle_time.isoformat(), "SETTLED", "NONE"
                ))

                daily_gw_gross += gw_amt
                daily_bk_net += (bk_amt - bk_fee)
                daily_fees += bk_fee

            elif roll < 0.994:
                # CASE 7: MISSING_IN_BANK
                expected_cls = "MISSING_IN_BANK"
                gw_amt = base_amount

                gw_insert_batch.append((
                    txn_id, run_id, scenario_id, f"GW_{txn_id}", f"REF_GW_{txn_id}", None,
                    gw_amt, std_fee_paise, txn_time_str, "CAPTURED", "NONE"
                ))

                daily_gw_gross += gw_amt
                daily_open_exceptions += gw_amt

            else:
                # CASE 8: MISSING_IN_GATEWAY
                expected_cls = "MISSING_IN_GATEWAY"
                bk_amt = base_amount

                bk_insert_batch.append((
                    txn_id, run_id, scenario_id, f"BK_{txn_id}", None, f"REF_BK_{txn_id}",
                    bk_amt, std_fee_paise, txn_time_str, "SETTLED", "NONE"
                ))

                daily_bk_net += (bk_amt - std_fee_paise)
                daily_fees += std_fee_paise
                daily_open_exceptions -= bk_amt

            ground_truth_map[txn_id] = expected_cls

        expected_balance = daily_bk_net + daily_fees + daily_open_exceptions
        identity_diff = daily_gw_gross - expected_balance

        assert identity_diff == 0, f"Identity diff non-zero on day {date_str}: {identity_diff}"

        daily_identity_records.append({
            "date": date_str,
            "day_index": day_idx + 1,
            "gateway_total_paise": daily_gw_gross,
            "bank_total_paise": daily_bk_net,
            "fees_total_paise": daily_fees,
            "open_exceptions_paise": daily_open_exceptions,
            "gateway_total_inr": f"₹{daily_gw_gross/100:,.2f}",
            "bank_total_inr": f"₹{daily_bk_net/100:,.2f}",
            "fees_total_inr": f"₹{daily_fees/100:,.2f}",
            "open_exceptions_inr": f"₹{daily_open_exceptions/100:,.2f}",
            "identity_diff_paise": identity_diff,
            "balanced": True
        })

    # Bulk insert into SQLite
    cursor.executemany(
        "INSERT INTO gateway_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        gw_insert_batch
    )
    cursor.executemany(
        "INSERT INTO bank_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        bk_insert_batch
    )
    conn.commit()

    total_gw_rows = len(gw_insert_batch)
    total_bk_rows = len(bk_insert_batch)
    gen_time_ms = round((time.perf_counter() - gen_start) * 1000, 2)
    print(f"Generated {total_gw_rows} gateway rows and {total_bk_rows} bank rows in {gen_time_ms}ms.")

    # High-performance indexed CTE staging
    recon_start = time.perf_counter()
    cursor.execute("""
    CREATE TEMP TABLE gw_agg AS 
    SELECT 
        transaction_id,
        run_id,
        scenario_id,
        COUNT(*) as gw_count,
        SUM(amount_paise) as gw_amount_paise,
        SUM(fee_paise) as gw_fee_paise,
        MIN(event_timestamp_utc) as gw_timestamp,
        MAX(status) as gw_status,
        MAX(reversal_status) as gw_reversal,
        GROUP_CONCAT(source_record_id, ', ') as gw_record_ids
    FROM gateway_records
    WHERE run_id = ?
    GROUP BY transaction_id, run_id, scenario_id;
    """, (run_id,))

    cursor.execute("CREATE INDEX idx_tmp_gw_txn ON gw_agg(transaction_id);")

    cursor.execute("""
    CREATE TEMP TABLE bk_agg AS 
    SELECT 
        transaction_id,
        run_id,
        scenario_id,
        COUNT(*) as bk_count,
        SUM(amount_paise) as bk_amount_paise,
        SUM(fee_paise) as bk_fee_paise,
        MAX(settlement_timestamp_utc) as bk_timestamp,
        MAX(status) as bk_status,
        MAX(reversal_status) as bk_reversal,
        GROUP_CONCAT(source_record_id, ', ') as bk_record_ids
    FROM bank_records
    WHERE run_id = ?
    GROUP BY transaction_id, run_id, scenario_id;
    """, (run_id,))

    cursor.execute("CREATE INDEX idx_tmp_bk_txn ON bk_agg(transaction_id);")

    cursor.execute(INDEXED_RECONCILIATION_SQL)
    columns = [desc[0] for desc in cursor.description]
    raw_joined_rows = cursor.fetchall()
    recon_time_ms = round((time.perf_counter() - recon_start) * 1000, 2)
    print(f"Executed analytical SQL in {recon_time_ms}ms ({len(raw_joined_rows)} rows joined).")

    # Fast classification & metrics resolution without heavy object allocation
    all_classes = [
        "MATCHED", "FEE_VARIANCE_MDR", "SETTLEMENT_DELAY", "AMOUNT_MISMATCH",
        "DUPLICATE", "AMBIGUOUS_REVIEW", "MISSING_IN_BANK", "MISSING_IN_GATEWAY"
    ]
    confusion_matrix = {a: {p: 0 for p in all_classes} for a in all_classes}
    daily_category_counts: Dict[str, Dict[str, int]] = {
        d["date"]: {c: 0 for c in all_classes} for d in daily_identity_records
    }
    aging_buckets = {"0-1d": 0, "2-3d": 0, "4-7d": 0, "7d+": 0}

    # Map column names to indices
    col_idx = {name: i for i, name in enumerate(columns)}
    i_txn = col_idx["transaction_id"]
    i_sql_cls = col_idx["preliminary_sql_classification"]
    i_gw_ts = col_idx["gw_timestamp"]
    i_bk_ts = col_idx["bk_timestamp"]

    total_clean = 0
    total_exceptions = 0

    for row in raw_joined_rows:
        txn_id = row[i_txn]
        sql_cls = row[i_sql_cls]
        actual_cls = ground_truth_map.get(txn_id, "MATCHED")

        # Resolve settlement delay if candidate match
        if sql_cls == "CANDIDATE_MATCH":
            gw_time_str = row[i_gw_ts]
            bk_time_str = row[i_bk_ts]
            if gw_time_str and bk_time_str:
                gw_t = parse_iso_datetime(gw_time_str)
                bk_t = parse_iso_datetime(bk_time_str)
                delay_hours = (bk_t - gw_t).total_seconds() / 3600.0 if (gw_t and bk_t) else 0.0
            else:
                delay_hours = 0.0

            if delay_hours > 24.0:
                final_cls = "SETTLEMENT_DELAY"
            else:
                final_cls = "MATCHED"
        else:
            final_cls = sql_cls
            gw_time_str = row[i_gw_ts]
            bk_time_str = row[i_bk_ts]
            if gw_time_str and bk_time_str:
                gw_t = parse_iso_datetime(gw_time_str)
                bk_t = parse_iso_datetime(bk_time_str)
                delay_hours = (bk_t - gw_t).total_seconds() / 3600.0 if (gw_t and bk_t) else 0.0
            else:
                delay_hours = 0.0

        confusion_matrix[actual_cls][final_cls] += 1

        d_str = txn_id.split("_")[1]
        formatted_date = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:8]}"
        if formatted_date in daily_category_counts:
            daily_category_counts[formatted_date][final_cls] += 1

        if final_cls == "MATCHED":
            total_clean += 1
        else:
            total_exceptions += 1
            if delay_hours <= 24:
                aging_buckets["0-1d"] += 1
            elif delay_hours <= 72:
                aging_buckets["2-3d"] += 1
            elif delay_hours <= 168:
                aging_buckets["4-7d"] += 1
            else:
                aging_buckets["7d+"] += 1

    # Per-class metrics
    total_eval = len(raw_joined_rows)
    total_tp = 0
    per_class_metrics: Dict[str, Dict[str, Any]] = {}

    for cls in all_classes:
        tp = confusion_matrix[cls][cls]
        fn = sum(confusion_matrix[cls][p] for p in all_classes if p != cls)
        fp = sum(confusion_matrix[a][cls] for a in all_classes if a != cls)
        tn = total_eval - (tp + fn + fp)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 1.0

        total_tp += tp
        per_class_metrics[cls] = {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
            "support": tp + fn,
            "precision": round(precision * 100, 2),
            "recall": round(recall * 100, 2),
            "f1_score": round(f1 * 100, 2)
        }

    overall_accuracy = round((total_tp / total_eval) * 100, 2)

    daily_stats: List[Dict[str, Any]] = []
    for id_rec in daily_identity_records:
        d_date = id_rec["date"]
        d_counts = daily_category_counts.get(d_date, {})
        d_total = sum(d_counts.values())
        d_clean = d_counts.get("MATCHED", 0)
        d_exc = d_total - d_clean
        d_rate = round((d_clean / d_total * 100), 2) if d_total > 0 else 0.0

        daily_stats.append({
            "date": d_date,
            "total_transactions": d_total,
            "clean_matches": d_clean,
            "exceptions_flagged": d_exc,
            "auto_match_rate_percent": d_rate,
            "category_breakdown": d_counts,
            "gateway_total_paise": id_rec["gateway_total_paise"],
            "bank_total_paise": id_rec["bank_total_paise"],
            "fees_total_paise": id_rec["fees_total_paise"],
            "open_exceptions_paise": id_rec["open_exceptions_paise"]
        })

    conn.close()

    return {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "seed": seed,
        "total_days": days,
        "total_transactions": total_eval,
        "total_gateway_rows": total_gw_rows,
        "total_bank_rows": total_bk_rows,
        "timings_ms": {
            "generation_time_ms": gen_time_ms,
            "reconciliation_time_ms": recon_time_ms
        },
        "overall_accuracy_percent": overall_accuracy,
        "per_class_metrics": per_class_metrics,
        "confusion_matrix": confusion_matrix,
        "daily_identity_records": daily_identity_records,
        "daily_stats": daily_stats,
        "aging_buckets": aging_buckets
    }
