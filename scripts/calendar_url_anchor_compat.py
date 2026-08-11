from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "erp" / "rebuild_urls.py"
text = path.read_text(encoding="utf-8")
move_route = '    path("appointments/<int:pk>/move/", views.appointment_move, name="next-appointment-move"),\n'

if move_route not in text:
    marker = 'name="next-appointment-detail"'
    marker_pos = text.find(marker)
    if marker_pos < 0:
        raise RuntimeError("appointment detail route not found")
    line_start = text.rfind("\n", 0, marker_pos) + 1
    text = text[:line_start] + move_route + text[line_start:]
    path.write_text(text, encoding="utf-8")

print("KAYI calendar route compatibility anchor installed")
