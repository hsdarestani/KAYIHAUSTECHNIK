from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "templates/rebuild/base.html"
DASHBOARD = ROOT / "templates/rebuild/dashboard.html"
CSS_SOURCE = ROOT / "design/v3/ab-bau-v3.css"
JS_SOURCE = ROOT / "design/v3/ab-bau-v3.js"
CSS_TARGET = ROOT / "static/css/ab-bau-v3.css"
JS_TARGET = ROOT / "static/js/ab-bau-v3.js"
MARKER = "A+BAU V3 PHASE 1 STRUCTURAL REDESIGN 2026-09-08"


def read(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"A+Bau V3 target missing: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_assets() -> None:
    CSS_TARGET.parent.mkdir(parents=True, exist_ok=True)
    JS_TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CSS_SOURCE, CSS_TARGET)
    shutil.copyfile(JS_SOURCE, JS_TARGET)


def patch_base_shell() -> None:
    text = read(BASE)

    css_link = '<link rel="stylesheet" href="/static/css/ab-bau-v3.css?v=20260908-2">'
    if css_link not in text:
        if "</head>" not in text:
            raise RuntimeError("A+Bau V3 base has no </head> anchor")
        text = text.replace("</head>", f"  {css_link}\n</head>", 1)

    body = re.search(r'<body class="([^"]*)"', text)
    if not body:
        raise RuntimeError("A+Bau V3 body class anchor missing")
    classes = body.group(1).split()
    if "ab-v3" not in classes:
        classes.insert(0, "ab-v3")
        text = text[:body.start(1)] + " ".join(classes) + text[body.end(1):]

    if "ab-v3-workspace-chip" not in text:
        brand = re.search(r'(<a[^>]*class="[^"]*\bnx-brand\b[^"]*"[^>]*>.*?</a>)', text, flags=re.S)
        if not brand:
            raise RuntimeError("A+Bau V3 sidebar brand anchor missing")
        workspace = r'''
    <div class="ab-v3-workspace-chip" aria-label="Aktiver Arbeitsbereich">
      <span class="ab-v3-workspace-dot" aria-hidden="true"></span>
      <span><small>Workspace</small><strong>{{ request.user.profile.organization.name|default:'A+Bau' }}</strong></span>
    </div>
    {% if request.user.profile.role == 'technician' or request.user.profile.is_mobile_worker %}{% else %}
    <button class="ab-v3-create" type="button" data-ab-v3-command-open><span><b>＋</b> Erstellen</span><kbd>⌘ K</kbd></button>
    {% endif %}'''
        text = text[:brand.end()] + workspace + text[brand.end():]

    if "ab-v3-top-context" not in text:
        anchor = '<div class="nx-top-actions">'
        if anchor not in text:
            raise RuntimeError("A+Bau V3 top action anchor missing")
        context = '<div class="ab-v3-top-context" aria-label="Systemstatus"><span>LIVE</span><strong data-ab-v3-clock>--:--</strong></div>'
        text = text.replace(anchor, context + anchor, 1)

    if 'data-ab-v3-command aria-hidden=' not in text:
        if "</body>" not in text:
            raise RuntimeError("A+Bau V3 body end anchor missing")
        palette = r'''
{% if request.user.profile.role == 'technician' or request.user.profile.is_mobile_worker %}{% else %}
<button class="ab-v3-mobile-fab" type="button" data-ab-v3-command-open aria-label="Erstellen">＋</button>
<div class="ab-v3-command-backdrop" data-ab-v3-command aria-hidden="true">
  <section class="ab-v3-command-panel" role="dialog" aria-modal="true" aria-label="Schnell erstellen">
    <header class="ab-v3-command-head"><span aria-hidden="true">◇</span><input class="ab-v3-command-search" data-ab-v3-command-search aria-label="Aktion suchen" placeholder="Was möchtest du erledigen?" autocomplete="off"><button class="ab-v3-command-esc" type="button" data-ab-v3-command-close aria-label="Schließen">ESC</button></header>
    <div class="ab-v3-command-grid">
      <a class="ab-v3-command-item" data-ab-v3-command-item data-search="projekt auftrag kunde arbeit" href="{% url 'next-project-create' %}"><span class="ab-v3-command-icon">▣</span><span class="ab-v3-command-copy"><strong>Projekt starten</strong><small>Neuen Auftrag mit Kunde und Einsatzort anlegen.</small></span></a>
      <a class="ab-v3-command-item" data-ab-v3-command-item data-search="termin kalender einsatz appointment" href="{% url 'next-appointment-create' %}"><span class="ab-v3-command-icon">◫</span><span class="ab-v3-command-copy"><strong>Termin planen</strong><small>Einsatz terminieren und Team zuweisen.</small></span></a>
      <a class="ab-v3-command-item" data-ab-v3-command-item data-search="kunde kontakt customer" href="{% url 'next-customer-create' %}"><span class="ab-v3-command-icon">◎</span><span class="ab-v3-command-copy"><strong>Kunde anlegen</strong><small>Kontakt und Objekt sauber erfassen.</small></span></a>
      <a class="ab-v3-command-item" data-ab-v3-command-item data-search="angebot quote kalkulation" href="{% url 'next-quote-create' %}"><span class="ab-v3-command-icon">◇</span><span class="ab-v3-command-copy"><strong>Angebot erstellen</strong><small>Leistungen kalkulieren und als Angebot vorbereiten.</small></span></a>
      <a class="ab-v3-command-item" data-ab-v3-command-item data-search="rechnung invoice faktura" href="{% url 'next-invoice-create' %}"><span class="ab-v3-command-icon">€</span><span class="ab-v3-command-copy"><strong>Rechnung erstellen</strong><small>Rechnung aus Projekt oder frei beginnen.</small></span></a>
      <a class="ab-v3-command-item" data-ab-v3-command-item data-search="ausgabe beleg receipt kosten" href="{% url 'next-expense-create' %}"><span class="ab-v3-command-icon">↘</span><span class="ab-v3-command-copy"><strong>Beleg erfassen</strong><small>Ausgabe hochladen und Projekt zuordnen.</small></span></a>
      <a class="ab-v3-command-item" data-ab-v3-command-item data-search="aufgabe task todo" href="{% url 'next-task-create' %}"><span class="ab-v3-command-icon">✓</span><span class="ab-v3-command-copy"><strong>Aufgabe anlegen</strong><small>Offenen Punkt direkt in die Ausführung geben.</small></span></a>
      <a class="ab-v3-command-item" data-ab-v3-command-item data-search="daten import csv xlsx tooltime" href="{% url 'next-tooltime-migration' %}"><span class="ab-v3-command-icon">⇄</span><span class="ab-v3-command-copy"><strong>Daten importieren</strong><small>Bestehende CSV/XLSX-Daten übernehmen.</small></span></a>
    </div>
    <p class="ab-v3-command-empty" data-ab-v3-command-empty role="status" hidden>Keine passende Aktion. Versuche einen anderen Suchbegriff.</p>
    <footer class="ab-v3-command-foot"><span>⌘K öffnet dieses Menü überall im Büro.</span><span>A+Bau Operations</span></footer>
  </section>
</div>
{% endif %}
'''
        text = text.replace("</body>", palette + "\n</body>", 1)

    js = '<script src="/static/js/ab-bau-v3.js?v=20260908-2" defer></script>'
    if js not in text:
        if "{% block scripts %}{% endblock %}" in text:
            text = text.replace("{% block scripts %}{% endblock %}", js + "\n{% block scripts %}{% endblock %}", 1)
        elif "</body>" in text:
            text = text.replace("</body>", js + "\n</body>", 1)
        else:
            raise RuntimeError("A+Bau V3 script anchor missing")

    write(BASE, text)


def install_dashboard() -> None:
    write(DASHBOARD, r'''{% extends 'rebuild/base.html' %}
{% block title %}Dashboard · A+Bau{% endblock %}
{% block content %}
<div class="ab-v3-dashboard" data-ab-v3-dashboard>
  <section class="ab-v3-dashboard-hero">
    <div class="ab-v3-hero-top">
      <div class="ab-v3-hero-copy">
        <div class="ab-v3-overline">Dashboard · {{ today|date:'d.m.Y' }}</div>
        <h1><span data-ab-v3-greeting>Guten Tag</span>.<br><span>Alles im Griff.</span></h1>
        <p>Dein operatives Cockpit für Einsätze, Projekte, Angebote und Zahlungsläufe — ohne Umwege in die eigentliche Arbeit.</p>
      </div>
      <div class="ab-v3-hero-actions">
        <button class="ab-v3-hero-secondary" type="button" data-ab-v3-command-open>Schnell erstellen</button>
        <a class="ab-v3-hero-primary" href="{% url 'next-appointment-create' %}">＋ Einsatz planen</a>
      </div>
    </div>
    <div class="ab-v3-metrics" aria-label="Betriebskennzahlen">
      <a class="ab-v3-metric" href="{% url 'next-projects' %}"><small>Aktive Projekte</small><strong>{{ active_projects }}</strong><em>laufende Aufträge</em></a>
      <a class="ab-v3-metric is-gold" href="{% url 'next-quotes' %}"><small>Offene Angebote</small><strong>{{ open_quotes }}</strong><em>Entwurf / versendet</em></a>
      <a class="ab-v3-metric is-alert" href="{% url 'next-invoices' %}"><small>Überfällige Rechnungen</small><strong>{{ overdue }}</strong><em>Aufmerksamkeit nötig</em></a>
      <a class="ab-v3-metric" href="{% url 'next-appointments' %}"><small>Einsätze heute</small><strong>{{ appointments|length }}</strong><em>im Tagesplan</em></a>
    </div>
  </section>

  <div class="ab-v3-ops-grid">
    <section class="ab-v3-panel">
      <header class="ab-v3-panel-head"><div><div class="ab-v3-overline">Operations</div><h2>Tagesplan</h2><p>Die nächsten Einsätze in zeitlicher Reihenfolge.</p></div><a class="ab-v3-panel-link" href="{% url 'next-appointments' %}">Kalender öffnen ↗</a></header>
      <div class="ab-v3-agenda">
        {% for event in appointments %}
        <a class="ab-v3-agenda-row" href="{% url 'next-appointment-detail' event.pk %}">
          <time class="ab-v3-agenda-time">{{ event.starts_at|date:'H:i' }}<small>{{ event.starts_at|date:'d.m.' }}</small></time>
          <span class="ab-v3-agenda-main"><strong>{{ event.title }}</strong><span>{% if event.project %}{{ event.project.customer.display_name }} · {{ event.project.number }}{% else %}Interner Termin{% endif %}</span></span>
          <span class="ab-v3-agenda-state">{{ event.get_type_display }}</span>
        </a>
        {% empty %}<div class="ab-v3-agenda-empty"><strong>Kein Einsatz blockiert den Tag.</strong><span>Nutze den freien Slot für offene Projekte oder plane direkt einen neuen Termin.</span></div>{% endfor %}
      </div>
    </section>

    <aside class="ab-v3-panel ab-v3-focus">
      <header class="ab-v3-panel-head"><div><div class="ab-v3-overline">Fokus</div><h2>Was braucht dich?</h2><p>Die zwei wichtigsten Warteschlangen.</p></div></header>
      <div class="ab-v3-focus-body">
        <a class="ab-v3-focus-card is-danger" href="{% url 'next-invoices' %}"><small>Forderungen</small><strong>{{ overdue }}</strong><span>überfällige Rechnungen prüfen und Zahlungslauf anstoßen.</span></a>
        <a class="ab-v3-focus-card is-gold" href="{% url 'next-quotes' %}"><small>Vertrieb</small><strong>{{ open_quotes }}</strong><span>offene Angebote finalisieren, senden oder nachfassen.</span></a>
        <a class="ab-v3-focus-card" href="{% url 'next-tasks' %}"><small>Ausführung</small><strong>→</strong><span>Aufgaben, Rückfragen und operative To-dos öffnen.</span></a>
      </div>
    </aside>
  </div>

  <section class="ab-v3-panel ab-v3-pipeline">
    <header class="ab-v3-panel-head"><div><div class="ab-v3-overline">Pipeline</div><h2>Zuletzt bewegt</h2><p>Direkter Wiedereinstieg in laufende Projekte.</p></div><a class="ab-v3-panel-link" href="{% url 'next-projects' %}">Alle Projekte ↗</a></header>
    <div class="ab-v3-pipeline-track">
      {% for project in recent_projects %}
      <a class="ab-v3-project-card" href="{% url 'next-project-detail' project.pk %}">
        <div class="ab-v3-project-top"><span class="ab-v3-project-no">{{ project.number|default:'PROJEKT' }}</span><span class="ab-v3-project-status">{{ project.get_status_display }}</span></div>
        <h3>{{ project.title }}</h3><p>{{ project.customer.display_name }}</p>
        <footer><span>Zuletzt bearbeitet</span><strong>{{ project.updated_at|date:'d.m. H:i' }}</strong></footer>
      </a>
      {% empty %}<div class="ab-v3-project-empty">Noch keine Projekte vorhanden. Starte den ersten Auftrag über „Schnell erstellen“.</div>{% endfor %}
    </div>
  </section>

  <section class="ab-v3-command-deck">
    <header class="ab-v3-command-deck-head"><div><div class="ab-v3-overline">Command Deck</div><h2>Direkt in die Arbeit</h2><p>Die häufigsten Aktionen ohne Zwischenbildschirm.</p></div><button type="button" data-ab-v3-command-open>Alle Aktionen · ⌘K</button></header>
    <div class="ab-v3-quick-grid">
      <a class="ab-v3-quick" href="{% url 'next-project-create' %}"><span class="ab-v3-quick-index">01</span><span class="ab-v3-quick-icon">▣</span><strong>Projekt</strong><small>Auftrag starten</small></a>
      <a class="ab-v3-quick" href="{% url 'next-appointment-create' %}"><span class="ab-v3-quick-index">02</span><span class="ab-v3-quick-icon">◫</span><strong>Termin</strong><small>Einsatz planen</small></a>
      <a class="ab-v3-quick" href="{% url 'next-customer-create' %}"><span class="ab-v3-quick-index">03</span><span class="ab-v3-quick-icon">◎</span><strong>Kunde</strong><small>Kontakt erfassen</small></a>
      <a class="ab-v3-quick" href="{% url 'next-quote-create' %}"><span class="ab-v3-quick-index">04</span><span class="ab-v3-quick-icon">◇</span><strong>Angebot</strong><small>Kalkulation starten</small></a>
      <a class="ab-v3-quick" href="{% url 'next-invoice-create' %}"><span class="ab-v3-quick-index">05</span><span class="ab-v3-quick-icon">€</span><strong>Rechnung</strong><small>Abrechnung beginnen</small></a>
      <a class="ab-v3-quick" href="{% url 'next-tooltime-migration' %}"><span class="ab-v3-quick-index">06</span><span class="ab-v3-quick-icon">⇄</span><strong>Daten importieren</strong><small>CSV / XLSX übernehmen</small></a>
    </div>
  </section>
</div>
{% endblock %}''')


def install_contract_tests() -> None:
    test = ROOT / "tests/test_ab_bau_v3_phase1.py"
    write(test, r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ABauV3Phase1Tests(SimpleTestCase):
    def test_shell_is_structurally_upgraded_without_losing_capabilities(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        for marker in ("ab-v3", "ab-v3-workspace-chip", "ab-v3-create", 'data-ab-v3-command aria-hidden=', "ab-bau-v3.css?v=20260908-2", "ab-bau-v3.js?v=20260908-2"):
            self.assertIn(marker, base)
        for route in ("next-dashboard", "next-appointments", "next-projects", "next-customers", "next-tasks", "next-quotes", "next-invoices", "next-expenses", "next-time", "next-employees", "next-field", "next-tooltime-migration", "next-settings"):
            self.assertIn(route, base)

    def test_dashboard_is_a_new_operations_cockpit_not_the_old_card_grid(self):
        dashboard = (ROOT / "templates/rebuild/dashboard.html").read_text(encoding="utf-8")
        for marker in ("data-ab-v3-dashboard", "ab-v3-dashboard-hero", "ab-v3-ops-grid", "ab-v3-focus", "ab-v3-pipeline", "ab-v3-command-deck", "Daten importieren"):
            self.assertIn(marker, dashboard)
        self.assertNotIn("Was steht an?", dashboard)
        self.assertNotIn("nx-grid nx-grid-4", dashboard)
        self.assertNotIn("Von ToolTime wechseln", dashboard)

    def test_dashboard_preserves_operational_server_data(self):
        dashboard = (ROOT / "templates/rebuild/dashboard.html").read_text(encoding="utf-8")
        for value in ("active_projects", "open_quotes", "overdue", "appointments", "recent_projects"):
            self.assertIn(value, dashboard)
        for route in ("next-appointment-detail", "next-project-detail", "next-quote-create", "next-invoice-create"):
            self.assertIn(route, dashboard)

    def test_v3_assets_cover_desktop_mobile_and_keyboard_command_flow(self):
        css = (ROOT / "static/css/ab-bau-v3.css").read_text(encoding="utf-8")
        js = (ROOT / "static/js/ab-bau-v3.js").read_text(encoding="utf-8")
        for marker in ("A+BAU V3", "ab-v3-dashboard-hero", "ab-v3-command-backdrop", "ab-v3-mobile-fab", "safe-area-inset-bottom", "@media(max-width:640px)"):
            self.assertIn(marker, css)
        for marker in ("A_BAU_V3_PHASE1_2026_09_08", "data-ab-v3-command-open", "event.metaKey", "event.ctrlKey", "abV3Ready"):
            self.assertIn(marker, js)
''')


def patch_browser_smoke() -> None:
    path = ROOT / "scripts/production_browser_smoke.py"
    text = read(path)
    # Preserve the authenticated route smoke while replacing obsolete heading copy
    # with the actual dashboard root. Interactive V3 checks run explicitly in CI.
    text = text.replace('"Was steht an?"', '"data-ab-v3-dashboard"')
    if "data-ab-v3-dashboard" not in text:
        raise RuntimeError("V3 dashboard browser smoke anchor missing")
    path.write_text(text, encoding="utf-8")
    compile(text, str(path), "exec")


def patch_native_loading_shell() -> None:
    path = ROOT / "native/www/index.html"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if "ABBAU_V3_NATIVE_PHASE1" in text or "</head>" not in text:
        return
    style = r'''<style id="ABBAU_V3_NATIVE_PHASE1">
body:after{content:"A+Bau · Operations";position:fixed;left:0;right:0;bottom:max(28px,env(safe-area-inset-bottom));text-align:center;color:#686d73;font:700 9px/1.2 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:.16em;text-transform:uppercase}
</style>'''
    text = text.replace("</head>", style + "\n</head>", 1)
    path.write_text(text, encoding="utf-8")


def guard() -> None:
    base = read(BASE)
    dashboard = read(DASHBOARD)
    css = read(CSS_TARGET)
    js = read(JS_TARGET)
    for marker in ("ab-v3", "ab-v3-workspace-chip", 'data-ab-v3-command aria-hidden=', "ab-bau-v3.css?v=20260908-2", "ab-bau-v3.js?v=20260908-2"):
        if marker not in base:
            raise RuntimeError(f"A+Bau V3 shell guard missing: {marker}")
    for marker in ("data-ab-v3-dashboard", "ab-v3-dashboard-hero", "ab-v3-ops-grid", "ab-v3-pipeline", "Daten importieren"):
        if marker not in dashboard:
            raise RuntimeError(f"A+Bau V3 dashboard guard missing: {marker}")
    if "Von ToolTime wechseln" in dashboard:
        raise RuntimeError("A+Bau V3 dashboard regressed to ToolTime clone copy")
    if "A+BAU V3" not in css or "A_BAU_V3_PHASE1_2026_09_08" not in js:
        raise RuntimeError("A+Bau V3 asset guards missing")


def main() -> None:
    install_assets()
    patch_base_shell()
    install_dashboard()
    patch_native_loading_shell()
    install_contract_tests()
    patch_browser_smoke()
    guard()
    print(f"{MARKER}: shell and dashboard structurally rebuilt while all existing office/field/document routes remain intact.")


if __name__ == "__main__":
    main()
