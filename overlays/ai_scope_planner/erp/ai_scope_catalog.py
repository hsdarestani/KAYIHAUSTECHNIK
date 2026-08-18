from __future__ import annotations

import re
import unicodedata
from typing import Any

from erp.services.bo_direct_search import search_bo_prices, serialize_bo_price


CATALOG_CONTEXT_HARDENING = "A+Bau catalog context hardening 2026-08-18"


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
    if unit in {"stk", "stuck", "stueck"}:
        return "piece"
    if unit in {"h", "std", "stunde", "stunden"}:
        return "time"
    if unit in {"psch", "pausch", "pauschal", "pauschale"}:
        return "flat"
    return unit


_PRIMARY_CONTEXT_TERMS = {
    "wall": ("wand", "wande", "wandflaeche", "wandflaechen"),
    "ceiling": ("decke", "decken", "deckenflaeche", "deckenflaechen"),
    "floor": ("boden", "fussboden", "fussbodenflaeche", "untergrund"),
    "tile": ("fliese", "fliesen", "flies"),
    "door": ("tuer", "tueren"),
    "window": ("fenster",),
}

# These are context qualifiers, not generic trade words. A candidate carrying one
# of them must be explicitly requested by the scope item; otherwise it is rejected.
# This prevents e.g. a Keller-only painting item from winning a generic apartment
# painting request simply because both contain "Wände" and "streichen".
_RESTRICTED_CONTEXT_TERMS = {
    "keller": ("keller", "kellerraum", "kellerraeume"),
    "exterior": ("aussen", "fassade", "fassaden"),
    "roof": ("dach", "dachflaeche", "dachflaechen"),
    "wood": ("holz", "parkett"),
    "metal": ("metall",),
    "fireproof": ("brandschutz", "fallrohr"),
    "stone_finish": ("buntsteinputz",),
    "bathroom": ("bad", "badezimmer", "nassraum"),
    "tile": ("fliese", "fliesen", "flies"),
    "stair": ("treppe", "treppen"),
}


def _scope_contexts(scope_item: dict[str, Any]) -> set[str]:
    key = _norm(scope_item.get("key") or "")
    text = _norm(f"{scope_item.get('label') or ''} {' '.join(scope_item.get('catalog_terms') or [])}")
    contexts: set[str] = set()
    for context, terms in _PRIMARY_CONTEXT_TERMS.items():
        if any(term in text for term in terms):
            contexts.add(context)
    if key.startswith("bath."):
        contexts.add("bathroom")
    if key in {"bath.walltile.demolish", "bath.substrate.fill", "bath.substrate.prime", "bath.walltile.install"}:
        contexts.add("wall")
    if key in {"bath.floortile.demolish", "bath.floor.seal", "bath.floortile.install"}:
        contexts.add("floor")
    if key == "protect.floor":
        contexts.add("floor")
    return contexts


def _candidate_contexts(row) -> set[str]:
    text = _norm(f"{getattr(row, 'description', '')} {getattr(row, 'code', '')}")
    contexts: set[str] = set()
    for context, terms in _PRIMARY_CONTEXT_TERMS.items():
        if any(term in text for term in terms):
            contexts.add(context)
    for context, terms in _RESTRICTED_CONTEXT_TERMS.items():
        if any(term in text for term in terms):
            contexts.add(context)
    return contexts


def _required_anchor_groups(scope_item: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    key = _norm(scope_item.get("key") or "")
    label = _norm(scope_item.get("label") or "")
    if key.endswith(".primer") or "grundierung" in label or "grundieren" in label:
        return (("grundier", "grundierung"),)
    if key.endswith(".coat") or "anstrich" in label:
        return (("dispersionsfarbe", "dispersionsanstrich", "anstrich", "streichen", "malern"),)
    if key == "paint.wallpaper.remove":
        return (("tapete", "tapeten"), ("entfern", "abtragen", "abnahme"))
    if key == "protect.floor":
        return (("abdeck", "abdecken"),)
    if key == "protect.furniture":
        return (("moebel", "mobiliar", "gegenstand", "gegenstaende"), ("schutz", "schuetz", "abdeck"))
    if key == "protect.moving":
        return (("umraum", "umraeum", "umstellen"),)
    if key == "protect.doors":
        return (("tuer", "tueren"), ("abkle", "schutz", "schuetz"))
    if key == "protect.windows":
        return (("fenster",), ("abkle", "schutz", "schuetz"))
    if key == "protect.difficulty":
        return (("erschwern", "zuschlag"),)
    if key == "documentation.damage":
        return (("schaden", "schaeden", "bestandsdokumentation", "schadendokumentation"),)
    if key.endswith(".demolish") and "tile" in key:
        return (("fliese", "fliesen", "flies"), ("abbruch", "abbrechen", "entfern"))
    if key.endswith(".install") and "tile" in key:
        return (("fliese", "fliesen", "flies"),)
    if key == "bath.floor.seal":
        return (("abdicht", "abdichtung", "verbundabdichtung"),)
    if key in {"bath.substrate.fill"}:
        return (("spachtel", "ausgleich", "untergrund vorbereiten"),)
    if key in {"bath.water.cold", "bath.water.hot"}:
        group = ("kaltwasser", "kalt wasser") if key.endswith("cold") else ("warmwasser", "warm wasser")
        return (group, ("leitung", "leitungen"), ("neu", "herstell", "umbau", "erneuer"))
    if key.startswith("bath.fixture."):
        if key.endswith("sink"):
            return (("waschbecken", "waschtisch"), ("erneuer", "austausch", "ersetzen"))
        if key.endswith("wc"):
            return (("wc", "toilette"), ("erneuer", "austausch", "ersetzen"))
        return (("dusche", "badewanne"), ("erneuer", "austausch", "ersetzen"))
    return tuple()


def _context_compatible(row, scope_item: dict[str, Any]) -> bool:
    scope_contexts = _scope_contexts(scope_item)
    candidate_contexts = _candidate_contexts(row)

    for restricted in _RESTRICTED_CONTEXT_TERMS:
        if restricted in candidate_contexts and restricted not in scope_contexts:
            return False

    candidate_primary = candidate_contexts & set(_PRIMARY_CONTEXT_TERMS)
    scope_primary = scope_contexts & set(_PRIMARY_CONTEXT_TERMS)
    if candidate_primary and scope_primary and not candidate_primary.intersection(scope_primary):
        return False
    if candidate_primary and not scope_primary:
        # A specialized surface must not be inferred for a context-free item.
        return False
    return True


def _candidate_score(row, scope_item: dict[str, Any]) -> int:
    description = _norm(getattr(row, "description", ""))
    code = _norm(getattr(row, "code", ""))
    target = _norm(scope_item.get("label") or "")
    terms = [_norm(term) for term in (scope_item.get("catalog_terms") or []) if _norm(term)]
    expected_unit = _unit_family(str(scope_item.get("unit") or ""))
    actual_unit = _unit_family(str(getattr(row, "unit", "") or ""))

    if expected_unit and actual_unit and expected_unit != actual_unit:
        return -10000
    if not _context_compatible(row, scope_item):
        return -10000

    candidate = f"{description} {code}".strip()
    for group in _required_anchor_groups(scope_item):
        if not any(anchor in candidate for anchor in group):
            return -10000

    score = 0
    if expected_unit and actual_unit and expected_unit == actual_unit:
        score += 60
    if target and target in description:
        score += 240
    target_words = {token for token in target.split() if len(token) > 2}
    score += 18 * sum(1 for token in target_words if token in candidate)
    for term in terms:
        if term and term in description:
            score += 150
        term_words = {token for token in term.split() if len(token) > 2}
        score += 12 * sum(1 for token in term_words if token in candidate)
    scope_contexts = _scope_contexts(scope_item)
    if _candidate_contexts(row) & (scope_contexts & set(_PRIMARY_CONTEXT_TERMS)):
        score += 60
    for group in _required_anchor_groups(scope_item):
        if any(anchor in candidate for anchor in group):
            score += 120
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

    ranked = sorted(
        ((row, _candidate_score(row, scope_item)) for row in candidates.values()),
        key=lambda pair: (pair[1], -len(str(getattr(pair[0], "description", "") or ""))),
        reverse=True,
    )
    ranked = [(row, score) for row, score in ranked if score > 0]
    if not ranked:
        return None

    best, best_score = ranked[0]
    if best_score < 100:
        return None

    # If two materially different rows are almost equally plausible, do not guess.
    # Exact/full phrase matches are allowed through; weaker matches need a clear lead.
    for alternative, alternative_score in ranked[1:]:
        same_identity = (
            str(getattr(alternative, "code", "") or "") == str(getattr(best, "code", "") or "")
            and _norm(getattr(alternative, "description", "")) == _norm(getattr(best, "description", ""))
        )
        if not same_identity:
            if best_score < 300 and alternative_score >= best_score - 18:
                return None
            break
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
