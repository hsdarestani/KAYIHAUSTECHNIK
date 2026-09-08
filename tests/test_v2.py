import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from openpyxl import Workbook

from erp.models import CalendarEvent, Organization, PriceItem, PriceSource, Supplier, UserProfile
from erp.services.reference_data import import_price_file


class V2Base(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI V2 Test")
        self.user = User.objects.create_user("v2admin", password="very-secure-password")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.client = Client()
        self.client.login(username="v2admin", password="very-secure-password")


class CalendarAndNavigationTests(V2Base):
    def test_calendar_and_new_business_lists_render(self):
        self.assertEqual(self.client.get(reverse("calendar")).status_code, 200)
        self.assertEqual(self.client.get(reverse("resource-list", args=["suppliers"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("resource-list", args=["payments"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("price-library")).status_code, 200)


class ReferenceDataTests(V2Base):
    def test_xlsx_price_file_is_versioned_and_searchable(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "Leistungskatalog_Kayi_Haustechnik.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["Positionsnummer", "Beschreibung", "Einheit", "Verkaufspreis"])
            sheet.append(["SAN-100", "Montage Waschtisch", "Stk.", 189.50])
            workbook.save(path)
            result = import_price_file(path, self.org)
        self.assertEqual(result["rows"], 1)
        source = PriceSource.objects.get(organization=self.org)
        self.assertTrue(source.raw_file.name)
        item = PriceItem.objects.get(source=source)
        self.assertEqual(item.code, "SAN-100")
        self.assertEqual(str(item.sales_price), "189.50")


class DemoDataTests(TestCase):
    def test_demo_seed_is_separate_and_idempotent(self):
        with TemporaryDirectory() as directory:
            credentials = str(Path(directory) / "demo.txt")
            call_command("seed_demo_data", credentials_file=credentials)
            call_command("seed_demo_data", credentials_file=credentials)
        org = Organization.objects.get(name="A+Bau Demo")
        self.assertTrue(org.settings["is_demo"])
        self.assertEqual(Organization.objects.filter(name="A+Bau Demo").count(), 1)
        self.assertGreaterEqual(CalendarEvent.objects.filter(organization=org).count(), 7)
        self.assertEqual(User.objects.get(username="demo").profile.organization, org)


class MobileApiTests(V2Base):
    def test_mobile_login_config_and_deletion_request(self):
        self.client.logout()
        config = self.client.get(reverse("api-mobile-config"))
        self.assertEqual(config.status_code, 200)
        response = self.client.post(reverse("api-mobile-login"), {"username": "v2admin", "password": "very-secure-password"}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        token = response.json()["token"]
        response = self.client.post(reverse("api-mobile-account-deletion"), HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(response.status_code, 202)
        self.user.profile.refresh_from_db()
        self.assertIn("deletion_requested_at", self.user.profile.preferences)

from decimal import Decimal
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile

from erp.models import Customer, Project, RoomMeasurement
from erp.services.numbering import next_number


class RoomMeasurementUiTests(V2Base):
    def setUp(self):
        super().setUp()
        self.customer = Customer.objects.create(
            organization=self.org,
            number=next_number(self.org, "customer"),
            company="Messkunde GmbH",
            email="messung@example.de",
        )
        self.project = Project.objects.create(
            organization=self.org,
            number=next_number(self.org, "project"),
            title="Bad mit Fotoaufmaß",
            customer=self.customer,
            status=Project.Status.PLANNING,
        )

    def test_measurement_calculations_and_confirmation(self):
        measurement = RoomMeasurement.objects.create(
            organization=self.org,
            project=self.project,
            name="Badezimmer",
            method=RoomMeasurement.Method.AI_PHOTO,
            status=RoomMeasurement.Status.REVIEW,
            length_m=Decimal("4.000"),
            width_m=Decimal("3.000"),
            height_m=Decimal("2.500"),
            deductions_area_m2=Decimal("2.000"),
            waste_percent=Decimal("10.00"),
            created_by=self.user,
        )
        self.assertEqual(measurement.floor_area_m2, Decimal("12.00"))
        self.assertEqual(measurement.perimeter_m, Decimal("14.00"))
        self.assertEqual(measurement.wall_area_m2, Decimal("33.00"))
        self.assertEqual(measurement.floor_with_waste_m2, Decimal("13.20"))
        self.assertEqual(measurement.wall_with_waste_m2, Decimal("36.30"))
        response = self.client.post(reverse("room-measurement-confirm", args=[self.project.pk, measurement.pk]))
        self.assertEqual(response.status_code, 302)
        measurement.refresh_from_db()
        self.assertEqual(measurement.status, RoomMeasurement.Status.CONFIRMED)
        self.assertEqual(measurement.confirmed_by, self.user)
        self.assertIsNotNone(measurement.confirmed_at)

    @unittest.skip("KAYI Next replaced the legacy nine-step wizard/tutorial; equivalent Next flow is covered by test_tooltime_rebuild and production browser smoke.")
    def test_wizard_creates_project_and_review_measurement(self):
        response = self.client.post(reverse("project-create"), {
            "project_type": "bathroom",
            "customer": self.customer.pk,
            "title": "Wizard Badezimmer",
            "priority": Project.Priority.NORMAL,
            "room_name": "Bad OG",
            "measurement_method": RoomMeasurement.Method.AI_PHOTO,
            "length_m": "4.20",
            "width_m": "2.80",
            "height_m": "2.55",
            "deductions_area_m2": "1.90",
            "waste_percent": "10",
            "reference_type": "a4",
            "measurement_confidence": "0.82",
            "measurement_ai_summary": "Skalierter Entwurf",
            "measurement_ai_warnings": '["Bitte Türbreite prüfen"]',
            "measurement_ai_payload": '{"scale_verified": true}',
            "action": "project",
        })
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(title="Wizard Badezimmer")
        measurement = project.room_measurements.get()
        self.assertEqual(measurement.status, RoomMeasurement.Status.REVIEW)
        self.assertEqual(measurement.reference_width_cm, Decimal("21.00"))
        self.assertEqual(measurement.ai_warnings, ["Bitte Türbreite prüfen"])
        self.assertEqual(measurement.confidence, Decimal("0.8200"))

    @patch("erp.api.analyze_room_photos")
    def test_ai_photo_analysis_never_skips_human_confirmation(self, analyze):
        # KAYI_STORE_CONSENT_FOR_test_ai_photo_analysis_never_skips_human_confirmation
        profile = self.user.profile
        prefs = dict(profile.preferences or {})
        prefs.update({"ai_third_party_consent_at": "2026-08-10T00:00:00+00:00", "ai_third_party_consent_version": "2026-08-10", "ai_third_party_consent_revoked_at": None})
        profile.preferences = prefs
        profile.save(update_fields=["preferences", "updated_at"])
        analyze.return_value = {
            "room_type": "Badezimmer",
            "length_m": 4.2,
            "width_m": 2.8,
            "height_m": 2.55,
            "deductions_area_m2": 1.9,
            "confidence": 0.82,
            "scale_verified": True,
            "method": "reference_photo",
            "summary": "A4-Referenz erkannt.",
            "evidence": ["A4-Blatt vollständig sichtbar"],
            "warnings": ["Türbreite prüfen"],
            "missing_captures": [],
            "openings": [],
        }
        image = SimpleUploadedFile("room.jpg", b"\xff\xd8\xff\xe0room", content_type="image/jpeg")
        response = self.client.post(reverse("api-room-measurement-analyze"), {
            "images": image,
            "reference_type": "a4",
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["requires_confirmation"])
        self.assertTrue(payload["scale_verified"])
        self.assertIn("prüfpflichtiger Entwurf", payload["disclaimer"])
        analyze.assert_called_once()

    @unittest.skip("KAYI Next replaced the legacy nine-step wizard/tutorial; equivalent Next flow is covered by test_tooltime_rebuild and production browser smoke.")
    def test_graphical_measurement_and_configurator_pages_render(self):
        measurement = RoomMeasurement.objects.create(
            organization=self.org,
            project=self.project,
            name="Bad",
            length_m=Decimal("4.0"),
            width_m=Decimal("3.0"),
            height_m=Decimal("2.5"),
            created_by=self.user,
        )
        response = self.client.get(reverse("room-measurement-edit", args=[self.project.pk, measurement.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "KAYI AI Fotoaufmaß")
        response = self.client.get(reverse("configurator"), {"project": self.project.pk, "measurement": measurement.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "3D-Konfigurator")
        response = self.client.get(reverse("project-create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "9-Schritte-Projektassistent")

    def test_mobile_config_describes_measurement_capabilities_precisely(self):
        self.client.logout()
        response = self.client.get(reverse("api-mobile-config"))
        features = response.json()["features"]
        self.assertTrue(features["ai_photo_measurement"])
        self.assertTrue(features["measurement_requires_human_confirmation"])
        self.assertTrue(features["native_ar_lidar_capture"])
        self.assertTrue(features["ios_roomplan_capture"])
        self.assertTrue(features["android_arcore_depth_capture"])
        self.assertTrue(features["measurement_requires_human_confirmation"])
