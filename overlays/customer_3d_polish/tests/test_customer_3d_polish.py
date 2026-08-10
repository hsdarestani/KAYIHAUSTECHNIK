from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import Customer, Organization, Project, RoomMeasurement, RoomModelRevision, UserProfile
from erp.services.numbering import next_number
from erp.services.room_planner_state import normalize_room_state
from erp.store_views import AI_CONSENT_VERSION


class CustomerAndRoomPlannerPolishTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI Polish Test")
        self.user = User.objects.create_user("polish-admin", password="very-secure-password", email="polish@example.com")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.customer = Customer.objects.create(
            organization=self.org,
            number=next_number(self.org, "customer"),
            company="KAYI Testkunde",
        )
        self.project = Project.objects.create(
            organization=self.org,
            number=next_number(self.org, "project"),
            title="3D KI Test",
            customer=self.customer,
        )
        self.measurement = RoomMeasurement.objects.create(
            organization=self.org,
            project=self.project,
            name="Bad",
            method=RoomMeasurement.Method.MANUAL,
            status=RoomMeasurement.Status.REVIEW,
            length_m=Decimal("4.000"),
            width_m=Decimal("3.000"),
            height_m=Decimal("2.500"),
            created_by=self.user,
        )
        self.client = Client()
        self.client.login(username="polish-admin", password="very-secure-password")

    def state(self):
        return normalize_room_state({
            "schema_version": 3,
            "room": {"length_m": 4, "width_m": 3, "height_m": 2.5, "wall_thickness_m": 0.12},
            "openings": [],
            "objects": [],
            "view": {"mode": "perspective", "grid": True, "snap": True},
        }, self.measurement)

    def grant_ki_consent(self):
        preferences = dict(self.user.profile.preferences or {})
        preferences.update({
            "ai_third_party_consent_at": timezone.now().isoformat(),
            "ai_third_party_consent_version": AI_CONSENT_VERSION,
            "ai_third_party_consent_revoked_at": None,
        })
        self.user.profile.preferences = preferences
        self.user.profile.save(update_fields=["preferences", "updated_at"])

    def test_customer_form_uses_progressive_german_fields(self):
        response = self.client.get(reverse("next-customer-create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Weitere Angaben")
        self.assertContains(response, "Abweichenden Einsatzort hinzufügen")
        self.assertContains(response, "Etage")
        self.assertContains(response, "Hinweise zum Zugang")
        self.assertNotContains(response, ">Floor<")
        self.assertNotContains(response, ">Access notes<")

    def test_room_planner_sets_fresh_csrf_cookie_and_visible_ki_assistant(self):
        response = self.client.get(reverse("next-room-planner", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)
        self.assertContains(response, "KI-Raumassistent")
        self.assertContains(response, "KI-Vorschlag anwenden")
        self.assertContains(response, "data-rp-ai-command")
        self.assertContains(response, "20260810-7")
        self.assertNotContains(response, "AI setzt")

    @patch("erp.room_planner_views.adjust_room_scene")
    def test_ki_command_requires_consent_then_returns_editable_draft_without_revision(self, adjust):
        draft = self.state()
        draft["objects"] = [{
            "id": "wc-ki", "kind": "toilet", "label": "WC", "category": "sanitary",
            "anchor": "wall", "wall": "right", "x_m": "2.790", "z_m": "2.000",
            "elevation_m": "0.000", "width_m": "0.420", "depth_m": "0.720", "height_m": "0.820",
            "rotation_deg": "270.000", "color": "#f6f8f9", "enabled": True, "locked": False,
            "source": "ki_command", "confidence": "0.900", "evidence": "Anweisung des Nutzers",
        }]
        adjust.return_value = {"state": draft, "summary": "WC an die rechte Wand gesetzt.", "warnings": []}
        url = reverse("next-room-planner-ai", args=[self.project.pk])
        payload = json.dumps({"measurement_id": self.measurement.pk, "command": "Stelle das WC an die rechte Wand.", "state": self.state()})

        denied = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(denied.status_code, 428, denied.content)
        self.assertTrue(denied.json()["consent_required"])
        self.assertEqual(denied.json()["settings_url"], "/settings/next/")
        adjust.assert_not_called()

        self.grant_ki_consent()
        before = RoomModelRevision.objects.filter(measurement=self.measurement).count()
        response = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["state"]["objects"][0]["kind"], "toilet")
        self.assertEqual(RoomModelRevision.objects.filter(measurement=self.measurement).count(), before)
        adjust.assert_called_once()

    def test_save_endpoint_passes_real_csrf_enforcement_after_planner_get(self):
        csrf_client = Client(enforce_csrf_checks=True)
        self.assertTrue(csrf_client.login(username="polish-admin", password="very-secure-password"))
        planner = csrf_client.get(reverse("next-room-planner", args=[self.project.pk]))
        self.assertEqual(planner.status_code, 200)
        self.assertIn("csrftoken", planner.cookies)
        token = planner.cookies["csrftoken"].value
        response = csrf_client.post(
            reverse("next-room-planner-save", args=[self.project.pk]),
            data=json.dumps({"measurement_id": self.measurement.pk, "label": "CSRF Save", "state": self.state()}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(RoomModelRevision.objects.filter(measurement=self.measurement).count(), 1)
