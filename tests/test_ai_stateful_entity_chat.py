from pathlib import Path

from django.test import SimpleTestCase

from erp import assistant_views


class AIStatefulEntityChatRegressionTests(SimpleTestCase):
    def test_client_alias_is_a_customer_route_and_not_a_search_term(self):
        self.assertEqual(assistant_views._requested_entity_route("client"), "customers")
        self.assertEqual(assistant_views._requested_entity_route("find ashkan client"), "customers")
        self.assertEqual(assistant_views._search_terms("find ashkan client"), ["ashkan"])

    def test_project_and_employee_aliases_are_normalized(self):
        self.assertEqual(assistant_views._requested_entity_route("project"), "projects")
        self.assertEqual(assistant_views._requested_entity_route("Mitarbeiter"), "employees")
        self.assertEqual(assistant_views._requested_entity_route("Termin"), "appointments")

    def test_short_history_is_compacted_for_followup_reasoning(self):
        payload = {"history": [
            {"role": "user", "content": "find ashkan"},
            {"role": "assistant", "content": "Ich habe Ashkan Asaid als Kunden gefunden."},
            {"role": "tool", "content": "ignore"},
        ]}
        history = assistant_views._compact_assistant_history(payload)
        self.assertEqual([item["role"] for item in history], ["user", "assistant"])
        self.assertIn("Ashkan Asaid", history[-1]["content"])

    def test_frontend_persists_history_and_renders_real_result_links(self):
        root = Path(__file__).resolve().parents[1]
        js = (root / "static/js/kayi-next.js").read_text(encoding="utf-8")
        backend = (root / "erp/assistant_views.py").read_text(encoding="utf-8")
        css = (root / "static/css/kayi-next.css").read_text(encoding="utf-8")
        base = (root / "templates/rebuild/base.html").read_text(encoding="utf-8")
        for marker in ("kayi-assistant-history-v3", "addEntityResults", "history:priorHistory", "nx-assistant-result"):
            self.assertIn(marker, js)
        for marker in ("_resolve_entity_search", "_direct_entity_response", "conversation_history", "entity_focus"):
            self.assertIn(marker, backend)
        self.assertIn("A+Bau STATEFUL ENTITY CHAT 2026-08-11", css)
        self.assertIn("kayi-next.js", base)
        self.assertRegex(base, r"kayi-next\.js.*\?v=20260818-scope-sidebar-ui-1")
        self.assertNotIn("Keine irreversible Aktion wurde automatisch ausgeführt.", js)
