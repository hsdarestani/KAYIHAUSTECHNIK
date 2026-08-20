from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 12 APPOINTMENT MAP 2026-08-21"
CSS_REL = "static/css/tooltime-phase12-appointment-map.css"
JS_REL = "static/js/tooltime-phase12-appointment-map.js"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 12 appointment-map anchor missing: {label}")
    return text.replace(old, new, 1)


def patch_backend(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)

    text = _replace_once(
        text,
        '    allowed_views = {"day", "week", "month", "list"}\n',
        '    allowed_views = {"day", "week", "month", "map", "list"}\n',
        "map allowed view",
    )
    text = _replace_once(
        text,
        '    elif calendar_view == "list":\n        range_start = anchor_date\n',
        '    elif calendar_view in {"list", "map"}:\n        range_start = anchor_date\n',
        "map planning range",
    )
    text = _replace_once(
        text,
        '        event.ui_project = f"{event.project.number} · {event.project.title}" if event.project_id else "Interner Termin"\n',
        '        event.ui_project = f"{event.project.number} · {event.project.title}" if event.project_id else "Interner Termin"\n        event.ui_map_address = (event.location or "").strip()\n',
        "map address projection",
    )
    text = _replace_once(
        text,
        '    day_events = grouped.get(anchor_date, [])\n\n    if calendar_view == "week":\n',
        '    day_events = grouped.get(anchor_date, [])\n    map_events = [event for event in event_list if event.ui_map_address]\n\n    if calendar_view == "week":\n',
        "map events",
    )
    text = _replace_once(
        text,
        '        {"key": "month", "label": "Monat", "url": calendar_url(anchor_date, "month")},\n        {"key": "list", "label": "Liste", "url": calendar_url(anchor_date, "list")},\n',
        '        {"key": "month", "label": "Monat", "url": calendar_url(anchor_date, "month")},\n        {"key": "map", "label": "Karte", "url": calendar_url(anchor_date, "map")},\n        {"key": "list", "label": "Liste", "url": calendar_url(anchor_date, "list")},\n',
        "map view link",
    )
    text = _replace_once(
        text,
        '        "day_events": day_events,\n        "list_days": list_days,\n',
        '        "day_events": day_events,\n        "map_events": map_events,\n        "list_days": list_days,\n',
        "map context",
    )

    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_template(module) -> None:
    rel = "templates/rebuild/appointments.html"
    text = module.read(rel)

    list_anchor = '''  {% else %}
  <div class="nx-calendar-list" data-list-view>'''
    map_block = '''  {% elif calendar_view == 'map' %}
  <div class="tt-appointment-map" data-appointment-map>
    <aside class="tt-appointment-map-list" aria-label="Termine mit Adresse">
      <div class="tt-appointment-map-list-head">
        <div><strong>Termine auf der Karte</strong><span>{{ map_events|length }} mit Adresse</span></div>
        <small>Zeitraum {{ range_start|date:'d.m.' }} – {{ range_end|date:'d.m.Y' }}</small>
      </div>
      <div class="tt-appointment-map-items">
        {% for event in map_events %}
        <article class="tt-appointment-map-item">
          <button type="button" data-map-select data-map-address="{{ event.ui_map_address|escape }}" data-map-label="{{ event.title|escape }}">
            <span class="tt-map-pin" aria-hidden="true">⌖</span>
            <span class="tt-map-copy">
              <time>{% if event.all_day %}{{ event.starts_at|date:'d.m.Y' }} · Ganztägig{% else %}{{ event.starts_at|date:'d.m.Y · H:i' }}{% endif %}</time>
              <strong>{{ event.title }}</strong>
              <span>{{ event.ui_map_address }}</span>
              <small>{{ event.ui_customer }} · {{ event.ui_attendees }}</small>
            </span>
          </button>
          <a href="{% url 'next-appointment-detail' event.pk %}" aria-label="Termin {{ event.title }} öffnen">→</a>
        </article>
        {% empty %}
        <div class="tt-appointment-map-empty-list"><b>Keine Termine mit Adresse.</b><span>Trage beim Termin einen Einsatzort ein, damit er hier auf der Karte verfügbar ist.</span></div>
        {% endfor %}
      </div>
    </aside>
    <section class="tt-appointment-map-canvas" aria-label="Kartenansicht">
      <div class="tt-appointment-map-placeholder" data-map-placeholder>
        <span aria-hidden="true">⌖</span>
        <strong>Termin auswählen</strong>
        <p>Wähle links einen Termin mit Adresse. Die externe Karte wird erst nach deiner Auswahl geladen.</p>
      </div>
      <iframe data-map-frame hidden title="Karte zum ausgewählten Termin" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
      <div class="tt-appointment-map-caption" data-map-caption hidden>
        <div><small>Ausgewählter Termin</small><strong data-map-title></strong><span data-map-current-address></span></div>
        <a class="nx-btn nx-btn-ghost" data-map-open href="#" target="_blank" rel="noopener noreferrer">In Karten öffnen ↗</a>
      </div>
    </section>
  </div>

  {% else %}
  <div class="nx-calendar-list" data-list-view>'''
    text = _replace_once(text, list_anchor, map_block, "map template branch")

    module.write(rel, text)


def patch_sidebar_and_assets(module) -> None:
    rel = "templates/rebuild/base.html"
    text = module.read(rel)

    if "data-appointment-subnav" not in text:
        token = 'href="{% url \'next-appointments\' %}"'
        token_pos = text.find(token)
        if token_pos < 0:
            raise RuntimeError("Phase 12 appointment sidebar link missing")
        anchor_start = text.rfind("<a", 0, token_pos)
        anchor_end = text.find("</a>", token_pos)
        if anchor_start < 0 or anchor_end < 0:
            raise RuntimeError("Phase 12 appointment sidebar anchor boundary missing")
        anchor_end += len("</a>")
        subnav = '''{% if request.resolver_match.url_name == 'next-appointments' %}<div class="tt-appointment-subnav" data-appointment-subnav><a class="{% if calendar_view != 'map' and calendar_view != 'list' %}is-active{% endif %}" href="{% url 'next-appointments' %}?view=week">Kalender</a><a class="{% if calendar_view == 'map' %}is-active{% endif %}" href="{% url 'next-appointments' %}?view=map">Karte</a><a class="{% if calendar_view == 'list' %}is-active{% endif %}" href="{% url 'next-appointments' %}?view=list">Liste</a></div>{% endif %}'''
        text = text[:anchor_end] + subnav + text[anchor_end:]

    css_tag = "  <link rel=\"stylesheet\" href=\"{% static 'css/tooltime-phase12-appointment-map.css' %}?v=20260821-1\">\n"
    if "tooltime-phase12-appointment-map.css" not in text:
        if "</head>" not in text:
            raise RuntimeError("Phase 12 base head anchor missing")
        text = text.replace("</head>", css_tag + "</head>", 1)

    js_tag = "<script src=\"{% static 'js/tooltime-phase12-appointment-map.js' %}?v=20260821-1\" defer></script>\n"
    if "tooltime-phase12-appointment-map.js" not in text:
        if "</body>" not in text:
            raise RuntimeError("Phase 12 base body anchor missing")
        text = text.replace("</body>", js_tag + "</body>", 1)

    module.write(rel, text)


def install_assets(module) -> None:
    module.write(CSS_REL, r'''/* A+BAU TOOLTIME PHASE 12 APPOINTMENT MAP 2026-08-21 */
.tt-appointment-subnav{display:grid;gap:2px;margin:-3px 0 8px 35px;padding:3px 0 3px 10px;border-left:1px solid rgba(108,118,129,.22)}
.nx-nav .tt-appointment-subnav a{min-height:28px;padding:4px 8px;border-radius:7px;font-size:11.5px;font-weight:720;color:#7a8087}
.nx-nav .tt-appointment-subnav a:hover{background:rgba(17,20,24,.045);color:#25292d}
.nx-nav .tt-appointment-subnav a.is-active{background:transparent;color:#111418;font-weight:850}
.tt-appointment-map{display:grid;grid-template-columns:minmax(300px,390px) minmax(0,1fr);min-height:580px;border:1px solid #dedbd4;border-radius:20px;overflow:hidden;background:#fff}
.tt-appointment-map-list{display:grid;grid-template-rows:auto minmax(0,1fr);min-width:0;border-right:1px solid #e5e2dc;background:#fff}
.tt-appointment-map-list-head{display:grid;gap:7px;padding:17px 18px;border-bottom:1px solid #e9e6e0}
.tt-appointment-map-list-head>div{display:flex;justify-content:space-between;gap:12px;align-items:center}
.tt-appointment-map-list-head strong{font-size:14px}.tt-appointment-map-list-head span,.tt-appointment-map-list-head small{font-size:11.5px;color:#777d82}.tt-appointment-map-list-head>div span{padding:4px 8px;border-radius:999px;background:#f1f4f3;color:#4f5c59;font-weight:750}
.tt-appointment-map-items{min-height:0;overflow:auto}
.tt-appointment-map-item{display:grid;grid-template-columns:minmax(0,1fr) 38px;align-items:stretch;border-bottom:1px solid #eeece7}
.tt-appointment-map-item>button{display:grid;grid-template-columns:31px minmax(0,1fr);gap:10px;width:100%;padding:14px 10px 14px 15px;border:0;background:transparent;text-align:left;cursor:pointer;color:#171a1d}
.tt-appointment-map-item>button:hover,.tt-appointment-map-item>button.is-active{background:#f7faf9}
.tt-map-pin{display:grid;place-items:center;width:29px;height:29px;border-radius:50%;background:#e7f5f2;color:#147c6e;font-size:16px;font-weight:900}
.tt-map-copy{display:grid;gap:3px;min-width:0}.tt-map-copy time{font-size:10.5px;font-weight:800;color:#72797d}.tt-map-copy strong{font-size:13.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tt-map-copy>span{font-size:11.5px;color:#4d5759;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tt-map-copy small{font-size:10.5px;color:#8a8f92;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tt-appointment-map-item>a{display:grid;place-items:center;color:#656b70;text-decoration:none;font-size:17px}.tt-appointment-map-item>a:hover{background:#f7f6f3;color:#111418}
.tt-appointment-map-empty-list{display:grid;gap:6px;padding:28px 20px;color:#747a7e}.tt-appointment-map-empty-list b{color:#25292d;font-size:14px}.tt-appointment-map-empty-list span{font-size:12px;line-height:1.5}
.tt-appointment-map-canvas{position:relative;min-width:0;min-height:580px;background:linear-gradient(135deg,#eef1ee,#e5ebe8)}
.tt-appointment-map-canvas iframe{position:absolute;inset:0;width:100%;height:100%;border:0;background:#edf0ed}
.tt-appointment-map-placeholder{position:absolute;inset:0;display:grid;place-content:center;justify-items:center;gap:9px;padding:28px;text-align:center;color:#65706d;background-image:radial-gradient(circle at 20% 20%,rgba(255,255,255,.72),transparent 32%),linear-gradient(135deg,#eef1ee,#e5ebe8)}
.tt-appointment-map-placeholder>span{display:grid;place-items:center;width:56px;height:56px;border-radius:50%;background:#fff;color:#147c6e;font-size:27px;box-shadow:0 8px 28px rgba(34,54,48,.09)}.tt-appointment-map-placeholder strong{font-size:17px;color:#222a27}.tt-appointment-map-placeholder p{max-width:380px;margin:0;font-size:12.5px;line-height:1.55}
.tt-appointment-map-caption{position:absolute;left:16px;right:16px;bottom:16px;display:flex;justify-content:space-between;gap:16px;align-items:center;padding:12px 13px 12px 15px;border:1px solid rgba(221,226,223,.95);border-radius:14px;background:rgba(255,255,255,.95);box-shadow:0 10px 30px rgba(24,35,31,.14);backdrop-filter:blur(10px)}
.tt-appointment-map-caption>div{display:grid;gap:2px;min-width:0}.tt-appointment-map-caption small{font-size:9.5px;font-weight:850;text-transform:uppercase;letter-spacing:.06em;color:#858b88}.tt-appointment-map-caption strong{font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tt-appointment-map-caption span{font-size:11px;color:#646c69;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:1000px){.tt-appointment-map{grid-template-columns:330px minmax(0,1fr)}}
@media(max-width:760px){.tt-appointment-map{grid-template-columns:1fr;min-height:0}.tt-appointment-map-list{border-right:0;border-bottom:1px solid #e5e2dc}.tt-appointment-map-items{max-height:330px}.tt-appointment-map-canvas{min-height:440px}.nx-calendar-views{grid-template-columns:repeat(5,minmax(74px,1fr))!important;overflow-x:auto}.tt-appointment-map-caption{align-items:flex-start;flex-direction:column}.tt-appointment-map-caption .nx-btn{width:100%}}
@media(max-width:520px){.tt-appointment-map{border-radius:15px}.tt-appointment-map-canvas{min-height:390px}.tt-appointment-map-item{grid-template-columns:minmax(0,1fr) 34px}.tt-appointment-map-item>button{padding-left:12px}}
''')

    module.write(JS_REL, r'''// A+BAU TOOLTIME PHASE 12 APPOINTMENT MAP 2026-08-21
(() => {
  const init = () => {
    const root = document.querySelector('[data-appointment-map]');
    if (!root || root.dataset.mapReady === '1') return;
    root.dataset.mapReady = '1';

    const frame = root.querySelector('[data-map-frame]');
    const placeholder = root.querySelector('[data-map-placeholder]');
    const caption = root.querySelector('[data-map-caption]');
    const title = root.querySelector('[data-map-title]');
    const addressLabel = root.querySelector('[data-map-current-address]');
    const openLink = root.querySelector('[data-map-open]');
    const buttons = Array.from(root.querySelectorAll('[data-map-select]'));
    if (!frame || !placeholder || !caption || !openLink) return;

    const selectAddress = (button) => {
      const address = (button.dataset.mapAddress || '').trim();
      if (!address) return;
      const label = (button.dataset.mapLabel || address).trim();
      buttons.forEach((candidate) => candidate.classList.toggle('is-active', candidate === button));
      const encoded = encodeURIComponent(address);
      frame.src = `https://www.google.com/maps?q=${encoded}&output=embed`;
      frame.hidden = false;
      placeholder.hidden = true;
      caption.hidden = false;
      if (title) title.textContent = label;
      if (addressLabel) addressLabel.textContent = address;
      openLink.href = `https://www.google.com/maps/search/?api=1&query=${encoded}`;
    };

    buttons.forEach((button) => button.addEventListener('click', () => selectAddress(button)));
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
''')


def install_tests(module) -> None:
    module.write("tests/test_tooltime_phase12_appointment_map.py", r'''from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import CalendarEvent, Organization, UserProfile


class ToolTimePhase12AppointmentMapTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="KAYI appointment phase12")
        self.other_org = Organization.objects.create(name="KAYI appointment phase12 foreign")
        self.user = User.objects.create_user("appointment-phase12-admin", password="safe-test-password")
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"organization": self.org, "role": UserProfile.Role.ADMIN, "is_mobile_worker": False},
        )
        self.client = Client()
        self.assertTrue(self.client.login(username="appointment-phase12-admin", password="safe-test-password"))
        start = timezone.localtime().replace(second=0, microsecond=0) + timedelta(hours=2)
        self.event = CalendarEvent.objects.create(
            organization=self.org,
            title="Kundendienst Sachsenhausen",
            location="Schweizer Straße 10, 60594 Frankfurt am Main",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            created_by=self.user,
        )
        CalendarEvent.objects.create(
            organization=self.other_org,
            title="Fremder Karten-Termin",
            location="Berlin Alexanderplatz",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
        )
        self.anchor = timezone.localtime(self.event.starts_at).date().isoformat()

    def test_map_view_lists_only_organization_scoped_addressed_events(self):
        response = self.client.get(reverse("next-appointments"), {"view": "map", "date": self.anchor})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-calendar-view="map"')
        self.assertContains(response, "Kundendienst Sachsenhausen")
        self.assertContains(response, "Schweizer Straße 10, 60594 Frankfurt am Main")
        self.assertNotContains(response, "Fremder Karten-Termin")
        self.assertContains(response, "Die externe Karte wird erst nach deiner Auswahl geladen.")

    def test_calendar_list_and_map_views_coexist(self):
        for view in ("day", "week", "month", "map", "list"):
            response = self.client.get(reverse("next-appointments"), {"view": view, "date": self.anchor})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f'data-calendar-view="{view}"')
''')

    module.write("tests/test_tooltime_phase12_appointment_map_contract.py", r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase12AppointmentMapContractTests(SimpleTestCase):
    def test_map_is_real_on_demand_view_without_fake_coordinates_or_api_key(self):
        backend = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/appointments.html").read_text(encoding="utf-8")
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        javascript = (ROOT / "static/js/tooltime-phase12-appointment-map.js").read_text(encoding="utf-8")
        css = (ROOT / "static/css/tooltime-phase12-appointment-map.css").read_text(encoding="utf-8")

        for marker in ('"map"', "map_events", "ui_map_address", "query_filter", "customer_filter"):
            self.assertIn(marker, backend)
        for marker in ("data-appointment-map", "data-map-select", "data-map-frame", "Karte", "data-list-view", "data-calendar-drop-date"):
            self.assertIn(marker, template)
        for marker in ("data-appointment-subnav", "?view=week", "?view=map", "?view=list"):
            self.assertIn(marker, base)
        self.assertIn("encodeURIComponent(address)", javascript)
        self.assertIn("output=embed", javascript)
        self.assertIn("maps/search/?api=1", javascript)
        self.assertNotIn("AIza", javascript)
        self.assertNotIn("latitude", backend.lower())
        self.assertNotIn("longitude", backend.lower())
        self.assertIn("@media(max-width:760px)", css)
        self.assertIn("dragstart", (ROOT / "static/js/kayi-calendar.js").read_text(encoding="utf-8"))
''')

    for rel in ("tests/test_tooltime_phase12_appointment_map.py", "tests/test_tooltime_phase12_appointment_map_contract.py"):
        compile(module.read(rel), str(ROOT / rel), "exec")


def guard(module) -> None:
    views = module.read("erp/rebuild_views.py")
    template = module.read("templates/rebuild/appointments.html")
    base = module.read("templates/rebuild/base.html")
    javascript = module.read(JS_REL)
    css = module.read(CSS_REL)

    for marker in ('{"day", "week", "month", "map", "list"}', "map_events", "ui_map_address"):
        if marker not in views:
            raise RuntimeError(f"Phase 12 map backend marker missing: {marker}")
    for marker in ("data-appointment-map", "data-map-select", "data-map-frame", "data-list-view", "data-calendar-drop-date"):
        if marker not in template:
            raise RuntimeError(f"Phase 12 map template marker missing: {marker}")
    for marker in ("data-appointment-subnav", "?view=week", "?view=map", "?view=list", "tooltime-phase12-appointment-map.css", "tooltime-phase12-appointment-map.js"):
        if marker not in base:
            raise RuntimeError(f"Phase 12 sidebar/asset marker missing: {marker}")
    if "encodeURIComponent(address)" not in javascript or "output=embed" not in javascript:
        raise RuntimeError("Phase 12 on-demand external map behavior missing")
    if MARKER not in css:
        raise RuntimeError("Phase 12 map CSS missing")


def run(module) -> None:
    patch_backend(module)
    patch_template(module)
    patch_sidebar_and_assets(module)
    install_assets(module)
    install_tests(module)
    guard(module)
    print(f"{MARKER}: Kalender/Karte/Liste navigation and on-demand address map added without schema changes or fake coordinates.")
