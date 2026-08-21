from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "tooltime_catalogue_exact_parity.py"
text = SOURCE.read_text(encoding="utf-8")

old = 'timezone.make_aware(timezone.datetime.min)'
new = 'timezone.now().replace(year=1970, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)'
if old not in text:
    raise RuntimeError("Catalogue exact-parity datetime compatibility anchor changed")
text = text.replace(old, new, 1)

namespace = {"__name__": "__main__", "__file__": str(SOURCE), "__package__": None}
exec(compile(text, str(SOURCE), "exec"), namespace)
