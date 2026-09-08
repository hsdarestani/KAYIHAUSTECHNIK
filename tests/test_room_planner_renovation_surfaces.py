from django.test import SimpleTestCase

from erp.services.room_planner_state import blank_room_state, normalize_room_state


class RoomPlannerRenovationSurfaceTests(SimpleTestCase):
    def test_structured_renovation_survives_normalization(self):
        state = blank_room_state()
        state["renovation"] = {
            "intent": {"preserve_positions": True, "allow_relayout": False, "replace_sanitary_in_place": True},
            "surface_plan": {
                "floor": {"finish": "Fliesen", "tile_color": "hellgrau", "tile_width_cm": 60, "tile_height_cm": 60},
                "wet_zone": {"present": True, "height_m": 2.0, "wall_tile_color": "weiß", "tile_width_cm": 30, "tile_height_cm": 60, "applies_to": ["right"], "basis": "Badewanne"},
                "other_walls": {"height_m": 1.4, "wall_tile_color": "weiß", "tile_width_cm": 30, "tile_height_cm": 60, "upper_finish": "Q3 gespachtelt und gestrichen"},
                "ceiling": {"finish": "Q3 gespachtelt und gestrichen"},
            },
            "work_scope": {"replace_bathtub": True, "replace_toilet": True, "replace_sink": True, "door_finish": "geschliffen und lackiert"},
            "source_command": "Bad sanieren",
        }
        normalized = normalize_room_state(state)
        plan = normalized["renovation"]["surface_plan"]
        self.assertEqual(plan["floor"]["tile_width_cm"], 60.0)
        self.assertEqual(plan["wet_zone"]["height_m"], 2.0)
        self.assertEqual(plan["wet_zone"]["applies_to"], ["right"])
        self.assertEqual(plan["other_walls"]["height_m"], 1.4)
        self.assertIn("Q3", plan["other_walls"]["upper_finish"])
        self.assertTrue(normalized["renovation"]["work_scope"]["replace_bathtub"])

    def test_unknown_renovation_payload_is_not_persisted(self):
        state = blank_room_state()
        state["renovation"] = {"unexpected": {"huge": "x" * 10000}, "source_command": "x" * 5000}
        normalized = normalize_room_state(state)
        self.assertNotIn("unexpected", normalized["renovation"])
        self.assertEqual(len(normalized["renovation"]["source_command"]), 4000)
