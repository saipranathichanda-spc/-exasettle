"""
Gate G8 Verification Tests: Final Regression, Repository Integrity & Security Audit
"""

import os
import re
from pathlib import Path
from exasettle.generator.dataset_generator import generate_synthetic_dataset
from exasettle.engine.fallback_reconciler import LocalFallbackReconciler


def test_no_secrets_in_repo_or_tracked_files():
    """Verify no live secrets, credentials or private .env files are tracked in source control."""
    import subprocess
    repo_root = Path(__file__).resolve().parent.parent

    # .env must NOT be tracked in Git (Rule 6: private local .env must be excluded from Git)
    res = subprocess.run(["git", "ls-files", ".env"], cwd=repo_root, capture_output=True, text=True)
    assert res.stdout.strip() == "", ".env file must not be committed or tracked in git"

    gitignore_text = (repo_root / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore_text, ".gitignore must exclude .env"

    # Scan python source files for leaked hardcoded API keys
    key_pattern = re.compile(r"(sk-[a-zA-Z0-9]{20,}|zep_[a-zA-Z0-9]{20,}|AIza[a-zA-Z0-9_\-]{20,}|AQ\.[a-zA-Z0-9_\-]{20,})")
    scanned_files = 0

    for py_file in repo_root.glob("exasettle/**/*.py"):
        content = py_file.read_text(encoding="utf-8")
        matches = key_pattern.findall(content)
        assert len(matches) == 0, f"Potential secret leak in {py_file}: {matches}"
        scanned_files += 1

    assert scanned_files >= 10, f"Expected to scan at least 10 python modules, scanned {scanned_files}"


def test_licensing_boundaries_intact():
    """Verify license files and notices are intact and uncompromised."""
    repo_root = Path(__file__).resolve().parent.parent

    # ExaSettle MIT license
    mit_text = (repo_root / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in mit_text
    assert "ExaSettle Contributors" in mit_text

    # NOTICE.md
    notice_text = (repo_root / "NOTICE.md").read_text(encoding="utf-8")
    assert "AGPL-3.0" in notice_text
    assert "MiroFish" in notice_text

    # MiroFish retains AGPL-3.0
    miro_license = (repo_root / "vendor" / "MiroFish" / "LICENSE").read_text(encoding="utf-8")
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in miro_license


def test_reconciliation_deterministic_stability():
    """Verify 10 repeated runs with the same seed yield identical outputs."""
    reconciler = LocalFallbackReconciler()
    first_hashes = None

    for i in range(10):
        pkg = generate_synthetic_dataset(seed=42, run_id=f"rep_run_{i}")
        results, _ = reconciler.reconcile(pkg.gateway_records, pkg.bank_records, pkg.ground_truth)
        cur_signatures = [(r.transaction_id, r.classification.value, r.difference_paise, r.priority_score) for r in results]

        if first_hashes is None:
            first_hashes = cur_signatures
        else:
            assert cur_signatures == first_hashes, f"Run {i} deviated from deterministic output"
