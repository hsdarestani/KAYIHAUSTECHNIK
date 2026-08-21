from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 16 APPOINTMENT RECURRENCE 2026-08-21"
MIGRATION_REL = "erp/migrations/0021_calendar_event_recurrence.py"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 16 recurrence anchor missing: {label}")
    return text.replace(old, new, 1)


def _function_block(text: str, start_marker: str, end_markers: tuple[str, ...], label: str) -> tuple[int, int, str]:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Phase 16 function start missing: {label}")
    candidates = [text.find(marker, start + len(start_marker)) for marker in end_markers]
    candidates = [value for value in candidates if value >= 0]
    if not candidates:
        raise RuntimeError(f"Phase 16 function end missing: {label}")
    end = min(candidates)
    return start, end, text[start:end]


def patch_model(module) -> None:
    rel = "erp/models.py"
    text = module.read(rel)
    class_start = text.find("class CalendarEvent(")
    if class_start < 0:
        raise RuntimeError("Phase 16 CalendarEvent model boundary missing")
    class_end = text.find("\n\nclass ", class_start + 1)
    if class_end < 0:
        class_end = len(text)
    block = text[class_start:class_end]
    if "recurrence_series = models.UUIDField" not in block:
        anchor = "\n    project = models.ForeignKey("
        pos = block.find(anchor)
        if pos < 0:
            raise RuntimeError("Phase 16 CalendarEvent project field anchor missing")
        fields = '''
    recurrence_series = models.UUIDField(null=True, blank=True, db_index=True)
    recurrence_rule = models.CharField(
        max_length=16,
        choices=[
            ("none", "Keine Wiederholung"),
            ("daily", "Täglich"),
            ("weekly", "Wöchentlich"),
            ("monthly", "Monatlich"),
        ],
        default="none",
    )
    recurrence_index = models.PositiveIntegerField(default=0)
'''
        block = block[:pos] + fields + block[pos:]
        text = text[:class_start] + block + text[class_end:]
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def install_migration(module) -> None:
    migration = '''from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("erp", "0020_calendar_event_customer"),
    ]

    operations = [
        migrations.AddField(
            model_name="calendarevent",
            name="recurrence_series",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="recurrence_rule",
            field=models.CharField(
                choices=[
                    ("none", "Keine Wiederholung"),
                    ("daily", "Täglich"),
                    ("weekly", "Wöchentlich"),
                    ("monthly", "Monatlich"),
                ],
                default="none",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="recurrence_index",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
'''
    module.write(MIGRATION_REL, migration)
    compile(migration, str(ROOT / MIGRATION_REL), "exec")


def patch_create_backend(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    if "import calendar as month_calendar" not in text:
        anchor = "import base64\n"
        if anchor not in text:
            raise RuntimeError("Phase 16 standard-library import anchor missing")
        text = text.replace(anchor, anchor + "import calendar as month_calendar\n", 1)
    if "import uuid\n" not in text:
        anchor = "import re\n"
        if anchor not in text:
            raise RuntimeError("Phase 16 uuid import anchor missing")
        text = text.replace(anchor, anchor + "import uuid\n", 1)

    helper_marker = "def _appointment_recurrence_request(request):"
    customer_helper = "def _appointment_customer_address(customer):"
    if helper_marker not in text:
        pos = text.find(customer_helper)
        if pos < 0:
            raise RuntimeError("Phase 16 appointment customer helper boundary missing")
        helper = '''def _appointment_recurrence_request(request):
    if request.method != "POST":
        return "none", 4
    rule = (request.POST.get("repeat_rule") or "none").strip().lower()
    if rule not in {"none", "daily", "weekly", "monthly"}:
        rule = "none"
    try:
        count = int(request.POST.get("repeat_count") or 4)
    except (TypeError, ValueError):
        count = 4
    count = max(2, min(count, 52)) if rule != "none" else 1
    return rule, count


def _appointment_shift_month(value, months):
    local_value = timezone.localtime(value)
    month_index = local_value.year * 12 + (local_value.month - 1) + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(local_value.day, month_calendar.monthrange(year, month)[1])
    return local_value.replace(year=year, month=month, day=day)


def _appointment_recurrence_shift(value, rule, index):
    if rule == "daily":
        return value + timedelta(days=index)
    if rule == "weekly":
        return value + timedelta(days=7 * index)
    if rule == "monthly":
        return _appointment_shift_month(value, index)
    return value


'''
        text = text[:pos] + helper + text[pos:]

    create_marker = '@login_required\n@require_http_methods(["GET", "POST"])\ndef appointment_create(request):\n'
    create_start, create_end, create = _function_block(
        text,
        create_marker,
        (
            '\n\n@login_required\n@require_http_methods(["GET", "POST"])\ndef appointment_edit(request, pk):\n',
            "\n\n@login_required\ndef appointment_detail(request, pk):\n",
        ),
        "appointment_create",
    )

    if "repeat_rule, repeat_count = _appointment_recurrence_request(request)" not in create:
        anchor = "    form = AppointmentForm(\n"
        if anchor not in create:
            raise RuntimeError("Phase 16 appointment form anchor missing")
        create = create.replace(
            anchor,
            "    repeat_rule, repeat_count = _appointment_recurrence_request(request)\n" + anchor,
            1,
        )

    save_anchor = '''        event.created_by = request.user
        event.customer = selected_customer
        if not event.location and event.customer_id:
            event.location = _appointment_customer_address(event.customer)
        event.save()
        form.save_m2m()
        messages.success(request, "Termin wurde geplant.")
'''
    save_replacement = '''        event.created_by = request.user
        event.customer = selected_customer
        if not event.location and event.customer_id:
            event.location = _appointment_customer_address(event.customer)
        series_id = uuid.uuid4() if repeat_rule != "none" and repeat_count > 1 else None
        event.recurrence_series = series_id
        event.recurrence_rule = repeat_rule
        event.recurrence_index = 0
        event.save()
        form.save_m2m()

        if series_id is not None:
            attendees = list(event.attendees.all())
            for occurrence_index in range(1, repeat_count):
                occurrence = m.CalendarEvent.objects.create(
                    organization=org,
                    customer=event.customer,
                    project=event.project,
                    title=event.title,
                    type=event.type,
                    starts_at=_appointment_recurrence_shift(event.starts_at, repeat_rule, occurrence_index),
                    ends_at=_appointment_recurrence_shift(event.ends_at, repeat_rule, occurrence_index),
                    all_day=event.all_day,
                    location=event.location,
                    notes=event.notes,
                    created_by=event.created_by,
                    recurrence_series=series_id,
                    recurrence_rule=repeat_rule,
                    recurrence_index=occurrence_index,
                )
                if attendees:
                    occurrence.attendees.set(attendees)
            messages.success(request, f"Terminserie mit {repeat_count} Terminen wurde geplant.")
        else:
            messages.success(request, "Termin wurde geplant.")
'''
    if save_replacement not in create:
        if save_anchor not in create:
            raise RuntimeError("Phase 16 create-save anchor missing")
        create = create.replace(save_anchor, save_replacement, 1)

    render_anchor = '''        "selected_project_id": selected_project_id,
    })'''
    render_replacement = '''        "selected_project_id": selected_project_id,
        "selected_repeat_rule": repeat_rule,
        "repeat_count": repeat_count,
    })'''
    if render_replacement not in create:
        if render_anchor not in create:
            raise RuntimeError("Phase 16 create-render context anchor missing")
        create = create.replace(render_anchor, render_replacement, 1)

    text = text[:create_start] + create + text[create_end:]

    edit_marker = '@login_required\n@require_http_methods(["GET", "POST"])\ndef appointment_edit(request, pk):\n'
    edit_start, edit_end, edit = _function_block(
        text,
        edit_marker,
        ("\n\n@login_required\ndef appointment_detail(request, pk):\n",),
        "appointment_edit",
    )
    edit_anchor = '''        "selected_project_id": str(selected_project.pk) if selected_project is not None else "",
    })'''
    edit_replacement = '''        "selected_project_id": str(selected_project.pk) if selected_project is not None else "",
        "selected_repeat_rule": event.recurrence_rule,
        "repeat_count": 1,
    })'''
    if edit_replacement not in edit:
        if edit_anchor not in edit:
            raise RuntimeError("Phase 16 edit-render context anchor missing")
        edit = edit.replace(edit_anchor, edit_replacement, 1)
    text = text[:edit_start] + edit + text[edit_end:]

    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_form_template(module) -> None:
    rel = "templates/rebuild/appointment_form.html"
    text = module.read(rel)
    old = '<select class="next-control" id="appointment-repeat" name="repeat_rule"><option value="none">Wiederholt sich nicht</option></select>\n              <small>Serientermine werden erst angeboten, sobald sie persistent im Terminmodell abgebildet sind.</small>'
    new = '''<select class="next-control" id="appointment-repeat" name="repeat_rule" data-repeat-rule {% if mode == 'edit' %}disabled{% endif %}>
                <option value="none" {% if selected_repeat_rule == 'none' %}selected{% endif %}>Wiederholt sich nicht</option>
                <option value="daily" {% if selected_repeat_rule == 'daily' %}selected{% endif %}>Täglich</option>
                <option value="weekly" {% if selected_repeat_rule == 'weekly' %}selected{% endif %}>Wöchentlich</option>
                <option value="monthly" {% if selected_repeat_rule == 'monthly' %}selected{% endif %}>Monatlich</option>
              </select>
              <div class="tt-appt-repeat-count" data-repeat-count-row hidden>
                <label for="appointment-repeat-count">Anzahl Termine</label>
                <input class="next-control" id="appointment-repeat-count" name="repeat_count" type="number" min="2" max="52" value="{{ repeat_count|default:4 }}" data-repeat-count>
              </div>
              <small>{% if mode == 'edit' and event.recurrence_series %}Dieser Termin gehört zu einer Serie. Änderungen auf dieser Seite gelten nur für diesen einzelnen Termin.{% elif mode == 'edit' %}Wiederholung wird nur beim Erstellen einer Terminserie festgelegt.{% else %}Bei einer Wiederholung werden eigenständige, dauerhaft gespeicherte Termine erzeugt. Maximal 52 Termine pro Serie.{% endif %}</small>'''
    text = _replace_once(text, old, new, "recurrence controls")

    variable_anchor = "  const allDay = form.querySelector('input[name=\"all_day\"]');\n"
    variable_addition = "  const repeatRule = form.querySelector('[data-repeat-rule]');\n  const repeatCountRow = form.querySelector('[data-repeat-count-row]');\n  const repeatCount = form.querySelector('[data-repeat-count]');\n"
    if variable_addition not in text:
        if variable_anchor not in text:
            raise RuntimeError("Phase 16 recurrence JS variable anchor missing")
        text = text.replace(variable_anchor, variable_anchor + variable_addition, 1)

    listener_anchor = "  customer?.addEventListener('change', () => { filterProjects(); updateAddress(); });\n"
    listener_addition = '''  const updateRepeatControls = () => {
    if (!repeatCountRow || !repeatRule) return;
    const recurring = repeatRule.value !== 'none' && root.dataset.appointmentMode !== 'edit';
    repeatCountRow.hidden = !recurring;
    if (repeatCount) repeatCount.disabled = !recurring;
  };
  repeatRule?.addEventListener('change', updateRepeatControls);
'''
    if listener_addition not in text:
        if listener_anchor not in text:
            raise RuntimeError("Phase 16 recurrence JS listener anchor missing")
        text = text.replace(listener_anchor, listener_addition + listener_anchor, 1)

    init_anchor = "  filterCustomers();\n"
    if "  updateRepeatControls();\n" not in text:
        if init_anchor not in text:
            raise RuntimeError("Phase 16 recurrence JS init anchor missing")
        text = text.replace(init_anchor, "  updateRepeatControls();\n" + init_anchor, 1)

    module.write(rel, text)

    css_rel = "static/css/tooltime-phase10-appointments.css"
    css = module.read(css_rel)
    css_marker = "/* A+BAU TOOLTIME PHASE 16 RECURRENCE */"
    if css_marker not in css:
        css += '''\n/* A+BAU TOOLTIME PHASE 16 RECURRENCE */
.tt-appt-repeat-count{display:grid;grid-template-columns:1fr 120px;align-items:center;gap:10px;margin-top:6px;padding:10px 12px;border:1px solid #e7ebf0;border-radius:10px;background:#fafbfd}.tt-appt-repeat-count label{font-size:11.5px;font-weight:700;color:#667184}.tt-appt-repeat-count input{min-height:38px}@media(max-width:700px){.tt-appt-repeat-count{grid-template-columns:1fr 96px}}\n'''
        module.write(css_rel, css)


def patch_detail_template(module) -> None:
    rel = "templates/rebuild/appointment_detail.html"
    text = module.read(rel)
    anchor = '''      <div><span>Terminart</span><strong>{{ event.get_type_display }}</strong></div>
'''
    addition = '''      <div><span>Terminart</span><strong>{{ event.get_type_display }}</strong></div>
      {% if event.recurrence_series %}<div><span>Wiederholung</span><strong>{{ event.get_recurrence_rule_display }} · Termin {{ event.recurrence_index|add:"1" }}</strong></div>{% endif %}
'''
    if addition not in text:
        if anchor not in text:
            raise RuntimeError("Phase 16 detail recurrence anchor missing")
        text = text.replace(anchor, addition, 1)
    module.write(rel, text)


def install_tests(module) -> None:
    runtime_rel = "tests/test_tooltime_phase16_appointment_recurrence.py"
    runtime = r'''from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp import rebuild_views
from erp.models import CalendarEvent, Customer, Organization, UserProfile


class ToolTimePhase16AppointmentRecurrenceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI phase16")
        self.user = User.objects.create_user("phase16-office", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="phase16-office", password="safe-test-password"))
        self.customer = Customer.objects.create(
            organization=self.org,
            number="K-P16-1",
            type="business",
            company="Serienkunde",
            street="Serienweg 16",
            postal_code="60316",
            city="Frankfurt",
        )

    def _payload(self, title, start, *, rule="none", count=4):
        form = rebuild_views.AppointmentForm(organization=self.org)
        end = start + timedelta(hours=1)
        data = {
            "title": title,
            "starts_at": start.strftime("%Y-%m-%dT%H:%M"),
            "ends_at": end.strftime("%Y-%m-%dT%H:%M"),
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

    def test_daily_series_creates_persistent_occurrences_with_one_series_id(self):
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(days=1)
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload("Tägliche Serie", start, rule="daily", count=3),
        )
        self.assertEqual(response.status_code, 302)
        events = list(CalendarEvent.objects.filter(organization=self.org, title="Tägliche Serie").order_by("recurrence_index"))
        self.assertEqual(len(events), 3)
        self.assertIsNotNone(events[0].recurrence_series)
        self.assertEqual(len({event.recurrence_series for event in events}), 1)
        self.assertEqual([event.recurrence_index for event in events], [0, 1, 2])
        self.assertEqual({event.recurrence_rule for event in events}, {"daily"})
        self.assertEqual({event.customer_id for event in events}, {self.customer.pk})
        dates = [timezone.localtime(event.starts_at).date() for event in events]
        self.assertEqual((dates[1] - dates[0]).days, 1)
        self.assertEqual((dates[2] - dates[1]).days, 1)

    def test_monthly_series_clamps_end_of_month_without_date_drift(self):
        start = timezone.make_aware(datetime(2027, 1, 31, 10, 0), timezone.get_current_timezone())
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload("Monatsserie", start, rule="monthly", count=3),
        )
        self.assertEqual(response.status_code, 302)
        events = list(CalendarEvent.objects.filter(organization=self.org, title="Monatsserie").order_by("recurrence_index"))
        self.assertEqual(len(events), 3)
        dates = [timezone.localtime(event.starts_at).date().isoformat() for event in events]
        self.assertEqual(dates, ["2027-01-31", "2027-02-28", "2027-03-31"])

    def test_no_repeat_stays_single_persistent_event(self):
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(days=2)
        response = self.client.post(
            reverse("next-appointment-create"),
            self._payload("Einzeltermin", start, rule="none", count=12),
        )
        self.assertEqual(response.status_code, 302)
        event = CalendarEvent.objects.get(organization=self.org, title="Einzeltermin")
        self.assertEqual(event.recurrence_rule, "none")
        self.assertIsNone(event.recurrence_series)
        self.assertEqual(event.recurrence_index, 0)

    def test_create_form_exposes_real_recurrence_controls(self):
        response = self.client.get(reverse("next-appointment-create"))
        self.assertEqual(response.status_code, 200)
        for marker in ("Täglich", "Wöchentlich", "Monatlich", "Anzahl Termine", "max=\"52\""):
            self.assertContains(response, marker)
'''
    module.write(runtime_rel, runtime)
    compile(runtime, str(ROOT / runtime_rel), "exec")

    contract_rel = "tests/test_tooltime_phase16_appointment_recurrence_contract.py"
    contract = r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase16AppointmentRecurrenceContractTests(SimpleTestCase):
    def test_recurrence_is_persistent_and_migration_is_linear(self):
        model = (ROOT / "erp/models.py").read_text(encoding="utf-8")
        migration = (ROOT / "erp/migrations/0021_calendar_event_recurrence.py").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        for marker in ("recurrence_series = models.UUIDField", "recurrence_rule = models.CharField", "recurrence_index = models.PositiveIntegerField"):
            self.assertIn(marker, model)
        self.assertIn('(\"erp\", \"0020_calendar_event_customer\")', migration)
        for marker in ("_appointment_recurrence_request", "_appointment_recurrence_shift", "uuid.uuid4()", "occurrence.attendees.set(attendees)"):
            self.assertIn(marker, views)
        for marker in ('value="daily"', 'value="weekly"', 'value="monthly"', "data-repeat-count", "Maximal 52 Termine"):
            self.assertIn(marker, template)
'''
    module.write(contract_rel, contract)
    compile(contract, str(ROOT / contract_rel), "exec")


def run(module) -> None:
    patch_model(module)
    install_migration(module)
    patch_create_backend(module)
    patch_form_template(module)
    patch_detail_template(module)
    install_tests(module)

    model = module.read("erp/models.py")
    views = module.read("erp/rebuild_views.py")
    template = module.read("templates/rebuild/appointment_form.html")
    migration = module.read(MIGRATION_REL)
    for marker in ("recurrence_series", "recurrence_rule", "recurrence_index"):
        if marker not in model:
            raise RuntimeError(f"Phase 16 model guard missing: {marker}")
    for marker in ("_appointment_recurrence_request", "uuid.uuid4()", "Terminserie mit"):
        if marker not in views:
            raise RuntimeError(f"Phase 16 backend guard missing: {marker}")
    for marker in ("Täglich", "Wöchentlich", "Monatlich", "data-repeat-count"):
        if marker not in template:
            raise RuntimeError(f"Phase 16 template guard missing: {marker}")
    if '("erp", "0020_calendar_event_customer")' not in migration:
        raise RuntimeError("Phase 16 migration dependency is not linear after 0020")
    print(f"{MARKER}: persistent daily/weekly/monthly appointment series installed with bounded occurrence generation and end-of-month-safe scheduling.")
