from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
api_path = ROOT / "erp/api.py"
urls_path = ROOT / "config/urls.py"
app_path = ROOT / "native/www/app.js"

app = app_path.read_text(encoding="utf-8")
for marker in (
    "renderAppointmentDetail", "renderAppointmentForm", "saveAppointment",
    "renderWorkReport", "saveWorkReport", "updateTaskStatus", "startTime", "stopTime",
    "/api/mobile/appointments/", "/api/time/start/", "/api/time/stop/",
):
    if marker not in app:
        raise RuntimeError(f"Native Full App phase 3 marker missing: {marker}")

api = api_path.read_text(encoding="utf-8")
if "class MobileAppointmentWorkReportAPIView" not in api:
    anchor = "\n\nclass MobileLoginAPIView(APIView):"
    endpoint = '''

class MobileAppointmentWorkReportAPIView(APIView):
    """Allow an assigned technician to document work without editing dispatch data."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        events = CalendarEvent.objects.filter(
            organization=organization_for(request.user), pk=pk,
        )
        if role_for(request.user) == "technician":
            employee = getattr(request.user, "employee", None)
            events = events.filter(attendees=employee) if employee else events.none()
        event = events.first()
        if not event:
            return Response({"detail": "Termin nicht gefunden oder nicht zugewiesen."}, status=404)
        report = str(request.data.get("work_report", "")).strip()
        if not report:
            return Response({"detail": "Bitte den Arbeitsbericht ausfüllen."}, status=400)
        event.work_report = report[:10000]
        event.save(update_fields=["work_report", "updated_at"])
        return Response(CalendarEventSerializer(event, context={"request": request}).data)
'''
    if anchor not in api:
        raise RuntimeError("Mobile API insertion anchor missing")
    api = api.replace(anchor, endpoint + anchor, 1)
    api_path.write_text(api, encoding="utf-8")

urls = urls_path.read_text(encoding="utf-8")
route = '    path("api/mobile/appointments/<int:pk>/work-report/", api.MobileAppointmentWorkReportAPIView.as_view(), name="api-mobile-appointment-work-report"),\n'
if route not in urls:
    anchor = '    path("api/mobile/config/", api.MobileConfigAPIView.as_view(), name="api-mobile-config"),\n'
    if anchor not in urls:
        raise RuntimeError("Mobile URL insertion anchor missing")
    urls = urls.replace(anchor, anchor + route, 1)
    urls_path.write_text(urls, encoding="utf-8")

(ROOT / "tests/test_native_full_app_phase3.py").write_text('''from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from erp.models import CalendarEvent, Employee, Organization, UserProfile

ROOT = Path(__file__).resolve().parents[1]


class NativeFullAppPhase3ContractTests(TestCase):
    def test_native_flows_have_specific_feedback(self):
        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")
        for marker in (
            "Termin wurde angelegt.", "Termin wurde aktualisiert.",
            "Arbeitsbericht wurde gespeichert.", "Aufgabenstatus wurde aktualisiert.",
            "Arbeitszeit wurde gestartet.", "Arbeitszeit wurde beendet und gespeichert.",
        ):
            self.assertIn(marker, app)

    def test_scanner_contract_remains_available(self):
        app = (ROOT / "native/www/app.js").read_text(encoding="utf-8")
        self.assertIn('// Native navigation contract: data-route="scanner"', app)
        self.assertIn("async function startScan(projectId){clearScannerFeedback();", app)
        self.assertIn("Scanner.uploadScan", app)


class MobileWorkReportPermissionTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau Phase 3")
        self.tech_user = User.objects.create_user("tech-phase3", password="test-pass")
        UserProfile.objects.update_or_create(user=self.tech_user, defaults={"organization": self.org, "role": "technician"})
        self.tech = Employee.objects.create(
            organization=self.org, user=self.tech_user, employee_number="M-P3",
            first_name="Mira", last_name="Montage",
        )
        self.other_user = User.objects.create_user("other-phase3", password="test-pass")
        UserProfile.objects.update_or_create(user=self.other_user, defaults={"organization": self.org, "role": "technician"})
        self.other = Employee.objects.create(
            organization=self.org, user=self.other_user, employee_number="M-P4",
            first_name="Otto", last_name="Andere",
        )
        start = timezone.now()
        self.event = CalendarEvent.objects.create(
            organization=self.org, title="Montage", starts_at=start,
            ends_at=start + timedelta(hours=2), created_by=self.tech_user,
        )
        self.event.attendees.add(self.tech)

    def client_for(self, user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")
        return client

    def test_assigned_technician_can_save_report(self):
        response = self.client_for(self.tech_user).patch(
            reverse("api-mobile-appointment-work-report", args=[self.event.pk]),
            {"work_report": "Armatur montiert und geprüft."}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertEqual(self.event.work_report, "Armatur montiert und geprüft.")

    def test_unassigned_technician_cannot_save_report(self):
        response = self.client_for(self.other_user).patch(
            reverse("api-mobile-appointment-work-report", args=[self.event.pk]),
            {"work_report": "Nicht erlaubt"}, format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_empty_report_is_rejected(self):
        response = self.client_for(self.tech_user).patch(
            reverse("api-mobile-appointment-work-report", args=[self.event.pk]),
            {"work_report": "   "}, format="json",
        )
        self.assertEqual(response.status_code, 400)
''', encoding="utf-8")

print("Installed Native Full App phase 3: appointments, tasks, time tracking and work reports.")
