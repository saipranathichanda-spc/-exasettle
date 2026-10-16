"""
Deterministic Synthetic Dataset and Ground-Truth Generator for ExaSettle.
Implements PRD Section 9.1:
- Fictional entities only with visible simulation labels
- Deterministic reproducibility from seed
- Plants all 8 required known-answer cases
- Pre-computes independent ground truth
- Calculates SHA-256 tamper-evident hashes
"""

import hashlib
import json
import random
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Dict, Any, Optional

from exasettle.core.models import (
    LedgerRecord,
    GroundTruthRecord,
    SourceSystem,
    ReconciliationClassification
)
from exasettle.core.money import rupees_to_paise


FICTIONAL_CUSTOMERS = [
    ("CUST_IND_101", "Aarav Sharma (Fictional Persona)"),
    ("CUST_IND_102", "Priya Patel (Fictional Persona)"),
    ("CUST_IND_103", "Rohan Gupta (Fictional Persona)"),
    ("CUST_IND_104", "Ananya Iyer (Fictional Persona)"),
    ("CUST_IND_105", "Vikram Verma (Fictional Persona)"),
    ("CUST_IND_106", "Kavita Rao (Fictional Persona)"),
    ("CUST_IND_107", "Suresh Nair (Fictional Persona)"),
    ("CUST_IND_108", "Deepika Sen (Fictional Persona)"),
    ("CUST_IND_109", "Arjun Reddy (Fictional Persona)"),
    ("CUST_IND_110", "Meera Joshi (Fictional Persona)")
]

FICTIONAL_MERCHANTS = [
    ("MERCH_001", "Kirana Express (Fictional Merchant)"),
    ("MERCH_002", "Bharat Retailers (Fictional Merchant)"),
    ("MERCH_003", "Deccan Electronics (Fictional Merchant)"),
    ("MERCH_004", "Himalayan Goods (Fictional Merchant)")
]


def compute_sha256(data: str) -> str:
    """Compute SHA-256 hex digest for tamper-evident hashing."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class SyntheticDatasetPackage:
    def __init__(
        self,
        run_id: str,
        scenario_id: str,
        seed: int,
        gateway_records: List[LedgerRecord],
        bank_records: List[LedgerRecord],
        ground_truth: List[GroundTruthRecord],
        dataset_hash: str,
        metadata: Dict[str, Any]
    ):
        self.run_id = run_id
        self.scenario_id = scenario_id
        self.seed = seed
        self.gateway_records = gateway_records
        self.bank_records = bank_records
        self.ground_truth = ground_truth
        self.dataset_hash = dataset_hash
        self.metadata = metadata

    @property
    def total_records(self) -> int:
        return len(self.gateway_records) + len(self.bank_records)


def generate_synthetic_dataset(
    run_id: str = "run_demo_001",
    scenario_id: str = "SCN_CORE_8PACK",
    seed: int = 42,
    extra_matched_count: int = 0,
    settlement_delay_threshold_hours: int = 24
) -> SyntheticDatasetPackage:
    """
    Generate synthetic gateway and bank records with planted known-answer test cases.
    Guarantees deterministic output given the same seed.
    """
    rng = random.Random(seed)
    base_time = datetime(2026, 10, 16, 10, 0, 0, tzinfo=timezone.utc)

    gateway_records: List[LedgerRecord] = []
    bank_records: List[LedgerRecord] = []
    ground_truth: List[GroundTruthRecord] = []

    # -------------------------------------------------------------
    # Case 1: MATCHED - Valid transaction matching perfectly
    # -------------------------------------------------------------
    t1_id = "TXN_SYN_101"
    cust1_id, cust1_name = FICTIONAL_CUSTOMERS[0]
    merch1_id, merch1_name = FICTIONAL_MERCHANTS[0]
    amount1 = rupees_to_paise(1500)  # ₹1500.00
    fee1 = rupees_to_paise(30)       # 2% MDR
    t1_gw_time = (base_time + timedelta(minutes=5)).isoformat()
    t1_bank_time = (base_time + timedelta(minutes=15)).isoformat()

    ground_truth.append(GroundTruthRecord(
        scenario_id=scenario_id,
        transaction_id=t1_id,
        expected_classification=ReconciliationClassification.MATCHED,
        expected_difference_paise=0,
        planted_reason="Gateway and bank amounts match; settlement within expected window.",
        synthetic_customer_name=cust1_name,
        synthetic_merchant_name=merch1_name
    ))

    gw1 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t1_id,
        synthetic_customer_id=cust1_id,
        synthetic_merchant_id=merch1_id,
        source_system=SourceSystem.GATEWAY,
        source_record_id="GW_REC_101",
        gateway_reference="PG_REF_101",
        bank_reference="UTR_101",
        amount_paise=amount1,
        fee_paise=fee1,
        currency="INR",
        event_timestamp_utc=t1_gw_time,
        settlement_timestamp_utc=None,
        status="SUCCESS",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    bk1 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t1_id,
        synthetic_customer_id=cust1_id,
        synthetic_merchant_id=merch1_id,
        source_system=SourceSystem.BANK,
        source_record_id="BK_REC_101",
        gateway_reference="PG_REF_101",
        bank_reference="UTR_101",
        amount_paise=amount1,
        fee_paise=fee1,
        currency="INR",
        event_timestamp_utc=t1_bank_time,
        settlement_timestamp_utc=t1_bank_time,
        status="SETTLED",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    gateway_records.append(gw1)
    bank_records.append(bk1)

    # -------------------------------------------------------------
    # Case 2: FEE_VARIANCE_MDR - Fee / commission discrepancy
    # -------------------------------------------------------------
    t2_id = "TXN_SYN_102"
    cust2_id, cust2_name = FICTIONAL_CUSTOMERS[1]
    merch2_id, merch2_name = FICTIONAL_MERCHANTS[1]
    amount2 = rupees_to_paise(2000)
    fee2_gw = rupees_to_paise(40)    # Gateway expects ₹40 MDR
    fee2_bank = rupees_to_paise(55)  # Bank debited ₹55 fee
    t2_time = (base_time + timedelta(minutes=20)).isoformat()

    ground_truth.append(GroundTruthRecord(
        scenario_id=scenario_id,
        transaction_id=t2_id,
        expected_classification=ReconciliationClassification.FEE_VARIANCE_MDR,
        expected_difference_paise=0,
        planted_reason="MDR fee mismatch: Gateway calculated ₹40.00 fee, Bank deducted ₹55.00 fee (₹15.00 variance).",
        synthetic_customer_name=cust2_name,
        synthetic_merchant_name=merch2_name
    ))

    gw2 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t2_id,
        synthetic_customer_id=cust2_id,
        synthetic_merchant_id=merch2_id,
        source_system=SourceSystem.GATEWAY,
        source_record_id="GW_REC_102",
        gateway_reference="PG_REF_102",
        bank_reference="UTR_102",
        amount_paise=amount2,
        fee_paise=fee2_gw,
        currency="INR",
        event_timestamp_utc=t2_time,
        status="SUCCESS",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    bk2 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t2_id,
        synthetic_customer_id=cust2_id,
        synthetic_merchant_id=merch2_id,
        source_system=SourceSystem.BANK,
        source_record_id="BK_REC_102",
        gateway_reference="PG_REF_102",
        bank_reference="UTR_102",
        amount_paise=amount2,
        fee_paise=fee2_bank,
        currency="INR",
        event_timestamp_utc=(base_time + timedelta(minutes=25)).isoformat(),
        settlement_timestamp_utc=(base_time + timedelta(minutes=25)).isoformat(),
        status="SETTLED",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    gateway_records.append(gw2)
    bank_records.append(bk2)

    # -------------------------------------------------------------
    # Case 3: AMOUNT_MISMATCH - Unexplained amount difference
    # -------------------------------------------------------------
    t3_id = "TXN_SYN_103"
    cust3_id, cust3_name = FICTIONAL_CUSTOMERS[2]
    merch3_id, merch3_name = FICTIONAL_MERCHANTS[2]
    amount3_gw = rupees_to_paise(3500)
    amount3_bk = rupees_to_paise(3000)  # Difference of ₹500
    t3_time = (base_time + timedelta(minutes=35)).isoformat()

    ground_truth.append(GroundTruthRecord(
        scenario_id=scenario_id,
        transaction_id=t3_id,
        expected_classification=ReconciliationClassification.AMOUNT_MISMATCH,
        expected_difference_paise=amount3_gw - amount3_bk,
        planted_reason="Principal amount discrepancy: Gateway shows ₹3,500.00 while Bank settled ₹3,000.00.",
        synthetic_customer_name=cust3_name,
        synthetic_merchant_name=merch3_name
    ))

    gw3 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t3_id,
        synthetic_customer_id=cust3_id,
        synthetic_merchant_id=merch3_id,
        source_system=SourceSystem.GATEWAY,
        source_record_id="GW_REC_103",
        gateway_reference="PG_REF_103",
        bank_reference="UTR_103",
        amount_paise=amount3_gw,
        fee_paise=rupees_to_paise(70),
        currency="INR",
        event_timestamp_utc=t3_time,
        status="SUCCESS",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    bk3 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t3_id,
        synthetic_customer_id=cust3_id,
        synthetic_merchant_id=merch3_id,
        source_system=SourceSystem.BANK,
        source_record_id="BK_REC_103",
        gateway_reference="PG_REF_103",
        bank_reference="UTR_103",
        amount_paise=amount3_bk,
        fee_paise=rupees_to_paise(70),
        currency="INR",
        event_timestamp_utc=(base_time + timedelta(minutes=40)).isoformat(),
        settlement_timestamp_utc=(base_time + timedelta(minutes=40)).isoformat(),
        status="SETTLED",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    gateway_records.append(gw3)
    bank_records.append(bk3)

    # -------------------------------------------------------------
    # Case 4: MISSING_IN_BANK - Gateway recorded success, Bank record absent
    # -------------------------------------------------------------
    t4_id = "TXN_SYN_104"
    cust4_id, cust4_name = FICTIONAL_CUSTOMERS[3]
    merch4_id, merch4_name = FICTIONAL_MERCHANTS[3]
    amount4 = rupees_to_paise(1200)
    t4_time = (base_time + timedelta(minutes=50)).isoformat()

    ground_truth.append(GroundTruthRecord(
        scenario_id=scenario_id,
        transaction_id=t4_id,
        expected_classification=ReconciliationClassification.MISSING_IN_BANK,
        expected_difference_paise=amount4,
        planted_reason="Transaction recorded as SUCCESS in gateway, but completely absent from bank settlement file.",
        synthetic_customer_name=cust4_name,
        synthetic_merchant_name=merch4_name
    ))

    gw4 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t4_id,
        synthetic_customer_id=cust4_id,
        synthetic_merchant_id=merch4_id,
        source_system=SourceSystem.GATEWAY,
        source_record_id="GW_REC_104",
        gateway_reference="PG_REF_104",
        bank_reference="UTR_104",
        amount_paise=amount4,
        fee_paise=rupees_to_paise(24),
        currency="INR",
        event_timestamp_utc=t4_time,
        status="SUCCESS",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    gateway_records.append(gw4)

    # -------------------------------------------------------------
    # Case 5: MISSING_IN_GATEWAY - Bank settled, Gateway record missing
    # -------------------------------------------------------------
    t5_id = "TXN_SYN_105"
    cust5_id, cust5_name = FICTIONAL_CUSTOMERS[4]
    merch5_id, merch5_name = FICTIONAL_MERCHANTS[0]
    amount5 = rupees_to_paise(850)
    t5_time = (base_time + timedelta(hours=1, minutes=10)).isoformat()

    ground_truth.append(GroundTruthRecord(
        scenario_id=scenario_id,
        transaction_id=t5_id,
        expected_classification=ReconciliationClassification.MISSING_IN_GATEWAY,
        expected_difference_paise=amount5,
        planted_reason="Credit found in bank settlement without corresponding gateway initiation record (orphaned settlement).",
        synthetic_customer_name=cust5_name,
        synthetic_merchant_name=merch5_name
    ))

    bk5 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t5_id,
        synthetic_customer_id=cust5_id,
        synthetic_merchant_id=merch5_id,
        source_system=SourceSystem.BANK,
        source_record_id="BK_REC_105",
        gateway_reference=None,
        bank_reference="UTR_105",
        amount_paise=amount5,
        fee_paise=rupees_to_paise(17),
        currency="INR",
        event_timestamp_utc=t5_time,
        settlement_timestamp_utc=t5_time,
        status="SETTLED",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    bank_records.append(bk5)

    # -------------------------------------------------------------
    # Case 6: DUPLICATE - Duplicate record injected
    # -------------------------------------------------------------
    t6_id = "TXN_SYN_106"
    cust6_id, cust6_name = FICTIONAL_CUSTOMERS[5]
    merch6_id, merch6_name = FICTIONAL_MERCHANTS[1]
    amount6 = rupees_to_paise(4500)
    t6_time = (base_time + timedelta(hours=1, minutes=30)).isoformat()

    ground_truth.append(GroundTruthRecord(
        scenario_id=scenario_id,
        transaction_id=t6_id,
        expected_classification=ReconciliationClassification.DUPLICATE,
        expected_difference_paise=0,
        planted_reason="Duplicate transaction record submitted twice in gateway feeds with identical transaction ID.",
        synthetic_customer_name=cust6_name,
        synthetic_merchant_name=merch6_name
    ))

    gw6_a = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t6_id,
        synthetic_customer_id=cust6_id,
        synthetic_merchant_id=merch6_id,
        source_system=SourceSystem.GATEWAY,
        source_record_id="GW_REC_106_A",
        gateway_reference="PG_REF_106",
        bank_reference="UTR_106",
        amount_paise=amount6,
        fee_paise=rupees_to_paise(90),
        currency="INR",
        event_timestamp_utc=t6_time,
        status="SUCCESS",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    gw6_b = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t6_id,
        synthetic_customer_id=cust6_id,
        synthetic_merchant_id=merch6_id,
        source_system=SourceSystem.GATEWAY,
        source_record_id="GW_REC_106_B",
        gateway_reference="PG_REF_106",
        bank_reference="UTR_106",
        amount_paise=amount6,
        fee_paise=rupees_to_paise(90),
        currency="INR",
        event_timestamp_utc=(base_time + timedelta(hours=1, minutes=31)).isoformat(),
        status="SUCCESS",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    bk6 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t6_id,
        synthetic_customer_id=cust6_id,
        synthetic_merchant_id=merch6_id,
        source_system=SourceSystem.BANK,
        source_record_id="BK_REC_106",
        gateway_reference="PG_REF_106",
        bank_reference="UTR_106",
        amount_paise=amount6,
        fee_paise=rupees_to_paise(90),
        currency="INR",
        event_timestamp_utc=(base_time + timedelta(hours=1, minutes=40)).isoformat(),
        settlement_timestamp_utc=(base_time + timedelta(hours=1, minutes=40)).isoformat(),
        status="SETTLED",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    gateway_records.extend([gw6_a, gw6_b])
    bank_records.append(bk6)

    # -------------------------------------------------------------
    # Case 7: SETTLEMENT_DELAY - Settlement delay exceeds threshold
    # -------------------------------------------------------------
    t7_id = "TXN_SYN_107"
    cust7_id, cust7_name = FICTIONAL_CUSTOMERS[6]
    merch7_id, merch7_name = FICTIONAL_MERCHANTS[2]
    amount7 = rupees_to_paise(5000)
    t7_gw_time = (base_time + timedelta(hours=2)).isoformat()
    # Bank settled 72 hours later (threshold is configurable, e.g. 24h)
    t7_bk_time = (base_time + timedelta(hours=74)).isoformat()

    ground_truth.append(GroundTruthRecord(
        scenario_id=scenario_id,
        transaction_id=t7_id,
        expected_classification=ReconciliationClassification.SETTLEMENT_DELAY,
        expected_difference_paise=0,
        planted_reason=f"Settlement elapsed time (72 hours) exceeds scenario threshold ({settlement_delay_threshold_hours}h).",
        synthetic_customer_name=cust7_name,
        synthetic_merchant_name=merch7_name
    ))

    gw7 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t7_id,
        synthetic_customer_id=cust7_id,
        synthetic_merchant_id=merch7_id,
        source_system=SourceSystem.GATEWAY,
        source_record_id="GW_REC_107",
        gateway_reference="PG_REF_107",
        bank_reference="UTR_107",
        amount_paise=amount7,
        fee_paise=rupees_to_paise(100),
        currency="INR",
        event_timestamp_utc=t7_gw_time,
        status="SUCCESS",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    bk7 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t7_id,
        synthetic_customer_id=cust7_id,
        synthetic_merchant_id=merch7_id,
        source_system=SourceSystem.BANK,
        source_record_id="BK_REC_107",
        gateway_reference="PG_REF_107",
        bank_reference="UTR_107",
        amount_paise=amount7,
        fee_paise=rupees_to_paise(100),
        currency="INR",
        event_timestamp_utc=t7_bk_time,
        settlement_timestamp_utc=t7_bk_time,
        status="SETTLED",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    gateway_records.append(gw7)
    bank_records.append(bk7)

    # -------------------------------------------------------------
    # Case 8: AMBIGUOUS_REVIEW - Conflicting status / reversal state
    # -------------------------------------------------------------
    t8_id = "TXN_SYN_108"
    cust8_id, cust8_name = FICTIONAL_CUSTOMERS[7]
    merch8_id, merch8_name = FICTIONAL_MERCHANTS[3]
    amount8 = rupees_to_paise(2200)
    t8_time = (base_time + timedelta(hours=3)).isoformat()

    ground_truth.append(GroundTruthRecord(
        scenario_id=scenario_id,
        transaction_id=t8_id,
        expected_classification=ReconciliationClassification.AMBIGUOUS_REVIEW,
        expected_difference_paise=0,
        planted_reason="Conflicting transaction status: Gateway marked REVERSED, Bank marked SETTLED.",
        synthetic_customer_name=cust8_name,
        synthetic_merchant_name=merch8_name
    ))

    gw8 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t8_id,
        synthetic_customer_id=cust8_id,
        synthetic_merchant_id=merch8_id,
        source_system=SourceSystem.GATEWAY,
        source_record_id="GW_REC_108",
        gateway_reference="PG_REF_108",
        bank_reference="UTR_108",
        amount_paise=amount8,
        fee_paise=rupees_to_paise(44),
        currency="INR",
        event_timestamp_utc=t8_time,
        status="REVERSED",
        reversal_status="REVERSED_CUSTOMER_REQUEST",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    bk8 = LedgerRecord(
        run_id=run_id,
        scenario_id=scenario_id,
        transaction_id=t8_id,
        synthetic_customer_id=cust8_id,
        synthetic_merchant_id=merch8_id,
        source_system=SourceSystem.BANK,
        source_record_id="BK_REC_108",
        gateway_reference="PG_REF_108",
        bank_reference="UTR_108",
        amount_paise=amount8,
        fee_paise=rupees_to_paise(44),
        currency="INR",
        event_timestamp_utc=(base_time + timedelta(hours=3, minutes=10)).isoformat(),
        settlement_timestamp_utc=(base_time + timedelta(hours=3, minutes=10)).isoformat(),
        status="SETTLED",
        reversal_status="NONE",
        row_hash="",
        dataset_hash="",
        generation_seed=seed
    )
    gateway_records.append(gw8)
    bank_records.append(bk8)

    # -------------------------------------------------------------
    # Scalable Extra Matched Transactions (if requested)
    # -------------------------------------------------------------
    for i in range(extra_matched_count):
        idx = 200 + i
        txn_id = f"TXN_SYN_{idx}"
        cust_id, cust_name = FICTIONAL_CUSTOMERS[i % len(FICTIONAL_CUSTOMERS)]
        merch_id, merch_name = FICTIONAL_MERCHANTS[i % len(FICTIONAL_MERCHANTS)]
        amt = rupees_to_paise(rng.randint(200, 10000))
        fee = int(amt * 0.02)
        ev_time = (base_time + timedelta(minutes=4 * i)).isoformat()
        st_time = (base_time + timedelta(minutes=4 * i + 15)).isoformat()

        ground_truth.append(GroundTruthRecord(
            scenario_id=scenario_id,
            transaction_id=txn_id,
            expected_classification=ReconciliationClassification.MATCHED,
            expected_difference_paise=0,
            planted_reason="Extra synthesized normal matched transaction.",
            synthetic_customer_name=cust_name,
            synthetic_merchant_name=merch_name
        ))

        gw_rec = LedgerRecord(
            run_id=run_id,
            scenario_id=scenario_id,
            transaction_id=txn_id,
            synthetic_customer_id=cust_id,
            synthetic_merchant_id=merch_id,
            source_system=SourceSystem.GATEWAY,
            source_record_id=f"GW_REC_{idx}",
            gateway_reference=f"PG_REF_{idx}",
            bank_reference=f"UTR_{idx}",
            amount_paise=amt,
            fee_paise=fee,
            currency="INR",
            event_timestamp_utc=ev_time,
            status="SUCCESS",
            row_hash="",
            dataset_hash="",
            generation_seed=seed
        )
        bk_rec = LedgerRecord(
            run_id=run_id,
            scenario_id=scenario_id,
            transaction_id=txn_id,
            synthetic_customer_id=cust_id,
            synthetic_merchant_id=merch_id,
            source_system=SourceSystem.BANK,
            source_record_id=f"BK_REC_{idx}",
            gateway_reference=f"PG_REF_{idx}",
            bank_reference=f"UTR_{idx}",
            amount_paise=amt,
            fee_paise=fee,
            currency="INR",
            event_timestamp_utc=st_time,
            settlement_timestamp_utc=st_time,
            status="SETTLED",
            row_hash="",
            dataset_hash="",
            generation_seed=seed
        )
        gateway_records.append(gw_rec)
        bank_records.append(bk_rec)

    # -------------------------------------------------------------
    # Compute Individual Row Hashes and Cumulative Dataset Hash
    # -------------------------------------------------------------
    all_row_hashes = []
    for rec in gateway_records + bank_records:
        raw_repr = (
            f"{rec.source_system}:{rec.source_record_id}:{rec.transaction_id}:"
            f"{rec.amount_paise}:{rec.fee_paise}:{rec.event_timestamp_utc}:{rec.status}"
        )
        r_hash = compute_sha256(raw_repr)
        rec.row_hash = r_hash
        all_row_hashes.append(r_hash)

    cumulative_str = ":".join(sorted(all_row_hashes))
    overall_dataset_hash = compute_sha256(cumulative_str)

    for rec in gateway_records + bank_records:
        rec.dataset_hash = overall_dataset_hash

    metadata = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "seed": seed,
        "gateway_records_count": len(gateway_records),
        "bank_records_count": len(bank_records),
        "total_records_count": len(gateway_records) + len(bank_records),
        "ground_truth_cases_count": len(ground_truth),
        "settlement_delay_threshold_hours": settlement_delay_threshold_hours,
        "dataset_hash": overall_dataset_hash,
        "synthetic_disclosure": "All data generated synthetically for ExaThon hackathon demonstration only."
    }

    return SyntheticDatasetPackage(
        run_id=run_id,
        scenario_id=scenario_id,
        seed=seed,
        gateway_records=gateway_records,
        bank_records=bank_records,
        ground_truth=ground_truth,
        dataset_hash=overall_dataset_hash,
        metadata=metadata
    )
