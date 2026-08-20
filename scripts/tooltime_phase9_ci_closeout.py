from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 9 CI CLOSEOUT 2026-08-20"


def run(module) -> None:
    views_rel = "erp/rebuild_views.py"
    views = module.read(views_rel)
    old_form = 'form = CustomerForm(request.POST or None, organization=org, initial=initial)'
    new_form = 'form = CustomerForm(request.POST if request.method == "POST" else None, organization=org, initial=initial)'
    if new_form not in views:
        if old_form not in views:
            raise RuntimeError("Phase 9 CI closeout customer binding anchor missing")
        views = views.replace(old_form, new_form, 1)
    module.write(views_rel, views)
    compile(views, str(ROOT / views_rel), "exec")

    project_rel = "templates/rebuild/project_form.html"
    project = module.read(project_rel)
    old_customer = '<div class="tt-field" data-select-search><label for="{{ form.customer.id_for_label }}">Kunde auswählen</label>{{ form.customer }}{{ form.customer.errors }}</div>'
    new_customer = '<div class="tt-field" data-select-search><label for="{{ form.customer.id_for_label }}">Kunde suchen</label>{{ form.customer }}{{ form.customer.errors }}<small>Kunde auswählen oder Suchbegriff eingeben.</small></div>'
    if new_customer not in project:
        if old_customer not in project:
            raise RuntimeError("Phase 9 CI closeout customer search anchor missing")
        project = project.replace(old_customer, new_customer, 1)
    module.write(project_rel, project)

    if 'request.POST if request.method == "POST" else None' not in module.read(views_rel):
        raise RuntimeError("Phase 9 CI closeout did not bind empty POSTs")
    if "Kunde suchen" not in module.read(project_rel):
        raise RuntimeError("Phase 9 CI closeout customer-search label missing")
    print(f"{MARKER}: empty POST validation and customer-search contract restored.")
