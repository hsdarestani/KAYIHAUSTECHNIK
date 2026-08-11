from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "templates" / "rebuild" / "project_form.html"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if "source_appointment" in text and "Projekt anlegen & Termin verbinden" in text:
        print("KAYI project recovery template already prepared.")
        return

    header_pattern = re.compile(
        r'<div class="nx-pagehead">.*?</div>\s*<form class="nx-form" method="post">\{% csrf_token %\}',
        re.S,
    )
    header = '''<div class="nx-pagehead"><div><div class="nx-kicker">{% if source_appointment %}Termin vervollständigen{% else %}Auftrag starten{% endif %}</div><h1>{% if source_appointment %}Projekt für „{{ source_appointment.title }}“ anlegen{% else %}Projekt anlegen{% endif %}</h1><p>{% if source_appointment %}Kunde und Grunddaten auswählen. Nach dem Speichern wird der Termin automatisch mit dem neuen Projekt verbunden.{% else %}Kunde, Auftrag und Team reichen für den Start – Aufmaß, Material, Angebot und Rechnung kommen danach im Projekt.{% endif %}</p></div></div>
{% if source_appointment %}<section class="nx-card nx-card-pad nx-link-context"><strong>Warum ist das nötig?</strong><p>Kundenfreigabe, Preise, Fotos, Zeiterfassung und Abschlussdokumentation gehören in KAYI zu einem Projekt. Du musst den Termin danach nicht noch einmal manuell verbinden.</p></section>{% endif %}
<form class="nx-form" method="post">{% csrf_token %}{% if source_appointment %}<input type="hidden" name="_appointment" value="{{ source_appointment.pk }}">{% endif %}'''
    text, count = header_pattern.subn(header, text, count=1)
    if count != 1:
        raise RuntimeError("Could not locate project form pagehead/form boundary")

    actions_pattern = re.compile(r'<div class="nx-form-actions">.*?</div>', re.S)
    actions = '''<div class="nx-form-actions"><a class="nx-btn" href="{% if source_appointment %}{% url 'next-appointment-detail' source_appointment.pk %}{% else %}{% url 'next-projects' %}{% endif %}">Abbrechen</a><button class="nx-btn nx-btn-accent" type="submit">{% if source_appointment %}Projekt anlegen & Termin verbinden →{% else %}Projekt anlegen →{% endif %}</button></div>'''
    text, count = actions_pattern.subn(actions, text, count=1)
    if count != 1:
        raise RuntimeError("Could not locate project form action row")

    PATH.write_text(text, encoding="utf-8")
    print("KAYI project recovery template prepared with tolerant DOM anchors.")


if __name__ == "__main__":
    main()
