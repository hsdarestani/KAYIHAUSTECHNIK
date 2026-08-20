from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "tooltime_parity_phase3_editor.py"
text = SOURCE.read_text(encoding="utf-8")

# Replace the old exact-class customer-card patch with semantic section bounds.
marker = 'raise RuntimeError("Phase 3 customer/project template block missing")'
marker_pos = text.find(marker)
block_start = text.rfind("    text, count = re.subn(", 0, marker_pos)
block_end = text.find("\n", marker_pos)
if marker_pos < 0 or block_start < 0 or block_end < 0:
    raise RuntimeError("Phase 3 tolerant template bootstrap could not locate the old customer patch block")
block_end += 1
robust_customer = '''    # Earlier ToolTime phases may append attributes/classes to this card. Resolve
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
text = text[:block_start] + robust_customer + text[block_end:]

# Phase 1 can insert extra modals after the main document form. Insert the status
# toolbar immediately after the actual document form instead of before a named modal.
toolbar_marker = 'raise RuntimeError("Phase 3 main document form closing anchor missing")'
toolbar_marker_pos = text.find(toolbar_marker)
toolbar_block_start = text.rfind('    if "tt-quote-statusbar" not in text:', 0, toolbar_marker_pos)
toolbar_block_end = text.find("    write(rel, text)", toolbar_marker_pos)
if toolbar_marker_pos < 0 or toolbar_block_start < 0 or toolbar_block_end < 0:
    raise RuntimeError("Phase 3 tolerant template bootstrap could not locate the old toolbar patch block")
robust_toolbar = '''    if "tt-quote-statusbar" not in text:
        form_start = text.find('<form class="tt-document-form"')
        form_close = text.find("</form>", form_start)
        if form_start < 0 or form_close < 0:
            raise RuntimeError("Phase 3 main document form semantic bounds missing")
        insert_at = form_close + len("</form>")
        text = text[:insert_at] + "\\n" + toolbar + text[insert_at:]
'''
text = text[:toolbar_block_start] + robust_toolbar + text[toolbar_block_end:]

code = compile(text, str(SOURCE), "exec")
namespace = {"__name__": "__main__", "__file__": str(SOURCE), "__package__": None}
exec(code, namespace)
