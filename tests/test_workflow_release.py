import unittest
import base64
import json
from datetime import timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from erp.models import (
    CalendarEvent,
    ChangeOrder,
    Customer,
    CustomerPortalAccess,
    CustomerSurvey,
    Document,
    EmailMessage,
    Employee,
    IntegrationConfig,
    Invoice,
    Notification,
    Organization,
    PriceItem,
    PriceSource,
    Project,
    ProjectMaterial,
    PurchaseDocument,
    PurchaseOrder,
    Quote,
    RoomMeasurement,
    SiteReport,
    Supplier,
    Task,
    UserProfile,
    WorkMedia,
)
from erp.services.numbering import next_number


class WorkflowReleaseTests(TestCase):
    def setUp(self):
        self.media_dir = TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.org = Organization.objects.create(name="KAYI Workflow Test")
        self.admin = User.objects.create_user("workflow-admin", password="very-secure-password", is_staff=True)
        self.admin.profile.organization = self.org
        self.admin.profile.role = UserProfile.Role.ADMIN
        self.admin.profile.save()

        self.customer = Customer.objects.create(
            organization=self.org,
            number=next_number(self.org, "customer"),
            company="Versicherungskunde GmbH",
            email="kunde@example.de",
        )
        self.insurance_source = PriceSource.objects.create(
            organization=self.org,
            name="B&O Versicherung 2026",
            kind=PriceSource.Kind.INSURANCE,
            original_filename="bo-2026.xlsx",
            sha256="a" * 64,
            imported_rows=1,
            imported_at=timezone.now(),
        )
        self.price_item = PriceItem.objects.create(
            organization=self.org,
            source=self.insurance_source,
            code="BO-WAND-01",
            description="Wandfläche vorbereiten",
            category="Wand",
            unit="m²",
            sales_price=Decimal("10.00"),
            tax_rate=Decimal("19.00"),
        )
        self.project = Project.objects.create(
            organization=self.org,
            number=next_number(self.org, "project"),
            title="B&O Wasserschaden",
            customer=self.customer,
            status=Project.Status.IN_PROGRESS,
            job_type=Project.JobType.INSURANCE,
            price_source=self.insurance_source,
            insurance_claim_number="BO-1234",
            budget=Decimal("5000.00"),
        )
        self.measurement = RoomMeasurement.objects.create(
            organization=self.org,
            project=self.project,
            name="Bad",
            status=RoomMeasurement.Status.CONFIRMED,
            length_m=Decimal("4.000"),
            width_m=Decimal("3.000"),
            height_m=Decimal("2.500"),
            waste_percent=Decimal("10.00"),
            created_by=self.admin,
        )

        self.technician_user = User.objects.create_user("workflow-tech", password="very-secure-password")
        self.technician_user.profile.organization = self.org
        self.technician_user.profile.role = UserProfile.Role.TECHNICIAN
        self.technician_user.profile.is_mobile_worker = True
        self.technician_user.profile.save()
        self.technician = Employee.objects.create(
            organization=self.org,
            user=self.technician_user,
            employee_number=next_number(self.org, "employee"),
            first_name="Murat",
            last_name="Monteur",
            email="murat@example.de",
            can_view_prices=False,
        )
        self.project.members.add(self.technician)
        self.task = Task.objects.create(
            organization=self.org,
            project=self.project,
            title="Schaden dokumentieren",
            assigned_to=self.technician,
        )
        self.other_project = Project.objects.create(
            organization=self.org,
            number=next_number(self.org, "project"),
            title="Nicht zugewiesenes Projekt",
            customer=self.customer,
            budget=Decimal("99999.00"),
        )
        self.other_task = Task.objects.create(
            organization=self.org,
            project=self.other_project,
            title="Fremde Aufgabe",
        )

        self.client = Client()
        self.client.login(username="workflow-admin", password="very-secure-password")
        self.tech_client = Client()
        self.tech_client.login(username="workflow-tech", password="very-secure-password")

    def test_employee_creation_builds_separate_technician_account_without_prices(self):
        response = self.client.post(reverse("employee-create"), {
            "first_name": "Ali",
            "last_name": "Neu",
            "email": "ali.neu@example.de",
            "phone": "",
            "trade": "Sanitär",
            "active": "on",
            "color": "#123456",
            "can_view_prices": "on",
            "create_account": "on",
            "username": "",
            "password": "",
            "role": UserProfile.Role.TECHNICIAN,
        })
        self.assertEqual(response.status_code, 302)
        employee = Employee.objects.get(email="ali.neu@example.de")
        self.assertIsNotNone(employee.user_id)
        self.assertFalse(employee.can_view_prices)
        self.assertEqual(employee.user.profile.role, UserProfile.Role.TECHNICIAN)
        self.assertFalse(employee.user.has_usable_password())

    def test_insurance_price_list_matches_job_and_measurement_updates_quote(self):
        response = self.client.post(reverse("project-pricing", args=[self.project.pk]), {
            "action": "add-items",
            "price_items": [self.price_item.pk],
        })
        self.assertEqual(response.status_code, 302)
        quote = Quote.objects.get(project=self.project)
        item = quote.items.get(code="BO-WAND-01")
        self.assertEqual(item.quantity, Decimal("38.500"))
        self.assertEqual(item.unit_price, Decimal("10.00"))

        self.measurement.length_m = Decimal("5.000")
        self.measurement.save()
        response = self.client.post(reverse("project-pricing", args=[self.project.pk]), {"action": "recalculate"})
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal("44.000"))

    def test_technician_only_sees_assigned_work_and_never_price_or_portal_token(self):
        portal = CustomerPortalAccess.objects.create(organization=self.org, project=self.project)
        response = self.tech_client.get(reverse("mobile-app"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, escape(self.project.title))
        self.assertNotContains(response, self.other_project.title)
        self.assertNotContains(response, "5.000,00")

        response = self.tech_client.get(reverse("project-operations", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, str(portal.token))
        self.assertNotContains(response, self.insurance_source.name)
        self.assertContains(response, "vom Büro verwaltet")

        self.assertEqual(self.tech_client.get(reverse("project-pricing", args=[self.project.pk])).status_code, 403)
        self.assertEqual(self.tech_client.get(reverse("project-detail", args=[self.other_project.pk])).status_code, 404)
        self.assertIn(self.tech_client.get("/api/price-sources/").status_code, {403, 404})

    def test_technician_can_update_own_task_but_not_unassigned_task(self):
        response = self.tech_client.post(reverse("task-mobile-update", args=[self.task.pk]), {
            "status": Task.Status.DONE,
            "description": "Vor Ort erledigt",
        })
        self.assertEqual(response.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.DONE)
        self.assertIsNotNone(self.task.completed_at)
        self.assertEqual(
            self.tech_client.post(reverse("task-mobile-update", args=[self.other_task.pk]), {"status": Task.Status.DONE}).status_code,
            403,
        )

    def test_change_order_can_be_added_by_technician_signed_and_invoiced(self):
        response = self.tech_client.post(reverse("change-order-create", args=[self.project.pk]), {
            "title": "Verdecktes Rohr ersetzen",
            "description": "Während der Ausführung entdeckt; Foto liegt bei.",
        })
        self.assertEqual(response.status_code, 302)
        order = ChangeOrder.objects.get(project=self.project)
        self.assertEqual(order.amount_net, Decimal("0.00"))
        self.assertEqual(order.requested_by, self.technician_user)

        order.amount_net = Decimal("450.00")
        order.status = ChangeOrder.Status.SENT
        order.save()
        response = self.client.post(reverse("change-order-sign", args=[order.public_token]), {
            "decision": "accept",
            "signed_name": "Max Kunde",
            "signature_data": "data:image/png;base64," + base64.b64encode(b"signature").decode(),
            "comment": "Freigegeben",
        })
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, ChangeOrder.Status.ACCEPTED)
        self.assertIsNotNone(order.signed_at)

        response = self.client.post(reverse("change-order-to-invoice", args=[order.pk]))
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, ChangeOrder.Status.INVOICED)
        invoice = Invoice.objects.get(project=self.project)
        self.assertTrue(invoice.items.filter(code=order.number, unit_price=Decimal("450.00")).exists())


    def test_bando_site_report_matches_customer_signoff_flow_and_keeps_employee_prices_hidden(self):
        material = ProjectMaterial.objects.create(
            project=self.project,
            name="Kupferrohr 22 mm",
            quantity=Decimal("2.000"),
            unit="m",
            unit_cost=Decimal("42.00"),
            unit_price=Decimal("123.45"),
        )

        response = self.tech_client.get(reverse("site-report-create", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "B&O Leistungsnachweis & Regiebericht")
        self.assertContains(response, "Bestätigung der Leistung")
        self.assertContains(response, "Aufmaß / Regiebericht")
        self.assertNotContains(response, "123.45")
        self.assertNotContains(response, "123,45")

        signature = "data:image/png;base64," + base64.b64encode(b"signed-at-customer").decode()
        response = self.tech_client.post(reverse("site-report-create", args=[self.project.pk]), {
            "title": "B&O Leistungsnachweis",
            "execution_satisfied": "1",
            "employee_punctual": "1",
            "repair_duration": "1 Std. 45 Min.",
            "tenant_fault": "",
            "report_text": "Abfluss instandgesetzt und geprüft.",
            "service_code[]": ["BO-WAND-01"],
            "service_description[]": ["Wandfläche vorbereiten"],
            "service_quantity[]": ["12.5"],
            "service_unit[]": ["m²"],
            "material_id[]": [str(material.pk)],
            "material_code[]": ["MAT-22"],
            "material_description[]": ["Kupferrohr 22 mm"],
            "material_quantity[]": ["2"],
            "material_unit[]": ["m"],
            "signed_name": "Max Kunde",
            "signature_data": signature,
            "signature_touched": "1",
            "action": "confirm",
        })
        self.assertEqual(response.status_code, 302)
        report = SiteReport.objects.get(project=self.project)
        self.assertEqual(report.kind, SiteReport.Kind.BANDO)
        self.assertTrue(report.execution_satisfied)
        self.assertTrue(report.employee_punctual)
        self.assertEqual(report.repair_duration, "1 Std. 45 Min.")
        self.assertEqual(report.signed_name, "Max Kunde")
        self.assertIsNotNone(report.signed_at)
        self.assertEqual(report.service_lines[0]["quantity"], "12.5")
        self.assertEqual(report.material_lines[0]["price"], "123.45")

        with patch("erp.workflow_views.build_site_report_pdf", return_value=b"%PDF-field") as build_pdf:
            response = self.tech_client.get(reverse("site-report-pdf", args=[report.pk]))
            self.assertEqual(response.status_code, 200)
            build_pdf.assert_called_once_with(report, include_prices=False)

        with patch("erp.workflow_views.build_site_report_pdf", return_value=b"%PDF-office") as build_pdf:
            response = self.client.get(reverse("site-report-pdf", args=[report.pk]))
            self.assertEqual(response.status_code, 200)
            build_pdf.assert_called_once_with(report, include_prices=True)

        response = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertContains(response, "B&O Leistungsnachweis / Regiebericht")
        self.assertContains(response, reverse("site-report-pdf", args=[report.pk]))

    def test_leistungsnachweise_overview_lists_reports_and_respects_technician_scope(self):
        assigned_report = SiteReport.objects.create(
            organization=self.org,
            project=self.project,
            employee=self.technician,
            kind=SiteReport.Kind.BANDO,
            title="B&O Leistungsnachweis",
            signed_name="Max Kunde",
            signed_at=timezone.now(),
            created_by=self.admin,
        )
        foreign_report = SiteReport.objects.create(
            organization=self.org,
            project=self.other_project,
            kind=SiteReport.Kind.GENERIC,
            title="Fremder Vor-Ort-Bericht",
            created_by=self.admin,
        )

        response = self.client.get(reverse("site-report-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Leistungsnachweise")
        self.assertContains(response, self.project.number)
        self.assertContains(response, self.other_project.number)
        self.assertContains(response, reverse("site-report-pdf", args=[assigned_report.pk]))
        self.assertContains(response, reverse("site-report-edit", args=[foreign_report.pk]))
        self.assertNotContains(response, reverse("site-report-pdf", args=[foreign_report.pk]))
        self.assertContains(response, "Max Kunde")

        response = self.tech_client.get(reverse("site-report-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.number)
        self.assertNotContains(response, self.other_project.number)
        self.assertContains(response, reverse("site-report-pdf", args=[assigned_report.pk]))
        self.assertNotContains(response, reverse("site-report-pdf", args=[foreign_report.pk]))

    def test_bando_draft_stays_pending_and_can_be_continued(self):
        draft = SiteReport.objects.create(
            organization=self.org, project=self.project, employee=self.technician,
            kind=SiteReport.Kind.BANDO, title="B&O Entwurf", created_by=self.admin,
        )
        response = self.client.get(reverse("site-report-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("site-report-edit", args=[draft.pk]))
        self.assertContains(response, "ohne abgeschlossenen Leistungsnachweis")
        edit = self.client.get(reverse("site-report-edit", args=[draft.pk]))
        self.assertEqual(edit.status_code, 200)
        self.assertContains(edit, "Entwurf weiterbearbeiten")

    @unittest.skip("KAYI Next replaced the legacy nine-step wizard/tutorial; equivalent Next flow is covered by test_tooltime_rebuild and production browser smoke.")
    def test_project_wizard_step_three_uses_grouped_project_and_team_sections(self):
        response = self.client.get(reverse("project-create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Projektdaten")
        self.assertContains(response, "Verantwortliches Team")
        self.assertContains(response, "Neuen Mitarbeiter direkt hinzufügen")
        self.assertContains(response, "wizard-project-basics")

    def test_work_media_annotations_and_customer_portal(self):
        upload = SimpleUploadedFile("before.jpg", b"not-a-real-image-but-valid-upload", content_type="image/jpeg")
        response = self.tech_client.post(reverse("work-media-create", args=[self.project.pk]), {
            "stage": WorkMedia.Stage.BEFORE,
            "kind": WorkMedia.Kind.PHOTO,
            "title": "Vorher",
            "caption": "Schadstelle",
            "visible_to_customer": "on",
            "file": upload,
        })
        self.assertEqual(response.status_code, 302)
        media = WorkMedia.objects.get(project=self.project)
        response = self.tech_client.post(reverse("work-media-edit", args=[media.pk]), {
            "annotations": json.dumps([{"type": "text", "x": 0.2, "y": 0.3, "text": "Rohrbruch"}]),
            "caption": "Schadstelle markiert",
            "visible_to_customer": "on",
        })
        self.assertEqual(response.status_code, 302)
        media.refresh_from_db()
        self.assertEqual(media.annotations[0]["text"], "Rohrbruch")

        portal = CustomerPortalAccess.objects.create(organization=self.org, project=self.project)
        response = self.client.get(reverse("customer-portal-public", args=[portal.token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Schadstelle markiert")

    def test_incoming_insurance_email_is_linked_and_attachments_become_documents(self):
        IntegrationConfig.objects.create(
            organization=self.org,
            provider=IntegrationConfig.Provider.GMX,
            enabled=True,
            config={"inbound_token": "secret-inbound-token"},
        )
        payload = {
            "organization_id": self.org.pk,
            "message_id": "insurance-message-1",
            "sender": self.customer.email,
            "recipients": ["office@kayi.example"],
            "subject": "B&O Schaden BO-1234",
            "body_text": "Bitte Termin mit dem Kunden vereinbaren.",
            "claim_number": "BO-1234",
            "attachments": [{
                "filename": "auftrag.pdf",
                "content_type": "application/pdf",
                "content_base64": base64.b64encode(b"%PDF-1.7\n%%EOF").decode(),
            }],
        }
        response = self.client.post(
            reverse("inbound-email-webhook"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_KAYI_INBOUND_TOKEN="secret-inbound-token",
        )
        self.assertEqual(response.status_code, 200)
        message = EmailMessage.objects.get(message_id="insurance-message-1")
        self.assertEqual(message.project, self.project)
        self.assertEqual(message.customer, self.customer)
        document = Document.objects.get(project=self.project, title="auftrag.pdf")
        self.assertEqual(document.metadata["source"], "inbound_email")
        self.assertEqual(
            self.client.post(reverse("inbound-email-webhook"), data=json.dumps(payload), content_type="application/json", HTTP_X_KAYI_INBOUND_TOKEN="wrong").status_code,
            403,
        )

    def test_calendar_assigns_employees_and_creates_scheduled_reminders(self):
        starts = timezone.now() + timedelta(days=2)
        ends = starts + timedelta(hours=2)
        response = self.client.post(reverse("event-create"), {
            "project": self.project.pk,
            "title": "Aufmaß vor Ort",
            "type": CalendarEvent.Type.SITE,
            "starts_at": starts.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": ends.strftime("%Y-%m-%dT%H:%M"),
            "location": "Baustelle",
            "notes": "",
            "attendees": [self.technician.pk],
            "reminders": ["15", "60"],
        })
        self.assertEqual(response.status_code, 302)
        event = CalendarEvent.objects.get(title="Aufmaß vor Ort")
        self.assertEqual(event.reminder_minutes, [15, 60])
        self.assertEqual(list(event.attendees.all()), [self.technician])
        self.assertEqual(Notification.objects.filter(user=self.technician_user, url=f"/calendar/?event={event.pk}").count(), 2)

    def test_ai_leistungen_live_edit_stays_unapproved(self):
        response = self.client.post(reverse("service-assistant", args=[self.project.pk]), {
            "action": "apply",
            "row_count": "1",
            "code_0": "AI-01",
            "description_0": "Bearbeitete Leistung",
            "quantity_0": "2",
            "unit_0": "Stk.",
            "unit_price_0": "125",
        })
        self.assertEqual(response.status_code, 302)
        item = Quote.objects.get(project=self.project).items.get(code="AI-01")
        self.assertTrue(item.ai_generated)
        self.assertFalse(item.approved)

    def test_purchase_document_chain_survey_and_public_price_list(self):
        supplier = Supplier.objects.create(
            organization=self.org,
            number=next_number(self.org, "supplier"),
            name="Material Lieferant",
        )
        receipt = SimpleUploadedFile("receipt.pdf", b"%PDF-1.7\n%%EOF", content_type="application/pdf")
        response = self.client.post(reverse("purchase-order-create"), {
            "project": self.project.pk,
            "supplier": supplier.pk,
            "status": PurchaseOrder.Status.ORDERED,
            "total_net": "500.00",
            "external_reference": "PO-EXT-1",
            "notes": "",
            "documents": receipt,
        })
        self.assertEqual(response.status_code, 302)
        purchase = PurchaseOrder.objects.get(external_reference="PO-EXT-1")
        self.assertTrue(PurchaseDocument.objects.filter(purchase_order=purchase, kind=PurchaseDocument.Kind.RECEIPT).exists())

        response = self.client.post(reverse("survey-create", args=[self.project.pk]), {"send_email": "1"})
        self.assertEqual(response.status_code, 302)
        survey = CustomerSurvey.objects.get(project=self.project)
        self.assertTrue(EmailMessage.objects.filter(classification__survey_id=survey.pk).exists())
        response = self.client.post(reverse("survey-public", args=[survey.token]), {
            "rating_quality": "5",
            "rating_punctuality": "4",
            "rating_team": "5",
            "rating_cleanliness": "5",
            "comment": "Sehr gut",
            "allow_public_review": "on",
        })
        self.assertEqual(response.status_code, 200)
        survey.refresh_from_db()
        self.assertIsNotNone(survey.completed_at)

        response = self.client.post(reverse("price-source-share-toggle", args=[self.insurance_source.pk]))
        self.assertEqual(response.status_code, 302)
        self.insurance_source.refresh_from_db()
        self.assertTrue(self.insurance_source.share_enabled)
        response = self.client.get(reverse("price-source-public", args=[self.insurance_source.share_token]), {"q": "Wand"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BO-WAND-01")
        export = self.client.get(reverse("price-source-export", args=[self.insurance_source.pk]))
        self.assertEqual(export.status_code, 200)
        self.assertIn("text/csv", export["Content-Type"])

    @unittest.skip("KAYI Next replaced the legacy nine-step wizard/tutorial; equivalent Next flow is covered by test_tooltime_rebuild and production browser smoke.")
    def test_new_routes_render_and_dropdowns_are_searchable(self):
        self.assertEqual(self.client.get(reverse("project-operations", args=[self.project.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("marketplace"), {"q": "Rohr"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("employee-create")).status_code, 200)
        response = self.client.get(reverse("event-create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-searchable="true"')
        wizard = self.client.get(reverse("project-create"))
        self.assertContains(wizard, "9-Schritte-Projektassistent")
        self.assertNotContains(wizard, "10-Schritte-Projektassistent")
        self.assertEqual(wizard.content.decode().count('data-step="'), 9)
