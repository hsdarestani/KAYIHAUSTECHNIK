from pathlib import Path

from django.test import SimpleTestCase


class LegacyAIRoleGuardContractTests(SimpleTestCase):
    def test_legacy_ai_provider_calls_are_admin_guarded(self):
        source = Path("erp/api.py").read_text(encoding="utf-8")
        marker = "A_BAU_LEGACY_AI_ADMIN_GUARD 2026-08-12"
        self.assertGreaterEqual(source.count(marker), 2)
        self.assertIn("role_for(request.user) != _ai_perm.ADMIN", source)

        chat_guard = source.rfind(marker, 0, source.index("output, usage = chat(org, history, context)"))
        self.assertGreaterEqual(chat_guard, 0)
        self.assertLess(source.index("role_for(request.user) != _ai_perm.ADMIN", chat_guard), source.index("output, usage = chat(org, history, context)"))

        photo_call = "result = analyze_room_photos(organization_for(request.user), images, calibration)"
        photo_guard = source.rfind(marker, 0, source.index(photo_call))
        self.assertGreaterEqual(photo_guard, 0)
        self.assertLess(source.index("role_for(request.user) != _ai_perm.ADMIN", photo_guard), source.index(photo_call))

    def test_unknown_global_assistant_paths_fail_closed(self):
        permissions = Path("erp/ai_role_permissions.py").read_text(encoding="utf-8")
        self.assertIn("if not route:", permissions)
        self.assertIn("return role_for(user) == ADMIN", permissions)
        self.assertNotIn("if not route or route in allowed_navigation_routes(user):", permissions)
