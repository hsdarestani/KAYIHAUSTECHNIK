from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "templates/rebuild/base.html"
CSS_SOURCE = ROOT / "design/apex/ab-bau-apex.css"
JS_SOURCE = ROOT / "design/apex/ab-bau-apex.js"
CSS_TARGET = ROOT / "static/css/ab-bau-apex.css"
JS_TARGET = ROOT / "static/js/ab-bau-apex.js"
MARKER = "A+BAU APEX DESIGN SYSTEM 2026-09-08"


def require(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"A+Bau Apex target missing: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def install_assets() -> None:
    CSS_TARGET.parent.mkdir(parents=True, exist_ok=True)
    JS_TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CSS_SOURCE, CSS_TARGET)
    shutil.copyfile(JS_SOURCE, JS_TARGET)


def patch_base() -> None:
    text = require(BASE)
    link = '<link rel="stylesheet" href="/static/css/ab-bau-apex.css?v=20260908-2">'
    if link not in text:
        if "</head>" not in text:
            raise RuntimeError("A+Bau Apex base has no head anchor")
        text = text.replace("</head>", f"  {link}\n</head>", 1)

    body = re.search(r'<body class="([^"]*)"', text)
    if not body:
        raise RuntimeError("A+Bau Apex body class anchor missing")
    classes = body.group(1)
    if "ab-apex" not in classes.split():
        text = text[:body.start(1)] + "ab-apex " + classes + text[body.end(1):]

    text = text.replace('content="#111418"', 'content="#0b0d10"')
    text = text.replace(">ToolTime Import</a>", ">Datenimport</a>")
    text = text.replace("<small>Work OS</small>", "<small>Operations</small>")

    if "ab-mobile-wordmark" not in text:
        menu = re.search(r'(<button class="nx-menu-btn"[^>]*data-nx-menu[^>]*>.*?</button>)', text)
        if not menu:
            raise RuntimeError("A+Bau Apex mobile menu anchor missing")
        wordmark = (
            "{% if request.user.profile.role == 'technician' or request.user.profile.is_mobile_worker %}"
            "<a class=\"ab-mobile-wordmark\" href=\"{% url 'next-field' %}\">A+Bau</a>"
            "{% else %}"
            "<a class=\"ab-mobile-wordmark\" href=\"{% url 'next-dashboard' %}\">A+Bau</a>"
            "{% endif %}"
        )
        text = text[:menu.end()] + wordmark + text[menu.end():]

    if "ab-mobile-dock" not in text:
        anchor = "{% if request.user.profile.role == 'technician' or request.user.profile.is_mobile_worker %}<nav class=\"nx-field-bottom\">"
        if anchor not in text:
            raise RuntimeError("A+Bau Apex field bottom navigation anchor missing")
        dock = r'''{% if request.user.profile.role == 'technician' or request.user.profile.is_mobile_worker %}{% else %}
<nav class="ab-mobile-dock" aria-label="Hauptnavigation">
  <a class="{% if request.resolver_match.url_name == 'next-dashboard' %}is-active{% endif %}" href="{% url 'next-dashboard' %}"><span class="ab-dock-ico">⌂</span><span>Start</span></a>
  <a class="{% if 'appointment' in request.resolver_match.url_name %}is-active{% endif %}" href="{% url 'next-appointments' %}"><span class="ab-dock-ico">◫</span><span>Termine</span></a>
  <a class="{% if 'project' in request.resolver_match.url_name %}is-active{% endif %}" href="{% url 'next-projects' %}"><span class="ab-dock-ico">▣</span><span>Projekte</span></a>
  <a class="{% if 'customer' in request.resolver_match.url_name %}is-active{% endif %}" href="{% url 'next-customers' %}"><span class="ab-dock-ico">◎</span><span>Kunden</span></a>
  <button type="button" data-ab-open-menu aria-label="Mehr Navigation"><span class="ab-dock-ico">•••</span><span>Mehr</span></button>
</nav>
{% endif %}
'''
        text = text.replace(anchor, dock + anchor, 1)

    runtime = '<script src="/static/js/ab-bau-apex.js?v=20260908-1" defer></script>'
    if runtime not in text:
        scripts = "{% block scripts %}{% endblock %}"
        if scripts not in text:
            raise RuntimeError("A+Bau Apex scripts block anchor missing")
        text = text.replace(scripts, runtime + "\n" + scripts, 1)

    BASE.write_text(text, encoding="utf-8")


def patch_copy() -> None:
    dashboard = ROOT / "templates/rebuild/dashboard.html"
    if dashboard.exists():
        text = dashboard.read_text(encoding="utf-8")
        text = text.replace("<b>Von ToolTime wechseln</b>", "<b>Daten importieren</b>")
        text = text.replace("Bestandsdaten aus CSV/XLSX übernehmen.", "Bestehende Daten sicher aus CSV/XLSX übernehmen.")
        dashboard.write_text(text, encoding="utf-8")


def patch_native_shell() -> None:
    path = ROOT / "native/www/index.html"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if '<meta name="theme-color"' not in text and "<head>" in text:
        text = text.replace("<head>", '<head>\n<meta name="theme-color" content="#0b0d10">', 1)
    if "ABBAU_APEX_NATIVE_2026_09_08" not in text and "</head>" in text:
        style = r'''<style id="ABBAU_APEX_NATIVE_2026_09_08">
:root{color-scheme:dark}html,body{margin:0;min-height:100%;background:#0b0d10;color:#f7f2e7;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
body{min-height:100dvh;display:grid;place-items:center;overflow:hidden;background:radial-gradient(circle at 50% 18%,#242019 0,#111316 34%,#0b0d10 72%)}
body:before{content:"";position:fixed;inset:auto 10vw 10vh;height:1px;background:linear-gradient(90deg,transparent,#c7a34b,transparent);opacity:.45}
.logo{width:78px!important;height:78px!important;border-radius:22px!important;display:grid!important;place-items:center!important;background:#15181b!important;border:1px solid rgba(199,163,75,.34)!important;color:#e3c977!important;font-weight:900!important;font-size:25px!important;box-shadow:0 22px 55px rgba(0,0,0,.35)!important}
h1{margin:18px 0 5px!important;font-size:25px!important;letter-spacing:-.045em!important}p{margin:0!important;color:#96928b!important;font-size:12px!important}
</style>'''
        text = text.replace("</head>", style + "\n</head>", 1)
    path.write_text(text, encoding="utf-8")


def install_tests() -> None:
    test = ROOT / "tests/test_ab_bau_apex_design_system.py"
    test.write_text(r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ABauApexDesignSystemTests(SimpleTestCase):
    def test_apex_is_loaded_from_main_shell(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        for marker in ("ab-apex", "ab-bau-apex.css?v=20260908-2", "ab-bau-apex.js?v=20260908-1", "ab-mobile-dock", "ab-mobile-wordmark", "data-ab-open-menu"):
            self.assertIn(marker, base)

    def test_apex_unifies_old_tooltime_and_mobile_surfaces(self):
        css = (ROOT / "static/css/ab-bau-apex.css").read_text(encoding="utf-8")
        for marker in ("A+BAU APEX DESIGN SYSTEM 2026-09-08", "--apex-gold:#c7a34b", ".ab-apex .nx-sidebar", ".tt-customer-page", ".tt-project-page", ".tt-document-page", ".tt-invoice-page", ".settings-sidebar", ".nx-job-address", ".ab-mobile-dock", "env(safe-area-inset-bottom)", "prefers-reduced-motion", ".rp-viewport"):
            self.assertIn(marker, css)

    def test_runtime_supports_mobile_dock(self):
        js = (ROOT / "static/js/ab-bau-apex.js").read_text(encoding="utf-8")
        for marker in ("A+BAU_APEX_RUNTIME_2026_09_08", "[data-ab-open-menu]", "is-scrolled", "abApexReady"):
            self.assertIn(marker, js)

    def test_apex_runs_after_previous_document_layers(self):
        unpack = (ROOT / "scripts/unpack-source.sh").read_text(encoding="utf-8")
        self.assertGreater(unpack.rfind("python3 scripts/ab_bau_apex_design_system.py"), unpack.rfind("python3 scripts/tooltime_document_workspace_regression_compat.py"))
''', encoding="utf-8")


install_assets()
patch_base()
patch_copy()
patch_native_shell()
install_tests()

base = require(BASE)
css = require(CSS_TARGET)
js = require(JS_TARGET)
for needle in ("ab-bau-apex.css?v=20260908-2", "ab-mobile-dock", "ab-mobile-wordmark", "ab-apex"):
    if needle not in base:
        raise RuntimeError(f"A+Bau Apex base guard missing: {needle}")
for needle in (MARKER, ".tt-customer-page", ".tt-document-page", ".ab-mobile-dock", "safe-area-inset-bottom"):
    if needle not in css:
        raise RuntimeError(f"A+Bau Apex CSS guard missing: {needle}")
if "A+BAU_APEX_RUNTIME_2026_09_08" not in js:
    raise RuntimeError("A+Bau Apex runtime guard missing")
print("A+Bau Apex installed: unified web, mobile web, native shell and ToolTime-derived surfaces.")
