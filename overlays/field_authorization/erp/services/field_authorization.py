from __future__ import annotations

import base64
import hashlib
import html
import io
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

from django.core.files.base import ContentFile
from django.http import FileResponse
from django.utils import timezone

from erp import models as m

AUTH_KIND = "field_authorization"
COMPLETION_KIND = "field_completion"
AUTH_VERSION = 1
MONEY = Decimal("0.01")


def money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0").replace(",", ".")).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def client_ip(request) -> str:
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or request.META.get("REMOTE_ADDR") or ""


def latest_authorization(org, event):
    return (
        m.Document.objects.filter(
            organization=org,
            project=event.project,
            metadata__kind=AUTH_KIND,
            metadata__event_id=event.pk,
            metadata__status="signed",
        )
        .order_by("-created_at", "-pk")
        .first()
    )


def latest_completion(org, event):
    return (
        m.Document.objects.filter(
            organization=org,
            project=event.project,
            metadata__kind=COMPLETION_KIND,
            metadata__event_id=event.pk,
        )
        .order_by("-created_at", "-pk")
        .first()
    )


def event_documents(org, event, *, phase: str | None = None):
    qs = m.Document.objects.filter(organization=org, project=event.project, metadata__event_id=event.pk)
    if phase:
        qs = qs.filter(metadata__phase=phase)
    return qs.order_by("created_at", "pk")


def latest_room_revision(project):
    measurement = project.room_measurements.order_by("-updated_at", "-pk").first()
    if measurement is None:
        return None, None
    revision = measurement.model_revisions.order_by("-revision", "-pk").first()
    return measurement, revision


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def room_plan_svg(state: dict[str, Any] | None, *, title: str = "Raumplan") -> str:
    state = state or {}
    room = state.get("room") if isinstance(state.get("room"), dict) else {}
    width = max(0.5, _f(room.get("width_m"), 3.0))
    length = max(0.5, _f(room.get("length_m"), 4.0))
    height = max(0.5, _f(room.get("height_m"), 2.5))
    vw, vh, pad = 860, 620, 72
    scale = min((vw - pad * 2) / width, (vh - pad * 2 - 44) / length)
    ox = (vw - width * scale) / 2
    oy = 82 + (vh - 82 - length * scale) / 2

    def sx(x): return ox + _f(x) * scale
    def sz(z): return oy + _f(z) * scale
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" role="img" aria-label="{html.escape(title)}">',
        '<rect width="100%" height="100%" rx="22" fill="#f7f8f9"/>',
        f'<text x="32" y="38" font-family="Arial,sans-serif" font-size="19" font-weight="700" fill="#172128">{html.escape(title)}</text>',
        f'<text x="32" y="62" font-family="Arial,sans-serif" font-size="12" fill="#66727b">{length:.2f} × {width:.2f} × {height:.2f} m · Grundriss aus dem gespeicherten 3D-Modell</text>',
        f'<rect x="{ox:.1f}" y="{oy:.1f}" width="{width*scale:.1f}" height="{length*scale:.1f}" fill="#fff" stroke="#29363e" stroke-width="8"/>',
    ]
    for opening in state.get("openings") or []:
        wall = opening.get("wall") or "back"
        offset = _f(opening.get("offset_m"))
        ow = max(0.05, _f(opening.get("width_m"), 0.8))
        color = "#2b79a0" if opening.get("kind") == "window" else "#a66f3e"
        if wall in {"back", "front"}:
            x1, x2 = sx(offset), sx(offset + ow)
            y = oy if wall == "back" else oy + length * scale
            pieces.append(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" stroke="#fff" stroke-width="12"/>')
            pieces.append(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" stroke="{color}" stroke-width="5"/>')
        else:
            z1, z2 = sz(offset), sz(offset + ow)
            x = ox if wall == "left" else ox + width * scale
            pieces.append(f'<line x1="{x:.1f}" y1="{z1:.1f}" x2="{x:.1f}" y2="{z2:.1f}" stroke="#fff" stroke-width="12"/>')
            pieces.append(f'<line x1="{x:.1f}" y1="{z1:.1f}" x2="{x:.1f}" y2="{z2:.1f}" stroke="{color}" stroke-width="5"/>')
    for obj in state.get("objects") or []:
        if obj.get("enabled", True) is False:
            continue
        x = _f(obj.get("x_m"), width / 2)
        z = _f(obj.get("z_m"), length / 2)
        ow = max(0.08, _f(obj.get("width_m"), 0.5))
        od = max(0.08, _f(obj.get("depth_m"), 0.5))
        rx, ry = sx(x - ow / 2), sz(z - od / 2)
        rw, rh = ow * scale, od * scale
        label = html.escape(str(obj.get("label") or obj.get("kind") or "Objekt"))
        pieces.append(f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" rx="4" fill="#d9e7e8" stroke="#2b666b" stroke-width="2"/>')
        if rw > 54 and rh > 24:
            pieces.append(f'<text x="{rx+rw/2:.1f}" y="{ry+rh/2+4:.1f}" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" fill="#24474b">{label[:24]}</text>')
    pieces.append('</svg>')
    return "".join(pieces)


def parse_items(post) -> list[dict[str, Any]]:
    descriptions = post.getlist("item_description")
    quantities = post.getlist("item_quantity")
    units = post.getlist("item_unit")
    prices = post.getlist("item_price")
    taxes = post.getlist("item_tax")
    items: list[dict[str, Any]] = []
    for index, description in enumerate(descriptions):
        description = (description or "").strip()
        if not description:
            continue
        qty = max(Decimal("0"), money(quantities[index] if index < len(quantities) else "1"))
        price = max(Decimal("0"), money(prices[index] if index < len(prices) else "0"))
        tax = max(Decimal("0"), money(taxes[index] if index < len(taxes) else "19"))
        net = (qty * price).quantize(MONEY, rounding=ROUND_HALF_UP)
        tax_amount = (net * tax / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
        items.append({
            "position": len(items) + 1,
            "description": description[:500],
            "quantity": str(qty),
            "unit": ((units[index] if index < len(units) else "Stk.") or "Stk.")[:30],
            "unit_price": str(price),
            "tax_rate": str(tax),
            "net": str(net),
            "tax": str(tax_amount),
            "gross": str(net + tax_amount),
        })
    return items


def totals_for_items(items: Iterable[dict[str, Any]]) -> dict[str, str]:
    net = sum((money(item.get("net")) for item in items), Decimal("0"))
    tax = sum((money(item.get("tax")) for item in items), Decimal("0"))
    return {"net": str(net.quantize(MONEY)), "tax": str(tax.quantize(MONEY)), "gross": str((net + tax).quantize(MONEY))}


def decode_signature(data: str) -> bytes:
    prefix = "data:image/png;base64,"
    if not data.startswith(prefix):
        return b""
    try:
        raw = base64.b64decode(data[len(prefix):], validate=True)
    except Exception:
        return b""
    if len(raw) < 64 or len(raw) > 4 * 1024 * 1024:
        return b""
    return raw


def uploaded_images(files, *, max_files: int = 12, max_total: int = 50 * 1024 * 1024) -> list[dict[str, Any]]:
    result = []
    total = 0
    for upload in list(files)[:max_files]:
        mime = getattr(upload, "content_type", "") or ""
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        raw = upload.read()
        if hasattr(upload, "seek"):
            upload.seek(0)
        total += len(raw)
        if len(raw) > 12 * 1024 * 1024 or total > max_total:
            raise ValueError("Die ausgewählten Fotos sind zu groß.")
        result.append({"name": Path(getattr(upload, "name", "foto.jpg")).name[:180], "mime": mime, "bytes": raw, "sha256": sha256_bytes(raw)})
    return result


def _data_uri(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _address(project) -> str:
    loc = project.object_location
    if loc:
        return ", ".join(part for part in [loc.street, f"{loc.postal_code} {loc.city}".strip()] if part)
    customer = project.customer
    return ", ".join(part for part in [customer.street, f"{customer.postal_code} {customer.city}".strip()] if part)


def authorization_snapshot(*, request, event, issue: str, scope: str, pricing_mode: str, items: list[dict[str, Any]], price_cap_gross: Decimal | None, room_revision, before_photos: list[dict[str, Any]], signer_name: str) -> dict[str, Any]:
    totals = totals_for_items(items)
    project = event.project
    customer = project.customer
    return {
        "schema": "kayi.field_authorization.v1",
        "version": AUTH_VERSION,
        "event": {"id": event.pk, "title": event.title, "starts_at": event.starts_at.isoformat() if event.starts_at else None},
        "project": {"id": project.pk, "number": project.number, "title": project.title},
        "customer": {"id": customer.pk, "number": customer.number, "name": customer.display_name, "email": customer.email, "phone": customer.mobile or customer.phone},
        "site_address": _address(project),
        "issue": issue,
        "scope": scope,
        "pricing_mode": pricing_mode,
        "items": items,
        "totals": totals,
        "price_cap_gross": str(price_cap_gross.quantize(MONEY)) if price_cap_gross is not None else None,
        "room_revision": ({"id": room_revision.pk, "revision": room_revision.revision, "measurement_id": room_revision.measurement_id, "state_sha256": sha256_json(room_revision.state)} if room_revision else None),
        "before_photos": [{"name": item["name"], "sha256": item["sha256"]} for item in before_photos],
        "signer": {"name": signer_name, "signed_at": timezone.now().isoformat(), "ip": client_ip(request), "user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:500]},
        "technician": {"user_id": request.user.pk, "name": request.user.get_full_name() or request.user.get_username()},
        "consent_text": "Ich bestätige den beschriebenen Auftrag, die Preisgrundlage und die gezeigten Anlagen und beauftrage die Ausführung. Änderungen oder Zusatzarbeiten benötigen eine neue Freigabe, sofern sie nicht von dieser Preisgrundlage gedeckt sind.",
    }


def _price_label(snapshot: dict[str, Any]) -> str:
    mode = snapshot.get("pricing_mode")
    gross = money((snapshot.get("totals") or {}).get("gross"))
    cap = snapshot.get("price_cap_gross")
    if mode == "fixed":
        return f"Festpreis: {gross:.2f} € brutto"
    if mode == "estimate":
        return f"Kostenschätzung: {gross:.2f} € brutto" + (f" · Maximalfreigabe {money(cap):.2f} €" if cap else "")
    if mode == "hourly":
        return f"Abrechnung nach Aufwand · aktuelle Kalkulation {gross:.2f} € brutto" + (f" · Kostenlimit {money(cap):.2f} €" if cap else "")
    return f"Preisgrundlage: {gross:.2f} € brutto"


def _photo_html(photos: list[dict[str, Any]], heading: str) -> str:
    if not photos:
        return ""
    cards = []
    for item in photos[:8]:
        cards.append(f'<figure><img src="{_data_uri(item["bytes"], item["mime"])}"><figcaption>{html.escape(item["name"])}</figcaption></figure>')
    return f'<section><h2>{html.escape(heading)}</h2><div class="photos">{"".join(cards)}</div></section>'


def authorization_html(*, org, snapshot: dict[str, Any], signature: bytes, room_svg: str | None, before_photos: list[dict[str, Any]]) -> str:
    rows = "".join(
        f'<tr><td>{item["position"]}</td><td>{html.escape(item["description"])}</td><td>{item["quantity"]} {html.escape(item["unit"])}</td><td>{money(item["unit_price"]):.2f} €</td><td>{money(item["gross"]):.2f} €</td></tr>'
        for item in snapshot.get("items") or []
    )
    signature_uri = _data_uri(signature, "image/png") if signature else ""
    room = f'<section><h2>Raum / Aufmaß zum Zeitpunkt der Freigabe</h2>{room_svg}</section>' if room_svg else ""
    return _pdf_html_shell(org, "Auftragsfreigabe / Reparaturauftrag", f'''
      <div class="hero"><div><span class="eyebrow">KAYI Vor-Ort-Freigabe</span><h1>Auftragsfreigabe / Reparaturauftrag</h1><p>{html.escape(snapshot["project"]["number"])} · {html.escape(snapshot["event"]["title"])}</p></div><div class="price">{html.escape(_price_label(snapshot))}</div></div>
      <div class="facts"><div><small>Kunde</small><b>{html.escape(snapshot["customer"]["name"])}</b><span>{html.escape(snapshot["customer"].get("phone") or "")}</span></div><div><small>Einsatzort</small><b>{html.escape(snapshot.get("site_address") or "–")}</b></div><div><small>Freigabe</small><b>{html.escape(snapshot["signer"]["signed_at"][:19].replace("T", " "))}</b><span>Snapshot {html.escape(sha256_json(snapshot)[:12])}</span></div></div>
      <section><h2>Festgestellter Zustand / Kundenwunsch</h2><p class="long">{html.escape(snapshot.get("issue") or "–")}</p></section>
      <section><h2>Freigegebener Leistungsumfang</h2><p class="long">{html.escape(snapshot.get("scope") or "–")}</p></section>
      <section><h2>Preis & Positionen</h2><table><thead><tr><th>Pos.</th><th>Leistung / Material</th><th>Menge</th><th>Einzel</th><th>Brutto</th></tr></thead><tbody>{rows or '<tr><td colspan="5">Keine Einzelpositionen</td></tr>'}</tbody></table><div class="total">Netto {money(snapshot["totals"]["net"]):.2f} € · MwSt. {money(snapshot["totals"]["tax"]):.2f} € · <b>Brutto {money(snapshot["totals"]["gross"]):.2f} €</b></div></section>
      {room}
      {_photo_html(before_photos, "Fotodokumentation vor Arbeitsbeginn")}
      <section class="signature"><h2>Beauftragung & Unterschrift</h2><p>{html.escape(snapshot["consent_text"])}</p><div class="sign-row"><div><small>Kunde / Auftraggeber</small><b>{html.escape(snapshot["signer"]["name"])}</b>{f'<img src="{signature_uri}">' if signature_uri else ''}</div><div><small>Erfasst durch</small><b>{html.escape(snapshot["technician"]["name"])}</b><span>{html.escape(snapshot["signer"]["signed_at"][:19].replace("T", " "))}</span></div></div></section>
    ''')


def completion_html(*, org, authorization: dict[str, Any], report: str, services: str, material: str, completion_signature: bytes, room_svg_before: str | None, room_svg_after: str | None, before_photos: list[dict[str, Any]], after_photos: list[dict[str, Any]], completed_by: str, completed_at: str) -> str:
    signature_uri = _data_uri(completion_signature, "image/png") if completion_signature else ""
    plans = ""
    if room_svg_before or room_svg_after:
        plans = f'<section><h2>Raumdokumentation</h2><div class="plans">{room_svg_before or ""}{room_svg_after or ""}</div></section>'
    return _pdf_html_shell(org, "Einsatzabschluss / Vorher-Nachher-Dokumentation", f'''
      <div class="hero"><div><span class="eyebrow">KAYI Einsatzakte</span><h1>Einsatzabschluss</h1><p>{html.escape(authorization["project"]["number"])} · {html.escape(authorization["event"]["title"])}</p></div><div class="price">{html.escape(_price_label(authorization))}</div></div>
      <div class="facts"><div><small>Kunde</small><b>{html.escape(authorization["customer"]["name"])}</b></div><div><small>Einsatzort</small><b>{html.escape(authorization.get("site_address") or "–")}</b></div><div><small>Abschluss</small><b>{html.escape(completed_at[:19].replace("T", " "))}</b><span>{html.escape(completed_by)}</span></div></div>
      <section><h2>Ursprünglich freigegebener Umfang</h2><p class="long">{html.escape(authorization.get("scope") or "–")}</p></section>
      <section><h2>Arbeitsbericht</h2><p class="long">{html.escape(report or "–")}</p></section>
      <section class="two"><div><h2>Ausgeführte Leistungen</h2><p class="long">{html.escape(services or "–")}</p></div><div><h2>Verwendetes Material</h2><p class="long">{html.escape(material or "–")}</p></div></section>
      {plans}
      {_photo_html(before_photos, "Vorher")}
      {_photo_html(after_photos, "Nachher")}
      <section class="signature"><h2>Abschluss / Kenntnisnahme</h2><p>Der ausgeführte Stand und die Dokumentation wurden vor Ort angezeigt. Die ursprüngliche Auftragsfreigabe bleibt Bestandteil dieser Einsatzakte.</p><div class="sign-row"><div><small>Kunde / Auftraggeber</small>{f'<img src="{signature_uri}">' if signature_uri else '<b>Keine Abschlussunterschrift erfasst</b>'}</div><div><small>Techniker</small><b>{html.escape(completed_by)}</b><span>{html.escape(completed_at[:19].replace("T", " "))}</span></div></div></section>
    ''')


def _pdf_html_shell(org, title: str, body: str) -> str:
    org_name = html.escape(getattr(org, "legal_name", "") or getattr(org, "name", "KAYI"))
    org_email = html.escape(getattr(org, "email", "") or "")
    org_phone = html.escape(getattr(org, "phone", "") or "")
    return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>
      @page{{size:A4;margin:14mm 13mm 15mm}}*{{box-sizing:border-box}}body{{font-family:Arial,Helvetica,sans-serif;color:#182126;font-size:10.5px;line-height:1.45;margin:0}}.top{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #dfe5e7;padding-bottom:8px;margin-bottom:14px}}.brand{{font-weight:800;font-size:15px}}.muted{{color:#6a747b}}.hero{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;background:#f1f6f6;border-radius:14px;padding:16px;margin-bottom:12px}}.hero h1{{font-size:23px;line-height:1.1;margin:4px 0 5px}}.hero p{{margin:0;color:#657079}}.eyebrow{{font-size:8px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#24666b}}.price{{font-weight:800;color:#164f54;background:#fff;border:1px solid #cfe0e1;border-radius:10px;padding:9px 11px;max-width:210px;text-align:right}}.facts{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:10px 0 14px}}.facts>div{{border:1px solid #e2e7e9;border-radius:10px;padding:9px}}small{{display:block;color:#78838a;font-size:8px;margin-bottom:3px}}.facts b,.facts span{{display:block}}section{{break-inside:avoid;margin:0 0 13px}}h2{{font-size:12px;margin:0 0 6px}}p.long{{white-space:pre-wrap;background:#fafbfb;border:1px solid #e5e9ea;border-radius:9px;padding:9px;margin:0}}table{{border-collapse:collapse;width:100%;font-size:9px}}th,td{{border-bottom:1px solid #e4e7e8;text-align:left;padding:6px 5px}}th{{background:#f7f8f9;color:#66727a}}th:nth-child(n+3),td:nth-child(n+3){{text-align:right}}.total{{margin-top:8px;text-align:right;font-size:10px}}.photos{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}figure{{margin:0;border:1px solid #e1e5e6;border-radius:10px;overflow:hidden;background:#fafafa}}figure img{{width:100%;height:170px;object-fit:cover;display:block}}figcaption{{padding:5px 7px;color:#6d777e;font-size:8px}}svg{{width:100%;height:auto;max-height:390px}}.plans{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}.two{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}.signature{{border-top:1px solid #dfe4e6;padding-top:10px}}.sign-row{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:10px}}.sign-row>div{{min-height:95px;border:1px solid #dfe4e6;border-radius:10px;padding:9px}}.sign-row img{{display:block;max-width:210px;max-height:70px;margin-top:4px}}.foot{{border-top:1px solid #e3e7e8;margin-top:14px;padding-top:7px;color:#7d878d;font-size:8px;display:flex;justify-content:space-between}}</style></head><body><div class="top"><div class="brand">{org_name}</div><div class="muted">{org_email}{' · ' if org_email and org_phone else ''}{org_phone}</div></div>{body}<div class="foot"><span>Digital erzeugt durch KAYI · Dokumentationsstand {timezone.now():%d.%m.%Y %H:%M}</span><span>{org_name}</span></div></body></html>'''


def html_to_pdf_bytes(source_html: str) -> bytes:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.set_content(source_html, wait_until="load")
            pdf = page.pdf(format="A4", print_background=True, prefer_css_page_size=True)
            browser.close()
            if pdf.startswith(b"%PDF"):
                return pdf
    except Exception:
        pass
    return minimal_pdf_bytes(_strip_html(source_html))


def _strip_html(source: str) -> str:
    import re
    source = re.sub(r"<style.*?</style>", " ", source, flags=re.S | re.I)
    source = re.sub(r"<[^>]+>", "\n", source)
    return html.unescape(source)


def minimal_pdf_bytes(text: str) -> bytes:
    # Dependency-free fallback for exceptional environments where Chromium is unavailable.
    # Production uses Chromium/Playwright for the designed PDF above.
    lines = [line.strip() for line in text.splitlines() if line.strip()][:72]
    stream_lines = ["BT", "/F1 10 Tf", "44 800 Td", "12 TL"]
    first = True
    for line in lines:
        encoded = line.encode("latin-1", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:110]
        if not first:
            stream_lines.append("T*")
        stream_lines.append(f"({encoded}) Tj")
        first = False
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO(); out.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(out.tell()); out.write(f"{i} 0 obj\n".encode()); out.write(obj); out.write(b"\nendobj\n")
    xref = out.tell(); out.write(f"xref\n0 {len(objects)+1}\n".encode()); out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]: out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def save_binary_document(*, org, project, customer, user, title: str, category: str, filename: str, mime: str, raw: bytes, metadata: dict[str, Any]):
    document = m.Document(
        organization=org, customer=customer, project=project, title=title, category=category,
        mime_type=mime, size=len(raw), metadata=metadata, uploaded_by=user,
    )
    document.file.save(filename, ContentFile(raw), save=False)
    document.save()
    return document


def document_response(document):
    document.file.open("rb")
    return FileResponse(document.file, content_type=document.mime_type or "application/octet-stream", filename=Path(document.file.name).name)
