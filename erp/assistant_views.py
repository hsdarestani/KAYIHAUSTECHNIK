# A+Bau AI scope authoritative catalog 2026-08-16
# A+Bau deterministic trade scope planner 2026-08-16
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
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import models as m
from .assistant_orchestrator import execute_workflow, looks_like_workflow, plan_workflow
from .rebuild_views import _org
from .services.ai import SYSTEM_PROMPT, _create_response
from .store_views import has_ai_consent
from .ai_scope_planner import plan_scope_message
from .ai_scope_catalog import enrich_scope_with_authoritative_catalog


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


_SEARCH_STOPWORDS = {
    "find", "search", "show", "open", "go", "to", "for", "the", "a", "an",
    "finde", "finden", "suche", "suchen", "zeig", "zeige", "öffne", "offne", "geh", "gehe", "nach",
    "mitarbeiter", "employee", "employees", "kunde", "kunden", "customer", "customers", "client", "clients",
    "projekt", "projekte", "project", "projects", "termin", "termine", "appointment", "appointments",
    "aufgabe", "aufgaben", "task", "tasks",
}


def _search_terms(message: str) -> list[str]:
    raw = re.findall(r"[\w@.+-]+", message or "", flags=re.UNICODE)
    terms = []
    for token in raw:
        normalized = token.casefold().strip("._-+")
        if len(normalized) < 2 or normalized in _SEARCH_STOPWORDS:
            continue
        terms.append(token[:80])
    return terms[:6]


def _and_text_query(terms: list[str], fields: tuple[str, ...]) -> Q:
    combined = Q()
    for term in terms:
        per_term = Q()
        for field in fields:
            per_term |= Q(**{f"{field}__icontains": term})
        combined &= per_term
    return combined


def _entity_search_context(organization, message: str) -> list[dict[str, Any]]:
    """Return only real records; the KI must never invent a search result."""
    terms = _search_terms(message)
    if not terms:
        return []
    matches: list[dict[str, Any]] = []

    employees = m.Employee.objects.filter(organization=organization).filter(
        _and_text_query(terms, ("first_name", "last_name", "email", "phone", "employee_number", "trade"))
    ).order_by("-active", "last_name", "first_name")[:8]
    for item in employees:
        matches.append({
            "route": "employees", "id": item.pk,
            "label": f"{item.first_name} {item.last_name}".strip() or item.employee_number,
            "detail": " · ".join(part for part in [item.employee_number, item.email, item.trade] if part),
        })

    customers = m.Customer.objects.filter(organization=organization).filter(
        _and_text_query(terms, ("company", "first_name", "last_name", "email", "phone", "mobile", "number"))
    ).order_by("-updated_at")[:8]
    for item in customers:
        matches.append({
            "route": "customers", "id": item.pk, "label": item.display_name,
            "detail": " · ".join(part for part in [item.number, item.email, item.city] if part),
        })

    projects = m.Project.objects.filter(organization=organization, archived=False).filter(
        _and_text_query(terms, ("number", "title", "description", "customer__company", "customer__first_name", "customer__last_name"))
    ).select_related("customer").order_by("-updated_at")[:8]
    for item in projects:
        matches.append({
            "route": "projects", "id": item.pk, "label": f"{item.number} · {item.title}",
            "detail": item.customer.display_name if item.customer_id else "",
        })

    appointments = m.CalendarEvent.objects.filter(organization=organization).filter(
        _and_text_query(terms, ("title", "location", "notes", "project__title", "project__number"))
    ).order_by("-starts_at")[:6]
    for item in appointments:
        matches.append({
            "route": "appointments", "id": item.pk, "label": item.title,
            "detail": timezone.localtime(item.starts_at).strftime("%d.%m.%Y %H:%M") if item.starts_at else "",
        })

    return matches[:20]


# A+Bau STATEFUL ENTITY CHAT 2026-08-11
_ENTITY_ROUTE_ALIASES = {
    "customers": {"kunde", "kunden", "customer", "customers", "client", "clients", "auftraggeber"},
    "projects": {"projekt", "projekte", "project", "projects", "auftrag", "aufträge", "auftrage"},
    "employees": {"mitarbeiter", "employee", "employees", "monteur", "monteure", "techniker", "technician"},
    "appointments": {"termin", "termine", "appointment", "appointments", "einsatz", "einsätze", "einsatze"},
}
_ENTITY_LOOKUP_VERBS = {
    "find", "search", "show", "open", "locate", "lookup",
    "finde", "finden", "suche", "suchen", "zeig", "zeige", "öffne", "offne", "such",
}
_ENTITY_OPEN_VERBS = {"open", "öffne", "offne", "go", "geh", "gehe", "navigate", "navigiere"}


def _assistant_tokens(message: str) -> list[str]:
    return [token.casefold().strip("._-+") for token in re.findall(r"[\w@.+-]+", message or "", flags=re.UNICODE) if token.strip("._-+")]


def _requested_entity_route(message: str) -> str:
    tokens = set(_assistant_tokens(message))
    for route, aliases in _ENTITY_ROUTE_ALIASES.items():
        if tokens.intersection(aliases):
            return route
    return ""


def _has_entity_lookup_verb(message: str) -> bool:
    return bool(set(_assistant_tokens(message)).intersection(_ENTITY_LOOKUP_VERBS))


def _has_entity_open_verb(message: str) -> bool:
    return bool(set(_assistant_tokens(message)).intersection(_ENTITY_OPEN_VERBS))


def _compact_assistant_history(payload: dict[str, Any]) -> list[dict[str, str]]:
    compact: list[dict[str, str]] = []
    for raw in (payload.get("history") or [])[-10:]:
        if not isinstance(raw, dict):
            continue
        role = str(raw.get("role") or "").strip().casefold()
        content = str(raw.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        compact.append({"role": role, "content": content[:900]})
    return compact


def _filter_entity_matches(matches: list[dict[str, Any]], route: str) -> list[dict[str, Any]]:
    if not route:
        return list(matches)
    return [item for item in matches if item.get("route") == route]


def _resolve_entity_search(request, organization, message: str) -> dict[str, Any]:
    """Resolve explicit searches and short follow-ups against real records only.

    The latest broad result set is stored in the Django session so a reply such as
    "client" can select the customer from the immediately preceding "find ashkan"
    request even after a page navigation/reload.
    """
    route = _requested_entity_route(message)
    terms = _search_terms(message)
    has_lookup = _has_entity_lookup_verb(message)
    previous = request.session.get("kayi_ai_entity_state") or {}
    previous_query = str(previous.get("query") or "").strip()
    previous_matches = previous.get("matches") if isinstance(previous.get("matches"), list) else []

    followup = bool(route and not terms and not has_lookup and previous_query)
    needs_query = bool(route and has_lookup and not terms)

    if terms:
        query = " ".join(terms)
        broad_matches = _entity_search_context(organization, query)
        request.session["kayi_ai_entity_state"] = {
            "query": query[:300],
            "matches": broad_matches[:20],
            "updated_at": timezone.now().isoformat(),
        }
        request.session.modified = True
    elif followup:
        query = previous_query
        broad_matches = previous_matches or _entity_search_context(organization, previous_query)
    else:
        query = ""
        broad_matches = [] if needs_query else _entity_search_context(organization, message)

    matches = _filter_entity_matches(broad_matches, route)
    return {
        "route": route,
        "query": query,
        "matches": matches[:20],
        "broad_matches": broad_matches[:20],
        "followup": followup,
        "needs_query": needs_query,
        "lookup": has_lookup,
        "open": _has_entity_open_verb(message),
    }


def _entity_route_label(route: str, count: int = 1) -> str:
    labels = {
        "customers": ("Kunde", "Kunden"),
        "projects": ("Projekt", "Projekte"),
        "employees": ("Mitarbeiter", "Mitarbeiter"),
        "appointments": ("Termin", "Termine"),
    }
    singular, plural = labels.get(route, ("Treffer", "Treffer"))
    return singular if count == 1 else plural


def _direct_entity_response(search: dict[str, Any]) -> dict[str, Any] | None:
    """Handle simple find/select flows deterministically instead of asking the LLM.

    This prevents contradictory replies such as finding a customer in one turn and
    claiming that same customer does not exist in the next turn.
    """
    route = str(search.get("route") or "")
    matches = list(search.get("matches") or [])
    broad_matches = list(search.get("broad_matches") or [])
    query = str(search.get("query") or "").strip()
    followup = bool(search.get("followup"))
    lookup = bool(search.get("lookup"))
    needs_query = bool(search.get("needs_query"))
    explicit_open = bool(search.get("open"))

    if not (lookup or followup):
        return None

    if needs_query:
        label = _entity_route_label(route, 1).lower()
        return {"ok": True, "reply": f"Welchen {label} soll ich suchen? Nenne mir bitte einen Namen, eine Nummer oder einen eindeutigen Suchbegriff.", "actions": [], "results": []}

    if not matches:
        if route:
            label = _entity_route_label(route, 1)
            suffix = f" zu „{query}“" if query else ""
            return {"ok": True, "reply": f"Ich habe keinen passenden {label}{suffix} gefunden.", "actions": [], "results": []}
        suffix = f" zu „{query}“" if query else ""
        return {"ok": True, "reply": f"Ich habe keine passenden Einträge{suffix} gefunden.", "actions": [], "results": []}

    # A short type-only follow-up ("client", "project") means the user selected
    # that category from the previous result. If it resolves to one record, open it.
    if (followup or explicit_open) and len(matches) == 1:
        match = matches[0]
        return {
            "ok": True,
            "reply": f"Ich öffne {match.get('label') or _entity_route_label(str(match.get('route') or ''), 1)}.",
            "actions": [{"type": "navigate_record", "target": str(match.get("route") or ""), "value": str(match.get("id") or ""), "count": 0}],
            "results": matches,
        }

    if len(matches) == 1:
        match = matches[0]
        return {
            "ok": True,
            "reply": f"Gefunden: {match.get('label')}. Du kannst den Eintrag direkt öffnen.",
            "actions": [],
            "results": matches,
        }

    if route:
        label = _entity_route_label(route, len(matches))
        return {
            "ok": True,
            "reply": f"Ich habe {len(matches)} passende {label} gefunden. Wähle den richtigen Eintrag aus.",
            "actions": [],
            "results": matches,
        }

    route_counts: dict[str, int] = {}
    for item in broad_matches:
        item_route = str(item.get("route") or "")
        route_counts[item_route] = route_counts.get(item_route, 0) + 1
    summary = ", ".join(f"{count} {_entity_route_label(item_route, count)}" for item_route, count in route_counts.items())
    return {
        "ok": True,
        "reply": f"Ich habe {len(matches)} echte Treffer zu „{query}“ gefunden" + (f": {summary}." if summary else ".") + " Wähle einen Eintrag oder sage z. B. „client“ bzw. „project“.",
        "actions": [],
        "results": matches,
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
        return JsonResponse({"ok": False, "error": "Bitte beschreibe kurz, was A+Bau KI erledigen soll."}, status=400)
    if len(message) > 5000:
        return JsonResponse({"ok": False, "error": "Die Anweisung ist zu lang. Bitte kürzer formulieren."}, status=400)

    if looks_like_workflow(message):
        return plan_workflow(request, payload, message)


    organization = _org(request)
    # A+Bau deterministic scope planning runs before generic LLM/entity handling.
    # It only activates for trade-work messages or an active scope follow-up.
    scope_plan = plan_scope_message(message, request.session, payload.get("catalog") or [])
    if scope_plan is not None:
        scope_plan = enrich_scope_with_authoritative_catalog(scope_plan, organization, request)
        return JsonResponse(scope_plan)
    context = _compact_ui_context(payload)
    context["now_local"] = timezone.localtime().isoformat(timespec="minutes")
    conversation_history = _compact_assistant_history(payload)
    entity_search = _resolve_entity_search(request, organization, message)
    context["conversation_history"] = conversation_history
    context["entity_matches"] = entity_search["matches"]
    context["entity_focus"] = {
        "route": entity_search["route"],
        "query": entity_search["query"],
        "followup": entity_search["followup"],
    }
    direct_entity = _direct_entity_response(entity_search)
    if direct_entity is not None:
        return JsonResponse(direct_entity)
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
                            "enum": ["set_field", "select_option", "catalog_add", "navigate", "navigate_record", "focus", "none"],
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
        "Du bist A+Bau KI, ein produktiver Assistent direkt in einer deutschen Handwerker-ERP-Oberfläche. "
        "Der Nutzer darf natürlich sprechen statt Suchbegriffe, Formulare und Dropdowns manuell zu bedienen. "
        "Arbeite ausschließlich mit den tatsächlich sichtbaren Feldern, Select-Optionen, Katalogpositionen und den erlaubten Routen aus dem UI-Kontext. "
        "Du darfst Entwürfe ausfüllen, Selects wählen, Katalogpositionen anklicken, den Fokus setzen und zu Listen navigieren. "
        "Du darfst NIEMALS Formulare absenden, Angebote/Rechnungen versenden, Zahlungen buchen, löschen oder sonstige irreversible Aktionen auslösen. "
        "Für set_field/select_option muss target exakt der Feldname aus dem Kontext sein. "
        "set_field darf auch Kontrollfelder bedienen: Checkboxen bekommen ausschließlich value=true oder value=false; "
        "date bekommt YYYY-MM-DD; datetime-local bekommt YYYY-MM-DDTHH:MM; time bekommt HH:MM; Zahlen bekommen eine Dezimalzahl mit Punkt. "
        "Relative Angaben wie heute, morgen oder nächsten Montag sind anhand von now_local in ein konkretes ISO-Datum umzuwandeln. "
        "Bei select_option ist value der sichtbare Optionstext oder ein eindeutiger Teil davon. "
        "Bei catalog_add ist value die gesuchte Leistung bzw. das Material und count die gewünschte Anzahl passender Positionen. "
        "Bei navigate ist target einer dieser Routenschlüssel: " + ", ".join(ROUTES) + ". value ist optional der Suchtext für q=. "
        "Bei navigate_record muss target dem route-Wert eines tatsächlich in entity_matches gelieferten Datensatzes entsprechen und value exakt dessen numerische id sein. "
        "Wenn der Nutzer einen konkreten Namen/Datensatz finden oder suchen will, verwende ausschließlich entity_matches: bei genau einem klaren Treffer navigate_record; "
        "bei mehreren plausiblen Treffern keine erfundene Auswahl; bei null Treffern action=none und klar sagen, dass nichts Passendes gefunden wurde. "
        "Niemals allein aufgrund eines Personennamens zu Mitarbeiter/Kunden navigieren, wenn entity_matches keinen solchen Treffer enthält. "
        "conversation_history enthält die letzten kurzen Chat-Turns. Nutze sie für Anschlusswörter wie dieser, der Kunde, client, project, dort, ihn oder das Projekt. "
        "Wenn entity_focus.followup=true ist, bezieht sich die aktuelle kurze Nachricht auf die unmittelbar vorherige Entitätssuche. "
        "Behaupte niemals, ein zuvor in entity_matches vorhandener Datensatz existiere nicht, sofern der neue Kontext ihn weiterhin enthält. "
        "Wenn etwas nicht sicher möglich ist, erkläre kurz warum und gib action=none zurück. Antworte auf Deutsch.\n\n"
        f"Nutzeranweisung:\n{message}\n\nUI-Kontext:\n{json.dumps(context, ensure_ascii=False)}"
    )
    try:
        response = _create_response(
            organization,
            input=[
                {"role": "developer", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
            ],
            text={"format": {"type": "json_schema", "name": "kayi_ui_assistant", "schema": schema, "strict": True}},
            store=False,
        )
        result = json.loads(response.output_text)
    except Exception:
        return JsonResponse({"ok": False, "error": "A+Bau KI ist momentan nicht erreichbar. Bitte erneut versuchen."}, status=502)
    return JsonResponse({"ok": True, "reply": str(result.get("reply") or ""), "actions": result.get("actions") or [], "results": []})


@login_required
@require_POST
def appointment_voice(request, pk):
    if not has_ai_consent(request.user):
        return _consent_error()
    org = _org(request)
    event = get_object_or_404(m.CalendarEvent, pk=pk, organization=org)
    transcript_only = str(request.POST.get("mode") or "").strip().lower() == "transcript_only"
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
    if transcript_only:
        return JsonResponse({"ok": True, "event_id": event.pk, "transcript": transcript})

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


@login_required
@require_POST
def field_voice_transcribe(request):
    """Transcribe a field recording without requiring an existing appointment.

    This endpoint is intentionally usable by Schnellauftrag before the job/event
    exists. The text is returned to the current form; nothing is saved here.
    """
    if not has_ai_consent(request.user):
        return _consent_error()
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
        if len(raw) < 32:
            return JsonResponse({"ok": False, "error": "Die Sprachaufnahme ist leer oder zu kurz."}, status=400)
        audio = io.BytesIO(raw)
        audio.name = getattr(upload, "name", "kayi-aufnahme.webm") or "kayi-aufnahme.webm"
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
    return JsonResponse({"ok": True, "transcript": transcript})


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
    pdf.drawString(42, height - 48, "A+Bau · Arbeitsnachweis")
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

# A_BAU_AI_ROLE_SCOPE_HARDENING 2026-08-12
from . import ai_role_permissions as _ai_perm

_ab_role_original_assistant_command = assistant_command
_ab_role_original_appointment_voice = appointment_voice


def _resolve_entity_search(request, organization, message: str) -> dict[str, Any]:
    """Role-scoped entity resolution; never trust matches stored under an older role."""
    route = _requested_entity_route(message)
    terms = _search_terms(message)
    has_lookup = _has_entity_lookup_verb(message)
    previous = request.session.get("kayi_ai_entity_state") or {}
    previous_query = str(previous.get("query") or "").strip()

    followup = bool(route and not terms and not has_lookup and previous_query)
    needs_query = bool(route and has_lookup and not terms)

    if terms:
        query = " ".join(terms)
        broad_matches = _ai_perm.entity_search_context(request.user, organization, query)
    elif followup:
        query = previous_query
        # Re-query under the CURRENT role. Stored result payloads are never reused,
        # which prevents a role downgrade from replaying old admin/office matches.
        broad_matches = _ai_perm.entity_search_context(request.user, organization, previous_query)
    else:
        query = ""
        broad_matches = [] if needs_query else _ai_perm.entity_search_context(request.user, organization, message)

    request.session["kayi_ai_entity_state"] = {
        "query": query[:300],
        "matches": broad_matches[:20],
        "role": _ai_perm.role_for(request.user),
        "updated_at": timezone.now().isoformat(),
    }
    request.session.modified = True

    matches = _filter_entity_matches(broad_matches, route)
    return {
        "route": route,
        "query": query,
        "matches": matches[:20],
        "broad_matches": broad_matches[:20],
        "followup": followup,
        "needs_query": needs_query,
        "lookup": has_lookup,
        "open": _has_entity_open_verb(message),
    }


@login_required
@require_POST
def assistant_command(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _ab_role_original_assistant_command(request)

    organization = _org(request)
    message = str(payload.get("message") or "").strip()

    if not _ai_perm.assistant_path_allowed(request.user, organization, str(payload.get("path") or "")):
        return JsonResponse(
            {"ok": False, "error": "A+Bau KI ist auf diesem Bereich für deine Rolle nicht freigeschaltet."},
            status=403,
        )

    # Hard stop before any model/database AI context is built. No LLM is called.
    if not _ai_perm.can_view_prices(request.user) and _ai_perm.is_price_request(message):
        return JsonResponse(
            {
                "ok": False,
                "error": "Auf Preisdaten, Einkauf, Verkauf, Margen und finanzielle Kennzahlen hast du mit deiner Rolle über A+Bau KI keinen Zugriff.",
                "permission_denied": True,
            },
            status=403,
        )

    safe_payload = _ai_perm.sanitize_assistant_payload(request.user, organization, payload)
    original_body = request.body
    request._body = json.dumps(safe_payload, ensure_ascii=False).encode("utf-8")
    try:
        response = _ab_role_original_assistant_command(request)
    finally:
        request._body = original_body

    if response.status_code >= 400:
        return response
    try:
        data = json.loads(response.content.decode("utf-8"))
    except Exception:
        return response

    data["actions"] = _ai_perm.filter_actions(
        request.user, organization, safe_payload, data.get("actions") or []
    )
    data["results"] = _ai_perm.filter_results(
        request.user, organization, data.get("results") or []
    )
    data["reply"] = _ai_perm.sanitize_reply(request.user, str(data.get("reply") or ""))
    return JsonResponse(data, status=response.status_code)


@login_required
@require_POST
def appointment_voice(request, pk):
    organization = _org(request)
    if not _ai_perm.can_use_field_ai(request.user):
        return JsonResponse({"ok": False, "error": "KI-Sprachauswertung ist für deine Rolle nicht freigeschaltet."}, status=403)
    if not _ai_perm.event_allowed(request.user, organization, pk):
        # Deliberately do not reveal whether an out-of-scope event exists.
        return JsonResponse({"ok": False, "error": "Einsatz nicht gefunden."}, status=404)
    return _ab_role_original_appointment_voice(request, pk)
