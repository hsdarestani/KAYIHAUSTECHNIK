from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "technician_project_approval"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Project approval target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        raise RuntimeError(f"Project approval overlay missing: {source}")
    for item in source.rglob("*"):
        if item.is_dir():
            continue
        dest = target / item.relative_to(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest)


def patch_models() -> None:
    rel = "erp/models.py"
    text = read(rel)
    line = "from .project_approval import ProjectApprovalFlow"
    if line not in text:
        write(rel, text.rstrip() + "\n\n# A+Bau pre-project approval extension.\n" + line + "\n")


def patch_routes() -> None:
    rel = "erp/field_authorization_urls.py"
    text = read(rel)
    import_line = "from . import project_intake_views as project_intake\n"
    if import_line not in text:
        anchor = "from . import field_authorization_views as views\n"
        if anchor not in text:
            raise RuntimeError("Field authorization URL import anchor changed")
        text = text.replace(anchor, anchor + import_line, 1)
    old = 'path("field/jobs/new/", views.quick_job, name="field-quick-job")'
    new = 'path("field/jobs/new/", project_intake.technician_quick_job, name="field-quick-job")'
    if new not in text:
        if old not in text:
            raise RuntimeError("Quick-job route anchor changed")
        text = text.replace(old, new, 1)
    anchor = '    path("field/customers/search/", views.customer_search, name="field-customer-search"),\n'
    if anchor not in text:
        raise RuntimeError("Field route insertion anchor changed")
    routes = (
        '    path("field/project-intake/ai/", project_intake.intake_ai, name="field-project-intake-ai"),',
        '    path("field/project-intake/voice/", project_intake.intake_voice, name="field-project-intake-voice"),',
        '    path("field/projects/<int:pk>/freigabe/", project_intake.technician_project_approval, name="field-project-approval"),',
        '    path("projektfreigaben/", project_intake.approval_queue, name="project-approval-queue"),',
        '    path("projektfreigaben/<int:pk>/", project_intake.approval_review, name="project-approval-review"),',
    )
    for route in reversed(routes):
        if route not in text:
            text = text.replace(anchor, route + "\n" + anchor, 1)
    write(rel, text)


def patch_field_handoff() -> None:
    rel = "erp/field_authorization_views.py"
    text = read(rel)
    if "A_BAU_PROJECT_APPROVAL_HANDOFF" in text:
        return
    anchor = '''    if event.project_id is None:\n        return render(request, "rebuild/appointment_detail.html", {"event": event, "project_missing": True})\n'''
    if anchor not in text:
        raise RuntimeError("Field detail handoff anchor changed")
    text = text.replace(anchor, anchor + '''    # A_BAU_PROJECT_APPROVAL_HANDOFF\n    from .project_intake_views import redirect_field_project_flow\n    approval_response = redirect_field_project_flow(request, event)\n    if approval_response is not None:\n        return approval_response\n''', 1)
    write(rel, text)


def patch_project_create() -> None:
    rel = "erp/rebuild_views.py"
    text = read(rel)
    if "A_BAU_TECHNICIAN_PROJECT_CREATE_GUARD" in text:
        return
    anchor = '''def project_create(request):\n    org = _org(request)\n'''
    if anchor not in text:
        raise RuntimeError("Project-create guard anchor changed")
    replacement = '''def project_create(request):\n    # A_BAU_TECHNICIAN_PROJECT_CREATE_GUARD\n    # Technicians cannot bypass the price-free field intake. Office/owner keeps full access.\n    if _is_field_user(request):\n        return redirect("field-quick-job")\n    org = _org(request)\n'''
    write(rel, text.replace(anchor, replacement, 1))


def patch_sidebar() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    if "project-approval-queue" in text:
        return
    anchor = '<a class="{% if \'field-review\' in request.resolver_match.url_name %}is-active{% endif %}" href="{% url \'field-review-queue\' %}"><span class="nx-ico">✓</span>Einsatzprüfung</a>'
    if anchor not in text:
        raise RuntimeError("Office Einsatzprüfung sidebar anchor changed")
    link = anchor + '\n      <a class="{% if \'project-approval\' in request.resolver_match.url_name %}is-active{% endif %}" href="{% url \'project-approval-queue\' %}"><span class="nx-ico">✓</span>Projektfreigaben</a>'
    write(rel, text.replace(anchor, link, 1))


def patch_field_home() -> None:
    rel = "templates/rebuild/field_home.html"
    text = read(rel)
    replacements = (
        ("＋ Schnellauftrag", "＋ Projekt aufnehmen"),
        ("Ungeplanter Vor-Ort-Auftrag?", "Neues Projekt beim Kunden aufnehmen?"),
        ("Kunden auswählen oder neu anlegen → Voice → Preis → Unterschrift → Arbeit starten.", "Kunde → Voice/Text → Positionen & Fotos → ans Büro zur Preisfreigabe."),
        ("Kunde → Auftrag & Preis → Unterschrift → Arbeit → Sprachnotiz → Kundenunterschrift → PDF.", "Kunde → technische Aufnahme → Bürofreigabe → Kundenunterschrift → Projektstart."),
        ("Für spontane Arbeiten oben „Schnellauftrag“ nutzen.", "Für neue Vor-Ort-Projekte oben „Projekt aufnehmen“ nutzen."),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    if "Projekt aufnehmen" not in text:
        raise RuntimeError("Field home was not converted to project intake")
    write(rel, text)


def patch_browser_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    text = text.replace('if "Schnellauftrag" not in field_html:', 'if "Projekt aufnehmen" not in field_html:')
    text = text.replace('fail("technician field surface is missing Schnellauftrag")', 'fail("technician field surface is missing price-free project intake")')
    text = text.replace('for marker in ("Schnellauftrag", "Bestehender Kunde", "Neuer Kunde"):', 'for marker in ("Projekt aufnehmen", "Bestehender Kunde", "Neuer Kunde", "keine Preise"):')
    text = text.replace('page.locator(\'button[type="submit"]:has-text("Auftrag anlegen")\').count() != 1', 'page.locator(\'button[type="submit"]:has-text("Zur Preisprüfung")\').count() != 1')
    text = text.replace('fail("quick-job flow is missing its visible submit action")', 'fail("project-intake flow is missing its office-review submit action")')
    if "project-intake flow" not in text:
        raise RuntimeError("Browser smoke still targets old priced quick job")
    write(rel, text)


def guard() -> None:
    required = (
        "erp/project_approval.py", "erp/project_intake_views.py", "erp/migrations/0011_project_approval_flow.py",
        "templates/rebuild/field_quick_job.html", "templates/rebuild/project_approval_queue.html",
        "templates/rebuild/project_approval_review.html", "templates/rebuild/field_project_approval.html",
        "tests/test_technician_project_approval_flow.py",
    )
    missing = [rel for rel in required if not (ROOT / rel).exists()]
    if missing:
        raise RuntimeError(f"Project approval files missing: {missing}")
    models = read("erp/models.py")
    urls = read("erp/field_authorization_urls.py")
    field_views = read("erp/field_authorization_views.py")
    rebuild = read("erp/rebuild_views.py")
    intake = read("erp/project_intake_views.py")
    quick = read("templates/rebuild/field_quick_job.html")
    owner = read("templates/rebuild/project_approval_review.html")
    tech = read("templates/rebuild/field_project_approval.html")
    base = read("templates/rebuild/base.html")
    if "ProjectApprovalFlow" not in models:
        raise RuntimeError("ProjectApprovalFlow import missing")
    for needle in ("project_intake.technician_quick_job", "field-project-intake-ai", "field-project-intake-voice", "field-project-approval", "project-approval-queue", "project-approval-review"):
        if needle not in urls:
            raise RuntimeError(f"Route missing: {needle}")
    if "A_BAU_PROJECT_APPROVAL_HANDOFF" not in field_views or "A_BAU_TECHNICIAN_PROJECT_CREATE_GUARD" not in rebuild:
        raise RuntimeError("Technician bypass protection missing")
    for needle in ('unit_price=Decimal("0")', "approved=False", 'status="submitted"', "search_bo_prices", "markup_percent", 'status = "confirmed"', 'status = "signed"', 'status = "in_progress"', "Notification.objects.create"):
        if needle not in intake:
            raise RuntimeError(f"Backend contract missing: {needle}")
    for forbidden in ('name="manual_ek_', 'data-price-source', 'data-markup', 'name="markup_', 'VK / Einheit'):
        if forbidden in quick:
            raise RuntimeError(f"Technician intake exposes financial control: {forbidden}")
    for needle in ("keine Preise", "data-intake-ai", "data-intake-record", 'name="photos"', "positions_json"):
        if needle not in quick:
            raise RuntimeError(f"Intake capability missing: {needle}")
    for needle in ("Preisgrundlage", "EK manuell", "Aufschlag (%)", "VK / Einheit", "Umsatzsteuer", "Skonto", "Projekt & Verkaufspreise bestätigen"):
        if needle not in owner:
            raise RuntimeError(f"Owner pricing UI missing: {needle}")
    for forbidden in ("data-price-source", "manual_ek_", "markup_", "commercial_meta", "purchase_price"):
        if forbidden in tech:
            raise RuntimeError(f"Technician/customer view leaks internal data: {forbidden}")
    for needle in ("Finale Kundenpreise", "Gesamtpreis", "data-signature", "Unterschreiben & Projekt starten"):
        if needle not in tech:
            raise RuntimeError(f"Customer approval UI missing: {needle}")
    if "Projektfreigaben" not in base:
        raise RuntimeError("Office approval navigation missing")


copy_tree(OVERLAY / "erp", ROOT / "erp")
copy_tree(OVERLAY / "templates", ROOT / "templates")
copy_tree(OVERLAY / "tests", ROOT / "tests")
patch_models()
patch_routes()
patch_field_handoff()
patch_project_create()
patch_sidebar()
patch_field_home()
patch_browser_smoke()
guard()
print("A+Bau technician project approval installed: price-free AI/voice/photo intake -> office EK/margin review -> final VK notification -> customer signature -> project start.")
