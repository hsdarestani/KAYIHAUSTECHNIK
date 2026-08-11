from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "/* KAYI CUSTOMER OBJECT UX 2026-08-11 */"
VERSION = "20260811-customer-object1"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_views_and_form() -> None:
    path = "erp/rebuild_views.py"
    text = read(path)

    project_form_pattern = re.compile(
        r"class ProjectForm\(StyledModelForm\):.*?\n\nclass AppointmentForm\(StyledModelForm\):",
        re.S,
    )
    project_form = '''class ProjectForm(StyledModelForm):
    class Meta:
        model = m.Project
        fields = ["title", "customer", "object_location", "description", "priority", "manager", "members"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "members": forms.SelectMultiple(attrs={"size": 5})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["object_location"].empty_label = "Kundenadresse verwenden (Standard)"
        if organization:
            self.fields["customer"].queryset = m.Customer.objects.filter(organization=organization, active=True)
            self.fields["manager"].queryset = m.Employee.objects.filter(organization=organization, active=True)
            self.fields["members"].queryset = m.Employee.objects.filter(organization=organization, active=True)

            customer_id = None
            if self.is_bound:
                customer_id = self.data.get("customer")
            if not customer_id:
                customer_id = self.initial.get("customer")
            if not customer_id and getattr(self.instance, "customer_id", None):
                customer_id = self.instance.customer_id

            locations = m.ObjectLocation.objects.filter(organization=organization)
            try:
                customer_id = int(customer_id) if customer_id else None
            except (TypeError, ValueError):
                customer_id = None
            self.fields["object_location"].queryset = locations.filter(customer_id=customer_id) if customer_id else locations.none()


class AppointmentForm(StyledModelForm):'''
    text, count = project_form_pattern.subn(project_form, text, count=1)
    if count != 1:
        raise RuntimeError("Could not replace ProjectForm for customer-scoped locations")

    customer_detail_pattern = re.compile(
        r"@login_required\n@require_http_methods\(\[\"GET\", \"POST\"\]\)\ndef customer_detail\(request, pk\):.*?\n\n@login_required\ndef project_list\(request\):",
        re.S,
    )
    customer_detail = '''@login_required
@require_http_methods(["GET", "POST"])
def customer_detail(request, pk):
    org = _org(request)
    customer = get_object_or_404(m.Customer, pk=pk, organization=org)
    add_object_open = request.GET.get("add_object") == "1"

    if request.method == "POST" and request.POST.get("action") == "add_location":
        form = CustomerForm(instance=customer)
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
        form = CustomerForm(request.POST, instance=customer)
        location_form = ObjectLocationForm(prefix="site")
        if form.is_valid():
            form.save()
            messages.success(request, "Kundendaten gespeichert.")
            return redirect("next-customer-detail", pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)
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
        "customer": {"id": customer.pk, "name": customer.display_name},
        "locations": [
            {
                "id": location.pk,
                "name": location.name or "Einsatzort",
                "address": ", ".join(part for part in [location.street, f"{location.postal_code} {location.city}".strip()] if part),
            }
            for location in locations
        ],
    })


@login_required
def project_list(request):'''
    text, count = customer_detail_pattern.subn(customer_detail, text, count=1)
    if count != 1:
        raise RuntimeError("Could not replace customer_detail with object-location flow")

    write(path, text)


def patch_urls() -> None:
    path = "erp/rebuild_urls.py"
    text = read(path)
    route = '    path("customers/<int:pk>/locations.json/", views.customer_locations_api, name="next-customer-locations-api"),\n'
    if route not in text:
        anchor = '    path("customers/<int:pk>/", views.customer_detail, name="next-customer-detail"),\n'
        if anchor not in text:
            raise RuntimeError("Customer detail URL anchor changed")
        text = text.replace(anchor, anchor + route, 1)
    write(path, text)


def patch_customer_template() -> None:
    template = r'''{% extends 'rebuild/base.html' %}
{% block title %}{{ customer.display_name }} · KAYI{% endblock %}
{% block content %}
<div class="nx-pagehead nx-customer-detail-head">
  <div>
    <div class="nx-kicker">{{ customer.number }}</div>
    <h1>{{ customer.display_name }}</h1>
    <p>{{ customer.email|default:'Keine E-Mail' }} · {{ customer.mobile|default:customer.phone|default:'Keine Telefonnummer' }}</p>
  </div>
</div>

<div class="nx-customer-detail-grid">
  <section class="nx-card nx-card-pad nx-customer-data-card">
    <div class="nx-card-head nx-customer-card-head"><div><h2>Kundendaten</h2><p>Kontakt und Rechnungsadresse bearbeiten.</p></div></div>
    <form class="nx-form nx-customer-detail-form" method="post">{% csrf_token %}
      <div class="nx-form-grid">
        {% for field in form %}
          {% if field.name == 'type' or field.name == 'company' or field.name == 'first_name' or field.name == 'last_name' or field.name == 'email' or field.name == 'phone' or field.name == 'mobile' or field.name == 'street' or field.name == 'postal_code' or field.name == 'city' %}
          <div class="nx-field {% if field.name == 'street' %}nx-field-full{% endif %}">
            <label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{{ field.errors }}
          </div>
          {% endif %}
        {% endfor %}
      </div>

      <details class="nx-progressive nx-customer-more" {% if form.salutation.errors or form.country.errors or form.vat_id.errors or form.notes.errors %}open{% endif %}>
        <summary><span>＋ Weitere Angaben</span><small>Anrede, Land, USt-IdNr. und Notizen</small></summary>
        <div class="nx-form-grid nx-progressive-body">
          {% for field in form %}
            {% if field.name == 'salutation' or field.name == 'country' or field.name == 'vat_id' or field.name == 'notes' %}
            <div class="nx-field {% if field.name == 'notes' %}nx-field-full{% endif %}"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{{ field.errors }}</div>
            {% endif %}
          {% endfor %}
        </div>
      </details>

      <div class="nx-form-actions nx-customer-save-actions"><button class="nx-btn nx-btn-primary" type="submit">Änderungen speichern</button></div>
    </form>
  </section>

  <div class="nx-customer-side-stack">
    <section class="nx-card nx-card-pad nx-customer-object-card" id="objekte">
      <div class="nx-card-head nx-customer-card-head">
        <div><h2>Objekte</h2><p>Rechnungsadresse und abweichende Einsatzorte.</p></div>
        <a class="nx-btn nx-btn-ghost nx-customer-add-object" href="?add_object=1#objekte">＋ Objekt hinzufügen</a>
      </div>

      {% if locations %}
      <div class="nx-object-list">
        {% for location in locations %}
        <article class="nx-object-item"><div class="nx-object-icon">⌖</div><div><b>{{ location.name|default:'Einsatzort' }}</b><span>{{ location.street }}{% if location.street and location.city %}, {% endif %}{{ location.postal_code }} {{ location.city }}</span>{% if location.floor %}<small>{{ location.floor }}</small>{% endif %}</div><span class="nx-badge">Objekt</span></article>
        {% endfor %}
      </div>
      {% else %}
      <div class="nx-customer-empty"><b>Noch kein zusätzlicher Einsatzort.</b><span>Standardmäßig wird die Kundenadresse im Projekt verwendet.</span></div>
      {% endif %}

      <details class="nx-progressive nx-object-create" {% if add_object_open or location_form.errors %}open{% endif %}>
        <summary><span>＋ Neuen Einsatzort erfassen</span><small>Nur nötig, wenn der Einsatzort von der Kundenadresse abweicht.</small></summary>
        <form class="nx-form nx-object-form" method="post">{% csrf_token %}<input type="hidden" name="action" value="add_location">
          <div class="nx-form-grid nx-progressive-body">
            {% for field in location_form %}<div class="nx-field {% if field.name == 'access_notes' %}nx-field-full{% endif %}"><label for="{{ field.id_for_label }}">{% if field.name == 'name' %}Bezeichnung{% elif field.name == 'street' %}Straße{% elif field.name == 'postal_code' %}PLZ{% elif field.name == 'city' %}Ort{% elif field.name == 'floor' %}Etage{% elif field.name == 'access_notes' %}Hinweise zum Zugang{% else %}{{ field.label }}{% endif %}</label>{{ field }}{{ field.errors }}</div>{% endfor %}
          </div>
          <div class="nx-form-actions"><button class="nx-btn nx-btn-primary" type="submit">Einsatzort speichern</button></div>
        </form>
      </details>
    </section>

    <section class="nx-card nx-card-pad nx-customer-project-card">
      <div class="nx-card-head nx-customer-card-head"><div><h2>Projekte</h2><p>Alle Aufträge dieses Kunden.</p></div><a class="nx-btn nx-btn-ghost" href="{% url 'next-project-create' %}?customer={{ customer.pk }}">＋ Projekt</a></div>
      {% if projects %}<div class="nx-customer-project-list">{% for project in projects %}<a class="nx-customer-project-row" href="{% url 'next-project-detail' project.pk %}"><div><b>{{ project.title }}</b><span>{{ project.number }} · zuletzt {{ project.updated_at|date:'d.m.Y' }}</span></div><span class="nx-badge {% if project.status == 'in_progress' %}nx-badge-success{% endif %}">{{ project.get_status_display }}</span></a>{% endfor %}</div>{% else %}<div class="nx-customer-empty"><b>Noch kein Projekt.</b><span>Ein Projekt übernimmt Kunde und Einsatzort in den operativen Ablauf.</span><a href="{% url 'next-project-create' %}?customer={{ customer.pk }}">Erstes Projekt anlegen →</a></div>{% endif %}
    </section>
  </div>
</div>
{% endblock %}
'''
    write("templates/rebuild/customer_detail.html", template)


def patch_project_template() -> None:
    path = "templates/rebuild/project_form.html"
    text = read(path)
    if "data-project-object-ux" not in text:
        text = text.replace('<form class="nx-form nx-project-form" method="post">', '<form class="nx-form nx-project-form" method="post" data-project-object-ux>', 1)
        if 'data-project-object-ux' not in text:
            text = text.replace('<form class="nx-form" method="post">', '<form class="nx-form nx-project-form" method="post" data-project-object-ux>', 1)

    script = r'''
<script>
(() => {
  const form = document.querySelector('[data-project-object-ux]');
  if (!form) return;
  const customer = form.querySelector('select[name="customer"]');
  const object = form.querySelector('select[name="object_location"]');
  if (!customer || !object) return;

  const field = object.closest('.nx-field');
  let action = field?.querySelector('[data-object-create-link]');
  if (!action && field) {
    const label = field.querySelector('label');
    const head = document.createElement('div');
    head.className = 'nx-project-object-head';
    if (label) head.appendChild(label);
    action = document.createElement('a');
    action.className = 'nx-project-inline-action';
    action.dataset.objectCreateLink = '1';
    action.textContent = '＋ Einsatzort anlegen';
    head.appendChild(action);
    field.prepend(head);
  }

  const setAction = () => {
    const id = customer.value;
    if (!action) return;
    action.href = id ? `/customers/${encodeURIComponent(id)}/?add_object=1#objekte` : '#';
    action.setAttribute('aria-disabled', id ? 'false' : 'true');
    action.classList.toggle('is-disabled', !id);
  };

  const loadLocations = async () => {
    const customerId = customer.value;
    const previous = object.value;
    object.innerHTML = '<option value="">Kundenadresse verwenden (Standard)</option>';
    setAction();
    if (!customerId) return;
    try {
      const response = await fetch(`/customers/${encodeURIComponent(customerId)}/locations.json/`, {credentials:'same-origin', headers:{'Accept':'application/json'}});
      if (!response.ok) throw new Error('load failed');
      const data = await response.json();
      (data.locations || []).forEach((location) => {
        const option = document.createElement('option');
        option.value = String(location.id);
        option.textContent = location.address ? `${location.name} · ${location.address}` : location.name;
        object.appendChild(option);
      });
      if ([...object.options].some((option) => option.value === previous)) object.value = previous;
    } catch (_) {
      const option = document.createElement('option');
      option.disabled = true;
      option.textContent = 'Einsatzorte konnten nicht geladen werden';
      object.appendChild(option);
    }
  };

  customer.addEventListener('change', loadLocations);
  setAction();
})();
</script>
'''
    if "Kundenadresse verwenden (Standard)" not in text or "data-object-create-link" not in text:
        # A child template can safely provide the base's scripts block. If another
        # final layer already added it, inject before that block's end instead.
        if "{% block scripts %}" in text:
            text = text.replace("{% block scripts %}", "{% block scripts %}" + script, 1)
        else:
            text += "\n{% block scripts %}" + script + "{% endblock %}\n"
    write(path, text)


def patch_css() -> None:
    css_path = "static/css/kayi-readability.css" if (ROOT / "static/css/kayi-readability.css").exists() else "static/css/kayi-next.css"
    css = read(css_path)
    if MARKER not in css:
        css += r'''

/* KAYI CUSTOMER OBJECT UX 2026-08-11 */
.nx-customer-detail-head{margin-bottom:20px;padding-top:10px}.nx-customer-detail-grid{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(380px,.92fr);gap:18px;align-items:start}.nx-customer-side-stack{display:grid;gap:18px;align-self:start}.nx-customer-detail-grid>.nx-card,.nx-customer-side-stack>.nx-card{min-height:0}.nx-customer-card-head{padding:0 0 16px!important;align-items:center}.nx-customer-card-head .nx-btn{min-height:35px;padding:7px 11px}.nx-customer-detail-form{gap:16px}.nx-customer-detail-form .nx-form-grid{align-items:start}.nx-customer-detail-form .nx-field-full{grid-column:1/-1}.nx-customer-more{margin-top:16px}.nx-customer-save-actions{justify-content:flex-end;padding-top:14px}.nx-customer-empty{display:grid;justify-items:center;gap:6px;padding:28px 18px;text-align:center;color:#777c80}.nx-customer-empty b{font-size:14px;color:#1b1e21}.nx-customer-empty a{margin-top:4px;font-weight:800;color:#2e6760;text-decoration:none}.nx-object-list,.nx-customer-project-list{display:grid;border-top:1px solid #e7e3dc}.nx-object-item,.nx-customer-project-row{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:10px;align-items:center;padding:13px 2px;border-bottom:1px solid #ece8e1}.nx-object-icon{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:#edf7f5}.nx-object-item>div:nth-child(2),.nx-customer-project-row>div{display:grid;gap:2px;min-width:0}.nx-object-item b,.nx-customer-project-row b{font-size:13.5px}.nx-object-item span,.nx-object-item small,.nx-customer-project-row span{font-size:11.5px;color:#777c80}.nx-customer-project-row{grid-template-columns:minmax(0,1fr) auto;color:inherit;text-decoration:none}.nx-object-create{margin-top:14px}.nx-object-form{padding-top:6px}.nx-project-object-head{display:flex;align-items:center;justify-content:space-between;gap:10px}.nx-project-object-head label{margin:0}.nx-project-inline-action.is-disabled{opacity:.45;pointer-events:none}.nx-project-card .nx-form-grid>.nx-field:nth-child(3){gap:7px}.nx-project-card .nx-form-grid>.nx-field:nth-child(3) select{min-height:46px}
@media(max-width:980px){.nx-customer-detail-grid{grid-template-columns:1fr}.nx-customer-side-stack{grid-template-columns:1fr 1fr}.nx-customer-data-card{order:1}.nx-customer-side-stack{order:2}}
@media(max-width:720px){.nx-customer-detail-head{padding-top:6px}.nx-customer-side-stack{grid-template-columns:1fr}.nx-customer-card-head{align-items:stretch;flex-direction:column;gap:10px}.nx-customer-card-head .nx-btn{width:100%}.nx-customer-detail-form .nx-form-grid,.nx-object-form .nx-form-grid{grid-template-columns:1fr}.nx-customer-detail-form .nx-field-full{grid-column:auto}.nx-project-object-head{align-items:stretch;flex-direction:column}.nx-project-object-head .nx-project-inline-action{width:100%}}
'''
        write(css_path, css)

    base = read("templates/rebuild/base.html")
    asset = Path(css_path).name
    pattern = re.compile(rf"(static 'css/{re.escape(asset)}' %\}}\?v=)[^\"']+")
    updated, count = pattern.subn(rf"\g<1>{VERSION}", base, count=1)
    if count == 0:
        raw = f"static 'css/{asset}' %}}"
        if raw in base:
            updated = base.replace(raw, raw + f"?v={VERSION}", 1)
        else:
            updated = base
    write("templates/rebuild/base.html", updated)


def install_tests() -> None:
    write("tests/test_customer_object_project_ux.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class CustomerObjectProjectUXContract(SimpleTestCase):
    def test_customer_detail_has_object_creation_and_no_duplicate_local_actions(self):
        template = (ROOT / "templates/rebuild/customer_detail.html").read_text(encoding="utf-8")
        self.assertIn("＋ Objekt hinzufügen", template)
        self.assertIn('name="action" value="add_location"', template)
        self.assertIn("Standardmäßig wird die Kundenadresse", template)
        self.assertNotIn("next-appointment-create", template)

    def test_project_object_locations_are_customer_scoped(self):
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        urls = (ROOT / "erp/rebuild_urls.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/project_form.html").read_text(encoding="utf-8")
        self.assertIn('empty_label = "Kundenadresse verwenden (Standard)"', views)
        self.assertIn("locations.filter(customer_id=customer_id)", views)
        self.assertIn("def customer_locations_api", views)
        self.assertIn("next-customer-locations-api", urls)
        self.assertIn("＋ Einsatzort anlegen", template)
        self.assertIn("locations.json", template)
''')


def guard() -> None:
    customer = read("templates/rebuild/customer_detail.html")
    views = read("erp/rebuild_views.py")
    project = read("templates/rebuild/project_form.html")
    for marker in ("＋ Objekt hinzufügen", "Einsatzort speichern", "nx-customer-detail-grid"):
        if marker not in customer:
            raise RuntimeError(f"Customer detail UX missing: {marker}")
    for marker in ("def customer_locations_api", "Kundenadresse verwenden (Standard)", "locations.filter(customer_id=customer_id)"):
        if marker not in views:
            raise RuntimeError(f"Customer-scoped object flow missing: {marker}")
    if "＋ Einsatzort anlegen" not in project:
        raise RuntimeError("Project form is missing contextual Einsatzort action")


def main() -> None:
    patch_views_and_form()
    patch_urls()
    patch_customer_template()
    patch_project_template()
    patch_css()
    install_tests()
    guard()
    print("KAYI customer/object/project UX upgraded and guarded.")


if __name__ == "__main__":
    main()
