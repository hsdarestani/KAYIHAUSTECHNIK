from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "manager_review"
MARKER = "KAYI manager review 20260810"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing manager review target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        raise RuntimeError(f"Missing manager review overlay: {source}")
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        if item.is_dir():
            continue
        destination = target / item.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)


def patch_urls() -> None:
    path = "erp/rebuild_urls.py"
    text = read(path)
    import_line = "from . import manager_review_views as manager_review\n"
    if import_line not in text:
        anchor = "from . import rebuild_views as views\n"
        if anchor not in text:
            raise RuntimeError("Manager review URL import anchor changed")
        text = text.replace(anchor, anchor + import_line, 1)
    anchor = '    path("settings/next/", views.settings_page, name="next-settings"),\n'
    if anchor not in text:
        raise RuntimeError("Manager review route anchor changed")
    routes = [
        '    path("einsatzpruefung/", manager_review.review_queue, name="field-review-queue"),',
        '    path("einsatzpruefung/<int:pk>/", manager_review.review_detail, name="field-review-detail"),',
        '    path("einsatzpruefung/<int:pk>/freigeben/", manager_review.approve_completion, name="field-review-approve"),',
        '    path("einsatzpruefung/<int:pk>/aenderung/", manager_review.request_changes, name="field-review-changes"),',
    ]
    for route in routes:
        if route not in text:
            text = text.replace(anchor, route + "\n" + anchor, 1)
    write(path, text)


def patch_sidebar() -> None:
    path = "templates/rebuild/base.html"
    text = read(path)
    if "field-review-queue" not in text:
        anchor = '<a class="{% if \'invoice\' in request.resolver_match.url_name %}is-active{% endif %}" href="{% url \'next-invoices\' %}"><span class="nx-ico">€</span>Rechnungen</a>'
        if anchor not in text:
            raise RuntimeError("Manager review sidebar anchor changed")
        link = anchor + '\n      <a class="{% if \'field-review\' in request.resolver_match.url_name %}is-active{% endif %}" href="{% url \'field-review-queue\' %}"><span class="nx-ico">✓</span>Einsatzprüfung</a>'
        text = text.replace(anchor, link, 1)
    write(path, text)


def patch_completion_backend() -> None:
    path = "erp/field_authorization_views.py"
    text = read(path)
    complete_at = text.find("def complete_job(request, pk):")
    if complete_at < 0:
        raise RuntimeError("Manager review completion function missing")
    status_at = text.find('"status": "completed"', complete_at)
    if status_at >= 0:
        text = text[:status_at] + text[status_at:].replace('"status": "completed"', '"status": "pending_review", "billing_ready": False', 1)
    elif '"status": "pending_review"' not in text[complete_at:]:
        raise RuntimeError("Manager review completion status anchor changed")

    employee_anchor = "        employee = _employee(request, org)\n"
    employee_at = text.find(employee_anchor, complete_at)
    if "KAYI_MANAGER_REVIEW_PROJECT_STATE" not in text[complete_at:]:
        if employee_at < 0:
            raise RuntimeError("Manager review project-state anchor changed")
        project_state = '''        # KAYI_MANAGER_REVIEW_PROJECT_STATE\n        if event.project.status not in {"invoiced", "completed", "cancelled"}:\n            event.project.status = "review"\n            event.project.save(update_fields=["status", "updated_at"])\n'''
        text = text[:employee_at] + project_state + text[employee_at:]
    write(path, text)


def patch_field_home() -> None:
    path = "erp/rebuild_views.py"
    text = read(path)
    old = '''        m.Document.objects.filter(organization=org, category="report", metadata__event_id__isnull=False)\n        .values_list("metadata__event_id", flat=True)\n'''
    new = '''        m.Document.objects.filter(organization=org, category="report", metadata__kind="field_completion", metadata__event_id__isnull=False)\n        .exclude(metadata__status="changes_requested")\n        .values_list("metadata__event_id", flat=True)\n'''
    if new not in text:
        if old not in text:
            raise RuntimeError("Manager review field-home documented anchor changed")
        text = text.replace(old, new, 1)
    write(path, text)


def patch_appointment_template() -> None:
    path = "templates/rebuild/appointment_detail.html"
    text = read(path)
    old = '''    {% if completion %}\n      <div class="fa-complete-success"><span>✓</span><div><b>Einsatz dokumentiert</b><small>{{ completion.created_at|date:'d.m.Y H:i' }} · Abschluss-PDF und Anlagen sind archiviert.</small></div><a class="nx-btn nx-btn-primary" href="{% url 'field-completion-pdf' event.pk %}" target="_blank">Abschluss-PDF</a></div>\n    {% else %}\n'''
    new = '''    {% if completion and completion.metadata.status != 'changes_requested' %}\n      {% if completion.metadata.status == 'approved' %}<div class="nx-review-banner is-approved"><span>✓</span><div><b>Vom Büro freigegeben</b><p>Der Einsatz wurde geprüft und ist für die Rechnungsstellung bereit.</p></div></div>{% elif completion.metadata.status == 'pending_review' %}<div class="nx-review-banner"><span>◷</span><div><b>Wartet auf Bürofreigabe</b><p>Abschluss, Fotos, Leistungen, Material und PDF liegen in der Einsatzprüfung.</p></div></div>{% else %}<div class="nx-review-banner"><span>◷</span><div><b>Büroprüfung offen</b><p>Dieser ältere Abschluss kann in der Einsatzprüfung nachträglich freigegeben werden.</p></div></div>{% endif %}\n      <div class="fa-complete-success"><span>✓</span><div><b>Einsatz dokumentiert</b><small>{{ completion.created_at|date:'d.m.Y H:i' }} · Abschluss-PDF und Anlagen sind archiviert.</small></div><a class="nx-btn nx-btn-primary" href="{% url 'field-completion-pdf' event.pk %}" target="_blank">Abschluss-PDF</a></div>\n    {% else %}\n      {% if completion and completion.metadata.status == 'changes_requested' %}<div class="nx-review-banner is-change"><span>↺</span><div><b>Änderung angefordert</b><p>{{ completion.metadata.review_note|default:'Bitte den Einsatzabschluss korrigieren und erneut einreichen.' }}</p></div></div>{% endif %}\n'''
    if "Wartet auf Bürofreigabe" not in text:
        if old not in text:
            raise RuntimeError("Manager review appointment completion anchor changed")
        text = text.replace(old, new, 1)
    write(path, text)


def patch_css() -> None:
    path = "static/css/kayi-next.css"
    text = read(path)
    css = (OVERLAY / "static" / "css" / "manager-review.css").read_text(encoding="utf-8")
    if MARKER not in text:
        text = text.rstrip() + "\n\n" + css.strip() + "\n"
    write(path, text)


def guard() -> None:
    urls = read("erp/rebuild_urls.py")
    views = read("erp/field_authorization_views.py")
    home = read("erp/rebuild_views.py")
    base = read("templates/rebuild/base.html")
    appointment = read("templates/rebuild/appointment_detail.html")
    css = read("static/css/kayi-next.css")
    for needle in ("field-review-queue", "field-review-detail", "field-review-approve", "field-review-changes"):
        if needle not in urls:
            raise RuntimeError(f"Manager review route missing: {needle}")
    for needle in ('"status": "pending_review"', '"billing_ready": False', "KAYI_MANAGER_REVIEW_PROJECT_STATE"):
        if needle not in views:
            raise RuntimeError(f"Manager review completion contract missing: {needle}")
    if 'exclude(metadata__status="changes_requested")' not in home:
        raise RuntimeError("Changes-requested field jobs are still shown as documented")
    if "Einsatzprüfung" not in base or "field-review-queue" not in base:
        raise RuntimeError("Manager review navigation missing")
    for needle in ("Wartet auf Bürofreigabe", "Vom Büro freigegeben", "Änderung angefordert"):
        if needle not in appointment:
            raise RuntimeError(f"Manager review field feedback missing: {needle}")
    if MARKER not in css:
        raise RuntimeError("Manager review styles missing")
    if not (ROOT / "tests" / "test_manager_review.py").exists():
        raise RuntimeError("Manager review tests missing")
    if not (ROOT / "templates" / "rebuild" / "review_detail.html").exists():
        raise RuntimeError("Owner review detail template missing")


copy_tree(OVERLAY / "erp", ROOT / "erp")
copy_tree(OVERLAY / "templates", ROOT / "templates")
copy_tree(OVERLAY / "tests", ROOT / "tests")
patch_urls()
patch_sidebar()
patch_completion_backend()
patch_field_home()
patch_appointment_template()
patch_css()
guard()
print("A+Bau manager review installed: office can edit billing/report details and evidence before approval while signed originals stay immutable.")
