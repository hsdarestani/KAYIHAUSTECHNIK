from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 13 APPOINTMENT DETAIL EDIT 2026-08-21"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 13 appointment anchor missing: {label}")
    return text.replace(old, new, 1)


def patch_backend(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    if "def appointment_edit(request, pk):" not in text:
        marker = '\n\n@login_required\ndef appointment_detail(request, pk):\n'
        if marker not in text:
            raise RuntimeError("Phase 13 appointment_detail boundary missing")
        block = r'''

@login_required
@require_http_methods(["GET", "POST"])
def appointment_edit(request, pk):
    org = _org(request)
    event = get_object_or_404(
        m.CalendarEvent.objects.filter(organization=org)
        .select_related("project", "project__customer", "project__object_location")
        .prefetch_related("attendees"),
        pk=pk,
    )
    if _is_field_user(request):
        messages.warning(request, "Die Terminplanung kann nur im Büro bearbeitet werden.")
        return redirect("next-appointment-detail", pk=event.pk)

    requested_project_id = (
        request.POST.get("project") if request.method == "POST" else event.project_id
    )
    requested_customer_id = (
        request.POST.get("customer_filter") if request.method == "POST" else None
    )

    selected_project = None
    if requested_project_id:
        selected_project = (
            m.Project.objects.filter(
                organization=org,
                archived=False,
                pk=requested_project_id,
            )
            .select_related("customer", "object_location")
            .first()
        )

    selected_customer = None
    if requested_customer_id:
        selected_customer = m.Customer.objects.filter(
            organization=org,
            active=True,
            pk=requested_customer_id,
        ).first()
    if selected_customer is None and selected_project is not None and selected_project.customer_id:
        selected_customer = selected_project.customer

    form = AppointmentForm(
        request.POST if request.method == "POST" else None,
        instance=event,
        organization=org,
    )
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.organization = org
        # Editing must never rewrite the original author merely because another
        # office user adjusts timing/team later.
        updated.created_by = event.created_by or request.user
        updated.save()
        form.save_m2m()
        messages.success(request, "Termin wurde aktualisiert.")
        return redirect("next-appointment-detail", pk=updated.pk)

    return render(request, "rebuild/appointment_form.html", {
        "form": form,
        "mode": "edit",
        "event": event,
        "selected_customer_id": str(selected_customer.pk) if selected_customer is not None else "",
        "selected_project_id": str(selected_project.pk) if selected_project is not None else "",
    })
'''
        text = text.replace(marker, block + marker, 1)
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_urls(module) -> None:
    rel = "erp/rebuild_urls.py"
    text = module.read(rel)
    anchor = '    path("appointments/<int:pk>/", field_auth.field_job_detail, name="next-appointment-detail"),\n'
    if anchor not in text:
        # Keep compatibility when this layer is ever assembled without the field
        # authorization route replacement.
        anchor = '    path("appointments/<int:pk>/", views.appointment_detail, name="next-appointment-detail"),\n'
    addition = '    path("appointments/<int:pk>/edit/", views.appointment_edit, name="next-appointment-edit"),\n'
    if addition not in text:
        if anchor not in text:
            raise RuntimeError("Phase 13 appointment detail URL anchor missing")
        text = text.replace(anchor, addition + anchor, 1)
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_field_detail_context(module) -> None:
    rel = "erp/field_authorization_views.py"
    text = module.read(rel)
    missing_old = '        return render(request, "rebuild/appointment_detail.html", {"event": event, "project_missing": True})'
    missing_new = '        return render(request, "rebuild/appointment_detail.html", {"event": event, "project_missing": True, "can_edit_schedule": not _is_field_user(request)})'
    text = _replace_once(text, missing_old, missing_new, "project-missing detail edit permission")

    context_anchor = '        "pricing_modes": [("fixed", "Festpreis"), ("estimate", "Kostenschätzung / Budgetfreigabe"), ("hourly", "Nach Aufwand")],\n'
    context_new = context_anchor + '        "can_edit_schedule": not _is_field_user(request),\n'
    text = _replace_once(text, context_anchor, context_new, "detail edit permission context")
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_form_template(module) -> None:
    rel = "templates/rebuild/appointment_form.html"
    text = module.read(rel)
    text = _replace_once(
        text,
        "{% block title %}Neuer Termin · A+Bau{% endblock %}",
        "{% block title %}{% if mode == 'edit' %}Termin bearbeiten{% else %}Neuer Termin{% endif %} · A+Bau{% endblock %}",
        "mode-aware page title",
    )
    text = _replace_once(
        text,
        '<div class="tt-appt-create" data-appointment-create\n',
        '<div class="tt-appt-create" data-appointment-create data-appointment-mode="{{ mode|default:\'create\' }}"\n',
        "mode data attribute",
    )
    text = _replace_once(
        text,
        '<a class="tt-appt-back" href="{% url \'next-appointments\' %}" aria-label="Zurück">←</a>',
        '<a class="tt-appt-back" href="{% if mode == \'edit\' %}{% url \'next-appointment-detail\' event.pk %}{% else %}{% url \'next-appointments\' %}{% endif %}" aria-label="Zurück">←</a>',
        "mode-aware back action",
    )
    text = _replace_once(
        text,
        '<div><span>Termin erstellen</span><h1>Neuer Termin</h1></div>',
        '<div><span>{% if mode == \'edit\' %}Terminplanung{% else %}Termin erstellen{% endif %}</span><h1>{% if mode == \'edit\' %}Termin bearbeiten{% else %}Neuer Termin{% endif %}</h1></div>',
        "mode-aware heading",
    )
    text = _replace_once(
        text,
        '<a class="nx-btn tt-appt-cancel" href="{% url \'next-appointments\' %}">Abbrechen</a>',
        '<a class="nx-btn tt-appt-cancel" href="{% if mode == \'edit\' %}{% url \'next-appointment-detail\' event.pk %}{% else %}{% url \'next-appointments\' %}{% endif %}">Abbrechen</a>',
        "mode-aware cancel action",
    )
    old_note = '<section class="tt-appt-side-note"><strong>Planung auf einer Seite</strong><p>Kein Assistent: Kunde/Projekt, Zeit, Team und interne Beschreibung werden direkt erfasst.</p></section>'
    new_note = '''<section class="tt-appt-side-note"><strong>{% if mode == 'edit' %}Planung aktualisieren{% else %}Planung auf einer Seite{% endif %}</strong><p>{% if mode == 'edit' %}Zeit, Projektbezug, Team und interne Beschreibung können hier angepasst werden. Einsatzfreigabe, Arbeitsbericht und Bilder bleiben im Termin dokumentiert.{% else %}Kein Assistent: Kunde/Projekt, Zeit, Team und interne Beschreibung werden direkt erfasst.{% endif %}</p>{% if mode == 'edit' %}<a class="nx-btn" href="{% url 'next-appointment-detail' event.pk %}">Einsatzdokumentation öffnen →</a>{% endif %}</section>'''
    text = _replace_once(text, old_note, new_note, "edit-side documentation link")
    module.write(rel, text)


def patch_detail_template(module) -> None:
    rel = "templates/rebuild/appointment_detail.html"
    text = module.read(rel)
    anchor = '''{% if event.project %}<a class="nx-btn" href="{% url 'next-project-detail' event.project.pk %}">Projekt</a>{% endif %}</div></div>'''
    replacement = '''{% if event.project %}<a class="nx-btn" href="{% url 'next-project-detail' event.project.pk %}">Projekt</a>{% endif %}{% if can_edit_schedule %}<a class="nx-btn nx-btn-primary" href="{% url 'next-appointment-edit' event.pk %}">Termin bearbeiten</a>{% endif %}</div></div>'''
    text = _replace_once(text, anchor, replacement, "appointment detail edit CTA")
    module.write(rel, text)


def install_tests(module) -> None:
    rel = "tests/test_tooltime_phase13_appointment_edit.py"
    test = r'''from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from erp.models import CalendarEvent, Customer, Employee, Organization, Project, UserProfile

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase13AppointmentEditTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI phase13 office")
        self.other_org = Organization.objects.create(name="KAYI phase13 other")
        self.office = User.objects.create_user("phase13-office", password="safe-test-password")
        self.office.profile.organization = self.org
        self.office.profile.role = "office"
        self.office.profile.is_mobile_worker = False
        self.office.profile.save()
        self.client = Client()
        self.assertTrue(self.client.login(username="phase13-office", password="safe-test-password"))

        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P13-1",
            type="private",
            first_name="Ada",
            last_name="Termin",
            street="Testweg 13",
            postal_code="60313",
            city="Frankfurt",
        )
        self.project = Project.objects.create(
            organization=self.org,
            number="P-P13-1",
            title="Phase 13 Projekt",
            customer=self.customer,
            status="planning",
            priority="normal",
        )
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_number="E-P13-1",
            first_name="Office",
            last_name="Team",
            active=True,
        )
        start = timezone.now().replace(second=0, microsecond=0) + timedelta(hours=2)
        self.event = CalendarEvent.objects.create(
            organization=self.org,
            project=self.project,
            title="Alter Termin",
            type="appointment",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            location="Testweg 13, 60313 Frankfurt",
            notes="Alt",
            created_by=self.office,
        )

    def _post_data(self, **overrides):
        start = timezone.localtime(self.event.starts_at) + timedelta(hours=1)
        end = timezone.localtime(self.event.ends_at) + timedelta(hours=1)
        data = {
            "title": "Aktualisierter Termin",
            "type": "site",
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": end.strftime("%Y-%m-%dT%H:%M"),
            "location": "Neue Adresse 13",
            "notes": "Neu geplant",
            "project": str(self.project.pk),
            "customer_filter": str(self.customer.pk),
            "attendees": [str(self.employee.pk)],
        }
        data.update(overrides)
        return data

    def test_edit_route_is_primary_rebuild_route(self):
        path = reverse("next-appointment-edit", args=[self.event.pk])
        self.assertEqual(path, f"/appointments/{self.event.pk}/edit/")
        self.assertEqual(resolve(path).url_name, "next-appointment-edit")

    def test_office_get_reuses_tooltime_form_with_existing_selection(self):
        response = self.client.get(reverse("next-appointment-edit", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Termin bearbeiten")
        self.assertContains(response, 'data-appointment-mode="edit"')
        self.assertContains(response, f'data-initial-project="{self.project.pk}"')
        self.assertContains(response, f'data-initial-customer="{self.customer.pk}"')
        self.assertContains(response, "Alter Termin")
        self.assertContains(response, "Einsatzdokumentation öffnen")

    def test_office_post_updates_real_event_and_team_without_rewriting_author(self):
        response = self.client.post(
            reverse("next-appointment-edit", args=[self.event.pk]),
            self._post_data(),
        )
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, "Aktualisierter Termin")
        self.assertEqual(self.event.type, "site")
        self.assertEqual(self.event.location, "Neue Adresse 13")
        self.assertEqual(self.event.notes, "Neu geplant")
        self.assertEqual(self.event.created_by, self.office)
        self.assertEqual(list(self.event.attendees.values_list("pk", flat=True)), [self.employee.pk])

    def test_cross_organization_event_cannot_be_edited(self):
        other_customer = Customer.objects.create(
            organization=self.other_org,
            number="K-P13-X",
            type="private",
            first_name="Andere",
            last_name="Firma",
        )
        other_project = Project.objects.create(
            organization=self.other_org,
            number="P-P13-X",
            title="Fremdprojekt",
            customer=other_customer,
            status="planning",
            priority="normal",
        )
        foreign = CalendarEvent.objects.create(
            organization=self.other_org,
            project=other_project,
            title="Fremder Termin",
            starts_at=timezone.now(),
            ends_at=timezone.now() + timedelta(hours=1),
        )
        response = self.client.get(reverse("next-appointment-edit", args=[foreign.pk]))
        self.assertEqual(response.status_code, 404)

    def test_field_user_is_redirected_to_operational_detail_instead_of_scheduler_edit(self):
        technician = User.objects.create_user("phase13-tech", password="safe-test-password")
        technician.profile.organization = self.org
        technician.profile.role = "technician"
        technician.profile.is_mobile_worker = True
        technician.profile.save()
        technician_employee = Employee.objects.create(
            organization=self.org,
            employee_number="E-P13-T",
            first_name="Field",
            last_name="Tech",
            active=True,
            user=technician,
        )
        self.event.attendees.add(technician_employee)
        tech_client = Client()
        self.assertTrue(tech_client.login(username="phase13-tech", password="safe-test-password"))
        response = tech_client.get(reverse("next-appointment-edit", args=[self.event.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("next-appointment-detail", args=[self.event.pk]))

    def test_detail_exposes_edit_action_to_office_only(self):
        response = self.client.get(reverse("next-appointment-detail", args=[self.event.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Termin bearbeiten")
        self.assertContains(response, reverse("next-appointment-edit", args=[self.event.pk]))


class ToolTimePhase13AppointmentEditContractTests(TestCase):
    def test_templates_and_backend_keep_field_documentation_separate_from_scheduler_edit(self):
        form = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        detail = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        for marker in (
            "data-appointment-mode",
            "Termin bearbeiten",
            "Einsatzdokumentation öffnen",
        ):
            self.assertIn(marker, form)
        self.assertIn("can_edit_schedule", detail)
        self.assertIn("def appointment_edit(request, pk):", views)
        self.assertIn("updated.created_by = event.created_by or request.user", views)
        self.assertIn("next-appointment-edit", urls)
'''
    module.write(rel, test)
    compile(test, str(ROOT / rel), "exec")


def run(module) -> None:
    patch_backend(module)
    patch_urls(module)
    patch_field_detail_context(module)
    patch_form_template(module)
    patch_detail_template(module)
    install_tests(module)

    views = module.read("erp/rebuild_views.py")
    urls = module.read("erp/rebuild_urls.py")
    form = module.read("templates/rebuild/appointment_form.html")
    detail = module.read("templates/rebuild/appointment_detail.html")
    field_views = module.read("erp/field_authorization_views.py")
    for marker in (
        "def appointment_edit(request, pk):",
        'organization=org,\n                archived=False,\n                pk=requested_project_id',
        "updated.created_by = event.created_by or request.user",
        '"mode": "edit"',
    ):
        if marker not in views:
            raise RuntimeError(f"Phase 13 backend guard missing: {marker}")
    for marker in ("next-appointment-edit", 'appointments/<int:pk>/edit/'):
        if marker not in urls:
            raise RuntimeError(f"Phase 13 URL guard missing: {marker}")
    for marker in ("data-appointment-mode", "Termin bearbeiten", "Einsatzdokumentation öffnen"):
        if marker not in form:
            raise RuntimeError(f"Phase 13 form guard missing: {marker}")
    for marker in ("can_edit_schedule", "next-appointment-edit", "Termin bearbeiten"):
        if marker not in detail:
            raise RuntimeError(f"Phase 13 detail guard missing: {marker}")
    if field_views.count('"can_edit_schedule": not _is_field_user(request)') < 2:
        raise RuntimeError("Phase 13 field detail permission context is incomplete")

    print(f"{MARKER}: office-only scheduler edit, real CalendarEvent/team persistence and operational-detail handoff installed.")
