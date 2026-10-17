"""
Primary Exasol Personal Analytical Reconciliation Engine.
Implements PRD Section 9.3 & 9.4:
- Connects to Exasol Personal via official pyexasol driver
- Manages Exasol schema and tables
- Executes core analytical reconciliation query inside Exasol with CTEs and CASE classification
- Captures Exasol database version, session ID, and distinct query vs prep timings
"""

import time
from typing import List, Dict, Any, Tuple, Optional

from exasettle.core.config import Settings
from exasettle.core.models import (
    LedgerRecord,
    GroundTruthRecord,
    ReconciliationResult
)
from exasettle.engine.reconciliation_core import resolve_reconciliation_results

EXASOL_RECONCILIATION_SQL = """
WITH gw_agg AS (
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
        GROUP_CONCAT(source_record_id SEPARATOR ', ') as gw_record_ids,
        GROUP_CONCAT(gateway_reference SEPARATOR ', ') as gw_references,
        GROUP_CONCAT(bank_reference SEPARATOR ', ') as gw_bank_references
    FROM gateway_records
    WHERE run_id = {run_id:s}
    GROUP BY transaction_id, run_id, scenario_id
),
bk_agg AS (
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
        GROUP_CONCAT(source_record_id SEPARATOR ', ') as bk_record_ids,
        GROUP_CONCAT(gateway_reference SEPARATOR ', ') as bk_gw_references,
        GROUP_CONCAT(bank_reference SEPARATOR ', ') as bk_references
    FROM bank_records
    WHERE run_id = {run_id:s}
    GROUP BY transaction_id, run_id, scenario_id
),
joined AS (
    SELECT 
        COALESCE(gw.transaction_id, bk.transaction_id) as transaction_id,
        COALESCE(gw.run_id, bk.run_id) as run_id,
        COALESCE(gw.scenario_id, bk.scenario_id) as scenario_id,
        COALESCE(gw.gw_count, 0) as gw_count,
        COALESCE(bk.bk_count, 0) as bk_count,
        gw.gw_record_ids,
        bk.bk_record_ids,
        gw.gw_references,
        bk.bk_references,
        gw.gw_bank_references,
        bk.bk_gw_references,
        gw.gw_amount_paise,
        bk.bk_amount_paise,
        gw.gw_fee_paise,
        bk.bk_fee_paise,
        gw.gw_timestamp,
        bk.bk_timestamp,
        gw.gw_status,
        bk.bk_status,
        gw.gw_reversal
    FROM gw_agg gw
    FULL OUTER JOIN bk_agg bk 
        ON gw.transaction_id = bk.transaction_id
)
SELECT 
    *,
    CASE 
        WHEN gw_count > 1 OR bk_count > 1 THEN 'DUPLICATE'
        WHEN gw_count > 0 AND bk_count = 0 THEN 'MISSING_IN_BANK'
        WHEN gw_count = 0 AND bk_count > 0 THEN 'MISSING_IN_GATEWAY'
        WHEN (gw_status = 'REVERSED' AND bk_status = 'SETTLED') OR (gw_reversal IS NOT NULL AND gw_reversal != 'NONE') THEN 'AMBIGUOUS_REVIEW'
        WHEN gw_amount_paise != bk_amount_paise THEN 'AMOUNT_MISMATCH'
        WHEN gw_fee_paise != bk_fee_paise THEN 'FEE_VARIANCE_MDR'
        ELSE 'CANDIDATE_MATCH'
    END as preliminary_sql_classification,
    ABS(COALESCE(gw_amount_paise, 0) - COALESCE(bk_amount_paise, 0)) as diff_amount_paise,
    ABS(COALESCE(gw_fee_paise, 0) - COALESCE(bk_fee_paise, 0)) as diff_fee_paise
FROM joined
ORDER BY transaction_id ASC
"""


class ExasolReconciler:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        schema: Optional[str] = None,
        encryption: Optional[bool] = None
    ):
        self.host = host or Settings.EXASOL_HOST
        self.port = port or Settings.EXASOL_PORT
        self.user = user or Settings.EXASOL_USER
        self.password = password or Settings.EXASOL_PASSWORD
        self.schema = schema or Settings.EXASOL_SCHEMA
        self.encryption = Settings.EXASOL_ENCRYPTION if encryption is None else encryption

    def _get_connection(self):
        import pyexasol
        if not self.password:
            raise ConnectionError(
                "EXASOL_PASSWORD is empty or unset. Please configure Exasol credentials in your private .env file."
            )
        return pyexasol.connect(
            dsn=f"{self.host}:{self.port}",
            user=self.user,
            password=self.password,
            schema=self.schema,
            encryption=self.encryption,
            connection_timeout=5
        )

    def init_schema(self, con) -> None:
        """Create ExaSettle tables in Exasol schema if they do not exist."""
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema}")
        con.execute(f"OPEN SCHEMA {self.schema}")

        con.execute("""
            CREATE TABLE IF NOT EXISTS gateway_records (
                run_id VARCHAR(100),
                scenario_id VARCHAR(100),
                transaction_id VARCHAR(100),
                source_record_id VARCHAR(100),
                synthetic_customer_id VARCHAR(100),
                synthetic_merchant_id VARCHAR(100),
                gateway_reference VARCHAR(100),
                bank_reference VARCHAR(100),
                amount_paise DECIMAL(18, 0),
                fee_paise DECIMAL(18, 0),
                currency VARCHAR(10),
                event_timestamp_utc VARCHAR(50),
                status VARCHAR(50),
                reversal_status VARCHAR(100)
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS bank_records (
                run_id VARCHAR(100),
                scenario_id VARCHAR(100),
                transaction_id VARCHAR(100),
                source_record_id VARCHAR(100),
                synthetic_customer_id VARCHAR(100),
                synthetic_merchant_id VARCHAR(100),
                gateway_reference VARCHAR(100),
                bank_reference VARCHAR(100),
                amount_paise DECIMAL(18, 0),
                fee_paise DECIMAL(18, 0),
                currency VARCHAR(10),
                event_timestamp_utc VARCHAR(50),
                settlement_timestamp_utc VARCHAR(50),
                status VARCHAR(50),
                reversal_status VARCHAR(100)
            )
        """)

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
        con = self._get_connection()
        try:
            self.init_schema(con)

            t_load_start = time.perf_counter()
            run_id = gateway_records[0].run_id if gateway_records else (bank_records[0].run_id if bank_records else "run_unknown")
            
            # Clean existing records for this specific run_id
            con.execute("DELETE FROM gateway_records WHERE run_id = {run_id:s}", {"run_id": run_id})
            con.execute("DELETE FROM bank_records WHERE run_id = {run_id:s}", {"run_id": run_id})

            con.import_from_iterable(gw_rows, "gateway_records")
            con.import_from_iterable(bk_rows, "bank_records")
            load_time_ms = round((time.perf_counter() - t_load_start) * 1000, 3)

            # 3. Query Execution on Exasol
            t_query_start = time.perf_counter()
            stmt = con.execute(EXASOL_RECONCILIATION_SQL, {"run_id": run_id})
            raw_rows = stmt.fetchall()
            col_names = [col["name"].lower() for col in stmt.columns()]
            dict_rows = [dict(zip(col_names, row)) for row in raw_rows]
            query_time_ms = round((time.perf_counter() - t_query_start) * 1000, 3)

            # Retrieve database metadata
            version_str = str(con.meta.sql_type())
            session_id = getattr(con, "session_id", "active")
        finally:
            con.close()

        # 4. Result Resolution & Validation
        gt_map = {gt.transaction_id: gt for gt in ground_truth}
        results = resolve_reconciliation_results(
            dict_rows,
            ground_truth_map=gt_map,
            settlement_delay_threshold_hours=settlement_delay_threshold_hours
        )

        total_time_ms = round((time.perf_counter() - t_total_start) * 1000, 3)

        metrics = {
            "engine": "EXASOL_PERSONAL_ANALYTICS",
            "engine_mode": "EXASOL",
            "is_fallback": False,
            "database_version": version_str,
            "session_id": str(session_id),
            "sql_query_type": "EXASOL_CTE_AGGREGATION_FULL_OUTER_JOIN",
            "timings_ms": {
                "prep_time_ms": prep_time_ms,
                "load_time_ms": load_time_ms,
                "query_time_ms": query_time_ms,
                "total_time_ms": total_time_ms
            },
            "counts": {
                "gateway_rows": len(gateway_records),
                "bank_rows": len(bank_records),
                "physical_source_rows": len(gateway_records) + len(bank_records),
                "logical_transactions_reconciled": len(results)
            }
        }

        return results, metrics
