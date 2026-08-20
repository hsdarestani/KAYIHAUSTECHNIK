from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 11 APPOINTMENT VIEWS 2026-08-21"
CSS_REL = "static/css/tooltime-phase11-appointments.css"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 11 appointment-view anchor missing: {label}")
    return text.replace(old, new, 1)


def patch_backend(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    old = '''@login_required
def appointment_list(request):
    org = _org(request)
    start = request.GET.get("start")
    events = m.CalendarEvent.objects.filter(organization=org).select_related("project", "project__customer").prefetch_related("attendees")
    if start:
        try:
            start_date = timezone.datetime.strptime(start, "%Y-%m-%d").date()
        except ValueError:
            start_date = timezone.localdate()
    else:
        start_date = timezone.localdate()
    week_start = start_date - timedelta(days=start_date.weekday())
    week_end = week_start + timedelta(days=7)
    aware_start = timezone.make_aware(timezone.datetime.combine(week_start, timezone.datetime.min.time()))
    aware_end = timezone.make_aware(timezone.datetime.combine(week_end, timezone.datetime.min.time()))
    events = events.filter(starts_at__gte=aware_start, starts_at__lt=aware_end).order_by("starts_at")
    days = []
    for offset in range(7):
        date = week_start + timedelta(days=offset)
        days.append({"date": date, "events": [event for event in events if timezone.localtime(event.starts_at).date() == date]})
    return render(request, "rebuild/appointments.html", {"days": days, "week_start": week_start, "prev": week_start - timedelta(days=7), "next": week_start + timedelta(days=7)})
'''
    new = '''@login_required
def appointment_list(request):
    org = _org(request)
    view_mode = (request.GET.get("view") or "week").strip().lower()
    if view_mode not in {"week", "list"}:
        view_mode = "week"

    start = (request.GET.get("start") or "").strip()
    query = (request.GET.get("q") or "").strip()
    employee_id = (request.GET.get("employee") or "").strip()
    project_id = (request.GET.get("project") or "").strip()
    customer_id = (request.GET.get("customer") or "").strip()

    if start:
        try:
            start_date = timezone.datetime.strptime(start, "%Y-%m-%d").date()
        except ValueError:
            start_date = timezone.localdate()
    else:
        start_date = timezone.localdate()

    week_start = start_date - timedelta(days=start_date.weekday())
    week_end = week_start + timedelta(days=7)
    aware_start = timezone.make_aware(timezone.datetime.combine(week_start, timezone.datetime.min.time()))
    aware_end = timezone.make_aware(timezone.datetime.combine(week_end, timezone.datetime.min.time()))

    events = (
        m.CalendarEvent.objects.filter(organization=org)
        .select_related("project", "project__customer", "project__object_location")
        .prefetch_related("attendees")
    )
    if query:
        events = events.filter(
            Q(title__icontains=query)
            | Q(location__icontains=query)
            | Q(project__number__icontains=query)
            | Q(project__title__icontains=query)
            | Q(project__customer__company__icontains=query)
            | Q(project__customer__first_name__icontains=query)
            | Q(project__customer__last_name__icontains=query)
        )
    if employee_id:
        events = events.filter(attendees__pk=employee_id)
    if project_id:
        events = events.filter(project_id=project_id)
    if customer_id:
        events = events.filter(project__customer_id=customer_id)

    events = list(
        events.filter(starts_at__gte=aware_start, starts_at__lt=aware_end)
        .distinct()
        .order_by("starts_at", "pk")
    )
    days = []
    today = timezone.localdate()
    for offset in range(7):
        date = week_start + timedelta(days=offset)
        day_events = [event for event in events if timezone.localtime(event.starts_at).date() == date]
        days.append({"date": date, "events": day_events, "is_today": date == today})

    employees = m.Employee.objects.filter(organization=org, active=True).order_by("last_name", "first_name")
    projects = m.Project.objects.filter(organization=org, archived=False).select_related("customer").order_by("-updated_at")[:250]
    customers = m.Customer.objects.filter(organization=org, active=True).order_by("company", "last_name", "first_name")[:250]
    assigned_count = sum(1 for event in events if event.project_id)

    return render(request, "rebuild/appointments.html", {
        "days": days,
        "events": events,
        "view_mode": view_mode,
        "week_start": week_start,
        "week_end_display": week_end - timedelta(days=1),
        "prev": week_start - timedelta(days=7),
        "next": week_start + timedelta(days=7),
        "today": today,
        "query": query,
        "employee_id": employee_id,
        "project_id": project_id,
        "customer_id": customer_id,
        "employees": employees,
        "projects": projects,
        "customers": customers,
        "event_count": len(events),
        "assigned_count": assigned_count,
        "internal_count": len(events) - assigned_count,
    })
'''
    text = _replace_once(text, old, new, "appointment_list backend")
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def install_template(module) -> None:
    module.write("templates/rebuild/appointments.html", r'''{% extends 'rebuild/base.html' %}
{% block title %}Termine · A+Bau{% endblock %}
{% block content %}
<div class="tt-appt-overview" data-appointment-overview data-view="{{ view_mode }}">
  <header class="tt-appt-overview-head">
    <div>
      <div class="nx-kicker">Einsatzplanung</div>
      <h1>Termine</h1>
      <p>{{ week_start|date:'d.m.Y' }} – {{ week_end_display|date:'d.m.Y' }} · {{ event_count }} Termin{{ event_count|pluralize:'e' }}</p>
    </div>
    <div class="tt-appt-overview-actions">
      <a class="nx-btn" href="?view={{ view_mode }}&start={{ today|date:'Y-m-d' }}{% if query %}&q={{ query|urlencode }}{% endif %}{% if employee_id %}&employee={{ employee_id }}{% endif %}{% if project_id %}&project={{ project_id }}{% endif %}{% if customer_id %}&customer={{ customer_id }}{% endif %}">Heute</a>
      <div class="tt-appt-period-nav" aria-label="Wochennavigation">
        <a class="nx-btn" href="?view={{ view_mode }}&start={{ prev|date:'Y-m-d' }}{% if query %}&q={{ query|urlencode }}{% endif %}{% if employee_id %}&employee={{ employee_id }}{% endif %}{% if project_id %}&project={{ project_id }}{% endif %}{% if customer_id %}&customer={{ customer_id }}{% endif %}" aria-label="Vorige Woche">←</a>
        <strong>KW {{ week_start|date:'W' }}</strong>
        <a class="nx-btn" href="?view={{ view_mode }}&start={{ next|date:'Y-m-d' }}{% if query %}&q={{ query|urlencode }}{% endif %}{% if employee_id %}&employee={{ employee_id }}{% endif %}{% if project_id %}&project={{ project_id }}{% endif %}{% if customer_id %}&customer={{ customer_id }}{% endif %}" aria-label="Nächste Woche">→</a>
      </div>
      <a class="nx-btn nx-btn-primary" href="{% url 'next-appointment-create' %}">＋ Neuer Termin</a>
    </div>
  </header>

  <div class="tt-appt-viewbar">
    <nav class="tt-appt-viewtabs" aria-label="Terminansicht">
      <a class="{% if view_mode == 'week' %}is-active{% endif %}" href="?view=week&start={{ week_start|date:'Y-m-d' }}{% if query %}&q={{ query|urlencode }}{% endif %}{% if employee_id %}&employee={{ employee_id }}{% endif %}{% if project_id %}&project={{ project_id }}{% endif %}{% if customer_id %}&customer={{ customer_id }}{% endif %}">Kalender</a>
      <span class="is-disabled" aria-disabled="true" title="Kartenansicht wird erst mit persistierten Geodaten aktiviert">Karte</span>
      <a class="{% if view_mode == 'list' %}is-active{% endif %}" href="?view=list&start={{ week_start|date:'Y-m-d' }}{% if query %}&q={{ query|urlencode }}{% endif %}{% if employee_id %}&employee={{ employee_id }}{% endif %}{% if project_id %}&project={{ project_id }}{% endif %}{% if customer_id %}&customer={{ customer_id }}{% endif %}">Liste</a>
    </nav>
    <div class="tt-appt-stats" aria-label="Terminübersicht">
      <span><b>{{ event_count }}</b> gesamt</span>
      <span><b>{{ assigned_count }}</b> Projekt</span>
      <span><b>{{ internal_count }}</b> intern</span>
    </div>
  </div>

  <form class="tt-appt-filters" method="get" data-appointment-filters>
    <input type="hidden" name="view" value="{{ view_mode }}">
    <input type="hidden" name="start" value="{{ week_start|date:'Y-m-d' }}">
    <label class="tt-appt-filter-search"><span>Suche</span><input class="next-control" type="search" name="q" value="{{ query }}" placeholder="Termin, Projekt oder Kunde …"></label>
    <label><span>Mitarbeiter</span><select class="next-control" name="employee"><option value="">Alle</option>{% for employee in employees %}<option value="{{ employee.pk }}" {% if employee_id == employee.pk|stringformat:'s' %}selected{% endif %}>{{ employee.first_name }} {{ employee.last_name }}</option>{% endfor %}</select></label>
    <label><span>Projekt</span><select class="next-control" name="project"><option value="">Alle Projekte</option>{% for project in projects %}<option value="{{ project.pk }}" {% if project_id == project.pk|stringformat:'s' %}selected{% endif %}>{{ project.number }} · {{ project.title }}</option>{% endfor %}</select></label>
    <label><span>Kunde</span><select class="next-control" name="customer"><option value="">Alle Kunden</option>{% for customer in customers %}<option value="{{ customer.pk }}" {% if customer_id == customer.pk|stringformat:'s' %}selected{% endif %}>{{ customer.display_name }}</option>{% endfor %}</select></label>
    <button class="nx-btn nx-btn-primary" type="submit">Filtern</button>
    {% if query or employee_id or project_id or customer_id %}<a class="nx-btn" href="?view={{ view_mode }}&start={{ week_start|date:'Y-m-d' }}">Zurücksetzen</a>{% endif %}
  </form>

  {% if view_mode == 'week' %}
  <div class="tt-appt-week" data-calendar-view>
    {% for day in days %}
    <section class="tt-appt-day {% if day.is_today %}is-today{% endif %}">
      <header><span>{{ day.date|date:'D' }}</span><b>{{ day.date|date:'d' }}</b><small>{{ day.date|date:'m.Y' }}</small>{% if day.is_today %}<i>Heute</i>{% endif %}</header>
      <div class="tt-appt-day-events">
        {% for event in day.events %}
        <a class="tt-appt-event" href="{% url 'next-appointment-detail' event.pk %}" data-appointment-event>
          <time>{{ event.starts_at|date:'H:i' }} – {{ event.ends_at|date:'H:i' }}</time>
          <strong>{{ event.title }}</strong>
          {% if event.project %}<span>{{ event.project.number }} · {{ event.project.customer.display_name }}</span>{% else %}<span>Interner Termin</span>{% endif %}
          {% if event.location %}<small>⌖ {{ event.location }}</small>{% elif event.project and event.project.object_location %}<small>⌖ {{ event.project.object_location.city }}</small>{% endif %}
          {% with team=event.attendees.all %}{% if team %}<div class="tt-appt-team">{% for member in team|slice:':3' %}<i title="{{ member.first_name }} {{ member.last_name }}">{{ member.first_name|first }}{{ member.last_name|first }}</i>{% endfor %}{% if team|length > 3 %}<em>+{{ team|length|add:'-3' }}</em>{% endif %}</div>{% endif %}{% endwith %}
        </a>
        {% empty %}<div class="tt-appt-day-empty">Keine Termine</div>{% endfor %}
      </div>
    </section>
    {% endfor %}
  </div>
  {% else %}
  <div class="tt-appt-list" data-list-view>
    <div class="tt-appt-list-head"><span>Zeit</span><span>Termin</span><span>Kunde / Projekt</span><span>Team</span><span></span></div>
    {% for event in events %}
    <a class="tt-appt-list-row" href="{% url 'next-appointment-detail' event.pk %}" data-appointment-row>
      <div><time>{{ event.starts_at|date:'D, d.m.' }}</time><strong>{{ event.starts_at|date:'H:i' }} – {{ event.ends_at|date:'H:i' }}</strong></div>
      <div><strong>{{ event.title }}</strong><small>{% if event.location %}⌖ {{ event.location }}{% else %}Keine separate Adresse{% endif %}</small></div>
      <div>{% if event.project %}<strong>{{ event.project.customer.display_name }}</strong><small>{{ event.project.number }} · {{ event.project.title }}</small>{% else %}<strong>Intern</strong><small>Ohne Projekt</small>{% endif %}</div>
      <div class="tt-appt-list-team">{% for member in event.attendees.all %}<span>{{ member.first_name }} {{ member.last_name }}</span>{% empty %}<small>Noch niemand zugewiesen</small>{% endfor %}</div>
      <b class="tt-appt-list-arrow">→</b>
    </a>
    {% empty %}<div class="tt-appt-list-empty"><span>◫</span><strong>Keine Termine in dieser Woche</strong><p>Filter ändern oder einen neuen Termin anlegen.</p><a class="nx-btn nx-btn-primary" href="{% url 'next-appointment-create' %}">＋ Neuer Termin</a></div>{% endfor %}
  </div>
  {% endif %}
</div>
{% endblock %}
''')


def install_css(module) -> None:
    module.write(CSS_REL, r'''/* A+BAU TOOLTIME PHASE 11 APPOINTMENT VIEWS 2026-08-21 */
.tt-appt-overview{max-width:1500px;margin:0 auto;color:#172033}.tt-appt-overview-head{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:20px}.tt-appt-overview-head h1{margin:3px 0 3px;font-size:28px;letter-spacing:-.03em}.tt-appt-overview-head p{margin:0;color:#7b8493;font-size:13px}.tt-appt-overview-actions{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.tt-appt-period-nav{display:flex;align-items:center;gap:7px;padding:4px;border:1px solid #e3e7ed;border-radius:12px;background:#fff}.tt-appt-period-nav .nx-btn{min-width:34px;padding:7px 9px;border:0!important}.tt-appt-period-nav strong{min-width:52px;text-align:center;font-size:12px}.tt-appt-viewbar{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:14px;padding:0 2px}.tt-appt-viewtabs{display:flex;align-items:center;gap:4px;padding:4px;border:1px solid #e3e7ed;border-radius:12px;background:#fff}.tt-appt-viewtabs a,.tt-appt-viewtabs span{padding:8px 13px;border-radius:8px;color:#687486;text-decoration:none;font-size:12px;font-weight:700}.tt-appt-viewtabs .is-active{background:#edf4ff;color:#2768c7}.tt-appt-viewtabs .is-disabled{opacity:.45;cursor:not-allowed}.tt-appt-stats{display:flex;gap:8px;flex-wrap:wrap}.tt-appt-stats span{padding:7px 10px;border:1px solid #e7eaf0;border-radius:999px;background:#fff;color:#7d8795;font-size:11px}.tt-appt-stats b{color:#253047}.tt-appt-filters{display:grid;grid-template-columns:minmax(210px,1.4fr) repeat(3,minmax(150px,1fr)) auto auto;gap:10px;align-items:end;margin-bottom:18px;padding:14px;border:1px solid #e3e7ed;border-radius:14px;background:#fff}.tt-appt-filters label{display:grid;gap:5px;min-width:0}.tt-appt-filters label>span{font-size:10.5px;font-weight:750;color:#727d8d}.tt-appt-filters .next-control{min-height:42px;border-radius:9px}.tt-appt-week{display:grid;grid-template-columns:repeat(7,minmax(145px,1fr));gap:8px;overflow-x:auto;padding-bottom:8px}.tt-appt-day{min-height:510px;border:1px solid #e3e7ed;border-radius:14px;background:#f9fafc;overflow:hidden}.tt-appt-day>header{position:relative;display:grid;grid-template-columns:1fr auto;align-items:center;gap:0 7px;padding:12px 12px 10px;border-bottom:1px solid #e8ebf0;background:#fff}.tt-appt-day>header span{font-size:11px;font-weight:750;color:#7a8493}.tt-appt-day>header b{grid-row:1/3;grid-column:2;font-size:22px}.tt-appt-day>header small{font-size:10px;color:#9aa2ae}.tt-appt-day>header i{position:absolute;right:9px;bottom:-9px;padding:2px 6px;border-radius:999px;background:#3478df;color:#fff;font-size:8px;font-style:normal}.tt-appt-day.is-today{border-color:#b8d1f5}.tt-appt-day-events{display:grid;gap:8px;padding:10px}.tt-appt-event{position:relative;display:grid;gap:4px;padding:11px;border:1px solid #e0e5ec;border-left:3px solid #4785de;border-radius:10px;background:#fff;color:#253047;text-decoration:none;box-shadow:0 2px 8px rgba(30,42,60,.03)}.tt-appt-event:hover{border-color:#b9c9df;box-shadow:0 7px 18px rgba(30,42,60,.08)}.tt-appt-event time{font-size:10px;font-weight:750;color:#4f74a7}.tt-appt-event strong{font-size:12.5px;line-height:1.25}.tt-appt-event span,.tt-appt-event small{color:#758091;font-size:10.5px;line-height:1.3}.tt-appt-team{display:flex;align-items:center;margin-top:3px}.tt-appt-team i,.tt-appt-team em{display:grid;place-items:center;width:24px;height:24px;margin-right:-5px;border:2px solid #fff;border-radius:50%;background:#edf1f6;color:#4e5c70;font-size:8px;font-weight:800;font-style:normal}.tt-appt-team em{background:#dfe8f5}.tt-appt-day-empty{display:grid;place-items:center;min-height:72px;color:#9aa2ae;font-size:10px}.tt-appt-list{border:1px solid #e3e7ed;border-radius:14px;background:#fff;overflow:hidden}.tt-appt-list-head,.tt-appt-list-row{display:grid;grid-template-columns:150px minmax(220px,1.2fr) minmax(230px,1fr) minmax(180px,.8fr) 28px;gap:16px;align-items:center}.tt-appt-list-head{padding:10px 16px;border-bottom:1px solid #e8ebf0;background:#f8fafc;color:#8a93a1;font-size:10px;font-weight:750;text-transform:uppercase;letter-spacing:.04em}.tt-appt-list-row{padding:14px 16px;border-bottom:1px solid #edf0f4;color:#263146;text-decoration:none}.tt-appt-list-row:last-child{border-bottom:0}.tt-appt-list-row:hover{background:#fbfcfe}.tt-appt-list-row>div{display:grid;gap:3px;min-width:0}.tt-appt-list-row time,.tt-appt-list-row small{color:#7f8997;font-size:10.5px}.tt-appt-list-row strong{font-size:12px;overflow:hidden;text-overflow:ellipsis}.tt-appt-list-team{display:flex!important;flex-wrap:wrap;gap:4px}.tt-appt-list-team span{padding:3px 6px;border-radius:999px;background:#f0f3f7;color:#566477;font-size:9.5px}.tt-appt-list-arrow{color:#91a0b3;font-size:16px}.tt-appt-list-empty{display:grid;place-items:center;min-height:310px;padding:34px;text-align:center}.tt-appt-list-empty>span{font-size:30px;color:#9ba5b4}.tt-appt-list-empty strong{margin-top:8px}.tt-appt-list-empty p{margin:5px 0 14px;color:#828c9a;font-size:12px}@media(max-width:1180px){.tt-appt-overview-head{display:grid}.tt-appt-filters{grid-template-columns:repeat(2,minmax(0,1fr)) auto}.tt-appt-filter-search{grid-column:1/-1}.tt-appt-list-head,.tt-appt-list-row{grid-template-columns:125px minmax(200px,1fr) minmax(210px,1fr) 28px}.tt-appt-list-head span:nth-child(4),.tt-appt-list-row>div:nth-child(4){display:none}}@media(max-width:760px){.tt-appt-overview-head h1{font-size:24px}.tt-appt-overview-actions{width:100%}.tt-appt-overview-actions>.nx-btn-primary{margin-left:auto}.tt-appt-viewbar{align-items:flex-start;flex-direction:column}.tt-appt-stats{display:none}.tt-appt-filters{grid-template-columns:1fr 1fr;padding:12px}.tt-appt-filter-search{grid-column:1/-1}.tt-appt-week{grid-template-columns:repeat(7,82vw);scroll-snap-type:x mandatory}.tt-appt-day{min-height:380px;scroll-snap-align:start}.tt-appt-list-head{display:none}.tt-appt-list-row{grid-template-columns:92px 1fr 24px;gap:10px}.tt-appt-list-row>div:nth-child(3),.tt-appt-list-row>div:nth-child(4){display:none}}@media(max-width:520px){.tt-appt-filters{grid-template-columns:1fr}.tt-appt-filter-search{grid-column:auto}.tt-appt-period-nav strong{display:none}.tt-appt-viewtabs{width:100%}.tt-appt-viewtabs a,.tt-appt-viewtabs span{flex:1;text-align:center}.tt-appt-overview-actions>.nx-btn:first-child{display:none}}
''')

    base_rel = "templates/rebuild/base.html"
    base = module.read(base_rel)
    css_tag = "  <link rel=\"stylesheet\" href=\"{% static 'css/tooltime-phase11-appointments.css' %}?v=20260821-1\">\n"
    if "tooltime-phase11-appointments.css" not in base:
        if "</head>" not in base:
            raise RuntimeError("Phase 11 base head anchor missing")
        base = base.replace("</head>", css_tag + "</head>", 1)
    module.write(base_rel, base)


def install_tests(module) -> None:
    module.write("tests/test_tooltime_phase11_appointment_views.py", r'''from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import CalendarEvent, Organization, UserProfile


class ToolTimePhase11AppointmentViewTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI appointment phase11")
        self.other_org = Organization.objects.create(name="KAYI appointment phase11 other")
        self.user = User.objects.create_user("appointment-phase11-admin", password="safe-test-password")
        self.user.profile.organization = self.org
        self.user.profile.role = UserProfile.Role.ADMIN
        self.user.profile.save()
        self.client = Client()
        self.assertTrue(self.client.login(username="appointment-phase11-admin", password="safe-test-password"))
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(hours=2)
        self.event = CalendarEvent.objects.create(
            organization=self.org,
            title="Wartung Wärmepumpe",
            location="Frankfurt",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            created_by=self.user,
        )
        CalendarEvent.objects.create(
            organization=self.other_org,
            title="Fremder Mandant Termin",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
        )
        self.start = timezone.localtime(self.event.starts_at).date().isoformat()

    def test_calendar_and_list_are_distinct_real_views(self):
        calendar = self.client.get(reverse("next-appointments"), {"view": "week", "start": self.start})
        self.assertEqual(calendar.status_code, 200)
        self.assertContains(calendar, "data-calendar-view")
        self.assertContains(calendar, "Wartung Wärmepumpe")
        self.assertNotContains(calendar, "data-list-view")

        listing = self.client.get(reverse("next-appointments"), {"view": "list", "start": self.start})
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, "data-list-view")
        self.assertContains(listing, "Wartung Wärmepumpe")
        self.assertNotContains(listing, "data-calendar-view")

    def test_search_is_organization_scoped(self):
        own = self.client.get(reverse("next-appointments"), {"view": "list", "start": self.start, "q": "Wärmepumpe"})
        self.assertContains(own, "Wartung Wärmepumpe")
        foreign = self.client.get(reverse("next-appointments"), {"view": "list", "start": self.start, "q": "Fremder Mandant"})
        self.assertNotContains(foreign, "Fremder Mandant Termin")
        self.assertContains(foreign, "Keine Termine in dieser Woche")

    def test_invalid_view_falls_back_to_calendar(self):
        response = self.client.get(reverse("next-appointments"), {"view": "unknown", "start": self.start})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-view="week"')
        self.assertContains(response, "data-calendar-view")
''')
    module.write("tests/test_tooltime_phase11_appointment_template.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase11AppointmentTemplateTests(SimpleTestCase):
    def test_overview_has_tooltime_navigation_filters_and_responsive_views(self):
        template = (ROOT / "templates/rebuild/appointments.html").read_text(encoding="utf-8")
        css = (ROOT / "static/css/tooltime-phase11-appointments.css").read_text(encoding="utf-8")
        for marker in (
            "Kalender", "Karte", "Liste", "Heute", "Wochennavigation", "data-appointment-filters",
            "Mitarbeiter", "Projekt", "Kunde", "data-calendar-view", "data-list-view",
        ):
            self.assertIn(marker, template)
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn("scroll-snap-type", css)
''')
    for rel in ("tests/test_tooltime_phase11_appointment_views.py", "tests/test_tooltime_phase11_appointment_template.py"):
        compile(module.read(rel), str(ROOT / rel), "exec")


def guard(module) -> None:
    views = module.read("erp/rebuild_views.py")
    template = module.read("templates/rebuild/appointments.html")
    base = module.read("templates/rebuild/base.html")
    css = module.read(CSS_REL)
    for marker in ("view_mode", "employee_id", "customer_id", "assigned_count", "week_end_display"):
        if marker not in views:
            raise RuntimeError(f"Phase 11 appointment backend marker missing: {marker}")
    for marker in ("data-appointment-overview", "data-calendar-view", "data-list-view", "data-appointment-filters"):
        if marker not in template:
            raise RuntimeError(f"Phase 11 appointment template marker missing: {marker}")
    if "tooltime-phase11-appointments.css" not in base or MARKER not in css:
        raise RuntimeError("Phase 11 appointment visual layer missing")


def run(module) -> None:
    patch_backend(module)
    install_template(module)
    install_css(module)
    install_tests(module)
    guard(module)
    print(f"{MARKER}: real calendar/list modes, scoped filters, week navigation and responsive planning UI installed.")
