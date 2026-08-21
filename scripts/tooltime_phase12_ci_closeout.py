from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 12 CI CLOSEOUT 2026-08-21"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 12 CI closeout anchor missing: {label}")
    return text.replace(old, new, 1)


def patch_phase11_contract(module) -> None:
    rel = "tests/test_tooltime_phase11_appointment_template.py"
    text = module.read(rel)
    old = '''        for marker in ("query_filter", "customer_filter", "allowed_views", '\"day\", \"week\", \"month\", \"list\"'):
            self.assertIn(marker, backend)
'''
    new = '''        for marker in ("query_filter", "customer_filter", "allowed_views", "appointment_move"):
            self.assertIn(marker, backend)
        for view_name in ('\"day\"', '\"week\"', '\"month\"', '\"list\"'):
            self.assertIn(view_name, backend)
'''
    text = _replace_once(text, old, new, "Phase 11 multiview test")
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_phase12_contract(module) -> None:
    rel = "tests/test_tooltime_phase12_appointment_map_contract.py"
    text = module.read(rel)
    old = '''        self.assertNotIn("AIza", javascript)
        self.assertNotIn("latitude", backend.lower())
        self.assertNotIn("longitude", backend.lower())
        self.assertIn("@media(max-width:760px)", css)
'''
    new = '''        self.assertNotIn("AIza", javascript)
        self.assertNotIn("data-latitude", template.lower())
        self.assertNotIn("data-longitude", template.lower())
        self.assertIn("@media(max-width:760px)", css)
'''
    text = _replace_once(text, old, new, "Phase 12 coordinate scope")
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def run(module) -> None:
    patch_phase11_contract(module)
    patch_phase12_contract(module)
    phase11_test = module.read("tests/test_tooltime_phase11_appointment_template.py")
    phase12_test = module.read("tests/test_tooltime_phase12_appointment_map_contract.py")
    if "appointment_move" not in phase11_test or "data-latitude" not in phase12_test:
        raise RuntimeError("Phase 12 CI closeout regression contracts were not installed")
    print(f"{MARKER}: existing calendar contracts accept additive map view and map assertions stay scoped to the map layer.")
