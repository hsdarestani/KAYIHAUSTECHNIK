from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "scripts" / "fix_ai_controls_search_checkbox.py"
MARKER = "KAYI AI CONTROL + SEARCH FIX 2026-08-11"
VERSION = "20260811-2"

spec = importlib.util.spec_from_file_location("kayi_ai_controls_impl", IMPL)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load KAYI AI controls implementation")
impl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impl)
_original_patch_assistant_javascript = impl.patch_assistant_javascript


def final_form_widget_contract() -> None:
    """Respect the already-hardened checkbox class produced by the late UI layer."""
    path = ROOT / "erp" / "rebuild_views.py"
    text = path.read_text(encoding="utf-8")
    if "nx-checkbox-input" in text and "isinstance(field.widget, forms.CheckboxInput)" in text:
        return
    impl.patch_form_widget_classes()


def final_checkbox_layout() -> None:
    """Keep the checkbox beside its label instead of at the far edge of the column."""
    path = ROOT / "static" / "css" / "kayi-next.css"
    css = path.read_text(encoding="utf-8")
    addition = r'''

/* KAYI AI CONTROL + SEARCH FIX 2026-08-11 */
/* The late UI layer already makes checkboxes compact; this final rule fixes alignment. */
.nx-field:has(> .nx-checkbox-input) {
  display: flex !important;
  flex-wrap: wrap;
  align-items: center !important;
  justify-content: flex-start !important;
  gap: 10px !important;
  min-height: 48px;
  padding: 11px 13px !important;
}
.nx-field:has(> .nx-checkbox-input) > label {
  order: 2;
  width: auto !important;
  margin: 0 !important;
  cursor: pointer;
}
.nx-field:has(> .nx-checkbox-input) > .nx-checkbox-input {
  order: 1;
  justify-self: auto !important;
  flex: 0 0 20px;
  width: 20px !important;
  min-width: 20px !important;
  max-width: 20px !important;
  height: 20px !important;
  min-height: 20px !important;
  max-height: 20px !important;
  margin: 0 !important;
  padding: 0 !important;
}
.nx-field:has(> .nx-checkbox-input) > .errorlist,
.nx-field:has(> .nx-checkbox-input) > small {
  order: 3;
  flex-basis: 100%;
}
@media (max-width: 900px) {
  .nx-field:has(> .nx-checkbox-input) > .nx-checkbox-input {
    flex-basis: 22px;
    width: 22px !important;
    min-width: 22px !important;
    height: 22px !important;
    min-height: 22px !important;
  }
}
'''
    if MARKER not in css:
        path.write_text(css.rstrip() + addition, encoding="utf-8")


def final_patch_assistant_javascript() -> None:
    """The global assistant overlay is appended into kayi-next.js during assembly."""
    bundle = ROOT / "static" / "js" / "kayi-next.js"
    temporary = ROOT / "static" / "js" / "global-assistant.js"
    temporary.write_text(bundle.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        _original_patch_assistant_javascript()
        bundle.write_text(temporary.read_text(encoding="utf-8"), encoding="utf-8")
    finally:
        if temporary.exists():
            temporary.unlink()


def final_bump_cache() -> None:
    """Force browsers to load the new assistant bundle instead of cached KI behavior."""
    path = ROOT / "templates" / "rebuild" / "base.html"
    text = path.read_text(encoding="utf-8")
    updated = re.sub(
        r"(kayi-next\.js'\s*%\}\?v=)[^\"'\s<]+",
        rf"\g<1>{VERSION}",
        text,
    )
    if updated == text and VERSION not in text:
        raise RuntimeError("Could not bump KAYI Next JavaScript cache version")
    path.write_text(updated, encoding="utf-8")


def final_regression_tests() -> None:
    test = r'''from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from erp import assistant_views
from erp.models import Employee, Organization, UserProfile


class AIControlAndSearchRegressionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI AI control regression")
        self.user = User.objects.create_user("ai-control-admin", password="safe-test-password")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.ashkan = Employee.objects.create(
            organization=self.org,
            employee_number="M-2026-9001",
            first_name="Ashkan",
            last_name="Test",
            email="ashkan@example.test",
            active=True,
        )
        Employee.objects.create(
            organization=self.org,
            employee_number="M-2026-9002",
            first_name="Hossein",
            last_name="Farahani",
            email="hossein@example.test",
            active=True,
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="ai-control-admin", password="safe-test-password"))

    def test_employee_query_really_filters_records(self):
        response = self.client.get(reverse("next-employees"), {"q": "ashkan"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ashkan Test")
        self.assertNotContains(response, "Hossein Farahani")
        self.assertContains(response, 'value="ashkan"')

    def test_real_entity_context_finds_ashkan_and_not_unrelated_employee(self):
        matches = assistant_views._entity_search_context(self.org, "find ashkan")
        self.assertEqual([m["id"] for m in matches if m["route"] == "employees"], [self.ashkan.pk])

    def test_checkbox_and_date_controls_are_part_of_final_ai_contract(self):
        root = Path(__file__).resolve().parents[1]
        js = (root / "static/js/kayi-next.js").read_text(encoding="utf-8")
        backend = (root / "erp/assistant_views.py").read_text(encoding="utf-8")
        form = (root / "erp/rebuild_views.py").read_text(encoding="utf-8")
        css = (root / "static/css/kayi-next.css").read_text(encoding="utf-8")
        base = (root / "templates/rebuild/base.html").read_text(encoding="utf-8")
        for marker in ("normalizeControlValue", "datetime-local", "parseBoolean", "navigate_record"):
            self.assertIn(marker, js)
        for marker in ("now_local", "entity_matches", "value=true", "YYYY-MM-DDTHH:MM", "navigate_record"):
            self.assertIn(marker, backend)
        self.assertIn("nx-checkbox-input", form)
        self.assertIn("KAYI AI CONTROL + SEARCH FIX 2026-08-11", css)
        self.assertIn("kayi-next.js' %}?v=", base)
'''
    path = ROOT / "tests" / "test_ai_controls_search_checkbox_fix.py"
    path.write_text(test, encoding="utf-8")


def final_guard() -> None:
    checks = {
        "erp/rebuild_views.py": ["nx-checkbox-input", "forms.CheckboxInput"],
        "erp/rebuild_ops.py": ["query = request.GET.get(\"q\"", "first_name__icontains=query"],
        "templates/rebuild/employees.html": ["Mitarbeiter nach Name", "Kein Mitarbeiter für"],
        "erp/assistant_views.py": ["_entity_search_context", "now_local", "navigate_record", "YYYY-MM-DDTHH:MM"],
        "static/js/kayi-next.js": [MARKER, "normalizeControlValue", "setControlValue", "navigate_record"],
        "static/css/kayi-next.css": [MARKER, "nx-checkbox-input", "justify-content: flex-start"],
        "templates/rebuild/base.html": ["kayi-next.js' %}?v="],
        "tests/test_ai_controls_search_checkbox_fix.py": ["test_employee_query_really_filters_records"],
    }
    missing = []
    for rel, markers in checks.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                missing.append(f"{rel}: {marker}")
    if missing:
        raise RuntimeError("AI control/search final guard failed: " + "; ".join(missing))


impl.patch_form_widget_classes = final_form_widget_contract
impl.patch_checkbox_layout = final_checkbox_layout
impl.patch_assistant_javascript = final_patch_assistant_javascript
impl.bump_cache = final_bump_cache
impl.install_regression_tests = final_regression_tests
impl.guard = final_guard
impl.main()