from __future__ import annotations

import base64
import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import resolve, reverse

from erp.models import Customer, Employee, MeasurementCapture, Organization, Project, RoomMeasurement, RoomModelRevision, UserProfile
from erp.services.numbering import next_number
from erp.services.room_planner_state import ALLOWED_KINDS, merge_vision_result, normalize_room_state


class RoomPlannerProTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="kayi-room-planner-tests-")
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.org = Organization.objects.create(name="KAYI Room Planner Pro")
        self.user = User.objects.create_user("room-admin", password="very-secure-password", email="admin@example.com")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.customer = Customer.objects.create(organization=self.org, number=next_number(self.org, "customer"), company="3D Profi Kunde")
        self.project = Project.objects.create(organization=self.org, number=next_number(self.org, "project"), title="Professionelle Raumplanung", customer=self.customer)
        self.measurement = RoomMeasurement.objects.create(
            organization=self.org, project=self.project, name="Bad EG", method=RoomMeasurement.Method.AR_LIDAR,
            status=RoomMeasurement.Status.CONFIRMED, length_m=Decimal("4.000"), width_m=Decimal("3.000"), height_m=Decimal("2.600"), confirmed_by=self.user,
        )
        self.client = Client()
        self.client.login(username="room-admin", password="very-secure-password")

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def state(self):
        return {
            "schema_version": 3,
            "room": {"length_m": "4.000", "width_m": "3.000", "height_m": "2.600", "wall_thickness_m": "0.140"},
            "openings": [
                {"id": "door-1", "kind": "door", "wall": "back", "width_m": "0.900", "height_m": "2.050", "offset_m": "0.450", "sill_height_m": "0"},
                {"id": "window-1", "kind": "window", "wall": "right", "width_m": "1.100", "height_m": "1.000", "offset_m": "1.100", "sill_height_m": "0.900"},
            ],
            "objects": [
                {"id": "washer-1", "kind": "washing_machine", "label": "Waschmaschine", "anchor": "floor", "x_m": "2.300", "z_m": "2.900", "elevation_m": "0", "width_m": "0.600", "depth_m": "0.620", "height_m": "0.860", "rotation_deg": "0", "color": "#eef2f4", "enabled": True},
                {"id": "rad-1", "kind": "radiator", "label": "Heizkörper", "anchor": "wall", "wall": "left", "x_m": "0.060", "z_m": "1.300", "elevation_m": "0.150", "width_m": "0.900", "depth_m": "0.120", "height_m": "0.750", "rotation_deg": "0", "color": "#e8ecef", "enabled": True},
            ],
            "view": {"mode": "perspective", "show_ceiling": False, "transparent_near_walls": True, "grid": True, "snap": True},
            "calibration": {"scale_verified": True, "method": "ar_lidar", "confidence": "0.980", "warnings": []},
        }

    def test_project_scoped_routes_and_webgl_assets_are_primary(self):
        planner_url = reverse("next-room-planner", args=[self.project.pk])
        self.assertEqual(resolve(planner_url).url_name, "next-room-planner")
        response = self.client.get(planner_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Raumplanung 3D")
        self.assertContains(response, "three@0.170.0")
        self.assertContains(response, "vollständigen Raum")
        self.assertContains(response, "data-rp-drag-metrics")
        project = Path(__file__).resolve().parents[1] / "templates/rebuild/project_detail.html"
        appointment = Path(__file__).resolve().parents[1] / "templates/rebuild/appointment_detail.html"
        self.assertIn("next-room-planner", project.read_text(encoding="utf-8"))
        self.assertIn("next-room-planner", appointment.read_text(encoding="utf-8"))

    def test_v3_state_supports_full_object_library_and_full_height_openings(self):
        raw = self.state()
        raw["objects"] = []
        for idx, kind in enumerate(sorted(ALLOWED_KINDS)):
            raw["objects"].append({"id": f"o-{idx}", "kind": kind, "x_m": "1.5", "z_m": "2", "width_m": "0.5", "depth_m": "0.4", "height_m": "0.8"})
        raw["openings"][1]["sill_height_m"] = "2.300"
        raw["openings"][1]["height_m"] = "1.500"
        normalized = normalize_room_state(raw, self.measurement)
        self.assertEqual(normalized["schema_version"], 3)
        self.assertEqual(normalized["room"]["wall_thickness_m"], "0.140")
        self.assertEqual({item["kind"] for item in normalized["objects"]}, ALLOWED_KINDS)
        window = next(item for item in normalized["openings"] if item["id"] == "window-1")
        self.assertEqual(window["sill_height_m"], "2.300")
        self.assertEqual(window["height_m"], "0.300")

    def test_opening_width_is_clamped_to_real_wall_length(self):
        raw = self.state()
        raw["openings"] = [{"id": "too-wide", "kind": "door", "wall": "back", "width_m": "9", "height_m": "2", "offset_m": "4", "sill_height_m": "0"}]
        normalized = normalize_room_state(raw, self.measurement)
        self.assertEqual(normalized["openings"][0]["width_m"], "3.000")
        self.assertEqual(normalized["openings"][0]["offset_m"], "0.000")

    def test_saving_scene_versions_model_and_reopens_geometry_for_review(self):
        response = self.client.post(
            reverse("next-room-planner-save", args=[self.project.pk]),
            data=json.dumps({"measurement_id": self.measurement.pk, "label": "Waschmaschine versetzt", "state": self.state()}), content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        payload = response.json()
        self.assertEqual(payload["revision"], 1)
        revision = RoomModelRevision.objects.get(measurement=self.measurement)
        self.assertEqual(revision.label, "Waschmaschine versetzt")
        self.assertEqual(revision.state["schema_version"], 3)
        self.assertEqual(revision.state["objects"][0]["kind"], "washing_machine")
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.deductions_area_m2, Decimal("2.945"))
        self.assertEqual(self.measurement.status, RoomMeasurement.Status.REVIEW)
        self.assertIsNone(self.measurement.confirmed_by)

    def test_revision_query_opens_exact_historical_scene(self):
        first = self.state(); first["objects"][0]["label"] = "Version Eins"
        second = self.state(); second["objects"][0]["label"] = "Version Zwei"
        rev1 = RoomModelRevision.objects.create(organization=self.org, project=self.project, measurement=self.measurement, revision=1, label="v1", state=normalize_room_state(first, self.measurement), created_by=self.user)
        RoomModelRevision.objects.create(organization=self.org, project=self.project, measurement=self.measurement, revision=2, label="v2", state=normalize_room_state(second, self.measurement), created_by=self.user)
        response = self.client.get(reverse("next-room-planner", args=[self.project.pk]), {"measurement": self.measurement.pk, "revision": rev1.pk})
        self.assertContains(response, "Version Eins")
        self.assertNotContains(response, "Version Zwei")

    def test_ai_merge_preserves_manual_objects_and_maps_relative_coordinates(self):
        current = normalize_room_state(self.state(), self.measurement)
        current["objects"][0]["source"] = "manual"
        current["objects"][1]["source"] = "ai_photo"
        vision = {
            "scale_verified": False, "method": "visual_only", "confidence": 0.78, "warnings": ["Maße prüfen"],
            "room": {"length_m": None, "width_m": None, "height_m": None},
            "openings": [{"id": "ai-window", "kind": "window", "wall": "back", "offset_ratio": 0.2, "width_ratio": 0.3, "offset_m": None, "width_m": None, "height_m": None, "sill_m": None, "confidence": 0.8, "evidence": "Fenster sichtbar"}],
            "objects": [{"id": "ai-fridge", "kind": "fridge", "label": "Kühlschrank", "anchor": "floor", "wall": None, "x_ratio": 0.5, "z_ratio": 0.25, "x_m": None, "z_m": None, "elevation_m": None, "width_m": None, "depth_m": None, "height_m": None, "rotation_deg": 0, "confidence": 0.82, "evidence": "Front und Seite sichtbar"}],
        }
        merged = normalize_room_state(merge_vision_result(current, vision), self.measurement)
        ids = {item["id"] for item in merged["objects"]}
        self.assertIn("washer-1", ids)
        self.assertNotIn("rad-1", ids, "old AI-generated objects should be refreshed, not duplicated")
        fridge = next(item for item in merged["objects"] if item["id"] == "ai-fridge")
        self.assertEqual(fridge["x_m"], "1.500")
        self.assertEqual(fridge["z_m"], "1.000")
        window = next(item for item in merged["openings"] if item["id"] == "ai-window")
        self.assertEqual(window["width_m"], "0.900")
        self.assertEqual(window["offset_m"], "0.600")

    @patch("erp.room_planner_views.analyze_room_scene")
    def test_photo_vision_persists_editable_scene_revision_and_capture(self, analyze):
        analyze.return_value = {
            "room_type": "Bad", "room": {"length_m": 4.0, "width_m": 3.0, "height_m": 2.6}, "scale_verified": True,
            "method": "reference_photo", "confidence": 0.91, "summary": "Bad mit Fenster, Heizkörper und Waschmaschine erkannt.",
            "warnings": ["Verdeckte Ecke prüfen"], "missing_captures": [],
            "openings": [{"id": "win-ai", "kind": "window", "wall": "back", "offset_ratio": 0.2, "width_ratio": 0.3, "offset_m": 0.6, "width_m": 0.9, "height_m": 1.0, "sill_m": 0.9, "confidence": 0.93, "evidence": "Fenster vollständig sichtbar"}],
            "objects": [{"id": "wm-ai", "kind": "washing_machine", "label": "Waschmaschine", "anchor": "floor", "wall": None, "x_ratio": 0.75, "z_ratio": 0.8, "x_m": 2.25, "z_m": 3.2, "elevation_m": 0, "width_m": 0.6, "depth_m": 0.62, "height_m": 0.86, "rotation_deg": 0, "confidence": 0.9, "evidence": "Gerätefront sichtbar"}],
        }
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6n4sAAAAASUVORK5CYII=")
        image = SimpleUploadedFile("room.png", png, content_type="image/png")
        response = self.client.post(
            reverse("next-room-planner-vision", args=[self.project.pk]),
            data={"measurement_id": self.measurement.pk, "state": json.dumps(self.state()), "reference_type": "a4", "images": image},
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertTrue(data["scale_verified"])
        self.assertGreaterEqual(data["recognized_objects"], 1)
        self.assertEqual(MeasurementCapture.objects.filter(measurement=self.measurement).count(), 1)
        self.assertEqual(RoomModelRevision.objects.filter(measurement=self.measurement, label="AI-Fotoerkennung").count(), 1)
        self.measurement.refresh_from_db()
        self.assertEqual(self.measurement.reference_type, "a4")
        self.assertEqual(self.measurement.reference_width_cm, Decimal("21.00"))
        self.assertEqual(self.measurement.ai_payload["planner_state"]["schema_version"], 3)

    def test_technician_only_sees_assigned_project_planner(self):
        tech_user = User.objects.create_user("room-tech", password="very-secure-password", email="tech@example.com")
        tech_user.profile.organization = self.org
        tech_user.profile.role = UserProfile.Role.TECHNICIAN
        tech_user.profile.save()
        tech = Employee.objects.create(organization=self.org, user=tech_user, employee_number="MON-3D-1", first_name="Mona", last_name="Montage", email=tech_user.email)
        self.client.logout(); self.client.login(username="room-tech", password="very-secure-password")
        url = reverse("next-room-planner", args=[self.project.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.project.members.add(tech)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Raumplanung 3D")
