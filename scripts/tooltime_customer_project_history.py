from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "scripts" / "tooltime_customer_project_history_impl.py"
text = IMPL.read_text(encoding="utf-8")

old = '''    project_anchor = '    path("projects/<int:pk>/", views.project_detail, name="next-project-detail"),\\n'\n    project_route = '    path("projects/<int:pk>/aktionen/", views.project_lifecycle, name="next-project-lifecycle"),\\n'\n    if project_route not in text:\n        if project_anchor not in text:\n            raise RuntimeError("Project detail URL anchor missing")\n        text = text.replace(project_anchor, project_anchor + project_route, 1)\n'''
new = '''    project_route = '    path("projects/<int:pk>/aktionen/", views.project_lifecycle, name="next-project-lifecycle"),\\n'\n    if project_route not in text:\n        marker = 'name="next-project-detail"'\n        marker_pos = text.find(marker)\n        if marker_pos < 0:\n            raise RuntimeError("Project detail URL semantic anchor missing")\n        line_end = text.find("\\n", marker_pos)\n        if line_end < 0:\n            raise RuntimeError("Project detail URL line boundary missing")\n        text = text[:line_end + 1] + project_route + text[line_end + 1:]\n'''
if old not in text:
    raise RuntimeError("Customer/project history wrapper could not locate legacy project-route patch")
text = text.replace(old, new, 1)

namespace = {"__name__": "__main__", "__file__": str(IMPL), "__package__": None}
exec(compile(text, str(IMPL), "exec"), namespace)
