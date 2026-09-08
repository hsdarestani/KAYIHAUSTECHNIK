import unittest
import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from erp.models import Customer, Organization, Project, RoomMeasurement, RoomModelRevision, UserProfile
from erp.services.numbering import next_number
from erp.services.room_models import normalize_room_model_state


class RoomModelEditorTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI Model Editor")
        self.user = User.objects.create_user("model-admin", password="very-secure-password")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.customer = Customer.objects.create(
            organization=self.org,
            number=next_number(self.org, "customer"),
            company="3D Kunde",
        )
        self.project = Project.objects.create(
            organization=self.org,
            number=next_number(self.org, "project"),
            title="Editierbares Bad",
            customer=self.customer,
        )
        self.measurement = RoomMeasurement.objects.create(
            organization=self.org,
            project=self.project,
            name="Bad EG",
            method=RoomMeasurement.Method.AR_LIDAR,
            status=RoomMeasurement.Status.CONFIRMED,
            length_m=Decimal("4.000"),
            width_m=Decimal("3.000"),
            height_m=Decimal("2.500"),
            confirmed_by=self.user,
        )
        self.client = Client()
        self.client.login(username="model-admin", password="very-secure-password")

    def state(self, length="4.200"):
        return {
            "schema_version": 2,
            "room": {"length_m": length, "width_m": "3.100", "height_m": "2.550"},
            "openings": [
                {"id": "door-1", "kind": "door", "wall": "back", "width_m": "0.900", "height_m": "2.000", "offset_m": "0.500", "sill_m": "0"},
                {"id": "window-1", "kind": "window", "wall": "right", "width_m": "1.200", "height_m": "1.000", "offset_m": "0.800", "sill_m": "0.900"},
            ],
            "objects": [{
                "id": "fixture-1", "kind": "shower", "x_m": "1.2", "z_m": "0.8",
                "width_m": "1.4", "depth_m": "0.9", "height_m": "2.2",
                "rotation_deg": "15", "color": "#78bfe0", "enabled": True,
            }],
            "materials": {
                "floor": "#30363d", "wall": "#f1eee8", "ceiling": "#ffffff",
                "accent": "#23415b", "grout_color": "#737b84", "pattern": "diagonal",
                "tile_width_cm": "60", "tile_height_cm": "120",
            },
            "lighting": {"brightness": "1.25", "warmth": "68"},
            "view": {"mode": "perspective", "rotation_deg": "35"},
        }

    def test_extended_model_state_normalizes_colors_sizes_and_lighting(self):
        normalized = normalize_room_model_state(self.state(), self.measurement)
        self.assertEqual(normalized["schema_version"], 2)
        self.assertEqual(normalized["materials"]["ceiling"], "#ffffff")
        self.assertEqual(normalized["materials"]["tile_height_cm"], "120.000")
        self.assertEqual(normalized["lighting"]["brightness"], "1.250")
        self.assertEqual(normalized["objects"][0]["width_m"], "1.400")
        self.assertEqual(normalized["objects"][0]["color"], "#78bfe0")

    def test_saving_model_creates_version_and_reopens_confirmed_measurement(self):
        response = self.client.post(
            reverse("configurator-model-save"),
            data=json.dumps({"measurement_id": self.measurement.pk, "label": "Fenster geprüft", "state": self.state()}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        revision = RoomModelRevision.objects.get()
        self.assertEqual(revision.revision, 1)
        self.assertEqual(revision.label, "Fenster geprüft")
        self.assertEqual(revision.state["materials"]["tile_height_cm"], "120.000")
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.length_m, Decimal("4.200"))
        self.assertEqual(self.measurement.deductions_area_m2, Decimal("3.000"))
        self.assertEqual(self.measurement.status, RoomMeasurement.Status.REVIEW)
        self.assertIsNone(self.measurement.confirmed_by)

    def test_each_save_creates_a_new_revision(self):
        endpoint = reverse("configurator-model-save")
        for label, length in (("Erster Stand", "4.100"), ("Zweiter Stand", "4.300")):
            response = self.client.post(endpoint, data=json.dumps({"measurement_id": self.measurement.pk, "label": label, "state": self.state(length)}), content_type="application/json")
            self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(list(RoomModelRevision.objects.order_by("revision").values_list("revision", flat=True)), [1, 2])
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.length_m, Decimal("4.300"))

    def test_invalid_geometry_is_rejected_without_revision(self):
        state = self.state(); state["room"]["height_m"] = "99"
        response = self.client.post(reverse("configurator-model-save"), data=json.dumps({"measurement_id": self.measurement.pk, "state": state}), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(RoomModelRevision.objects.exists())

    @unittest.skip("KAYI Next replaced the legacy nine-step wizard/tutorial; equivalent Next flow is covered by test_tooltime_rebuild and production browser smoke.")
    def test_project_wizard_renders_responsive_material_sources_and_inline_editor(self):
        response = self.client.get(reverse("project-create"))
        self.assertContains(response, "9-Schritte-Projektassistent")
        self.assertContains(response, 'class="material-source-grid"')
        self.assertContains(response, 'data-inline-room-model="1"')
        self.assertContains(response, 'data-model-ai-apply')
        self.assertContains(response, 'data-model-openings="front"')
        self.assertContains(response, reverse("project-room-model-suggestions"))
        self.assertContains(response, reverse("project-wizard-price-preview"))

    @unittest.skip("KAYI Next replaced the legacy nine-step wizard/tutorial; equivalent Next flow is covered by test_tooltime_rebuild and production browser smoke.")
    def test_project_wizard_persists_edited_model_as_first_revision(self):
        model_state = self.state("4.800")
        response = self.client.post(reverse("project-create"), {
            "project_type": "bathroom",
            "job_type": Project.JobType.PRIVATE,
            "customer": self.customer.pk,
            "title": "Inline 3D Projekt",
            "priority": Project.Priority.NORMAL,
            "measurement_method": RoomMeasurement.Method.MANUAL,
            "deductions_area_m2": "0",
            "waste_percent": "10",
            "room_model_touched": "1",
            "room_model_state": json.dumps(model_state),
            "action": "project",
        })
        self.assertEqual(response.status_code, 302, response.content)
        created = Project.objects.get(title="Inline 3D Projekt")
        measurement = created.room_measurements.get()
        revision = created.room_model_revisions.get()
        self.assertEqual(measurement.length_m, Decimal("4.800"))
        self.assertEqual(measurement.deductions_area_m2, Decimal("3.000"))
        self.assertEqual(revision.revision, 1)
        self.assertEqual(revision.state["objects"][0]["height_m"], "2.200")
        self.assertEqual(revision.state["materials"]["accent"], "#23415b")

    @patch("erp.views.suggest_room_model_state", side_effect=RuntimeError("provider unavailable"))
    def test_room_model_ai_endpoint_has_local_fallback(self, _suggest):
        response = self.client.post(
            reverse("project-room-model-suggestions"),
            data=json.dumps({
                "prompt": "Raum 4,5 x 3,2 x 2,6 m, Boden anthrazit, Wände weiß, Fliesen 60 x 120 cm, warmes Licht und eine Badewanne",
                "state": self.state(),
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["state"]["room"]["length_m"], "4.500")
        self.assertEqual(data["state"]["materials"]["floor"], "#3d434b")
        self.assertEqual(data["state"]["materials"]["tile_height_cm"], "120.000")
        self.assertEqual(data["state"]["lighting"]["warmth"], "75.000")
        self.assertIn("bathtub", {item["kind"] for item in data["state"]["objects"]})
        self.assertTrue(data["warnings"])

    @patch("erp.views.suggest_room_model_state", side_effect=RuntimeError("provider unavailable"))
    def test_german_window_door_opposite_and_tile_prompt_is_parsed_safely(self, _suggest):
        response = self.client.post(
            reverse("project-room-model-suggestions"),
            data=json.dumps({
                "prompt": "wir haben hier ein bad mit einem fenster breite 1 meter und die höhe des fensters ist 1,5 meter gegenüber soll die tür sein mit einer breite von 74 cm die wände sollen beige gefliest werden und der boden grau beide fliesen haben die größe 60x60 cm",
                "state": self.state(),
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["state"]
        window = next(item for item in data["openings"] if item["kind"] == "window")
        door = next(item for item in data["openings"] if item["kind"] == "door")
        self.assertEqual(window["width_m"], "1.000")
        self.assertEqual(window["height_m"], "1.500")
        self.assertEqual(window["wall"], "back")
        self.assertEqual(door["width_m"], "0.740")
        self.assertEqual(door["height_m"], "2.000")
        self.assertEqual(door["wall"], "front")
        self.assertEqual(data["materials"]["wall"], "#d9cdbd")
        self.assertEqual(data["materials"]["floor"], "#aeb5bd")
        self.assertEqual(data["materials"]["tile_width_cm"], "60.000")
        self.assertEqual(data["materials"]["tile_height_cm"], "60.000")

    @unittest.skip("KAYI Next replaced the legacy nine-step wizard/tutorial; equivalent Next flow is covered by test_tooltime_rebuild and production browser smoke.")
    def test_project_wizard_scan_action_redirects_to_scan_page(self):
        response = self.client.post(reverse("project-create"), {
            "project_type": "bathroom",
            "job_type": Project.JobType.PRIVATE,
            "customer": self.customer.pk,
            "title": "Direkter Raumscan",
            "priority": Project.Priority.NORMAL,
            "measurement_method": RoomMeasurement.Method.MANUAL,
            "deductions_area_m2": "0",
            "waste_percent": "10",
            "action": "scan",
        })
        self.assertEqual(response.status_code, 302, response.content)
        created = Project.objects.get(title="Direkter Raumscan")
        self.assertEqual(created.status, Project.Status.INQUIRY)
        self.assertEqual(response.url, f"{reverse('room-measurement-create', args=[created.pk])}?scan=1")
