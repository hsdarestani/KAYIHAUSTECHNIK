from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import CalendarEvent, Customer, Organization, Project, UserProfile


class ToolTimePhase15AppointmentCustomerTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI phase15")
        self.user = User.objects.create_user("phase15-office", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="phase15-office", password="safe-test-password"))
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P15-1",
            type="business",
            company="Direktkunde Phase15",
            street="Kundenstraße 15",
            postal_code="60314",
            city="Frankfurt",
        )
        self.project_customer = Customer.objects.create(
            organization=self.org,
            number="K-P15-2",
            type="business",
            company="Projektkunde Phase15",
            street="Projektweg 2",
            postal_code="60315",
            city="Frankfurt",
        )
        self.project = Project.objects.create(
            organization=self.org,
            number="P-P15-1",
            title="Phase 15 Projekt",
            customer=self.project_customer,
            status="planning",
            priority="normal",
        )

    def _payload(self, title, *, customer=None, project=None, location=""):
        form = rebuild_views.AppointmentForm(organization=self.org)
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(hours=2)
        end = start + timedelta(hours=1)
        data = {
            "title": title,
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": end.strftime("%Y-%m-%dT%H:%M"),
            "location": location,
            "project": str(project.pk) if project is not None else "",
            "customer_filter": str(customer.pk) if customer is not None else "",
        }
        for name, field in form.fields.items():
            if name in data or not field.required:
                continue
            choices = list(getattr(field, "choices", []) or [])
            usable = [value for value, _label in choices if str(value) != ""]
            data[name] = str(usable[0]) if usable else "Test"
        return data

    def test_customer_only_create_persists_customer_and_address(self):
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload("Direkter Kundentermin", customer=self.customer),
        )
        self.assertEqual(response.status_code, 302)
        event = CalendarEvent.objects.get(organization=self.org, title="Direkter Kundentermin")
        self.assertIsNone(event.project_id)
        self.assertEqual(event.customer_id, self.customer.pk)
        self.assertEqual(event.location, "Kundenstraße 15, 60314 Frankfurt")

    def test_project_customer_overrides_mismatched_customer_filter(self):
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload("Projekttermin Phase15", customer=self.customer, project=self.project),
        )
        self.assertEqual(response.status_code, 302)
        event = CalendarEvent.objects.get(organization=self.org, title="Projekttermin Phase15")
        self.assertEqual(event.project_id, self.project.pk)
        self.assertEqual(event.customer_id, self.project_customer.pk)

    def test_customer_only_event_is_filterable_searchable_and_mappable(self):
        self.client.post(
            reverse("next-appointment-create"),
            self._payload("Kundenfilter Phase15", customer=self.customer),
        )
        event = CalendarEvent.objects.get(organization=self.org, title="Kundenfilter Phase15")
        anchor = timezone.localtime(event.starts_at).date().isoformat()

        filtered = self.client.get(reverse("next-appointments"), {
            "view": "list", "date": anchor, "customer": str(self.customer.pk),
        })
        self.assertEqual(filtered.status_code, 200)
        self.assertContains(filtered, "Kundenfilter Phase15")
        self.assertContains(filtered, "Direktkunde Phase15")

        searched = self.client.get(reverse("next-appointments"), {
            "view": "list", "date": anchor, "q": "Direktkunde Phase15",
        })
        self.assertContains(searched, "Kundenfilter Phase15")

        mapped = self.client.get(reverse("next-appointments"), {"view": "map", "date": anchor})
        self.assertEqual(mapped.status_code, 200)
        self.assertContains(mapped, "Kundenfilter Phase15")
        self.assertContains(mapped, "Kundenstraße 15, 60314 Frankfurt")

    def test_edit_prefills_and_persists_direct_customer(self):
        self.client.post(
            reverse("next-appointment-create"),
            self._payload("Edit Kunde Phase15", customer=self.customer),
        )
        event = CalendarEvent.objects.get(organization=self.org, title="Edit Kunde Phase15")
        response = self.client.get(reverse("next-appointment-edit", args=[event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-initial-customer="{self.customer.pk}"')
        self.assertContains(response, 'data-initial-project=""')

        response = self.client.post(
            reverse("next-appointment-edit", args=[event.pk]),
            self._payload("Edit Kunde Phase15 neu", customer=self.project_customer, location=""),
        )
        self.assertEqual(response.status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.customer_id, self.project_customer.pk)
        self.assertEqual(event.title, "Edit Kunde Phase15 neu")
        self.assertEqual(event.location, "Projektweg 2, 60315 Frankfurt")

    def test_customer_only_detail_identifies_customer_and_project_gap(self):
        self.client.post(
            reverse("next-appointment-create"),
            self._payload("Detail Kunde Phase15", customer=self.customer),
        )
        event = CalendarEvent.objects.get(organization=self.org, title="Detail Kunde Phase15")
        response = self.client.get(reverse("next-appointment-detail", args=[event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Direktkunde Phase15")
        self.assertContains(response, "Ohne Projekt")
