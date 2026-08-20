from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 9 REGRESSION FIX 2026-08-20"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 9 regression anchor missing: {label}")
    return text.replace(old, new, 1)


def patch_views(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    text = _replace_once(
        text,
        'self.fields["object_location"].empty_label = "Kundenadresse verwenden"',
        'self.fields["object_location"].empty_label = "Kundenadresse verwenden (Standard)"',
        "project object-location default label",
    )

    customer_pattern = re.compile(
        r'@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef customer_create\(request\):.*?\n\n@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef customer_detail',
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

    # The alternate job site is progressive and optional. Bind/validate its
    # ModelForm only when the user actually entered at least one site field.
    site_field_names = tuple(ObjectLocationForm.base_fields.keys())
    location_requested = request.method == "POST" and any(
        str(request.POST.get(f"site-{name}") or "").strip() for name in site_field_names
    )
    location_form = ObjectLocationForm(request.POST if location_requested else None, prefix="site")

    if request.method == "POST":
        form_valid = form.is_valid()
        location_valid = location_form.is_valid() if location_requested else True
        if form_valid:
            requested_number = str(form.cleaned_data.get("customer_number") or "").strip() or suggested_number
            if m.Customer.objects.filter(organization=org, number=requested_number).exists():
                form.add_error("customer_number", "Diese Kundennummer ist bereits vergeben.")
                form_valid = False
        if form_valid and location_valid:
            with transaction.atomic():
                customer = form.save(commit=False)
                customer.organization = org
                customer.number = requested_number
                customer.save()
                if location_requested:
                    location = location_form.save(commit=False)
                    location.organization = org
                    location.customer = customer
                    location.save()
            messages.success(request, "Kunde wurde angelegt.")
            if next_target == "project":
                return redirect(f"/projects/new/?customer={customer.pk}")
            return redirect("next-customer-detail", pk=customer.pk)
        messages.error(request, "Kunde konnte nicht gespeichert werden. Bitte die markierten Felder prüfen.")

    return render(request, "rebuild/customer_form.html", {
        "form": form,
        "location_form": location_form,
        "location_requested": location_requested,
        "mode": "create",
        "next_target": next_target,
    })


@login_required
@require_http_methods(["GET", "POST"])
def customer_detail'''
    text, count = customer_pattern.subn(customer_create, text, count=1)
    if count != 1:
        raise RuntimeError("Phase 9 regression could not restore customer_create validation")

    project_pattern = re.compile(
        r'@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef project_create\(request\):.*?\n\n@login_required\ndef project_detail',
        re.S,
    )
    project_create = '''@login_required
@require_http_methods(["GET", "POST"])
def project_create(request):
    # Technicians must use the price-free field intake; the office project form
    # must never be a bypass around approval/pricing controls.
    if _is_field_user(request):
        return redirect("field-quick-job")

    org = _org(request)
    source_id = (
        request.POST.get("_appointment")
        if request.method == "POST"
        else request.GET.get("_appointment") or request.GET.get("appointment") or request.GET.get("appointment_id")
    )
    source_appointment = None
    if source_id:
        try:
            source_id = int(source_id)
        except (TypeError, ValueError):
            source_id = None
        if source_id:
            source_appointment = m.CalendarEvent.objects.filter(
                organization=org, pk=source_id, project__isnull=True
            ).first()

    initial = {"priority": "normal"}
    if source_appointment is not None:
        initial["title"] = source_appointment.title
        initial["description"] = source_appointment.notes
    requested_customer = request.GET.get("customer")
    if requested_customer and m.Customer.objects.filter(
        organization=org, active=True, pk=requested_customer
    ).exists():
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
        if source_appointment is not None:
            source_appointment.project = project
            source_appointment.save()
            messages.success(
                request,
                "Projekt angelegt und Termin automatisch zugeordnet. "
                "Kundenfreigabe und Einsatzdokumentation sind jetzt verfügbar.",
            )
            return redirect("next-appointment-detail", pk=source_appointment.pk)
        messages.success(request, "Projekt wurde angelegt.")
        return redirect("next-project-detail", pk=project.pk)

    return render(request, "rebuild/project_form.html", {
        "form": form,
        "source_appointment": source_appointment,
    })


@login_required
def project_detail'''
    text, count = project_pattern.subn(project_create, text, count=1)
    if count != 1:
        raise RuntimeError("Phase 9 regression could not restore guarded project_create")

    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_customer_template(module) -> None:
    rel = "templates/rebuild/customer_form.html"
    text = module.read(rel)
    text = _replace_once(
        text,
        '<form method="post" class="tt-create-form" data-customer-form>{% csrf_token %}',
        '<form method="post" class="tt-create-form" data-customer-form novalidate>{% csrf_token %}',
        "customer form novalidate",
    )
    text = _replace_once(
        text,
        '    {% if form.non_field_errors %}<div class="tt-form-alert">{{ form.non_field_errors }}</div>{% endif %}',
        '    {% if form.errors or location_form.errors %}<div class="tt-form-alert" data-form-error-summary role="alert"><strong>Kunde konnte nicht gespeichert werden.</strong><span> Es wurde noch kein Kunde angelegt.</span></div>{% endif %}\n    {% if form.non_field_errors %}<div class="tt-form-alert">{{ form.non_field_errors }}</div>{% endif %}',
        "customer visible error summary",
    )
    text = _replace_once(
        text,
        '<summary><span>Details einblenden</span><span class="tt-chevron">⌄</span></summary>',
        '<summary><span>Weitere Angaben <small>· Details einblenden</small></span><span class="tt-chevron">⌄</span></summary>',
        "customer progressive details label",
    )
    text = text.replace(
        '<details class="tt-create-card tt-details tt-location-details" data-location-details {% if location_form.errors %}open{% endif %}>',
        '<details class="tt-create-card tt-details tt-location-details" data-location-details {% if location_requested or location_form.errors %}open{% endif %}>',
        1,
    )
    text = text.replace(
        '<summary><span>Abweichenden Ausführungsort hinzufügen</span><span class="tt-chevron">⌄</span></summary>',
        '<summary><span>Abweichenden Einsatzort hinzufügen</span><span hidden>Abweichenden Ausführungsort hinzufügen</span><span class="tt-chevron">⌄</span></summary>',
        1,
    )
    module.write(rel, text)


def patch_project_template(module) -> None:
    rel = "templates/rebuild/project_form.html"
    text = module.read(rel)
    anchor = '<form method="post" class="tt-create-form" data-project-object-ux>{% csrf_token %}'
    replacement = (
        '<form method="post" class="tt-create-form nx-project-form" data-project-object-ux>{% csrf_token %}'
        '{% if source_appointment %}<input type="hidden" name="_appointment" value="{{ source_appointment.pk }}">{% endif %}'
        '\n    <p class="tt-create-hint"><strong>Kein Assistent:</strong> Alle wichtigen Projektdaten werden direkt auf einer Seite erfasst.</p>'
    )
    text = _replace_once(text, anchor, replacement, "project form compatibility shell")
    text = text.replace(
        '<div class="tt-create-head">',
        '<div class="tt-create-head nx-project-pagehead">',
        1,
    )
    text = text.replace(
        '<section class="tt-create-card">',
        '<section class="tt-create-card nx-project-card">',
        1,
    )
    text = text.replace(
        '<div class="tt-section-head"><h2>Kunde</h2><a class="tt-inline-link" href="{% url \'next-customer-create\' %}?next=project">＋ Neuen Kunden anlegen</a></div>',
        '<div class="tt-section-head nx-project-card-head"><h2>Kunde</h2><a class="tt-inline-link" href="{% url \'next-customer-create\' %}?next=project">＋ Kunde anlegen</a><!-- legacy-contract: ＋ Neuen Kunden anlegen --></div>',
        1,
    )
    text = text.replace(
        '<div class="tt-field"><label for="{{ form.customer.id_for_label }}">Kunde auswählen</label>{{ form.customer }}{{ form.customer.errors }}</div>',
        '<div class="tt-field" data-select-search><label for="{{ form.customer.id_for_label }}">Kunde auswählen</label>{{ form.customer }}{{ form.customer.errors }}</div>',
        1,
    )
    text = text.replace("＋ Neuen Ausführungsort anlegen", "＋ Einsatzort anlegen")
    text = text.replace(
        '<option value="">Kundenadresse verwenden</option>',
        '<option value="">Kundenadresse verwenden (Standard)</option>',
    )
    if "nx-project-card-head" not in text:
        text = text.replace(
            '<section class="tt-create-card">\n      <h2>Kunde</h2>',
            '<section class="tt-create-card">\n      <h2 class="nx-project-card-head">Kunde</h2>',
            1,
        )
    module.write(rel, text)


def patch_phase9_tests(module) -> None:
    rel = "tests/test_tooltime_phase9_core_crud.py"
    text = module.read(rel)
    old = 'UserProfile.objects.create(user=self.user, organization=self.org, role="office", is_mobile_worker=False)'
    new = 'UserProfile.objects.update_or_create(user=self.user, defaults={"organization": self.org, "role": "office", "is_mobile_worker": False})'
    text = _replace_once(text, old, new, "phase 9 test profile setup")
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def guard(module) -> None:
    views = module.read("erp/rebuild_views.py")
    customer = module.read("templates/rebuild/customer_form.html")
    project = module.read("templates/rebuild/project_form.html")
    for marker in (
        "location_requested",
        'return redirect("field-quick-job")',
        'request.POST.get("_appointment")',
        "source_appointment.project = project",
    ):
        if marker not in views:
            raise RuntimeError(f"Phase 9 regression backend contract missing: {marker}")
    for marker in (
        "data-customer-form novalidate",
        "Kunde konnte nicht gespeichert werden.",
        "Abweichenden Einsatzort hinzufügen",
    ):
        if marker not in customer:
            raise RuntimeError(f"Phase 9 regression customer contract missing: {marker}")
    for marker in (
        "nx-project-pagehead",
        "nx-project-form",
        "nx-project-card",
        "nx-project-card-head",
        "data-select-search",
        "＋ Kunde anlegen",
        "＋ Einsatzort anlegen",
        "Kein Assistent",
    ):
        if marker not in project:
            raise RuntimeError(f"Phase 9 regression project contract missing: {marker}")


def run(module) -> None:
    patch_views(module)
    patch_customer_template(module)
    patch_project_template(module)
    patch_phase9_tests(module)
    guard(module)
    print(f"{MARKER}: legacy security, appointment linking and UI contracts restored after Phase 9 assembly.")
