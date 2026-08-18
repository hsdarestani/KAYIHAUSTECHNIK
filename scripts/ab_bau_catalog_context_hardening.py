from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+Bau catalog context hardening 2026-08-18"
OVERLAY = ROOT / "overlays" / "ai_scope_planner" / "erp" / "ai_scope_catalog.py"
RUNTIME = ROOT / "erp" / "ai_scope_catalog.py"


def main() -> None:
    if not OVERLAY.exists():
        raise RuntimeError("Catalog hardening overlay is missing")
    RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OVERLAY, RUNTIME)
    text = RUNTIME.read_text(encoding="utf-8")
    required = (
        "_RESTRICTED_CONTEXT_TERMS",
        "_required_anchor_groups",
        "_context_compatible",
        "best_score < 300",
        MARKER,
    )
    missing = [needle for needle in required if needle not in text]
    if missing:
        raise RuntimeError("Catalog context hardening guard failed: " + "; ".join(missing))
    print("A+Bau catalog context hardening applied: strict surface/context/anchor matching is active.")


if __name__ == "__main__":
    main()
