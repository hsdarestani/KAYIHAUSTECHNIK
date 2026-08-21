from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 9 CORE CRUD 2026-08-20"
CACHE_VERSION = "20260820-tooltime-core-crud-1"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Phase 9 target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_forms_and_views() -> None:
    path = "erp/rebuild_views.py"
    text = read(path)

    customer_form_pattern = re.compile(
        r"class CustomerForm\(StyledModelForm\):.*?\n\nclass ObjectLocationForm\(StyledModelForm\):",
        re.S,
    )
    customer_form = '''class CustomerForm(StyledModelForm):
    customer_number = forms.CharField(label="Kundennummer", required=False, max_length=30)

    class Meta:
        model = m.Customer
        fields = [
            "type", "company", "salutation", "first_name", "last_name", "email", "phone", "mobile",
            "street", "postal_code", "city", "country", "vat_id", "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "type": "Kundentyp",
            "company": "Firmenname",
            "salutation": "Anrede",
            "first_name": "Vorname",
            "last_name": "Nachname",
            "email": "E-Mail",
            "phone": "Telefon",
            "mobile": "Mobil",
            "street": "Straße und Hausnummer",
            "postal_code": "PLZ",
            "city": "Ort",
            "country": "Land",
            "vat_id": "USt-IdNr.",
            "notes": "Beschreibung",
        }
        for name, label in labels.items():
            if name in self.fields:
                self.fields[name].label = label
        self.fields["customer_number"].widget.attrs.setdefault("placeholder", "wird automatisch vergeben")
        if getattr(self.instance, "pk", None):
            self.fields["customer_number"].initial = self.instance.number
            self.fields["customer_number"].disabled = True


class ObjectLocationForm(StyledModelForm):'''
    text, count = customer_form_pattern.subn(customer_form, text, count=1)
    if count != 1:
        raise RuntimeError("Phase 9 could not replace CustomerForm")

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
        self.fields["title"].label = "Projekttitel"
        self.fields["customer"].label = "Kunde auswählen"
        self.fields["object_location"].label = "Ausführungsort"
        self.fields["description"].label = "Projektbeschreibung"
        self.fields["priority"].label = "Priorität"
        self.fields["manager"].label = "Projektleitung"
        self.fields["members"].label = "Mitarbeiter"
        self.fields["customer"].widget.attrs["data-searchable"] = "true"
        self.fields["customer"].widget.attrs["data-search-placeholder"] = "Kunde suchen …"
        self.fields["object_location"].empty_label = "Kundenadresse verwenden"
        self.fields["priority"].required = False
        self.fields["manager"].required = False
        self.fields["members"].required = False
        self.fields["description"].required = False
        self.fields["priority"].initial = self.initial.get("priority") or "normal"
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
            try:
                customer_id = int(customer_id) if customer_id else None
            except (TypeError, ValueError):
                customer_id = None
            locations = m.ObjectLocation.objects.filter(organization=organization)
            self.fields["object_location"].queryset = locations.filter(customer_id=customer_id) if customer_id else locations.none()

    def clean_priority(self):
        return self.cleaned_data.get("priority") or "normal"


class AppointmentForm(StyledModelForm):'''
    text, count = project_form_pattern.subn(project_form, text, count=1)
    if count != 1:
        raise RuntimeError("Phase 9 could not replace ProjectForm")

    customer_create_pattern = re.compile(
        r"@login_required\n@require_http_methods\(\[\"GET\", \"POST\"\]\)\ndef customer_create\(request\):.*?\n\n@login_required\n@require_http_methods\(\[\"GET\", \"POST\"\]\)\ndef customer_detail",
        re.S,
    )
    customer_create = '''@login_required
@require_http_methods(["GET", "POST"])
def customer_create(request):
    org = _org(request)
    next_target = (request.POST.get("next") if request.method == "POST" else request.GET.get("next")) or ""
    next_target = next_target if next_target in {"project"} else ""
    suggested_number = _unique_number(m.Customer, org, "K")
    initial = {"customer_number": suggested_number}
    form = CustomerForm(request.POST or None, organization=org, initial=initial)
    location_form = ObjectLocationForm(request.POST or None, prefix="site")
    if request.method == "POST" and form.is_valid():
        requested_number = str(form.cleaned_data.get("customer_number") or "").strip() or suggested_number
        if m.Customer.objects.filter(organization=org, number=requested_number).exists():
            form.add_error("customer_number", "Diese Kundennummer ist bereits vergeben.")
        else:
            with transaction.atomic():
                customer = form.save(commit=False)
                customer.organization = org
                customer.number = requested_number
                customer.save()
                if request.POST.get("site-street"):
                    if location_form.is_valid():
                        location = location_form.save(commit=False)
                        location.organization = org
                        location.customer = customer
                        location.save()
                    else:
                        transaction.set_rollback(True)
                        return render(request, "rebuild/customer_form.html", {
                            "form": form,
                            "location_form": location_form,
                            "mode": "create",
                            "next_target": next_target,
                        })
            messages.success(request, "Kunde wurde angelegt.")
            if next_target == "project":
                return redirect(f"/projects/new/?customer={customer.pk}")
            return redirect("next-customer-detail", pk=customer.pk)
    return render(request, "rebuild/customer_form.html", {
        "form": form,
        "location_form": location_form,
        "mode": "create",
        "next_target": next_target,
    })


@login_required
@require_http_methods(["GET", "POST"])
def customer_detail'''
    text, count = customer_create_pattern.subn(customer_create, text, count=1)
    if count != 1:
        raise RuntimeError("Phase 9 could not replace customer_create")

    project_create_pattern = re.compile(
        r"@login_required\n@require_http_methods\(\[\"GET\", \"POST\"\]\)\ndef project_create\(request\):.*?\n\n@login_required\ndef project_detail",
        re.S,
    )
    project_create = '''@login_required
@require_http_methods(["GET", "POST"])
def project_create(request):
    org = _org(request)
    initial = {"priority": "normal"}
    requested_customer = request.GET.get("customer")
    if requested_customer and m.Customer.objects.filter(organization=org, active=True, pk=requested_customer).exists():
        initial["customer"] = requested_customer
    data = request.POST.copy() if request.method == "POST" else None
    if data is not None and not data.get("priority"):
        data["priority"] = "normal"
    form = ProjectForm(data, organization=org, initial=initial)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.organization = org
        project.number = _unique_number(m.Project, org, "P")
        project.status = "inquiry"
        project.save()
        form.save_m2m()
        messages.success(request, "Projekt wurde angelegt.")
        return redirect("next-project-detail", pk=project.pk)
    return render(request, "rebuild/project_form.html", {"form": form})


@login_required
def project_detail'''
    text, count = project_create_pattern.subn(project_create, text, count=1)
    if count != 1:
        raise RuntimeError("Phase 9 could not replace project_create")

    # Existing customer-location endpoint is extended with the billing-address
    # preview so project creation can mirror ToolTime without duplicating data.
    customer_payload = '"customer": {"id": customer.pk, "name": customer.display_name},'
    if customer_payload in text:
        text = text.replace(
            customer_payload,
            '"customer": {\n            "id": customer.pk,\n            "name": customer.display_name,\n            "address": ", ".join(part for part in [customer.street, f"{customer.postal_code} {customer.city}".strip()] if part),\n        },',
            1,
        )
    elif '"address": ", ".join(part for part in [customer.street' not in text:
        raise RuntimeError("Phase 9 customer location API anchor missing")

    write(path, text)


CUSTOMER_TEMPLATE = r'''{% extends 'rebuild/base.html' %}
{% block title %}Neuer Kunde · A+Bau{% endblock %}
{% block content %}
<div class="tt-create-shell tt-customer-create" data-tt-customer-create>
  <div class="tt-create-head">
    <div><a class="tt-back" href="{% if next_target == 'project' %}{% url 'next-project-create' %}{% else %}{% url 'next-customers' %}{% endif %}">← Zurück</a><h1>Neuer Kunde</h1></div>
  </div>

  <form method="post" class="tt-create-form" data-customer-form>{% csrf_token %}
    {% if next_target %}<input type="hidden" name="next" value="{{ next_target }}">{% endif %}
    {% if form.non_field_errors %}<div class="tt-form-alert">{{ form.non_field_errors }}</div>{% endif %}

    <section class="tt-create-card">
      <h2>Kundendaten</h2>
      <div class="tt-grid tt-grid-2">
        <div class="tt-field tt-span-2"><label for="{{ form.type.id_for_label }}">Kundentyp</label>{{ form.type }}{{ form.type.errors }}</div>
        <div class="tt-field tt-span-2" data-company-field><label for="{{ form.company.id_for_label }}">Firmenname <span class="tt-optional" data-company-optional>optional</span></label>{{ form.company }}{{ form.company.errors }}</div>
        <div class="tt-field"><label for="{{ form.first_name.id_for_label }}">Vorname</label>{{ form.first_name }}{{ form.first_name.errors }}</div>
        <div class="tt-field"><label for="{{ form.last_name.id_for_label }}">Nachname</label>{{ form.last_name }}{{ form.last_name.errors }}</div>
      </div>
    </section>

    <section class="tt-create-card">
      <h2>Kontakt</h2>
      <div class="tt-grid tt-grid-2">
        <div class="tt-field"><label for="{{ form.email.id_for_label }}">E-Mail</label>{{ form.email }}{{ form.email.errors }}</div>
        <div class="tt-field"><label for="{{ form.mobile.id_for_label }}">Mobil</label>{{ form.mobile }}{{ form.mobile.errors }}</div>
        <div class="tt-field"><label for="{{ form.phone.id_for_label }}">Telefon</label>{{ form.phone }}{{ form.phone.errors }}</div>
      </div>
    </section>

    <section class="tt-create-card">
      <h2>Rechnungsadresse</h2>
      <div class="tt-grid tt-grid-2">
        <div class="tt-field tt-span-2"><label for="{{ form.street.id_for_label }}">Straße und Hausnummer</label>{{ form.street }}{{ form.street.errors }}</div>
        <div class="tt-field"><label for="{{ form.postal_code.id_for_label }}">PLZ</label>{{ form.postal_code }}{{ form.postal_code.errors }}</div>
        <div class="tt-field"><label for="{{ form.city.id_for_label }}">Ort</label>{{ form.city }}{{ form.city.errors }}</div>
        <div class="tt-field tt-span-2"><label for="{{ form.country.id_for_label }}">Land</label>{{ form.country }}{{ form.country.errors }}</div>
      </div>
    </section>

    <details class="tt-create-card tt-details" data-more-details {% if form.salutation.errors or form.vat_id.errors or form.notes.errors or form.customer_number.errors %}open{% endif %}>
      <summary><span>Details einblenden</span><span class="tt-chevron">⌄</span></summary>
      <div class="tt-details-body tt-grid tt-grid-2">
        <div class="tt-field"><label for="{{ form.salutation.id_for_label }}">Anrede</label>{{ form.salutation }}{{ form.salutation.errors }}</div>
        <div class="tt-field"><label for="{{ form.customer_number.id_for_label }}">Kundennummer</label>{{ form.customer_number }}{{ form.customer_number.errors }}<small>Kann geändert oder automatisch fortlaufend vergeben werden.</small></div>
        <div class="tt-field"><label for="{{ form.vat_id.id_for_label }}">USt-IdNr.</label>{{ form.vat_id }}{{ form.vat_id.errors }}</div>
        <div class="tt-field tt-span-2"><label for="{{ form.notes.id_for_label }}">Beschreibung</label>{{ form.notes }}{{ form.notes.errors }}</div>
      </div>
    </details>

    <details class="tt-create-card tt-details tt-location-details" data-location-details {% if location_form.errors %}open{% endif %}>
      <summary><span>Abweichenden Ausführungsort hinzufügen</span><span class="tt-chevron">⌄</span></summary>
      <div class="tt-details-body tt-grid tt-grid-2">
        {% for field in location_form %}
        <div class="tt-field {% if field.name == 'access_notes' or field.name == 'street' %}tt-span-2{% endif %}">
          <label for="{{ field.id_for_label }}">{% if field.name == 'name' %}Bezeichnung{% elif field.name == 'street' %}Straße und Hausnummer{% elif field.name == 'postal_code' %}PLZ{% elif field.name == 'city' %}Ort{% elif field.name == 'floor' %}Etage{% elif field.name == 'access_notes' %}Hinweise zum Zugang{% else %}{{ field.label }}{% endif %}</label>
          {{ field }}{{ field.errors }}
        </div>
        {% endfor %}
      </div>
    </details>

    <div class="tt-create-actions">
      <a class="nx-btn" href="{% if next_target == 'project' %}{% url 'next-project-create' %}{% else %}{% url 'next-customers' %}{% endif %}">Abbrechen</a>
      <button class="nx-btn nx-btn-primary tt-submit" type="submit">＋ Erstellen</button>
    </div>
  </form>
</div>
{% endblock %}
{% block scripts %}
<script>
(() => {
  const root = document.querySelector('[data-tt-customer-create]');
  if (!root) return;
  const type = root.querySelector('[name="type"]');
  const companyWrap = root.querySelector('[data-company-field]');
  const company = root.querySelector('[name="company"]');
  const optional = root.querySelector('[data-company-optional]');
  const syncType = () => {
    if (!type || !companyWrap) return;
    const selectedText = type.options[type.selectedIndex]?.textContent || '';
    const isPrivate = type.value === 'private' || /privat/i.test(selectedText);
    companyWrap.classList.toggle('tt-secondary-field', isPrivate);
    if (optional) optional.textContent = isPrivate ? 'optional' : '';
    if (company) company.placeholder = isPrivate ? 'optional bei Privatkunden' : 'Firmenname';
  };
  type?.addEventListener('change', syncType);
  syncType();
})();
</script>
{% endblock %}
'''


PROJECT_TEMPLATE = r'''{% extends 'rebuild/base.html' %}
{% block title %}Neues Projekt · A+Bau{% endblock %}
{% block content %}
<div class="tt-create-shell tt-project-create" data-tt-project-create>
  <div class="tt-create-head"><div><a class="tt-back" href="{% url 'next-projects' %}">← Zurück</a><h1>Neues Projekt</h1></div></div>

  <form method="post" class="tt-create-form" data-project-object-ux>{% csrf_token %}
    {% if form.non_field_errors %}<div class="tt-form-alert">{{ form.non_field_errors }}</div>{% endif %}
    <section class="tt-create-card">
      <h2>Projektdetails</h2>
      <div class="tt-grid tt-grid-2">
        <div class="tt-field tt-span-2"><label for="{{ form.title.id_for_label }}">Projekttitel</label>{{ form.title }}{{ form.title.errors }}</div>
        <div class="tt-field tt-span-2"><label for="{{ form.description.id_for_label }}">Projektbeschreibung <span class="tt-optional">optional</span></label>{{ form.description }}{{ form.description.errors }}</div>
      </div>
    </section>

    <section class="tt-create-card">
      <div class="tt-section-head"><h2>Kunde</h2><a class="tt-inline-link" href="{% url 'next-customer-create' %}?next=project">＋ Neuen Kunden anlegen</a></div>
      <div class="tt-field"><label for="{{ form.customer.id_for_label }}">Kunde auswählen</label>{{ form.customer }}{{ form.customer.errors }}</div>
      <div class="tt-address-preview" data-customer-address-preview hidden><small>Rechnungsadresse</small><strong data-customer-address></strong></div>
    </section>

    <section class="tt-create-card">
      <h2>Ausführungsort</h2>
      <label class="tt-switch-row">
        <span><strong>Abweichenden Ausführungsort verwenden</strong><small>Standardmäßig wird die Kundenadresse übernommen.</small></span>
        <input type="checkbox" data-alt-location-toggle>
        <i aria-hidden="true"></i>
      </label>
      <div class="tt-alt-location" data-alt-location hidden>
        <div class="tt-field"><label for="{{ form.object_location.id_for_label }}">Gespeicherten Ausführungsort auswählen</label>{{ form.object_location }}{{ form.object_location.errors }}</div>
        <a class="tt-inline-link" data-object-create-link aria-disabled="true">＋ Neuen Ausführungsort anlegen</a>
      </div>
    </section>

    <details class="tt-create-card tt-details" {% if form.priority.errors or form.manager.errors or form.members.errors %}open{% endif %}>
      <summary><span>Details einblenden</span><span class="tt-chevron">⌄</span></summary>
      <div class="tt-details-body tt-grid tt-grid-2">
        <div class="tt-field"><label for="{{ form.priority.id_for_label }}">Priorität</label>{{ form.priority }}{{ form.priority.errors }}</div>
        <div class="tt-field"><label for="{{ form.manager.id_for_label }}">Projektleitung</label>{{ form.manager }}{{ form.manager.errors }}</div>
        <div class="tt-field tt-span-2"><label for="{{ form.members.id_for_label }}">Mitarbeiter</label>{{ form.members }}{{ form.members.errors }}</div>
      </div>
    </details>

    <div class="tt-create-actions"><a class="nx-btn" href="{% url 'next-projects' %}">Abbrechen</a><button class="nx-btn nx-btn-primary tt-submit" type="submit">＋ Erstellen</button></div>
  </form>
</div>
{% endblock %}
{% block scripts %}
<script>
(() => {
  const root = document.querySelector('[data-tt-project-create]');
  const form = root?.querySelector('[data-project-object-ux]');
  if (!form) return;
  const customer = form.querySelector('select[name="customer"]');
  const object = form.querySelector('select[name="object_location"]');
  const toggle = form.querySelector('[data-alt-location-toggle]');
  const alt = form.querySelector('[data-alt-location]');
  const action = form.querySelector('[data-object-create-link]');
  const preview = form.querySelector('[data-customer-address-preview]');
  const previewText = form.querySelector('[data-customer-address]');
  if (!customer || !object || !toggle || !alt) return;

  const setToggle = (enabled) => {
    toggle.checked = Boolean(enabled);
    alt.hidden = !toggle.checked;
    if (!toggle.checked) object.value = '';
  };
  const setAction = () => {
    const id = customer.value;
    if (!action) return;
    action.href = id ? `/customers/${encodeURIComponent(id)}/?add_object=1#objekte` : '#';
    action.setAttribute('aria-disabled', id ? 'false' : 'true');
    action.classList.toggle('is-disabled', !id);
  };
  const loadCustomer = async () => {
    const customerId = customer.value;
    const previous = object.value;
    object.innerHTML = '<option value="">Kundenadresse verwenden</option>';
    setAction();
    if (!customerId) {
      if (preview) preview.hidden = true;
      setToggle(false);
      return;
    }
    try {
      const response = await fetch(`/customers/${encodeURIComponent(customerId)}/locations.json/`, {credentials:'same-origin', headers:{'Accept':'application/json'}});
      if (!response.ok) throw new Error('load failed');
      const data = await response.json();
      if (preview && previewText) {
        previewText.textContent = data.customer?.address || 'Keine Rechnungsadresse hinterlegt';
        preview.hidden = false;
      }
      (data.locations || []).forEach((location) => {
        const option = document.createElement('option');
        option.value = String(location.id);
        option.textContent = location.address ? `${location.name} · ${location.address}` : location.name;
        object.appendChild(option);
      });
      if ([...object.options].some((option) => option.value === previous)) object.value = previous;
      if (previous) setToggle(true);
    } catch (_) {
      if (preview) preview.hidden = true;
    }
  };
  toggle.addEventListener('change', () => setToggle(toggle.checked));
  customer.addEventListener('change', loadCustomer);
  setToggle(Boolean(object.value));
  loadCustomer();
})();
</script>
{% endblock %}
'''


def install_templates_and_css() -> None:
    write("templates/rebuild/customer_form.html", CUSTOMER_TEMPLATE)
    write("templates/rebuild/project_form.html", PROJECT_TEMPLATE)

    css_path = "static/css/kayi-next.css"
    css = read(css_path)
    if MARKER not in css:
        css += f'''\n\n/* {MARKER} */
.tt-create-shell{{max-width:820px;margin:0 auto;padding:8px 0 72px}}
.tt-create-head{{display:flex;align-items:flex-start;justify-content:space-between;margin:4px 0 20px}}
.tt-create-head h1{{font-size:32px;line-height:1.15;margin:8px 0 0;letter-spacing:-.02em}}
.tt-back,.tt-inline-link{{color:#615338;text-decoration:none;font-weight:650}}
.tt-back:hover,.tt-inline-link:hover{{text-decoration:underline}}
.tt-create-form{{display:grid;gap:14px}}
.tt-create-card{{background:#fff;border:1px solid #e7e4de;border-radius:12px;padding:22px 24px;box-shadow:0 1px 2px rgba(20,20,20,.03)}}
.tt-create-card h2{{font-size:18px;margin:0 0 18px;color:#242424}}
.tt-section-head{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}}
.tt-section-head h2{{margin:0}}
.tt-grid{{display:grid;gap:16px}}
.tt-grid-2{{grid-template-columns:repeat(2,minmax(0,1fr))}}
.tt-span-2{{grid-column:1/-1}}
.tt-field{{display:grid;gap:7px;min-width:0}}
.tt-field label{{font-weight:650;font-size:14px;color:#353535}}
.tt-field .next-control,.tt-field input,.tt-field select,.tt-field textarea{{width:100%;min-height:46px;border:1px solid #d8d4cc;border-radius:8px;background:#fff;padding:10px 12px;font:inherit;color:#202020;box-sizing:border-box}}
.tt-field textarea{{min-height:88px;resize:vertical}}
.tt-field input:focus,.tt-field select:focus,.tt-field textarea:focus{{outline:0;border-color:#ad8a49;box-shadow:0 0 0 3px rgba(173,138,73,.14)}}
.tt-field small,.tt-optional{{font-size:12px;color:#87827a;font-weight:500}}
.tt-secondary-field{{opacity:.78}}
.tt-details{{padding:0;overflow:hidden}}
.tt-details summary{{display:flex;align-items:center;justify-content:space-between;cursor:pointer;list-style:none;padding:18px 24px;font-weight:700}}
.tt-details summary::-webkit-details-marker{{display:none}}
.tt-details[open] .tt-chevron{{transform:rotate(180deg)}}
.tt-chevron{{transition:transform .15s ease}}
.tt-details-body{{border-top:1px solid #ece9e3;padding:20px 24px 24px}}
.tt-create-actions{{position:sticky;bottom:0;z-index:12;display:flex;justify-content:flex-end;gap:10px;background:rgba(248,247,244,.94);backdrop-filter:blur(10px);border-top:1px solid #e5e1da;padding:14px 0;margin-top:4px}}
.tt-submit{{min-width:130px}}
.tt-address-preview{{margin-top:14px;padding:12px 14px;border-radius:8px;background:#f7f6f2;display:grid;gap:3px}}
.tt-address-preview small{{color:#858078}}
.tt-switch-row{{display:flex;align-items:center;justify-content:space-between;gap:18px;cursor:pointer}}
.tt-switch-row>span{{display:grid;gap:3px}}
.tt-switch-row small{{font-weight:500;color:#858078}}
.tt-switch-row input{{position:absolute;opacity:0;pointer-events:none}}
.tt-switch-row i{{position:relative;width:42px;height:24px;border-radius:999px;background:#c9c5bd;flex:0 0 auto;transition:.15s}}
.tt-switch-row i::after{{content:"";position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.2);transition:.15s}}
.tt-switch-row input:checked+i{{background:#b28b48}}
.tt-switch-row input:checked+i::after{{transform:translateX(18px)}}
.tt-alt-location{{margin-top:18px;padding-top:18px;border-top:1px solid #ece9e3;display:grid;gap:14px}}
.tt-alt-location[hidden],.tt-address-preview[hidden]{{display:none!important}}
.tt-form-alert,.tt-field .errorlist{{color:#9f2727}}
.tt-field .errorlist{{list-style:none;margin:0;padding:0;font-size:12px}}
@media(max-width:700px){{
  .tt-create-shell{{padding:0 0 88px}}
  .tt-create-head h1{{font-size:27px}}
  .tt-create-card{{border-radius:10px;padding:18px 16px}}
  .tt-grid-2{{grid-template-columns:1fr}}
  .tt-span-2{{grid-column:auto}}
  .tt-section-head{{align-items:flex-start;flex-direction:column;gap:8px}}
  .tt-details summary{{padding:17px 16px}}
  .tt-details-body{{padding:18px 16px}}
  .tt-create-actions{{padding:12px 0}}
  .tt-create-actions .nx-btn{{flex:1;justify-content:center}}
}}
'''
        write(css_path, css)

    base_path = "templates/rebuild/base.html"
    base = read(base_path)
    base = re.sub(r"(kayi-next\.css[^\"']*\?v=)[^\"']+", rf"\g<1>{CACHE_VERSION}", base)
    write(base_path, base)


def install_tests() -> None:
    test = r'''from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from erp.models import Customer, Organization, Project, UserProfile

ROOT = Path(__file__).resolve().parents[1]


class ToolTimeCoreCrudContractTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Phase9 GmbH")
        User = get_user_model()
        self.user = User.objects.create_user(username="phase9-office", password="secret")
        UserProfile.objects.create(user=self.user, organization=self.org, role="office", is_mobile_worker=False)
        self.client.force_login(self.user)

    def test_customer_create_accepts_manual_number(self):
        response = self.client.post(reverse("next-customer-create"), {
            "type": "private",
            "first_name": "Mara",
            "last_name": "Beispiel",
            "email": "mara@example.test",
            "street": "Musterstraße 1",
            "postal_code": "60311",
            "city": "Frankfurt",
            "country": "DE",
            "customer_number": "K-TEST-9001",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Customer.objects.filter(organization=self.org, number="K-TEST-9001").exists())

    def test_customer_create_returns_to_project_with_customer_selected(self):
        response = self.client.post(reverse("next-customer-create") + "?next=project", {
            "next": "project",
            "type": "private",
            "first_name": "Tool",
            "last_name": "Time",
            "street": "Testweg 2",
            "postal_code": "10115",
            "city": "Berlin",
            "country": "DE",
        })
        self.assertEqual(response.status_code, 302)
        customer = Customer.objects.get(organization=self.org, first_name="Tool")
        self.assertEqual(response.url, f"/projects/new/?customer={customer.pk}")

    def test_project_can_be_created_with_tooltime_minimum(self):
        customer = Customer.objects.create(organization=self.org, number="K-1", type="private", first_name="Max", last_name="Muster", active=True)
        response = self.client.post(reverse("next-project-create"), {
            "title": "Badsanierung Muster",
            "customer": str(customer.pk),
            "description": "",
            "object_location": "",
            "priority": "",
            "manager": "",
        })
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(organization=self.org, title="Badsanierung Muster")
        self.assertEqual(project.customer, customer)
        self.assertEqual(project.priority, "normal")

    def test_templates_use_tooltime_creation_information_architecture(self):
        customer = (ROOT / "templates/rebuild/customer_form.html").read_text(encoding="utf-8")
        project = (ROOT / "templates/rebuild/project_form.html").read_text(encoding="utf-8")
        self.assertIn("Details einblenden", customer)
        self.assertIn("Kundennummer", customer)
        self.assertIn("Abweichenden Ausführungsort hinzufügen", customer)
        self.assertIn("Kunde auswählen", project)
        self.assertIn("Abweichenden Ausführungsort verwenden", project)
        self.assertIn("＋ Neuen Kunden anlegen", project)
        self.assertNotIn("Aufmaß / 3D", project)
        self.assertNotIn("Kein Wizard", project)
'''
    write("tests/test_tooltime_phase9_core_crud.py", test)


def patch_browser_smoke() -> None:
    path = "scripts/production_browser_smoke.py"
    text = read(path)
    replacements = {
        '("/customers/new/", ("Neuen Kunden anlegen", "Nur das eintragen"))': '("/customers/new/", ("Neuer Kunde", "Details einblenden", "＋ Erstellen"))',
        '("/projects/new/", ("Projekt anlegen", "Kein Wizard", "Aufmaß / 3D"))': '("/projects/new/", ("Neues Projekt", "Kunde auswählen", "Abweichenden Ausführungsort verwenden", "＋ Erstellen"))',
    }
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new, 1)
        elif new not in text:
            raise RuntimeError(f"Phase 9 browser smoke marker missing: {old}")

    old_block = '''            page.goto(urljoin(base_url, "projects/new/"), wait_until="domcontentloaded", timeout=30_000)
            html = page.content()
            if "9-Schritte-Projektassistent" in html or "wizard-step" in html:
                fail("legacy project wizard is still the primary creation flow")
            visible_controls = page.locator('form input:not([type="hidden"]), form select, form textarea')
            if visible_controls.count() < 4:
                fail("new project flow has too few controls and appears broken")
'''
    new_block = '''            page.goto(urljoin(base_url, "projects/new/"), wait_until="domcontentloaded", timeout=30_000)
            html = page.content()
            if "9-Schritte-Projektassistent" in html or "wizard-step" in html or "Aufmaß / 3D" in html:
                fail("legacy/non-ToolTime project creation content is still visible")
            if page.locator('input[name="title"]').count() != 1 or page.locator('select[name="customer"]').count() != 1:
                fail("ToolTime-like project title/customer controls are missing")
            if page.locator('[data-alt-location-toggle]').count() != 1:
                fail("project creation is missing the alternate-location switch")
            alt_panel = page.locator('[data-alt-location]')
            if alt_panel.count() != 1 or alt_panel.is_visible():
                fail("alternate location must be progressively disclosed")
            page.locator('[data-alt-location-toggle]').check()
            if not alt_panel.is_visible():
                fail("alternate-location switch does not reveal the location selector")
            page.locator('[data-alt-location-toggle]').uncheck()
            if alt_panel.is_visible():
                fail("alternate-location switch does not restore customer-address default")

            page.goto(urljoin(base_url, "customers/new/"), wait_until="domcontentloaded", timeout=30_000)
            if page.locator('[data-more-details]').count() != 1 or page.locator('[data-location-details]').count() != 1:
                fail("ToolTime-like customer progressive details are missing")
            if page.locator('input[name="customer_number"]').count() != 1:
                fail("customer creation is missing the customer-number field")
'''
    if old_block in text:
        text = text.replace(old_block, new_block, 1)
    elif "ToolTime-like project title/customer controls are missing" not in text:
        raise RuntimeError("Phase 9 browser interaction anchor missing")
    write(path, text)


def guard() -> None:
    views = read("erp/rebuild_views.py")
    customer = read("templates/rebuild/customer_form.html")
    project = read("templates/rebuild/project_form.html")
    smoke = read("scripts/production_browser_smoke.py")
    css = read("static/css/kayi-next.css")
    for needle in ("customer_number = forms.CharField", "def clean_priority", 'next_target == "project"'):
        if needle not in views:
            raise RuntimeError(f"Phase 9 view/form guard missing: {needle}")
    for needle in ("Neuer Kunde", "Details einblenden", "Kundennummer", "＋ Erstellen"):
        if needle not in customer:
            raise RuntimeError(f"Phase 9 customer UI missing: {needle}")
    for needle in ("Neues Projekt", "Kunde auswählen", "Abweichenden Ausführungsort verwenden", "＋ Neuen Kunden anlegen"):
        if needle not in project:
            raise RuntimeError(f"Phase 9 project UI missing: {needle}")
    if "Aufmaß / 3D" in project or "Kein Wizard" in project:
        raise RuntimeError("Phase 9 project form still contains legacy explanatory cards")
    if "ToolTime-like project title/customer controls are missing" not in smoke:
        raise RuntimeError("Phase 9 browser smoke interaction missing")
    if MARKER not in css:
        raise RuntimeError("Phase 9 CSS missing")
    compile(views, str(ROOT / "erp/rebuild_views.py"), "exec")
    compile(smoke, str(ROOT / "scripts/production_browser_smoke.py"), "exec")


patch_forms_and_views()
install_templates_and_css()
install_tests()
patch_browser_smoke()
guard()
print("A+BAU TOOLTIME PHASE 9 CORE CRUD 2026-08-20: Kunden- und Projekterstellung folgen jetzt dem aktuellen ToolTime-Kernflow mit progressiven Details, minimalem Projektstart, Kundennummer und Ausführungsort-Umschalter.")
