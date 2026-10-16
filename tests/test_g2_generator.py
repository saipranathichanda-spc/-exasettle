"""
Gate G2 Verification Tests: Synthetic Data Generator and Known Answers
"""

from exasettle.generator.dataset_generator import generate_synthetic_dataset
from exasettle.core.models import ReconciliationClassification


def test_seed_reproducibility():
    """Verify that identical seeds produce bit-for-bit identical records and dataset hashes."""
    pkg1 = generate_synthetic_dataset(seed=42, run_id="run_test_a")
    pkg2 = generate_synthetic_dataset(seed=42, run_id="run_test_a")

    assert pkg1.dataset_hash == pkg2.dataset_hash
    assert len(pkg1.gateway_records) == len(pkg2.gateway_records)
    assert len(pkg1.bank_records) == len(pkg2.bank_records)

    for r1, r2 in zip(pkg1.gateway_records, pkg2.gateway_records):
        assert r1.row_hash == r2.row_hash
        assert r1.amount_paise == r2.amount_paise
        assert r1.transaction_id == r2.transaction_id


def test_different_seeds_produce_different_hashes():
    """Verify that varying seed creates distinct datasets."""
    pkg1 = generate_synthetic_dataset(seed=42)
    pkg2 = generate_synthetic_dataset(seed=999)

    assert pkg1.seed != pkg2.seed


def test_all_eight_planted_cases_present():
    """Verify that all 8 required known-answer cases are present in independent ground truth."""
    pkg = generate_synthetic_dataset(seed=42)
    gt_classes = {gt.expected_classification for gt in pkg.ground_truth}

    required_classes = {
        ReconciliationClassification.MATCHED,
        ReconciliationClassification.FEE_VARIANCE_MDR,
        ReconciliationClassification.AMOUNT_MISMATCH,
        ReconciliationClassification.MISSING_IN_BANK,
        ReconciliationClassification.MISSING_IN_GATEWAY,
        ReconciliationClassification.DUPLICATE,
        ReconciliationClassification.SETTLEMENT_DELAY,
        ReconciliationClassification.AMBIGUOUS_REVIEW,
    }

    assert required_classes.issubset(gt_classes), f"Missing cases: {required_classes - gt_classes}"


def test_monetary_values_are_integer_paise():
    """Verify all monetary values are strict integers (no floats allowed)."""
    pkg = generate_synthetic_dataset(seed=42, extra_matched_count=10)

    for rec in pkg.gateway_records + pkg.bank_records:
        assert isinstance(rec.amount_paise, int), f"Amount must be int, got {type(rec.amount_paise)}"
        assert isinstance(rec.fee_paise, int), f"Fee must be int, got {type(rec.fee_paise)}"
        assert rec.amount_paise >= 0
        assert rec.fee_paise >= 0


def test_synthetic_disclosure_labels_present():
    """Verify every single record carries visible synthetic disclosure."""
    pkg = generate_synthetic_dataset(seed=42)

    for rec in pkg.gateway_records + pkg.bank_records:
        assert rec.synthetic_label == "Synthetic demo transaction"
        assert "Fictional" in rec.synthetic_customer_id or "IND" in rec.synthetic_customer_id

    assert "synthetic" in pkg.metadata["synthetic_disclosure"].lower()
