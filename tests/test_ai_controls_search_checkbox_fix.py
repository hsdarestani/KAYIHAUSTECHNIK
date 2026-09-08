from pathlib import Path

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
        self.assertIn("A+Bau AI CONTROL + SEARCH FIX 2026-08-11", css)
        self.assertIn("kayi-next.js' %}?v=", base)
