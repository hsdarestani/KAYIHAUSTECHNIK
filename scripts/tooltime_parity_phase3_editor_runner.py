from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "tooltime_parity_phase3_editor.py"
text = SOURCE.read_text(encoding="utf-8")

fragile = '''    text, count = re.subn(r'<section class=\\"tt-card tt-document-top\\">.*?</section>', lambda _m: top, text, count=1, flags=re.S)\n    if count != 1:\n        raise RuntimeError("Phase 3 customer/project template block missing")\n'''
robust = '''    # Earlier ToolTime phases may append attributes/classes to this card. Resolve\n    # the customer section semantically instead of depending on exact markup.\n    heading_pos = text.find("Kunde und Projekt")\n    if heading_pos < 0:\n        raise RuntimeError("Phase 3 customer/project heading missing")\n    section_start = text.rfind("<section", 0, heading_pos)\n    next_section = text.find("<section", heading_pos + len("Kunde und Projekt"))\n    if section_start < 0 or next_section < 0 or next_section <= section_start:\n        raise RuntimeError("Phase 3 customer/project semantic section bounds missing")\n    text = text[:section_start] + top + "\\n" + text[next_section:]\n'''
if fragile not in text:
    raise RuntimeError("Phase 3 tolerant template bootstrap could not find the fragile source block")
text = text.replace(fragile, robust, 1)

code = compile(text, str(SOURCE), "exec")
namespace = {"__name__": "__main__", "__file__": str(SOURCE), "__package__": None}
exec(code, namespace)
