from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import CalendarEvent, Customer, Organization, Project, Quote, UserProfile


class ABauV3HistoryLifecycleTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau V3 Closeout Test")
        User = get_user_model()
        self.user = User.objects.create_user(username="v3-closeout-office", password="secret")
        profile = self.user.profile
        profile.organization = self.org
        profile.role = UserProfile.Role.ADMIN
        profile.is_mobile_worker = False
        profile.save()
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-V3C",
            type="private",
            first_name="Mara",
            last_name="Muster",
            active=True,
        )
        self.project = Project.objects.create(
            organization=self.org,
            customer=self.customer,
            number="P-V3C",
            title="Badmodernisierung",
            status="inquiry",
            archived=False,
        )

    def test_customer_v3_keeps_cockpit_and_adds_history_and_direct_documents(self):
        response = self.client.get(reverse("next-customer-detail", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 200)
        for marker in ("data-ab-v3-customer-detail", "Kundenverlauf", "＋ Angebot", "＋ Rechnung", "Umsatz (netto)"):
            self.assertContains(response, marker)
        self.assertNotContains(response, "next-appointment-create")

    def test_direct_quote_uses_hidden_customer_document_project(self):
        response = self.client.post(reverse("next-customer-quote-create", args=[self.customer.pk]))
        self.assertEqual(response.status_code, 302)
        quote = Quote.objects.get(organization=self.org)
        self.assertEqual(quote.project.customer_id, self.customer.pk)
        self.assertTrue(quote.project.archived)
        self.assertEqual(quote.status, "draft")
        detail = self.client.get(reverse("next-customer-detail", args=[self.customer.pk]))
        self.assertContains(detail, "Direkt für Kunde")
        self.assertNotContains(detail, quote.project.title)

    def test_project_v3_keeps_room_planner_finance_guard_and_adds_lifecycle(self):
        response = self.client.get(reverse("next-project-detail", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        for marker in ("data-ab-v3-project-detail", "Projektverlauf", "Projekt abschließen", "Projekt abbrechen", "Raum & 3D", "Finanzen"):
            self.assertContains(response, marker)

    def test_planned_appointment_blocks_project_completion(self):
        CalendarEvent.objects.create(
            organization=self.org,
            project=self.project,
            customer=self.customer,
            created_by=self.user,
            title="Montage",
            type="installation",
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=1),
        )
        response = self.client.post(reverse("next-project-lifecycle", args=[self.project.pk]), {"action": "complete"})
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertFalse(self.project.archived)
        self.assertNotEqual(self.project.status, "completed")

    def test_empty_project_can_complete_and_reactivate(self):
        self.client.post(reverse("next-project-lifecycle", args=[self.project.pk]), {"action": "complete"})
        self.project.refresh_from_db()
        self.assertTrue(self.project.archived)
        self.assertEqual(self.project.status, "completed")
        self.client.post(reverse("next-project-lifecycle", args=[self.project.pk]), {"action": "reactivate"})
        self.project.refresh_from_db()
        self.assertFalse(self.project.archived)
        self.assertEqual(self.project.status, "inquiry")
