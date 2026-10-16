"""
Deterministic local fallback reconciliation engine for ExaSettle.
Implements PRD Section 9.3 & 9.4:
- Executes the identical CTE / ROW_NUMBER() / FULL OUTER JOIN SQL logic
- Explicitly labeled as local fallback engine (never silently masquerades as Exasol)
- Measures prep, load, and query times
"""

import sqlite3
import time
from typing import List, Dict, Any, Tuple

from exasettle.core.models import (
    LedgerRecord,
    GroundTruthRecord,
    ReconciliationResult
)
from exasettle.engine.reconciliation_core import (
    RECONCILIATION_SQL,
    resolve_reconciliation_results
)


class LocalFallbackReconciler:
    ENGINE_NAME = f"LOCAL_SQLITE_ENGINE_v{sqlite3.sqlite_version}"

    def reconcile(
        self,
        gateway_records: List[LedgerRecord],
        bank_records: List[LedgerRecord],
        ground_truth: List[GroundTruthRecord],
        settlement_delay_threshold_hours: float = 24.0
    ) -> Tuple[List[ReconciliationResult], Dict[str, Any]]:
        t_total_start = time.perf_counter()

        # 1. Preparation
        t_prep_start = time.perf_counter()
        gw_rows = [
            (
                r.run_id, r.scenario_id, r.transaction_id, r.source_record_id,
                r.synthetic_customer_id, r.synthetic_merchant_id, r.gateway_reference,
                r.bank_reference, r.amount_paise, r.fee_paise, r.currency,
                r.event_timestamp_utc, r.status, r.reversal_status
            )
            for r in gateway_records
        ]
        bk_rows = [
            (
                r.run_id, r.scenario_id, r.transaction_id, r.source_record_id,
                r.synthetic_customer_id, r.synthetic_merchant_id, r.gateway_reference,
                r.bank_reference, r.amount_paise, r.fee_paise, r.currency,
                r.event_timestamp_utc, r.settlement_timestamp_utc, r.status, r.reversal_status
            )
            for r in bank_records
        ]
        prep_time_ms = round((time.perf_counter() - t_prep_start) * 1000, 3)

        # 2. Database Loading
        t_load_start = time.perf_counter()
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE gateway_records (
                run_id TEXT,
                scenario_id TEXT,
                transaction_id TEXT,
                source_record_id TEXT,
                synthetic_customer_id TEXT,
                synthetic_merchant_id TEXT,
                gateway_reference TEXT,
                bank_reference TEXT,
                amount_paise INTEGER,
                fee_paise INTEGER,
                currency TEXT,
                event_timestamp_utc TEXT,
                status TEXT,
                reversal_status TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE bank_records (
                run_id TEXT,
                scenario_id TEXT,
                transaction_id TEXT,
                source_record_id TEXT,
                synthetic_customer_id TEXT,
                synthetic_merchant_id TEXT,
                gateway_reference TEXT,
                bank_reference TEXT,
                amount_paise INTEGER,
                fee_paise INTEGER,
                currency TEXT,
                event_timestamp_utc TEXT,
                settlement_timestamp_utc TEXT,
                status TEXT,
                reversal_status TEXT
            )
        """)

        cur.executemany(
            "INSERT INTO gateway_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            gw_rows
        )
        cur.executemany(
            "INSERT INTO bank_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            bk_rows
        )
        conn.commit()
        load_time_ms = round((time.perf_counter() - t_load_start) * 1000, 3)

        # 3. Query Execution
        t_query_start = time.perf_counter()
        run_id = gateway_records[0].run_id if gateway_records else (bank_records[0].run_id if bank_records else "run_unknown")
        cur.execute(RECONCILIATION_SQL, (run_id, run_id))
        raw_rows = [dict(row) for row in cur.fetchall()]
        query_time_ms = round((time.perf_counter() - t_query_start) * 1000, 3)

        conn.close()

        # 4. Result Resolution & Ground Truth Validation
        gt_map = {gt.transaction_id: gt for gt in ground_truth}
        results = resolve_reconciliation_results(
            raw_rows,
            ground_truth_map=gt_map,
            settlement_delay_threshold_hours=settlement_delay_threshold_hours
        )

        total_time_ms = round((time.perf_counter() - t_total_start) * 1000, 3)

        metrics = {
            "engine": self.ENGINE_NAME,
            "engine_mode": "LOCAL_FALLBACK",
            "is_fallback": True,
            "sql_query_type": "CTE_WINDOW_FULL_OUTER_JOIN",
            "timings_ms": {
                "prep_time_ms": prep_time_ms,
                "load_time_ms": load_time_ms,
                "query_time_ms": query_time_ms,
                "total_time_ms": total_time_ms
            },
            "counts": {
                "gateway_rows": len(gateway_records),
                "bank_rows": len(bank_records),
                "reconciled_results": len(results)
            }
        }

        return results, metrics
