from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from erp import models as m


class ToolTimeCustomerDetailFunctionalE2E(TestCase):
    """Exercise the real customer-detail HTTP flows and verify persisted database state."""

    def setUp(self):
        self.org = m.Organization.objects.create(name="A+Bau E2E")
        self.user = get_user_model().objects.create_user(
            username="tooltime-customer-e2e",
            password="test-password-123",
            email="e2e@example.invalid",
        )
        profile = self.user.profile
        profile.organization = self.org
        profile.role = m.UserProfile.Role.ADMIN
        profile.is_mobile_worker = False
        profile.save()
        self.client.force_login(self.user)
        self.customer = m.Customer.objects.create(
            organization=self.org,
            number="K-E2E-0001",
            type="business",
            company="ToolTime E2E Kunde",
            first_name="Max",
            last_name="Muster",
            email="kunde@example.invalid",
            phone="06196 100200",
            street="Musterstraße 10",
            postal_code="65760",
            city="Eschborn",
            country="DE",
        )

    def customer_url(self, suffix=""):
        return reverse("next-customer-detail", args=[self.customer.pk]) + suffix

    def test_full_customer_workflow_persists_and_reloads(self):
        # 1) Real customer detail page renders.
        response = self.client.get(self.customer_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ToolTime E2E Kunde")
        self.assertContains(response, "Übersicht")
        self.assertContains(response, "Weitere Standorte & Kontakte")

        # 2) Editing the customer through the same POST endpoint persists.
        response = self.client.post(
            self.customer_url(),
            {
                "action": "update_customer",
                "type": "business",
                "company": "ToolTime E2E Kunde GmbH",
                "salutation": "Herr",
                "first_name": "Max",
                "last_name": "Muster",
                "email": "max.muster@example.invalid",
                "phone": "06196 100201",
                "mobile": "0170 1234567",
                "street": "Neue Straße 22",
                "postal_code": "65760",
                "city": "Eschborn",
                "country": "DE",
                "vat_id": "DE123456789",
                "notes": "E2E gespeichert",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.company, "ToolTime E2E Kunde GmbH")
        self.assertEqual(self.customer.mobile, "0170 1234567")
        self.assertEqual(self.customer.street, "Neue Straße 22")
        self.assertEqual(self.customer.notes, "E2E gespeichert")

        # 3) Additional ToolTime-style Einsatzort is created and belongs to this customer.
        response = self.client.post(
            self.customer_url(),
            {
                "action": "add_location",
                "site-name": "Baustelle West",
                "site-street": "Industriestraße 5",
                "site-postal_code": "65760",
                "site-city": "Eschborn",
                "site-floor": "2. OG",
                "site-access_notes": "Hofeinfahrt rechts",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        location = m.ObjectLocation.objects.get(
            organization=self.org,
            customer=self.customer,
            name="Baustelle West",
        )
        self.assertEqual(location.street, "Industriestraße 5")
        self.assertEqual(location.floor, "2. OG")

        # 4) Create a project through the real project-create route opened from the customer page.
        response = self.client.post(
            reverse("next-project-create") + f"?customer={self.customer.pk}",
            {
                "title": "Badmodernisierung E2E",
                "customer": str(self.customer.pk),
                "object_location": str(location.pk),
                "description": "Kompletter E2E Auftrag",
                "priority": "normal",
                "manager": "",
                "members": [],
            },
        )
        self.assertEqual(response.status_code, 302)
        project = m.Project.objects.get(
            organization=self.org,
            customer=self.customer,
            title="Badmodernisierung E2E",
        )
        self.assertEqual(project.object_location_id, location.pk)

        # 5) Create a Termin through the actual appointment route.
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(days=1)
        end = start + timedelta(hours=2)
        response = self.client.post(
            reverse("next-appointment-create") + f"?project={project.pk}",
            {
                "title": "Vor-Ort Termin E2E",
                "type": "appointment",
                "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
                "ends_at": end.strftime("%Y-%m-%dT%H:%M"),
                "location": "Industriestraße 5, Eschborn",
                "notes": "E2E Termin",
                "project": str(project.pk),
                "attendees": [],
            },
        )
        self.assertEqual(response.status_code, 302)
        appointment = m.CalendarEvent.objects.get(
            organization=self.org,
            project=project,
            title="Vor-Ort Termin E2E",
        )

        # 6) Create an Angebot with a real line item through the actual editor endpoint.
        today = timezone.localdate()
        response = self.client.post(
            reverse("next-quote-create") + f"?project={project.pk}",
            {
                "project": str(project.pk),
                "issue_date": today.isoformat(),
                "valid_until": (today + timedelta(days=14)).isoformat(),
                "intro_text": "E2E Angebot",
                "outro_text": "Danke",
                "discount_percent": "0",
                "notes": "E2E",
                "item_description": ["Montageleistung E2E"],
                "item_quantity": ["2"],
                "item_unit": ["Std."],
                "item_sales_price": ["75.00"],
                "item_tax": ["19"],
                "action": "save",
            },
        )
        self.assertEqual(response.status_code, 302)
        quote = m.Quote.objects.get(organization=self.org, project=project)
        self.assertEqual(quote.items.count(), 1)
        self.assertEqual(quote.items.get().description, "Montageleistung E2E")
        self.assertEqual(quote.items.get().unit_price, Decimal("75.00"))

        # 7) Create a Rechnung with a real line item through the actual editor endpoint.
        response = self.client.post(
            reverse("next-invoice-create") + f"?project={project.pk}",
            {
                "project": str(project.pk),
                "quote": str(quote.pk),
                "issue_date": today.isoformat(),
                "due_date": (today + timedelta(days=14)).isoformat(),
                "service_date": today.isoformat(),
                "intro_text": "E2E Rechnung",
                "outro_text": "Danke",
                "notes": "E2E",
                "item_description": ["Rechnungsposition E2E"],
                "item_quantity": ["1"],
                "item_unit": ["Psch."],
                "item_sales_price": ["100.00"],
                "item_tax": ["19"],
                "action": "save",
            },
        )
        self.assertEqual(response.status_code, 302)
        invoice = m.Invoice.objects.get(organization=self.org, project=project)
        self.assertEqual(invoice.items.count(), 1)
        self.assertEqual(invoice.items.get().unit_price, Decimal("100.00"))

        # Additional customer-scoped data for the customer tabs/KPIs.
        expense = m.Expense.objects.create(
            organization=self.org,
            project=project,
            supplier="E2E Lieferant",
            description="E2E Material",
            amount_net=Decimal("25.00"),
            tax_rate=Decimal("19.00"),
        )
        task = m.Task.objects.create(
            organization=self.org,
            project=project,
            title="E2E Aufgabe",
            status="open",
        )
        document = m.Document.objects.create(
            organization=self.org,
            customer=self.customer,
            project=project,
            title="E2E Dokument",
            category="other",
            mime_type="text/plain",
            size=0,
            uploaded_by=self.user,
        )

        # 8) Reload the customer cockpit and verify relational data and KPI math from DB.
        response = self.client.get(self.customer_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, project.title)
        self.assertContains(response, appointment.title)
        self.assertContains(response, quote.number)
        self.assertContains(response, invoice.number)
        self.assertContains(response, expense.supplier)
        self.assertEqual(response.context["revenue_net"], Decimal("100.00"))
        self.assertEqual(response.context["expenditure_net"], Decimal("25.00"))
        self.assertEqual(response.context["open_invoice_gross"], Decimal("119.00"))

        # 9) Tabs are backed by customer-scoped database records, not placeholders.
        response = self.client.get(self.customer_url("?tab=tasks"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, task.title)
        response = self.client.get(self.customer_url("?tab=documents"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, document.title)

        # 10) The concrete action targets from this customer open successfully.
        for url in (
            reverse("next-project-detail", args=[project.pk]),
            reverse("next-appointment-detail", args=[appointment.pk]),
            reverse("next-quote-edit", args=[quote.pk]),
            reverse("next-invoice-edit", args=[invoice.pk]),
        ):
            opened = self.client.get(url)
            self.assertLess(opened.status_code, 400, url)

    def test_customer_scope_prevents_cross_customer_finance_leakage(self):
        other = m.Customer.objects.create(
            organization=self.org,
            number="K-E2E-OTHER",
            type="business",
            company="Andere Firma",
            country="DE",
        )
        other_project = m.Project.objects.create(
            organization=self.org,
            number="P-E2E-OTHER",
            title="Fremdes Projekt",
            customer=other,
        )
        other_invoice = m.Invoice.objects.create(
            organization=self.org,
            number="R-E2E-OTHER",
            project=other_project,
            issue_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=14),
            created_by=self.user,
        )
        m.InvoiceItem.objects.create(
            invoice=other_invoice,
            position=1,
            description="Fremde Rechnung",
            quantity=Decimal("1"),
            unit="Psch.",
            unit_price=Decimal("9999.00"),
            tax_rate=Decimal("19"),
        )

        response = self.client.get(self.customer_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Fremdes Projekt")
        self.assertNotContains(response, other_invoice.number)
        self.assertEqual(response.context["revenue_net"], Decimal("0"))
        self.assertEqual(response.context["open_invoice_gross"], Decimal("0"))
