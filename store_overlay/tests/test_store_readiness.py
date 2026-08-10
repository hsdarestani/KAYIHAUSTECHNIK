from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from erp.models import Organization, UserProfile
from erp.store_views import AI_CONSENT_VERSION, has_ai_consent


class StoreReadinessTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI Store Test")
        self.user = get_user_model().objects.create_user(username="storetest", email="store@example.test", password="Secret123!")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.organization = self.org
        self.profile.save()

    def test_public_privacy_support_and_deletion_pages_are_reachable(self):
        for name, marker in (
            ("store-privacy", "Datenschutzerklärung"),
            ("store-support", "KAYI Support"),
            ("store-account-deletion", "Konto und Daten löschen"),
        ):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, marker)

    def test_privacy_page_discloses_google_arcore(self):
        response = self.client.get(reverse("store-privacy"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Google Play Services for AR (ARCore)")
        self.assertContains(response, "https://policies.google.com/privacy")
        self.assertContains(response, "https://policies.google.com/terms")

    def test_external_deletion_request_does_not_require_installed_app(self):
        response = self.client.post(reverse("store-account-deletion"), {"identifier": self.user.email})
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertIn("deletion_requested_at", self.profile.preferences)
        self.assertEqual(self.profile.preferences.get("deletion_source"), "public_web")
        self.assertContains(response, "Anfrage erhalten")

    def test_ai_consent_is_explicit_versioned_and_revocable(self):
        self.client.force_login(self.user)
        self.assertFalse(has_ai_consent(self.user))
        response = self.client.post(reverse("store-ai-consent"), {"action": "accept"})
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.profile.preferences.get("ai_third_party_consent_version"), AI_CONSENT_VERSION)
        self.assertTrue(has_ai_consent(self.user))
        response = self.client.post(reverse("store-ai-consent"), {"action": "revoke"})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(has_ai_consent(self.user))

    def test_primary_settings_exposes_store_privacy_controls(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("next-settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "KI-Datenverarbeitung")
        self.assertContains(response, "Konto und Daten löschen")
        self.assertContains(response, reverse("store-privacy"))
