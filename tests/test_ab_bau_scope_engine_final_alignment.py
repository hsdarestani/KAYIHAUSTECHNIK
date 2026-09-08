from pathlib import Path
from django.test import SimpleTestCase


class ScopeEngineFinalAlignmentTests(SimpleTestCase):
    def test_global_scope_assets_are_cache_busted_to_final_version(self):
        base = Path("templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("kayi-next.css' %}?v=20260818-scope-sidebar-ui-1", base)
        self.assertIn("kayi-next.js' %}?v=20260818-scope-sidebar-ui-1", base)

    def test_direct_bo_search_contract_matches_current_specialized_ui(self):
        editor = Path("templates/rebuild/document_editor.html").read_text(encoding="utf-8")
        self.assertIn("B&O-Position suchen", editor)
        self.assertIn("A+Bau-Vorlagen mit Preis", editor)
        self.assertIn("data-bo-direct-search", editor)

    def test_scope_completion_behavior_tests_are_still_present(self):
        test = Path("tests/test_ab_bau_scope_engine_completion.py").read_text(encoding="utf-8")
        for needle in ("test_abgedeckt_triggers_floor_cover", "test_furniture_number_never_becomes_door_number", "test_bad_catalog_examples_are_rejected", "test_appointment_ui_uses_shared_scope_engine"):
            self.assertIn(needle, test)

    def test_unmatched_scope_position_is_explicit_and_selectable(self):
        js = Path("static/js/kayi-next.js").read_text(encoding="utf-8")
        self.assertIn("Keine sichere Katalogposition gefunden.", js)
        self.assertIn("data-scope-catalog-choose", js)
        self.assertIn("Position wählen", js)
        self.assertIn("Katalog wählen", js)

    def test_desktop_sidebar_background_covers_full_viewport(self):
        css = Path("static/css/kayi-next.css").read_text(encoding="utf-8")
        self.assertIn("@media(min-width:861px)", css)
        self.assertIn("linear-gradient(90deg,#111418 0 var(--nx-sidebar)", css)
        self.assertIn("height:100vh!important", css)
        self.assertIn("overflow-y:auto!important", css)
