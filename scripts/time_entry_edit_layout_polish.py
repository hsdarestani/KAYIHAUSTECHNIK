from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "rebuild" / "time_entry_form.html"
TEST = ROOT / "tests" / "test_time_entry_edit_layout_polish.py"
MARKER = "A+BAU TIME ENTRY EDIT LAYOUT 2026-08-18"


if not TEMPLATE.exists():
    raise RuntimeError("Time-entry edit template is missing after source assembly")

text = TEMPLATE.read_text(encoding="utf-8")

# This form already has its own KAYI Next structure. Keep the generic runtime
# form enhancer from wrapping it in a second card/grid system.
if 'data-no-form-polish' not in text:
    old = '<form method="post">'
    new = '<form method="post" class="nx-time-edit-form" data-no-form-polish>'
    if old not in text:
        raise RuntimeError("Time-entry edit form anchor changed")
    text = text.replace(old, new, 1)

if 'nx-time-edit-head' not in text:
    old = '<div class="nx-pagehead">'
    new = '<div class="nx-pagehead nx-time-edit-head">'
    if old not in text:
        raise RuntimeError("Time-entry edit page-head anchor changed")
    text = text.replace(old, new, 1)

if MARKER not in text:
    anchor = '<div class="nx-pagehead nx-time-edit-head">'
    if anchor not in text:
        raise RuntimeError("Time-entry edit styled page-head anchor changed")
    style = r'''<style>
/* A+BAU TIME ENTRY EDIT LAYOUT 2026-08-18 */
.nx-time-edit-head,
.nx-time-edit-card {
  width: min(100%, 1160px);
  max-width: none;
}
.nx-time-edit-head {
  align-items: flex-end;
  gap: 20px;
}
.nx-time-edit-head > div {
  min-width: 0;
}
.nx-time-edit-card {
  margin-right: auto;
  padding: 24px 26px 22px;
  border-radius: 20px;
  box-shadow: 0 12px 30px rgba(16, 24, 40, .035);
}
.nx-time-edit-card .nx-time-edit-form {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.nx-time-edit-card .next-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px 20px;
  align-items: start;
}
.nx-time-edit-card .next-field {
  min-width: 0;
  display: grid;
  gap: 7px;
  margin: 0;
}
.nx-time-edit-card .next-field > span {
  font-size: 12.5px;
  font-weight: 800;
  color: #25282d;
}
.nx-time-edit-card .next-control {
  width: 100%;
  min-width: 0;
  min-height: 46px;
  border-radius: 12px;
}
.nx-time-edit-card textarea.next-control {
  min-height: 118px;
  resize: vertical;
}
.nx-time-edit-card .next-span-2 {
  grid-column: 1 / -1;
}
.nx-time-edit-card .next-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid #e3dfd6;
}
.nx-time-edit-card .next-actions .nx-btn {
  min-height: 42px;
}
@media (max-width: 760px) {
  .nx-time-edit-head {
    align-items: flex-start;
    gap: 12px;
  }
  .nx-time-edit-head > .nx-btn {
    align-self: flex-start;
  }
  .nx-time-edit-card {
    width: 100%;
    padding: 17px;
    border-radius: 16px;
  }
  .nx-time-edit-card .next-grid {
    grid-template-columns: 1fr;
    gap: 14px;
  }
  .nx-time-edit-card .next-span-2 {
    grid-column: auto;
  }
  .nx-time-edit-card .next-actions {
    display: grid;
    grid-template-columns: 1fr;
  }
  .nx-time-edit-card .next-actions .nx-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>'''
    text = text.replace(anchor, style + anchor, 1)

TEMPLATE.write_text(text, encoding="utf-8")

TEST.write_text(
    r'''from pathlib import Path

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
''',
    encoding="utf-8",
)

print(f"{MARKER}: time correction form is balanced on desktop and isolated from generic form polishing.")
