from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 18 RECURRENCE EDIT SCOPE 2026-08-21"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 18 recurrence-edit anchor missing: {label}")
    return text.replace(old, new, 1)


def _function_block(text: str, start_marker: str, end_markers: tuple[str, ...], label: str) -> tuple[int, int, str]:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Phase 18 function start missing: {label}")
    candidates = [text.find(marker, start + len(start_marker)) for marker in end_markers]
    candidates = [value for value in candidates if value >= 0]
    if not candidates:
        raise RuntimeError(f"Phase 18 function end missing: {label}")
    end = min(candidates)
    return start, end, text[start:end]


def patch_edit_backend(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    edit_marker = '@login_required\n@require_http_methods(["GET", "POST"])\ndef appointment_edit(request, pk):\n'
    start, end, block = _function_block(
        text,
        edit_marker,
        (
            '\n\n@login_required\n@require_POST\ndef appointment_delete(request, pk):\n',
            '\n\n@login_required\ndef appointment_detail(request, pk):\n',
        ),
        "appointment_edit",
    )

    old_save = '''    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.organization = org
        # Editing must never rewrite the original author merely because another
        # office user adjusts timing/team later.
        updated.created_by = event.created_by or request.user
        updated.customer = selected_customer
        if not updated.location and updated.customer_id:
            updated.location = _appointment_customer_address(updated.customer)
        updated.save()
        form.save_m2m()
        messages.success(request, "Termin wurde aktualisiert.")
        return redirect("next-appointment-detail", pk=updated.pk)
'''
    new_save = '''    if request.method == "POST" and form.is_valid():
        original_start = event.starts_at
        original_series = event.recurrence_series
        original_index = event.recurrence_index
        series_scope = (request.POST.get("series_scope") or "single").strip().lower()
        if series_scope not in {"single", "following", "all"}:
            series_scope = "single"

        updated = form.save(commit=False)
        updated.organization = org
        # Editing must never rewrite the original author merely because another
        # office user adjusts timing/team later.
        updated.created_by = event.created_by or request.user
        updated.customer = selected_customer
        if not updated.location and updated.customer_id:
            updated.location = _appointment_customer_address(updated.customer)
        updated.save()
        form.save_m2m()

        affected = 1
        if original_series and series_scope in {"following", "all"}:
            targets = m.CalendarEvent.objects.filter(
                organization=org,
                recurrence_series=original_series,
            ).exclude(pk=updated.pk)
            if series_scope == "following":
                targets = targets.filter(recurrence_index__gte=original_index)

            start_delta = updated.starts_at - original_start
            duration = updated.ends_at - updated.starts_at
            attendees = list(updated.attendees.all())
            for occurrence in targets.order_by("recurrence_index"):
                occurrence.starts_at = occurrence.starts_at + start_delta
                occurrence.ends_at = occurrence.starts_at + duration
                occurrence.title = updated.title
                occurrence.type = updated.type
                occurrence.all_day = updated.all_day
                occurrence.location = updated.location
                occurrence.notes = updated.notes
                occurrence.project = updated.project
                occurrence.customer = updated.customer
                occurrence.save(update_fields=[
                    "starts_at", "ends_at", "title", "type", "all_day", "location",
                    "notes", "project", "customer", "updated_at",
                ])
                occurrence.attendees.set(attendees)
                affected += 1

        if affected > 1:
            label = "diesem und allen folgenden Terminen" if series_scope == "following" else "allen Terminen der Serie"
            messages.success(request, f"Änderungen wurden auf {label} übernommen ({affected} Termine).")
        else:
            messages.success(request, "Termin wurde aktualisiert.")
        return redirect("next-appointment-detail", pk=updated.pk)
'''
    block = _replace_once(block, old_save, new_save, "appointment edit persistence block")
    text = text[:start] + block + text[end:]
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_edit_form(module) -> None:
    rel = "templates/rebuild/appointment_form.html"
    text = module.read(rel)
    anchor = '''              <small>{% if mode == 'edit' and event.recurrence_series %}Dieser Termin gehört zu einer Serie. Änderungen auf dieser Seite gelten nur für diesen einzelnen Termin.{% elif mode == 'edit' %}Wiederholung wird nur beim Erstellen einer Terminserie festgelegt.{% else %}Bei einer Wiederholung werden eigenständige, dauerhaft gespeicherte Termine erzeugt. Maximal 52 Termine pro Serie.{% endif %}</small>'''
    replacement = '''              <small>{% if mode == 'edit' and event.recurrence_series %}Dieser Termin gehört zu einer Serie. Wähle unten, für welche Termine Deine Änderungen gelten sollen.{% elif mode == 'edit' %}Wiederholung wird nur beim Erstellen einer Terminserie festgelegt.{% else %}Bei einer Wiederholung werden eigenständige, dauerhaft gespeicherte Termine erzeugt. Maximal 52 Termine pro Serie.{% endif %}</small>
              {% if mode == 'edit' and event.recurrence_series %}
              <div class="tt-appt-series-scope" data-series-scope>
                <label for="appointment-series-scope">Änderungen anwenden auf</label>
                <select class="next-control" id="appointment-series-scope" name="series_scope">
                  <option value="single">Nur diesen Termin</option>
                  <option value="following">Diesen und alle folgenden Termine</option>
                  <option value="all">Alle Termine der Serie</option>
                </select>
              </div>
              {% endif %}'''
    text = _replace_once(text, anchor, replacement, "series edit scope controls")
    module.write(rel, text)

    css_rel = "static/css/tooltime-phase10-appointments.css"
    css = module.read(css_rel)
    marker = "/* A+BAU TOOLTIME PHASE 18 RECURRENCE EDIT SCOPE */"
    if marker not in css:
        css += '''\n/* A+BAU TOOLTIME PHASE 18 RECURRENCE EDIT SCOPE */
.tt-appt-series-scope{display:grid;grid-template-columns:minmax(0,1fr) minmax(220px,1.1fr);align-items:center;gap:12px;margin-top:10px;padding:12px;border:1px solid #dfe7f2;border-radius:11px;background:#f7faff}.tt-appt-series-scope label{font-size:12px;font-weight:750;color:#3d4b61}@media(max-width:700px){.tt-appt-series-scope{grid-template-columns:1fr}}\n'''
        module.write(css_rel, css)


def install_tests(module) -> None:
    runtime_rel = "tests/test_tooltime_phase18_recurrence_edit_scope.py"
    runtime = r'''from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import CalendarEvent, Customer, Organization, UserProfile


class ToolTimePhase18RecurrenceEditScopeTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI phase18")
        self.user = User.objects.create_user("phase18-office", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="phase18-office", password="safe-test-password"))
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P18-1",
            type="business",
            company="Serienkunde Phase18",
            street="Serienweg 18",
            postal_code="60318",
            city="Frankfurt",
        )

    def _payload(self, title, start, *, repeat_rule="none", repeat_count=1, series_scope="single"):
        form = rebuild_views.AppointmentForm(organization=self.org)
        data = {
            "title": title,
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "customer_filter": str(self.customer.pk),
            "repeat_rule": repeat_rule,
            "repeat_count": str(repeat_count),
            "series_scope": series_scope,
        }
        for name, field in form.fields.items():
            if name in data or not field.required:
                continue
            choices = list(getattr(field, "choices", []) or [])
            usable = [value for value, _label in choices if str(value) != ""]
            data[name] = str(usable[0]) if usable else "Test"
        return data

    def _create_series(self, title):
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(days=1)
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload(title, start, repeat_rule="daily", repeat_count=3),
        )
        self.assertEqual(response.status_code, 302)
        return list(CalendarEvent.objects.filter(title=title).order_by("recurrence_index"))

    def test_edit_form_offers_all_three_tooltime_scopes(self):
        events = self._create_series("Scope form")
        response = self.client.get(reverse("next-appointment-edit", args=[events[1].pk]))
        self.assertEqual(response.status_code, 200)
        for marker in ("Nur diesen Termin", "Diesen und alle folgenden Termine", "Alle Termine der Serie"):
            self.assertContains(response, marker)

    def test_single_scope_changes_only_selected_occurrence(self):
        events = self._create_series("Scope single")
        selected = events[1]
        start = timezone.localtime(selected.starts_at) + timedelta(hours=1)
        response = self.client.post(
            reverse("next-appointment-edit", args=[selected.pk]),
            self._payload("Nur dieser geändert", start, series_scope="single"),
        )
        self.assertEqual(response.status_code, 302)
        titles = list(
            CalendarEvent.objects.filter(recurrence_series=selected.recurrence_series)
            .order_by("recurrence_index").values_list("title", flat=True)
        )
        self.assertEqual(titles, ["Scope single", "Nur dieser geändert", "Scope single"])

    def test_following_scope_changes_selected_and_later_occurrences(self):
        events = self._create_series("Scope following")
        selected = events[1]
        original_first_start = events[0].starts_at
        original_last_start = events[2].starts_at
        start = timezone.localtime(selected.starts_at) + timedelta(hours=2)
        response = self.client.post(
            reverse("next-appointment-edit", args=[selected.pk]),
            self._payload("Ab hier geändert", start, series_scope="following"),
        )
        self.assertEqual(response.status_code, 302)
        rows = list(
            CalendarEvent.objects.filter(recurrence_series=selected.recurrence_series).order_by("recurrence_index")
        )
        self.assertEqual([event.title for event in rows], ["Scope following", "Ab hier geändert", "Ab hier geändert"])
        self.assertEqual(rows[0].starts_at, original_first_start)
        self.assertEqual(rows[2].starts_at, original_last_start + timedelta(hours=2))

    def test_all_scope_changes_every_occurrence(self):
        events = self._create_series("Scope all")
        selected = events[1]
        start = timezone.localtime(selected.starts_at) + timedelta(minutes=30)
        response = self.client.post(
            reverse("next-appointment-edit", args=[selected.pk]),
            self._payload("Alle geändert", start, series_scope="all"),
        )
        self.assertEqual(response.status_code, 302)
        rows = list(
            CalendarEvent.objects.filter(recurrence_series=selected.recurrence_series).order_by("recurrence_index")
        )
        self.assertEqual([event.title for event in rows], ["Alle geändert", "Alle geändert", "Alle geändert"])
        self.assertEqual(rows[0].starts_at, events[0].starts_at + timedelta(minutes=30))
        self.assertEqual(rows[2].starts_at, events[2].starts_at + timedelta(minutes=30))
'''
    module.write(runtime_rel, runtime)
    compile(runtime, str(ROOT / runtime_rel), "exec")

    contract_rel = "tests/test_tooltime_phase18_recurrence_edit_scope_contract.py"
    contract = r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase18RecurrenceEditScopeContractTests(SimpleTestCase):
    def test_series_edit_scope_is_persisted_by_real_backend(self):
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        form = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        for marker in (
            'series_scope = (request.POST.get("series_scope") or "single")',
            'series_scope in {"following", "all"}',
            'recurrence_index__gte=original_index',
            'start_delta = updated.starts_at - original_start',
            'occurrence.attendees.set(attendees)',
        ):
            self.assertIn(marker, views)
        for marker in (
            'name="series_scope"',
            'value="single"',
            'value="following"',
            'value="all"',
            "Nur diesen Termin",
            "Diesen und alle folgenden Termine",
            "Alle Termine der Serie",
        ):
            self.assertIn(marker, form)
'''
    module.write(contract_rel, contract)
    compile(contract, str(ROOT / contract_rel), "exec")


def run(module) -> None:
    patch_edit_backend(module)
    patch_edit_form(module)
    install_tests(module)
    views = module.read("erp/rebuild_views.py")
    form = module.read("templates/rebuild/appointment_form.html")
    for marker in (
        'series_scope = (request.POST.get("series_scope") or "single")',
        'series_scope in {"following", "all"}',
        'recurrence_index__gte=original_index',
        'occurrence.attendees.set(attendees)',
    ):
        if marker not in views:
            raise RuntimeError(f"Phase 18 backend guard missing: {marker}")
    for marker in ("Nur diesen Termin", "Diesen und alle folgenden Termine", "Alle Termine der Serie"):
        if marker not in form:
            raise RuntimeError(f"Phase 18 form guard missing: {marker}")
    print(f"{MARKER}: office users can apply recurrence edits to one occurrence, the selected and all following occurrences, or the whole series while preserving relative schedule offsets.")
