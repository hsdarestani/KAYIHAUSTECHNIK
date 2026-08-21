from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 19 CUSTOM RECURRENCE 2026-08-21"
MIGRATION_REL = "erp/migrations/0022_calendar_event_custom_recurrence.py"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 19 custom-recurrence anchor missing: {label}")
    return text.replace(old, new, 1)


def _function_block(text: str, start_marker: str, end_markers: tuple[str, ...], label: str) -> tuple[int, int, str]:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Phase 19 function start missing: {label}")
    candidates = [text.find(marker, start + len(start_marker)) for marker in end_markers]
    candidates = [value for value in candidates if value >= 0]
    if not candidates:
        raise RuntimeError(f"Phase 19 function end missing: {label}")
    end = min(candidates)
    return start, end, text[start:end]


def patch_model(module) -> None:
    rel = "erp/models.py"
    text = module.read(rel)
    old_choices = '''            ("half_yearly", "Halbjährlich"),
            ("yearly", "Jährlich"),
        ],
'''
    new_choices = '''            ("half_yearly", "Halbjährlich"),
            ("yearly", "Jährlich"),
            ("custom", "Benutzerdefiniert"),
        ],
'''
    text = _replace_once(text, old_choices, new_choices, "custom recurrence model choice")

    anchor = "    recurrence_index = models.PositiveIntegerField(default=0, editable=False)\n"
    fields = '''    recurrence_index = models.PositiveIntegerField(default=0, editable=False)
    recurrence_interval = models.PositiveSmallIntegerField(default=1, editable=False)
    recurrence_unit = models.CharField(
        max_length=12,
        choices=[
            ("day", "Tag(e)"),
            ("weekday", "Werktag(e)"),
            ("week", "Woche(n)"),
            ("month", "Monat(e)"),
            ("year", "Jahr(e)"),
        ],
        default="day",
        editable=False,
    )
    recurrence_until = models.DateField(null=True, blank=True, editable=False)
'''
    text = _replace_once(text, anchor, fields, "custom recurrence model metadata")
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")

    migration21_rel = "erp/migrations/0021_calendar_event_recurrence.py"
    migration21 = module.read(migration21_rel)
    old_migration_choice = '''                    ("half_yearly", "Halbjährlich"),
                    ("yearly", "Jährlich"),
                ],
'''
    new_migration_choice = '''                    ("half_yearly", "Halbjährlich"),
                    ("yearly", "Jährlich"),
                    ("custom", "Benutzerdefiniert"),
                ],
'''
    migration21 = _replace_once(
        migration21,
        old_migration_choice,
        new_migration_choice,
        "0021 custom recurrence choice state",
    )
    module.write(migration21_rel, migration21)
    compile(migration21, str(ROOT / migration21_rel), "exec")


def install_migration(module) -> None:
    migration = '''from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("erp", "0021_calendar_event_recurrence"),
    ]

    operations = [
        migrations.AddField(
            model_name="calendarevent",
            name="recurrence_interval",
            field=models.PositiveSmallIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="recurrence_unit",
            field=models.CharField(
                choices=[
                    ("day", "Tag(e)"),
                    ("weekday", "Werktag(e)"),
                    ("week", "Woche(n)"),
                    ("month", "Monat(e)"),
                    ("year", "Jahr(e)"),
                ],
                default="day",
                editable=False,
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="recurrence_until",
            field=models.DateField(blank=True, editable=False, null=True),
        ),
    ]
'''
    module.write(MIGRATION_REL, migration)
    compile(migration, str(ROOT / MIGRATION_REL), "exec")


def patch_backend(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    if "import datetime as dt\n" not in text:
        anchor = "import calendar as month_calendar\n"
        if anchor not in text:
            raise RuntimeError("Phase 19 calendar import anchor missing")
        text = text.replace(anchor, anchor + "import datetime as dt\n", 1)

    request_start = "def _appointment_recurrence_request(request):\n"
    start, end, _block = _function_block(
        text,
        request_start,
        ("\n\ndef _appointment_shift_month",),
        "recurrence request",
    )
    request_helper = '''def _appointment_recurrence_request(request):
    if request.method != "POST":
        return "none", 4, 1, "day", None
    rule = (request.POST.get("repeat_rule") or "none").strip().lower()
    allowed = {"none", "daily", "weekdays", "weekly", "biweekly", "monthly", "half_yearly", "yearly", "custom"}
    if rule not in allowed:
        rule = "none"
    try:
        count = int(request.POST.get("repeat_count") or 4)
    except (TypeError, ValueError):
        count = 4
    count = max(2, min(count, 52)) if rule != "none" else 1
    try:
        interval = int(request.POST.get("repeat_interval") or 1)
    except (TypeError, ValueError):
        interval = 1
    interval = max(1, min(interval, 52))
    unit = (request.POST.get("repeat_unit") or "day").strip().lower()
    if unit not in {"day", "weekday", "week", "month", "year"}:
        unit = "day"
    until = None
    end_mode = (request.POST.get("repeat_end_mode") or "count").strip().lower()
    until_raw = (request.POST.get("repeat_until") or "").strip()
    if rule == "custom" and end_mode == "date" and until_raw:
        try:
            until = dt.date.fromisoformat(until_raw)
        except ValueError:
            until = None
    return rule, count, interval, unit, until
'''
    text = text[:start] + request_helper + text[end:]

    shift_start = "def _appointment_recurrence_shift(value, rule, index):\n"
    shift_pos = text.find(shift_start)
    if shift_pos < 0:
        raise RuntimeError("Phase 19 recurrence shift signature missing")
    shift_end = text.find("\n\ndef _appointment_customer_address", shift_pos)
    if shift_end < 0:
        raise RuntimeError("Phase 19 recurrence shift boundary missing")
    shift_helper = '''def _appointment_recurrence_shift(value, rule, index, interval=1, unit="day"):
    if rule == "custom":
        step = interval * index
        if unit == "day":
            return value + timedelta(days=step)
        if unit == "weekday":
            return _appointment_shift_weekdays(value, step)
        if unit == "week":
            return value + timedelta(days=7 * step)
        if unit == "month":
            return _appointment_shift_month(value, step)
        if unit == "year":
            return _appointment_shift_month(value, 12 * step)
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


def _appointment_recurrence_indices(starts_at, rule, count, interval=1, unit="day", until=None):
    if rule == "none":
        return []
    if rule == "custom" and until is not None:
        indices = []
        for index in range(1, 731):
            candidate = _appointment_recurrence_shift(starts_at, rule, index, interval, unit)
            if timezone.localtime(candidate).date() > until:
                break
            indices.append(index)
        return indices
    return list(range(1, count))
'''
    text = text[:shift_pos] + shift_helper + text[shift_end:]

    text = _replace_once(
        text,
        "    repeat_rule, repeat_count = _appointment_recurrence_request(request)\n",
        "    repeat_rule, repeat_count, repeat_interval, repeat_unit, repeat_until = _appointment_recurrence_request(request)\n",
        "create recurrence request unpack",
    )

    old_series = '''        series_id = uuid.uuid4() if repeat_rule != "none" and repeat_count > 1 else None
        event.recurrence_series = series_id
        event.recurrence_rule = repeat_rule
        event.recurrence_index = 0
        event.save()
'''
    new_series = '''        occurrence_indices = _appointment_recurrence_indices(
            event.starts_at, repeat_rule, repeat_count, repeat_interval, repeat_unit, repeat_until
        )
        series_id = uuid.uuid4() if repeat_rule != "none" and occurrence_indices else None
        event.recurrence_series = series_id
        event.recurrence_rule = repeat_rule
        event.recurrence_index = 0
        event.recurrence_interval = repeat_interval
        event.recurrence_unit = repeat_unit
        event.recurrence_until = repeat_until
        event.save()
'''
    text = _replace_once(text, old_series, new_series, "custom recurrence series metadata")

    text = _replace_once(
        text,
        "            for occurrence_index in range(1, repeat_count):\n",
        "            for occurrence_index in occurrence_indices:\n",
        "custom recurrence occurrence indices",
    )
    text = text.replace(
        "starts_at=_appointment_recurrence_shift(event.starts_at, repeat_rule, occurrence_index),",
        "starts_at=_appointment_recurrence_shift(event.starts_at, repeat_rule, occurrence_index, repeat_interval, repeat_unit),",
        1,
    )
    text = text.replace(
        "ends_at=_appointment_recurrence_shift(event.ends_at, repeat_rule, occurrence_index),",
        "ends_at=_appointment_recurrence_shift(event.ends_at, repeat_rule, occurrence_index, repeat_interval, repeat_unit),",
        1,
    )
    occurrence_anchor = '''                    recurrence_series=series_id,
                    recurrence_rule=repeat_rule,
                    recurrence_index=occurrence_index,
'''
    occurrence_replacement = '''                    recurrence_series=series_id,
                    recurrence_rule=repeat_rule,
                    recurrence_index=occurrence_index,
                    recurrence_interval=repeat_interval,
                    recurrence_unit=repeat_unit,
                    recurrence_until=repeat_until,
'''
    text = _replace_once(text, occurrence_anchor, occurrence_replacement, "occurrence custom recurrence metadata")
    text = _replace_once(
        text,
        '            messages.success(request, f"Terminserie mit {repeat_count} Terminen wurde geplant.")\n',
        '            messages.success(request, f"Terminserie mit {1 + len(occurrence_indices)} Terminen wurde geplant.")\n',
        "accurate custom recurrence success count",
    )

    create_context_anchor = '''        "selected_repeat_rule": repeat_rule,
        "repeat_count": repeat_count,
    })'''
    create_context_replacement = '''        "selected_repeat_rule": repeat_rule,
        "repeat_count": repeat_count,
        "repeat_interval": repeat_interval,
        "repeat_unit": repeat_unit,
        "repeat_until": repeat_until.isoformat() if repeat_until else "",
    })'''
    text = _replace_once(text, create_context_anchor, create_context_replacement, "custom recurrence create context")

    edit_context_anchor = '''        "selected_repeat_rule": event.recurrence_rule,
        "repeat_count": 1,
    })'''
    edit_context_replacement = '''        "selected_repeat_rule": event.recurrence_rule,
        "repeat_count": 1,
        "repeat_interval": event.recurrence_interval,
        "repeat_unit": event.recurrence_unit,
        "repeat_until": event.recurrence_until.isoformat() if event.recurrence_until else "",
    })'''
    text = _replace_once(text, edit_context_anchor, edit_context_replacement, "custom recurrence edit context")

    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_template(module) -> None:
    rel = "templates/rebuild/appointment_form.html"
    text = module.read(rel)
    option_anchor = '''                <option value="yearly" {% if selected_repeat_rule == 'yearly' %}selected{% endif %}>Jährlich</option>
'''
    option_replacement = '''                <option value="yearly" {% if selected_repeat_rule == 'yearly' %}selected{% endif %}>Jährlich</option>
                <option value="custom" {% if selected_repeat_rule == 'custom' %}selected{% endif %}>Benutzerdefiniert …</option>
'''
    text = _replace_once(text, option_anchor, option_replacement, "custom recurrence select option")

    count_anchor = '''              <div class="tt-appt-repeat-count" data-repeat-count-row hidden>
                <label for="appointment-repeat-count">Anzahl Termine</label>
                <input class="next-control" id="appointment-repeat-count" name="repeat_count" type="number" min="2" max="52" value="{{ repeat_count|default:4 }}" data-repeat-count>
              </div>
'''
    count_replacement = '''              <div class="tt-appt-repeat-count" data-repeat-count-row hidden>
                <label for="appointment-repeat-count">Anzahl Termine</label>
                <input class="next-control" id="appointment-repeat-count" name="repeat_count" type="number" min="2" max="52" value="{{ repeat_count|default:4 }}" data-repeat-count>
              </div>
              <div class="tt-appt-custom-repeat" data-custom-repeat hidden>
                <div><label for="appointment-repeat-interval">Rhythmus</label><div class="tt-appt-custom-rhythm"><span>Alle</span><input class="next-control" id="appointment-repeat-interval" name="repeat_interval" type="number" min="1" max="52" value="{{ repeat_interval|default:1 }}" data-repeat-interval><select class="next-control" name="repeat_unit" data-repeat-unit><option value="day" {% if repeat_unit == 'day' %}selected{% endif %}>Tag(e)</option><option value="weekday" {% if repeat_unit == 'weekday' %}selected{% endif %}>Werktag(e)</option><option value="week" {% if repeat_unit == 'week' %}selected{% endif %}>Woche(n)</option><option value="month" {% if repeat_unit == 'month' %}selected{% endif %}>Monat(e)</option><option value="year" {% if repeat_unit == 'year' %}selected{% endif %}>Jahr(e)</option></select></div></div>
                <div><label for="appointment-repeat-end-mode">Serie endet</label><select class="next-control" id="appointment-repeat-end-mode" name="repeat_end_mode" data-repeat-end-mode><option value="count">Nach Anzahl</option><option value="date">An einem Datum</option></select></div>
                <div data-repeat-until-row hidden><label for="appointment-repeat-until">Enddatum</label><input class="next-control" id="appointment-repeat-until" name="repeat_until" type="date" value="{{ repeat_until|default:'' }}" data-repeat-until></div>
              </div>
'''
    text = _replace_once(text, count_anchor, count_replacement, "custom recurrence controls")

    variable_anchor = "  const repeatCount = form.querySelector('[data-repeat-count]');\n"
    variable_addition = '''  const customRepeat = form.querySelector('[data-custom-repeat]');
  const repeatEndMode = form.querySelector('[data-repeat-end-mode]');
  const repeatUntilRow = form.querySelector('[data-repeat-until-row]');
  const repeatUntil = form.querySelector('[data-repeat-until]');
'''
    if variable_addition not in text:
        if variable_anchor not in text:
            raise RuntimeError("Phase 19 recurrence JS variables anchor missing")
        text = text.replace(variable_anchor, variable_anchor + variable_addition, 1)

    old_update = '''  const updateRepeatControls = () => {
    if (!repeatCountRow || !repeatRule) return;
    const recurring = repeatRule.value !== 'none' && root.dataset.appointmentMode !== 'edit';
    repeatCountRow.hidden = !recurring;
    if (repeatCount) repeatCount.disabled = !recurring;
  };
  repeatRule?.addEventListener('change', updateRepeatControls);
'''
    new_update = '''  const updateRepeatControls = () => {
    if (!repeatCountRow || !repeatRule) return;
    const editable = root.dataset.appointmentMode !== 'edit';
    const recurring = repeatRule.value !== 'none' && editable;
    const custom = repeatRule.value === 'custom' && editable;
    repeatCountRow.hidden = !recurring || (custom && repeatEndMode?.value === 'date');
    if (repeatCount) repeatCount.disabled = !recurring || (custom && repeatEndMode?.value === 'date');
    if (customRepeat) customRepeat.hidden = !custom;
    if (repeatUntilRow) repeatUntilRow.hidden = !custom || repeatEndMode?.value !== 'date';
    if (repeatUntil) repeatUntil.disabled = !custom || repeatEndMode?.value !== 'date';
  };
  repeatRule?.addEventListener('change', updateRepeatControls);
  repeatEndMode?.addEventListener('change', updateRepeatControls);
'''
    text = _replace_once(text, old_update, new_update, "custom recurrence JS behavior")
    module.write(rel, text)

    css_rel = "static/css/tooltime-phase10-appointments.css"
    css = module.read(css_rel)
    marker = "/* A+BAU TOOLTIME PHASE 19 CUSTOM RECURRENCE */"
    if marker not in css:
        css += '''\n/* A+BAU TOOLTIME PHASE 19 CUSTOM RECURRENCE */
.tt-appt-custom-repeat{display:grid;grid-template-columns:1.5fr .8fr 1fr;gap:10px;margin-top:9px;padding:12px;border:1px solid #e3e8ef;border-radius:11px;background:#fbfcfe}.tt-appt-custom-repeat>div{display:grid;gap:6px}.tt-appt-custom-repeat label{font-size:11.5px;font-weight:750;color:#566176}.tt-appt-custom-rhythm{display:grid;grid-template-columns:auto 74px minmax(120px,1fr);align-items:center;gap:7px}.tt-appt-custom-rhythm span{font-size:12px;color:#6d7788}@media(max-width:800px){.tt-appt-custom-repeat{grid-template-columns:1fr}.tt-appt-custom-rhythm{grid-template-columns:auto 70px 1fr}}\n'''
        module.write(css_rel, css)


def patch_detail(module) -> None:
    rel = "templates/rebuild/appointment_detail.html"
    text = module.read(rel)
    old = '''{% if event.recurrence_series %}<div><span>Wiederholung</span><strong>{{ event.get_recurrence_rule_display }} · Termin {{ event.recurrence_index|add:"1" }}</strong></div>{% endif %}'''
    new = '''{% if event.recurrence_series %}<div><span>Wiederholung</span><strong>{% if event.recurrence_rule == 'custom' %}Alle {{ event.recurrence_interval }} {{ event.get_recurrence_unit_display }}{% if event.recurrence_until %} · bis {{ event.recurrence_until|date:'d.m.Y' }}{% endif %}{% else %}{{ event.get_recurrence_rule_display }}{% endif %} · Termin {{ event.recurrence_index|add:"1" }}</strong></div>{% endif %}'''
    text = _replace_once(text, old, new, "custom recurrence detail summary")
    module.write(rel, text)


def install_tests(module) -> None:
    runtime_rel = "tests/test_tooltime_phase19_custom_recurrence.py"
    runtime = r'''from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import CalendarEvent, Customer, Organization, UserProfile


class ToolTimePhase19CustomRecurrenceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI phase19")
        self.user = User.objects.create_user("phase19-office", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="phase19-office", password="safe-test-password"))
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P19-1",
            type="business",
            company="Custom Serie Phase19",
            street="Rhythmusweg 19",
            postal_code="60319",
            city="Frankfurt",
        )

    def _payload(self, title, start, **extra):
        form = rebuild_views.AppointmentForm(organization=self.org)
        data = {
            "title": title,
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": (start + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "customer_filter": str(self.customer.pk),
            "repeat_rule": "custom",
            "repeat_count": "3",
            "repeat_interval": "2",
            "repeat_unit": "week",
            "repeat_end_mode": "count",
            "repeat_until": "",
        }
        data.update(extra)
        for name, field in form.fields.items():
            if name in data or not field.required:
                continue
            choices = list(getattr(field, "choices", []) or [])
            usable = [value for value, _label in choices if str(value) != ""]
            data[name] = str(usable[0]) if usable else "Test"
        return data

    def test_custom_every_two_weeks_by_count(self):
        start = timezone.make_aware(datetime(2026, 8, 21, 10, 0), timezone.get_current_timezone())
        response = self.client.post(reverse("next-appointment-create"), self._payload("Alle zwei Wochen custom", start))
        self.assertEqual(response.status_code, 302)
        events = list(CalendarEvent.objects.filter(title="Alle zwei Wochen custom").order_by("recurrence_index"))
        self.assertEqual([timezone.localtime(event.starts_at).date().isoformat() for event in events], [
            "2026-08-21", "2026-09-04", "2026-09-18",
        ])
        self.assertEqual({event.recurrence_rule for event in events}, {"custom"})
        self.assertEqual({event.recurrence_interval for event in events}, {2})
        self.assertEqual({event.recurrence_unit for event in events}, {"week"})

    def test_custom_daily_until_date_is_inclusive(self):
        start = timezone.make_aware(datetime(2026, 8, 21, 10, 0), timezone.get_current_timezone())
        payload = self._payload(
            "Bis Datum custom",
            start,
            repeat_interval="1",
            repeat_unit="day",
            repeat_end_mode="date",
            repeat_until="2026-08-24",
        )
        response = self.client.post(reverse("next-appointment-create"), payload)
        self.assertEqual(response.status_code, 302)
        events = list(CalendarEvent.objects.filter(title="Bis Datum custom").order_by("recurrence_index"))
        self.assertEqual([timezone.localtime(event.starts_at).date().isoformat() for event in events], [
            "2026-08-21", "2026-08-22", "2026-08-23", "2026-08-24",
        ])
        self.assertEqual(events[0].recurrence_until.isoformat(), "2026-08-24")

    def test_custom_weekday_interval_skips_weekends(self):
        start = timezone.make_aware(datetime(2026, 8, 21, 10, 0), timezone.get_current_timezone())
        payload = self._payload(
            "Werktag custom",
            start,
            repeat_interval="2",
            repeat_unit="weekday",
            repeat_count="3",
        )
        response = self.client.post(reverse("next-appointment-create"), payload)
        self.assertEqual(response.status_code, 302)
        events = list(CalendarEvent.objects.filter(title="Werktag custom").order_by("recurrence_index"))
        self.assertEqual([timezone.localtime(event.starts_at).date().isoformat() for event in events], [
            "2026-08-21", "2026-08-25", "2026-08-27",
        ])

    def test_form_exposes_custom_rhythm_and_end_modes(self):
        response = self.client.get(reverse("next-appointment-create"))
        self.assertEqual(response.status_code, 200)
        for marker in ("Benutzerdefiniert", "Rhythmus", "Serie endet", "Nach Anzahl", "An einem Datum", "Enddatum"):
            self.assertContains(response, marker)
'''
    module.write(runtime_rel, runtime)
    compile(runtime, str(ROOT / runtime_rel), "exec")

    contract_rel = "tests/test_tooltime_phase19_custom_recurrence_contract.py"
    contract = r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase19CustomRecurrenceContractTests(SimpleTestCase):
    def test_custom_recurrence_is_persistent_and_linear(self):
        model = (ROOT / "erp/models.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0022_calendar_event_custom_recurrence.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        form = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        for marker in ("recurrence_interval", "recurrence_unit", "recurrence_until", '("custom", "Benutzerdefiniert")'):
            self.assertIn(marker, model)
        self.assertIn('(\"erp\", \"0021_calendar_event_recurrence\")', migration)
        for marker in (
            "_appointment_recurrence_indices",
            'rule == "custom"',
            "repeat_interval",
            "repeat_unit",
            "repeat_until",
            "dt.date.fromisoformat",
        ):
            self.assertIn(marker, views)
        for marker in ('value="custom"', 'name="repeat_interval"', 'name="repeat_unit"', 'name="repeat_end_mode"', 'name="repeat_until"'):
            self.assertIn(marker, form)
'''
    module.write(contract_rel, contract)
    compile(contract, str(ROOT / contract_rel), "exec")


def run(module) -> None:
    patch_model(module)
    install_migration(module)
    patch_backend(module)
    patch_template(module)
    patch_detail(module)
    install_tests(module)

    model = module.read("erp/models.py")
    migration = module.read(MIGRATION_REL)
    views = module.read("erp/rebuild_views.py")
    form = module.read("templates/rebuild/appointment_form.html")
    for marker in ("recurrence_interval", "recurrence_unit", "recurrence_until", '("custom", "Benutzerdefiniert")'):
        if marker not in model:
            raise RuntimeError(f"Phase 19 model guard missing: {marker}")
    for marker in ('("erp", "0021_calendar_event_recurrence")', "recurrence_interval", "recurrence_until"):
        if marker not in migration:
            raise RuntimeError(f"Phase 19 migration guard missing: {marker}")
    for marker in ("_appointment_recurrence_indices", 'rule == "custom"', "repeat_interval", "repeat_until"):
        if marker not in views:
            raise RuntimeError(f"Phase 19 backend guard missing: {marker}")
    for marker in ("Benutzerdefiniert", "Rhythmus", "Serie endet", "Enddatum"):
        if marker not in form:
            raise RuntimeError(f"Phase 19 form guard missing: {marker}")
    print(f"{MARKER}: custom recurrence intervals now support arbitrary day/weekday/week/month/year cadence and either occurrence-count or inclusive end-date termination with persistent series metadata.")
