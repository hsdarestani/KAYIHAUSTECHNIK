from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "templates/rebuild/base.html"
FIELD = ROOT / "templates/rebuild/field_home.html"
CSS_SOURCE = ROOT / "design/v3/ab-bau-v3-field.css"
CSS_TARGET = ROOT / "static/css/ab-bau-v3-field.css"
MARKER = "A+BAU V3 PHASE 1 FIELD COCKPIT 2026-09-08"


def read(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f"A+Bau V3 field target missing: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_css() -> None:
    CSS_TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CSS_SOURCE, CSS_TARGET)
    base = read(BASE)
    link = '<link rel="stylesheet" href="/static/css/ab-bau-v3-field.css?v=20260908-2">'
    if link not in base:
        if "</head>" not in base:
            raise RuntimeError("A+Bau V3 field CSS head anchor missing")
        base = base.replace("</head>", f"  {link}\n</head>", 1)
        write(BASE, base)


def install_field_template() -> None:
    write(FIELD, r'''{% extends 'rebuild/base.html' %}
{% block title %}Meine Einsätze · A+Bau{% endblock %}
{% block content %}
<div class="nx-field-shell ab-v3-field" data-ab-v3-field>
  <section class="ab-v3-field-hero">
    <div class="ab-v3-field-hero-top">
      <div><div class="ab-v3-field-eyebrow">Field Deck · Live</div><h1>Meine Einsätze</h1><p>{% if employee %}{{ employee.first_name }} {{ employee.last_name }} · {% endif %}Termine, Zeit und Dokumentation in einem klaren Arbeitsfluss.</p></div>
      <div class="ab-v3-field-time"><span>Jetzt</span><strong>{% now 'H:i' %}</strong></div>
    </div>
    <div class="ab-v3-field-counters">
      <div class="ab-v3-field-counter"><small>Geplant</small><strong>{{ planned|length }}</strong></div>
      <div class="ab-v3-field-counter is-warn"><small>Überfällig</small><strong>{{ overdue|length }}</strong></div>
      <div class="ab-v3-field-counter is-done"><small>Dokumentiert</small><strong>{{ documented|length }}</strong></div>
    </div>
  </section>

  <section class="ab-v3-next-job">
    <div class="ab-v3-next-label"><span>Nächster Einsatz</span><span>Priorität: jetzt</span></div>
    {% for event in planned|slice:':1' %}
    <a class="ab-v3-next-content" href="{% url 'next-appointment-detail' event.pk %}">
      <time class="ab-v3-next-time">{{ event.starts_at|date:'H:i' }}<small>{{ event.starts_at|date:'d.m.' }}</small></time>
      <span class="ab-v3-next-copy"><h2>{{ event.title }}</h2><p>{% if event.project %}{{ event.project.customer.display_name }} · {{ event.location|default:event.project.title }}{% else %}Interner Termin{% endif %}</p></span>
      <span class="ab-v3-next-arrow" aria-hidden="true">›</span>
    </a>
    {% empty %}<div class="nx-card nx-card-pad nx-empty ab-v3-field-empty"><strong>Kein Einsatz wartet.</strong>Neue Termine erscheinen automatisch hier.</div>{% endfor %}
  </section>

  <div data-tabs>
    <nav class="nx-mobile-tabs ab-v3-field-tabs" aria-label="Einsatzstatus">
      <button class="is-active" type="button" data-tab="planned">Geplant <b>{{ planned|length }}</b></button>
      <button type="button" data-tab="overdue">Überfällig <b>{{ overdue|length }}</b></button>
      <button type="button" data-tab="documented">Erledigt <b>{{ documented|length }}</b></button>
    </nav>

    <div class="nx-tab-panel ab-v3-field-panel is-active" data-tab-panel="planned">
      {% for event in planned %}<a class="nx-card nx-job-card ab-v3-field-job" href="{% url 'next-appointment-detail' event.pk %}"><time>{{ event.starts_at|date:'H:i' }}<small>{{ event.starts_at|date:'d.m.' }}</small></time><span class="ab-v3-field-job-copy"><strong>{{ event.title }}</strong><span>{% if event.project %}{{ event.project.customer.display_name }} · {{ event.location|default:event.project.title }}{% else %}Interner Termin{% endif %}</span></span><span class="ab-v3-field-job-state">Öffnen</span></a>{% empty %}<div class="nx-card nx-card-pad nx-empty ab-v3-field-empty"><strong>Keine geplanten Einsätze.</strong>Neue Termine erscheinen automatisch hier.</div>{% endfor %}
    </div>

    <div class="nx-tab-panel ab-v3-field-panel" data-tab-panel="overdue">
      {% for event in overdue %}<a class="nx-card nx-job-card ab-v3-field-job" href="{% url 'next-appointment-detail' event.pk %}"><time>{{ event.starts_at|date:'H:i' }}<small>{{ event.starts_at|date:'d.m.' }}</small></time><span class="ab-v3-field-job-copy"><strong>{{ event.title }}</strong><span>{% if event.project %}{{ event.project.customer.display_name }}{% endif %}</span></span><span class="ab-v3-field-job-state is-warn">Offen</span></a>{% empty %}<div class="nx-card nx-card-pad nx-empty ab-v3-field-empty"><strong>Alles erledigt.</strong>Keine überfällige Dokumentation.</div>{% endfor %}
    </div>

    <div class="nx-tab-panel ab-v3-field-panel" data-tab-panel="documented">
      {% for event in documented %}<a class="nx-card nx-job-card ab-v3-field-job" href="{% url 'next-appointment-detail' event.pk %}"><time>{{ event.starts_at|date:'H:i' }}<small>{{ event.starts_at|date:'d.m.' }}</small></time><span class="ab-v3-field-job-copy"><strong>{{ event.title }}</strong><span>{% if event.project %}{{ event.project.customer.display_name }}{% endif %}</span></span><span class="ab-v3-field-job-state is-done">✓ Dokumentiert</span></a>{% empty %}<div class="nx-card nx-card-pad nx-empty ab-v3-field-empty"><strong>Noch nichts dokumentiert.</strong>Abgeschlossene Einsätze landen automatisch hier.</div>{% endfor %}
    </div>
  </div>

  <div class="ab-v3-field-actions"><a href="{% url 'next-time' %}"><span>◷</span> Zeiterfassung</a><a href="{% url 'next-settings' %}">◎ Konto & Einstellungen</a></div>
</div>
{% endblock %}''')


def install_tests() -> None:
    test = ROOT / "tests/test_ab_bau_v3_field.py"
    write(test, r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ABauV3FieldTests(SimpleTestCase):
    def test_field_home_is_structurally_rebuilt_and_keeps_operational_data(self):
        template = (ROOT / "templates/rebuild/field_home.html").read_text(encoding="utf-8")
        for marker in ("data-ab-v3-field", "Field Deck", "Nächster Einsatz", "data-tabs", "nx-mobile-tabs", "nx-job-card", 'data-tab="planned"', 'data-tab-panel="overdue"', "planned", "overdue", "documented", "next-appointment-detail", "next-time"):
            self.assertIn(marker, template)
        self.assertNotIn("Nur Termine, Zeit und Dokumentation – ohne Büro-Menüs", template)

    def test_field_visuals_are_mobile_first(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        css = (ROOT / "static/css/ab-bau-v3-field.css").read_text(encoding="utf-8")
        self.assertIn("ab-bau-v3-field.css?v=20260908-2", base)
        for marker in ("A+BAU V3", ".ab-v3-field-hero", ".ab-v3-next-job", ".ab-v3-field-tabs", ".ab-v3-field-job", "safe-area-inset-bottom"):
            self.assertIn(marker, css)
''')


def guard() -> None:
    base = read(BASE)
    field = read(FIELD)
    css = read(CSS_TARGET)
    if "ab-bau-v3-field.css?v=20260908-2" not in base:
        raise RuntimeError("A+Bau V3 field stylesheet is not loaded")
    for marker in ("data-ab-v3-field", "Nächster Einsatz", "data-tabs", "nx-mobile-tabs", "nx-job-card", "next-appointment-detail", "next-time"):
        if marker not in field:
            raise RuntimeError(f"A+Bau V3 field contract missing: {marker}")
    if "A+BAU V3" not in css:
        raise RuntimeError("A+Bau V3 field CSS guard missing")


def main() -> None:
    install_css()
    install_field_template()
    install_tests()
    guard()
    print(f"{MARKER}: field app home structurally rebuilt while appointment/time/documentation flows remain unchanged.")


if __name__ == "__main__":
    main()
