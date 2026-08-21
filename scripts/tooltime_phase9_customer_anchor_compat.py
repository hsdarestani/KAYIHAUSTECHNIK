from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "tooltime_parity_phase9_core_crud.py"

text = PATH.read_text(encoding="utf-8")
old = '''    elif '"address": ", ".join(part for part in [customer.street' not in text:
        raise RuntimeError("Phase 9 customer location API anchor missing")
'''
new = '''    elif '"address": ", ".join(part for part in [customer.street' not in text and not ("customer.street" in text and "customer.display_name" in text):
        raise RuntimeError("Phase 9 customer location API anchor missing")
'''
if new not in text:
    if old not in text:
        raise RuntimeError("Phase 9 customer location compatibility guard anchor changed")
    text = text.replace(old, new, 1)
    PATH.write_text(text, encoding="utf-8")

final = PATH.read_text(encoding="utf-8")
if 'and not ("customer.street" in text and "customer.display_name" in text)' not in final:
    raise RuntimeError("Phase 9 customer location compatibility guard was not installed")
compile(final, str(PATH), "exec")
print("ToolTime Phase 9 customer-location source guard is tolerant of the final customer payload.")
