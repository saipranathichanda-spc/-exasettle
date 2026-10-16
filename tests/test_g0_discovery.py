import os
import subprocess
from pathlib import Path

PINNED_MIROFISH_COMMIT = "7657031ac01184afe2cb220f5ee3545573b5e843"

def test_worktree_confirmed():
    """Verify current working tree root contains expected ExaSettle files."""
    repo_root = Path(__file__).resolve().parent.parent
    assert (repo_root / ".gitignore").is_file()
    assert (repo_root / "LICENSE").is_file()
    assert (repo_root / "NOTICE.md").is_file()
    assert (repo_root / ".env.example").is_file()

def test_mirofish_revision_pinned():
    """Verify MiroFish repository is checked out and pinned to the verified revision."""
    repo_root = Path(__file__).resolve().parent.parent
    mirofish_dir = repo_root / "vendor" / "MiroFish"
    assert mirofish_dir.is_dir(), "vendor/MiroFish directory must exist"

    git_dir = mirofish_dir / ".git"
    assert git_dir.exists(), "vendor/MiroFish must be a git repository"

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(mirofish_dir),
        capture_output=True,
        text=True,
        check=True
    )
    commit = result.stdout.strip()
    assert commit == PINNED_MIROFISH_COMMIT, f"Expected commit {PINNED_MIROFISH_COMMIT}, got {commit}"

def test_license_separation_and_notices():
    """Verify license separation: ExaSettle is MIT, MiroFish remains AGPL-3.0."""
    repo_root = Path(__file__).resolve().parent.parent
    
    # Check ExaSettle MIT license
    mit_license = (repo_root / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in mit_license

    # Check MiroFish AGPL license
    miro_license = (repo_root / "vendor" / "MiroFish" / "LICENSE").read_text(encoding="utf-8")
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in miro_license
    assert "Version 3" in miro_license

    # Check NOTICE.md documents AGPL-3.0 and boundaries
    notice = (repo_root / "NOTICE.md").read_text(encoding="utf-8")
    assert "AGPL-3.0" in notice
    assert "MiroFish" in notice
    assert "Zep Cloud" in notice
