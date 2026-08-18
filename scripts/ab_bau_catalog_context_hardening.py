from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+Bau catalog context hardening 2026-08-18"
OVERLAY = ROOT / "overlays" / "ai_scope_planner" / "erp" / "ai_scope_catalog.py"
RUNTIME = ROOT / "erp" / "ai_scope_catalog.py"

# Specialized remediation / hazardous-material positions often contain generic
# verbs such as "streichen" or "abdecken". Those verbs must never be enough to
# satisfy a normal painting/protection scope. Keep these as restricted contexts so
# they are only eligible when a future dedicated scope explicitly requests them.
SPECIALIZED_REMEDIATION_CONTEXTS = '''    "mold_remediation": ("schimmel", "schimmelpilz", "schimmelpilzsporen", "sporenbinder", "sporen", "demobilisier"),
    "hazard_remediation": ("asbest", "schadstoff", "gefahrstoff", "kontamin", "dekontamin", "pcb", "pak", "kmf"),
'''


def _install_specialized_contexts(text: str) -> str:
    if '"mold_remediation"' in text:
        return text
    anchor = '    "stone_finish": ("buntsteinputz",),\n'
    if anchor not in text:
        raise RuntimeError("Catalog restricted-context anchor changed")
    return text.replace(anchor, anchor + SPECIALIZED_REMEDIATION_CONTEXTS, 1)


def main() -> None:
    if not OVERLAY.exists():
        raise RuntimeError("Catalog hardening overlay is missing")
    RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    text = _install_specialized_contexts(OVERLAY.read_text(encoding="utf-8"))
    RUNTIME.write_text(text, encoding="utf-8")
    required = (
        "_RESTRICTED_CONTEXT_TERMS",
        "_required_anchor_groups",
        "_context_compatible",
        "best_score < 300",
        '"mold_remediation"',
        '"hazard_remediation"',
        "sporenbinder",
        MARKER,
    )
    missing = [needle for needle in required if needle not in text]
    if missing:
        raise RuntimeError("Catalog context hardening guard failed: " + "; ".join(missing))
    print("A+Bau catalog context hardening applied: strict surface/context/anchor matching plus remediation exclusion is active.")


if __name__ == "__main__":
    main()
