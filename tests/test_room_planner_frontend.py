from pathlib import Path

from django.test import SimpleTestCase


class RoomPlannerFrontendContractTests(SimpleTestCase):
    def test_assembled_webgl_engine_keeps_interaction_contract(self):
        root = Path(__file__).resolve().parents[1]
        js = (root / "static/js/room-planner.js").read_text(encoding="utf-8")
        template = (root / "templates/rebuild/room_planner.html").read_text(encoding="utf-8")

        for marker in (
            "KAYI_ROOM_PLANNER_PRO",
            "new THREE.WebGLRenderer",
            "function showDragMetrics",
            "function renderDimensionGuides",
            "function collisionSet",
            "function snapObject",
            "function buildWallWithOpenings",
            "const submit=$('[data-rp-run-vision]',visionForm)",
        ):
            self.assertIn(marker, js)

        self.assertIn('data-rp-run-vision', template)
        self.assertIn('data-rp-drag-metrics', template)
        self.assertIn('three@0.170.0', template)

    def test_all_library_objects_are_rendered_as_threejs_scene_objects(self):
        root = Path(__file__).resolve().parents[1]
        js = (root / "static/js/room-planner.js").read_text(encoding="utf-8")
        for kind in (
            "shower", "vanity", "sink", "toilet", "bathtub", "radiator", "boiler", "water_heater", "heat_pump",
            "cabinet", "wardrobe", "shelf", "table", "chair", "sofa", "bed", "kitchen_base", "kitchen_wall",
            "fridge", "oven", "stove", "dishwasher", "washing_machine", "dryer", "socket", "switch", "pipe", "drain", "column",
        ):
            self.assertIn(kind, js)
        self.assertIn("createObjectMesh", js)
