from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def install_tests(module) -> None:
    runtime_rel = "tests/test_tooltime_appointment_process_parity.py"
    runtime = r'''from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import (
    CalendarEvent, CatalogItem, CommercialItemMeta, Customer, Document,
    Invoice, Organization, Project, Quote, QuoteItem, UserProfile,
)


class ToolTimeAppointmentProcessParityTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau Terminparität")
        self.user = User.objects.create_user("appointment-parity-office", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="appointment-parity-office", password="safe-test-password"))
        self.customer = Customer.objects.create(
            organization=self.org, number="K-TP-1", type="business", company="Termin Kunde",
            street="Terminweg 1", postal_code="60311", city="Frankfurt",
        )
        self.project = Project.objects.create(
            organization=self.org, number="P-TP-1", title="Termin Projekt",
            customer=self.customer, status="planning", priority="normal",
        )
        self.catalog = CatalogItem.objects.create(
            organization=self.org, code="L-100", name="Montageleistung", description="Montage",
            kind="service", unit="Std.", purchase_price=Decimal("40"), sales_price=Decimal("80"),
            tax_rate=Decimal("19"), active=True,
        )

    def _payload(self, title="Termin mit Leistungen", **extra):
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(days=1)
        form = rebuild_views.AppointmentForm(organization=self.org)
        data = {
            "title": title,
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "customer_filter": str(self.customer.pk),
            "project": str(self.project.pk),
            "repeat_rule": "none",
            "repeat_count": "1",
            "service_editor_present": "1",
            "service_group_title": ["Montage"],
            "service_group_index": ["0"],
            "service_kind": ["labour"],
            "service_quantity": ["2"],
            "service_unit": ["Std."],
            "service_description": ["Montageleistung"],
            "service_catalog_id": [str(self.catalog.pk)],
            "service_purchase_price": ["40"],
            "service_unit_price": ["80"],
            "service_tax_rate": ["19"],
            "service_mixed_json": ["[]"],
            "service_source_quote_item_id": [""],
            "work_report": "Vor Ort Anschluss prüfen.",
        }
        for name, field in form.fields.items():
            if name in data or not field.required:
                continue
            choices = list(getattr(field, "choices", []) or [])
            usable = [value for value, _label in choices if str(value) != ""]
            data[name] = str(usable[0]) if usable else "Test"
        data.update(extra)
        return data

    def test_appointment_services_store_prices_but_appointment_ui_hides_them(self):
        response = self.client.post(reverse("next-appointment-create"), self._payload())
        self.assertEqual(response.status_code, 302)
        event = CalendarEvent.objects.get(title="Termin mit Leistungen")
        item = event.service_items.get()
        self.assertEqual(item.group.title, "Montage")
        self.assertEqual(item.purchase_price, Decimal("40"))
        self.assertEqual(item.unit_price, Decimal("80"))
        self.assertEqual(event.work_report, "Vor Ort Anschluss prüfen.")
        detail = self.client.get(reverse("next-appointment-detail", args=[event.pk]))
        self.assertContains(detail, "Montageleistung")
        self.assertContains(detail, "Arbeitszeit")
        self.assertNotContains(detail, "Einkaufspreis")
        self.assertNotContains(detail, "Verkaufspreis")
        self.assertNotContains(detail, "80,00")

    def test_accepted_quote_prefills_appointment_and_all_positions_are_copied(self):
        quote = Quote.objects.create(
            organization=self.org, project=self.project, number="A-TP-1", status="accepted",
            issue_date=timezone.localdate(), created_by=self.user,
        )
        quote_item = QuoteItem.objects.create(
            quote=quote, position=1, description="Angebotsposition", quantity=Decimal("3"),
            unit="Std.", unit_price=Decimal("90"), tax_rate=Decimal("19"), catalog_item=self.catalog,
        )
        CommercialItemMeta.objects.create(
            organization=self.org, quote_item=quote_item, position_type="labour",
            purchase_price=Decimal("45"), markup_percent=Decimal("100"), group_title="Angebotsgruppe",
        )
        start = self.client.post(reverse("next-quote-to-appointment", args=[quote.pk]))
        self.assertEqual(start.status_code, 302)
        self.assertIn(f"quote={quote.pk}", start.url)
        page = self.client.get(start.url)
        self.assertContains(page, "Angebotsposition")
        self.assertContains(page, "Angebotsgruppe")
        payload = self._payload(
            title="Aus Angebot", source_quote=str(quote.pk),
            service_group_title=["Angebotsgruppe"], service_group_index=["0"],
            service_kind=["labour"], service_quantity=["3"], service_unit=["Std."],
            service_description=["Angebotsposition"], service_catalog_id=[str(self.catalog.pk)],
            service_purchase_price=["45"], service_unit_price=["90"], service_tax_rate=["19"],
            service_mixed_json=["[]"], service_source_quote_item_id=[str(quote_item.pk)],
        )
        response = self.client.post(reverse("next-appointment-create"), payload)
        self.assertEqual(response.status_code, 302)
        event = CalendarEvent.objects.get(title="Aus Angebot")
        self.assertEqual(event.source_quote_id, quote.pk)
        copied = event.service_items.get()
        self.assertEqual(copied.source_quote_item_id, quote_item.pk)
        self.assertEqual(copied.unit_price, Decimal("90"))

    def test_appointment_to_quote_and_documented_appointment_to_invoice_copy_services_and_prices(self):
        self.client.post(reverse("next-appointment-create"), self._payload(title="Dokumentquelle"))
        event = CalendarEvent.objects.get(title="Dokumentquelle")
        response = self.client.post(reverse("next-appointment-to-quote", args=[event.pk]))
        self.assertEqual(response.status_code, 302)
        quote = Quote.objects.get(source_event=event)
        self.assertEqual(quote.items.get().unit_price, Decimal("80"))
        self.assertEqual(quote.items.get().commercial_meta.group_title, "Montage")

        blocked = self.client.post(reverse("next-appointment-to-invoice", args=[event.pk]))
        self.assertEqual(blocked.status_code, 302)
        self.assertFalse(Invoice.objects.filter(source_event=event).exists())

        report = Document(
            organization=self.org, customer=self.customer, project=self.project,
            title="Arbeitsbericht", category="report", mime_type="text/plain", size=2,
            metadata={"event_id": event.pk}, uploaded_by=self.user,
        )
        report.file.save("report.txt", ContentFile(b"ok"), save=False)
        report.save()
        response = self.client.post(reverse("next-appointment-to-invoice", args=[event.pk]))
        self.assertEqual(response.status_code, 302)
        invoice = Invoice.objects.get(source_event=event)
        self.assertEqual(invoice.items.get().unit_price, Decimal("80"))
        self.assertEqual(invoice.items.get().commercial_meta.group_title, "Montage")

    def test_customer_only_appointment_can_be_documented_without_real_project(self):
        start = timezone.now() + timedelta(days=1)
        event = CalendarEvent.objects.create(
            organization=self.org, customer=self.customer, title="Ohne Projekt", type="appointment",
            starts_at=start, ends_at=start + timedelta(hours=1), work_report="Vorgabe",
            created_by=self.user,
        )
        response = self.client.post(
            reverse("next-appointment-document", args=[event.pk]),
            {"report_text": "Erledigt", "customer_name": self.customer.display_name},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Document.objects.filter(
            organization=self.org, customer=self.customer, project__isnull=True,
            category="report", metadata__event_id=event.pk,
        ).exists())
'''
    module.write(runtime_rel, runtime)
    compile(runtime, str(ROOT / runtime_rel), "exec")

    contract_rel = "tests/test_tooltime_appointment_process_parity_contract.py"
    contract = r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeAppointmentProcessParityContractTests(SimpleTestCase):
    def test_tooltime_appointment_process_contract_is_present(self):
        models = (ROOT / "erp/models.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        form = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        detail = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        editor = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        for marker in (
            "class AppointmentServiceGroup", "class AppointmentServiceItem",
            "source_quote = models.ForeignKey", "source_event = models.ForeignKey",
            "work_report = models.TextField",
        ):
            self.assertIn(marker, models)
        for marker in (
            "def appointment_from_quote", "def appointment_to_quote", "def appointment_to_invoice",
            "_appointment_copy_services_to_document", "_appointment_apply_field_services",
        ):
            self.assertIn(marker, views)
        for marker in ("next-quote-to-appointment", "next-appointment-to-quote", "next-appointment-to-invoice"):
            self.assertIn(marker, urls)
        for marker in (
            "Terminname", "Mitarbeiter hinzufügen", "Leistungsgruppe hinzufügen", "Position hinzufügen",
            'name="work_report"', "service_purchase_price", "service_unit_price",
        ):
            self.assertIn(marker, form)
        for marker in ("Angebot erstellen", "Rechnung erstellen", "document_service_quantity"):
            self.assertIn(marker, detail)
        self.assertNotIn("Verkaufspreis", detail)
        self.assertIn("data-quote-to-appointment", editor)
'''
    module.write(contract_rel, contract)
    compile(contract, str(ROOT / contract_rel), "exec")


def run(module) -> None:
    install_tests(module)
