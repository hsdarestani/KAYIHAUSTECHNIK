from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "tooltime_parity_pdf_layout_bridge.py"
text = SOURCE.read_text(encoding="utf-8")

# Ein unbenutztes Suchmuster enthielt absichtlich den zu patchenden Triple-Quote-
# Quelltext. Vor dem Compile wird nur diese Hilfsvariable entfernt; die eigentliche
# PDF-Patchlogik bleibt unverändert und wird anschließend syntaktisch validiert.
text, count = re.subn(
    r"\n    old_header = '''.*?\n    # The helper itself contains triple-quoted f-string syntax; patch through simpler anchors\.\n",
    "\n    # Der Header wird über stabile, einfache Anker gepatcht.\n",
    text,
    count=1,
    flags=re.S,
)
if count != 1:
    raise RuntimeError("PDF-Layout-Brücke: Quelltext-Reparaturanker fehlt.")

code = compile(text, str(SOURCE), "exec")
namespace = {"__name__": "__main__", "__file__": str(SOURCE), "__package__": None}
exec(code, namespace)
