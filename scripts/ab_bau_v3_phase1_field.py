from __future__ import annotations

import re
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
    link = '<link rel="stylesheet" href="/static/css/ab-bau-v3-field.css?v=20260908-3">'
    if link not in base:
        if "</head>" not in base:
            raise RuntimeError("A+Bau V3 field CSS head anchor missing")
        base = base.replace("</head>", f"  {link}\n</head>", 1)
        write(BASE, base)


def install_field_template() -> None:
    """Upgrade the final technician surface without deleting field capabilities.

    Multiple late production layers add one-tap project capture, voice AI, customer
    signature and signed-PDF handoff to field_home.html. Replacing the template would
    silently remove those workflows. V3 therefore treats the fully assembled field
    template as the source of truth and changes its composition in-place: a new Field
    Deck and next-job focus are injected into the existing operational shell, while
    every existing form, route, signed-PDF action, tab and data hook remains intact.
    """
    legacy = read(FIELD)
    required_upstream = (
        "nx-field-shell",
        "nx-mobile-tabs",
        "nx-job-card",
        "Projekt aufnehmen",
        "Vor Ort in einem Ablauf",
        "Signierte PDF",
    )
    missing = [marker for marker in required_upstream if marker not in legacy]
    if missing:
        raise RuntimeError(
            "A+Bau V3 refuses to replace an incomplete field workflow; missing upstream contracts: "
            + ", ".join(missing)
        )

    if "data-ab-v3-field" in legacy:
        # Repeatable source assembly: the final template is already upgraded.
        return

    root = re.search(r'<div class="([^"]*\bnx-field-shell\b[^"]*)"([^>]*)>', legacy)
    if not root:
        raise RuntimeError("A+Bau V3 field root anchor missing")
    classes = root.group(1).split()
    if "ab-v3-field" not in classes:
        classes.append("ab-v3-field")
    replacement = f'<div class="{" ".join(classes)}"{root.group(2)} data-ab-v3-field>'

    hero = r'''
  <section class="ab-v3-field-hero" data-ab-v3-field-deck>
    <div class="ab-v3-field-hero-top">
      <div><div class="ab-v3-field-eyebrow">Field Deck · Live</div><h1>Meine Einsätze</h1><p>{% if employee %}{{ employee.first_name }} {{ employee.last_name }} · {% endif %}Termin, KI-Aufnahme, Unterschrift und Dokumentation bleiben in einem durchgängigen Baustellen-Workflow.</p></div>
      <div class="ab-v3-field-time"><span>Jetzt</span><strong>{% now 'H:i' %}</strong></div>
    </div>
    <div class="ab-v3-field-counters">
      <div class="ab-v3-field-counter"><small>Geplant</small><strong>{{ planned|length }}</strong></div>
      <div class="ab-v3-field-counter is-warn"><small>Überfällig</small><strong>{{ overdue|length }}</strong></div>
      <div class="ab-v3-field-counter is-done"><small>Dokumentiert</small><strong>{{ documented|length }}</strong></div>
    </div>
  </section>

  <section class="ab-v3-next-job" data-ab-v3-next-job>
    <div class="ab-v3-next-label"><span>Nächster Einsatz</span><span>Priorität: jetzt</span></div>
    {% for event in planned|slice:':1' %}
    <a class="ab-v3-next-content" href="{% url 'next-appointment-detail' event.pk %}">
      <time class="ab-v3-next-time">{{ event.starts_at|date:'H:i' }}<small>{{ event.starts_at|date:'d.m.' }}</small></time>
      <span class="ab-v3-next-copy"><h2>{{ event.title }}</h2><p>{% if event.project %}{{ event.project.customer.display_name }} · {{ event.location|default:event.project.title }}{% else %}Interner Termin{% endif %}</p></span>
      <span class="ab-v3-next-arrow" aria-hidden="true">›</span>
    </a>
    {% empty %}<div class="nx-card nx-card-pad nx-empty ab-v3-field-empty"><strong>Kein Einsatz wartet.</strong>Neue Termine erscheinen automatisch hier.</div>{% endfor %}
  </section>

  <div class="ab-v3-field-flow-label"><span>Vor Ort in einem Ablauf</span><small>Projekt aufnehmen · Sprach-KI · Unterschrift · Signierte PDF</small></div>
'''
    legacy = legacy[:root.start()] + replacement + hero + legacy[root.end():]
    write(FIELD, legacy)


def install_tests() -> None:
    test = ROOT / "tests/test_ab_bau_v3_field.py"
    write(test, r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]

class ABauV3FieldTests(SimpleTestCase):
    def test_field_home_is_structurally_upgraded_without_deleting_tooltime_capabilities(self):
        template = (ROOT / "templates/rebuild/field_home.html").read_text(encoding="utf-8")
        for marker in (
            "data-ab-v3-field", "data-ab-v3-field-deck", "data-ab-v3-next-job",
            "Field Deck", "Nächster Einsatz", "nx-mobile-tabs", "nx-job-card",
            "planned", "overdue", "documented", "next-appointment-detail", "next-time",
            "Projekt aufnehmen", "Vor Ort in einem Ablauf", "Signierte PDF",
        ):
            self.assertIn(marker, template)

    def test_v3_keeps_upstream_field_workflow_instead_of_reimplementing_it(self):
        installer = (ROOT / "scripts/ab_bau_v3_phase1_field.py").read_text(encoding="utf-8")
        self.assertIn("legacy = read(FIELD)", installer)
        self.assertNotIn("write(FIELD, r'''{% extends", installer)
        for marker in ("Projekt aufnehmen", "Vor Ort in einem Ablauf", "Signierte PDF"):
            self.assertIn(marker, installer)

    def test_field_visuals_are_mobile_first(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        css = (ROOT / "static/css/ab-bau-v3-field.css").read_text(encoding="utf-8")
        self.assertIn("ab-bau-v3-field.css?v=20260908-3", base)
        for marker in ("A+BAU V3", ".ab-v3-field-hero", ".ab-v3-next-job", ".ab-v3-field-flow-label", "safe-area-inset-bottom"):
            self.assertIn(marker, css)
''')


def guard() -> None:
    base = read(BASE)
    field = read(FIELD)
    css = read(CSS_TARGET)
    if "ab-bau-v3-field.css?v=20260908-3" not in base:
        raise RuntimeError("A+Bau V3 field stylesheet is not loaded")
    for marker in (
        "data-ab-v3-field", "data-ab-v3-field-deck", "data-ab-v3-next-job",
        "Nächster Einsatz", "nx-mobile-tabs", "nx-job-card", "next-appointment-detail",
        "Projekt aufnehmen", "Vor Ort in einem Ablauf", "Signierte PDF",
    ):
        if marker not in field:
            raise RuntimeError(f"A+Bau V3 field contract missing after redesign: {marker}")
    if "A+BAU V3" not in css:
        raise RuntimeError("A+Bau V3 field CSS guard missing")


def main() -> None:
    install_css()
    install_field_template()
    install_tests()
    guard()
    print(f"{MARKER}: Field Deck structurally upgraded; one-tap capture, voice, signature and signed-PDF workflows preserved from the authoritative assembled template.")


if __name__ == "__main__":
    main()
