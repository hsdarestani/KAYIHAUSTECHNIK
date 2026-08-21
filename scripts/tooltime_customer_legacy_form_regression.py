from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU CUSTOMER LEGACY FORM REGRESSION 2026-08-21"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Customer legacy regression target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


# Empty POST QueryDicts are falsy. Using `request.POST or None` therefore turned
# an intentionally invalid empty submit back into an unbound form and hid all
# validation feedback. Keep POST forms bound even when the payload is empty.
views_rel = "erp/rebuild_views.py"
views = read(views_rel)
customer_create_match = re.search(
    r'@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef customer_create\(request\):.*?(?=\n\n@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef customer_detail)',
    views,
    re.S,
)
if not customer_create_match:
    raise RuntimeError("Customer create regression anchor changed")
block = customer_create_match.group(0)
block = block.replace(
    "        request.POST or None,\n        organization=org,",
    "        request.POST if request.method == \"POST\" else None,\n        organization=org,",
    1,
)
# The optional Einsatzort must stay unbound unless the user actually starts it;
# otherwise an empty customer POST would surface unrelated required site errors.
block = block.replace(
    '    location_form = ObjectLocationForm(request.POST or None, prefix="site")',
    '    location_payload = request.POST if request.method == "POST" and str(request.POST.get("site-street") or "").strip() else None\n    location_form = ObjectLocationForm(location_payload, prefix="site")',
    1,
)
views = views[: customer_create_match.start()] + block + views[customer_create_match.end() :]
write(views_rel, views)

# Preserve the ToolTime progressive layout but keep the exact German wording and
# error-summary hook used by the established customer regression/browser contracts.
template_rel = "templates/rebuild/customer_form.html"
template = read(template_rel)
old_loop = '''{% for field in location_form %}<div class="tt-field {% if field.name == 'access_notes' or field.name == 'street' %}tt-span-2{% endif %}"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{{ field.errors }}</div>{% endfor %}'''
old_loop_v2 = '''{% for field in location_form %}<div class="tt-field {% if field.name == 'access_notes' or field.name == 'street' %}tt-span-2{% endif %}"><label for="{{ field.id_for_label }}">{% if field.name == 'floor' %}Etage{% elif field.name == 'access_notes' %}Zugangshinweise{% else %}{{ field.label }}{% endif %}</label>{{ field }}{{ field.errors }}</div>{% endfor %}'''
new_loop = '''{% for field in location_form %}<div class="tt-field {% if field.name == 'access_notes' or field.name == 'street' %}tt-span-2{% endif %}"><label for="{{ field.id_for_label }}">{% if field.name == 'floor' %}Etage{% elif field.name == 'access_notes' %}Hinweise zum Zugang{% else %}{{ field.label }}{% endif %}</label>{{ field }}{{ field.errors }}</div>{% endfor %}'''
if old_loop in template:
    template = template.replace(old_loop, new_loop, 1)
elif old_loop_v2 in template:
    template = template.replace(old_loop_v2, new_loop, 1)
elif "Hinweise zum Zugang" not in template:
    raise RuntimeError("Customer Einsatzort field-label anchor changed")

alert = '<div class="tt-form-alert" role="alert">'
alert_with_hook = '<div class="tt-form-alert" role="alert" data-form-error-summary>'
if alert in template:
    template = template.replace(alert, alert_with_hook, 1)
elif "data-form-error-summary" not in template:
    raise RuntimeError("Customer validation summary anchor changed")
write(template_rel, template)

final_views = read(views_rel)
final_template = read(template_rel)
for needle in (
    'request.POST if request.method == "POST" else None',
    'location_payload = request.POST if request.method == "POST"',
):
    if needle not in final_views:
        raise RuntimeError(f"Customer bound-POST regression fix missing: {needle}")
for needle in ("Etage", "Hinweise zum Zugang", "Kunde konnte nicht gespeichert werden.", "data-form-error-summary"):
    if needle not in final_template:
        raise RuntimeError(f"Customer German validation regression fix missing: {needle}")

print(f"{MARKER}: empty POST validation, German Einsatzort labels and error summary hook restored.")
