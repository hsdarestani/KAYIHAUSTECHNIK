import unittest
from decimal import Decimal
from unittest.mock import patch
from tempfile import NamedTemporaryFile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from erp.models import CatalogItem, Customer, Document, Organization, PriceItem, PriceSource, Project, Quote, QuoteItem, UserProfile
from erp.services.importers import import_customers
from erp.services.numbering import next_number


class AppUxAndPricingTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI UX Test")
        self.user = User.objects.create_user("ux-admin", password="very-secure-password")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.customer = Customer.objects.create(
            organization=self.org,
            number=next_number(self.org, "customer"),
            company="B&O Testkunde",
        )
        self.project = Project.objects.create(
            organization=self.org,
            number=next_number(self.org, "project"),
            title="B&O Bad",
            customer=self.customer,
            job_type=Project.JobType.INSURANCE,
        )
        self.bando = PriceSource.objects.create(
            organization=self.org,
            name="B&O PL 1658",
            kind=PriceSource.Kind.INSURANCE,
            original_filename="va04_preisliste_pl1658.csv",
            sha256="1" * 64,
            active=True,
        )
        self.priced = PriceItem.objects.create(
            organization=self.org,
            source=self.bando,
            code="VA04-1",
            description="Wandfliesen herstellen",
            category="Wand",
            unit="m²",
            sales_price=Decimal("42.50"),
        )
        self.unpriced = PriceItem.objects.create(
            organization=self.org,
            source=self.bando,
            code="VA04-0",
            description="Position ohne Preis",
            unit="Stk.",
            sales_price=Decimal("0.00"),
        )
        self.joda = PriceSource.objects.create(
            organization=self.org,
            name="JOKA",
            kind=PriceSource.Kind.SUPPLIER,
            original_filename="joka.003",
            sha256="2" * 64,
            active=True,
        )
        PriceItem.objects.create(
            organization=self.org,
            source=self.joda,
            code="MAT-1",
            description="Materialeinkauf",
            unit="Stk.",
            purchase_price=Decimal("10.00"),
        )
        self.client = Client()
        self.client.login(username="ux-admin", password="very-secure-password")

    def test_html_api_project_detail_redirects_to_real_project_screen(self):
        response = self.client.get(f"/api/projects/{self.project.pk}/", HTTP_ACCEPT="text/html")
        self.assertRedirects(response, reverse("project-detail", args=[self.project.pk]), fetch_redirect_response=False)
        response = self.client.get(f"/api/projects/{self.project.pk}/?format=json", HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ui_url"], f"http://testserver/projects/{self.project.pk}/")

    def test_pricing_dropdown_excludes_joka_and_hides_zero_prices(self):
        response = self.client.get(reverse("project-pricing", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "B&amp;O PL 1658")
        self.assertNotContains(response, ">JOKA ·")
        self.project.price_source = self.bando
        self.project.save(update_fields=["price_source"])
        response = self.client.get(reverse("project-pricing", args=[self.project.pk]))
        self.assertContains(response, "Wandfliesen herstellen")
        self.assertNotContains(response, "Position ohne Preis")
        self.assertContains(response, "42,50")

    def test_forged_zero_price_item_is_never_added_to_quote(self):
        self.project.price_source = self.bando
        self.project.save(update_fields=["price_source"])
        response = self.client.post(reverse("project-pricing", args=[self.project.pk]), {
            "action": "add-items",
            "price_items": [self.unpriced.pk],
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(QuoteItem.objects.filter(code="VA04-0").exists())
        self.assertFalse(Quote.objects.filter(project=self.project).exists())

    @patch("erp.workflow_views.extract_text")
    def test_order_pdf_lives_in_pricing_workspace_and_can_apply_reference(self, extract_text):
        extract_text.return_value = "Auftrag: 260669697\nMieter: Beatrix Brunner\nSchaden: Eternit Leitung gebrochen"
        upload = SimpleUploadedFile("B&O Auftrag.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf")
        response = self.client.post(reverse("project-pricing", args=[self.project.pk]), {
            "action": "upload-order-pdf",
            "order_pdf": upload,
        })
        self.assertEqual(response.status_code, 302)
        document = Document.objects.get(project=self.project, metadata__source_order=True)
        self.assertEqual(document.metadata["bando_order"]["auftrag"], "260669697")
        response = self.client.post(reverse("project-pricing", args=[self.project.pk]), {
            "action": "apply-order-data",
            "document_id": document.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.external_reference, "260669697")
        self.assertEqual(self.project.price_source, self.bando)
        self.assertIn("Schadstoff", self.project.internal_notes)

    @unittest.skip("KAYI Next replaced the legacy nine-step wizard/tutorial; equivalent Next flow is covered by test_tooltime_rebuild and production browser smoke.")
    def test_first_run_tutorial_and_global_back_control_are_rendered(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "data-tutorial-overlay")
        self.assertContains(response, "data-tutorial-replay")
        response = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertContains(response, "data-smart-back")


    def test_price_library_uses_top_dropdown_and_excludes_supplier_and_zero_rows(self):
        response = self.client.get(reverse("price-library"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="source"')
        self.assertContains(response, "Alle Preislisten")
        self.assertContains(response, "B&amp;O PL 1658")
        self.assertNotContains(response, ">JOKA<")
        self.assertNotContains(response, "Position ohne Preis")
        self.assertContains(response, "Preisliste importieren")

    def test_wizard_price_preview_resolves_catalog_code_against_selected_source(self):
        catalog = CatalogItem.objects.create(
            organization=self.org, code="VA04-1", name="Wandfliesen",
            kind=CatalogItem.Kind.SERVICE, unit="m²", sales_price=Decimal("0.00"),
        )
        response = self.client.post(reverse("project-wizard-price-preview"), {
            "price_source": self.bando.pk,
            "services": [catalog.pk],
        })
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["price_source"], "B&O PL 1658")
        self.assertEqual(data["priced_count"], 1)
        self.assertEqual(data["unresolved_count"], 0)
        self.assertEqual(data["items"][0]["price"], "42.50")


    def test_wizard_price_items_endpoint_returns_selected_source_prices(self):
        response = self.client.get(reverse("project-wizard-price-items"), {"price_source": self.bando.pk})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["price_source"], "B&O PL 1658")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["code"], "VA04-1")
        self.assertEqual(data["items"][0]["price"], "42.50")
        self.assertNotIn("VA04-0", [item["code"] for item in data["items"]])

    @unittest.skip("KAYI Next replaced the legacy nine-step wizard/tutorial; equivalent Next flow is covered by test_tooltime_rebuild and production browser smoke.")
    def test_wizard_quote_accepts_price_item_directly(self):
        response = self.client.post(reverse("project-create"), {
            "project_type": "bathroom",
            "job_type": Project.JobType.INSURANCE,
            "price_source": self.bando.pk,
            "customer": self.customer.pk,
            "title": "Wizard B&O Direktpreis",
            "priority": Project.Priority.NORMAL,
            "measurement_method": "manual",
            "waste_percent": "10",
            "price_items": [self.priced.pk],
            "action": "quote",
        })
        self.assertEqual(response.status_code, 302, response.content)
        quote = Quote.objects.get(project__title="Wizard B&O Direktpreis")
        item = quote.items.get()
        self.assertEqual(item.code, "VA04-1")
        self.assertEqual(item.unit_price, Decimal("42.50"))
        self.assertIsNone(item.catalog_item)

    def test_customer_register_import_updates_by_customer_number(self):
        csv_data = (
            "K-Nr;Typ;Firma;Name;PLZ;Ort;E-Mail;Anzahl_Angebote;Anzahl_Rechnungen;Umsatz_Netto_Bezahlt;Ordner\n"
            "K-1001;UNTERNEHMEN;Acar Haustechnik;;68159;Mannheim;info@example.test;1;0;0.00;K-1001_acar\n"
            "K-1002;PRIVAT;;Adil Taher;63452;Hanau;;2;3;4374.35;K-1002_adil\n"
        )
        with NamedTemporaryFile("w", suffix=".csv", encoding="utf-8-sig", delete=False) as handle:
            handle.write(csv_data)
            path = handle.name
        try:
            first = import_customers(path, self.org)
            second = import_customers(path, self.org)
        finally:
            Path(path).unlink(missing_ok=True)
        self.assertEqual(first["created"], 2)
        self.assertEqual(second["updated"], 2)
        business = Customer.objects.get(organization=self.org, number="K-1001")
        private = Customer.objects.get(organization=self.org, number="K-1002")
        self.assertEqual(business.company, "Acar Haustechnik")
        self.assertEqual(business.type, Customer.Type.BUSINESS)
        self.assertEqual(private.first_name, "Adil")
        self.assertEqual(private.last_name, "Taher")
        self.assertEqual(private.postal_code, "63452")

    def test_quote_pdf_is_available_from_offer_and_has_kayi_document(self):
        quote = Quote.objects.create(
            organization=self.org, project=self.project, number=next_number(self.org, "quote"), created_by=self.user,
        )
        QuoteItem.objects.create(
            quote=quote, position=1, code="VA04-1", description="Wandfliesen herstellen",
            quantity=Decimal("2"), unit="m²", unit_price=Decimal("42.50"),
        )
        response = self.client.get(reverse("quote-pdf", args=[quote.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertGreater(len(response.content), 1500)
        list_response = self.client.get(reverse("resource-list", args=["quotes"]))
        self.assertContains(list_response, reverse("quote-pdf", args=[quote.pk]))

    def test_pricing_workspace_opens_only_the_next_relevant_step(self):
        response = self.client.get(reverse("project-pricing", args=[self.project.pk]))
        self.assertEqual(response.content.decode().count('class="pricing-step" open'), 1)
