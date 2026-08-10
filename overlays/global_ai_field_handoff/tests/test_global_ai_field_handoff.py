from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import CalendarEvent, Customer, Document, Organization, Project, UserProfile


PNG_1X1 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


class GlobalAIAndFieldHandoffTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI Global KI Test")
        self.user = User.objects.create_user("global-ai-admin", password="very-secure-password", email="global@example.com")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-2026-9901",
            type="private",
            first_name="Max",
            last_name="Müller",
            street="Teststraße 1",
            postal_code="60311",
            city="Frankfurt",
        )
        self.project = Project.objects.create(
            organization=self.org,
            number="P-2026-9901",
            title="Bad Müller",
            customer=self.customer,
            status="confirmed",
        )
        now = timezone.now()
        self.event = CalendarEvent.objects.create(
            organization=self.org,
            title="Vor-Ort-Termin",
            type="site",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            project=self.project,
            created_by=self.user,
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="global-ai-admin", password="very-secure-password"))

    def test_profile_menu_and_global_assistant_are_on_every_next_page(self):
        for name in ("next-dashboard", "next-customers", "next-projects", "next-appointments"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "data-profile-toggle")
            self.assertContains(response, "data-profile-menu")
            self.assertContains(response, "data-global-assistant-form")
            self.assertContains(response, "data-assistant-drawer")

    def test_global_assistant_requires_explicit_ai_consent(self):
        response = self.client.post(
            reverse("next-assistant-command"),
            data='{"message":"Wähle Kunde Müller","fields":[]}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 428)
        self.assertTrue(response.json()["consent_required"])

    def test_field_appointment_exposes_record_sign_and_pdf_handoff(self):
        response = self.client.get(reverse("next-appointment-detail", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        for marker in (
            "Vor-Ort-Sprachnotiz aufnehmen",
            "Aufnahme mit KI auswerten",
            "Gemeinsam geprüft",
            "Kundenunterschrift",
            "Einsatz abschließen & PDF erstellen",
            "data-handoff-result",
        ):
            self.assertContains(response, marker)

    def test_voice_transcription_requires_ai_consent_before_upload(self):
        response = self.client.post(reverse("next-appointment-voice", args=[self.event.pk]), data={})
        self.assertEqual(response.status_code, 428)
        self.assertTrue(response.json()["consent_required"])

    def test_signed_field_completion_creates_pdf_document(self):
        response = self.client.post(
            reverse("next-appointment-document", args=[self.event.pk]),
            data={
                "report_text": "Rohrverbindung erneuert und Anlage geprüft.",
                "services": "Rohrverbindung erneuern\nFunktionsprüfung",
                "material": "2 Pressfittings",
                "customer_name": "Max Müller",
                "customer_reviewed": "1",
                "signature_data": PNG_1X1,
                "voice_transcript": "Wir haben die Rohrverbindung erneuert und zwei Pressfittings verwendet.",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertIn("pdf_url", payload)
        document = Document.objects.filter(project=self.project, metadata__event_id=self.event.pk, metadata__kind="field_handoff_pdf").latest("created_at")
        self.assertEqual(document.mime_type, "application/pdf")
        self.assertGreater(document.size, 500)
        self.assertTrue(document.file.name.endswith(".pdf"))
