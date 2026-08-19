from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "erp/rebuild_views.py"
MARKER = "A+BAU INVOICE COMPLIANCE CATALOG PERFORMANCE FIX 2026-08-20"

if not VIEWS.exists():
    raise RuntimeError("erp/rebuild_views.py is missing after source assembly")

text = VIEWS.read_text(encoding="utf-8")
slow = '"catalog": m.CatalogItem.objects.filter(organization=org, active=True).order_by("name")[:500],'
fast = '"catalog": _fast_catalog_preview(org),'

# The compliance overlay owns two invoice render paths: validation-error and
# normal GET. Both must preserve the lazy/fast first-paint contract installed
# by the runtime performance layer.
text = text.replace(slow, fast)

if "def _fast_catalog_preview(org, limit=18):" not in text:
    raise RuntimeError("Fast catalog helper is unavailable after compliance overlay")
if text.count("_fast_catalog_preview(org)") < 2:
    raise RuntimeError("Quote and invoice editors are not both using fast catalog preview")
if slow in text:
    raise RuntimeError("Synchronous 500-item invoice catalog path survived compliance overlay")

if MARKER not in text:
    text += f"\n# {MARKER}\n"

VIEWS.write_text(text, encoding="utf-8")
print("Invoice compliance catalog performance contract restored for quote + invoice editors.")
