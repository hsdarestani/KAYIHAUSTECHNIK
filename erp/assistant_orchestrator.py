from __future__ import annotations

import json
import re
import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import models as m
from .rebuild_views import _is_field_user, _org, _unique_number
from .services.ai import SYSTEM_PROMPT, _create_response
from .store_views import has_ai_consent

PLAN_SALT = "ab-bau-agent-plan-v1"
PLAN_MAX_AGE_SECONDS = 15 * 60
PENDING_SESSION_KEY = "ab_bau_agent_pending_v1"
ALLOWED_STEP_TYPES = {"create_customer", "create_project", "create_quote", "create_invoice"}

_WORKFLOW_VERBS = {
    "erstell", "erstelle", "erstellen", "anleg", "anlegen", "lege", "mach", "mache", "create", "make", "build",
    "بساز", "ساختن", "ایجاد", "درست", "صدور", "صادر",
}
_WORKFLOW_ENTITIES = {
    "kunde", "kunden", "customer", "client", "مشتری",
    "projekt", "project", "پروژه",
    "angebot", "quote", "kostenvoranschlag", "پیشنهاد",
    "rechnung", "invoice", "فاکتور", "صورتحساب",
}


class AgentPlanError(ValueError):
    pass


def _words(value: str) -> set[str]:
    return {part.casefold() for part in re.findall(r"[\w+äöüßآ-ی]+", value or "", flags=re.UNICODE) if part}


def looks_like_workflow(message: str) -> bool:
    words = _words(message)
    entities = words.intersection(_WORKFLOW_ENTITIES)
    has_verb = bool(words.intersection(_WORKFLOW_VERBS)) or any(token.startswith(("erstell", "anleg")) for token in words)
    return bool((has_verb and entities) or len(entities) >= 2)


def _decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value not in (None, "") else default).replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _clamp_decimal(value: Any, low: Decimal, high: Decimal) -> Decimal:
    return min(high, max(low, _decimal(value)))


def _business_context(org) -> dict[str, Any]:
    customers = []
    for customer in m.Customer.objects.filter(organization=org, active=True).order_by("-updated_at")[:60]:
        customers.append({
            "id": customer.pk,
            "number": customer.number,
            "name": customer.display_name,
            "company": customer.company,
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "email": customer.email,
            "city": customer.city,
        })
    projects = []
    for project in m.Project.objects.filter(organization=org, archived=False).select_related("customer").order_by("-updated_at")[:60]:
        projects.append({
            "id": project.pk,
            "number": project.number,
            "title": project.title,
            "status": project.status,
            "customer_id": project.customer_id,
            "customer": project.customer.display_name,
        })
    return {"customers": customers, "projects": projects, "today": timezone.localdate().isoformat()}


def _item_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "description": {"type": "string"},
            "quantity": {"type": "number", "minimum": 0, "maximum": 1000000},
            "unit": {"type": "string"},
            "purchase_price": {"type": "number", "minimum": 0, "maximum": 100000000},
            "unit_price": {"type": "number", "minimum": 0, "maximum": 100000000},
            "markup_percent": {"type": "number", "minimum": -100, "maximum": 10000},
            "position_type": {"type": "string", "enum": ["material", "labour", "mixed", "other"]},
            "service_model": {"type": "string", "enum": ["normal", "alternative", "contingent"]},
        },
        "required": ["description", "quantity", "unit", "purchase_price", "unit_price", "markup_percent", "position_type", "service_model"],
        "additionalProperties": False,
    }


def _plan_schema() -> dict[str, Any]:
    step_properties = {
        "id": {"type": "string"},
        "type": {"type": "string", "enum": sorted(ALLOWED_STEP_TYPES)},
        "parent_ref": {"type": "string"},
        "parent_id": {"type": "integer", "minimum": 0},
        "source_ref": {"type": "string"},
        "source_id": {"type": "integer", "minimum": 0},
        "customer_type": {"type": "string", "enum": ["private", "business", "insurance", "property_manager"]},
        "company": {"type": "string"},
        "salutation": {"type": "string"},
        "first_name": {"type": "string"},
        "last_name": {"type": "string"},
        "email": {"type": "string"},
        "phone": {"type": "string"},
        "mobile": {"type": "string"},
        "street": {"type": "string"},
        "postal_code": {"type": "string"},
        "city": {"type": "string"},
        "country": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
        "status": {"type": "string", "enum": ["draft", "sent"]},
        "intro_text": {"type": "string"},
        "notes": {"type": "string"},
        "valid_days": {"type": "integer", "minimum": 0, "maximum": 365},
        "due_days": {"type": "integer", "minimum": 0, "maximum": 365},
        "tax_code": {"type": "string", "enum": ["19", "7", "0_19", "0_13b", "0_4", "0"]},
        "discount_type": {"type": "string", "enum": ["percent", "fixed"]},
        "discount_value": {"type": "number", "minimum": 0, "maximum": 100000000},
        "items": {"type": "array", "maxItems": 40, "items": _item_schema()},
    }
    return {
        "type": "object",
        "properties": {
            "reply": {"type": "string"},
            "needs_clarification": {"type": "boolean"},
            "clarification": {"type": "string"},
            "workflow": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "confirmation_text": {"type": "string"},
                    "steps": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 8,
                        "items": {
                            "type": "object",
                            "properties": step_properties,
                            "required": list(step_properties),
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["title", "confirmation_text", "steps"],
                "additionalProperties": False,
            },
        },
        "required": ["reply", "needs_clarification", "clarification", "workflow"],
        "additionalProperties": False,
    }


def _validate_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    steps = workflow.get("steps") if isinstance(workflow, dict) else None
    if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
        raise AgentPlanError("Der Ablauf enthält keine gültigen Schritte.")
    seen: set[str] = set()
    clean_steps = []
    for raw in steps:
        if not isinstance(raw, dict):
            raise AgentPlanError("Ein KI-Schritt ist ungültig.")
        step = dict(raw)
        step_id = str(step.get("id") or "").strip()[:50]
        kind = str(step.get("type") or "").strip()
        if not step_id or step_id in seen or kind not in ALLOWED_STEP_TYPES:
            raise AgentPlanError("Der KI-Ablauf enthält einen ungültigen oder doppelten Schritt.")
        seen.add(step_id)
        step["id"] = step_id
        step["type"] = kind
        step["parent_ref"] = str(step.get("parent_ref") or "").strip()[:50]
        step["source_ref"] = str(step.get("source_ref") or "").strip()[:50]
        step["parent_id"] = int(step.get("parent_id") or 0)
        step["source_id"] = int(step.get("source_id") or 0)
        if step["parent_ref"] and step["parent_ref"] not in seen:
            raise AgentPlanError(f"Schritt {step_id} verweist auf einen noch nicht vorhandenen Vorgänger.")
        if step["source_ref"] and step["source_ref"] not in seen:
            raise AgentPlanError(f"Schritt {step_id} verweist auf eine noch nicht vorhandene Quelle.")
        clean_steps.append(step)
    return {
        "title": str(workflow.get("title") or "A+Bau KI-Ablauf").strip()[:180],
        "confirmation_text": str(workflow.get("confirmation_text") or "Diese Schritte jetzt ausführen?").strip()[:600],
        "steps": clean_steps,
    }


def _step_summary(step: dict[str, Any]) -> str:
    kind = step["type"]
    if kind == "create_customer":
        name = str(step.get("company") or "").strip() or " ".join(filter(None, [step.get("first_name"), step.get("last_name")])).strip() or "Neuer Kunde"
        return f"Kunde anlegen: {name}"
    if kind == "create_project":
        return f"Projekt anlegen: {str(step.get('title') or 'Neues Projekt').strip()}"
    if kind == "create_quote":
        mode = "erstellen und als gesendet markieren" if step.get("status") == "sent" else "als Entwurf erstellen"
        count = len(step.get("items") or [])
        return f"Angebot {mode}" + (f" · {count} Position(en)" if count else "")
    mode = "ausstellen / als gesendet markieren" if step.get("status") == "sent" else "als Entwurf erstellen"
    count = len(step.get("items") or [])
    return f"Rechnung {mode}" + (f" · {count} Position(en)" if count else "")


def _public_plan(workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": workflow["title"],
        "confirmation_text": workflow["confirmation_text"],
        "steps": [{"id": step["id"], "type": step["type"], "summary": _step_summary(step)} for step in workflow["steps"]],
    }


def _save_pending_plan(request, workflow: dict[str, Any]) -> str:
    nonce = secrets.token_urlsafe(18)
    token = signing.dumps(
        {"v": 1, "nonce": nonce, "org_id": _org(request).pk, "user_id": request.user.pk, "workflow": workflow},
        salt=PLAN_SALT,
        compress=True,
    )
    pending = request.session.get(PENDING_SESSION_KEY)
    if not isinstance(pending, dict):
        pending = {}
    pending[nonce] = timezone.now().isoformat()
    if len(pending) > 10:
        pending = dict(list(pending.items())[-10:])
    request.session[PENDING_SESSION_KEY] = pending
    request.session.modified = True
    return token


def plan_workflow(request, payload: dict[str, Any], message: str) -> JsonResponse:
    if _is_field_user(request):
        return JsonResponse({"ok": False, "error": "Mehrstufige Geschäftsabläufe dürfen nur Büro, Projektleitung oder Buchhaltung ausführen."}, status=403)
    org = _org(request)
    context = _business_context(org)
    prompt = f"""
Du bist der A+Bau Agent-Orchestrator für ein deutsches Handwerker-ERP.
Plane aus der Nutzeranweisung einen zusammenhängenden, serverseitig ausführbaren Ablauf. Nichts wird in diesem Schritt gespeichert.

Erlaubte Schreiboperationen:
- create_customer: einen Kunden anlegen.
- create_project: ein Projekt für einen Kunden anlegen.
- create_quote: ein Angebot für ein Projekt anlegen.
- create_invoice: eine Rechnung für ein Projekt anlegen; optional aus einem zuvor geplanten Angebot.

Sicherheitsregeln:
- Der gesamte Plan wird dem Nutzer anschließend EINMAL vollständig zur Bestätigung gezeigt. Erst nach dieser Bestätigung wird alles transaktional ausgeführt.
- Keine Löschungen, keine Zahlungen, keine Bankaktionen und keine E-Mails versenden.
- status=sent bedeutet nur, dass Angebot/Rechnung im ERP als gesendet/ausgestellt markiert wird. Es wird keine E-Mail verschickt.
- Nutze parent_ref für einen Datensatz, der in einem früheren Schritt dieses Plans angelegt wird. Nutze parent_id nur für einen eindeutig passenden vorhandenen Datensatz aus dem Kontext; IDs niemals erfinden.
- Bei einer Rechnung aus einem gerade erstellten Angebot source_ref auf dessen Schritt-ID setzen. Bei einem vorhandenen Angebot source_id verwenden.
- Wenn der Nutzer ein Angebot/eine Rechnung ohne Positionen verlangt, darf ein leerer Dokumententwurf erstellt werden. Wenn konkrete Leistungen/Preise genannt sind, in items übernehmen.
- unit_price ist der Verkaufspreis. purchase_price ist der interne Einkaufspreis. Wenn nur ein Verkaufspreis genannt ist, purchase_price=0 und unit_price entsprechend setzen.
- Für neue Kunden reicht Firma ODER Vor-/Nachname. Nicht nach Telefon/E-Mail/Adresse fragen, wenn diese nicht benötigt oder genannt wurden.
- Für ein Projekt darfst du aus der beschriebenen Arbeit einen kurzen sinnvollen Projekttitel ableiten.
- needs_clarification=true nur wenn der gewünschte Ablauf ohne eine wirklich notwendige Information nicht eindeutig planbar ist.
- Antworte und formuliere confirmation_text vollständig auf Deutsch.

Aktuelle echte Datensätze (nur zur eindeutigen Wiederverwendung):
{json.dumps(context, ensure_ascii=False)}

Nutzeranweisung:
{message}
""".strip()
    try:
        response = _create_response(
            org,
            input=[
                {"role": "developer", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
            ],
            text={"format": {"type": "json_schema", "name": "ab_bau_agent_workflow", "schema": _plan_schema(), "strict": True}},
            store=False,
        )
        result = json.loads(response.output_text)
    except Exception:
        return JsonResponse({"ok": False, "error": "A+Bau KI konnte den mehrstufigen Ablauf gerade nicht planen. Bitte erneut versuchen."}, status=502)

    if bool(result.get("needs_clarification")):
        clarification = str(result.get("clarification") or result.get("reply") or "Bitte ergänze die fehlenden Angaben.").strip()
        return JsonResponse({"ok": True, "mode": "clarification", "reply": clarification, "actions": [], "results": []})
    try:
        workflow = _validate_workflow(result.get("workflow") or {})
    except AgentPlanError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=422)
    token = _save_pending_plan(request, workflow)
    return JsonResponse({
        "ok": True,
        "mode": "workflow_plan",
        "requires_confirmation": True,
        "reply": str(result.get("reply") or "Ich habe den Ablauf vorbereitet. Bitte einmal vollständig bestätigen."),
        "plan": _public_plan(workflow),
        "plan_token": token,
        "actions": [],
        "results": [],
    })


def _tax_rate(code: str) -> Decimal:
    return {"19": Decimal("19"), "7": Decimal("7")}.get(str(code or "19"), Decimal("0"))


def _parent_customer(org, step: dict[str, Any], refs: dict[str, Any]):
    ref = step.get("parent_ref")
    if ref:
        obj = refs.get(ref)
        if isinstance(obj, m.Customer):
            return obj
        raise AgentPlanError("Der Kundenbezug im Ablauf ist ungültig.")
    pk = int(step.get("parent_id") or 0)
    if pk:
        customer = m.Customer.objects.filter(organization=org, active=True, pk=pk).first()
        if customer:
            return customer
    raise AgentPlanError("Für das Projekt fehlt ein eindeutiger Kunde.")


def _parent_project(org, step: dict[str, Any], refs: dict[str, Any]):
    ref = step.get("parent_ref")
    if ref:
        obj = refs.get(ref)
        if isinstance(obj, m.Project):
            return obj
        raise AgentPlanError("Der Projektbezug im Ablauf ist ungültig.")
    pk = int(step.get("parent_id") or 0)
    if pk:
        project = m.Project.objects.filter(organization=org, archived=False, pk=pk).first()
        if project:
            return project
    raise AgentPlanError("Für das Dokument fehlt ein eindeutiges Projekt.")


def _source_quote(org, step: dict[str, Any], refs: dict[str, Any]):
    ref = step.get("source_ref")
    if ref:
        obj = refs.get(ref)
        if isinstance(obj, m.Quote):
            return obj
        raise AgentPlanError("Der Angebotsbezug für die Rechnung ist ungültig.")
    pk = int(step.get("source_id") or 0)
    if pk:
        return m.Quote.objects.filter(organization=org, pk=pk).first()
    return None


def _find_or_create_customer(org, step: dict[str, Any]):
    email = str(step.get("email") or "").strip()
    company = str(step.get("company") or "").strip()
    first = str(step.get("first_name") or "").strip()
    last = str(step.get("last_name") or "").strip()
    if not (company or first or last):
        raise AgentPlanError("Für den neuen Kunden fehlt ein Name oder eine Firma.")
    existing = None
    if email:
        existing = m.Customer.objects.filter(organization=org, active=True, email__iexact=email).first()
    if existing is None and (company or last):
        query = Q(organization=org, active=True)
        if company:
            query &= Q(company__iexact=company)
        if first:
            query &= Q(first_name__iexact=first)
        if last:
            query &= Q(last_name__iexact=last)
        existing = m.Customer.objects.filter(query).first()
    if existing:
        return existing, False
    customer = m.Customer.objects.create(
        organization=org,
        number=_unique_number(m.Customer, org, "K"),
        type=str(step.get("customer_type") or "private"),
        company=company[:180], salutation=str(step.get("salutation") or "")[:30],
        first_name=first[:100], last_name=last[:100], email=email[:254],
        phone=str(step.get("phone") or "")[:60], mobile=str(step.get("mobile") or "")[:60],
        street=str(step.get("street") or "")[:180], postal_code=str(step.get("postal_code") or "")[:20],
        city=str(step.get("city") or "")[:120], country=(str(step.get("country") or "DE").strip().upper()[:2] or "DE"),
        notes=str(step.get("notes") or ""), active=True,
    )
    return customer, True


def _find_or_create_project(org, step: dict[str, Any], customer):
    title = str(step.get("title") or "").strip()
    if not title:
        raise AgentPlanError("Für das neue Projekt fehlt ein Titel.")
    existing = m.Project.objects.filter(organization=org, customer=customer, archived=False, title__iexact=title).first()
    if existing:
        return existing, False
    project = m.Project.objects.create(
        organization=org, number=_unique_number(m.Project, org, "P"), title=title[:220], customer=customer,
        status="inquiry", priority=str(step.get("priority") or "normal"), description=str(step.get("description") or ""), archived=False,
    )
    return project, True


def _commercial_settings(org, document, step: dict[str, Any], kind: str):
    kwargs = {"quote": document} if kind == "quote" else {"invoice": document}
    settings = m.CommercialDocumentSettings.objects.create(
        organization=org,
        tax_code=str(step.get("tax_code") or "19"),
        tax_rate=_tax_rate(str(step.get("tax_code") or "19")),
        discount_type=str(step.get("discount_type") or "percent"),
        discount_value=max(Decimal("0"), _decimal(step.get("discount_value"))),
        payment_due_days=max(0, min(365, int(step.get("due_days") or 14))),
        closing_text="",
        **kwargs,
    )
    return settings


def _create_item(document, org, raw: dict[str, Any], position: int, tax_rate: Decimal, kind: str):
    description = str(raw.get("description") or "").strip()
    if not description:
        return None
    quantity = max(Decimal("0"), _decimal(raw.get("quantity"), "1"))
    purchase = max(Decimal("0"), _decimal(raw.get("purchase_price")))
    markup = _clamp_decimal(raw.get("markup_percent"), Decimal("-100"), Decimal("10000"))
    explicit_price = max(Decimal("0"), _decimal(raw.get("unit_price")))
    unit_price = explicit_price if explicit_price > 0 else (purchase * (Decimal("1") + markup / Decimal("100"))).quantize(Decimal("0.01"))
    model = m.QuoteItem if kind == "quote" else m.InvoiceItem
    parent_field = "quote" if kind == "quote" else "invoice"
    item = model.objects.create(
        **{parent_field: document}, position=position, description=description, quantity=quantity,
        unit=(str(raw.get("unit") or "Stk.")[:30] or "Stk."), unit_price=unit_price, tax_rate=tax_rate,
        ai_generated=True, approved=True,
    )
    meta_kwargs = {
        "organization": org,
        "position_type": str(raw.get("position_type") or "other"),
        "purchase_price": purchase,
        "markup_percent": markup,
        "service_model": str(raw.get("service_model") or "normal"),
        "detail_text": "",
        "group_title": "",
        "quote_item" if kind == "quote" else "invoice_item": item,
    }
    m.CommercialItemMeta.objects.create(**meta_kwargs)
    return item


def _copy_quote_items_to_invoice(org, quote, invoice, tax_rate: Decimal):
    for position, source in enumerate(quote.items.select_related("catalog_item").order_by("position"), 1):
        item = m.InvoiceItem.objects.create(
            invoice=invoice, position=position, code=source.code, description=source.description,
            quantity=source.quantity, unit=source.unit, unit_price=source.unit_price, tax_rate=tax_rate,
            ai_generated=True, approved=True, catalog_item=source.catalog_item,
        )
        try:
            meta = source.commercial_meta
        except (m.CommercialItemMeta.DoesNotExist, AttributeError):
            meta = None
        m.CommercialItemMeta.objects.create(
            organization=org, invoice_item=item,
            position_type=getattr(meta, "position_type", "other"),
            purchase_price=getattr(meta, "purchase_price", Decimal("0")),
            markup_percent=getattr(meta, "markup_percent", Decimal("0")),
            service_model=getattr(meta, "service_model", "normal"),
            detail_text=getattr(meta, "detail_text", ""), group_title=getattr(meta, "group_title", ""),
        )


def _created_result(kind: str, obj, created: bool) -> dict[str, Any]:
    if kind == "create_customer":
        return {"type": kind, "id": obj.pk, "number": obj.number, "label": obj.display_name, "url": f"/customers/{obj.pk}/", "created": created}
    if kind == "create_project":
        return {"type": kind, "id": obj.pk, "number": obj.number, "label": obj.title, "url": f"/projects/{obj.pk}/", "created": created}
    if kind == "create_quote":
        return {"type": kind, "id": obj.pk, "number": obj.number, "label": f"Angebot {obj.number}", "url": f"/quotes/{obj.pk}/", "created": True}
    return {"type": kind, "id": obj.pk, "number": obj.number, "label": f"Rechnung {obj.number}", "url": f"/invoices/{obj.pk}/", "created": True}


@transaction.atomic
def execute_steps(org, user, workflow: dict[str, Any]) -> list[dict[str, Any]]:
    refs: dict[str, Any] = {}
    results: list[dict[str, Any]] = []
    for step in workflow["steps"]:
        kind = step["type"]
        if kind == "create_customer":
            obj, created = _find_or_create_customer(org, step)
        elif kind == "create_project":
            customer = _parent_customer(org, step, refs)
            obj, created = _find_or_create_project(org, step, customer)
        elif kind == "create_quote":
            project = _parent_project(org, step, refs)
            status = "sent" if step.get("status") == "sent" else "draft"
            today = timezone.localdate()
            obj = m.Quote.objects.create(
                organization=org, number=_unique_number(m.Quote, org, "A"), project=project,
                status=status, issue_date=today, valid_until=today + timedelta(days=max(0, min(365, int(step.get("valid_days") or 30)))),
                intro_text=str(step.get("intro_text") or ""), notes=str(step.get("notes") or ""), created_by=user,
                sent_at=timezone.now() if status == "sent" else None,
                discount_percent=_decimal(step.get("discount_value")) if step.get("discount_type") == "percent" else Decimal("0"),
            )
            settings = _commercial_settings(org, obj, step, "quote")
            for position, item in enumerate(step.get("items") or [], 1):
                _create_item(obj, org, item, position, settings.tax_rate, "quote")
            if project.status in {"inquiry", "planning"}:
                project.status = "quoted"; project.save(update_fields=["status", "updated_at"])
            created = True
        elif kind == "create_invoice":
            project = _parent_project(org, step, refs)
            quote = _source_quote(org, step, refs)
            if quote is not None and quote.project_id != project.pk:
                raise AgentPlanError("Angebot und Rechnung gehören nicht zum selben Projekt.")
            status = "sent" if step.get("status") == "sent" else "draft"
            today = timezone.localdate()
            due_days = max(0, min(365, int(step.get("due_days") or 14)))
            obj = m.Invoice.objects.create(
                organization=org, number=_unique_number(m.Invoice, org, "R"), project=project, quote=quote,
                status=status, issue_date=today, due_date=today + timedelta(days=due_days), service_date=today,
                intro_text=str(step.get("intro_text") or ""), notes=str(step.get("notes") or ""), created_by=user,
                sent_at=timezone.now() if status == "sent" else None,
            )
            settings = _commercial_settings(org, obj, step, "invoice")
            items = step.get("items") or []
            if items:
                for position, item in enumerate(items, 1):
                    _create_item(obj, org, item, position, settings.tax_rate, "invoice")
            elif quote is not None:
                _copy_quote_items_to_invoice(org, quote, obj, settings.tax_rate)
            if project.status not in {"completed", "cancelled"}:
                project.status = "invoiced"; project.save(update_fields=["status", "updated_at"])
            created = True
        else:
            raise AgentPlanError("Nicht erlaubter KI-Schritt.")
        refs[step["id"]] = obj
        results.append(_created_result(kind, obj, created))
        m.ActivityLog.objects.create(
            organization=org, user=user, verb="ki_agent_created" if created else "ki_agent_reused",
            entity_type=obj.__class__.__name__, entity_id=str(obj.pk),
            description=f"A+Bau KI: {_step_summary(step)}",
            metadata={"agent_step": step["id"], "agent_type": kind, "created": created},
        )
    return results


@login_required
@require_POST
def execute_workflow(request):
    if not has_ai_consent(request.user):
        return JsonResponse({"ok": False, "error": "Vor der KI-Verarbeitung ist deine ausdrückliche Einwilligung erforderlich.", "consent_required": True, "settings_url": "/settings/next/"}, status=428)
    if _is_field_user(request):
        return JsonResponse({"ok": False, "error": "Mehrstufige Geschäftsabläufe dürfen nur Büro, Projektleitung oder Buchhaltung ausführen."}, status=403)
    try:
        body = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Ungültige Bestätigung."}, status=400)
    if body.get("confirmed") is not True:
        return JsonResponse({"ok": False, "error": "Der Ablauf wurde nicht bestätigt."}, status=400)
    token = str(body.get("plan_token") or "").strip()
    if not token:
        return JsonResponse({"ok": False, "error": "Der Bestätigungsplan fehlt."}, status=400)
    try:
        signed = signing.loads(token, salt=PLAN_SALT, max_age=PLAN_MAX_AGE_SECONDS)
    except signing.SignatureExpired:
        return JsonResponse({"ok": False, "error": "Der KI-Plan ist abgelaufen. Bitte die Anweisung erneut senden."}, status=410)
    except signing.BadSignature:
        return JsonResponse({"ok": False, "error": "Der KI-Plan ist ungültig oder wurde verändert."}, status=400)
    org = _org(request)
    if int(signed.get("org_id") or 0) != org.pk or int(signed.get("user_id") or 0) != request.user.pk:
        return JsonResponse({"ok": False, "error": "Dieser KI-Plan gehört zu einem anderen Konto oder Betrieb."}, status=403)
    nonce = str(signed.get("nonce") or "")
    pending = request.session.get(PENDING_SESSION_KEY)
    if not isinstance(pending, dict) or nonce not in pending:
        return JsonResponse({"ok": False, "error": "Dieser KI-Plan wurde bereits ausgeführt oder ist nicht mehr gültig."}, status=409)
    try:
        workflow = _validate_workflow(signed.get("workflow") or {})
        results = execute_steps(org, request.user, workflow)
    except AgentPlanError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=422)
    except Exception:
        return JsonResponse({"ok": False, "error": "Der Ablauf wurde vollständig zurückgerollt, weil ein Schritt nicht ausgeführt werden konnte."}, status=500)

    pending.pop(nonce, None)
    request.session[PENDING_SESSION_KEY] = pending
    request.session.modified = True
    created_count = sum(1 for item in results if item.get("created"))
    reused_count = len(results) - created_count
    reply = f"Erledigt. {created_count} Datensatz/Datensätze wurden angelegt."
    if reused_count:
        reply += f" {reused_count} bereits vorhandene Datensätze wurden sicher wiederverwendet."
    return JsonResponse({
        "ok": True, "mode": "workflow_result", "reply": reply, "created": results,
        "final_url": results[-1]["url"] if results else "/",
    })
