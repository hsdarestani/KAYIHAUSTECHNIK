from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "technician_project_approval"
MARKER = "A+BAU TECHNICIAN PROJECT APPROVAL 2026-08-12"


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
    target.mkdir(parents=True, exist_ok=True)
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
        text = text.rstrip() + "\n\n# A+Bau pre-project approval extension.\n" + line + "\n"
        write(rel, text)


def patch_routes() -> None:
    rel = "erp/field_authorization_urls.py"
    text = read(rel)
    import_line = "from . import project_intake_views as project_intake\n"
    if import_line not in text:
        anchor = "from . import field_authorization_views as views\n"
        if anchor not in text:
            raise RuntimeError("Field authorization URL import anchor changed")
        text = text.replace(anchor, anchor + import_line, 1)
    text = text.replace('path("field/jobs/new/", views.quick_job, name="field-quick-job")', 'path("field/jobs/new/", project_intake.technician_quick_job, name="field-quick-job")')
    routes = [
        '    path("field/project-intake/ai/", project_intake.intake_ai, name="field-project-intake-ai"),',
        '    path("field/project-intake/voice/", project_intake.intake_voice, name="field-project-intake-voice"),',
        '    path("field/projects/<int:pk>/freigabe/", project_intake.technician_project_approval, name="field-project-approval"),',
        '    path("projektfreigaben/", project_intake.approval_queue, name="project-approval-queue"),',
        '    path("projektfreigaben/<int:pk>/", project_intake.approval_review, name="project-approval-review"),',
    ]
    anchor = '    path("field/customers/search/", views.customer_search, name="field-customer-search"),\n'
    if anchor not in text:
        raise RuntimeError("Field authorization route insertion anchor changed")
    for route in reversed(routes):
        if route not in text:
            text = text.replace(anchor, route + "\n" + anchor, 1)
    write(rel, text)


def patch_field_event_handoff() -> None:
    rel = "erp/field_authorization_views.py"
    text = read(rel)
    if "A_BAU_PROJECT_APPROVAL_HANDOFF" not in text:
        anchor = '''    if event.project_id is None:\n        return render(request, "rebuild/appointment_detail.html", {"event": event, "project_missing": True})\n'''
        if anchor not in text:
            raise RuntimeError("Field project detail handoff anchor changed")
        block = anchor + '''    # A_BAU_PROJECT_APPROVAL_HANDOFF\n    from .project_intake_views import redirect_field_project_flow\n    project_approval_response = redirect_field_project_flow(request, event)\n    if project_approval_response is not None:\n        return project_approval_response\n'''
        text = text.replace(anchor, block, 1)
    write(rel, text)


def patch_project_create_guard() -> None:
    rel = "erp/rebuild_views.py"
    text = read(rel)
    marker = "A_BAU_TECHNICIAN_PROJECT_CREATE_GUARD"
    if marker not in text:
        anchor = '''def project_create(request):\n    org = _org(request)\n'''
        replacement = '''def project_create(request):\n    # A_BAU_TECHNICIAN_PROJECT_CREATE_GUARD\n    # Field users must use the price-free intake; owners/office keep the full project form.\n    if _is_field_user(request):\n        return redirect("field-quick-job")\n    org = _org(request)\n'''
        if anchor not in text:
            raise RuntimeError("Project create guard anchor changed")
        text = text.replace(anchor, replacement, 1)
    write(rel, text)


def patch_sidebar() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    if "project-approval-queue" not in text:
        # Manager-review runs earlier and guarantees this office-only navigation item.
        patterns = [
            r'(<a class="\{% if \'field-review\' in request\.resolver_match\.url_name %\}is-active\{% endif %\}" href="\{% url \'field-review-queue\' %\}"><span class="nx-ico">✓</span>Einsatzprüfung</a>)',
            r'(<a[^>]+href="\{% url \'field-review-queue\' %\}"[^>]*>.*?Einsatzprüfung</a>)',
        ]
        inserted = False
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.S)
            if match:
                link = match.group(1) + '\n      <a class="{% if \'project-approval\' in request.resolver_match.url_name %}is-active{% endif %}" href="{% url \'project-approval-queue\' %}"><span class="nx-ico">✓</span>Projektfreigaben</a>'
                text = text[:match.start(1)] + link + text[match.end(1):]
                inserted = True
                break
        if not inserted:
            anchor = '</nav>'
            if anchor not in text:
                raise RuntimeError("Sidebar navigation anchor changed")
            text = text.replace(anchor, '      <a href="{% url \'project-approval-queue\' %}"><span class="nx-ico">✓</span>Projektfreigaben</a>\n    ' + anchor, 1)
    write(rel, text)


def patch_field_home() -> None:
    rel = "templates/rebuild/field_home.html"
    text = read(rel)
    replacements = {
        "＋ Schnellauftrag": "＋ Projekt aufnehmen",
        "Ungeplanter Vor-Ort-Auftrag?": "Neues Projekt beim Kunden aufnehmen?",
        "Kunden auswählen oder neu anlegen → Voice → Preis → Unterschrift → Arbeit starten.": "Kunde → Voice/Text → Positionen & Fotos → ans Büro zur Preisfreigabe.",
        "Kunde → Auftrag & Preis → Unterschrift → Arbeit → Sprachnotiz → Kundenunterschrift → PDF.": "Kunde → technische Aufnahme → Bürofreigabe → Kundenunterschrift → Projektstart.",
        "Für spontane Arbeiten oben „Schnellauftrag“ nutzen.": "Für neue Vor-Ort-Projekte oben „Projekt aufnehmen“ nutzen.",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    write(rel, text)


def patch_browser_smoke() -> None:
    rel = "scripts/production_browser_smoke.py"
    text = read(rel)
    # The original field smoke expected the old direct-price Schnellauftrag. The
    # final product contract is now price-free intake -> office pricing -> customer sign.
    text = text.replace('if "Schnellauftrag" not in field_html:', 'if "Projekt aufnehmen" not in field_html:')
    text = text.replace('fail("technician field surface is missing Schnellauftrag")', 'fail("technician field surface is missing price-free project intake")')
    text = text.replace('for marker in ("Schnellauftrag", "Bestehender Kunde", "Neuer Kunde"):', 'for marker in ("Projekt aufnehmen", "Bestehender Kunde", "Neuer Kunde", "keine Preise"):' )
    text = text.replace('page.locator(\'button[type="submit"]:has-text("Auftrag anlegen")\').count() != 1', 'page.locator(\'button[type="submit"]:has-text("Zur Preisprüfung")\').count() != 1')
    text = text.replace('fail("quick-job flow is missing its visible submit action")', 'fail("project-intake flow is missing its office-review submit action")')
    if "project-intake flow" not in text:
        raise RuntimeError("Production browser smoke was not aligned to the new intake")
    write(rel, text)


def patch_cache_contract() -> None:
    rel = "templates/rebuild/base.html"
    text = read(rel)
    text = re.sub(r"(kayi-next\.css' %\}\?v=)[^\"']+", r"\g<1>20260812-project-approval-1", text)
    text = re.sub(r"(kayi-next\.js' %\}\?v=)[^\"']+", r"\g<1>20260812-project-approval-1", text)
    write(rel, text)


def guard() -> None:
    required = [
        "erp/project_approval.py", "erp/project_intake_views.py", "erp/migrations/0011_project_approval_flow.py",
        "templates/rebuild/field_quick_job.html", "templates/rebuild/project_approval_queue.html",
        "templates/rebuild/project_approval_review.html", "templates/rebuild/field_project_approval.html",
        "tests/test_technician_project_approval_flow.py",
    ]
    missing = [rel for rel in required if not (ROOT / rel).exists()]
    if missing:
        raise RuntimeError(f"Technician project approval installation incomplete: {missing}")
    models = read("erp/models.py")
    urls = read("erp/field_authorization_urls.py")
    field_views = read("erp/field_authorization_views.py")
    rebuild = read("erp/rebuild_views.py")
    intake = read("erp/project_intake_views.py")
    quick = read("templates/rebuild/field_quick_job.html")
    owner = read("templates/rebuild/project_approval_review.html")
    tech = read("templates/rebuild/field_project_approval.html")
    base = read("templates/rebuild/base.html")
    smoke = read("scripts/production_browser_smoke.py")
    if "ProjectApprovalFlow" not in models:
        raise RuntimeError("ProjectApprovalFlow model import missing")
    for needle in ("project_intake.technician_quick_job", "field-project-intake-ai", "field-project-intake-voice", "field-project-approval", "project-approval-queue", "project-approval-review"):
        if needle not in urls:
            raise RuntimeError(f"Project approval route missing: {needle}")
    if "A_BAU_PROJECT_APPROVAL_HANDOFF" not in field_views or "A_BAU_TECHNICIAN_PROJECT_CREATE_GUARD" not in rebuild:
        raise RuntimeError("Technician cannot be safely routed through the project approval flow")
    for needle in ("unit_price=Decimal(\"0\")", "approved=False", 'status="submitted"', 'status="review"', "search_bo_prices", "markup_percent", 'status = "confirmed"', 'status = "signed"', 'status = "in_progress"', "Notification.objects.create"):
        if needle not in intake:
            raise RuntimeError(f"Project approval backend contract missing: {needle}")
    for forbidden in ("Einkaufspreis", "Aufschlag (%)", "Marge"):
        if forbidden in quick:
            raise RuntimeError(f"Technician intake leaks financial field: {forbidden}")
    for needle in ("keine Preise", "data-intake-ai", "data-intake-record", "name=\"photos\"", "positions_json"):
        if needle not in quick:
            raise RuntimeError(f"Price-free technician intake missing: {needle}")
    for needle in ("Preisgrundlage", "EK manuell", "Aufschlag (%)", "VK / Einheit", "Umsatzsteuer", "Skonto", "Projekt & Verkaufspreise bestätigen"):
        if needle not in owner:
            raise RuntimeError(f"Owner ToolTime pricing UI missing: {needle}")
    for forbidden in ("Einkaufspreis", "Preisgrundlage", "Aufschlag (%)", "Marge"):
        if forbidden in tech:
            raise RuntimeError(f"Technician customer view leaks internal commercial data: {forbidden}")
    for needle in ("Finale Kundenpreise", "Gesamtpreis", "data-signature", "Unterschreiben & Projekt starten"):
        if needle not in tech:
            raise RuntimeError(f"Technician/customer approval view missing: {needle}")
    if "Projektfreigaben" not in base or "project-approval-queue" not in base:
        raise RuntimeError("Office project approval navigation missing")
    if "project-intake flow" not in smoke:
        raise RuntimeError("Production smoke still expects the obsolete priced Schnellauftrag")


copy_tree(OVERLAY / "erp", ROOT / "erp")
copy_tree(OVERLAY / "templates", ROOT / "templates")
copy_tree(OVERLAY / "tests", ROOT / "tests")
patch_models()
patch_routes()
patch_field_event_handoff()
patch_project_create_guard()
patch_sidebar()
patch_field_home()
patch_browser_smoke()
patch_cache_contract()
guard()
print("A+Bau technician project approval installed: price-free AI/voice/photo intake -> office EK/margin review -> final VK notification -> customer signature -> project start.")
