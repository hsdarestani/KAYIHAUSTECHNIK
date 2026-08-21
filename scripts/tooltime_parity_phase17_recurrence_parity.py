from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 17 RECURRENCE PARITY 2026-08-21"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 17 recurrence-parity anchor missing: {label}")
    return text.replace(old, new, 1)


def patch_recurrence_choices(module) -> None:
    model_rel = "erp/models.py"
    model = module.read(model_rel)
    old_choices = '''        choices=[
            ("none", "Keine Wiederholung"),
            ("daily", "Täglich"),
            ("weekly", "Wöchentlich"),
            ("monthly", "Monatlich"),
        ],
'''
    new_choices = '''        choices=[
            ("none", "Keine Wiederholung"),
            ("daily", "Täglich"),
            ("weekdays", "Werktags"),
            ("weekly", "Wöchentlich"),
            ("biweekly", "Alle zwei Wochen"),
            ("monthly", "Monatlich"),
            ("half_yearly", "Halbjährlich"),
            ("yearly", "Jährlich"),
        ],
'''
    model = _replace_once(model, old_choices, new_choices, "CalendarEvent recurrence choices")
    module.write(model_rel, model)
    compile(model, str(ROOT / model_rel), "exec")

    migration_rel = "erp/migrations/0021_calendar_event_recurrence.py"
    migration = module.read(migration_rel)
    migration = _replace_once(migration, old_choices, new_choices, "0021 migration recurrence choices")
    module.write(migration_rel, migration)
    compile(migration, str(ROOT / migration_rel), "exec")


def patch_recurrence_engine(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    text = _replace_once(
        text,
        '    if rule not in {"none", "daily", "weekly", "monthly"}:\n',
        '    if rule not in {"none", "daily", "weekdays", "weekly", "biweekly", "monthly", "half_yearly", "yearly"}:\n',
        "accepted recurrence rules",
    )

    old_shift = '''def _appointment_recurrence_shift(value, rule, index):
    if rule == "daily":
        return value + timedelta(days=index)
    if rule == "weekly":
        return value + timedelta(days=7 * index)
    if rule == "monthly":
        return _appointment_shift_month(value, index)
    return value
'''
    new_shift = '''def _appointment_shift_weekdays(value, index):
    if index <= 0:
        return value
    shifted = value
    remaining = index
    while remaining:
        shifted = shifted + timedelta(days=1)
        if timezone.localtime(shifted).weekday() < 5:
            remaining -= 1
    return shifted


def _appointment_recurrence_shift(value, rule, index):
    if rule == "daily":
        return value + timedelta(days=index)
    if rule == "weekdays":
        return _appointment_shift_weekdays(value, index)
    if rule == "weekly":
        return value + timedelta(days=7 * index)
    if rule == "biweekly":
        return value + timedelta(days=14 * index)
    if rule == "monthly":
        return _appointment_shift_month(value, index)
    if rule == "half_yearly":
        return _appointment_shift_month(value, 6 * index)
    if rule == "yearly":
        return _appointment_shift_month(value, 12 * index)
    return value
'''
    text = _replace_once(text, old_shift, new_shift, "recurrence shift engine")

    detail_marker = '\n\n@login_required\ndef appointment_detail(request, pk):\n'
    if "def appointment_delete(request, pk):" not in text:
        pos = text.find(detail_marker)
        if pos < 0:
            raise RuntimeError("Phase 17 appointment_detail boundary missing")
        delete_view = '''\n\n@login_required
@require_POST
def appointment_delete(request, pk):
    org = _org(request)
    event = get_object_or_404(m.CalendarEvent.objects.filter(organization=org), pk=pk)
    if _is_field_user(request):
        messages.warning(request, "Die Terminplanung kann nur im Büro gelöscht werden.")
        return redirect("next-appointment-detail", pk=event.pk)

    scope = (request.POST.get("scope") or "single").strip().lower()
    if scope == "following" and event.recurrence_series:
        deleted, _ = m.CalendarEvent.objects.filter(
            organization=org,
            recurrence_series=event.recurrence_series,
            recurrence_index__gte=event.recurrence_index,
        ).delete()
        messages.success(request, f"{deleted} Termin(e) der Serie wurden gelöscht.")
    else:
        event.delete()
        messages.success(request, "Termin wurde gelöscht.")
    return redirect("next-appointments")
'''
        text = text[:pos] + delete_view + text[pos:]

    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_urls(module) -> None:
    rel = "erp/rebuild_urls.py"
    text = module.read(rel)
    anchor = '    path("appointments/<int:pk>/edit/", views.appointment_edit, name="next-appointment-edit"),\n'
    addition = '    path("appointments/<int:pk>/delete/", views.appointment_delete, name="next-appointment-delete"),\n'
    if addition not in text:
        if anchor not in text:
            raise RuntimeError("Phase 17 appointment edit URL anchor missing")
        text = text.replace(anchor, anchor + addition, 1)
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_form_template(module) -> None:
    rel = "templates/rebuild/appointment_form.html"
    text = module.read(rel)
    old_options = '''                <option value="daily" {% if selected_repeat_rule == 'daily' %}selected{% endif %}>Täglich</option>
                <option value="weekly" {% if selected_repeat_rule == 'weekly' %}selected{% endif %}>Wöchentlich</option>
                <option value="monthly" {% if selected_repeat_rule == 'monthly' %}selected{% endif %}>Monatlich</option>
'''
    new_options = '''                <option value="daily" {% if selected_repeat_rule == 'daily' %}selected{% endif %}>Täglich</option>
                <option value="weekdays" {% if selected_repeat_rule == 'weekdays' %}selected{% endif %}>Werktags</option>
                <option value="weekly" {% if selected_repeat_rule == 'weekly' %}selected{% endif %}>Wöchentlich</option>
                <option value="biweekly" {% if selected_repeat_rule == 'biweekly' %}selected{% endif %}>Alle zwei Wochen</option>
                <option value="monthly" {% if selected_repeat_rule == 'monthly' %}selected{% endif %}>Monatlich</option>
                <option value="half_yearly" {% if selected_repeat_rule == 'half_yearly' %}selected{% endif %}>Halbjährlich</option>
                <option value="yearly" {% if selected_repeat_rule == 'yearly' %}selected{% endif %}>Jährlich</option>
'''
    text = _replace_once(text, old_options, new_options, "recurrence select options")
    module.write(rel, text)


def patch_detail_template(module) -> None:
    rel = "templates/rebuild/appointment_detail.html"
    text = module.read(rel)
    marker = '  {% if project_missing %}\n'
    if "tt-appt-delete-actions" not in text:
        if marker not in text:
            raise RuntimeError("Phase 17 appointment detail insertion anchor missing")
        controls = r'''  {% if request.user.profile.role != 'technician' and not request.user.profile.is_mobile_worker %}
  <section class="tt-appt-delete-actions" aria-label="Termin löschen">
    <form method="post" action="{% url 'next-appointment-delete' event.pk %}">{% csrf_token %}
      <button class="nx-btn" type="submit" name="scope" value="single">Termin löschen</button>
      {% if event.recurrence_series %}<button class="nx-btn" type="submit" name="scope" value="following">Diesen und alle folgenden Serientermine löschen</button>{% endif %}
    </form>
  </section>
  {% endif %}

'''
        text = text.replace(marker, controls + marker, 1)
    module.write(rel, text)

    css_rel = "static/css/tooltime-phase14-appointment-detail.css"
    css = module.read(css_rel)
    css_marker = "/* A+BAU TOOLTIME PHASE 17 DELETE ACTIONS */"
    if css_marker not in css:
        css += '''\n/* A+BAU TOOLTIME PHASE 17 DELETE ACTIONS */
.tt-appt-delete-actions{display:flex;justify-content:flex-end;margin:0 0 18px}.tt-appt-delete-actions form{display:flex;gap:9px;flex-wrap:wrap}.tt-appt-delete-actions .nx-btn{color:#9b2d2d;border-color:#eed5d5;background:#fffafa}@media(max-width:650px){.tt-appt-delete-actions,.tt-appt-delete-actions form{display:grid;width:100%}.tt-appt-delete-actions .nx-btn{width:100%}}\n'''
        module.write(css_rel, css)


def install_tests(module) -> None:
    runtime_rel = "tests/test_tooltime_phase17_recurrence_parity.py"
    runtime = r'''from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import CalendarEvent, Customer, Organization, UserProfile


class ToolTimePhase17RecurrenceParityTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI phase17")
        self.user = User.objects.create_user("phase17-office", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="phase17-office", password="safe-test-password"))
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P17-1",
            type="business",
            company="Serienkunde Phase17",
            street="Serienweg 17",
            postal_code="60317",
            city="Frankfurt",
        )

    def _payload(self, title, start, *, rule, count):
        form = rebuild_views.AppointmentForm(organization=self.org)
        data = {
            "title": title,
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "customer_filter": str(self.customer.pk),
            "repeat_rule": rule,
            "repeat_count": str(count),
        }
        for name, field in form.fields.items():
            if name in data or not field.required:
                continue
            choices = list(getattr(field, "choices", []) or [])
            usable = [value for value, _label in choices if str(value) != ""]
            data[name] = str(usable[0]) if usable else "Test"
        return data

    def test_weekday_series_skips_weekend(self):
        start = timezone.make_aware(datetime(2026, 8, 21, 10, 0), timezone.get_current_timezone())  # Friday
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload("Werktagsserie", start, rule="weekdays", count=3),
        )
        self.assertEqual(response.status_code, 302)
        events = list(CalendarEvent.objects.filter(title="Werktagsserie").order_by("recurrence_index"))
        self.assertEqual([timezone.localtime(event.starts_at).date().isoformat() for event in events], [
            "2026-08-21", "2026-08-24", "2026-08-25",
        ])

    def test_biweekly_half_yearly_and_yearly_rules_are_persisted(self):
        start = timezone.make_aware(datetime(2026, 8, 21, 10, 0), timezone.get_current_timezone())
        expectations = {
            "biweekly": "2026-09-04",
            "half_yearly": "2027-02-21",
            "yearly": "2027-08-21",
        }
        for rule, second_date in expectations.items():
            title = f"Serie {rule}"
            response = self.client.post(
                reverse("next-appointment-create"),
                self._payload(title, start, rule=rule, count=2),
            )
            self.assertEqual(response.status_code, 302)
            events = list(CalendarEvent.objects.filter(title=title).order_by("recurrence_index"))
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].recurrence_rule, rule)
            self.assertEqual(timezone.localtime(events[1].starts_at).date().isoformat(), second_date)

    def test_single_delete_keeps_other_series_occurrences(self):
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(days=1)
        self.client.post(reverse("next-appointment-create"), self._payload("Delete single", start, rule="daily", count=3))
        events = list(CalendarEvent.objects.filter(title="Delete single").order_by("recurrence_index"))
        response = self.client.post(reverse("next-appointment-delete", args=[events[1].pk]), {"scope": "single"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(CalendarEvent.objects.filter(title="Delete single").values_list("recurrence_index", flat=True)), [0, 2])

    def test_delete_following_removes_selected_and_later_occurrences(self):
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(days=2)
        self.client.post(reverse("next-appointment-create"), self._payload("Delete following", start, rule="daily", count=4))
        events = list(CalendarEvent.objects.filter(title="Delete following").order_by("recurrence_index"))
        response = self.client.post(reverse("next-appointment-delete", args=[events[1].pk]), {"scope": "following"})
        self.assertEqual(response.status_code, 302)
        remaining = list(CalendarEvent.objects.filter(title="Delete following").values_list("recurrence_index", flat=True))
        self.assertEqual(remaining, [0])

    def test_create_form_exposes_tooltime_interval_set(self):
        response = self.client.get(reverse("next-appointment-create"))
        self.assertEqual(response.status_code, 200)
        for marker in ("Werktags", "Alle zwei Wochen", "Halbjährlich", "Jährlich"):
            self.assertContains(response, marker)
'''
    module.write(runtime_rel, runtime)
    compile(runtime, str(ROOT / runtime_rel), "exec")

    contract_rel = "tests/test_tooltime_phase17_recurrence_parity_contract.py"
    contract = r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase17RecurrenceParityContractTests(SimpleTestCase):
    def test_interval_choices_delete_route_and_detail_actions_are_real(self):
        model = (ROOT / "erp/models.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0021_calendar_event_recurrence.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        form = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        detail = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        for marker in ("weekdays", "biweekly", "half_yearly", "yearly"):
            self.assertIn(marker, model)
            self.assertIn(marker, migration)
            self.assertIn(marker, views)
            self.assertIn(marker, form)
        self.assertIn("def appointment_delete(request, pk):", views)
        self.assertIn('scope == "following"', views)
        self.assertIn("recurrence_index__gte=event.recurrence_index", views)
        self.assertIn("next-appointment-delete", urls)
        self.assertIn("next-appointment-delete", detail)
        self.assertIn("Diesen und alle folgenden Serientermine löschen", detail)
'''
    module.write(contract_rel, contract)
    compile(contract, str(ROOT / contract_rel), "exec")


def run(module) -> None:
    patch_recurrence_choices(module)
    patch_recurrence_engine(module)
    patch_urls(module)
    patch_form_template(module)
    patch_detail_template(module)
    install_tests(module)

    model = module.read("erp/models.py")
    migration = module.read("erp/migrations/0021_calendar_event_recurrence.py")
    views = module.read("erp/rebuild_views.py")
    urls = module.read("erp/rebuild_urls.py")
    form = module.read("templates/rebuild/appointment_form.html")
    detail = module.read("templates/rebuild/appointment_detail.html")
    for marker in ("weekdays", "biweekly", "half_yearly", "yearly"):
        for text, label in ((model, "model"), (migration, "migration"), (views, "views"), (form, "form")):
            if marker not in text:
                raise RuntimeError(f"Phase 17 {label} recurrence marker missing: {marker}")
    for marker in ("def appointment_delete(request, pk):", 'scope == "following"', "recurrence_index__gte=event.recurrence_index"):
        if marker not in views:
            raise RuntimeError(f"Phase 17 delete backend marker missing: {marker}")
    if "next-appointment-delete" not in urls or "next-appointment-delete" not in detail:
        raise RuntimeError("Phase 17 delete route/detail action missing")
    print(f"{MARKER}: ToolTime interval set plus single/following-series deletion installed; existing bounded occurrence generation remains safety-limited to 52 persisted appointments per creation.")
