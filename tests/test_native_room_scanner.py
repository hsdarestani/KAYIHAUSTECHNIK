import json
import uuid
from decimal import Decimal
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from erp.models import Customer, Employee, NativeRoomScan, Organization, Project, RoomMeasurement, UserProfile
from erp.services.numbering import next_number


class NativeRoomScannerTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory(); self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name); self.override.enable(); self.addCleanup(self.override.disable)
        self.org = Organization.objects.create(name="KAYI Native Scanner")
        self.admin = User.objects.create_user("native-admin", password="very-secure-password")
        self.admin.profile.organization = self.org; self.admin.profile.role = UserProfile.Role.ADMIN; self.admin.profile.save()
        self.customer = Customer.objects.create(organization=self.org, number=next_number(self.org, "customer"), company="Scan Kunde")
        self.project = Project.objects.create(organization=self.org, number=next_number(self.org, "project"), title="LiDAR Bad", customer=self.customer)
        self.other_project = Project.objects.create(organization=self.org, number=next_number(self.org, "project"), title="Fremdes Bad", customer=self.customer)
        self.tech_user = User.objects.create_user("native-tech", password="very-secure-password")
        self.tech_user.profile.organization = self.org; self.tech_user.profile.role = UserProfile.Role.TECHNICIAN; self.tech_user.profile.save()
        self.tech = Employee.objects.create(organization=self.org, user=self.tech_user, employee_number=next_number(self.org, "employee"), first_name="Native", last_name="Monteur")
        self.project.members.add(self.tech)
        self.client = Client(); self.client.login(username="native-admin", password="very-secure-password")
        self.tech_client = Client(); self.tech_client.login(username="native-tech", password="very-secure-password")

    def payload(self, provider="apple_roomplan"):
        return {
            "schema_version": "1.0", "provider": provider, "confidence": 0.87,
            "room": {"name": "Bad EG", "dimensions": {"length_m": 4.2, "width_m": 2.8, "height_m": 2.55}},
            "walls": [{"identifier": "w1", "dimensions": {"width_m": 4.2, "height_m": 2.55}}],
            "doors": [{"dimensions": {"width_m": 0.9, "height_m": 2.0}}],
            "windows": [{"dimensions": {"width_m": 1.2, "height_m": 1.0}}],
            "openings": [], "objects": [], "corners": [], "warnings": [],
        }

    def post_scan(self, client, project, provider="apple_roomplan", scan_id=None, with_model=True):
        data = {"client_scan_id": str(scan_id or uuid.uuid4()), "project_id": project.pk, "provider": provider, "payload": json.dumps(self.payload(provider)), "app_version": "2.2.0", "device_model": "Test Device", "operating_system": "Test OS"}
        if with_model:
            filename = "room.usdz" if provider == "apple_roomplan" else "room.obj"
            mime = "model/vnd.usdz+zip" if provider == "apple_roomplan" else "model/obj"
            data["model_file"] = SimpleUploadedFile(filename, b"native-model", content_type=mime)
        return client.post(reverse("api-native-scans"), data)

    def test_roomplan_scan_creates_review_measurement_and_deductions(self):
        response = self.post_scan(self.tech_client, self.project)
        self.assertEqual(response.status_code, 201, response.content)
        scan = NativeRoomScan.objects.get()
        measurement = scan.measurement
        self.assertEqual(scan.provider, NativeRoomScan.Provider.APPLE_ROOMPLAN)
        self.assertEqual(scan.status, NativeRoomScan.Status.REVIEW)
        self.assertEqual(measurement.method, RoomMeasurement.Method.AR_LIDAR)
        self.assertEqual(measurement.status, RoomMeasurement.Status.REVIEW)
        self.assertEqual(measurement.length_m, Decimal("4.200"))
        self.assertEqual(measurement.deductions_area_m2, Decimal("3.000"))
        self.assertTrue(response.json()["requires_confirmation"])

    def test_android_scan_is_review_only_and_marks_device_dependent_warning(self):
        response = self.post_scan(self.tech_client, self.project, provider="android_arcore_depth")
        self.assertEqual(response.status_code, 201, response.content)
        scan = NativeRoomScan.objects.get()
        self.assertEqual(scan.status, NativeRoomScan.Status.REVIEW)
        self.assertTrue(any("geräteabhängiger" in warning for warning in scan.warnings))
        self.assertEqual(scan.measurement.confidence, Decimal("0.8700"))

    def test_ios_manual_fallback_is_accepted_without_model_and_marked_manual(self):
        payload = self.payload()
        payload.update({
            "capture_mode": "manual_fallback",
            "confidence": 0.50,
            "walls": [],
            "doors": [],
            "windows": [],
            "warnings": ["Manuelles Ersatz-Aufmaß auf einem iOS-Gerät ohne LiDAR."],
        })
        response = self.tech_client.post(reverse("api-native-scans"), {
            "client_scan_id": str(uuid.uuid4()),
            "project_id": self.project.pk,
            "provider": "apple_roomplan",
            "payload": json.dumps(payload),
            "app_version": "2.2.3",
            "device_model": "iPad Air",
            "operating_system": "iPadOS 26.6",
        })
        self.assertEqual(response.status_code, 201, response.content)
        scan = NativeRoomScan.objects.get()
        self.assertFalse(bool(scan.model_file))
        self.assertEqual(scan.normalized_payload["capture_mode"], "manual_fallback")
        self.assertEqual(scan.measurement.method, RoomMeasurement.Method.MANUAL)
        self.assertIn("ohne LiDAR", scan.measurement.ai_summary)

    def test_native_scan_upload_is_idempotent(self):
        scan_id = uuid.uuid4()
        first = self.post_scan(self.tech_client, self.project, scan_id=scan_id, with_model=False)
        second = self.post_scan(self.tech_client, self.project, scan_id=scan_id, with_model=False)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["created"])
        self.assertEqual(NativeRoomScan.objects.count(), 1)
        self.assertEqual(RoomMeasurement.objects.count(), 1)

    def test_technician_cannot_upload_to_unassigned_project(self):
        response = self.post_scan(self.tech_client, self.other_project, with_model=False)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(NativeRoomScan.objects.count(), 0)

    def test_invalid_geometry_and_wrong_roomplan_model_are_rejected(self):
        payload = self.payload(); payload["room"]["dimensions"]["height_m"] = 0.5
        response = self.tech_client.post(reverse("api-native-scans"), {"client_scan_id": str(uuid.uuid4()), "project_id": self.project.pk, "provider": "apple_roomplan", "payload": json.dumps(payload)})
        self.assertEqual(response.status_code, 400)
        wrong = SimpleUploadedFile("room.obj", b"obj", content_type="model/obj")
        response = self.tech_client.post(reverse("api-native-scans"), {"client_scan_id": str(uuid.uuid4()), "project_id": self.project.pk, "provider": "apple_roomplan", "payload": json.dumps(self.payload()), "model_file": wrong})
        self.assertEqual(response.status_code, 400)

    def test_human_confirmation_updates_measurement_and_native_scan(self):
        response = self.post_scan(self.client, self.project, with_model=False)
        scan = NativeRoomScan.objects.get()
        response = self.client.post(reverse("room-measurement-confirm", args=[self.project.pk, scan.measurement_id]))
        self.assertEqual(response.status_code, 302)
        scan.refresh_from_db(); scan.measurement.refresh_from_db()
        self.assertEqual(scan.status, NativeRoomScan.Status.CONFIRMED)
        self.assertEqual(scan.measurement.status, RoomMeasurement.Status.CONFIRMED)
        self.assertEqual(scan.confirmed_by, self.admin)

    def test_mobile_config_advertises_real_native_capabilities_precisely(self):
        response = self.client.get(reverse("api-mobile-config"))
        features = response.json()["features"]
        self.assertTrue(features["native_ar_lidar_capture"])
        self.assertTrue(features["ios_roomplan_requires_lidar"])
        self.assertEqual(features["android_arcore_depth_quality"], "device_dependent_beta")
        self.assertTrue(features["measurement_requires_human_confirmation"])
