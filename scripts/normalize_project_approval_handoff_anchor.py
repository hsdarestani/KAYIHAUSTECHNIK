from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "erp" / "field_authorization_views.py"
text = path.read_text(encoding="utf-8")
marker = "A_BAU_PROJECT_APPROVAL_HANDOFF"
if marker not in text:
    anchor = "def field_job_detail(request, pk):\n    org, event = _event_for(request, pk)\n"
    if anchor not in text:
        raise RuntimeError("Final field_job_detail entry anchor changed")
    block = anchor + '''    # A_BAU_PROJECT_APPROVAL_HANDOFF\n    from .project_intake_views import redirect_field_project_flow\n    approval_response = redirect_field_project_flow(request, event)\n    if approval_response is not None:\n        return approval_response\n'''
    text = text.replace(anchor, block, 1)
    path.write_text(text, encoding="utf-8")
print("A+Bau project approval handoff anchor normalized on final field source.")
