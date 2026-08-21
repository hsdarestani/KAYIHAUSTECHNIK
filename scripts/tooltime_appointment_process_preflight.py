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
    if canonical_field not in detail:
        pattern = re.compile(
            r'<div class="nx-doc-section"[^>]*>\s*<div class="nx-grid nx-grid-2"[^>]*>.*?name="services".*?name="material".*?</div>\s*</div>',
            re.S,
        )
        detail, count = pattern.subn(canonical_field.rstrip(), detail, count=1)
        if count == 0:
            customer_pos = detail.find('name="customer_name"')
            if customer_pos >= 0:
                section_pos = detail.rfind('<div class="nx-doc-section', 0, customer_pos)
                if section_pos >= 0:
                    detail = detail[:section_pos] + canonical_field + detail[section_pos:]
        if canonical_field not in detail:
            raise RuntimeError("Appointment parity preflight: mobile documentation insertion anchor fehlt")
    module.write(detail_rel, detail)
