from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME APPOINTMENT SIDEBAR NAV FIX 2026-08-21"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Appointment sidebar target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_sidebar() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)

    # Phase 10 originally added Kalender/Liste plus a disabled Karte entry. Phase 12
    # later added the real Kalender/Karte/Liste navigation, which left both groups in
    # the assembled sidebar. Replace the complete appointment group with one canonical
    # ToolTime-style submenu that remains visible on create/detail pages as well.
    start = text.find('<div class="tt-appt-nav-group">')
    if start < 0:
        raise RuntimeError("Appointment sidebar group anchor missing")

    project_token = 'href="{% url \'next-projects\' %}"'
    project_pos = text.find(project_token, start)
    if project_pos < 0:
        raise RuntimeError("Projects link after appointment group missing")
    end = text.rfind("<a", start, project_pos)
    if end < 0:
        raise RuntimeError("Projects anchor boundary after appointment group missing")

    canonical = '''<div class="tt-appt-nav-group" data-appointment-nav-group>
      <a class="{% if 'appointment' in request.resolver_match.url_name %}is-active{% endif %}" href="{% url 'next-appointments' %}"><span class="nx-ico">◫</span>Termine</a>
      <div class="tt-appointment-subnav" data-appointment-subnav>
        <a class="{% if request.resolver_match.url_name == 'next-appointments' and calendar_view != 'map' and calendar_view != 'list' %}is-active{% endif %}" href="{% url 'next-appointments' %}?view=week">Kalender</a>
        <a class="{% if request.resolver_match.url_name == 'next-appointments' and calendar_view == 'map' %}is-active{% endif %}" href="{% url 'next-appointments' %}?view=map">Karte</a>
        <a class="{% if request.resolver_match.url_name == 'next-appointments' and calendar_view == 'list' %}is-active{% endif %}" href="{% url 'next-appointments' %}?view=list">Liste</a>
      </div>
      </div>
      '''
    text = text[:start] + canonical + text[end:]

    # There must be exactly one live submenu and no obsolete disabled duplicate.
    if text.count('data-appointment-subnav') != 1:
        raise RuntimeError("Appointment sidebar still contains duplicate subnavigation")
    if '<div class="tt-appt-subnav">' in text:
        raise RuntimeError("Legacy appointment subnavigation still present")
    if 'Kartenansicht folgt auf Basis persistierter Geodaten' in text:
        raise RuntimeError("Legacy disabled Karte entry still present")

    write(rel, text)


def patch_sidebar_css() -> None:
    rel = "static/css/tooltime-phase12-appointment-map.css"
    css = read(rel)
    if MARKER not in css:
        css += r'''

/* A+BAU TOOLTIME APPOINTMENT SIDEBAR NAV FIX 2026-08-21 */
.nx-sidebar .tt-appt-nav-group{display:grid}
.nx-sidebar .tt-appt-subnav{display:none!important}
.nx-sidebar .tt-appointment-subnav{display:grid;gap:2px;margin:-3px 0 8px 35px;padding:3px 0 3px 10px;border-left:1px solid rgba(255,255,255,.10)}
.nx-sidebar .tt-appointment-subnav a{min-height:28px!important;padding:5px 9px!important;border-radius:7px!important;background:transparent!important;color:#8e959d!important;font-size:11.5px!important;font-weight:720!important;box-shadow:none!important}
.nx-sidebar .tt-appointment-subnav a:hover{background:rgba(255,255,255,.055)!important;color:#e7e9eb!important}
.nx-sidebar .tt-appointment-subnav a.is-active{background:rgba(201,161,59,.13)!important;color:#fff!important;font-weight:850!important;box-shadow:inset 2px 0 #d0a536!important}
@media(max-width:860px){.nx-sidebar .tt-appointment-subnav{margin-left:31px}.nx-sidebar .tt-appointment-subnav a{min-height:34px!important;padding:7px 9px!important}}
'''
        write(rel, css)


def install_tests() -> None:
    write("tests/test_tooltime_appointment_sidebar_nav_fix.py", r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeAppointmentSidebarNavFixTests(SimpleTestCase):
    def test_sidebar_has_one_live_calendar_map_list_group(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertEqual(base.count("data-appointment-subnav"), 1)
        self.assertEqual(base.count("?view=week"), 1)
        self.assertEqual(base.count("?view=map"), 1)
        self.assertEqual(base.count("?view=list"), 1)
        self.assertNotIn('<div class="tt-appt-subnav">', base)
        self.assertNotIn("Kartenansicht folgt auf Basis persistierter Geodaten", base)

    def test_submenu_is_present_on_all_appointment_pages_and_active_state_is_safe(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        self.assertIn("data-appointment-nav-group", base)
        self.assertIn("request.resolver_match.url_name == 'next-appointments' and calendar_view == 'map'", base)
        self.assertNotIn("{% if request.resolver_match.url_name == 'next-appointments' %}<div class=\"tt-appointment-subnav\"", base)

    def test_active_map_label_is_visible_on_dark_sidebar(self):
        css = (ROOT / "static/css/tooltime-phase12-appointment-map.css").read_text(encoding="utf-8")
        self.assertIn("A+BAU TOOLTIME APPOINTMENT SIDEBAR NAV FIX 2026-08-21", css)
        self.assertIn(".nx-sidebar .tt-appointment-subnav a.is-active", css)
        self.assertIn("color:#fff!important", css)
        self.assertIn(".nx-sidebar .tt-appt-subnav{display:none!important}", css)
''')


def guard() -> None:
    base = read("templates/rebuild/base.html")
    css = read("static/css/tooltime-phase12-appointment-map.css")
    tests = read("tests/test_tooltime_appointment_sidebar_nav_fix.py")
    for value in ("Kalender", "Karte", "Liste", "?view=week", "?view=map", "?view=list"):
        if value not in base:
            raise RuntimeError(f"Appointment sidebar canonical item missing: {value}")
    if base.count("data-appointment-subnav") != 1:
        raise RuntimeError("Appointment sidebar canonical submenu count is not one")
    if MARKER not in css or "color:#fff!important" not in css:
        raise RuntimeError("Appointment sidebar active-state visibility CSS missing")
    compile(tests, str(ROOT / "tests/test_tooltime_appointment_sidebar_nav_fix.py"), "exec")


def main() -> None:
    patch_sidebar()
    patch_sidebar_css()
    install_tests()
    guard()
    print(f"{MARKER}: duplicate Kalender/Karte/Liste groups removed and one visible canonical submenu installed.")


if __name__ == "__main__":
    main()
