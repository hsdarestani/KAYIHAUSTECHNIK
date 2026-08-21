from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 16 CI CLOSEOUT 2026-08-21"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 16 closeout anchor missing: {label}")
    return text.replace(old, new, 1)


def patch_phase10_contract(module) -> None:
    rel = "tests/test_tooltime_phase10_appointments.py"
    text = module.read(rel)
    old = '        self.assertIn("Serientermine werden erst angeboten", template)\n'
    new = (
        '        self.assertIn(\'name="repeat_rule"\', template)\n'
        '        self.assertIn(\'value="daily"\', template)\n'
        '        self.assertIn(\'value="weekly"\', template)\n'
        '        self.assertIn(\'value="monthly"\', template)\n'
        '        self.assertIn("data-repeat-count", template)\n'
    )
    text = _replace_once(text, old, new, "stale Phase 10 recurrence assertion")
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def probe_legacy_reminder_contract(module) -> None:
    # Temporary assembly diagnostic: expose only the legacy test method so the
    # Phase 16 compatibility fix can preserve its exact reminder semantics.
    rel = "tests/test_workflow_release.py"
    text = module.read(rel)
    marker = "    def test_calendar_assigns_employees_and_creates_scheduled_reminders(self):"
    start = text.find(marker)
    if start < 0:
        raise RuntimeError("Phase 16 legacy reminder test method missing")
    next_test = text.find("\n    def test_", start + len(marker))
    if next_test < 0:
        next_test = min(len(text), start + 8000)
    snippet = text[start:next_test]
    print("A+BAU PHASE16 REMINDER CONTRACT PROBE START")
    print(snippet)
    print("A+BAU PHASE16 REMINDER CONTRACT PROBE END")


def run(module) -> None:
    patch_phase10_contract(module)
    probe_legacy_reminder_contract(module)
    print(f"{MARKER}: recurrence contract synchronized; reminder compatibility contract captured for final closeout.")
