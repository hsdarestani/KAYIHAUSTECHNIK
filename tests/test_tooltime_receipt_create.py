import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from erp import models as m


class ToolTimeReceiptCreateParityTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.mkdtemp(prefix="kayi-receipt-test-")
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir)
        self.media_override.enable()
        self.org = m.Organization.objects.create(name="A+Bau Receipt Test")
        User = get_user_model()
        self.user = User.objects.create_user(username="receipt-office", password="test-pass")
        profile, _ = m.UserProfile.objects.get_or_create(user=self.user)
        profile.organization = self.org
        profile.role = "office"
        profile.save()
        self.customer = m.Customer.objects.create(
            organization=self.org,
            number="K-R-0001",
            type="business",
            company="Acar Haustechnik",
        )
        self.project = m.Project.objects.create(
            organization=self.org,
            customer=self.customer,
            number="P-R-0001",
            title="Medrese",
            status="inquiry",
        )
        self.client.force_login(self.user)

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_dir, ignore_errors=True)
        super().tearDown()

    def test_receipt_page_uses_customer_context_and_upload_first_ui(self):
        response = self.client.get(reverse("next-expense-create"), {"customer": self.customer.pk, "project": self.project.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Beleg erfassen")
        self.assertContains(response, "data-tooltime-receipt-create=\"1\"")
        self.assertContains(response, "data-receipt-dropzone=\"1\"")
        self.assertContains(response, "Ausgabe als Beleg hochladen")
        self.assertContains(response, "Acar Haustechnik")
        self.assertContains(response, "Projekt auswählen (optional)")
        self.assertContains(response, "Lieferant auswählen (optional)")

    def test_pdf_upload_creates_linked_document_and_expense(self):
        upload = SimpleUploadedFile("rechnung-4711.pdf", b"%PDF-1.4\nreceipt-test\n", content_type="application/pdf")
        response = self.client.post(
            reverse("next-expense-create") + f"?customer={self.customer.pk}",
            {
                "customer": str(self.customer.pk),
                "project": str(self.project.pk),
                "supplier": "Test Lieferant GmbH",
                "amount_net": "120.50",
                "tax_rate": "19.00",
                "expense_date": "2026-09-07",
                "category": "Material",
                "description": "Materialbeleg",
                "receipt_file": upload,
            },
        )
        self.assertRedirects(response, reverse("next-customer-detail", args=[self.customer.pk]))
        expense = m.Expense.objects.get(organization=self.org)
        self.assertEqual(expense.amount_net, Decimal("120.50"))
        self.assertEqual(expense.project, self.project)
        self.assertEqual(expense.supplier, "Test Lieferant GmbH")
        self.assertIsNotNone(expense.document_id)
        self.assertEqual(expense.document.customer, self.customer)
        self.assertEqual(expense.document.project, self.project)
        self.assertEqual(expense.document.metadata.get("kind"), "expense_receipt")
        self.assertTrue(expense.document.file.name.endswith(".pdf"))

    def test_rejects_unsupported_receipt_file(self):
        upload = SimpleUploadedFile("payload.exe", b"not-a-receipt", content_type="application/octet-stream")
        response = self.client.post(
            reverse("next-expense-create"),
            {
                "customer": str(self.customer.pk),
                "project": str(self.project.pk),
                "supplier": "Test",
                "amount_net": "10.00",
                "tax_rate": "19.00",
                "expense_date": "2026-09-07",
                "receipt_file": upload,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bitte PDF, XML, JPG, JPEG oder PNG hochladen.")
        self.assertFalse(m.Expense.objects.filter(organization=self.org).exists())
        self.assertFalse(m.Document.objects.filter(organization=self.org).exists())
