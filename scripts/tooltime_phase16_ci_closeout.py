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


def patch_legacy_event_form_compatibility(module) -> None:
    # Recurrence bookkeeping is system-owned metadata. Keeping it non-editable
    # prevents generic/legacy ModelForms from suddenly requiring Phase 16 fields,
    # while the Next appointment flow continues to assign them explicitly.
    model_rel = "erp/models.py"
    model = module.read(model_rel)
    old_model = '''    recurrence_series = models.UUIDField(null=True, blank=True, db_index=True)
    recurrence_rule = models.CharField(
        max_length=16,
        choices=[
            ("none", "Keine Wiederholung"),
            ("daily", "Täglich"),
            ("weekly", "Wöchentlich"),
            ("monthly", "Monatlich"),
        ],
        default="none",
    )
    recurrence_index = models.PositiveIntegerField(default=0)
'''
    new_model = '''    recurrence_series = models.UUIDField(null=True, blank=True, db_index=True, editable=False)
    recurrence_rule = models.CharField(
        max_length=16,
        choices=[
            ("none", "Keine Wiederholung"),
            ("daily", "Täglich"),
            ("weekly", "Wöchentlich"),
            ("monthly", "Monatlich"),
        ],
        default="none",
        editable=False,
    )
    recurrence_index = models.PositiveIntegerField(default=0, editable=False)
'''
    model = _replace_once(model, old_model, new_model, "CalendarEvent recurrence metadata editability")
    module.write(model_rel, model)
    compile(model, str(ROOT / model_rel), "exec")

    migration_rel = "erp/migrations/0021_calendar_event_recurrence.py"
    migration = module.read(migration_rel)
    migration = _replace_once(
        migration,
        'field=models.UUIDField(blank=True, db_index=True, null=True),',
        'field=models.UUIDField(blank=True, db_index=True, editable=False, null=True),',
        "recurrence series migration state",
    )
    migration = _replace_once(
        migration,
        '''                default="none",
                max_length=16,
            ),''',
        '''                default="none",
                editable=False,
                max_length=16,
            ),''',
        "recurrence rule migration state",
    )
    migration = _replace_once(
        migration,
        'field=models.PositiveIntegerField(default=0),',
        'field=models.PositiveIntegerField(default=0, editable=False),',
        "recurrence index migration state",
    )
    module.write(migration_rel, migration)
    compile(migration, str(ROOT / migration_rel), "exec")

    test_rel = "tests/test_tooltime_phase16_legacy_form_compatibility.py"
    test = r'''from django.test import SimpleTestCase

from erp.models import CalendarEvent


class ToolTimePhase16LegacyFormCompatibilityTests(SimpleTestCase):
    def test_recurrence_bookkeeping_is_internal_model_metadata(self):
        for name in ("recurrence_series", "recurrence_rule", "recurrence_index"):
            self.assertFalse(CalendarEvent._meta.get_field(name).editable, name)
'''
    module.write(test_rel, test)
    compile(test, str(ROOT / test_rel), "exec")


def run(module) -> None:
    patch_phase10_contract(module)
    patch_legacy_event_form_compatibility(module)
    print(f"{MARKER}: recurrence contract synchronized and legacy event forms remain compatible with scheduled reminders.")
