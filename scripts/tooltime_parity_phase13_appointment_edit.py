from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 13 APPOINTMENT EDIT 2026-08-21"
CSS_REL = "static/css/tooltime-phase13-appointment-edit.css"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 13 appointment-edit anchor missing: {label}")
    return text.replace(old, new, 1)


def patch_backend(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    detail_marker = "\n\n@login_required\ndef appointment_detail(request, pk):\n"
    if "def appointment_edit(request, pk):" not in text:
        pos = text.find(detail_marker)
        if pos < 0:
            raise RuntimeError("Phase 13 appointment_detail boundary missing")
        block = r'''

@login_required
@require_http_methods(["GET", "POST"])
def appointment_edit(request, pk):
    org = _org(request)
    if _is_field_user(request):
        return JsonResponse({"ok": False, "error": "Terminbearbeitung ist nur für Büro/Leitung verfügbar."}, status=403)

    event = get_object_or_404(
        m.CalendarEvent.objects.select_related("project", "project__customer"),
        organization=org,
        pk=pk,
    )
    requested_project_id = request.POST.get("project") if request.method == "POST" else (event.project_id or "")
    requested_customer_id = request.POST.get("customer_filter") if request.method == "POST" else ""

    selected_project = None
    if requested_project_id:
        selected_project = (
            m.Project.objects.filter(organization=org, archived=False, pk=requested_project_id)
            .select_related("customer")
            .first()
        )
    selected_customer = None
    if requested_customer_id:
        selected_customer = m.Customer.objects.filter(
            organization=org, active=True, pk=requested_customer_id
        ).first()
    if selected_customer is None and selected_project is not None and selected_project.customer_id:
        selected_customer = selected_project.customer

    form = AppointmentForm(
        request.POST if request.method == "POST" else None,
        instance=event,
        organization=org,
    )
    if request.method == "POST" and form.is_valid():
        # Update the existing event in place so its primary key, created_by,
        # field-authorization documents and any scheduler references remain intact.
        updated = form.save(commit=False)
        updated.organization = org
        updated.save()
        form.save_m2m()
        messages.success(request, "Termin wurde aktualisiert.")
        return redirect("next-appointment-detail", pk=updated.pk)

    return render(request, "rebuild/appointment_form.html", {
        "form": form,
        "editing": True,
        "event": event,
        "selected_customer_id": str(selected_customer.pk) if selected_customer is not None else "",
        "selected_project_id": str(selected_project.pk) if selected_project is not None else "",
    })
'''
        text = text[:pos] + block + text[pos:]
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_urls(module) -> None:
    rel = "erp/rebuild_urls.py"
    text = module.read(rel)
    route = '    path("appointments/<int:pk>/edit/", views.appointment_edit, name="next-appointment-edit"),\n'
    if route not in text:
        anchor = '    path("appointments/<int:pk>/", field_auth.field_job_detail, name="next-appointment-detail"),\n'
        if anchor not in text:
            anchor = '    path("appointments/<int:pk>/", views.appointment_detail, name="next-appointment-detail"),\n'
        if anchor not in text:
            raise RuntimeError("Phase 13 appointment detail URL anchor missing")
        text = text.replace(anchor, route + anchor, 1)
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_form_template(module) -> None:
    rel = "templates/rebuild/appointment_form.html"
    text = module.read(rel)
    text = _replace_once(
        text,
        "{% block title %}Neuer Termin · A+Bau{% endblock %}",
        "{% block title %}{% if editing %}Termin bearbeiten{% else %}Neuer Termin{% endif %} · A+Bau{% endblock %}",
        "generic appointment title",
    )
    text = _replace_once(
        text,
        '<div class="tt-appt-create" data-appointment-create',
        '<div class="tt-appt-create" data-appointment-create data-appointment-editor="{% if editing %}edit{% else %}create{% endif %}"',
        "appointment editor mode",
    )
    text = _replace_once(
        text,
        '<div><span>Termin erstellen</span><h1>Neuer Termin</h1></div>',
        '<div><span>{% if editing %}Termin bearbeiten{% else %}Termin erstellen{% endif %}</span><h1>{% if editing %}{{ event.title }}{% else %}Neuer Termin{% endif %}</h1></div>',
        "appointment heading mode",
    )
    text = _replace_once(
        text,
        '<a class="nx-btn tt-appt-cancel" href="{% url \'next-appointments\' %}">Abbrechen</a>',
        '<a class="nx-btn tt-appt-cancel" href="{% if editing %}{% url \'next-appointment-detail\' event.pk %}{% else %}{% url \'next-appointments\' %}{% endif %}">Abbrechen</a>',
        "appointment cancel destination",
    )
    text = _replace_once(
        text,
        '<button class="nx-btn nx-btn-primary" type="submit">Speichern</button>',
        '<button class="nx-btn nx-btn-primary" type="submit">{% if editing %}Änderungen speichern{% else %}Speichern{% endif %}</button>',
        "appointment save label",
    )
    module.write(rel, text)


def patch_field_detail(module) -> None:
    views_rel = "erp/field_authorization_views.py"
    views = module.read(views_rel)
    views = _replace_once(
        views,
        '        return render(request, "rebuild/appointment_detail.html", {"event": event, "project_missing": True})',
        '        return render(request, "rebuild/appointment_detail.html", {"event": event, "project_missing": True, "can_edit_appointment": not _is_field_user(request)})',
        "project-missing edit permission",
    )
    pricing = '        "pricing_modes": [("fixed", "Festpreis"), ("estimate", "Kostenschätzung / Budgetfreigabe"), ("hourly", "Nach Aufwand")],\n'
    if '"can_edit_appointment": not _is_field_user(request),' not in views[views.find("def field_job_detail"):]:
        if pricing not in views:
            raise RuntimeError("Phase 13 field detail context anchor missing")
        views = views.replace(pricing, pricing + '        "can_edit_appointment": not _is_field_user(request),\n', 1)
    module.write(views_rel, views)
    compile(views, str(ROOT / views_rel), "exec")

    template_rel = "templates/rebuild/appointment_detail.html"
    template = module.read(template_rel)
    old_actions = '<div class="nx-actions"><a class="nx-btn" href="{% url \'next-field\' %}">← Einsätze</a>{% if event.project %}<a class="nx-btn" href="{% url \'next-project-detail\' event.project.pk %}">Projekt</a>{% endif %}</div>'
    new_actions = '<div class="nx-actions"><a class="nx-btn" href="{% url \'next-field\' %}">← Einsätze</a>{% if event.project %}<a class="nx-btn" href="{% url \'next-project-detail\' event.project.pk %}">Projekt</a>{% endif %}{% if can_edit_appointment %}<a class="nx-btn nx-btn-primary" href="{% url \'next-appointment-edit\' event.pk %}" data-appointment-edit-link>Termin bearbeiten</a>{% endif %}</div>'
    template = _replace_once(template, old_actions, new_actions, "office edit action")

    summary_anchor = '</div></div>\n\n  {% if project_missing %}'
    summary = '''</div></div>

  <section class="tt-appt-detail-summary" data-appointment-detail-summary>
    <div><small>Zeitraum</small><strong>{{ event.starts_at|date:'d.m.Y H:i' }} – {{ event.ends_at|date:'d.m.Y H:i' }}</strong></div>
    <div><small>Terminart</small><strong>{{ event.get_type_display|default:event.type }}</strong></div>
    <div><small>Team</small><strong>{% for attendee in event.attendees.all %}{{ attendee.first_name }} {{ attendee.last_name }}{% if not forloop.last %}, {% endif %}{% empty %}Nicht zugewiesen{% endfor %}</strong></div>
    <div><small>Adresse</small><strong>{% if event.location %}{{ event.location }}{% elif event.project and event.project.object_location %}{{ event.project.object_location.street }}, {{ event.project.object_location.postal_code }} {{ event.project.object_location.city }}{% else %}Keine Adresse{% endif %}</strong></div>
  </section>

  {% if project_missing %}'''
    template = _replace_once(template, summary_anchor, summary, "appointment detail summary")
    css_link = '<link rel="stylesheet" href="{% static \'css/tooltime-phase13-appointment-edit.css\' %}?v=20260821-1">\n'
    if "tooltime-phase13-appointment-edit.css" not in template:
        anchor = '<link rel="stylesheet" href="{% static \'css/field-authorization.css\' %}?v=20260810-1">'
        if anchor not in template:
            raise RuntimeError("Phase 13 field detail CSS anchor missing")
        template = template.replace(anchor, css_link + anchor, 1)
    module.write(template_rel, template)


def install_css(module) -> None:
    module.write(CSS_REL, r'''/* A+BAU TOOLTIME PHASE 13 APPOINTMENT EDIT 2026-08-21 */
.tt-appt-detail-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;margin:0 0 16px;border:1px solid #e1e4e7;border-radius:14px;overflow:hidden;background:#e1e4e7}
.tt-appt-detail-summary>div{display:grid;gap:5px;min-width:0;padding:14px 15px;background:#fff}.tt-appt-detail-summary small{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:#858c93}.tt-appt-detail-summary strong{font-size:12.5px;line-height:1.4;color:#22272b;overflow-wrap:anywhere}
@media(max-width:900px){.tt-appt-detail-summary{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.tt-appt-detail-summary{grid-template-columns:1fr}.fa-head .nx-actions{flex-wrap:wrap}.fa-head [data-appointment-edit-link]{order:-1;width:100%;justify-content:center}}
''')


def install_tests(module) -> None:
    module.write("tests/test_tooltime_phase13_appointment_edit.py", r'''from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import CalendarEvent, Employee, Organization, UserProfile


class ToolTimePhase13AppointmentEditTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI appointment phase13")
        self.admin = User.objects.create_user("appointment-phase13-admin", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.admin,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.employee = Employee.objects.create(
            organization=self.org,
            user=self.admin,
            employee_number="P13-001",
            first_name="Anna",
            last_name="Office",
        )
        self.tech = User.objects.create_user("appointment-phase13-tech", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.tech,
            defaults={"organization": self.org, "role": UserProfile.Role.TECHNICIAN, "is_mobile_worker": True},
        )
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(hours=2)
        self.event = CalendarEvent.objects.create(
            organization=self.org,
            title="Alter Termin",
            type="site",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            location="Altstraße 1, Frankfurt",
            created_by=self.admin,
        )
        self.client = Client()

    def test_office_can_edit_existing_event_in_place(self):
        self.assertTrue(self.client.login(username="appointment-phase13-admin", password="safe-test-password"))
        edit_url = reverse("next-appointment-edit", args=[self.event.pk])
        response = self.client.get(edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-appointment-editor="edit"')
        self.assertContains(response, "Änderungen speichern")

        start = timezone.localtime(self.event.starts_at) + timedelta(days=1)
        end = start + timedelta(hours=2)
        response = self.client.post(edit_url, {
            "title": "Aktualisierter Termin",
            "type": "site",
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": end.strftime("%Y-%m-%dT%H:%M"),
            "location": "Neustraße 2, Frankfurt",
            "notes": "Aktualisierte interne Notiz",
            "project": "",
            "attendees": [str(self.employee.pk)],
        })
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, "Aktualisierter Termin")
        self.assertEqual(self.event.location, "Neustraße 2, Frankfurt")
        self.assertEqual(self.event.created_by, self.admin)
        self.assertTrue(self.event.attendees.filter(pk=self.employee.pk).exists())

    def test_field_user_cannot_open_edit_route(self):
        self.assertTrue(self.client.login(username="appointment-phase13-tech", password="safe-test-password"))
        response = self.client.get(reverse("next-appointment-edit", args=[self.event.pk]))
        self.assertEqual(response.status_code, 403)

    def test_detail_shows_summary_and_office_edit_action(self):
        self.assertTrue(self.client.login(username="appointment-phase13-admin", password="safe-test-password"))
        response = self.client.get(reverse("next-appointment-detail", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-appointment-detail-summary")
        self.assertContains(response, "Termin bearbeiten")
''')

    module.write("tests/test_tooltime_phase13_appointment_edit_contract.py", r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase13AppointmentEditContractTests(SimpleTestCase):
    def test_edit_route_and_existing_event_save_are_installed(self):
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        detail = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        form = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        self.assertIn('name="next-appointment-edit"', urls)
        self.assertIn("def appointment_edit(request, pk):", views)
        self.assertIn("instance=event", views)
        self.assertIn("form.save_m2m()", views)
        self.assertIn("_is_field_user(request)", views)
        self.assertIn("data-appointment-edit-link", detail)
        self.assertIn("data-appointment-detail-summary", detail)
        self.assertIn("data-appointment-editor", form)
''')

    for rel in ("tests/test_tooltime_phase13_appointment_edit.py", "tests/test_tooltime_phase13_appointment_edit_contract.py"):
        compile(module.read(rel), str(ROOT / rel), "exec")


def guard(module) -> None:
    views = module.read("erp/rebuild_views.py")
    urls = module.read("erp/rebuild_urls.py")
    form = module.read("templates/rebuild/appointment_form.html")
    detail = module.read("templates/rebuild/appointment_detail.html")
    field_views = module.read("erp/field_authorization_views.py")
    css = module.read(CSS_REL)
    for marker in ("def appointment_edit(request, pk):", "instance=event", "Termin wurde aktualisiert."):
        if marker not in views:
            raise RuntimeError(f"Phase 13 edit backend marker missing: {marker}")
    if 'name="next-appointment-edit"' not in urls:
        raise RuntimeError("Phase 13 edit route missing")
    for marker in ("data-appointment-editor", "Änderungen speichern"):
        if marker not in form:
            raise RuntimeError(f"Phase 13 editor template marker missing: {marker}")
    for marker in ("data-appointment-edit-link", "data-appointment-detail-summary", "tooltime-phase13-appointment-edit.css"):
        if marker not in detail:
            raise RuntimeError(f"Phase 13 detail marker missing: {marker}")
    if "can_edit_appointment" not in field_views or MARKER not in css:
        raise RuntimeError("Phase 13 permission/visual layer missing")


def run(module) -> None:
    patch_backend(module)
    patch_urls(module)
    patch_form_template(module)
    patch_field_detail(module)
    install_css(module)
    install_tests(module)
    guard(module)
    print(f"{MARKER}: office-only in-place appointment editing and ToolTime-like detail summary installed while technician authorization flow remains intact.")
