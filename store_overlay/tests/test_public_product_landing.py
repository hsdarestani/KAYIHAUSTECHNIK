from pathlib import Path

from django.test import TestCase
from django.urls import reverse


class PublicProductLandingTests(TestCase):
    def test_anonymous_root_is_product_landing_not_login_redirect(self):
        response = self.client.get(reverse("store-landing"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "store/landing.html")
        self.assertContains(response, "Betriebssoftware für Bau & Handwerk")
        self.assertContains(response, "Vom ersten Termin")
        self.assertContains(response, "Ein System statt fünf einzelner Tools")
        self.assertContains(response, "KI & 3D Room Planner")
        self.assertContains(response, "Zum Login")

    def test_landing_keeps_public_store_links(self):
        response = self.client.get(reverse("store-landing"))
        self.assertContains(response, reverse("store-privacy"))
        self.assertContains(response, reverse("store-support"))
        self.assertContains(response, reverse("store-account-deletion"))

    def test_landing_source_stays_standalone_and_mobile_responsive(self):
        root = Path(__file__).resolve().parents[1]
        landing = (root / "templates" / "store" / "landing.html").read_text(encoding="utf-8")
        self.assertIn('name="viewport"', landing)
        self.assertIn("@media(max-width:720px)", landing)
        self.assertIn("brand/ab-bau-logo.png", landing)
        self.assertNotIn("Registrieren", landing)
        self.assertNotIn("Kostenlos starten", landing)
