from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tests" / "test_tooltime_rebuild.py"
LANDING = ROOT / "templates" / "store" / "landing.html"
URLS = ROOT / "erp" / "store_urls.py"
MARKER = "A+Bau public landing route contract 2026-08-18"

for required in (TEST, LANDING, URLS):
    if not required.exists():
        raise RuntimeError(f"Public landing assembly target is missing: {required.relative_to(ROOT)}")

text = TEST.read_text(encoding="utf-8")
legacy = '            "/": "next-dashboard",\n'
current = '            "/": "store-landing",\n'
if legacy in text:
    text = text.replace(legacy, current, 1)
elif current not in text:
    raise RuntimeError("Primary root-route regression contract changed unexpectedly")
TEST.write_text(text, encoding="utf-8")

urls = URLS.read_text(encoding="utf-8")
if 'path("", store_views.landing_page, name="store-landing")' not in urls:
    raise RuntimeError("Public A+Bau landing route is not first-class in the assembled store URL layer")

landing = LANDING.read_text(encoding="utf-8")
for expected in (
    "Betriebssoftware für Bau & Handwerk",
    "Vom ersten Termin",
    "Ein System statt fünf einzelner Tools",
    "KI & 3D Room Planner",
    "brand/ab-bau-logo.png",
):
    if expected not in landing:
        raise RuntimeError(f"Public landing lost required product marker: {expected}")

print(f"{MARKER}: anonymous / presents the product; authenticated dashboard routing remains handled by landing_page().")
