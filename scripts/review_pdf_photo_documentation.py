from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "overlays" / "manager_review" / "erp" / "manager_review_pdf.py"
TARGET = ROOT / "erp" / "manager_review_pdf.py"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Review PDF target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.write_text(text, encoding="utf-8")


def install_pdf_view() -> None:
    if not SOURCE.exists():
        raise RuntimeError("Manager review PDF overlay source missing")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, TARGET)


def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    import_line = "from . import manager_review_pdf as manager_review_pdf\n"
    if import_line not in text:
        anchor = "from . import manager_review_views as manager_review\n"
        if anchor not in text:
            raise RuntimeError("Manager review import anchor changed")
        text = text.replace(anchor, anchor + import_line, 1)
    route = '    path("einsatzpruefung/<int:pk>/pdf/", manager_review_pdf.review_pdf, name="field-review-pdf"),\n'
    if route not in text:
        anchor = '    path("einsatzpruefung/<int:pk>/", manager_review.review_detail, name="field-review-detail"),\n'
        if anchor not in text:
            raise RuntimeError("Manager review detail route anchor changed")
        text = text.replace(anchor, anchor + route, 1)
    write(rel, text)


def patch_review_template() -> None:
    rel = "templates/rebuild/review_detail.html"
    text = read(rel)
    if "field-review-pdf" not in text:
        anchor = '<div class="nx-review-doc-links"><a class="nx-btn" href="/appointments/{{ completion.metadata.event_id }}/completion/pdf/" target="_blank">Original Abschluss-PDF</a>'
        if anchor not in text:
            raise RuntimeError("Owner review document-links anchor changed")
        replacement = (
            '<div class="nx-review-doc-links">'
            '<a class="nx-btn nx-btn-primary" href="{% url \'field-review-pdf\' completion.pk %}" target="_blank">Prüf-PDF mit Vorher/Nachher</a>'
            '<a class="nx-btn" href="/appointments/{{ completion.metadata.event_id }}/completion/pdf/" target="_blank">Original Abschluss-PDF</a>'
        )
        text = text.replace(anchor, replacement, 1)
    write(rel, text)


def patch_completion_snapshot() -> None:
    rel = "erp/field_authorization_views.py"
    text = read(rel)
    complete_at = text.find("def complete_job(request, pk):")
    if complete_at < 0:
        raise RuntimeError("Completion function missing")
    tail = text[complete_at:]
    before_line = '        "before_photos": [{"name": item["name"], "sha256": item["sha256"]} for item in before_photos],\n'
    if before_line not in tail:
        after_line = '        "after_photos": [{"name": item["name"], "sha256": item["sha256"]} for item in after_photos],\n'
        if after_line not in tail:
            raise RuntimeError("Completion photo snapshot anchor changed")
        tail = tail.replace(after_line, before_line + after_line, 1)
        text = text[:complete_at] + tail
    write(rel, text)


def guard() -> None:
    urls = read("erp/rebuild_urls.py")
    template = read("templates/rebuild/review_detail.html")
    completion = read("erp/field_authorization_views.py")
    pdf_view = read("erp/manager_review_pdf.py")
    required_urls = ("manager_review_pdf", "field-review-pdf", "einsatzpruefung/<int:pk>/pdf/")
    for needle in required_urls:
        if needle not in urls:
            raise RuntimeError(f"Review PDF route missing: {needle}")
    if "Prüf-PDF mit Vorher/Nachher" not in template or "field-review-pdf" not in template:
        raise RuntimeError("Review PDF button missing from owner review")
    if '"before_photos": [{"name": item["name"], "sha256": item["sha256"]} for item in before_photos]' not in completion:
        raise RuntimeError("Completion snapshot does not retain before-photo evidence")
    for needle in ("before_photos=before_photos", "after_photos=after_photos"):
        if needle not in completion:
            raise RuntimeError(f"Original completion PDF photo contract missing: {needle}")
    for needle in ("Vorher-Fotos", "Nachher-Fotos", "html_to_pdf_bytes", "Revisionssichere Originale"):
        if needle not in pdf_view:
            raise RuntimeError(f"Office review PDF implementation incomplete: {needle}")


install_pdf_view()
patch_urls()
patch_review_template()
patch_completion_snapshot()
guard()
print("A+Bau review PDFs now include separate before/after photo documentation while signed originals remain immutable.")
