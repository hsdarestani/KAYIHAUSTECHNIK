from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 14 APPOINTMENT DETAIL POLISH 2026-08-21"
CSS_REL = "static/css/tooltime-phase14-appointment-detail.css"


def patch_detail(module) -> None:
    rel = "templates/rebuild/appointment_detail.html"
    text = module.read(rel)
    marker = '  {% if project_missing %}\n'
    if "tt-appt-detail-summary" not in text:
        if marker not in text:
            raise RuntimeError("Phase 14 appointment detail body anchor missing")
        summary = r'''  {% if request.user.profile.role != 'technician' and not request.user.profile.is_mobile_worker %}
  <section class="tt-appt-detail-summary" aria-label="Terminübersicht">
    <div class="tt-appt-detail-summary-head">
      <div><span>Terminübersicht</span><strong>Planung &amp; Zuordnung</strong></div>
      <a class="nx-btn" href="{% url 'next-appointment-edit' event.pk %}">Planung bearbeiten</a>
    </div>
    <div class="tt-appt-detail-facts">
      <div><span>Zeit</span><strong>{% if event.all_day %}{{ event.starts_at|date:'d.m.Y' }} · Ganztägig{% else %}{{ event.starts_at|date:'d.m.Y H:i' }} – {{ event.ends_at|date:'H:i' }}{% endif %}</strong></div>
      <div><span>Terminart</span><strong>{{ event.get_type_display }}</strong></div>
      <div><span>Team</span><strong>{% for employee in event.attendees.all %}{{ employee.first_name }} {{ employee.last_name }}{% if not forloop.last %}, {% endif %}{% empty %}Nicht zugewiesen{% endfor %}</strong></div>
      <div><span>Projekt / Kunde</span><strong>{% if event.project %}{{ event.project.number }} · {{ event.project.customer.display_name }}{% else %}Interner Termin{% endif %}</strong></div>
    </div>
    <div class="tt-appt-detail-location">
      <span>⌖</span>
      <div><small>Einsatzort</small><strong>{% if event.location %}{{ event.location }}{% elif event.project.object_location %}{{ event.project.object_location.street }}, {{ event.project.object_location.postal_code }} {{ event.project.object_location.city }}{% elif event.project %}{{ event.project.customer.street }}, {{ event.project.customer.postal_code }} {{ event.project.customer.city }}{% else %}Keine Adresse hinterlegt{% endif %}</strong></div>
    </div>
    {% if event.notes %}<div class="tt-appt-detail-note"><small>Interne Beschreibung</small><p>{{ event.notes|linebreaksbr }}</p></div>{% endif %}
  </section>
  {% endif %}

'''
        text = text.replace(marker, summary + marker, 1)

    css_tag = "<link rel=\"stylesheet\" href=\"{% static 'css/tooltime-phase14-appointment-detail.css' %}?v=20260821-1\">\n"
    if "tooltime-phase14-appointment-detail.css" not in text:
        anchor = "<link rel=\"stylesheet\" href=\"{% static 'css/field-authorization.css' %}?v=20260810-1\">"
        if anchor not in text:
            raise RuntimeError("Phase 14 detail stylesheet anchor missing")
        text = text.replace(anchor, css_tag + anchor, 1)
    module.write(rel, text)


def install_css(module) -> None:
    module.write(CSS_REL, r'''/* A+BAU TOOLTIME PHASE 14 APPOINTMENT DETAIL POLISH 2026-08-21 */
.tt-appt-detail-summary{display:grid;gap:18px;margin:0 0 18px;padding:22px;border:1px solid #e3e8ef;border-radius:18px;background:#fff;box-shadow:0 8px 28px rgba(29,43,64,.045)}
.tt-appt-detail-summary-head{display:flex;align-items:center;justify-content:space-between;gap:18px;padding-bottom:15px;border-bottom:1px solid #eef1f5}.tt-appt-detail-summary-head>div{display:grid;gap:2px}.tt-appt-detail-summary-head span,.tt-appt-detail-facts span,.tt-appt-detail-note small,.tt-appt-detail-location small{font-size:10.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#8993a3}.tt-appt-detail-summary-head strong{font-size:17px;color:#1d2737}.tt-appt-detail-facts{display:grid;grid-template-columns:1.15fr .75fr 1fr 1.25fr;gap:10px}.tt-appt-detail-facts>div{display:grid;gap:5px;min-width:0;padding:14px;border:1px solid #edf0f4;border-radius:12px;background:#fafbfd}.tt-appt-detail-facts strong{overflow-wrap:anywhere;font-size:13px;line-height:1.45;color:#2b3545}.tt-appt-detail-location{display:flex;align-items:center;gap:12px;padding:14px 16px;border-radius:13px;background:#f2f6fc}.tt-appt-detail-location>span{display:grid;place-items:center;flex:0 0 38px;width:38px;height:38px;border-radius:11px;background:#fff;color:#3478df;font-size:20px}.tt-appt-detail-location>div{display:grid;gap:3px;min-width:0}.tt-appt-detail-location strong{overflow-wrap:anywhere;font-size:13px;color:#273244}.tt-appt-detail-note{display:grid;gap:6px;padding:0 2px}.tt-appt-detail-note p{margin:0;color:#596577;font-size:12.5px;line-height:1.6}@media(max-width:1050px){.tt-appt-detail-facts{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.tt-appt-detail-summary{padding:16px;border-radius:15px}.tt-appt-detail-summary-head{align-items:flex-start}.tt-appt-detail-summary-head .nx-btn{min-height:38px;padding-inline:10px;font-size:11px}.tt-appt-detail-facts{grid-template-columns:1fr}.tt-appt-detail-facts>div{padding:12px}.tt-appt-detail-location{align-items:flex-start}}
''')


def install_tests(module) -> None:
    rel = "tests/test_tooltime_phase14_appointment_detail_polish.py"
    test = r'''from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import CalendarEvent, Customer, Employee, Organization, Project

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase14AppointmentDetailPolishTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="A+Bau phase14")
        self.office = User.objects.create_user("phase14-office", password="safe-test-password")
        self.office.profile.organization = self.org
        self.office.profile.role = "office"
        self.office.profile.is_mobile_worker = False
        self.office.profile.save()
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P14-1",
            type="private",
            first_name="Mira",
            last_name="Kunde",
            street="Mainzer Landstraße 14",
            postal_code="60329",
            city="Frankfurt",
        )
        self.project = Project.objects.create(
            organization=self.org,
            number="P-P14-1",
            title="Badmodernisierung",
            customer=self.customer,
            status="planning",
            priority="normal",
        )
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_number="E-P14-1",
            first_name="Max",
            last_name="Monteur",
            active=True,
        )
        start = timezone.now().replace(second=0, microsecond=0) + timedelta(days=1)
        self.event = CalendarEvent.objects.create(
            organization=self.org,
            project=self.project,
            title="Besichtigung Bad",
            type="inspection",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            location="Mainzer Landstraße 14, 60329 Frankfurt",
            notes="Zugang über Innenhof.",
            created_by=self.office,
        )
        self.event.attendees.add(self.employee)
        self.client = Client()
        self.assertTrue(self.client.login(username="phase14-office", password="safe-test-password"))

    def test_office_detail_shows_compact_schedule_summary(self):
        response = self.client.get(reverse("next-appointment-detail", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        for marker in (
            "Terminübersicht",
            "Planung &amp; Zuordnung",
            "Terminart",
            "Besichtigung",
            "Max Monteur",
            "P-P14-1",
            "Mira Kunde",
            "Mainzer Landstraße 14, 60329 Frankfurt",
            "Zugang über Innenhof.",
        ):
            self.assertContains(response, marker)
        self.assertContains(response, reverse("next-appointment-edit", args=[self.event.pk]))

    def test_field_detail_does_not_get_duplicate_office_summary(self):
        technician = User.objects.create_user("phase14-tech", password="safe-test-password")
        technician.profile.organization = self.org
        technician.profile.role = "technician"
        technician.profile.is_mobile_worker = True
        technician.profile.save()
        technician_employee = Employee.objects.create(
            organization=self.org,
            employee_number="E-P14-T",
            first_name="Tina",
            last_name="Technik",
            active=True,
            user=technician,
        )
        self.event.attendees.add(technician_employee)
        client = Client()
        self.assertTrue(client.login(username="phase14-tech", password="safe-test-password"))
        response = client.get(reverse("next-appointment-detail", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Planung &amp; Zuordnung")
        self.assertNotContains(response, "Planung bearbeiten")


class ToolTimePhase14AppointmentDetailPolishContractTests(TestCase):
    def test_detail_summary_is_responsive_and_keeps_field_workflow_markers(self):
        template = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        css = (ROOT / "static/css/tooltime-phase14-appointment-detail.css").read_text(encoding="utf-8")
        for marker in (
            "tt-appt-detail-summary",
            "Terminübersicht",
            "event.get_type_display",
            "event.attendees.all",
            "next-appointment-edit",
            "Auftrag aufnehmen & freigeben",
            "Abschluss & Vorher/Nachher",
        ):
            self.assertIn(marker, template)
        for marker in (".tt-appt-detail-facts", "@media(max-width:650px)", "grid-template-columns:1fr"):
            self.assertIn(marker, css)
'''
    module.write(rel, test)
    compile(test, str(ROOT / rel), "exec")


def run(module) -> None:
    patch_detail(module)
    install_css(module)
    install_tests(module)
    template = module.read("templates/rebuild/appointment_detail.html")
    css = module.read(CSS_REL)
    for marker in (
        "tt-appt-detail-summary",
        "Terminübersicht",
        "event.get_type_display",
        "event.attendees.all",
        "next-appointment-edit",
        "tooltime-phase14-appointment-detail.css",
    ):
        if marker not in template:
            raise RuntimeError(f"Phase 14 detail guard missing: {marker}")
    for marker in (".tt-appt-detail-facts", "@media(max-width:650px)"):
        if marker not in css:
            raise RuntimeError(f"Phase 14 CSS guard missing: {marker}")
    print(f"{MARKER}: office schedule summary polished without changing technician field execution workflow.")