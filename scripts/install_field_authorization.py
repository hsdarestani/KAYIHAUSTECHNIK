from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "overlays" / "field_authorization"


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        raise RuntimeError(f"Missing Field Authorization overlay: {source}")
    target.mkdir(parents=True, exist_ok=True)
    for item in source.rglob("*"):
        if item.is_dir():
            continue
        relative = item.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)


def patch_latest_room_revision() -> None:
    path = ROOT / "erp" / "services" / "field_authorization.py"
    text = path.read_text(encoding="utf-8")
    old = '''def latest_room_revision(project):
    measurement = project.room_measurements.order_by("-updated_at", "-pk").first()
    if measurement is None:
        return None, None
    revision = measurement.model_revisions.order_by("-revision", "-pk").first()
    return measurement, revision
'''
    new = '''def latest_room_revision(project):
    measurement = m.RoomMeasurement.objects.filter(organization=project.organization, project=project).order_by("-updated_at", "-pk").first()
    if measurement is None:
        return None, None
    revision = measurement.model_revisions.order_by("-revision", "-pk").first()
    return measurement, revision
'''
    if new in text:
        return
    if old not in text:
        raise RuntimeError("Could not harden latest_room_revision lookup")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_compact_room_labels() -> None:
    path = ROOT / "erp" / "services" / "field_authorization.py"
    text = path.read_text(encoding="utf-8")
    old = '''        pieces.append(f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" rx="4" fill="#d9e7e8" stroke="#2b666b" stroke-width="2"/>')
        if rw > 54 and rh > 24:
            pieces.append(f'<text x="{rx+rw/2:.1f}" y="{ry+rh/2+4:.1f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" fill="#24474b">{label[:24]}</text>')
'''
    new = '''        pieces.append(f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" rx="4" fill="#d9e7e8" stroke="#2b666b" stroke-width="2"/>')
        if rw > 54 and rh > 24:
            pieces.append(f'<text x="{rx+rw/2:.1f}" y="{ry+rh/2+4:.1f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" fill="#24474b">{label[:24]}</text>')
        else:
            # Shallow technical objects (radiators, sockets, pipes) would otherwise
            # be geometrically visible but anonymous in the signed evidence PDF.
            label_x = min(max(rx + rw / 2, ox + 34), ox + width * scale - 34)
            label_y = max(oy + 13, ry - 6)
            pieces.append(f'<line x1="{rx+rw/2:.1f}" y1="{ry+rh/2:.1f}" x2="{label_x:.1f}" y2="{label_y+2:.1f}" stroke="#789095" stroke-width="1"/>')
            pieces.append(f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="9" font-weight="700" fill="#24474b">{label[:24]}</text>')
'''
    if new in text:
        return
    if old not in text:
        raise RuntimeError("Could not add compact Room Plan evidence labels")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_rebuild_urls() -> None:
    path = ROOT / "erp" / "rebuild_urls.py"
    text = path.read_text(encoding="utf-8")
    if "field_authorization_views as field_auth" not in text:
        anchor = "from . import rebuild_views as views\n"
        if anchor not in text:
            raise RuntimeError("Could not locate rebuild view import")
        text = text.replace(anchor, anchor + "from . import field_authorization_views as field_auth\n", 1)
    if "from django.urls import include, path" not in text:
        text = text.replace("from django.urls import path", "from django.urls import include, path", 1)
    if 'include("erp.field_authorization_urls")' not in text:
        marker = "urlpatterns = ["
        if marker not in text:
            raise RuntimeError("Could not locate rebuild urlpatterns")
        text = text.replace(marker, marker + '\n    # KAYI signed field order/freigabe routes.\n    path("", include("erp.field_authorization_urls")),', 1)
    text = text.replace('path("appointments/<int:pk>/", views.appointment_detail, name="next-appointment-detail")', 'path("appointments/<int:pk>/", field_auth.field_job_detail, name="next-appointment-detail")')
    text = text.replace('path("appointments/<int:event_pk>/time/", views.time_toggle, name="next-time-toggle")', 'path("appointments/<int:event_pk>/time/", field_auth.gated_time_toggle, name="next-time-toggle")')
    path.write_text(text, encoding="utf-8")


def patch_production_smoke() -> None:
    path = ROOT / "scripts" / "production_browser_smoke.py"
    text = path.read_text(encoding="utf-8")
    marker = "# KAYI signed field authorization browser smoke"
    if marker in text:
        return
    anchor = '''            if page.locator(".nx-field-bottom a").count() != 3:
                fail("technician mobile navigation must contain exactly Termine, Zeit and Konto")
'''
    if anchor not in text:
        raise RuntimeError("Could not locate technician browser smoke insertion point")
    block = anchor + '''
            # KAYI signed field authorization browser smoke: the spontaneous-job entry
            # and short intake must remain reachable inside technician mode.
            if "Schnellauftrag" not in field_html:
                fail("technician field surface is missing Schnellauftrag")
            quick = page.locator('a[href="/field/jobs/new/"]').first
            if quick.count() != 1:
                fail("technician field surface is missing quick-job link")
            quick.click()
            page.wait_for_load_state("domcontentloaded")
            quick_html = page.content()
            for marker in ("Schnellauftrag", "Bestehender Kunde", "Neuer Kunde", "Auftrag anlegen & Freigabe öffnen"):
                if marker not in quick_html:
                    fail(f"quick-job flow is missing {marker!r}")
'''
    path.write_text(text.replace(anchor, block, 1), encoding="utf-8")


def guard() -> None:
    required = [
        ROOT / "erp" / "field_authorization_urls.py",
        ROOT / "erp" / "field_authorization_views.py",
        ROOT / "erp" / "services" / "field_authorization.py",
        ROOT / "templates" / "rebuild" / "appointment_detail.html",
        ROOT / "templates" / "rebuild" / "field_quick_job.html",
        ROOT / "templates" / "rebuild" / "field_home.html",
        ROOT / "static" / "css" / "field-authorization.css",
        ROOT / "static" / "js" / "field-authorization.js",
        ROOT / "tests" / "test_field_authorization.py",
        ROOT / "tests" / "test_tooltime_rebuild.py",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Field Authorization installation incomplete: {missing}")
    urls = (ROOT / "erp" / "rebuild_urls.py").read_text(encoding="utf-8")
    for marker in ("field_authorization_views as field_auth", "field_auth.field_job_detail", "field_auth.gated_time_toggle", 'include("erp.field_authorization_urls")'):
        if marker not in urls:
            raise RuntimeError(f"Field Authorization URL contract missing: {marker}")
    service = (ROOT / "erp" / "services" / "field_authorization.py").read_text(encoding="utf-8")
    for marker in ("kayi.field_authorization.v1", "sha256_json", "html_to_pdf_bytes", "RoomMeasurement.objects.filter", "label_x"):
        if marker not in service:
            raise RuntimeError(f"Field Authorization service contract missing: {marker}")
    views = (ROOT / "erp" / "field_authorization_views.py").read_text(encoding="utf-8")
    for marker in ("snapshot_sha256", "requires_authorization", "field_completion"):
        if marker not in views:
            raise RuntimeError(f"Field Authorization persistence contract missing: {marker}")
    template = (ROOT / "templates" / "rebuild" / "appointment_detail.html").read_text(encoding="utf-8")
    for marker in ("Auftrag aufnehmen & freigeben", "Vorher-Fotos & Raum", "Kundenfreigabe", "Arbeit starten", "Abschluss & Vorher/Nachher"):
        if marker not in template:
            raise RuntimeError(f"Field Authorization UX contract missing: {marker}")
    smoke = (ROOT / "scripts" / "production_browser_smoke.py").read_text(encoding="utf-8")
    if "KAYI signed field authorization browser smoke" not in smoke:
        raise RuntimeError("Field Authorization production browser smoke missing")


copy_tree(OVERLAY / "erp", ROOT / "erp")
copy_tree(OVERLAY / "templates", ROOT / "templates")
copy_tree(OVERLAY / "static", ROOT / "static")
copy_tree(OVERLAY / "tests", ROOT / "tests")
patch_latest_room_revision()
patch_compact_room_labels()
patch_rebuild_urls()
patch_production_smoke()
guard()
print("KAYI signed field authorization, customer approval and before/after documentation installed and verified.")
