from __future__ import annotations


def run(module) -> None:
    rel = "templates/rebuild/appointment_form.html"
    text = module.read(rel)
    compatibility = '<section class="tt-appt-card tt-appt-after-save" data-after-save aria-label="Nach dem Speichern">'
    canonical = '<section class="tt-appt-card tt-appt-after-save">'
    if compatibility in text:
        text = text.replace(compatibility, canonical, 1)
    module.write(rel, text)
