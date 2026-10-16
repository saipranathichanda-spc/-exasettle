"""
ExaSettle: Explainable Settlement-Reconciliation Prototype
ExaThon India 2026 - Track 01: Money, Risk & Regulation
"""

import os
import sys

# Windows UTF-8 console output support
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

__version__ = "2.0.0"
