from __future__ import annotations

import html
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from . import models as m
from .manager_review_views import _authorization, _completion, _office_only, _review_state
from .rebuild_views import _org
from .services.field_authorization import _data_uri, _pdf_html_shell, html_to_pdf_bytes, money


MAX_PHOTOS_PER_PHASE = 12


def _photo_payload(document):
    mime = (document.mime_type or "").lower().strip()
    if mime not in {"image/jpeg", "image/png", "image/webp"} or not document.file:
        return None
    try:
        document.file.open("rb")
        raw = document.file.read()
        document.file.close()
    except Exception:
        return None
    if not raw:
        return None
    return {
        "name": Path(document.file.name).name,
        "title": document.title or Path(document.file.name).name,
        "mime": mime,
        "bytes": raw,
    }


def _phase_photos(org, completion, phase: str):
    event_id = (completion.metadata or {}).get("event_id")
    if not event_id or not completion.project_id:
        return []
    docs = (
        m.Document.objects.filter(
            organization=org,
            project=completion.project,
            category="photo",
            metadata__event_id=event_id,
            metadata__phase=phase,
        )
        .order_by("created_at", "pk")[:MAX_PHOTOS_PER_PHASE]
    )
    return [payload for payload in (_photo_payload(doc) for doc in docs) if payload]


def _photo_section(photos, heading: str, empty_text: str) -> str:
    if not photos:
        return f'<section><h2>{html.escape(heading)}</h2><p class="long muted">{html.escape(empty_text)}</p></section>'
    figures = []
    for index, item in enumerate(photos, 1):
        figures.append(
            '<figure>'
            f'<img src="{_data_uri(item["bytes"], item["mime"])}" alt="{html.escape(heading)} {index}">'
            f'<figcaption>{html.escape(heading)} {index} · {html.escape(item["title"])}</figcaption>'
            '</figure>'
        )
    return f'<section><h2>{html.escape(heading)} <span class="muted">({len(photos)})</span></h2><div class="photos">{"".join(figures)}</div></section>'


def _status_label(metadata: dict) -> str:
    status = str(metadata.get("status") or "pending_review")
    return {
        "approved": "Vom Büro freigegeben",
        "changes_requested": "Zur Ergänzung zurückgegeben",
        "pending_review": "Büroprüfung offen",
        "completed": "Büroprüfung offen",
    }.get(status, status)


def _review_pdf_html(*, org, completion, authorization, review, before_photos, after_photos) -> str:
    metadata = completion.metadata or {}
    auth = authorization.metadata.get("snapshot") if authorization and isinstance(authorization.metadata, dict) else {}
    project = completion.project
    customer = project.customer if project else None
    project_number = getattr(project, "number", "") or "–"
    project_title = getattr(project, "title", "") or "Einsatz"
    customer_name = getattr(customer, "display_name", "") or "–"
    event_id = metadata.get("event_id") or "–"
    reviewed_at = metadata.get("reviewed_at") or review.get("edited_at") or ""
    reviewed_by = metadata.get("reviewed_by") or review.get("edited_by") or "–"
    status = _status_label(metadata)

    rows = []
    for item in review.get("items") or []:
        rows.append(
            "<tr>"
            f'<td>{html.escape(str(item.get("position") or ""))}</td>'
            f'<td>{html.escape(str(item.get("description") or ""))}</td>'
            f'<td>{html.escape(str(item.get("quantity") or "0"))} {html.escape(str(item.get("unit") or ""))}</td>'
            f'<td>{money(item.get("unit_price")):.2f} €</td>'
            f'<td>{money(item.get("net")):.2f} €</td>'
            f'<td>{money(item.get("tax_rate")):.2f} %</td>'
            f'<td>{money(item.get("gross")):.2f} €</td>'
            "</tr>"
        )
    totals = review.get("totals") or {}
    item_table = "".join(rows) or '<tr><td colspan="7">Keine Abrechnungspositionen vorhanden.</td></tr>'

    original_refs = []
    if authorization:
        original_refs.append(f"Kundenfreigabe Dokument #{authorization.pk}")
    original_refs.append(f"Original Abschluss Dokument #{completion.pk}")

    body = f'''
      <div class="hero"><div><span class="eyebrow">A+Bau Büro · Einsatzprüfung</span><h1>Einsatzprüfungs- & Abrechnungsdokumentation</h1><p>{html.escape(project_number)} · {html.escape(project_title)}</p></div><div class="price">Brutto geprüft: {money(totals.get("gross")):.2f} €</div></div>
      <div class="facts"><div><small>Kunde</small><b>{html.escape(customer_name)}</b></div><div><small>Einsatz / Termin</small><b>#{html.escape(str(event_id))}</b><span>{html.escape(str((auth.get("event") or {}).get("title") or project_title))}</span></div><div><small>Prüfstatus</small><b>{html.escape(status)}</b><span>{html.escape(reviewed_by)}</span></div></div>
      <section><h2>Revisionssichere Originale</h2><p class="long">Die unterschriebene Kundenfreigabe und der ursprüngliche Monteur-Abschluss bleiben unverändert archiviert. Dieses PDF dokumentiert separat den aktuellen Büro-/Abrechnungsstand. Quellen: {html.escape(" · ".join(original_refs))}.</p></section>
      <section><h2>Abrechnungspositionen</h2><table><thead><tr><th>Pos.</th><th>Beschreibung</th><th>Menge</th><th>Verkauf</th><th>Netto</th><th>USt.</th><th>Brutto</th></tr></thead><tbody>{item_table}</tbody></table><div class="total"><b>Netto {money(totals.get("net")):.2f} € · USt. {money(totals.get("tax")):.2f} € · Brutto {money(totals.get("gross")):.2f} €</b></div></section>
      <section><h2>Arbeitsbericht</h2><p class="long">{html.escape(str(review.get("report") or "–"))}</p></section>
      <section class="two"><div><h2>Ausgeführte Leistungen</h2><p class="long">{html.escape(str(review.get("services") or "–"))}</p></div><div><h2>Material / Hinweise</h2><p class="long">{html.escape(str(review.get("material") or "–"))}</p></div></section>
      {_photo_section(before_photos, "Vorher-Fotos", "Keine Vorher-Fotos für diesen Einsatz gespeichert.")}
      {_photo_section(after_photos, "Nachher-Fotos", "Keine Nachher-Fotos für diesen Einsatz gespeichert.")}
      <section><h2>Büroprüfung</h2><p class="long">Status: {html.escape(status)}\nPrüfer: {html.escape(reviewed_by)}\nStand: {html.escape(str(reviewed_at)[:19].replace("T", " ") if reviewed_at else timezone.now().strftime("%d.%m.%Y %H:%M"))}\nInterne Prüfnotiz: {html.escape(str(review.get("note") or "–"))}</p></section>
    '''
    return _pdf_html_shell(org, "Einsatzprüfungs- & Abrechnungsdokumentation", body)


@login_required
@require_GET
def review_pdf(request, pk):
    denied = _office_only(request)
    if denied:
        return denied
    org = _org(request)
    completion = _completion(org, pk)
    authorization = _authorization(org, completion)
    review = _review_state(completion, authorization)
    before_photos = _phase_photos(org, completion, "before")
    after_photos = _phase_photos(org, completion, "after")
    source_html = _review_pdf_html(
        org=org,
        completion=completion,
        authorization=authorization,
        review=review,
        before_photos=before_photos,
        after_photos=after_photos,
    )
    pdf = html_to_pdf_bytes(source_html)
    project_number = getattr(completion.project, "number", "einsatz") or "einsatz"
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="einsatzpruefung-{project_number}-{completion.pk}.pdf"'
    response["X-Content-Type-Options"] = "nosniff"
    return response
