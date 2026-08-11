from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK = "KAYI CALENDAR MULTIVIEW 2026-08-11"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# --- backend: multiview calendar, filters and safe drag/drop move endpoint ---
views_path = "erp/rebuild_views.py"
views = read(views_path)

if "from urllib.parse import urlencode" not in views:
    anchor = "from pathlib import Path\n"
    if anchor not in views:
        raise RuntimeError("rebuild_views import anchor changed")
    views = views.replace(anchor, anchor + "from urllib.parse import urlencode\n", 1)

start_marker = "@login_required\ndef appointment_list(request):\n"
end_marker = "\n\n@login_required\n@require_http_methods([\"GET\", \"POST\"])\ndef appointment_create(request):\n"
start = views.find(start_marker)
end = views.find(end_marker, start)
if start < 0 or end < 0:
    raise RuntimeError("appointment_list block anchor changed")

new_block = r'''@login_required
def appointment_list(request):
    org = _org(request)
    allowed_views = {"day", "week", "month", "list"}
    calendar_view = (request.GET.get("view") or "week").strip().lower()
    if calendar_view not in allowed_views:
        calendar_view = "week"

    raw_date = (request.GET.get("date") or request.GET.get("start") or "").strip()
    try:
        anchor_date = timezone.datetime.strptime(raw_date, "%Y-%m-%d").date() if raw_date else timezone.localdate()
    except ValueError:
        anchor_date = timezone.localdate()

    employee_filter = (request.GET.get("employee") or "").strip()
    project_filter = (request.GET.get("project") or "").strip()
    events = (
        m.CalendarEvent.objects.filter(organization=org)
        .select_related("project", "project__customer")
        .prefetch_related("attendees")
    )
    if employee_filter.isdigit():
        events = events.filter(attendees__pk=int(employee_filter)).distinct()
    else:
        employee_filter = ""
    if project_filter.isdigit():
        events = events.filter(project_id=int(project_filter))
    else:
        project_filter = ""

    def month_shift(value, delta):
        index = value.year * 12 + (value.month - 1) + delta
        year, month_index = divmod(index, 12)
        return value.replace(year=year, month=month_index + 1, day=1)

    month_first = anchor_date.replace(day=1)
    next_month_first = month_shift(month_first, 1)
    week_start = anchor_date - timedelta(days=anchor_date.weekday())

    if calendar_view == "day":
        range_start = anchor_date
        range_end = anchor_date + timedelta(days=1)
        prev_date = anchor_date - timedelta(days=1)
        next_date = anchor_date + timedelta(days=1)
    elif calendar_view == "month":
        range_start = month_first - timedelta(days=month_first.weekday())
        month_last = next_month_first - timedelta(days=1)
        range_end = month_last + timedelta(days=(6 - month_last.weekday()) + 1)
        prev_date = month_shift(month_first, -1)
        next_date = next_month_first
    elif calendar_view == "list":
        range_start = anchor_date
        range_end = anchor_date + timedelta(days=90)
        prev_date = anchor_date - timedelta(days=30)
        next_date = anchor_date + timedelta(days=30)
    else:
        range_start = week_start
        range_end = week_start + timedelta(days=7)
        prev_date = week_start - timedelta(days=7)
        next_date = week_start + timedelta(days=7)

    tz = timezone.get_current_timezone()
    aware_start = timezone.make_aware(timezone.datetime.combine(range_start, timezone.datetime.min.time()), tz)
    aware_end = timezone.make_aware(timezone.datetime.combine(range_end, timezone.datetime.min.time()), tz)
    event_list = list(events.filter(starts_at__lt=aware_end, ends_at__gte=aware_start).order_by("starts_at"))

    grouped = {}
    for event in event_list:
        local_start = timezone.localtime(event.starts_at)
        event.ui_date = local_start.date()
        event.ui_customer = event.project.customer.display_name if event.project_id else "Intern"
        event.ui_project = f"{event.project.number} · {event.project.title}" if event.project_id else "Interner Termin"
        attendee_names = []
        for attendee in event.attendees.all():
            name = f"{attendee.first_name} {attendee.last_name}".strip()
            attendee_names.append(name or getattr(attendee, "email", "") or str(attendee.pk))
        event.ui_attendees = ", ".join(attendee_names) if attendee_names else "Nicht zugewiesen"
        grouped.setdefault(event.ui_date, []).append(event)

    def calendar_url(target_date, target_view=None):
        params = {"view": target_view or calendar_view, "date": target_date.isoformat()}
        if employee_filter:
            params["employee"] = employee_filter
        if project_filter:
            params["project"] = project_filter
        return "?" + urlencode(params)

    today = timezone.localdate()
    days = []
    month_weeks = []
    list_days = []
    day_events = grouped.get(anchor_date, [])

    if calendar_view == "week":
        for offset in range(7):
            day_date = week_start + timedelta(days=offset)
            days.append({
                "date": day_date,
                "events": grouped.get(day_date, []),
                "is_today": day_date == today,
                "day_url": calendar_url(day_date, "day"),
            })
    elif calendar_view == "month":
        cursor = range_start
        while cursor < range_end:
            week = []
            for _ in range(7):
                day_events_for_date = grouped.get(cursor, [])
                week.append({
                    "date": cursor,
                    "events": day_events_for_date[:4],
                    "extra_count": max(0, len(day_events_for_date) - 4),
                    "in_month": cursor.month == month_first.month,
                    "is_today": cursor == today,
                    "day_url": calendar_url(cursor, "day"),
                })
                cursor += timedelta(days=1)
            month_weeks.append(week)
    elif calendar_view == "list":
        cursor = range_start
        while cursor < range_end:
            date_events = grouped.get(cursor, [])
            if date_events:
                list_days.append({"date": cursor, "events": date_events, "is_today": cursor == today})
            cursor += timedelta(days=1)

    employees = m.Employee.objects.filter(organization=org, active=True).order_by("last_name", "first_name")
    projects = m.Project.objects.filter(organization=org, archived=False).select_related("customer").order_by("-updated_at")[:300]
    view_links = [
        {"key": "day", "label": "Tag", "url": calendar_url(anchor_date, "day")},
        {"key": "week", "label": "Woche", "url": calendar_url(anchor_date, "week")},
        {"key": "month", "label": "Monat", "url": calendar_url(anchor_date, "month")},
        {"key": "list", "label": "Liste", "url": calendar_url(anchor_date, "list")},
    ]
    reset_query = "?" + urlencode({"view": calendar_view, "date": anchor_date.isoformat()})

    return render(request, "rebuild/appointments.html", {
        "calendar_view": calendar_view,
        "anchor_date": anchor_date,
        "range_start": range_start,
        "range_end": range_end - timedelta(days=1),
        "month_first": month_first,
        "week_start": week_start,
        "days": days,
        "month_weeks": month_weeks,
        "day_events": day_events,
        "list_days": list_days,
        "view_links": view_links,
        "prev_url": calendar_url(prev_date),
        "next_url": calendar_url(next_date),
        "today_url": calendar_url(today),
        "employees": employees,
        "projects": projects,
        "employee_filter": employee_filter,
        "project_filter": project_filter,
        "reset_query": reset_query,
        "can_dispatch": not _is_field_user(request),
    })


@login_required
@require_POST
def appointment_move(request, pk):
    org = _org(request)
    if _is_field_user(request):
        return JsonResponse({"ok": False, "error": "Terminverschiebungen sind nur für Büro/Leitung verfügbar."}, status=403)
    event = get_object_or_404(m.CalendarEvent, pk=pk, organization=org)
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Ungültige Anfrage."}, status=400)
    raw_date = str(payload.get("date") or "").strip()
    try:
        target_date = timezone.datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"ok": False, "error": "Bitte ein gültiges Datum wählen."}, status=400)

    local_start = timezone.localtime(event.starts_at)
    duration = event.ends_at - event.starts_at
    local_time = local_start.time().replace(tzinfo=None)
    target_start = timezone.make_aware(
        timezone.datetime.combine(target_date, local_time),
        timezone.get_current_timezone(),
    )
    event.starts_at = target_start
    event.ends_at = target_start + duration
    event.save(update_fields=["starts_at", "ends_at", "updated_at"])
    return JsonResponse({
        "ok": True,
        "id": event.pk,
        "date": target_date.isoformat(),
        "starts_at": timezone.localtime(event.starts_at).isoformat(),
        "ends_at": timezone.localtime(event.ends_at).isoformat(),
    })
'''
views = views[:start] + new_block + views[end:]
write(views_path, views)

# --- route ---
urls_path = "erp/rebuild_urls.py"
urls = read(urls_path)
move_route = '    path("appointments/<int:pk>/move/", views.appointment_move, name="next-appointment-move"),\n'
if move_route not in urls:
    anchor = '    path("appointments/<int:pk>/", views.appointment_detail, name="next-appointment-detail"),\n'
    if anchor not in urls:
        raise RuntimeError("appointment URL anchor changed")
    urls = urls.replace(anchor, move_route + anchor, 1)
write(urls_path, urls)

# --- template ---
template = r'''{% extends 'rebuild/base.html' %}
{% load static %}
{% block title %}Termine · KAYI{% endblock %}
{% block content %}
<div class="nx-pagehead nx-calendar-pagehead">
  <div>
    <div class="nx-kicker">Einsatzplanung</div>
    <h1>Termine</h1>
    <p>Termine flexibel nach Tag, Woche, Monat oder als Liste planen und Mitarbeiter zuweisen.</p>
  </div>
  <div class="nx-actions"><a class="nx-btn nx-btn-primary" href="{% url 'next-appointment-create' %}">＋ Neuer Termin</a></div>
</div>

<section class="nx-calendar-shell" data-calendar-view="{{ calendar_view }}" data-calendar-dispatch="{% if can_dispatch %}1{% else %}0{% endif %}">
  <div class="nx-calendar-toolbar">
    <nav class="nx-calendar-views" aria-label="Kalenderansicht">
      {% for item in view_links %}<a class="nx-calendar-view-btn {% if calendar_view == item.key %}is-active{% endif %}" href="{{ item.url }}" data-view="{{ item.key }}">{{ item.label }}</a>{% endfor %}
    </nav>
    <div class="nx-calendar-navigation">
      <a class="nx-btn nx-btn-ghost nx-calendar-arrow" href="{{ prev_url }}" aria-label="Zurück">←</a>
      <a class="nx-btn nx-btn-ghost" href="{{ today_url }}">Heute</a>
      <a class="nx-btn nx-btn-ghost nx-calendar-arrow" href="{{ next_url }}" aria-label="Weiter">→</a>
    </div>
  </div>

  <div class="nx-calendar-period">
    {% if calendar_view == 'day' %}<strong>{{ anchor_date|date:'l, d.m.Y' }}</strong>
    {% elif calendar_view == 'week' %}<strong>{{ range_start|date:'d.m.' }} – {{ range_end|date:'d.m.Y' }}</strong>
    {% elif calendar_view == 'month' %}<strong>{{ month_first|date:'F Y' }}</strong>
    {% else %}<strong>{{ range_start|date:'d.m.Y' }} – {{ range_end|date:'d.m.Y' }}</strong>{% endif %}
    <span data-calendar-status>{% if can_dispatch and calendar_view == 'week' or can_dispatch and calendar_view == 'month' %}Termine können per Drag & Drop auf einen anderen Tag verschoben werden.{% endif %}</span>
  </div>

  <form class="nx-calendar-filters" method="get">
    <input type="hidden" name="view" value="{{ calendar_view }}">
    <input type="hidden" name="date" value="{{ anchor_date|date:'Y-m-d' }}">
    <label><span>Mitarbeiter</span><select class="nx-control" name="employee"><option value="">Alle Mitarbeiter</option>{% for employee in employees %}<option value="{{ employee.pk }}" {% if employee_filter == employee.pk|stringformat:'s' %}selected{% endif %}>{{ employee.first_name }} {{ employee.last_name }}</option>{% endfor %}</select></label>
    <label><span>Projekt</span><select class="nx-control" name="project"><option value="">Alle Projekte</option>{% for project in projects %}<option value="{{ project.pk }}" {% if project_filter == project.pk|stringformat:'s' %}selected{% endif %}>{{ project.number }} · {{ project.title }}</option>{% endfor %}</select></label>
    <div class="nx-calendar-filter-actions"><button class="nx-btn nx-btn-primary" type="submit">Filtern</button><a class="nx-btn nx-btn-ghost" href="{{ reset_query }}">Zurücksetzen</a></div>
  </form>

  {% if calendar_view == 'week' %}
  <div class="nx-week nx-week-upgraded" data-calendar-grid>
    {% for day in days %}
    <section class="nx-day {% if day.is_today %}is-today{% endif %}" data-calendar-drop-date="{{ day.date|date:'Y-m-d' }}">
      <div class="nx-day-head"><a href="{{ day.day_url }}">{{ day.date|date:'D' }}<small>{{ day.date|date:'d.m.Y' }}</small></a></div>
      <div class="nx-day-events">
      {% for event in day.events %}
        <a class="nx-cal-event" data-calendar-event data-event-id="{{ event.pk }}" data-move-url="{% url 'next-appointment-move' event.pk %}" {% if can_dispatch %}draggable="true"{% endif %} href="{% url 'next-appointment-detail' event.pk %}">
          <time>{% if event.all_day %}Ganztägig{% else %}{{ event.starts_at|date:'H:i' }} – {{ event.ends_at|date:'H:i' }}{% endif %}</time><b>{{ event.title }}</b><small>{{ event.ui_customer }}</small><span>{{ event.ui_attendees }}</span>
        </a>
      {% empty %}<div class="nx-calendar-empty">Keine Termine</div>{% endfor %}
      </div>
    </section>
    {% endfor %}
  </div>

  {% elif calendar_view == 'month' %}
  <div class="nx-month-scroll"><div class="nx-month" data-calendar-grid>
    <div class="nx-month-weekdays"><span>Mo</span><span>Di</span><span>Mi</span><span>Do</span><span>Fr</span><span>Sa</span><span>So</span></div>
    {% for week in month_weeks %}<div class="nx-month-week">{% for day in week %}
      <section class="nx-month-day {% if not day.in_month %}is-outside{% endif %} {% if day.is_today %}is-today{% endif %}" data-calendar-drop-date="{{ day.date|date:'Y-m-d' }}">
        <a class="nx-month-date" href="{{ day.day_url }}">{{ day.date|date:'j' }}</a>
        <div class="nx-month-events">
        {% for event in day.events %}<a class="nx-month-event" data-calendar-event data-event-id="{{ event.pk }}" data-move-url="{% url 'next-appointment-move' event.pk %}" {% if can_dispatch %}draggable="true"{% endif %} href="{% url 'next-appointment-detail' event.pk %}"><time>{% if not event.all_day %}{{ event.starts_at|date:'H:i' }}{% else %}Tag{% endif %}</time><b>{{ event.title }}</b></a>{% endfor %}
        {% if day.extra_count %}<a class="nx-month-more" href="{{ day.day_url }}">+ {{ day.extra_count }} weitere</a>{% endif %}
        </div>
      </section>
    {% endfor %}</div>{% endfor %}
  </div></div>

  {% elif calendar_view == 'day' %}
  <div class="nx-day-view">
    <div class="nx-day-view-head"><div><span>{{ anchor_date|date:'D' }}</span><strong>{{ anchor_date|date:'d' }}</strong></div><p>Alle Termine dieses Tages in zeitlicher Reihenfolge.</p></div>
    <div class="nx-day-agenda">
    {% for event in day_events %}
      <a class="nx-day-agenda-event" href="{% url 'next-appointment-detail' event.pk %}">
        <time>{% if event.all_day %}Ganztägig{% else %}{{ event.starts_at|date:'H:i' }}<small>bis {{ event.ends_at|date:'H:i' }}</small>{% endif %}</time>
        <div><b>{{ event.title }}</b><span>{{ event.ui_project }}</span><small>{{ event.ui_customer }} · {{ event.ui_attendees }}{% if event.location %} · {{ event.location }}{% endif %}</small></div><i>→</i>
      </a>
    {% empty %}<div class="nx-calendar-big-empty"><b>Keine Termine an diesem Tag.</b><span>Du kannst direkt einen neuen Termin anlegen.</span><a class="nx-btn nx-btn-primary" href="{% url 'next-appointment-create' %}">＋ Neuer Termin</a></div>{% endfor %}
    </div>
  </div>

  {% else %}
  <div class="nx-calendar-list">
    {% for day in list_days %}<section class="nx-calendar-list-day"><header><strong>{{ day.date|date:'l' }}</strong><span>{{ day.date|date:'d.m.Y' }}</span>{% if day.is_today %}<em>Heute</em>{% endif %}</header><div>
      {% for event in day.events %}<a class="nx-calendar-list-event" href="{% url 'next-appointment-detail' event.pk %}"><time>{% if event.all_day %}Ganztägig{% else %}{{ event.starts_at|date:'H:i' }} – {{ event.ends_at|date:'H:i' }}{% endif %}</time><div><b>{{ event.title }}</b><span>{{ event.ui_project }}</span><small>{{ event.ui_customer }} · {{ event.ui_attendees }}</small></div><i>→</i></a>{% endfor %}
    </div></section>{% empty %}<div class="nx-calendar-big-empty"><b>Keine Termine im gewählten Zeitraum.</b><span>Filter ändern oder einen neuen Termin anlegen.</span></div>{% endfor %}
  </div>
  {% endif %}
</section>
{% endblock %}
{% block scripts %}<script src="{% static 'js/kayi-calendar.js' %}?v=20260811-1" defer></script>{% endblock %}
'''
write("templates/rebuild/appointments.html", template)

# --- drag/drop JS ---
calendar_js = r'''(() => {
  "use strict";

  const getCookie = (name) => {
    const parts = document.cookie ? document.cookie.split(";") : [];
    for (const raw of parts) {
      const item = raw.trim();
      if (item.startsWith(name + "=")) return decodeURIComponent(item.slice(name.length + 1));
    }
    return "";
  };

  const init = () => {
    const root = document.querySelector("[data-calendar-view]");
    if (!root || root.dataset.calendarDispatch !== "1") return;
    const status = root.querySelector("[data-calendar-status]");
    let dragged = null;
    let draggedFrom = null;

    const setStatus = (text, kind = "") => {
      if (!status) return;
      status.textContent = text;
      status.dataset.kind = kind;
    };

    root.querySelectorAll("[data-calendar-event][draggable='true']").forEach((eventCard) => {
      eventCard.addEventListener("dragstart", (event) => {
        dragged = eventCard;
        draggedFrom = eventCard.closest("[data-calendar-drop-date]")?.dataset.calendarDropDate || "";
        eventCard.classList.add("is-dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", eventCard.dataset.eventId || "");
      });
      eventCard.addEventListener("dragend", () => {
        eventCard.classList.remove("is-dragging");
        root.querySelectorAll(".is-drop-target").forEach((el) => el.classList.remove("is-drop-target"));
        dragged = null;
        draggedFrom = null;
      });
    });

    root.querySelectorAll("[data-calendar-drop-date]").forEach((zone) => {
      zone.addEventListener("dragover", (event) => {
        if (!dragged) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        zone.classList.add("is-drop-target");
      });
      zone.addEventListener("dragleave", (event) => {
        if (!zone.contains(event.relatedTarget)) zone.classList.remove("is-drop-target");
      });
      zone.addEventListener("drop", async (event) => {
        if (!dragged) return;
        event.preventDefault();
        zone.classList.remove("is-drop-target");
        const date = zone.dataset.calendarDropDate;
        if (!date || date === draggedFrom) {
          setStatus("Termin bleibt am bisherigen Tag.");
          return;
        }
        const url = dragged.dataset.moveUrl;
        if (!url) return;
        setStatus("Termin wird verschoben …");
        try {
          const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": getCookie("csrftoken"),
              "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify({ date }),
          });
          const data = await response.json().catch(() => ({}));
          if (!response.ok || !data.ok) throw new Error(data.error || "Termin konnte nicht verschoben werden.");
          setStatus("Termin verschoben. Kalender wird aktualisiert …", "success");
          window.setTimeout(() => window.location.reload(), 260);
        } catch (error) {
          setStatus(error?.message || "Termin konnte nicht verschoben werden.", "error");
        }
      });
    });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
'''
write("static/js/kayi-calendar.js", calendar_js)

# --- visual layer ---
css_path = "static/css/kayi-next.css"
css = read(css_path)
if MARK not in css:
    css += r'''

/* KAYI CALENDAR MULTIVIEW 2026-08-11 */
.nx-calendar-shell{display:grid;gap:16px}.nx-calendar-toolbar{display:flex;justify-content:space-between;gap:14px;align-items:center}.nx-calendar-views{display:inline-flex;border:1px solid #dedbd4;border-radius:14px;padding:4px;background:#fff}.nx-calendar-view-btn{display:flex;align-items:center;justify-content:center;min-height:40px;padding:0 17px;border-radius:10px;color:#5f6368;text-decoration:none;font-weight:800;font-size:13px}.nx-calendar-view-btn.is-active{background:#111418;color:#fff}.nx-calendar-navigation{display:flex;gap:7px;align-items:center}.nx-calendar-arrow{min-width:44px;padding-inline:12px}.nx-calendar-period{display:flex;justify-content:space-between;gap:18px;align-items:center;min-height:28px}.nx-calendar-period strong{font-size:18px}.nx-calendar-period span{font-size:12.5px;color:#72777d}.nx-calendar-period span[data-kind="success"]{color:#087b5a}.nx-calendar-period span[data-kind="error"]{color:#a83d35}.nx-calendar-filters{display:grid;grid-template-columns:minmax(210px,1fr) minmax(260px,1.35fr) auto;gap:11px;align-items:end;padding:14px;border:1px solid #dedbd4;border-radius:18px;background:#fff}.nx-calendar-filters label{display:grid;gap:5px}.nx-calendar-filters label>span{font-size:12.5px;font-weight:800}.nx-calendar-filter-actions{display:flex;gap:8px}.nx-week-upgraded{gap:9px}.nx-week-upgraded .nx-day{transition:border-color .16s,background .16s;min-width:0}.nx-week-upgraded .nx-day.is-today,.nx-month-day.is-today{border-color:#65bdb1;box-shadow:inset 0 0 0 1px rgba(38,190,169,.15)}.nx-day-head a{color:inherit;text-decoration:none;display:grid;gap:2px}.nx-day-events{display:grid;gap:7px}.nx-cal-event{position:relative}.nx-cal-event span{display:block;margin-top:4px;font-size:11.5px;color:#747980;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.nx-cal-event[draggable="true"]{cursor:grab}.nx-cal-event.is-dragging,.nx-month-event.is-dragging{opacity:.4}.nx-day.is-drop-target,.nx-month-day.is-drop-target{background:#eaf8f5!important;border-color:#39a895!important;box-shadow:inset 0 0 0 2px rgba(57,168,149,.18)}.nx-calendar-empty{padding:10px 7px;color:#8a8e92;font-size:12.5px}.nx-month-scroll{overflow-x:auto;padding-bottom:3px}.nx-month{min-width:760px;border:1px solid #dedbd4;border-radius:18px;overflow:hidden;background:#fff}.nx-month-weekdays,.nx-month-week{display:grid;grid-template-columns:repeat(7,minmax(0,1fr))}.nx-month-weekdays{background:#f7f6f3;border-bottom:1px solid #dedbd4}.nx-month-weekdays span{padding:10px 12px;font-size:12px;font-weight:850;color:#666b70}.nx-month-week:not(:last-child){border-bottom:1px solid #e5e2dc}.nx-month-day{min-height:132px;padding:8px;border-right:1px solid #e5e2dc;transition:background .16s,border-color .16s}.nx-month-day:last-child{border-right:0}.nx-month-day.is-outside{background:#faf9f7;color:#a0a3a5}.nx-month-date{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:50%;font-size:12.5px;font-weight:850;color:inherit;text-decoration:none}.nx-month-day.is-today .nx-month-date{background:#111418;color:#fff}.nx-month-events{display:grid;gap:4px;margin-top:4px}.nx-month-event{display:flex;gap:5px;align-items:center;min-width:0;padding:5px 6px;border-radius:7px;background:#f1f5f4;color:#1c2827;text-decoration:none;font-size:11.5px}.nx-month-event time{flex:none;font-size:10.5px;font-weight:800;color:#55706c}.nx-month-event b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.nx-month-event[draggable="true"]{cursor:grab}.nx-month-more{font-size:11px;font-weight:750;color:#426c66;text-decoration:none;padding:2px 5px}.nx-day-view{border:1px solid #dedbd4;border-radius:20px;background:#fff;overflow:hidden}.nx-day-view-head{display:flex;align-items:center;gap:16px;padding:18px 20px;border-bottom:1px solid #e4e1db}.nx-day-view-head>div{display:grid;place-items:center;width:58px;height:62px;border-radius:14px;background:#edf7f5}.nx-day-view-head>div span{font-size:11px;font-weight:850;text-transform:uppercase}.nx-day-view-head>div strong{font-size:25px;line-height:1}.nx-day-view-head p{margin:0;color:#757a7e}.nx-day-agenda{display:grid}.nx-day-agenda-event{display:grid;grid-template-columns:100px 1fr 24px;gap:15px;align-items:center;padding:17px 20px;border-bottom:1px solid #ece9e3;color:#171a1d;text-decoration:none}.nx-day-agenda-event:hover{background:#fafaf8}.nx-day-agenda-event>time{font-size:16px;font-weight:850}.nx-day-agenda-event>time small{display:block;margin-top:3px;font-size:11.5px;color:#777c80;font-weight:650}.nx-day-agenda-event>div{display:grid;gap:3px;min-width:0}.nx-day-agenda-event b{font-size:15px}.nx-day-agenda-event span{font-size:12.5px;color:#4e5559}.nx-day-agenda-event small{font-size:11.5px;color:#85898d}.nx-day-agenda-event i,.nx-calendar-list-event i{font-style:normal;font-size:18px}.nx-calendar-big-empty{display:grid;justify-items:start;gap:7px;padding:28px}.nx-calendar-big-empty>b{font-size:17px}.nx-calendar-big-empty>span{color:#777c80}.nx-calendar-big-empty .nx-btn{margin-top:5px}.nx-calendar-list{display:grid;gap:15px}.nx-calendar-list-day{display:grid;grid-template-columns:145px 1fr;border:1px solid #dedbd4;border-radius:18px;background:#fff;overflow:hidden}.nx-calendar-list-day>header{display:grid;align-content:start;gap:3px;padding:17px;background:#f7f6f3}.nx-calendar-list-day>header strong{font-size:14px}.nx-calendar-list-day>header span{font-size:12px;color:#74797d}.nx-calendar-list-day>header em{justify-self:start;margin-top:5px;padding:3px 7px;border-radius:999px;background:#ddf5ef;color:#087b5a;font-size:10px;font-style:normal;font-weight:850}.nx-calendar-list-day>div{display:grid}.nx-calendar-list-event{display:grid;grid-template-columns:110px 1fr 24px;gap:12px;align-items:center;padding:14px 17px;color:#171a1d;text-decoration:none}.nx-calendar-list-event:not(:last-child){border-bottom:1px solid #ece9e3}.nx-calendar-list-event:hover{background:#fafaf8}.nx-calendar-list-event>time{font-size:12.5px;font-weight:850}.nx-calendar-list-event>div{display:grid;gap:2px;min-width:0}.nx-calendar-list-event b{font-size:14px}.nx-calendar-list-event span,.nx-calendar-list-event small{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.nx-calendar-list-event span{font-size:12px;color:#555c60}.nx-calendar-list-event small{font-size:11.5px;color:#85898d}
@media(max-width:900px){.nx-calendar-toolbar,.nx-calendar-period{align-items:flex-start;flex-direction:column}.nx-calendar-navigation{width:100%}.nx-calendar-navigation .nx-btn:nth-child(2){flex:1}.nx-calendar-filters{grid-template-columns:1fr 1fr}.nx-calendar-filter-actions{grid-column:1/-1}.nx-week-upgraded{grid-template-columns:repeat(7,minmax(180px,1fr));overflow-x:auto;padding-bottom:8px}.nx-week-upgraded .nx-day{min-width:180px}.nx-calendar-period span{min-height:18px}}
@media(max-width:680px){.nx-calendar-pagehead{gap:12px}.nx-calendar-pagehead .nx-actions{width:100%}.nx-calendar-pagehead .nx-actions .nx-btn{width:100%}.nx-calendar-views{display:grid;grid-template-columns:repeat(4,1fr);width:100%;box-sizing:border-box}.nx-calendar-view-btn{padding:0 8px;font-size:12px}.nx-calendar-filters{grid-template-columns:1fr;padding:12px}.nx-calendar-filter-actions{grid-column:auto;display:grid;grid-template-columns:1fr 1fr}.nx-calendar-period strong{font-size:16px}.nx-calendar-period span{font-size:12px}.nx-day-agenda-event{grid-template-columns:74px 1fr 18px;padding:14px 13px;gap:10px}.nx-day-agenda-event>time{font-size:14px}.nx-calendar-list-day{grid-template-columns:1fr}.nx-calendar-list-day>header{grid-template-columns:auto auto 1fr;gap:8px;align-items:center}.nx-calendar-list-day>header em{margin:0;justify-self:end}.nx-calendar-list-event{grid-template-columns:86px 1fr 18px;padding:13px}.nx-month{min-width:690px}}
'''
write(css_path, css)

# Bust the shared CSS so production/mobile cannot retain the old week-only styling.
base_path = "templates/rebuild/base.html"
base = read(base_path)
base = re.sub(r"(static 'css/kayi-next\.css' %\}\?v=)[^\"']+", r"\g<1>20260811-calendar1", base, count=1)
write(base_path, base)

# Regression contract generated into the assembled test tree.
test_content = r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class CalendarUpgradeContractTests(SimpleTestCase):
    def test_calendar_multiview_contract(self):
        template = (ROOT / "templates/rebuild/appointments.html").read_text(encoding="utf-8")
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        js = (ROOT / "static/js/kayi-calendar.js").read_text(encoding="utf-8")
        for marker in ("Tag", "Woche", "Monat", "Liste", "Mitarbeiter", "Projekt", "data-calendar-view"):
            self.assertIn(marker, template)
        self.assertIn("def appointment_move", views)
        self.assertIn("attendees__pk", views)
        self.assertIn("next-appointment-move", urls)
        self.assertIn("data-calendar-drop-date", template)
        self.assertIn("X-CSRFToken", js)
        self.assertIn("window.location.reload", js)
'''
write("tests/test_calendar_upgrade.py", test_content)

print("KAYI calendar upgraded: day/week/month/list, filters and safe drag/drop")
