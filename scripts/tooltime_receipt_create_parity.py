from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI TOOLTIME RECEIPT CREATE PARITY 2026-09-07"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_ops() -> None:
    path = "erp/rebuild_ops.py"
    text = read(path)

    if "from django.core.exceptions import PermissionDenied, ValidationError" not in text:
        anchor = "from django.db import transaction\n"
        if anchor not in text:
            raise RuntimeError("Receipt parity: rebuild_ops import anchor missing")
        text = text.replace(anchor, "from django.core.exceptions import PermissionDenied, ValidationError\n" + anchor, 1)

    if "class ReceiptExpenseForm(forms.Form):" not in text:
        anchor = "\n\nclass EmployeeForm(StyledModelForm):"
        if anchor not in text:
            raise RuntimeError("Receipt parity: EmployeeForm anchor missing")
        receipt_form = r'''

class ReceiptExpenseForm(forms.Form):
    """Upload-first receipt capture matching ToolTime's expense flow."""

    ALLOWED_EXTENSIONS = {".pdf", ".xml", ".jpg", ".jpeg", ".png"}
    MAX_FILE_SIZE = 10 * 1024 * 1024

    customer = forms.ModelChoiceField(queryset=m.Customer.objects.none(), required=False)
    project = forms.ModelChoiceField(queryset=m.Project.objects.none(), required=False)
    supplier = forms.CharField(required=False, max_length=180)
    receipt_file = forms.FileField(required=True)
    amount_net = forms.DecimalField(required=True, min_value=0, max_digits=14, decimal_places=2, localize=True)
    tax_rate = forms.DecimalField(required=True, min_value=0, max_value=100, max_digits=5, decimal_places=2, initial=19, localize=True)
    expense_date = forms.DateField(required=True, initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    category = forms.CharField(required=False, max_length=100)
    paid = forms.BooleanField(required=False)
    description = forms.CharField(required=False, max_length=240)

    def __init__(self, *args, organization=None, customer=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization is None:
            return
        customers = m.Customer.objects.filter(organization=organization, active=True).order_by("company", "last_name", "first_name")
        projects = m.Project.objects.filter(organization=organization, archived=False).select_related("customer").order_by("-updated_at")
        self.fields["customer"].queryset = customers
        if customer is not None:
            projects = projects.filter(customer=customer)
            self.fields["customer"].initial = customer
        self.fields["project"].queryset = projects

    def clean_receipt_file(self):
        upload = self.cleaned_data["receipt_file"]
        name = (getattr(upload, "name", "") or "").lower()
        suffix = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        if suffix not in self.ALLOWED_EXTENSIONS:
            raise ValidationError("Bitte PDF, XML, JPG, JPEG oder PNG hochladen.")
        if getattr(upload, "size", 0) > self.MAX_FILE_SIZE:
            raise ValidationError("Der Beleg darf maximal 10 MB groß sein.")
        return upload

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get("customer")
        project = cleaned.get("project")
        if project is not None and customer is not None and project.customer_id != customer.pk:
            self.add_error("project", "Das Projekt gehört nicht zum ausgewählten Kunden.")
        elif project is not None and customer is None:
            cleaned["customer"] = project.customer
        return cleaned
'''
        text = text.replace(anchor, receipt_form + anchor, 1)

    helper_marker = "def _receipt_context_customer(request, org):"
    if helper_marker not in text:
        anchor = "\n\n@login_required\ndef expense_list(request):"
        if anchor not in text:
            raise RuntimeError("Receipt parity: expense_list anchor missing")
        helpers = r'''


def _receipt_numeric_id(value):
    value = str(value or "").strip()
    return int(value) if value.isdigit() else None


def _receipt_context_customer(request, org):
    customer_id = _receipt_numeric_id(
        request.POST.get("customer")
        or request.GET.get("customer")
        or request.GET.get("customerId")
    )
    project_id = _receipt_numeric_id(request.POST.get("project") or request.GET.get("project"))
    project = None
    if project_id:
        project = (
            m.Project.objects.filter(organization=org, pk=project_id, archived=False)
            .select_related("customer")
            .first()
        )
    customer = None
    if customer_id:
        customer = m.Customer.objects.filter(organization=org, pk=customer_id, active=True).first()
    if customer is None and project is not None:
        customer = project.customer
    if project is not None and customer is not None and project.customer_id != customer.pk:
        project = None
    return customer, project
'''
        text = text.replace(anchor, helpers + anchor, 1)

    pattern = re.compile(
        r'@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef expense_edit\(request, pk=None\):.*?(?=\n\n@login_required\ndef employee_list\(request\):)',
        re.S,
    )
    replacement = r'''@login_required
@require_http_methods(["GET", "POST"])
def expense_edit(request, pk=None):
    org = _org(request)
    from erp.services.permissions import role_for
    if role_for(request.user) not in {"admin", "office", "project_manager", "accounting"}:
        raise PermissionDenied("Belege sind nur für das Büro freigegeben.")
    expense = get_object_or_404(m.Expense, organization=org, pk=pk) if pk else None

    # Existing expenses keep the detailed accounting editor. New expenses use the
    # ToolTime receipt-first workflow and create the linked Document automatically.
    if expense is not None or request.GET.get("mode") == "manual":
        form = ExpenseForm(request.POST or None, instance=expense, organization=org)
        if request.method == "POST" and form.is_valid():
            obj = form.save(commit=False)
            obj.organization = org
            obj.save()
            messages.success(request, "Ausgabe gespeichert.")
            return redirect("next-expenses")
        return render(request, "rebuild/ops_form.html", {"form": form, "kind": "expense", "object": expense})

    selected_customer, selected_project = _receipt_context_customer(request, org)
    initial = {"expense_date": timezone.localdate(), "tax_rate": 19}
    if selected_customer is not None:
        initial["customer"] = selected_customer
    if selected_project is not None:
        initial["project"] = selected_project

    form = ReceiptExpenseForm(
        request.POST or None,
        request.FILES or None,
        organization=org,
        customer=selected_customer,
        initial=initial,
    )

    if request.method == "POST" and form.is_valid():
        project = form.cleaned_data.get("project")
        customer = form.cleaned_data.get("customer")
        if customer is None and project is not None:
            customer = project.customer
        upload = form.cleaned_data["receipt_file"]
        safe_name = (getattr(upload, "name", "beleg") or "beleg").rsplit("/", 1)[-1]
        description = (form.cleaned_data.get("description") or "").strip() or safe_name
        supplier = (form.cleaned_data.get("supplier") or "").strip()

        with transaction.atomic():
            document = m.Document(
                organization=org,
                customer=customer,
                project=project,
                title=safe_name,
                category="other",
                mime_type=getattr(upload, "content_type", "") or "",
                size=getattr(upload, "size", 0) or 0,
                metadata={
                    "kind": "expense_receipt",
                    "source": "tooltime-receipt-create",
                    "supplier": supplier,
                    "amount_net": str(form.cleaned_data["amount_net"]),
                    "tax_rate": str(form.cleaned_data["tax_rate"]),
                },
                uploaded_by=request.user,
            )
            document.file.save(safe_name, upload, save=False)
            document.save()
            expense = m.Expense.objects.create(
                organization=org,
                supplier=supplier,
                description=description,
                amount_net=form.cleaned_data["amount_net"],
                tax_rate=form.cleaned_data["tax_rate"],
                expense_date=form.cleaned_data["expense_date"],
                category=(form.cleaned_data.get("category") or "").strip(),
                paid=bool(form.cleaned_data.get("paid")),
                project=project,
                document=document,
            )

        messages.success(request, "Beleg und Ausgabe wurden gespeichert.")
        if customer is not None:
            return redirect("next-customer-detail", pk=customer.pk)
        return redirect("next-expenses")

    suppliers = list(
        m.Expense.objects.filter(organization=org)
        .exclude(supplier="")
        .order_by("supplier")
        .values_list("supplier", flat=True)
        .distinct()[:200]
    )
    customers = form.fields["customer"].queryset
    projects = form.fields["project"].queryset
    cancel_url = (
        f"/customers/{selected_customer.pk}/" if selected_customer is not None else "/expenses/"
    )
    return render(request, "rebuild/expense_receipt_form.html", {
        "receipt_form": form,
        "selected_customer": selected_customer,
        "selected_project": selected_project,
        "customers": customers,
        "projects": projects,
        "suppliers": suppliers,
        "cancel_url": cancel_url,
    })
'''
    text, count = pattern.subn(lambda match: replacement, text, count=1)
    if count != 1:
        raise RuntimeError("Receipt parity: could not replace final expense_edit view")

    list_anchor = "def expense_list(request):\n    org = _org(request)\n"
    if list_anchor in text and list_anchor + '    from erp.services.permissions import role_for' not in text:
        text = text.replace(list_anchor, list_anchor + '    from erp.services.permissions import role_for\n    if role_for(request.user) not in {"admin", "office", "project_manager", "accounting"}:\n        raise PermissionDenied("Belege sind nur für das Büro freigegeben.")\n', 1)

    compile(text, str(ROOT / path), "exec")
    write(path, text)


def write_template() -> None:
    template = r'''{% extends 'rebuild/base.html' %}
{% block title %}Beleg erfassen · A+Bau{% endblock %}
{% block content %}
<style>
  .tt-receipt-page{max-width:1480px;margin:-6px auto 0;color:#263445}.tt-receipt-form{display:block}.tt-receipt-toolbar{display:grid;grid-template-columns:32px 1fr auto;align-items:center;gap:12px;padding:8px 0 30px;border-bottom:1px solid #e8edf2}.tt-receipt-back{display:grid;place-items:center;width:30px;height:30px;text-decoration:none;color:#34495e;font-size:24px}.tt-receipt-toolbar h1{font-size:20px;line-height:1.2;margin:0;font-weight:700;color:#263445}.tt-receipt-actions{display:flex;gap:12px}.tt-receipt-action{border:1px solid #dbe2e9;border-radius:9px;background:#f5f7f9;padding:11px 18px;font:inherit;font-weight:650;color:#2d3947;text-decoration:none;cursor:pointer}.tt-receipt-action.primary{background:var(--ab-v3-gold,#b59652);border-color:var(--ab-v3-gold,#b59652);color:#201d16;min-width:84px}.tt-receipt-action.primary:disabled{opacity:.45;cursor:not-allowed}.tt-receipt-grid{display:grid;grid-template-columns:minmax(0,2.05fr) minmax(330px,.95fr);gap:68px;padding:54px 28px 30px}.tt-receipt-upload-card{min-width:0;border-radius:10px;background:#f8fafc;padding:24px;min-height:650px}.tt-receipt-dropzone{min-height:600px;border:1.5px dashed #cbd6e1;border-radius:10px;background:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:34px;cursor:pointer;transition:border-color .16s,background .16s,box-shadow .16s}.tt-receipt-dropzone:hover,.tt-receipt-dropzone.is-dragging{border-color:#2184e8;background:#f7fbff;box-shadow:0 0 0 3px rgba(33,132,232,.08)}.tt-receipt-dropzone input{position:absolute;opacity:0;pointer-events:none;width:1px;height:1px}.tt-receipt-upload-icon{width:116px;height:92px;position:relative;margin-bottom:24px}.tt-receipt-upload-icon .paper{position:absolute;width:65px;height:78px;border-radius:8px;background:linear-gradient(145deg,#eef2f5,#dfe7ee);left:32px;top:4px;transform:rotate(5deg);box-shadow:0 8px 18px rgba(44,65,82,.08)}.tt-receipt-upload-icon .photo{position:absolute;width:58px;height:46px;border:6px solid #eef2f5;border-radius:7px;background:#fff;left:4px;top:34px;transform:rotate(-4deg)}.tt-receipt-upload-icon .photo:after{content:'●▲';font-size:18px;letter-spacing:-5px;color:#0d3d5a;position:absolute;left:12px;top:8px}.tt-receipt-upload-icon .up{position:absolute;display:grid;place-items:center;width:34px;height:34px;border-radius:50%;background:#0e486b;color:#fff;right:3px;bottom:1px;font-size:21px;font-weight:800}.tt-receipt-upload-button{display:inline-flex;align-items:center;gap:9px;border-radius:9px;background:#f1f4f7;color:#263445;padding:11px 18px;font-weight:700;margin-bottom:13px}.tt-receipt-help{font-size:14px;color:#8190a1;max-width:560px;line-height:1.55}.tt-receipt-file-state{display:none;margin-top:14px;padding:11px 15px;border-radius:8px;background:#eaf5ff;color:#145f9f;font-size:14px;font-weight:650;max-width:90%;overflow-wrap:anywhere}.tt-receipt-file-state.is-visible{display:block}.tt-receipt-side{padding-top:4px}.tt-receipt-customer{display:flex;align-items:center;gap:10px;color:#1479dc;text-decoration:none;font-weight:750;margin:0 0 18px 8px}.tt-receipt-customer-icon{font-size:20px}.tt-receipt-side-field{margin-bottom:16px}.tt-receipt-side-field label{display:block;font-size:12px;font-weight:700;color:#6c7b8b;margin:0 0 6px 4px}.tt-receipt-side-field select,.tt-receipt-side-field input{width:100%;min-height:44px;border:1px solid #d3dce5;border-radius:8px;background:#fff;padding:0 14px;font:inherit;color:#344253;box-sizing:border-box;outline:none}.tt-receipt-side-field select:focus,.tt-receipt-side-field input:focus{border-color:#2786e5;box-shadow:0 0 0 3px rgba(39,134,229,.1)}.tt-receipt-side-field input::placeholder{color:#8a99aa}.tt-receipt-error{margin:7px 3px 0;color:#bb3041;font-size:13px}.tt-receipt-details{display:none;margin-top:18px;padding:22px;border:1px solid #dce5ed;border-radius:10px;background:#fff;text-align:left;width:min(620px,100%);box-sizing:border-box}.tt-receipt-details.is-visible{display:block}.tt-receipt-details h2{font-size:16px;margin:0 0 5px}.tt-receipt-details>p{font-size:13px;color:#7b8a99;margin:0 0 17px}.tt-receipt-detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.tt-receipt-detail-grid .wide{grid-column:1/-1}.tt-receipt-detail-grid label{display:block;font-size:12px;font-weight:700;color:#596878;margin-bottom:6px}.tt-receipt-detail-grid input{width:100%;height:42px;border:1px solid #d3dce5;border-radius:8px;padding:0 11px;box-sizing:border-box;font:inherit}.tt-receipt-paid{display:flex!important;align-items:center;gap:9px;margin-top:5px}.tt-receipt-paid input{width:18px;height:18px}.tt-receipt-global-errors{margin-bottom:15px;padding:11px 14px;background:#fff0f2;border:1px solid #f0cbd0;border-radius:8px;color:#a92839;font-size:13px}.tt-receipt-drop-error{margin-top:10px;color:#b83242;font-size:13px}.tt-receipt-no-customer{margin:0 0 18px}.tt-receipt-no-customer select{width:100%;min-height:44px;border:1px solid #d3dce5;border-radius:8px;background:#fff;padding:0 14px;font:inherit}.tt-receipt-security{font-size:12px;color:#8a98a8;line-height:1.5;margin:22px 8px 0}.tt-receipt-security strong{color:#607083}@media(max-width:980px){.tt-receipt-grid{grid-template-columns:1fr;gap:26px;padding:28px 0}.tt-receipt-side{order:-1}.tt-receipt-upload-card{min-height:auto}.tt-receipt-dropzone{min-height:430px}.tt-receipt-toolbar{padding-bottom:18px}}@media(max-width:620px){.tt-receipt-toolbar{grid-template-columns:28px 1fr}.tt-receipt-actions{grid-column:1/-1;justify-content:flex-end}.tt-receipt-grid{padding-top:20px}.tt-receipt-upload-card{padding:12px}.tt-receipt-dropzone{min-height:350px;padding:22px 14px}.tt-receipt-detail-grid{grid-template-columns:1fr}.tt-receipt-detail-grid .wide{grid-column:auto}}
</style>

<div class="tt-receipt-page" data-tooltime-receipt-create="1">
<form id="receipt-create-form" class="tt-receipt-form" method="post" enctype="multipart/form-data" novalidate>
  {% csrf_token %}
  <header class="tt-receipt-toolbar">
    <a class="tt-receipt-back" href="{{ cancel_url }}" aria-label="Zurück">←</a>
    <div><h1>Beleg erfassen</h1><a class="tt-receipt-manual" href="?mode=manual{% if selected_project %}&project={{ selected_project.pk }}{% endif %}">Ausgabe ohne Beleg erfassen</a></div>
    <div class="tt-receipt-actions">
      <a class="tt-receipt-action" href="{{ cancel_url }}">Abbrechen</a>
      <button id="receipt-save" class="tt-receipt-action primary" type="submit" disabled>Speichern</button>
    </div>
  </header>

  <div class="tt-receipt-grid">
    <section class="tt-receipt-upload-card">
      {% if receipt_form.non_field_errors %}<div class="tt-receipt-global-errors">{{ receipt_form.non_field_errors }}</div>{% endif %}
      <label id="receipt-dropzone" class="tt-receipt-dropzone" for="receipt-file" tabindex="0" data-receipt-dropzone="1">
        <input id="receipt-file" name="receipt_file" type="file" accept=".pdf,.xml,.jpg,.jpeg,.png,application/pdf,application/xml,text/xml,image/jpeg,image/png" required>
        <div class="tt-receipt-upload-icon" aria-hidden="true"><span class="paper"></span><span class="photo"></span><span class="up">↥</span></div>
        <span class="tt-receipt-upload-button">↥&nbsp; Ausgabe als Beleg hochladen</span>
        <span class="tt-receipt-help">Oder Beleg hierher ziehen. Unterstützt .pdf, .xml, .jpg, .jpeg oder .png (max. 10 MB).</span>
        <span id="receipt-file-state" class="tt-receipt-file-state"></span>
        {% for error in receipt_form.receipt_file.errors %}<span class="tt-receipt-drop-error">{{ error }}</span>{% endfor %}

        <div id="receipt-details" class="tt-receipt-details {% if receipt_form.errors %}is-visible{% endif %}" data-force-open="{% if receipt_form.errors %}1{% else %}0{% endif %}" onclick="event.preventDefault();event.stopPropagation();">
          <h2>Belegdaten prüfen</h2>
          <p>Nach dem Hochladen nur noch die für die Buchung nötigen Angaben ergänzen.</p>
          <div class="tt-receipt-detail-grid">
            <div><label for="id_amount_net">Netto-Betrag</label><input id="id_amount_net" name="amount_net" inputmode="decimal" value="{{ receipt_form.amount_net.value|default_if_none:'' }}" placeholder="0,00" required>{% for error in receipt_form.amount_net.errors %}<div class="tt-receipt-error">{{ error }}</div>{% endfor %}</div>
            <div><label for="id_tax_rate">MwSt. (%)</label><input id="id_tax_rate" name="tax_rate" inputmode="decimal" value="{{ receipt_form.tax_rate.value|default_if_none:'19' }}" required>{% for error in receipt_form.tax_rate.errors %}<div class="tt-receipt-error">{{ error }}</div>{% endfor %}</div>
            <div><label for="id_expense_date">Belegdatum</label><input id="id_expense_date" name="expense_date" type="date" value="{{ receipt_form.expense_date.value|date:'Y-m-d'|default:receipt_form.expense_date.value }}" required>{% for error in receipt_form.expense_date.errors %}<div class="tt-receipt-error">{{ error }}</div>{% endfor %}</div>
            <div><label for="id_category">Kategorie</label><input id="id_category" name="category" value="{{ receipt_form.category.value|default_if_none:'' }}" placeholder="Optional">{% for error in receipt_form.category.errors %}<div class="tt-receipt-error">{{ error }}</div>{% endfor %}</div>
            <div class="wide"><label for="id_description">Beschreibung</label><input id="id_description" name="description" value="{{ receipt_form.description.value|default_if_none:'' }}" placeholder="Optional – sonst wird der Dateiname verwendet">{% for error in receipt_form.description.errors %}<div class="tt-receipt-error">{{ error }}</div>{% endfor %}</div>
            <div class="wide"><label class="tt-receipt-paid"><input name="paid" type="checkbox" value="1" {% if receipt_form.paid.value %}checked{% endif %}> Bereits bezahlt</label></div>
          </div>
        </div>
      </label>
    </section>

    <aside class="tt-receipt-side">
      {% if selected_customer %}
        <a class="tt-receipt-customer" href="{% url 'next-customer-detail' selected_customer.pk %}"><span class="tt-receipt-customer-icon">♙</span><span>{{ selected_customer.display_name }}</span></a>
        <input type="hidden" name="customer" value="{{ selected_customer.pk }}">
      {% else %}
        <div class="tt-receipt-no-customer tt-receipt-side-field">
          <label for="receipt-customer">Kunde</label>
          <select id="receipt-customer" name="customer">
            <option value="">Kunde auswählen (optional)</option>
            {% for customer in customers %}<option value="{{ customer.pk }}" {% if receipt_form.customer.value|stringformat:'s' == customer.pk|stringformat:'s' %}selected{% endif %}>{{ customer.display_name }}</option>{% endfor %}
          </select>
          {% for error in receipt_form.customer.errors %}<div class="tt-receipt-error">{{ error }}</div>{% endfor %}
        </div>
      {% endif %}

      <div class="tt-receipt-side-field">
        <label for="receipt-project">Projekt</label>
        <select id="receipt-project" name="project">
          <option value="">▢ &nbsp; Projekt auswählen (optional)</option>
          {% for project in projects %}<option value="{{ project.pk }}" data-customer="{{ project.customer_id }}" {% if receipt_form.project.value|stringformat:'s' == project.pk|stringformat:'s' %}selected{% endif %}>{{ project.number }} · {{ project.title }}</option>{% endfor %}
        </select>
        {% for error in receipt_form.project.errors %}<div class="tt-receipt-error">{{ error }}</div>{% endfor %}
      </div>

      <div class="tt-receipt-side-field">
        <label for="receipt-supplier">Lieferant</label>
        <input id="receipt-supplier" name="supplier" list="receipt-suppliers" value="{{ receipt_form.supplier.value|default_if_none:'' }}" placeholder="▱  Lieferant auswählen (optional)" autocomplete="off">
        <datalist id="receipt-suppliers">{% for supplier in suppliers %}<option value="{{ supplier }}"></option>{% endfor %}</datalist>
        {% for error in receipt_form.supplier.errors %}<div class="tt-receipt-error">{{ error }}</div>{% endfor %}
      </div>

      <p class="tt-receipt-security"><strong>Belegablage:</strong> Die Originaldatei wird dem Vorgang als Dokument zugeordnet. Kunde und Projekt bleiben optional; bei einem Projekt wird der zugehörige Kunde automatisch übernommen.</p>
    </aside>
  </div>
</form>
</div>

<script>
(function(){
  const input=document.getElementById('receipt-file');
  const drop=document.getElementById('receipt-dropzone');
  const state=document.getElementById('receipt-file-state');
  const details=document.getElementById('receipt-details');
  const save=document.getElementById('receipt-save');
  const customer=document.getElementById('receipt-customer');
  const project=document.getElementById('receipt-project');
  if(!input||!drop||!details||!save)return;

  function showFile(){
    const file=input.files&&input.files[0];
    if(file){
      const mb=(file.size/1024/1024).toFixed(file.size>1024*1024?1:2);
      state.textContent=file.name+' · '+mb+' MB';
      state.classList.add('is-visible');
      details.classList.add('is-visible');
      save.disabled=false;
    }else{
      state.classList.remove('is-visible');
      if(details.dataset.forceOpen!=='1')details.classList.remove('is-visible');
      save.disabled=true;
    }
  }
  input.addEventListener('change',showFile);
  ['dragenter','dragover'].forEach(type=>drop.addEventListener(type,e=>{e.preventDefault();drop.classList.add('is-dragging');}));
  ['dragleave','drop'].forEach(type=>drop.addEventListener(type,e=>{e.preventDefault();drop.classList.remove('is-dragging');}));
  drop.addEventListener('drop',e=>{if(e.dataTransfer&&e.dataTransfer.files&&e.dataTransfer.files.length){input.files=e.dataTransfer.files;showFile();}});
  drop.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target===drop){e.preventDefault();input.click();}});

  function filterProjects(){
    if(!customer||!project)return;
    const cid=customer.value;
    Array.from(project.options).forEach((option,index)=>{if(index===0)return;const visible=!cid||option.dataset.customer===cid;option.hidden=!visible;option.disabled=!visible;});
    if(project.selectedOptions.length&&project.selectedOptions[0].disabled)project.value='';
  }
  if(customer){customer.addEventListener('change',filterProjects);filterProjects();}
  showFile();
})();
</script>
{% endblock %}
'''
    write("templates/rebuild/expense_receipt_form.html", template)

    # Direct customer receipts have no project; include the document relation in
    # the existing customer cockpit and totals, without duplicating either record.
    views = read("erp/rebuild_views.py")
    views = views.replace(
        "m.Expense.objects.filter(organization=org, project__customer=customer)",
        "m.Expense.objects.filter(organization=org).filter(Q(project__customer=customer) | Q(document__customer=customer)).distinct()",
    )
    write("erp/rebuild_views.py", views)


def patch_customer_entrypoint() -> None:
    path = "templates/rebuild/customer_detail.html"
    if not (ROOT / path).exists():
        return
    text = read(path)
    text = text.replace(
        "{% url 'next-expense-create' %}?project={{ projects.0.pk }}",
        "{% url 'next-expense-create' %}?customer={{ customer.pk }}&project={{ projects.0.pk }}",
    )
    text = text.replace(
        "{% else %}<a href=\"{% url 'next-expense-create' %}\">▣ Ausgabe hinzufügen</a>{% endif %}",
        "{% else %}<a href=\"{% url 'next-expense-create' %}?customer={{ customer.pk }}\">▣ Ausgabe hinzufügen</a>{% endif %}",
    )
    write(path, text)


def write_tests() -> None:
    tests = r'''import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from erp import models as m


class ToolTimeReceiptCreateParityTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.mkdtemp(prefix="kayi-receipt-test-")
        self.media_override = override_settings(MEDIA_ROOT=self.media_dir)
        self.media_override.enable()
        self.org = m.Organization.objects.create(name="A+Bau Receipt Test")
        User = get_user_model()
        self.user = User.objects.create_user(username="receipt-office", password="test-pass")
        profile, _ = m.UserProfile.objects.get_or_create(user=self.user)
        profile.organization = self.org
        profile.role = "office"
        profile.save()
        self.customer = m.Customer.objects.create(
            organization=self.org,
            number="K-R-0001",
            type="business",
            company="Acar Haustechnik",
        )
        self.project = m.Project.objects.create(
            organization=self.org,
            customer=self.customer,
            number="P-R-0001",
            title="Medrese",
            status="inquiry",
        )
        self.client.force_login(self.user)

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_dir, ignore_errors=True)
        super().tearDown()

    def test_receipt_page_uses_customer_context_and_upload_first_ui(self):
        response = self.client.get(reverse("next-expense-create"), {"customer": self.customer.pk, "project": self.project.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Beleg erfassen")
        self.assertContains(response, "data-tooltime-receipt-create=\"1\"")
        self.assertContains(response, "data-receipt-dropzone=\"1\"")
        self.assertContains(response, "Ausgabe als Beleg hochladen")
        self.assertContains(response, "Acar Haustechnik")
        self.assertContains(response, "Projekt auswählen (optional)")
        self.assertContains(response, "Lieferant auswählen (optional)")

    def test_pdf_upload_creates_linked_document_and_expense(self):
        upload = SimpleUploadedFile("rechnung-4711.pdf", b"%PDF-1.4\nreceipt-test\n", content_type="application/pdf")
        response = self.client.post(
            reverse("next-expense-create") + f"?customer={self.customer.pk}",
            {
                "customer": str(self.customer.pk),
                "project": str(self.project.pk),
                "supplier": "Test Lieferant GmbH",
                "amount_net": "120.50",
                "tax_rate": "19.00",
                "expense_date": "2026-09-07",
                "category": "Material",
                "description": "Materialbeleg",
                "receipt_file": upload,
            },
        )
        self.assertRedirects(response, reverse("next-customer-detail", args=[self.customer.pk]))
        expense = m.Expense.objects.get(organization=self.org)
        self.assertEqual(expense.amount_net, Decimal("120.50"))
        self.assertEqual(expense.project, self.project)
        self.assertEqual(expense.supplier, "Test Lieferant GmbH")
        self.assertIsNotNone(expense.document_id)
        self.assertEqual(expense.document.customer, self.customer)
        self.assertEqual(expense.document.project, self.project)
        self.assertEqual(expense.document.metadata.get("kind"), "expense_receipt")
        self.assertTrue(expense.document.file.name.endswith(".pdf"))

    def test_rejects_unsupported_receipt_file(self):
        upload = SimpleUploadedFile("payload.exe", b"not-a-receipt", content_type="application/octet-stream")
        response = self.client.post(
            reverse("next-expense-create"),
            {
                "customer": str(self.customer.pk),
                "project": str(self.project.pk),
                "supplier": "Test",
                "amount_net": "10.00",
                "tax_rate": "19.00",
                "expense_date": "2026-09-07",
                "receipt_file": upload,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bitte PDF, XML, JPG, JPEG oder PNG hochladen.")
        self.assertFalse(m.Expense.objects.filter(organization=self.org).exists())
        self.assertFalse(m.Document.objects.filter(organization=self.org).exists())
'''
    write("tests/test_tooltime_receipt_create.py", tests)


def guard() -> None:
    ops = read("erp/rebuild_ops.py")
    template = read("templates/rebuild/expense_receipt_form.html")
    tests = read("tests/test_tooltime_receipt_create.py")
    required_ops = ["class ReceiptExpenseForm", "request.FILES or None", "expense_receipt", "tooltime-receipt-create"]
    for token in required_ops:
        if token not in ops:
            raise RuntimeError(f"Receipt parity guard missing in ops: {token}")
    for token in ("data-tooltime-receipt-create", "data-receipt-dropzone", "receipt_file", "max. 10 MB", "Belegdaten prüfen"):
        if token not in template:
            raise RuntimeError(f"Receipt parity guard missing in template: {token}")
    if "test_pdf_upload_creates_linked_document_and_expense" not in tests:
        raise RuntimeError("Receipt parity functional test missing")


patch_ops()
write_template()
patch_customer_entrypoint()
write_tests()
guard()
print(f"{MARKER}: upload-first receipt UI, customer/project context, persisted Document and functional tests installed.")
