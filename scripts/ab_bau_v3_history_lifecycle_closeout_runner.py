from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "ab_bau_v3_history_lifecycle_closeout.py"
text = TARGET.read_text(encoding="utf-8")
old = '''        context_anchor = '        "invoice_gross": invoice_gross,\\n'\n        if context_anchor not in project:\n            raise RuntimeError("V3 closeout project context anchor missing")\n        project = project.replace(\n            context_anchor,\n            context_anchor\n            + '        "history": history,\\n'\n            + '        "tooltime_status": tooltime_status,\\n'\n            + '        "has_planned_appointments": has_planned_appointments,\\n',\n            1,\n        )\n'''
new = '''        project_context_anchor = '    return render(request, "rebuild/project_detail.html", {\\n'\n        if project_context_anchor not in project:\n            raise RuntimeError("V3 closeout project render-context anchor missing")\n        project = project.replace(\n            project_context_anchor,\n            project_context_anchor\n            + '        "history": history,\\n'\n            + '        "tooltime_status": tooltime_status,\\n'\n            + '        "has_planned_appointments": has_planned_appointments,\\n',\n            1,\n        )\n'''
if old not in text and new not in text:
    raise RuntimeError("V3 closeout project-context compatibility anchor missing")
if old in text:
    TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")

runpy.run_path(str(TARGET), run_name="__main__")
