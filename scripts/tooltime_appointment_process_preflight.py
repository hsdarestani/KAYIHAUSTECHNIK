from __future__ import annotations

import re


def run(module) -> None:
    form_rel = "templates/rebuild/appointment_form.html"
    form = module.read(form_rel)
    compatibility = '<section class="tt-appt-card tt-appt-after-save" data-after-save aria-label="Nach dem Speichern">'
    canonical = '<section class="tt-appt-card tt-appt-after-save">'
    if compatibility in form:
        form = form.replace(compatibility, canonical, 1)
    module.write(form_rel, form)

    detail_rel = "templates/rebuild/appointment_detail.html"
    detail = module.read(detail_rel)
    canonical_field = '''      <div class="nx-doc-section">
        <div class="nx-grid nx-grid-2">
          <div class="nx-field"><label>Leistungen</label><textarea class="nx-control" name="services" placeholder="Ausgeführte Arbeiten"></textarea></div>
          <div class="nx-field"><label>Material</label><textarea class="nx-control" name="material" placeholder="Verwendetes Material"></textarea></div>
        </div>
      </div>
'''
    if "data-field-services" not in detail and canonical_field not in detail:
        # The active KAYI technician flow is the signed Field-Authorization
        # completion form. Normalize only its two free-text completion fields so
        # the ToolTime service editor can replace them without destroying the
        # surrounding authorization -> work -> completion workflow.
        field_pattern = re.compile(
            r'\s*<div class="fa-grid-2">\s*<label class="fa-field"><span>Ausgeführte Leistungen</span><textarea[^>]*name="services".*?</textarea></label>\s*<label class="fa-field"><span>Material</span><textarea[^>]*name="material".*?</textarea></label>\s*</div>',
            re.S,
        )
        detail, count = field_pattern.subn("\n" + canonical_field.rstrip(), detail, count=1)
        if count == 0:
            # Compatibility with the older, simpler appointment documentation
            # template if a deployment still assembles that variant.
            legacy_pattern = re.compile(
                r'<div class="nx-doc-section"[^>]*>\s*<div class="nx-grid nx-grid-2"[^>]*>.*?name="services".*?name="material".*?</div>\s*</div>',
                re.S,
            )
            detail, count = legacy_pattern.subn(canonical_field.rstrip(), detail, count=1)
        if count == 0 or canonical_field not in detail:
            raise RuntimeError("Appointment parity preflight: completion service fields anchor fehlt")
    module.write(detail_rel, detail)
