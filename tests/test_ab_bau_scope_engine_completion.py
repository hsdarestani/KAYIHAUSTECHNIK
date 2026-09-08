from pathlib import Path
from django.test import SimpleTestCase
from erp.ai_scope_planner import catalog_semantic_match, plan_scope_message

class Session(dict): modified = False

class ScopeEngineCompletionTests(SimpleTestCase):
    def test_abgedeckt_triggers_floor_cover_and_occupied_question(self):
        session = Session(); result = plan_scope_message("Wir haben eine Wohnung mit 90 qm. Alle Wände müssen gestrichen werden und der Boden muss abgedeckt werden.", session, [])
        by_key = {item["key"]: item for item in result["scope_items"]}; self.assertEqual(by_key["paint.wall.primer"]["quantity_display"], "225"); self.assertEqual(by_key["protect.floor"]["quantity_display"], "90")
        result = plan_scope_message("Ja, der Untergrund ist geeignet.", session, []); self.assertIn("bewohnt", result["scope_question"])
    def test_off_order_occupied_fact_is_kept_in_scope(self):
        session = Session(); plan_scope_message("90 qm Wohnung, alle Wände streichen", session, []); plan_scope_message("ja", session, []); result = plan_scope_message("Ja, die Wohnung ist bewohnt und möbliert.", session, [])
        self.assertIsNotNone(result); state = session["ab_bau_scope_planner_v1"]; self.assertTrue(state["facts"]["occupied"]); self.assertNotIn("door_count", state["facts"])
    def test_furniture_number_never_becomes_door_number(self):
        session = Session(); plan_scope_message("90 qm Wohnung, alle Wände streichen, Untergrund geeignet", session, []); result = plan_scope_message("12 Möbelstücke", session, [])
        self.assertIsNotNone(result); state = session["ab_bau_scope_planner_v1"]; self.assertEqual(state["facts"]["furniture_count"], 12); self.assertNotEqual(state["facts"].get("door_count"), 12)
    def test_semantic_counts_doors_and_windows(self):
        session = Session(); plan_scope_message("60 qm Wohnung, Wände streichen, Untergrund geeignet", session, []); plan_scope_message("3 Türen", session, []); self.assertEqual(session["ab_bau_scope_planner_v1"]["facts"]["door_count"], 3); plan_scope_message("4 Fenster", session, []); self.assertEqual(session["ab_bau_scope_planner_v1"]["facts"]["window_count"], 4)
    def test_natural_damage_phrase_is_recognized(self):
        session = Session(); plan_scope_message("60 qm Wohnung, Wände streichen, Untergrund geeignet, 2 Türen, 3 Fenster", session, []); result = plan_scope_message("Ja, es gibt bereits Schäden an Türen und Möbeln.", session, []); self.assertTrue(session["ab_bau_scope_planner_v1"]["facts"]["damage_present"]); self.assertTrue(any(item["key"] == "documentation.damage" for item in result["scope_items"]))
    def test_bad_catalog_examples_are_rejected(self):
        cases = [
            ({"key":"paint.wall.coat","unit":"m²"}, {"name":"Buntsteinputz, ca. 2 mm, Wände; Zwischenbeschichtung mit Dispersionsfarbe","unit":"m²"}),
            ({"key":"paint.ceiling.coat","unit":"m²"}, {"name":"Tapeten entfernen Decke","unit":"m²"}),
            ({"key":"bath.walltile.install","unit":"m²"}, {"name":"Brandschutz Dämmwolle ums Fallrohr verlegen","unit":"m²"}),
            ({"key":"bath.floor.seal","unit":"m²"}, {"name":"Abbruch und Entsorgung vorhandene Parkettböden","unit":"m²"}),]
        for scope, candidate in cases: self.assertFalse(catalog_semantic_match(scope, candidate), (scope, candidate))
    def test_good_catalog_examples_are_accepted(self):
        cases = [
            ({"key":"paint.wall.primer","unit":"m²"}, {"name":"Wandflächen einmal lösemittelfrei grundieren","unit":"m²"}),
            ({"key":"paint.wall.coat","unit":"m²"}, {"name":"Wandflächen mit Dispersionsfarbe zweimal streichen","unit":"m²"}),
            ({"key":"bath.floor.seal","unit":"m²"}, {"name":"Boden im Bad mit Verbundabdichtung abdichten","unit":"m²"}),]
        for scope, candidate in cases: self.assertTrue(catalog_semantic_match(scope, candidate), (scope, candidate))
    def test_appointment_ui_uses_shared_scope_engine(self):
        template = Path("templates/rebuild/appointment_detail.html").read_text(encoding="utf-8"); views = Path("erp/field_authorization_views.py").read_text(encoding="utf-8"); js = Path("static/js/field-authorization.js").read_text(encoding="utf-8")
        self.assertIn("data-auth-scope-planner", template); self.assertIn("_AppointmentScopeSession", views); self.assertIn("plan_scope_message(raw, scoped_session, [])", views); self.assertIn('"mode": "scope"', views); self.assertIn("bindAuthorizationScopePlanner", js)
    def test_appointment_scope_state_is_isolated_from_global_state(self):
        views = Path("erp/field_authorization_views.py").read_text(encoding="utf-8"); self.assertIn('f"{STATE_KEY}:appointment:{event_id}"', views)
