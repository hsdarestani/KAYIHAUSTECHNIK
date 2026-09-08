from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU ANGEBOT/FREIGABE CI ALIGNMENT 2026-09-08"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"CI alignment target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.write_text(text, encoding="utf-8")


# The final dashboard-action layer owns this global cache key. The authorization
# bridge must not change unrelated base-shell asset versions.
base_rel = "templates/rebuild/base.html"
base = read(base_rel)
base, count = re.subn(
    r"ab-bau-v3-finance-mobile-pdf-hotfix\.css\?v=[^\"'\s<]+",
    "ab-bau-v3-finance-mobile-pdf-hotfix.css?v=20260908-dashboard-actions-1",
    base,
    count=1,
)
if count != 1:
    raise RuntimeError("Final finance/mobile/PDF stylesheet cache-key anchor missing")
write(base_rel, base)


# The old appointment parity contract deliberately hid internal pricing. That is no
# longer the requested product behavior: the Termin authorization editor now reuses
# the exact Angebot pricing editor for authorized staff. Keep the customer-facing
# signed snapshot rules separate; only align this obsolete office-UI assertion.
appointment_test_rel = "tests/test_tooltime_appointment_process_parity.py"
if (ROOT / appointment_test_rel).exists():
    test = read(appointment_test_rel)
    test = test.replace(
        "def test_appointment_services_store_prices_but_appointment_ui_hides_them(self):",
        "def test_appointment_authorization_reuses_angebot_pricing_fields(self):",
        1,
    )
    old = '        self.assertNotContains(detail, "Einkaufspreis")\n'
    new = '''        self.assertContains(detail, "Einkaufspreis")
        self.assertContains(detail, "Aufschlag")
'''
    if old in test:
        test = test.replace(old, new, 1)
    elif 'self.assertContains(detail, "Einkaufspreis")' not in test:
        raise RuntimeError("Appointment pricing visibility regression anchor changed")
    write(appointment_test_rel, test)


# Guard the two exact regressions that blocked PR #184 while keeping the canonical
# Angebot integration untouched.
if "ab-bau-v3-finance-mobile-pdf-hotfix.css?v=20260908-dashboard-actions-1" not in read(base_rel):
    raise RuntimeError("Dashboard-owned finance stylesheet cache key was not restored")
if (ROOT / appointment_test_rel).exists():
    final_test = read(appointment_test_rel)
    if 'self.assertNotContains(detail, "Einkaufspreis")' in final_test:
        raise RuntimeError("Obsolete hidden-EK appointment assertion survived")
    if 'self.assertContains(detail, "Einkaufspreis")' not in final_test:
        raise RuntimeError("Shared Angebot pricing visibility assertion missing")

print(f"{MARKER}: obsolete appointment pricing assertion aligned; unrelated base cache key preserved.")
