from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 10 CI CLOSEOUT 2026-08-20"


def _patch_backend(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    start_marker = '@login_required\n@require_http_methods(["GET", "POST"])\ndef appointment_create(request):\n'
    end_marker = '\n\n@login_required\ndef appointment_detail(request, pk):\n'
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError("Phase 10 CI closeout appointment_create anchors missing")

    block = text[start:end]
    old_setup = '''    if request.GET.get("project"):
        initial["project"] = request.GET.get("project")
    form = AppointmentForm(request.POST or None, organization=org, initial=initial)
'''
    new_setup = '''    requested_project_id = (
        request.POST.get("project") if request.method == "POST" else request.GET.get("project")
    )
    requested_customer_id = (
        request.POST.get("customer_filter") if request.method == "POST" else request.GET.get("customer")
    )

    # Resolve all preselection values through organization-scoped querysets.
    # Customer is presentation-only on CalendarEvent; project remains the
    # persistent relationship and its ModelChoiceField is organization-scoped.
    selected_project = None
    if requested_project_id:
        selected_project = m.Project.objects.filter(
            organization=org, archived=False, pk=requested_project_id
        ).select_related("customer").first()
        if selected_project is not None:
            initial["project"] = selected_project.pk

    selected_customer = None
    if requested_customer_id:
        selected_customer = m.Customer.objects.filter(
            organization=org, active=True, pk=requested_customer_id
        ).first()
    if selected_customer is None and selected_project is not None and selected_project.customer_id:
        selected_customer = selected_project.customer

    selected_customer_id = str(selected_customer.pk) if selected_customer is not None else ""
    selected_project_id = str(selected_project.pk) if selected_project is not None else ""
    form = AppointmentForm(
        request.POST if request.method == "POST" else None,
        organization=org,
        initial=initial,
    )
'''
    if new_setup not in block:
        if old_setup not in block:
            raise RuntimeError("Phase 10 CI closeout appointment setup anchor missing")
        block = block.replace(old_setup, new_setup, 1)

    old_render = '    return render(request, "rebuild/appointment_form.html", {"form": form})'
    new_render = '''    return render(request, "rebuild/appointment_form.html", {
        "form": form,
        "selected_customer_id": selected_customer_id,
        "selected_project_id": selected_project_id,
    })'''
    if new_render not in block:
        if old_render not in block:
            raise RuntimeError("Phase 10 CI closeout appointment render anchor missing")
        block = block.replace(old_render, new_render, 1)

    text = text[:start] + block + text[end:]
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def _patch_template(module) -> None:
    rel = "templates/rebuild/appointment_form.html"
    text = module.read(rel)

    unsafe = '''data-initial-customer="{{ request.POST.customer_filter|default:request.GET.customer|default:'' }}"
     data-initial-project="{{ form.project.value|default:'' }}"'''
    safe = '''data-initial-customer="{{ selected_customer_id|default:'' }}"
     data-initial-project="{{ selected_project_id|default:'' }}"'''
    if safe not in text:
        if unsafe not in text:
            raise RuntimeError("Phase 10 CI closeout safe preselection anchor missing")
        text = text.replace(unsafe, safe, 1)

    old = '<section class="tt-appt-card tt-appt-after-save">'
    new = '<section class="tt-appt-card tt-appt-after-save" data-after-save aria-label="Nach dem Speichern">'
    if "Nach dem Speichern" not in text:
        if old not in text:
            raise RuntimeError("Phase 10 CI closeout after-save anchor missing")
        text = text.replace(old, new, 1)

    # Keep the German-only browser/UI contract: "Wizard" is an English label.
    text = text.replace("Kein Wizard:", "Kein Assistent:")

    # Explicitly associate the custom all-day switch label with Django's
    # checkbox so keyboard/assistive-tech and browser-smoke semantics match.
    old_toggle = '<label class="tt-appt-toggle"><span><strong>Ganztägig</strong>'
    new_toggle = '<label class="tt-appt-toggle" for="{{ form.all_day.id_for_label }}"><span><strong>Ganztägig</strong>'
    if new_toggle not in text:
        if old_toggle not in text:
            raise RuntimeError("Phase 10 CI closeout all-day label anchor missing")
        text = text.replace(old_toggle, new_toggle, 1)

    module.write(rel, text)


def _install_runtime_tests(module) -> None:
    rel = "tests/test_tooltime_phase10_appointment_runtime.py"
    test = r'''from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import CalendarEvent, Organization, UserProfile


class ToolTimePhase10AppointmentRuntimeTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI appointment phase10 runtime")
        self.user = User.objects.create_user("appointment-phase10-admin", password="safe-test-password")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.client = Client()
        self.assertTrue(self.client.login(username="appointment-phase10-admin", password="safe-test-password"))

    def test_empty_get_renders_without_querydict_key_lookup_failure(self):
        response = self.client.get(reverse("next-appointment-create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-appointment-create")
        self.assertContains(response, "Kunde oder Projekt auswählen")
        self.assertContains(response, 'data-initial-customer=""')
        self.assertContains(response, 'for="id_all_day"')

    def test_empty_post_is_bound_and_surfaces_validation_errors(self):
        response = self.client.post(reverse("next-appointment-create"), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Termin konnte nicht gespeichert werden.")

    def test_unknown_preselection_is_ignored_without_crashing(self):
        response = self.client.get(reverse("next-appointment-create"), {"customer": "99999999", "project": "99999999"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-initial-customer=""')
        self.assertContains(response, 'data-initial-project=""')

    def test_valid_minimal_post_creates_real_calendar_event(self):
        form = rebuild_views.AppointmentForm(organization=self.org)
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(hours=1)
        end = start + timedelta(hours=1)
        data = {
            "title": "Phase 10 echter Termin",
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": end.strftime("%Y-%m-%dT%H:%M"),
        }
        for name, field in form.fields.items():
            if not field.required or name in data:
                continue
            choices = list(getattr(field, "choices", []) or [])
            usable = [value for value, _label in choices if str(value) != ""]
            if usable:
                data[name] = str(usable[0])
            else:
                data[name] = "Test"

        response = self.client.post(reverse("next-appointment-create"), data)
        self.assertEqual(response.status_code, 302)
        event = CalendarEvent.objects.get(organization=self.org, title="Phase 10 echter Termin")
        self.assertEqual(event.created_by, self.user)
'''
    module.write(rel, test)
    compile(test, str(ROOT / rel), "exec")


def run(module) -> None:
    _patch_backend(module)
    _patch_template(module)
    _install_runtime_tests(module)

    views = module.read("erp/rebuild_views.py")
    template = module.read("templates/rebuild/appointment_form.html")
    for marker in (
        "selected_customer_id",
        "selected_project_id",
        'request.POST if request.method == "POST" else None',
        "organization=org, archived=False, pk=requested_project_id",
        "organization=org, active=True, pk=requested_customer_id",
    ):
        if marker not in views:
            raise RuntimeError(f"Phase 10 CI closeout backend marker missing: {marker}")
    for marker in (
        'data-initial-customer="{{ selected_customer_id|default:\'\' }}"',
        'data-initial-project="{{ selected_project_id|default:\'\' }}"',
        "Nach dem Speichern",
        "Kein Assistent",
        'for="{{ form.all_day.id_for_label }}"',
    ):
        if marker not in template:
            raise RuntimeError(f"Phase 10 CI closeout template marker missing: {marker}")
    if "request.POST.customer_filter" in template or "request.GET.customer" in template:
        raise RuntimeError("Phase 10 CI closeout left unsafe QueryDict template access")
    if "Wizard" in template:
        raise RuntimeError("Phase 10 CI closeout left English Wizard copy in German appointment UI")

    print(f"{MARKER}: safe scoped preselection, real submit coverage, accessible all-day toggle and browser-safe German appointment creation restored.")
