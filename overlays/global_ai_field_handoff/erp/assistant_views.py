from __future__ import annotations

import base64
import io
import json
import os
import re
import textwrap
from typing import Any

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import models as m
from .rebuild_views import _org
from .services.ai import SYSTEM_PROMPT, _create_response
from .store_views import has_ai_consent


ROUTES = {
    "dashboard": "/",
    "customers": "/customers/",
    "projects": "/projects/",
    "appointments": "/appointments/",
    "tasks": "/tasks/",
    "quotes": "/quotes/",
    "invoices": "/invoices/",
    "expenses": "/expenses/",
    "time": "/time/",
    "employees": "/employees/",
    "settings": "/settings/next/",
    "field": "/field/",
}


def _consent_error() -> JsonResponse:
    return JsonResponse(
        {
            "ok": False,
            "error": "Vor der KI-Verarbeitung ist deine ausdrückliche Einwilligung in den Einstellungen erforderlich.",
            "consent_required": True,
            "settings_url": "/settings/next/",
        },
        status=428,
    )


def _compact_ui_context(payload: dict[str, Any]) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    for raw in (payload.get("fields") or [])[:80]:
        if not isinstance(raw, dict):
            continue
        options = []
        for option in (raw.get("options") or [])[:100]:
            if isinstance(option, dict):
                options.append({
                    "value": str(option.get("value") or "")[:160],
                    "label": str(option.get("label") or "")[:240],
                })
        fields.append({
            "name": str(raw.get("name") or "")[:120],
            "label": str(raw.get("label") or "")[:220],
            "type": str(raw.get("type") or "")[:50],
            "value": str(raw.get("value") or "")[:800],
            "options": options,
        })
    catalog = []
    for raw in (payload.get("catalog") or [])[:160]:
        if not isinstance(raw, dict):
            continue
        catalog.append({
            "name": str(raw.get("name") or "")[:260],
            "code": str(raw.get("code") or "")[:100],
            "unit": str(raw.get("unit") or "")[:50],
            "price": str(raw.get("price") or "")[:80],
        })
    return {
        "path": str(payload.get("path") or "")[:500],
        "title": str(payload.get("title") or "")[:300],
        "fields": fields,
        "catalog": catalog,
        "routes": ROUTES,
    }


@login_required
@require_POST
def assistant_command(request):
    if not has_ai_consent(request.user):
        return _consent_error()
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Ungültige Anfrage."}, status=400)
    message = str(payload.get("message") or "").strip()
    if not message:
        return JsonResponse({"ok": False, "error": "Bitte beschreibe kurz, was KAYI KI erledigen soll."}, status=400)
    if len(message) > 5000:
        return JsonResponse({"ok": False, "error": "Die Anweisung ist zu lang. Bitte kürzer formulieren."}, status=400)

    context = _compact_ui_context(payload)
    schema = {
        "type": "object",
        "properties": {
            "reply": {"type": "string"},
            "actions": {
                "type": "array",
                "maxItems": 14,
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["set_field", "select_option", "catalog_add", "navigate", "focus", "none"],
                        },
                        "target": {"type": "string"},
                        "value": {"type": "string"},
                        "count": {"type": "integer", "minimum": 0, "maximum": 20},
                    },
                    "required": ["type", "target", "value", "count"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["reply", "actions"],
        "additionalProperties": False,
    }
    prompt = (
        "Du bist KAYI KI, ein produktiver Assistent direkt in einer deutschen Handwerker-ERP-Oberfläche. "
        "Der Nutzer darf natürlich sprechen statt Suchbegriffe, Formulare und Dropdowns manuell zu bedienen. "
        "Arbeite ausschließlich mit den tatsächlich sichtbaren Feldern, Select-Optionen, Katalogpositionen und den erlaubten Routen aus dem UI-Kontext. "
        "Du darfst Entwürfe ausfüllen, Selects wählen, Katalogpositionen anklicken, den Fokus setzen und zu Listen navigieren. "
        "Du darfst NIEMALS Formulare absenden, Angebote/Rechnungen versenden, Zahlungen buchen, löschen oder sonstige irreversible Aktionen auslösen. "
        "Für set_field/select_option muss target exakt der Feldname aus dem Kontext sein. "
        "Bei select_option ist value der sichtbare Optionstext oder ein eindeutiger Teil davon. "
        "Bei catalog_add ist value die gesuchte Leistung bzw. das Material und count die gewünschte Anzahl passender Positionen. "
        "Bei navigate ist target einer dieser Routenschlüssel: " + ", ".join(ROUTES) + ". value ist optional der Suchtext für q=. "
        "Wenn etwas nicht sicher möglich ist, erkläre kurz warum und gib action=none zurück. Antworte auf Deutsch.\n\n"
        f"Nutzeranweisung:\n{message}\n\nUI-Kontext:\n{json.dumps(context, ensure_ascii=False)}"
    )
    try:
        response = _create_response(
            _org(request),
            input=[
                {"role": "developer", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
            ],
            text={"format": {"type": "json_schema", "name": "kayi_ui_assistant", "schema": schema, "strict": True}},
            store=False,
        )
        result = json.loads(response.output_text)
    except Exception:
        return JsonResponse({"ok": False, "error": "KAYI KI ist momentan nicht erreichbar. Bitte erneut versuchen."}, status=502)
    return JsonResponse({"ok": True, "reply": str(result.get("reply") or ""), "actions": result.get("actions") or []})


@login_required
@require_POST
def appointment_voice(request, pk):
    if not has_ai_consent(request.user):
        return _consent_error()
    org = _org(request)
    event = get_object_or_404(m.CalendarEvent, pk=pk, organization=org)
    upload = request.FILES.get("voice")
    if upload is None:
        return JsonResponse({"ok": False, "error": "Keine Sprachaufnahme empfangen."}, status=400)
    if getattr(upload, "size", 0) > 20 * 1024 * 1024:
        return JsonResponse({"ok": False, "error": "Die Sprachaufnahme ist zu groß. Bitte kürzer aufnehmen."}, status=400)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return JsonResponse({"ok": False, "error": "Die KI-Sprachauswertung ist noch nicht konfiguriert."}, status=503)

    try:
        from openai import OpenAI

        raw = upload.read()
        audio = io.BytesIO(raw)
        audio.name = getattr(upload, "name", "einsatz.webm") or "einsatz.webm"
        client = OpenAI(api_key=api_key)
        transcription = client.audio.transcriptions.create(
            model=os.environ.get("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"),
            file=audio,
            language="de",
        )
        transcript = str(getattr(transcription, "text", "") or "").strip()
    except Exception:
        return JsonResponse({"ok": False, "error": "Die Sprachaufnahme konnte nicht transkribiert werden."}, status=502)
    if not transcript:
        return JsonResponse({"ok": False, "error": "In der Aufnahme wurde kein verständlicher Text erkannt."}, status=422)

    schema = {
        "type": "object",
        "properties": {
            "report": {"type": "string"},
            "services": {"type": "string"},
            "material": {"type": "string"},
        },
        "required": ["report", "services", "material"],
        "additionalProperties": False,
    }
    try:
        response = _create_response(
            org,
            input=[
                {"role": "developer", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [{"type": "input_text", "text": (
                    "Strukturiere diese Vor-Ort-Sprachnotiz für einen Arbeitsbericht. "
                    "Trenne nur tatsächlich erwähnte ausgeführte Arbeiten und Materialien; nichts erfinden.\n\n" + transcript
                )}]},
            ],
            text={"format": {"type": "json_schema", "name": "field_voice_report", "schema": schema, "strict": True}},
            store=False,
        )
        structured = json.loads(response.output_text)
    except Exception:
        structured = {"report": transcript, "services": "", "material": ""}
    return JsonResponse({
        "ok": True,
        "event_id": event.pk,
        "transcript": transcript,
        "report": str(structured.get("report") or transcript),
        "services": str(structured.get("services") or ""),
        "material": str(structured.get("material") or ""),
    })


def _draw_wrapped(pdf, text: str, x: float, y: float, width_chars: int = 92, leading: float = 13) -> float:
    for paragraph in (text or "-").splitlines() or ["-"]:
        lines = textwrap.wrap(paragraph, width=width_chars, replace_whitespace=False, drop_whitespace=True) or [""]
        for line in lines:
            if y < 70:
                pdf.showPage()
                pdf.setFont("Helvetica", 9.5)
                y = 790
            pdf.drawString(x, y, line[:140])
            y -= leading
        y -= 3
    return y


def build_field_report_pdf(*, organization, event, user, report_text: str, services: str, material: str,
                           customer_name: str, voice_transcript: str, signature_data: str,
                           photo_names: list[str]) -> m.Document:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    project = event.project
    customer = project.customer

    pdf.setTitle(f"Arbeitsnachweis {project.number} {event.title}")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(42, height - 48, "KAYI · Arbeitsnachweis")
    pdf.setFont("Helvetica", 9.5)
    y = height - 78
    rows = [
        ("Projekt", f"{project.number} · {project.title}"),
        ("Kunde", customer.display_name),
        ("Termin", event.title),
        ("Datum", timezone.localtime(event.starts_at).strftime("%d.%m.%Y %H:%M") if event.starts_at else timezone.localdate().strftime("%d.%m.%Y")),
        ("Einsatzort", event.location or (f"{getattr(project.object_location, 'street', '')}, {getattr(project.object_location, 'postal_code', '')} {getattr(project.object_location, 'city', '')}" if project.object_location_id else f"{customer.street}, {customer.postal_code} {customer.city}")),
    ]
    for label, value in rows:
        pdf.setFont("Helvetica-Bold", 9.5)
        pdf.drawString(42, y, f"{label}:")
        pdf.setFont("Helvetica", 9.5)
        pdf.drawString(120, y, str(value or "-")[:105])
        y -= 15

    sections = [
        ("Arbeitsbericht", report_text),
        ("Ausgeführte Leistungen", services),
        ("Verwendetes Material", material),
    ]
    if voice_transcript and voice_transcript.strip() and voice_transcript.strip() != (report_text or "").strip():
        sections.append(("Transkript der Vor-Ort-Sprachnotiz", voice_transcript))
    if photo_names:
        sections.append(("Fotodokumentation", "\n".join(f"• {name}" for name in photo_names)))

    for title, value in sections:
        y -= 8
        if y < 95:
            pdf.showPage(); y = height - 48
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(42, y, title)
        y -= 17
        pdf.setFont("Helvetica", 9.5)
        y = _draw_wrapped(pdf, value or "-", 42, y)

    y -= 8
    if y < 190:
        pdf.showPage(); y = height - 48
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(42, y, "Bestätigung vor Ort")
    y -= 18
    pdf.setFont("Helvetica", 9.5)
    pdf.drawString(42, y, f"Geprüft und unterschrieben von: {customer_name or customer.display_name}")
    y -= 18
    if signature_data.startswith("data:image/png;base64,"):
        try:
            signature_raw = base64.b64decode(signature_data.split(",", 1)[1])
            image = ImageReader(io.BytesIO(signature_raw))
            pdf.drawImage(image, 42, y - 90, width=220, height=85, preserveAspectRatio=True, mask="auto")
            y -= 100
        except Exception:
            pdf.drawString(42, y, "Unterschrift konnte nicht in das PDF eingebettet werden.")
            y -= 18
    pdf.setFont("Helvetica", 8)
    pdf.drawString(42, 38, f"Erstellt mit KAYI am {timezone.localtime():%d.%m.%Y %H:%M} · Dokumentation bleibt im Projekt gespeichert.")
    pdf.save()
    raw_pdf = buffer.getvalue()

    document = m.Document(
        organization=organization,
        customer=customer,
        project=project,
        title=f"Arbeitsnachweis PDF · {event.title} · {timezone.localdate():%d.%m.%Y}",
        category="report",
        mime_type="application/pdf",
        size=len(raw_pdf),
        metadata={
            "event_id": event.pk,
            "kind": "field_handoff_pdf",
            "signed_by": customer_name or customer.display_name,
            "generated_at": timezone.now().isoformat(),
            "source": "kayi-next-field",
        },
        uploaded_by=user,
    )
    document.file.save(f"arbeitsnachweis-{event.pk}-{timezone.now():%Y%m%d%H%M%S}.pdf", ContentFile(raw_pdf), save=False)
    document.save()
    return document


@login_required
@require_POST
def account_logout(request):
    logout(request)
    return redirect("/login/")
