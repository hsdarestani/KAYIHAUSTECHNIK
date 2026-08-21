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
    """Extend the existing multiview calendar instead of replacing it.

    calendar_views_upgrade.py already owns day/week/month/list navigation and the
    safe drag/drop move endpoint. Phase 11 only adds the ToolTime-style search
    and customer filter to that final implementation.
    """
    rel = "erp/rebuild_views.py"
    text = module.read(rel)

    text = _replace_once(
        text,
        '    employee_filter = (request.GET.get("employee") or "").strip()\n    project_filter = (request.GET.get("project") or "").strip()\n',
        '    employee_filter = (request.GET.get("employee") or "").strip()\n    project_filter = (request.GET.get("project") or "").strip()\n    query_filter = (request.GET.get("q") or "").strip()\n    customer_filter = (request.GET.get("customer") or "").strip()\n',
        "advanced calendar filter inputs",
    )

    filter_anchor = '''    if project_filter.isdigit():
        events = events.filter(project_id=int(project_filter))
    else:
        project_filter = ""
'''
    filter_replacement = filter_anchor + '''    if customer_filter.isdigit():
        events = events.filter(project__customer_id=int(customer_filter))
    else:
        customer_filter = ""
    if query_filter:
        events = events.filter(
            Q(title__icontains=query_filter)
            | Q(location__icontains=query_filter)
            | Q(project__number__icontains=query_filter)
            | Q(project__title__icontains=query_filter)
            | Q(project__customer__company__icontains=query_filter)
            | Q(project__customer__first_name__icontains=query_filter)
            | Q(project__customer__last_name__icontains=query_filter)
        ).distinct()
'''
    text = _replace_once(text, filter_anchor, filter_replacement, "advanced calendar scoped search")

    url_anchor = '''        if project_filter:
            params["project"] = project_filter
        return "?" + urlencode(params)
'''
    url_replacement = '''        if project_filter:
            params["project"] = project_filter
        if customer_filter:
            params["customer"] = customer_filter
        if query_filter:
            params["q"] = query_filter
        return "?" + urlencode(params)
'''
    text = _replace_once(text, url_anchor, url_replacement, "calendar URL filter preservation")

    queryset_anchor = '''    employees = m.Employee.objects.filter(organization=org, active=True).order_by("last_name", "first_name")
    projects = m.Project.objects.filter(organization=org, archived=False).select_related("customer").order_by("-updated_at")[:300]
    view_links = [
'''
    queryset_replacement = '''    employees = m.Employee.objects.filter(organization=org, active=True).order_by("last_name", "first_name")
    projects = m.Project.objects.filter(organization=org, archived=False).select_related("customer").order_by("-updated_at")[:300]
    customers = m.Customer.objects.filter(organization=org, active=True).order_by("company", "last_name", "first_name")[:300]
    view_links = [
'''
    text = _replace_once(text, queryset_anchor, queryset_replacement, "customer filter queryset")

    context_anchor = '''        "projects": projects,
        "employee_filter": employee_filter,
        "project_filter": project_filter,
        "reset_query": reset_query,
'''
    context_replacement = '''        "projects": projects,
        "customers": customers,
        "employee_filter": employee_filter,
        "project_filter": project_filter,
        "customer_filter": customer_filter,
        "query_filter": query_filter,
        "reset_query": reset_query,
'''
    text = _replace_once(text, context_anchor, context_replacement, "calendar filter context")

    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_template(module) -> None:
    rel = "templates/rebuild/appointments.html"
    text = module.read(rel)

    text = _replace_once(
        text,
        '<section class="nx-calendar-shell" data-calendar-view="{{ calendar_view }}" data-calendar-dispatch="{% if can_dispatch %}1{% else %}0{% endif %}">',
        '<section class="nx-calendar-shell tt-phase11-appointments" data-appointment-overview data-calendar-view="{{ calendar_view }}" data-calendar-dispatch="{% if can_dispatch %}1{% else %}0{% endif %}">',
        "appointment overview root",
    )

    old_filters = '''  <form class="nx-calendar-filters" method="get">
    <input type="hidden" name="view" value="{{ calendar_view }}">
    <input type="hidden" name="date" value="{{ anchor_date|date:'Y-m-d' }}">
    <label><span>Mitarbeiter</span><select class="nx-control" name="employee"><option value="">Alle Mitarbeiter</option>{% for employee in employees %}<option value="{{ employee.pk }}" {% if employee_filter == employee.pk|stringformat:'s' %}selected{% endif %}>{{ employee.first_name }} {{ employee.last_name }}</option>{% endfor %}</select></label>
    <label><span>Projekt</span><select class="nx-control" name="project"><option value="">Alle Projekte</option>{% for project in projects %}<option value="{{ project.pk }}" {% if project_filter == project.pk|stringformat:'s' %}selected{% endif %}>{{ project.number }} · {{ project.title }}</option>{% endfor %}</select></label>
    <div class="nx-calendar-filter-actions"><button class="nx-btn nx-btn-primary" type="submit">Filtern</button><a class="nx-btn nx-btn-ghost" href="{{ reset_query }}">Zurücksetzen</a></div>
  </form>
'''
    new_filters = '''  <form class="nx-calendar-filters tt-phase11-filters" method="get" data-appointment-filters>
    <input type="hidden" name="view" value="{{ calendar_view }}">
    <input type="hidden" name="date" value="{{ anchor_date|date:'Y-m-d' }}">
    <label class="tt-phase11-search"><span>Suche</span><input class="nx-control" type="search" name="q" value="{{ query_filter }}" placeholder="Termin, Projekt oder Kunde …" autocomplete="off"></label>
    <label><span>Mitarbeiter</span><select class="nx-control" name="employee"><option value="">Alle Mitarbeiter</option>{% for employee in employees %}<option value="{{ employee.pk }}" {% if employee_filter == employee.pk|stringformat:'s' %}selected{% endif %}>{{ employee.first_name }} {{ employee.last_name }}</option>{% endfor %}</select></label>
    <label><span>Projekt</span><select class="nx-control" name="project"><option value="">Alle Projekte</option>{% for project in projects %}<option value="{{ project.pk }}" {% if project_filter == project.pk|stringformat:'s' %}selected{% endif %}>{{ project.number }} · {{ project.title }}</option>{% endfor %}</select></label>
    <label><span>Kunde</span><select class="nx-control" name="customer"><option value="">Alle Kunden</option>{% for customer in customers %}<option value="{{ customer.pk }}" {% if customer_filter == customer.pk|stringformat:'s' %}selected{% endif %}>{{ customer.display_name }}</option>{% endfor %}</select></label>
    <div class="nx-calendar-filter-actions"><button class="nx-btn nx-btn-primary" type="submit">Filtern</button><a class="nx-btn nx-btn-ghost" href="{{ reset_query }}">Zurücksetzen</a></div>
  </form>
'''
    text = _replace_once(text, old_filters, new_filters, "ToolTime appointment filters")

    text = _replace_once(
        text,
        '<div class="nx-calendar-list">',
        '<div class="nx-calendar-list" data-list-view>',
        "real list view marker",
    )

    module.write(rel, text)


def install_css(module) -> None:
    module.write(CSS_REL, r'''/* A+BAU TOOLTIME PHASE 11 APPOINTMENT VIEWS 2026-08-21 */
.tt-phase11-appointments{max-width:1500px;margin-inline:auto}
.tt-phase11-filters{grid-template-columns:minmax(230px,1.35fr) minmax(160px,.85fr) minmax(210px,1.1fr) minmax(190px,1fr) auto}
.tt-phase11-filters .tt-phase11-search{min-width:0}
.tt-phase11-filters .tt-phase11-search input{width:100%}
.tt-phase11-filters .nx-calendar-filter-actions{white-space:nowrap}
.tt-phase11-appointments .nx-calendar-list[data-list-view]{box-shadow:0 6px 24px rgba(20,28,38,.035)}
@media(max-width:1180px){.tt-phase11-filters{grid-template-columns:repeat(2,minmax(0,1fr)) auto}.tt-phase11-filters .tt-phase11-search{grid-column:1/-1}}
@media(max-width:760px){.tt-phase11-filters{grid-template-columns:1fr 1fr}.tt-phase11-filters .tt-phase11-search{grid-column:1/-1}.tt-phase11-filters .nx-calendar-filter-actions{grid-column:1/-1}.tt-phase11-appointments .nx-calendar-views{max-width:100%;overflow-x:auto;scroll-snap-type:x proximity}.tt-phase11-appointments .nx-calendar-view-btn{scroll-snap-align:start;white-space:nowrap}}
@media(max-width:520px){.tt-phase11-filters{grid-template-columns:1fr}.tt-phase11-filters .tt-phase11-search,.tt-phase11-filters .nx-calendar-filter-actions{grid-column:auto}.tt-phase11-filters .nx-calendar-filter-actions{display:grid;grid-template-columns:1fr 1fr}}
''')

    base_rel = "templates/rebuild/base.html"
    base = module.read(base_rel)
    css_tag = "  <link rel=\"stylesheet\" href=\"{% static 'css/tooltime-phase11-appointments.css' %}?v=20260821-2\">\n"
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
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
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
        self.anchor = timezone.localtime(self.event.starts_at).date().isoformat()

    def test_existing_multiview_calendar_is_preserved(self):
        for view in ("day", "week", "month", "list"):
            response = self.client.get(reverse("next-appointments"), {"view": view, "date": self.anchor})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f'data-calendar-view="{view}"')
            self.assertContains(response, "Wartung Wärmepumpe")

    def test_search_is_organization_scoped(self):
        own = self.client.get(reverse("next-appointments"), {"view": "list", "date": self.anchor, "q": "Wärmepumpe"})
        self.assertContains(own, "Wartung Wärmepumpe")
        foreign = self.client.get(reverse("next-appointments"), {"view": "list", "date": self.anchor, "q": "Fremder Mandant"})
        self.assertNotContains(foreign, "Fremder Mandant Termin")

    def test_invalid_view_falls_back_to_week(self):
        response = self.client.get(reverse("next-appointments"), {"view": "unknown", "date": self.anchor})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-calendar-view="week"')
''')

    module.write("tests/test_tooltime_phase11_appointment_template.py", r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase11AppointmentTemplateTests(SimpleTestCase):
    def test_tooltime_filters_are_layered_over_advanced_calendar(self):
        template = (ROOT / "templates/rebuild/appointments.html").read_text(encoding="utf-8")
        backend = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        calendar_js = (ROOT / "static/js/kayi-calendar.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/tooltime-phase11-appointments.css").read_text(encoding="utf-8")

        for marker in (
            "data-appointment-overview", "data-appointment-filters", "data-list-view",
            'name="q"', 'name="customer"', "Tag", "Woche", "Monat", "Liste",
            "data-calendar-drop-date", "next-appointment-move",
        ):
            self.assertIn(marker, template)
        for marker in ("query_filter", "customer_filter", "allowed_views", '"day", "week", "month", "list"'):
            self.assertIn(marker, backend)
        self.assertIn("dragstart", calendar_js)
        self.assertIn("fetch(url", calendar_js)
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
    calendar_js = module.read("static/js/kayi-calendar.js")

    for marker in ("query_filter", "customer_filter", "allowed_views", "calendar_url", "appointment_move"):
        if marker not in views:
            raise RuntimeError(f"Phase 11 appointment backend marker missing: {marker}")
    for marker in ("data-appointment-overview", "data-appointment-filters", "data-list-view", "data-calendar-drop-date"):
        if marker not in template:
            raise RuntimeError(f"Phase 11 appointment template marker missing: {marker}")
    for marker in ("Tag", "Woche", "Monat", "Liste"):
        if marker not in template:
            raise RuntimeError(f"Phase 11 existing calendar view lost: {marker}")
    if "dragstart" not in calendar_js or "next-appointment-move" not in template:
        raise RuntimeError("Phase 11 must preserve safe calendar drag/drop")
    if "tooltime-phase11-appointments.css" not in base or MARKER not in css:
        raise RuntimeError("Phase 11 appointment visual layer missing")


def run(module) -> None:
    patch_backend(module)
    patch_template(module)
    install_css(module)
    install_tests(module)
    guard(module)
    print(f"{MARKER}: ToolTime search/customer filters layered over existing day/week/month/list calendar and drag/drop.")
