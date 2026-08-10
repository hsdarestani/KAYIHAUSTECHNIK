from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "erp" / "room_planner_views.py"
text = path.read_text(encoding="utf-8")
marker = "KAYI_CUSTOMER_3D_KI_CONSENT"
if marker not in text:
    old = '''    org, project = _project(request, project_pk)\n    try:\n        payload = json.loads(request.body.decode("utf-8"))\n'''
    new = '''    org, project = _project(request, project_pk)\n    # KAYI_CUSTOMER_3D_KI_CONSENT\n    from erp.store_views import has_ai_consent\n    if not has_ai_consent(request.user):\n        return JsonResponse({\n            "ok": False,\n            "error": "Vor der KI-Verarbeitung ist deine ausdrückliche Einwilligung in den Einstellungen erforderlich.",\n            "consent_required": True,\n            "settings_url": "/settings/next/",\n        }, status=428)\n    try:\n        payload = json.loads(request.body.decode("utf-8"))\n'''
    start = text.find("def room_planner_ai(")
    end = text.find("def room_planner_vision(", start)
    if start < 0 or end < 0:
        raise RuntimeError("Room Planner KI view contract missing")
    segment = text[start:end]
    if old not in segment:
        raise RuntimeError("Room Planner KI consent insertion point changed")
    segment = segment.replace(old, new, 1)
    text = text[:start] + segment + text[end:]
    path.write_text(text, encoding="utf-8")

text = path.read_text(encoding="utf-8")
start = text.find("def room_planner_ai(")
end = text.find("def room_planner_vision(", start)
segment = text[start:end]
for needle in (marker, "has_ai_consent", "consent_required", '"settings_url": "/settings/next/"'):
    if needle not in segment:
        raise RuntimeError(f"3D KI consent guard missing: {needle}")
print("KAYI 3D KI assistant now enforces explicit store consent before OpenAI processing.")
