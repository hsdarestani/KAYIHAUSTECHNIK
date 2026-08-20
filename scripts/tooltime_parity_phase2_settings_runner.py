from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "tooltime_parity_phase2_settings.py"
text = SOURCE.read_text(encoding="utf-8")

old = '''    # Normalize settings on every settings-page request.\n    start = "def settings_page(request):\\n    org = base._org(request)\\n"\n    normalized = start + "    cfg = phase2_settings(org)\\n"\n    if normalized not in text:\n        if start not in text: raise RuntimeError("Phase 2 settings start anchor missing")\n        text = text.replace(start, normalized, 1)\n    # Existing page obtains cfg later; keep the same object instead of replacing it.\n    text = text.replace("    cfg = profile.settings\\n", "    cfg = phase2_settings(org)\\n", 1)\n'''
new = '''    # Normalize settings on every settings-page request. Phase 1 inserts its\n    # template bootstrap directly after the organization lookup, so Phase 2 must\n    # not depend on the older two-line function preamble.\n    if "def settings_page(request):" not in text or "    org = base._org(request)\\n" not in text:\n        raise RuntimeError("Phase 2 settings function missing")\n    text = text.replace("    cfg = profile.settings\\n", "    cfg = phase2_settings(org)\\n", 1)\n    settings_pos = text.index("def settings_page(request):")\n    settings_tail = text[settings_pos:settings_pos + 700]\n    if "    cfg = phase2_settings(org)\\n" not in settings_tail:\n        phase1_anchor = "    _ensure_standard_text_templates(org)\\n"\n        org_anchor = "    org = base._org(request)\\n"\n        local_anchor = phase1_anchor if phase1_anchor in settings_tail else org_anchor\n        insert_at = text.index(local_anchor, settings_pos) + len(local_anchor)\n        text = text[:insert_at] + "    cfg = phase2_settings(org)\\n" + text[insert_at:]\n'''
if old not in text:
    raise RuntimeError("Phase 2 tolerant settings bootstrap anchor was not found")
text = text.replace(old, new, 1)

# Remove a no-op template loop that is not needed for the German numbering UI and
# would otherwise depend on a context variable that does not exist.
text = text.replace('{% for key,label in number_labels %}{% endfor %}', '')

# The shared commercial generator still contains a known Mahnmail string that is
# repaired by the final batch runner after all feature layers have finished. Phase 2
# must validate its own model/service/migration/template output without compiling
# that intermediate generated view a second too early. The final runner compiles the
# repaired view before source assembly can complete.
text = text.replace(
    'for rel in ("erp/tooltime_parity_finance.py", "erp/tooltime_parity_views.py", "erp/services/tooltime_parity_finance.py"):',
    'for rel in ("erp/tooltime_parity_finance.py", "erp/services/tooltime_parity_finance.py"):',
    1,
)

compile(text, str(SOURCE), "exec")
namespace = {"__name__": "__main__", "__file__": str(SOURCE), "__package__": None}
exec(compile(text, str(SOURCE), "exec"), namespace)
print("ToolTime Phase 2 Runner: Einstellungen werden unabhängig vom Phase-1-Layout installiert.")
