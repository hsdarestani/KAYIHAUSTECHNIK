from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from erp.models import Organization, UserProfile
from erp.services.ai import chat


class FakeModelNotFound(Exception):
    body = {"error": {"code": "model_not_found"}}


@override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-5", OPENAI_FALLBACK_MODEL="gpt-4.1-mini")
class AIProviderFallbackTests(TestCase):
    @patch("erp.services.ai.get_client")
    def test_chat_retries_access_failure_with_fallback_model(self, get_client):
        client = Mock()
        client.responses.create.side_effect = [
            FakeModelNotFound("organization must be verified"),
            SimpleNamespace(output_text="OK", usage=None),
        ]
        get_client.return_value = client
        output, usage = chat(None, [{"role": "user", "content": "Hallo"}])
        self.assertEqual(output, "OK")
        self.assertEqual(usage, {})
        self.assertEqual(client.responses.create.call_count, 2)
        self.assertEqual(client.responses.create.call_args_list[0].kwargs["model"], "gpt-5")
        self.assertEqual(client.responses.create.call_args_list[1].kwargs["model"], "gpt-4.1-mini")

    @patch("erp.services.ai.get_client")
    def test_chat_does_not_hide_non_access_provider_errors(self, get_client):
        client = Mock()
        client.responses.create.side_effect = RuntimeError("quota exhausted")
        get_client.return_value = client
        with self.assertRaisesRegex(RuntimeError, "quota exhausted"):
            chat(None, [{"role": "user", "content": "Hallo"}])
        self.assertEqual(client.responses.create.call_count, 1)


class AISafeApiErrorTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI AI Error Test")
        self.user = User.objects.create_user("ai-admin", password="very-secure-password")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.client = Client()
        self.client.login(username="ai-admin", password="very-secure-password")

    @patch("erp.api.chat", side_effect=RuntimeError("secret provider detail"))
    def test_ai_chat_does_not_leak_provider_error(self, _chat):
        # KAYI_STORE_CONSENT_FOR_test_ai_chat_does_not_leak_provider_error
        profile = self.user.profile
        prefs = dict(profile.preferences or {})
        prefs.update({"ai_third_party_consent_at": "2026-08-10T00:00:00+00:00", "ai_third_party_consent_version": "2026-08-10", "ai_third_party_consent_revoked_at": None})
        profile.preferences = prefs
        profile.save(update_fields=["preferences", "updated_at"])
        response = self.client.post(reverse("api-ai-chat"), {"message": "Hallo"}, content_type="application/json")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret provider detail", response.content.decode())
        self.assertIn("momentan nicht erreichbar", response.json()["error"])

    @patch("erp.api.analyze_room_photos", side_effect=RuntimeError("secret photo provider detail"))
    def test_photo_api_does_not_leak_provider_error(self, _analyze):
        # KAYI_STORE_CONSENT_FOR_test_photo_api_does_not_leak_provider_error
        profile = self.user.profile
        prefs = dict(profile.preferences or {})
        prefs.update({"ai_third_party_consent_at": "2026-08-10T00:00:00+00:00", "ai_third_party_consent_version": "2026-08-10", "ai_third_party_consent_revoked_at": None})
        profile.preferences = prefs
        profile.save(update_fields=["preferences", "updated_at"])
        from django.core.files.uploadedfile import SimpleUploadedFile
        image = SimpleUploadedFile("room.jpg", b"\xff\xd8\xff\xe0room", content_type="image/jpeg")
        response = self.client.post(reverse("api-room-measurement-analyze"), {"images": image})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("secret photo provider detail", response.content.decode())
        self.assertIn("momentan nicht ausgewertet", response.json()["error"])
