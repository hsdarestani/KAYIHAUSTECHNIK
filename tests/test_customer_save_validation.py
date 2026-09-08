from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from erp import rebuild_views
from erp.models import Customer, Organization, UserProfile


class CustomerSaveValidationRegressionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI customer save regression")
        self.user = User.objects.create_user("customer-save-admin", password="safe-test-password")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.client = Client()
        self.assertTrue(self.client.login(username="customer-save-admin", password="safe-test-password"))

    def _valid_customer_post(self):
        form = rebuild_views.CustomerForm()
        data = {}
        for name, field in form.fields.items():
            if not field.required:
                continue
            choices = list(getattr(field, "choices", []) or [])
            if choices:
                usable = [value for value, _label in choices if str(value) != ""]
                if usable:
                    data[name] = str(usable[0])
                    continue
            if "email" in name:
                data[name] = "mobile-save@test.de"
            elif "postal" in name:
                data[name] = "60311"
            elif "country" in name:
                data[name] = "DE"
            else:
                data[name] = "Test"
        data.setdefault("first_name", "Mobile")
        data.setdefault("last_name", "Save")
        data.setdefault("email", "mobile-save@test.de")
        return data

    def test_optional_collapsed_job_site_does_not_block_customer_save(self):
        data = self._valid_customer_post()
        response = self.client.post(reverse("next-customer-create"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Customer.objects.filter(organization=self.org).count(), 1)

    def test_invalid_customer_returns_visible_error_summary_instead_of_silent_failure(self):
        response = self.client.post(reverse("next-customer-create"), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kunde konnte nicht gespeichert werden.")
        self.assertContains(response, "data-form-error-summary")
        self.assertEqual(Customer.objects.filter(organization=self.org).count(), 0)

    def test_final_template_disables_browser_native_validation_for_progressive_form(self):
        root = Path(__file__).resolve().parents[1]
        template = (root / "templates/rebuild/customer_form.html").read_text(encoding="utf-8")
        backend = (root / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn("data-customer-form novalidate", template)
        self.assertIn("location_requested", backend)
        self.assertIn("Es wurde noch kein Kunde angelegt.", template)
