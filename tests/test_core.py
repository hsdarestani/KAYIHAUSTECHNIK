from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import (
    Customer, EmailMessage, Employee, IntegrationConfig, Invoice, InvoiceItem, Organization,
    Payment, Project, Quote, QuoteItem, TimeEntry, UserProfile,
)
from erp.services.documents import validate_upload
from erp.services.emailing import send_approved_email
from erp.services.numbering import next_number
from erp.services.pdf import build_invoice_pdf, build_quote_pdf


class BaseTestCase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI Test")
        self.user = User.objects.create_user("admin", password="very-secure-password", is_staff=True)
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.customer = Customer.objects.create(
            organization=self.org,
            number=next_number(self.org, "customer"),
            company="Testkunde GmbH",
            email="kunde@example.de",
            street="Testweg 1",
            postal_code="60311",
            city="Frankfurt",
        )
        self.employee = Employee.objects.create(
            organization=self.org,
            user=self.user,
            employee_number=next_number(self.org, "employee"),
            first_name="Test",
            last_name="Monteur",
        )
        self.project = Project.objects.create(
            organization=self.org,
            number=next_number(self.org, "project"),
            title="Testprojekt",
            customer=self.customer,
            status=Project.Status.IN_PROGRESS,
        )
        self.project.members.add(self.employee)
        self.client = Client()
        self.client.login(username="admin", password="very-secure-password")


class FinanceFlowTests(BaseTestCase):
    def test_quote_invoice_payment_flow_and_pdfs(self):
        quote = Quote.objects.create(
            organization=self.org,
            project=self.project,
            number=next_number(self.org, "quote"),
            status=Quote.Status.ACCEPTED,
            created_by=self.user,
        )
        QuoteItem.objects.create(
            quote=quote,
            position=1,
            description="Montage",
            quantity=Decimal("2"),
            unit="Stk.",
            unit_price=Decimal("100"),
            tax_rate=Decimal("19"),
        )
        self.assertEqual(quote.net_total, Decimal("200"))
        self.assertEqual(quote.gross_total, Decimal("238"))
        self.assertTrue(build_quote_pdf(quote).startswith(b"%PDF"))

        response = self.client.post(reverse("quote-to-invoice", args=[quote.pk]))
        self.assertEqual(response.status_code, 302)
        invoice = Invoice.objects.get(quote=quote)
        self.assertEqual(invoice.gross_total, Decimal("238"))
        self.assertTrue(build_invoice_pdf(invoice).startswith(b"%PDF"))

        Payment.objects.create(invoice=invoice, amount=Decimal("100"), recorded_by=self.user)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PARTIAL)
        Payment.objects.create(invoice=invoice, amount=Decimal("138"), recorded_by=self.user)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.outstanding_total, Decimal("0"))


class HumanApprovalTests(BaseTestCase):
    def test_email_cannot_send_without_approval(self):
        message = EmailMessage.objects.create(
            organization=self.org,
            direction=EmailMessage.Direction.DRAFT,
            status=EmailMessage.Status.REVIEW,
            recipients=["kunde@example.de"],
            subject="Test",
            body_text="Hallo",
        )
        with self.assertRaises(PermissionError):
            send_approved_email(message)

    @patch("erp.services.emailing.smtplib.SMTP_SSL")
    @patch("erp.services.emailing.settings.GMX_EMAIL", "office@example.de")
    @patch("erp.services.emailing.settings.GMX_PASSWORD", "secret")
    def test_approved_email_sends(self, smtp):
        IntegrationConfig.objects.create(organization=self.org, provider=IntegrationConfig.Provider.GMX, enabled=True)
        message = EmailMessage.objects.create(
            organization=self.org,
            direction=EmailMessage.Direction.DRAFT,
            status=EmailMessage.Status.APPROVED,
            approved_by=self.user,
            recipients=["kunde@example.de"],
            subject="Test",
            body_text="Hallo",
        )
        send_approved_email(message)
        message.refresh_from_db()
        self.assertEqual(message.status, EmailMessage.Status.SENT)
        smtp.return_value.__enter__.return_value.send_message.assert_called_once()


class TimeTrackingTests(BaseTestCase):
    def test_mobile_start_stop(self):
        response = self.client.post(
            reverse("api-time-start"),
            data={"project_id": self.project.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(TimeEntry.objects.filter(employee=self.employee, ended_at__isnull=True).exists())
        response = self.client.post(
            reverse("api-time-stop"),
            data={"description": "Montage", "break_minutes": 10},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        entry = TimeEntry.objects.get(employee=self.employee)
        self.assertIsNotNone(entry.ended_at)
        self.assertEqual(entry.break_minutes, 10)


class SecurityTests(BaseTestCase):
    def test_invalid_pdf_signature_is_rejected(self):
        upload = SimpleUploadedFile("fake.pdf", b"not a pdf", content_type="application/pdf")
        with self.assertRaises(ValueError):
            validate_upload(upload)

    def test_valid_pdf_signature_is_allowed(self):
        upload = SimpleUploadedFile("ok.pdf", b"%PDF-1.7\n%%EOF", content_type="application/pdf")
        validate_upload(upload)

    def test_anonymous_api_is_blocked(self):
        self.client.logout()
        response = self.client.get("/api/projects/")
        self.assertIn(response.status_code, {401, 403})


class DashboardTests(BaseTestCase):
    def test_dashboard_and_project_detail_render(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("project-detail", args=[self.project.pk])).status_code, 200)
