from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from erp.models import Customer, Organization, Project, UserProfile

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeCoreCrudContractTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Phase9 GmbH")
        User = get_user_model()
        self.user = User.objects.create_user(username="phase9-office", password="secret")
        UserProfile.objects.update_or_create(user=self.user, defaults={"organization": self.org, "role": "office", "is_mobile_worker": False})
        self.client.force_login(self.user)

    def test_customer_create_accepts_manual_number(self):
        response = self.client.post(reverse("next-customer-create"), {
            "type": "private",
            "first_name": "Mara",
            "last_name": "Beispiel",
            "email": "mara@example.test",
            "street": "Musterstraße 1",
            "postal_code": "60311",
            "city": "Frankfurt",
            "country": "DE",
            "customer_number": "K-TEST-9001",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Customer.objects.filter(organization=self.org, number="K-TEST-9001").exists())

    def test_customer_create_returns_to_project_with_customer_selected(self):
        response = self.client.post(reverse("next-customer-create") + "?next=project", {
            "next": "project",
            "type": "private",
            "first_name": "Tool",
            "last_name": "Time",
            "street": "Testweg 2",
            "postal_code": "10115",
            "city": "Berlin",
            "country": "DE",
        })
        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(organization=self.org, first_name="Tool")
        self.assertEqual(response.url, f"/projects/new/?customer={customer.pk}")

    def test_project_can_be_created_with_tooltime_minimum(self):
        customer = Customer.objects.create(organization=self.org, number="K-1", type="private", first_name="Max", last_name="Muster", active=True)
        response = self.client.post(reverse("next-project-create"), {
            "title": "Badsanierung Muster",
            "customer": str(customer.pk),
            "description": "",
            "object_location": "",
            "priority": "",
            "manager": "",
        })
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(organization=self.org, title="Badsanierung Muster")
        self.assertEqual(project.customer, customer)
        self.assertEqual(project.priority, "normal")

    def test_templates_use_tooltime_creation_information_architecture(self):
        customer = (ROOT / "templates/rebuild/customer_form.html").read_text(encoding="utf-8")
        project = (ROOT / "templates/rebuild/project_form.html").read_text(encoding="utf-8")
        self.assertIn("Details einblenden", customer)
        self.assertIn("Kundennummer", customer)
        self.assertIn("Abweichenden Ausführungsort hinzufügen", customer)
        self.assertIn("Kunde auswählen", project)
        self.assertIn("Abweichenden Ausführungsort verwenden", project)
        self.assertIn("＋ Neuen Kunden anlegen", project)
        self.assertNotIn("Aufmaß / 3D", project)
        self.assertNotIn("Kein Wizard", project)
