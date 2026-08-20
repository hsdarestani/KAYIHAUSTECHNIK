from __future__ import annotations


def run(module) -> None:
    rel = "templates/rebuild/appointment_form.html"
    text = module.read(rel)
    old = '<section class="tt-appt-card tt-appt-after-save">'
    new = '<section class="tt-appt-card tt-appt-after-save" data-after-save aria-label="Nach dem Speichern">'
    if "Nach dem Speichern" not in text:
        if old not in text:
            raise RuntimeError("Phase 10 CI closeout after-save anchor missing")
        text = text.replace(old, new, 1)
    module.write(rel, text)
    if "Nach dem Speichern" not in module.read(rel):
        raise RuntimeError("Phase 10 CI closeout marker missing")
    print("A+BAU TOOLTIME PHASE 10 CI CLOSEOUT: post-save UX contract aligned.")
