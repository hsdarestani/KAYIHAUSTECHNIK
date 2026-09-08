from django.test import SimpleTestCase

from erp.ai_scope_planner import WALL_AREA_FACTOR, plan_scope_message


class Session(dict):
    modified = False


class AIScopePlannerTests(SimpleTestCase):
    def test_wall_painting_uses_floor_area_factor_and_required_coats(self):
        session = Session()
        result = plan_scope_message(
            "Wir haben eine Wohnung mit 90 qm und alle Wände müssen gestrichen werden.",
            session,
            [],
        )
        by_key = {item["key"]: item for item in result["scope_items"]}
        self.assertEqual(str(WALL_AREA_FACTOR), "2.5")
        self.assertEqual(by_key["paint.wall.primer"]["quantity_display"], "225")
        self.assertEqual(by_key["paint.wall.coat"]["quantity_display"], "225")
        self.assertIn("90 m² × 2,5 = 225 m²", result["reply"])
        self.assertIn("Untergründe", result["scope_question"])

    def test_ceiling_uses_floor_area_without_wall_multiplier(self):
        session = Session()
        result = plan_scope_message("Wohnung 90 m2, die Decke komplett streichen.", session, [])
        by_key = {item["key"]: item for item in result["scope_items"]}
        self.assertEqual(by_key["paint.ceiling.primer"]["quantity_display"], "90")
        self.assertEqual(by_key["paint.ceiling.coat"]["quantity_display"], "90")

    def test_bad_substrate_expands_prep_and_wallpaper_followup(self):
        session = Session()
        plan_scope_message("80 qm Wohnung, alle Wände streichen", session, [])
        result = plan_scope_message("nein", session, [])
        self.assertTrue(any(item["key"] == "paint.substrate.fill" for item in result["scope_items"]))
        self.assertIn("Tapeten", result["scope_question"])
        result = plan_scope_message("ja", session, [])
        wallpaper = next(item for item in result["scope_items"] if item["key"] == "paint.wallpaper.remove")
        self.assertEqual(wallpaper["quantity_display"], "200")

    def test_floor_covering_occupied_flow_never_invents_counts(self):
        session = Session()
        result = plan_scope_message("90 qm Wohnung, Boden abdecken", session, [])
        self.assertIn("bewohnt", result["scope_question"])
        result = plan_scope_message("bewohnt", session, [])
        by_key = {item["key"]: item for item in result["scope_items"]}
        self.assertEqual(by_key["protect.floor"]["quantity_display"], "90")
        self.assertEqual(by_key["protect.furniture"]["quantity_display"], "offen")
        self.assertEqual(by_key["protect.moving"]["quantity_display"], "offen")
        self.assertEqual(by_key["protect.difficulty"]["quantity_display"], "1")
        self.assertIn("Stückzahl", result["scope_question"])

    def test_door_window_and_damage_questions_are_sequential(self):
        session = Session()
        plan_scope_message("60 qm Wohnung, Wände streichen, Untergrund geeignet", session, [])
        result = plan_scope_message("3 Türen", session, [])
        self.assertEqual(session["ab_bau_scope_planner_v1"]["facts"]["door_count"], 3)
        result = plan_scope_message("4 Fenster", session, [])
        self.assertIn("Schäden", result["scope_question"])

    def test_bathroom_baseline_and_individual_technical_questions(self):
        session = Session()
        result = plan_scope_message("Wir möchten ein neues Bad komplett sanieren.", session, [])
        keys = {item["key"] for item in result["scope_items"]}
        self.assertTrue({
            "bath.walltile.demolish", "bath.floortile.demolish", "bath.substrate.fill",
            "bath.substrate.prime", "bath.walltile.install", "bath.floor.seal",
            "bath.floortile.install",
        }.issubset(keys))
        self.assertIn("Bodenfläche", result["scope_question"])
        plan_scope_message("8", session, [])
        result = plan_scope_message("24", session, [])
        self.assertIn("Wasserleitungen", result["scope_question"])
        result = plan_scope_message("Leitungen neu", session, [])
        keys = {item["key"] for item in result["scope_items"]}
        self.assertIn("bath.water.cold", keys)
        self.assertIn("bath.water.hot", keys)
        self.assertIn("laufende Meter", result["scope_question"])

    def test_bathroom_sanitary_answers_create_piece_positions(self):
        session = Session()
        plan_scope_message("Bad sanieren, Bodenfläche 8 qm, Wandfläche 24 qm, Leitungen bleiben im Bestand", session, [])
        result = plan_scope_message("ja", session, [])
        self.assertTrue(any(item["key"] == "bath.fixture.sink" and item["quantity_display"] == "1" for item in result["scope_items"]))

    def test_visible_catalog_is_matched_but_quantity_stays_trade_quantity(self):
        session = Session()
        catalog = [
            {"name": "Wände grundieren", "code": "M-01", "unit": "m²"},
            {"name": "Dispersionsfarbe Wände streichen", "code": "M-02", "unit": "m²"},
        ]
        result = plan_scope_message("100 qm Wohnung, alle Wände streichen", session, catalog)
        actions = {action["scope_key"]: action for action in result["actions"]}
        self.assertEqual(actions["paint.wall.primer"]["quantity"], 250.0)
        self.assertEqual(actions["paint.wall.coat"]["quantity"], 250.0)
        self.assertEqual(actions["paint.wall.primer"]["count"], 1)

    def test_unrelated_messages_fall_through_to_general_assistant(self):
        self.assertIsNone(plan_scope_message("Finde den Kunden Müller", Session(), []))
