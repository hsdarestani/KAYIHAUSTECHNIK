from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class TimeEntryEditLayoutPolishTests(SimpleTestCase):
    def test_time_edit_uses_one_scoped_form_system(self):
        template = (ROOT / "templates" / "rebuild" / "time_entry_form.html").read_text(encoding="utf-8")
        self.assertIn("A+BAU TIME ENTRY EDIT LAYOUT 2026-08-18", template)
        self.assertIn('class="nx-pagehead nx-time-edit-head"', template)
        self.assertIn('class="nx-time-edit-form" data-no-form-polish', template)
        self.assertIn("width: min(100%, 1160px)", template)
        self.assertIn("max-width: none", template)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", template)
        self.assertIn("@media (max-width: 760px)", template)
        self.assertIn("grid-template-columns: 1fr", template)

    def test_time_edit_business_fields_and_actions_remain_present(self):
        template = (ROOT / "templates" / "rebuild" / "time_entry_form.html").read_text(encoding="utf-8")
        for field in ("started_at", "ended_at", "break_minutes", "approved", "description"):
            self.assertIn(f'name="{field}"', template)
        self.assertIn("Korrektur speichern", template)
        self.assertIn("Abbrechen", template)
