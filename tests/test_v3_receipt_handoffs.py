import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from erp import models as m


class ReceiptHandoffTests(TestCase):
    def setUp(self):
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.org = m.Organization.objects.create(name="V3 receipts")
        self.user = get_user_model().objects.create_user(username="receipt-handoff")
        self.user.profile.organization = self.org
        self.user.profile.role = m.UserProfile.Role.OFFICE
        self.user.profile.save()
        self.client.force_login(self.user)
        self.customer = m.Customer.objects.create(organization=self.org, number="K1", company="Receipt customer")

    def payload(self, **changes):
        data = {"customer": self.customer.pk, "amount_net": "12,50", "tax_rate": "0",
                "expense_date": "2026-09-08", "paid": "1",
                "receipt_file": SimpleUploadedFile("beleg.pdf", b"%PDF-1.4\nreceipt", content_type="application/pdf")}
        data.update(changes)
        return data

    def test_customer_only_receipt_returns_to_cockpit_with_cost_and_document(self):
        response = self.client.post(reverse("next-expense-create"), self.payload())
        self.assertRedirects(response, reverse("next-customer-detail", args=[self.customer.pk]))
        expense = m.Expense.objects.get(organization=self.org)
        self.assertIsNone(expense.project_id)
        self.assertEqual(expense.amount_net, Decimal("12.50"))
        self.assertEqual(expense.tax_rate, 0)
        self.assertTrue(expense.paid)
        self.assertEqual(expense.document.customer_id, self.customer.pk)
        cockpit = self.client.get(response.url)
        self.assertIn(expense, cockpit.context["expenses"])
        self.assertEqual(cockpit.context["expenditure_net"], Decimal("12.50"))

    def test_customer_project_mismatch_and_cross_tenant_customer_do_not_write(self):
        other = m.Customer.objects.create(organization=self.org, number="K2", company="Other")
        project = m.Project.objects.create(organization=self.org, customer=other, number="P2", title="Other project")
        response = self.client.post(reverse("next-expense-create"), self.payload(project=project.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["receipt_form"].errors)
        foreign_org = m.Organization.objects.create(name="Other tenant")
        foreign = m.Customer.objects.create(organization=foreign_org, number="K1", company="Foreign")
        response = self.client.post(reverse("next-expense-create"), self.payload(customer=foreign.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["receipt_form"].errors)
        self.assertFalse(m.Expense.objects.exists())
        self.assertFalse(m.Document.objects.exists())

    def test_missing_and_oversized_upload_do_not_write(self):
        for upload in (None, SimpleUploadedFile("large.pdf", b"x" * (10 * 1024 * 1024 + 1))):
            data = self.payload()
            if upload is None:
                del data["receipt_file"]
            else:
                data["receipt_file"] = upload
            response = self.client.post(reverse("next-expense-create"), data)
            self.assertEqual(response.status_code, 200)
            self.assertIn("receipt_file", response.context["receipt_form"].errors)
        self.assertFalse(m.Expense.objects.exists())
        self.assertFalse(m.Document.objects.exists())

    def test_manual_expense_creation_remains_available(self):
        url = reverse("next-expense-create") + "?mode=manual"
        self.assertContains(self.client.get(url), 'name="amount_net"')
        response = self.client.post(url, {"supplier": "Manual", "description": "Fahrtkosten",
            "amount_net": "20.00", "tax_rate": "0", "expense_date": "2026-09-08"})
        self.assertRedirects(response, reverse("next-expenses"))
        expense = m.Expense.objects.get(organization=self.org)
        self.assertEqual(expense.amount_net, Decimal("20"))
        self.assertIsNone(expense.document_id)

    def test_field_users_cannot_read_or_write_expenses(self):
        expense = m.Expense.objects.create(organization=self.org, supplier="Restricted", amount_net=99)
        self.user.profile.role = m.UserProfile.Role.TECHNICIAN
        self.user.profile.save()
        for name, args in (("next-expenses", []), ("next-expense-create", []), ("next-expense-edit", [expense.pk])):
            url = reverse(name, args=args)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, self.payload()).status_code, 403)
        self.assertEqual(m.Expense.objects.count(), 1)
        self.assertFalse(m.Document.objects.exists())
