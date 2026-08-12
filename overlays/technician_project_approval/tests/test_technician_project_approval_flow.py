import base64
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from erp import models as m


User = get_user_model()


class TechnicianProjectApprovalContractTests(SimpleTestCase):
    def test_technician_intake_has_no_financial_inputs(self):
        template = Path("templates/rebuild/field_quick_job.html").read_text(encoding="utf-8")
        self.assertIn("data-intake-ai", template)
        self.assertIn("data-intake-record", template)
        self.assertIn('name="photos"', template)
        self.assertIn("positions_json", template)
        self.assertIn("keine Preise", template)
        for internal in ('name="manual_ek_', 'data-price-source', 'data-markup', 'name="markup_', 'VK / Einheit'):
            self.assertNotIn(internal, template)

    def test_customer_view_contains_only_final_sales_values(self):
        template = Path("templates/rebuild/field_project_approval.html").read_text(encoding="utf-8")
        self.assertIn("Finale Kundenpreise", template)
        self.assertIn("Gesamtpreis", template)
        self.assertIn("data-signature", template)
        self.assertIn("Unterschreiben & Projekt starten", template)
        for internal in ('data-price-source', 'manual_ek_', 'markup_', 'commercial_meta', 'purchase_price'):
            self.assertNotIn(internal, template)

    def test_office_review_has_tooltime_commercial_controls(self):
        template = Path("templates/rebuild/project_approval_review.html").read_text(encoding="utf-8")
        for label in ("Preisgrundlage", "EK manuell", "Aufschlag (%)", "VK / Einheit", "Umsatzsteuer", "Rabatt", "Zahlungsziel", "Skonto", "Projekt & Verkaufspreise bestätigen"):
            self.assertIn(label, template)

    def test_ai_schema_never_requests_prices(self):
        source = Path("erp/project_intake_views.py").read_text(encoding="utf-8")
        schema_start = source.index("def _structured_schema")
        schema_end = source.index("def _structure_intake", schema_start)
        schema = source[schema_start:schema_end]
        self.assertNotIn("unit_price", schema)
        self.assertNotIn("purchase_price", schema)
        self.assertNotIn("markup", schema)
        self.assertIn("Niemals Preise", source)


class TechnicianProjectApprovalDatabaseTests(TestCase):
    def setUp(self):
        self.org = m.Organization.objects.create(name="A+Bau Approval Test")
        self.office_user = User.objects.create_user(username="owner", password="testpass", email="owner@example.com")
        self.tech_user = User.objects.create_user(username="monteur", password="testpass", email="tech@example.com")
        # User creation already provisions UserProfile via the application's signal.
        self.office_user.profile.organization = self.org
        self.office_user.profile.role = "admin"
        self.office_user.profile.is_mobile_worker = False
        self.office_user.profile.save()
        self.tech_user.profile.organization = self.org
        self.tech_user.profile.role = "technician"
        self.tech_user.profile.is_mobile_worker = True
        self.tech_user.profile.save()
        self.employee = m.Employee.objects.create(
            organization=self.org,
            employee_number="M-100",
            first_name="Max",
            last_name="Monteur",
            email="tech@example.com",
            user=self.tech_user,
            active=True,
        )
        self.customer = m.Customer.objects.create(
            organization=self.org,
            number="K-TEST-1",
            type="private",
            first_name="Erika",
            last_name="Muster",
            street="Teststraße 1",
            postal_code="60311",
            city="Frankfurt",
            country="DE",
            active=True,
        )
        self.bo_source = m.PriceSource.objects.create(
            organization=self.org,
            name="B&O VA04 Preisliste",
            original_filename="B&O-VA04.xlsx",
            sha256="c" * 64,
            active=True,
        )
        self.bo_row = m.PriceItem.objects.create(
            organization=self.org,
            source=self.bo_source,
            code="VA04-WT-001",
            description="Waschtisch montieren mit vorhandenen Anschlussteilen",
            unit="Stk.",
            sales_price=Decimal("100.00"),
        )
        self.tech = Client()
        self.office = Client()
        self.tech.force_login(self.tech_user)
        self.office.force_login(self.office_user)

    def _submit_intake(self):
        photo = SimpleUploadedFile("bad-vorher.jpg", b"fake-jpeg-content", content_type="image/jpeg")
        response = self.tech.post(
            reverse("field-quick-job"),
            {
                "customer_mode": "existing",
                "customer_id": str(self.customer.pk),
                "title": "Bad Waschtisch",
                "issue": "Alten Waschtisch demontieren und neuen Waschtisch montieren.",
                "voice_transcript": "Beim Kunden soll der Waschtisch erneuert werden.",
                "positions_json": json.dumps([
                    {
                        "title": "Waschtisch montieren",
                        "description": "Neuen Waschtisch montieren",
                        "quantity": "2",
                        "unit": "Stk.",
                        "position_type": "labour",
                    }
                ]),
                "photos": photo,
            },
        )
        self.assertEqual(response.status_code, 302)
        return m.Project.objects.get(title="Bad Waschtisch")

    def test_full_technician_owner_customer_flow(self):
        project = self._submit_intake()
        flow = m.ProjectApprovalFlow.objects.select_related("quote").get(project=project)
        quote = flow.quote
        item = quote.items.get()
        meta = m.CommercialItemMeta.objects.get(quote_item=item)

        self.assertEqual(project.status, "review")
        self.assertEqual(flow.status, "submitted")
        self.assertEqual(quote.status, "review")
        self.assertEqual(item.unit_price, Decimal("0"))
        self.assertFalse(item.approved)
        self.assertEqual(meta.purchase_price, Decimal("0"))
        self.assertEqual(meta.markup_percent, Decimal("0"))
        self.assertTrue(m.Document.objects.filter(project=project, metadata__kind="project_intake_photo").exists())
        self.assertTrue(m.Notification.objects.filter(user=self.office_user, title="Neue Projektfreigabe").exists())

        denied = self.tech.get(reverse("project-approval-review", args=[project.pk]))
        self.assertEqual(denied.status_code, 403)
        waiting = self.tech.get(reverse("field-project-approval", args=[project.pk]))
        self.assertEqual(waiting.status_code, 200)
        waiting_html = waiting.content.decode("utf-8")
        self.assertIn("Wartet auf Freigabe", waiting_html)
        self.assertNotIn("100,00 €", waiting_html)

        confirm = self.office.post(
            reverse("project-approval-review", args=[project.pk]),
            {
                f"price_source_{item.pk}": str(self.bo_row.pk),
                f"manual_ek_{item.pk}": "0",
                f"markup_{item.pk}": "25",
                f"position_type_{item.pk}": "labour",
                f"service_model_{item.pk}": "normal",
                "tax_code": "19",
                "discount_type": "percent",
                "discount_value": "0",
                "payment_due_days": "14",
                "skonto_percent": "2",
                "skonto_days": "7",
                "closing_text": "Ausführung nach Kundenfreigabe.",
            },
        )
        self.assertEqual(confirm.status_code, 302)
        project.refresh_from_db()
        flow.refresh_from_db()
        quote.refresh_from_db()
        item.refresh_from_db()
        meta.refresh_from_db()
        self.assertEqual(project.status, "confirmed")
        self.assertEqual(flow.status, "confirmed")
        self.assertEqual(quote.status, "sent")
        self.assertEqual(meta.purchase_price, Decimal("100.00"))
        self.assertEqual(meta.markup_percent, Decimal("25.00"))
        self.assertEqual(item.unit_price, Decimal("125.00"))
        self.assertTrue(item.approved)
        self.assertTrue(m.Notification.objects.filter(user=self.tech_user, title="Projekt freigegeben").exists())

        approved = self.tech.get(reverse("field-project-approval", args=[project.pk]))
        self.assertEqual(approved.status_code, 200)
        approved_html = approved.content.decode("utf-8")
        self.assertIn("Finale Kundenpreise", approved_html)
        self.assertIn("125,00", approved_html)
        self.assertIn("297,50", approved_html)
        self.assertNotIn("25,00 %", approved_html)
        self.assertNotIn("VA04-WT-001", approved_html)

        signature = "data:image/png;base64," + base64.b64encode(b"signed-png").decode("ascii")
        signed = self.tech.post(
            reverse("field-project-approval", args=[project.pk]),
            {"signer_name": "Erika Muster", "signature_data": signature},
        )
        self.assertEqual(signed.status_code, 302)
        project.refresh_from_db()
        flow.refresh_from_db()
        quote.refresh_from_db()
        self.assertEqual(project.status, "in_progress")
        self.assertIsNotNone(project.actual_start)
        self.assertEqual(flow.status, "signed")
        self.assertEqual(quote.status, "accepted")
        self.assertTrue(m.Document.objects.filter(project=project, metadata__kind="project_customer_approval_signature").exists())
        self.assertTrue(m.Notification.objects.filter(user=self.office_user, title="Projekt vom Kunden unterschrieben").exists())

    def test_technician_cannot_bypass_price_free_project_create(self):
        response = self.tech.get(reverse("next-project-create"))
        self.assertRedirects(response, reverse("field-quick-job"), fetch_redirect_response=False)
        office = self.office.get(reverse("next-project-create"))
        self.assertEqual(office.status_code, 200)
