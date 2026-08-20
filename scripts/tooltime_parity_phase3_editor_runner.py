from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "tooltime_parity_phase3_editor.py"
text = SOURCE.read_text(encoding="utf-8")

marker = 'raise RuntimeError("Phase 3 customer/project template block missing")'
marker_pos = text.find(marker)
block_start = text.rfind("    text, count = re.subn(", 0, marker_pos)
block_end = text.find("\n", marker_pos)
if marker_pos < 0 or block_start < 0 or block_end < 0:
    raise RuntimeError("Phase 3 tolerant template bootstrap could not locate the old patch block")
block_end += 1

robust = '''    # Earlier ToolTime phases may append attributes/classes to this card. Resolve
    # the customer section semantically instead of depending on exact markup.
    heading_pos = text.find("Kunde und Projekt")
    if heading_pos < 0:
        raise RuntimeError("Phase 3 customer/project heading missing")
    section_start = text.rfind("<section", 0, heading_pos)
    next_section = text.find("<section", heading_pos + len("Kunde und Projekt"))
    if section_start < 0 or next_section < 0 or next_section <= section_start:
        raise RuntimeError("Phase 3 customer/project semantic section bounds missing")
    text = text[:section_start] + top + "\\n" + text[next_section:]
'''
text = text[:block_start] + robust + text[block_end:]

code = compile(text, str(SOURCE), "exec")
namespace = {"__name__": "__main__", "__file__": str(SOURCE), "__package__": None}
exec(code, namespace)
