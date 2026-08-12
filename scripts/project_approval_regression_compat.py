from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Regression compatibility target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


def patch_field_authorization_test() -> None:
    rel = "tests/test_field_authorization.py"
    text = read(rel)
    old = '''    def test_quick_job_can_reuse_existing_customer(self):
        response = self.client.post(reverse("field-quick-job"), data={"customer_mode": "existing", "customer_id": self.customer.pk, "title": "Spontaner Wasserschaden", "issue": "Wasser unter Spüle"})
        self.assertEqual(response.status_code, 302)
        created = Project.objects.exclude(pk=self.project.pk).get(customer=self.customer)
        event = CalendarEvent.objects.get(project=created)
        self.assertEqual(created.status, "confirmed")
        self.assertTrue(created.members.filter(pk=self.employee.pk).exists())
        self.assertTrue(event.attendees.filter(pk=self.employee.pk).exists())
        self.assertIn(f"/appointments/{event.pk}/", response["Location"])
'''
    new = '''    def test_quick_job_can_reuse_existing_customer(self):
        response = self.client.post(reverse("field-quick-job"), data={
            "customer_mode": "existing",
            "customer_id": self.customer.pk,
            "title": "Spontaner Wasserschaden",
            "issue": "Wasser unter Spüle",
            "positions_json": '[{"title":"Wasserschaden prüfen","description":"Wasser unter Spüle","quantity":"1","unit":"Psch.","position_type":"labour"}]',
        })
        self.assertEqual(response.status_code, 302)
        created = Project.objects.exclude(pk=self.project.pk).get(customer=self.customer)
        event = CalendarEvent.objects.get(project=created)
        self.assertEqual(created.status, "review")
        self.assertEqual(created.approval_flow.status, "submitted")
        quote = created.quotes.get()
        position = quote.items.get()
        self.assertEqual(position.unit_price, 0)
        self.assertFalse(position.approved)
        self.assertTrue(created.members.filter(pk=self.employee.pk).exists())
        self.assertTrue(event.attendees.filter(pk=self.employee.pk).exists())
        self.assertIn(f"/field/projects/{created.pk}/freigabe/", response["Location"])
'''
    if new in text:
        return
    if old not in text:
        raise RuntimeError("Legacy quick-job regression block changed")
    write(rel, text.replace(old, new, 1))


def patch_tooltime_test() -> None:
    rel = "tests/test_tooltime_rebuild.py"
    text = read(rel)
    old = 'self.assertIn("Schnellauftrag", field_home)'
    new = 'self.assertIn("Projekt aufnehmen", field_home)'
    if new in text:
        return
    if old not in text:
        raise RuntimeError("ToolTime field-home Schnellauftrag assertion changed")
    write(rel, text.replace(old, new, 1))


def guard() -> None:
    field = read("tests/test_field_authorization.py")
    tooltime = read("tests/test_tooltime_rebuild.py")
    if 'created.status, "review"' not in field or 'created.approval_flow.status, "submitted"' not in field:
        raise RuntimeError("Field authorization test still expects direct project confirmation")
    if 'self.assertIn("Projekt aufnehmen", field_home)' not in tooltime:
        raise RuntimeError("ToolTime test still expects obsolete Schnellauftrag copy")


patch_field_authorization_test()
patch_tooltime_test()
guard()
print("A+Bau regression contracts aligned to price-free technician intake and owner approval.")
