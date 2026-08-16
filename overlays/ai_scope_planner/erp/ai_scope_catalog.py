from __future__ import annotations

import re
import unicodedata
from typing import Any

from erp.services.bo_direct_search import search_bo_prices, serialize_bo_price


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _unit_family(value: str) -> str:
    unit = _norm(value)
    if unit in {"m2", "qm", "quadratmeter"}:
        return "area"
    if unit in {"m", "lfm", "meter", "laufmeter"}:
        return "length"
    if unit in {"stk", "stuck", "stueck", "stück"}:
        return "piece"
    if unit in {"h", "std", "stunde", "stunden"}:
        return "time"
    if unit in {"psch", "pausch", "pauschal", "pauschale"}:
        return "flat"
    return unit


def _candidate_score(row, scope_item: dict[str, Any]) -> int:
    description = _norm(getattr(row, "description", ""))
    code = _norm(getattr(row, "code", ""))
    target = _norm(scope_item.get("label") or "")
    terms = [_norm(term) for term in (scope_item.get("catalog_terms") or []) if _norm(term)]
    expected_unit = _unit_family(str(scope_item.get("unit") or ""))
    actual_unit = _unit_family(str(getattr(row, "unit", "") or ""))
    score = 0
    if expected_unit and actual_unit and expected_unit == actual_unit:
        score += 60
    elif expected_unit and actual_unit and expected_unit != actual_unit:
        score -= 80
    if target and target in description:
        score += 160
    words = {token for token in target.split() if len(token) > 2}
    if words:
        score += 28 * sum(1 for token in words if token in description or token in code)
    for term in terms:
        if term in description or term in code:
            score += 120
        t_words = {token for token in term.split() if len(token) > 2}
        score += 20 * sum(1 for token in t_words if token in description or token in code)
    return score


def _best_bo_row(organization, scope_item: dict[str, Any]):
    candidates = {}
    queries = list(scope_item.get("catalog_terms") or []) + [scope_item.get("label") or ""]
    for query in queries[:6]:
        query = str(query or "").strip()
        if len(query) < 2:
            continue
        for row in search_bo_prices(organization, query, limit=8):
            candidates[row.pk] = row
    if not candidates:
        return None
    ranked = sorted(candidates.values(), key=lambda row: (_candidate_score(row, scope_item), -len(str(getattr(row, "description", "") or ""))), reverse=True)
    best = ranked[0]
    # Unit compatibility plus a lexical match is deliberately required. This is
    # safer than blindly picking the first priced row for a broad word like "Boden".
    if _candidate_score(best, scope_item) < 75:
        return None
    return best


def _can_see_prices(request) -> bool:
    profile = getattr(getattr(request, "user", None), "profile", None)
    role = str(getattr(profile, "role", "office") or "office").lower()
    if role == "technician" or bool(getattr(profile, "is_mobile_worker", False)):
        return False
    return True


def enrich_scope_with_authoritative_catalog(scope_plan: dict[str, Any], organization, request) -> dict[str, Any]:
    """Attach real imported B&O price rows to deterministic scope items.

    Field users never receive price-row payloads. Office users can get a real
    imported position even when it is outside the 500 quick-catalog rows currently
    rendered in the browser. Nothing is saved: the frontend only inserts editable
    draft rows in an open Angebot/Rechnung editor.
    """
    if not isinstance(scope_plan, dict) or not _can_see_prices(request):
        return scope_plan
    items = scope_plan.get("scope_items") or []
    if not isinstance(items, list):
        return scope_plan
    actions = list(scope_plan.get("actions") or [])
    existing_keys = {str(action.get("scope_key") or "") for action in actions if isinstance(action, dict)}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        if item.get("catalog_match") or key in existing_keys:
            continue
        row = _best_bo_row(organization, item)
        if row is None:
            continue
        payload = serialize_bo_price(row)
        item["catalog_match"] = {
            "name": payload["description"],
            "code": payload["code"],
            "unit": payload["unit"],
            "source": payload["source"],
            "price_mode": payload["price_mode"],
            "authoritative": True,
        }
        actions.append({
            "type": "bo_catalog_add",
            "scope_key": key,
            "target": "",
            "value": payload["code"] or payload["description"],
            "count": 1,
            "quantity": item.get("quantity"),
            "unit": item.get("unit") or payload["unit"],
            "label": item.get("label") or payload["description"],
            "item": payload,
        })
        existing_keys.add(key)
    scope_plan["actions"] = actions
    return scope_plan
