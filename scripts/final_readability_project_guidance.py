from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "20260811-1"
MARKER = "/* KAYI FINAL READABILITY 2026-08-11 */"

LATE_CSS = r'''
/* KAYI FINAL READABILITY 2026-08-11 */
/* Loaded after page-specific overlay CSS so compact legacy rules cannot shrink live UI again. */
body.nx-body {
  font-size: 15px !important;
  line-height: 1.5;
}

.nx-brand strong { font-size: 18px !important; }
.nx-brand small,
.nx-sidebar-foot { font-size: 13px !important; line-height: 1.5 !important; }
.nx-nav-label,
.nx-kicker { font-size: 12px !important; line-height: 1.35 !important; }
.nx-nav a { font-size: 14px !important; line-height: 1.4 !important; }
.nx-pagehead p { font-size: 15px !important; line-height: 1.5 !important; }
.nx-card-head h2 { font-size: 20px !important; }
.nx-card-head h3 { font-size: 17px !important; }
.nx-card-head p { font-size: 14px !important; line-height: 1.5 !important; }

.nx-body .nx-btn,
.nx-body button {
  font-size: 14px !important;
  line-height: 1.35 !important;
}
.nx-body input,
.nx-body select,
.nx-body textarea,
.nx-control,
.next-control {
  font-size: 14px !important;
  line-height: 1.45 !important;
}
.nx-body label,
.nx-field > label,
.nx-body .form-label,
.nx-body .field-label,
.nx-body .section-label {
  font-size: 13.5px !important;
  line-height: 1.4 !important;
}
.nx-body small,
.nx-body .helptext,
.nx-body .nx-help,
.nx-body .form-help,
.nx-body .field-help,
.nx-body .section-help {
  font-size: 12.5px !important;
  line-height: 1.5 !important;
}
.nx-table th,
.nx-item-table th { font-size: 12px !important; line-height: 1.35 !important; }
.nx-table td,
.nx-item-table td { font-size: 14px !important; line-height: 1.45 !important; }
.nx-table strong,
.nx-doc-title b { font-size: 14.5px !important; }
.nx-badge { font-size: 12px !important; }
.nx-meta,
.nx-tabs button,
.nx-tabs a { font-size: 13px !important; }
.nx-quick b,
.nx-event-time,
.nx-event b,
.nx-day-head,
.nx-job-time { font-size: 14px !important; }
.nx-quick small,
.nx-event small,
.nx-day-head small,
.nx-cal-event time,
.nx-cal-event b,
.nx-cal-event small,
.nx-job-card p,
.nx-job-address small,
.nx-doc-title small { font-size: 12px !important; line-height: 1.45 !important; }
.nx-job-card h3 { font-size: 16px !important; }
.nx-job-address p { font-size: 14px !important; }
.nx-job-actions a,
.nx-job-actions button,
.nx-mobile-tabs button { font-size: 13px !important; }

/* Signed field / Kundenfreigabe overlay: this stylesheet previously contained many 7–10px rules. */
.fa-mobile-shell { font-size: 15px !important; }
.fa-site-card small { font-size: 12.5px !important; }
.fa-site-card h2 { font-size: 20px !important; }
.fa-site-card p { font-size: 14px !important; line-height: 1.5 !important; }
.fa-site-actions a { font-size: 13px !important; }
.fa-progress span { font-size: 12.5px !important; line-height: 1.35 !important; }
.fa-section-head h2 { font-size: 18px !important; }
.fa-section-head p { font-size: 14px !important; line-height: 1.5 !important; }
.fa-block-head b { font-size: 14.5px !important; }
.fa-block-head small { font-size: 12.5px !important; }
.fa-field { font-size: 13.5px !important; }
.fa-photo-drop b { font-size: 14px !important; }
.fa-photo-drop small,
.fa-room-attachment small,
.fa-room-finish small { font-size: 12.5px !important; }
.fa-room-attachment b,
.fa-room-finish b { font-size: 14px !important; }
.fa-segmented span { font-size: 13px !important; }
.fa-price-head { font-size: 12.5px !important; }
.fa-price-row .nx-control { font-size: 13.5px !important; line-height: 1.4 !important; }
.fa-price-summary small { font-size: 12px !important; }
.fa-price-summary b { font-size: 14px !important; }
.fa-total-main b { font-size: 17px !important; }
.fa-price-summary label { font-size: 13px !important; }
.fa-consent { font-size: 13.5px !important; line-height: 1.55 !important; }
.fa-form-status { font-size: 13px !important; }
.fa-approved-card h2 { font-size: 18px !important; }
.fa-approved-card p { font-size: 14px !important; }
.fa-inline-meta span { font-size: 12px !important; }
.fa-work-toggle b { font-size: 15px !important; }
.fa-work-toggle small { font-size: 12.5px !important; }
.fa-locked-scope small { font-size: 12px !important; }
.fa-locked-scope p { font-size: 14px !important; }
.fa-locked-scope a { font-size: 13px !important; }
.fa-final-sign summary { font-size: 13px !important; }
.fa-complete-success b { font-size: 14px !important; }
.fa-complete-success small { font-size: 12.5px !important; }
.fa-doc-grid b { font-size: 13px !important; }
.fa-doc-phase { font-size: 12px !important; }
.fa-alert { font-size: 14px !important; line-height: 1.5 !important; }
.fa-quick-hero b { font-size: 14px !important; }
.fa-quick-hero small { font-size: 12.5px !important; }
.fa-toast { font-size: 13.5px !important; line-height: 1.45 !important; }
.fa-mic { font-size: 18px !important; }
.fa-remove-row { font-size: 18px !important; }
.nx-assistant-fab { font-size: 22px !important; }
.nx-menu-btn { font-size: 22px !important; }

/* Recovery UI for appointments without a project. */
.fa-project-missing-card { display: grid; gap: 16px; }
.fa-project-missing-card .fa-alert { padding: 14px 16px; }
.fa-project-missing-card .fa-alert strong { display: block; font-size: 16px; margin-bottom: 4px; }
.fa-project-missing-card .fa-alert span { display: block; }
.fa-project-steps { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 10px; }
.fa-project-step { border: 1px solid var(--fa-line,#e1e6e8); border-radius: 12px; padding: 12px; background: #fafcfc; }
.fa-project-step b { display: block; font-size: 14px; margin-bottom: 4px; }
.fa-project-step span { display: block; font-size: 13px; line-height: 1.45; color: var(--fa-muted,#6b777e); }
.fa-project-attach { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 10px; align-items: end; padding-top: 2px; }
.fa-project-attach label { display: grid; gap: 6px; font-weight: 800; }
.fa-project-create { display: flex; align-items: center; justify-content: space-between; gap: 14px; border-top: 1px solid var(--fa-line,#e1e6e8); padding-top: 14px; }
.fa-project-create b { display: block; font-size: 14.5px; margin-bottom: 3px; }
.fa-project-create small { display: block; }
.nx-link-context { margin-bottom: 16px; border-color: #cfe1df !important; background: #f5fbfa !important; }
.nx-link-context strong { font-size: 15px; }
.nx-link-context p { margin: 5px 0 0; font-size: 14px !important; color: var(--nx-muted); }

@media (max-width: 900px) {
  body.nx-body { font-size: 15px !important; }
  .nx-body input,
  .nx-body select,
  .nx-body textarea,
  .nx-control,
  .next-control { font-size: 16px !important; }
  .fa-project-steps { grid-template-columns: 1fr; }
  .fa-project-attach { grid-template-columns: 1fr; }
  .fa-project-create { display: grid; }
}
'''


def replace_once(path: Path, old: str, new: str, description: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Could not patch {description}: expected source fragment missing in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_field_urls() -> None:
    path = ROOT / "erp" / "field_authorization_urls.py"
    text = path.read_text(encoding="utf-8")
    route = '    path("appointments/<int:pk>/project/attach/", views.attach_project, name="field-attach-project"),\n'
    if "field-attach-project" in text:
        return
    anchor = '    path("appointments/<int:pk>/authorization/sign/", views.authorization_sign, name="field-authorization-sign"),\n'
    if anchor not in text:
        raise RuntimeError("Could not add appointment-project attachment route")
    path.write_text(text.replace(anchor, route + anchor, 1), encoding="utf-8")


def patch_field_views() -> None:
    path = ROOT / "erp" / "field_authorization_views.py"
    text = path.read_text(encoding="utf-8")
    if "from django.contrib import messages" not in text:
        anchor = "from django.contrib.auth.decorators import login_required\n"
        if anchor not in text:
            raise RuntimeError("Could not add django messages import")
        text = text.replace(anchor, "from django.contrib import messages\n" + anchor, 1)

    if "def attach_project(request, pk):" not in text:
        anchor = "\n\n@login_required\ndef field_job_detail(request, pk):\n"
        if anchor not in text:
            raise RuntimeError("Could not locate field_job_detail for project recovery insertion")
        block = '''\n\n@login_required\n@require_POST\ndef attach_project(request, pk):\n    org, event = _event_for(request, pk)\n    if event.project_id is not None:\n        messages.info(request, "Dieser Termin ist bereits einem Projekt zugeordnet.")\n        return redirect("next-appointment-detail", pk=event.pk)\n    project = get_object_or_404(\n        m.Project.objects.select_related("customer", "object_location"),\n        organization=org,\n        archived=False,\n        pk=request.POST.get("project_id"),\n    )\n    event.project = project\n    if not event.location and project.object_location:\n        location = project.object_location\n        event.location = ", ".join(\n            part for part in [location.street, f"{location.postal_code} {location.city}".strip()] if part\n        )\n    event.save()\n    messages.success(request, f"Termin wurde mit Projekt {project.number} · {project.title} verbunden.")\n    return redirect("next-appointment-detail", pk=event.pk)\n'''
        text = text.replace(anchor, block + anchor, 1)

    old = '    if event.project_id is None:\n        return render(request, "rebuild/appointment_detail.html", {"event": event, "project_missing": True})\n'
    new = '''    if event.project_id is None:\n        available_projects = (\n            m.Project.objects.filter(organization=org, archived=False)\n            .select_related("customer", "object_location")\n            .exclude(status="cancelled")\n            .order_by("-updated_at", "-pk")[:150]\n        )\n        return render(request, "rebuild/appointment_detail.html", {\n            "event": event,\n            "project_missing": True,\n            "available_projects": available_projects,\n        })\n'''
    if new not in text:
        if old not in text:
            raise RuntimeError("Could not add available projects to missing-project appointment page")
        text = text.replace(old, new, 1)

    path.write_text(text, encoding="utf-8")


def patch_project_create() -> None:
    path = ROOT / "erp" / "rebuild_views.py"
    text = path.read_text(encoding="utf-8")
    if "source_appointment" in text and "Projekt angelegt und Termin automatisch zugeordnet" in text:
        return
    pattern = re.compile(
        r'@login_required\n@require_http_methods\(\["GET", "POST"\]\)\ndef project_create\(request\):\n.*?\n\n@login_required\ndef project_detail\(request, pk\):',
        re.S,
    )
    match = pattern.search(text)
    if not match:
        raise RuntimeError("Could not locate project_create function for appointment handoff")
    replacement = '''@login_required\n@require_http_methods(["GET", "POST"])\ndef project_create(request):\n    org = _org(request)\n    source_pk = (request.GET.get("appointment") or request.POST.get("_appointment") or "").strip()\n    source_appointment = None\n    if source_pk.isdigit():\n        source_appointment = m.CalendarEvent.objects.filter(\n            organization=org, pk=int(source_pk), project__isnull=True\n        ).first()\n\n    initial = {}\n    if source_appointment is not None:\n        initial["title"] = source_appointment.title\n        initial["description"] = source_appointment.notes\n    if request.GET.get("customer"):\n        initial["customer"] = request.GET.get("customer")\n\n    form = ProjectForm(request.POST or None, organization=org, initial=initial)\n    if request.method == "POST" and form.is_valid():\n        project = form.save(commit=False)\n        project.organization = org\n        project.number = _unique_number(m.Project, org, "P")\n        project.status = "inquiry"\n        project.save()\n        form.save_m2m()\n        if source_appointment is not None:\n            source_appointment.project = project\n            source_appointment.save()\n            messages.success(request, "Projekt angelegt und Termin automatisch zugeordnet. Kundenfreigabe und Einsatzdokumentation sind jetzt verfügbar.")\n            return redirect("next-appointment-detail", pk=source_appointment.pk)\n        messages.success(request, "Projekt angelegt. Du kannst jetzt Termin, Angebot oder Dokumentation hinzufügen.")\n        return redirect("next-project-detail", pk=project.pk)\n    return render(request, "rebuild/project_form.html", {"form": form, "source_appointment": source_appointment})\n\n\n@login_required\ndef project_detail(request, pk):'''
    path.write_text(text[: match.start()] + replacement + text[match.end() :], encoding="utf-8")


def patch_appointment_template() -> None:
    path = ROOT / "templates" / "rebuild" / "appointment_detail.html"
    text = path.read_text(encoding="utf-8")
    marker = "Vorhandenes Projekt zuordnen"
    if marker in text:
        return
    old = '''  {% if project_missing %}\n    <section class="fa-card"><div class="fa-alert fa-alert-danger">Dieser Termin ist keinem Projekt zugeordnet. Für eine Kundenfreigabe bitte zuerst ein Projekt hinterlegen.</div></section>\n  {% else %}\n'''
    new = '''  {% if project_missing %}\n    <section class="fa-card fa-project-missing-card">\n      <div class="fa-alert fa-alert-danger">\n        <strong>Dieser Termin braucht zuerst ein Projekt.</strong>\n        <span>Kundenfreigabe, Preise, Fotos, Zeiterfassung und Abschlussdokumentation werden in KAYI immer einem Projekt zugeordnet.</span>\n      </div>\n      <div class="fa-project-steps" aria-label="So geht es weiter">\n        <div class="fa-project-step"><b>1 · Projekt wählen</b><span>Ein vorhandenes Projekt unten auswählen oder ein neues anlegen.</span></div>\n        <div class="fa-project-step"><b>2 · Termin verbinden</b><span>KAYI verknüpft diesen Termin direkt mit dem Projekt.</span></div>\n        <div class="fa-project-step"><b>3 · Einsatz fortsetzen</b><span>Danach erscheinen Kundenfreigabe, Preis, Fotos, Arbeit und PDF hier automatisch.</span></div>\n      </div>\n      {% if available_projects %}\n      <form class="fa-project-attach" method="post" action="{% url 'field-attach-project' event.pk %}">\n        {% csrf_token %}\n        <label>Vorhandenes Projekt zuordnen\n          <select class="nx-control" name="project_id" required>\n            <option value="">Projekt auswählen …</option>\n            {% for project in available_projects %}<option value="{{ project.pk }}">{{ project.number }} · {{ project.title }} · {{ project.customer.display_name }}</option>{% endfor %}\n          </select>\n        </label>\n        <button class="nx-btn nx-btn-accent" type="submit">Projekt zuordnen →</button>\n      </form>\n      {% endif %}\n      <div class="fa-project-create">\n        <div><b>Noch kein passendes Projekt?</b><small>Das neue Projekt wird nach dem Speichern automatisch mit diesem Termin verbunden.</small></div>\n        <a class="nx-btn nx-btn-primary" href="{% url 'next-project-create' %}?appointment={{ event.pk }}">＋ Neues Projekt anlegen</a>\n      </div>\n    </section>\n  {% else %}\n'''
    if old not in text:
        raise RuntimeError("Could not replace missing-project appointment warning with recovery UI")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_project_template() -> None:
    path = ROOT / "templates" / "rebuild" / "project_form.html"
    text = path.read_text(encoding="utf-8")
    if "source_appointment" in text and "Projekt anlegen & Termin verbinden" in text:
        return
    old_head = '<div class="nx-pagehead"><div><div class="nx-kicker">Auftrag starten</div><h1>Projekt anlegen</h1><p>Kein Wizard. Kunde, Auftrag und Team reichen für den Start – Aufmaß, Material, Angebot und Rechnung kommen danach im Projekt.</p></div></div>\n<form class="nx-form" method="post">{% csrf_token %}\n'
    new_head = '''<div class="nx-pagehead"><div><div class="nx-kicker">{% if source_appointment %}Termin vervollständigen{% else %}Auftrag starten{% endif %}</div><h1>{% if source_appointment %}Projekt für „{{ source_appointment.title }}“ anlegen{% else %}Projekt anlegen{% endif %}</h1><p>{% if source_appointment %}Kunde und Grunddaten auswählen. Nach dem Speichern wird der Termin automatisch mit dem neuen Projekt verbunden.{% else %}Kein Wizard. Kunde, Auftrag und Team reichen für den Start – Aufmaß, Material, Angebot und Rechnung kommen danach im Projekt.{% endif %}</p></div></div>\n{% if source_appointment %}<section class="nx-card nx-card-pad nx-link-context"><strong>Warum ist das nötig?</strong><p>Kundenfreigabe, Preise, Fotos, Zeiterfassung und Abschlussdokumentation gehören in KAYI zu einem Projekt. Du musst den Termin danach nicht noch einmal manuell verbinden.</p></section>{% endif %}\n<form class="nx-form" method="post">{% csrf_token %}{% if source_appointment %}<input type="hidden" name="_appointment" value="{{ source_appointment.pk }}">{% endif %}\n'''
    if old_head not in text:
        raise RuntimeError("Could not add appointment context to project form")
    text = text.replace(old_head, new_head, 1)
    old_actions = '  <div class="nx-form-actions"><a class="nx-btn" href="{% url \'next-projects\' %}">Abbrechen</a><button class="nx-btn nx-btn-accent" type="submit">Projekt anlegen →</button></div>\n'
    new_actions = '''  <div class="nx-form-actions"><a class="nx-btn" href="{% if source_appointment %}{% url 'next-appointment-detail' source_appointment.pk %}{% else %}{% url 'next-projects' %}{% endif %}">Abbrechen</a><button class="nx-btn nx-btn-accent" type="submit">{% if source_appointment %}Projekt anlegen & Termin verbinden →{% else %}Projekt anlegen →{% endif %}</button></div>\n'''
    if old_actions not in text:
        raise RuntimeError("Could not update project form actions for appointment handoff")
    path.write_text(text.replace(old_actions, new_actions, 1), encoding="utf-8")


def install_late_stylesheet() -> None:
    css_path = ROOT / "static" / "css" / "kayi-readability.css"
    css_path.parent.mkdir(parents=True, exist_ok=True)
    css_path.write_text(LATE_CSS.strip() + "\n", encoding="utf-8")

    base = ROOT / "templates" / "rebuild" / "base.html"
    text = base.read_text(encoding="utf-8")
    link = f'<link rel="stylesheet" href="{{% static \'css/kayi-readability.css\' %}}?v={VERSION}">'
    if "css/kayi-readability.css" not in text:
        marker = "</main>"
        index = text.find(marker)
        if index < 0:
            raise RuntimeError("Could not install late readability stylesheet in rebuild/base.html")
        index += len(marker)
        text = text[:index] + "\n    " + link + text[index:]
        base.write_text(text, encoding="utf-8")

    # Bust every CSS reference, not only kayi-next.css. Page overlays such as
    # field-authorization.css otherwise remain cached even after their readability rules change.
    pattern = re.compile(r"(\{%\s*static\s+['\"][^'\"]+\.css['\"]\s*%\}\?v=)([^'\"\s<]+)")
    for template in (ROOT / "templates").rglob("*.html"):
        source = template.read_text(encoding="utf-8")
        updated = pattern.sub(rf"\g<1>{VERSION}", source)
        if updated != source:
            template.write_text(updated, encoding="utf-8")


def patch_tests() -> None:
    path = ROOT / "tests" / "test_field_authorization.py"
    text = path.read_text(encoding="utf-8")
    marker = "test_project_missing_page_explains_recovery_and_can_attach_project"
    if marker in text:
        return
    block = '''\n\n    def test_project_missing_page_explains_recovery_and_can_attach_project(self):\n        internal = CalendarEvent.objects.create(\n            organization=self.org, project=None, title="Sercan", type="site",\n            starts_at="2026-08-11T09:30:00+00:00", ends_at="2026-08-11T10:30:00+00:00",\n            notes="Interner Termin", created_by=self.user,\n        )\n        internal.attendees.add(self.employee)\n        response = self.client.get(reverse("next-appointment-detail", args=[internal.pk]))\n        self.assertEqual(response.status_code, 200)\n        self.assertContains(response, "Vorhandenes Projekt zuordnen")\n        self.assertContains(response, "Neues Projekt anlegen")\n        self.assertContains(response, "Kundenfreigabe, Preise, Fotos, Zeiterfassung")\n        response = self.client.post(reverse("field-attach-project", args=[internal.pk]), {"project_id": self.project.pk})\n        self.assertEqual(response.status_code, 302)\n        internal.refresh_from_db()\n        self.assertEqual(internal.project_id, self.project.pk)\n\n    def test_project_created_from_missing_appointment_is_linked_back(self):\n        internal = CalendarEvent.objects.create(\n            organization=self.org, project=None, title="Sercan", type="site",\n            starts_at="2026-08-11T09:30:00+00:00", ends_at="2026-08-11T10:30:00+00:00",\n            notes="Interner Termin", created_by=self.user,\n        )\n        internal.attendees.add(self.employee)\n        response = self.client.post(\n            reverse("next-project-create") + f"?appointment={internal.pk}",\n            {\n                "_appointment": str(internal.pk),\n                "title": "Sercan Projekt",\n                "customer": str(self.customer.pk),\n                "object_location": "",\n                "description": "Aus Termin erstellt",\n                "priority": "normal",\n                "manager": str(self.employee.pk),\n                "members": [str(self.employee.pk)],\n            },\n        )\n        self.assertEqual(response.status_code, 302, response.content)\n        internal.refresh_from_db()\n        self.assertIsNotNone(internal.project_id)\n        self.assertIn(f"/appointments/{internal.pk}/", response["Location"])\n'''
    path.write_text(text.rstrip() + block + "\n", encoding="utf-8")


def guard() -> None:
    checks = {
        ROOT / "static" / "css" / "kayi-readability.css": [MARKER, ".fa-alert { font-size: 14px", ".fa-project-missing-card"],
        ROOT / "templates" / "rebuild" / "base.html": ["css/kayi-readability.css"],
        ROOT / "templates" / "rebuild" / "appointment_detail.html": ["Vorhandenes Projekt zuordnen", "field-attach-project", "Neues Projekt anlegen"],
        ROOT / "templates" / "rebuild" / "project_form.html": ["source_appointment", "Projekt anlegen & Termin verbinden"],
        ROOT / "erp" / "field_authorization_urls.py": ["field-attach-project"],
        ROOT / "erp" / "field_authorization_views.py": ["def attach_project", "available_projects"],
        ROOT / "erp" / "rebuild_views.py": ["source_appointment", "Termin automatisch zugeordnet"],
        ROOT / "tests" / "test_field_authorization.py": ["test_project_missing_page_explains_recovery_and_can_attach_project"],
    }
    for path, tokens in checks.items():
        if not path.exists():
            raise RuntimeError(f"Final readability/recovery file missing: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        missing = [token for token in tokens if token not in text]
        if missing:
            raise RuntimeError(f"Final readability/recovery verification failed for {path.relative_to(ROOT)}: {missing}")


def main() -> None:
    patch_field_urls()
    patch_field_views()
    patch_project_create()
    patch_appointment_template()
    patch_project_template()
    install_late_stylesheet()
    patch_tests()
    guard()
    print("KAYI final readability and missing-project recovery flow installed and verified.")


if __name__ == "__main__":
    main()
