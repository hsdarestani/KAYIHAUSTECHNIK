from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Customer parity fix target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


template_path = "templates/rebuild/customers.html"
template = read(template_path)
private_duplicate = '''          <div class="tt-private-only tt-two-col" data-private-only>
            <div class="tt-field"><label for="{{ create_form.first_name.id_for_label }}">Vorname</label>{{ create_form.first_name }}{{ create_form.first_name.errors }}</div>
            <div class="tt-field"><label for="{{ create_form.last_name.id_for_label }}">Nachname</label>{{ create_form.last_name }}{{ create_form.last_name.errors }}</div>
          </div>

'''
if private_duplicate in template:
    template = template.replace(private_duplicate, "", 1)
template = template.replace('class="tt-field tt-company-contact"', 'class="tt-field tt-name-contact"')
old_range = '''        <span>{{ offset|add:'1' }}–{% if has_next %}{{ offset|add:page_size }}{% else %}{{ total_count }}{% endif %}</span>'''
new_range = '''        <span>{% if total_count %}{{ offset|add:'1' }}–{% if has_next %}{{ offset|add:page_size }}{% else %}{{ total_count }}{% endif %}{% else %}0{% endif %}</span>'''
if old_range in template:
    template = template.replace(old_range, new_range, 1)
write(template_path, template)

js_path = "static/js/kayi-next.js"
js = read(js_path)
js = js.replace("    form.querySelectorAll('[data-private-only]').forEach((node) => { node.hidden = business; });\n", "")
js = js.replace("    form.querySelectorAll('.tt-company-contact').forEach((node) => { node.hidden = !business; });\n", "")
write(js_path, js)

# The earlier object/location layer inserts customer_locations_api between
# customer_detail and project_list. The parity layer intentionally replaces the
# entire customer block, so restore the object workflow and JSON endpoint here
# while keeping the new identifiers and customer-number editing semantics.
views_path = "erp/rebuild_views.py"
views = read(views_path)
detail_pattern = re.compile(
    r'@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef customer_detail\(request, pk\):.*?(?=\n\n@login_required\ndef supplier_list\(request\):)',
    re.S,
)
detail_and_api = '''@login_required
@require_http_methods(["GET", "POST"])
def customer_detail(request, pk):
    org = _org(request)
    customer = get_object_or_404(m.Customer, pk=pk, organization=org)
    add_object_open = request.GET.get("add_object") == "1"

    if request.method == "POST" and request.POST.get("action") == "add_location":
        form = CustomerForm(instance=customer, organization=org, initial={"customer_number": customer.number})
        location_form = ObjectLocationForm(request.POST, prefix="site")
        add_object_open = True
        if location_form.is_valid():
            location = location_form.save(commit=False)
            location.organization = org
            location.customer = customer
            location.save()
            messages.success(request, "Einsatzort wurde hinzugefügt.")
            return redirect(f"/customers/{customer.pk}/#objekte")
    elif request.method == "POST":
        form = CustomerForm(request.POST, instance=customer, organization=org, initial={"customer_number": customer.number})
        location_form = ObjectLocationForm(prefix="site")
        if form.is_valid():
            requested_number = str(form.cleaned_data.get("customer_number") or customer.number).strip() or customer.number
            duplicate = m.Customer.objects.filter(organization=org, number=requested_number).exclude(pk=customer.pk).exists()
            if duplicate:
                form.add_error("customer_number", "Diese Kundennummer ist bereits vergeben.")
            else:
                customer = form.save(commit=False)
                customer.number = requested_number
                customer.save()
                messages.success(request, "Kundendaten gespeichert.")
                return redirect("next-customer-detail", pk=customer.pk)
    else:
        form = CustomerForm(instance=customer, organization=org, initial={"customer_number": customer.number})
        location_form = ObjectLocationForm(prefix="site")

    projects = customer.projects.filter(organization=org).order_by("-updated_at")
    locations = customer.object_locations.filter(organization=org).order_by("name", "city", "street")
    return render(request, "rebuild/customer_detail.html", {
        "customer": customer,
        "form": form,
        "projects": projects,
        "locations": locations,
        "location_form": location_form,
        "add_object_open": add_object_open,
    })


@login_required
def customer_locations_api(request, pk):
    org = _org(request)
    customer = get_object_or_404(m.Customer, pk=pk, organization=org, active=True)
    locations = customer.object_locations.filter(organization=org).order_by("name", "city", "street")
    return JsonResponse({
        "customer": {
            "id": customer.pk,
            "name": customer.display_name,
            "address": ", ".join(part for part in [customer.street, f"{customer.postal_code} {customer.city}".strip()] if part),
        },
        "locations": [
            {
                "id": location.pk,
                "name": location.name or "Einsatzort",
                "address": ", ".join(part for part in [location.street, f"{location.postal_code} {location.city}".strip()] if part),
            }
            for location in locations
        ],
    })
'''
views, count = detail_pattern.subn(detail_and_api.rstrip(), views, count=1)
if count != 1:
    if "def customer_locations_api(request, pk):" not in views:
        raise RuntimeError("Customer detail/location API compatibility anchor changed")
write(views_path, views)

final_template = read(template_path)
final_js = read(js_path)
final_views = read(views_path)
if "tt-private-only tt-two-col" in final_template:
    raise RuntimeError("Duplicate private customer name inputs remain")
if 'class="tt-field tt-company-contact"' in final_template:
    raise RuntimeError("Business-only name fields remain")
if "{% if total_count %}" not in final_template:
    raise RuntimeError("Empty customer pagination is not normalized")
if "querySelectorAll('[data-private-only]')" in final_js or "querySelectorAll('.tt-company-contact')" in final_js:
    raise RuntimeError("Obsolete customer-name visibility JS remains")
for needle in (
    "def customer_locations_api(request, pk):",
    '"address": ", ".join(part for part in [customer.street',
    'request.POST.get("action") == "add_location"',
    'location_form = ObjectLocationForm(request.POST, prefix="site")',
):
    if needle not in final_views:
        raise RuntimeError(f"Customer object/location compatibility missing: {needle}")
print("Customer modal, object-location API and empty-pagination parity polish applied.")