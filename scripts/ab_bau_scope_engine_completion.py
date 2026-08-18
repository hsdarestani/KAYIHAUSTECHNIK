from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+Bau scope engine completion 2026-08-18"
VERSION = "20260818-scope-complete-1"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing scope completion target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def ensure_scope_runtime() -> None:
    planner = ROOT / "erp" / "ai_scope_planner.py"
    catalog = ROOT / "erp" / "ai_scope_catalog.py"
    overlay = ROOT / "overlays" / "ai_scope_planner" / "erp"
    if not planner.exists():
        shutil.copy2(overlay / "ai_scope_planner.py", planner)
    if not catalog.exists():
        shutil.copy2(overlay / "ai_scope_catalog.py", catalog)

    rel = "erp/assistant_views.py"
    text = read(rel)
    planner_import = "from .ai_scope_planner import plan_scope_message\n"
    if planner_import not in text:
        anchor = "from .store_views import has_ai_consent\n"
        if anchor not in text:
            raise RuntimeError("assistant scope import anchor changed")
        text = text.replace(anchor, anchor + planner_import, 1)

    catalog_import = "from .ai_scope_catalog import enrich_scope_with_authoritative_catalog\n"
    if catalog_import not in text:
        text = text.replace(planner_import, planner_import + catalog_import, 1)

    if "scope_plan = plan_scope_message(message, request.session" not in text:
        command_at = text.find("def assistant_command(request):")
        if command_at < 0:
            raise RuntimeError("assistant_command missing")
        org_anchor = "    organization = _org(request)\n"
        org_at = text.find(org_anchor, command_at)
        if org_at < 0:
            context_anchor = "    context = _compact_ui_context(payload)\n"
            context_at = text.find(context_anchor, command_at)
            if context_at < 0:
                raise RuntimeError("assistant scope organization/context anchor changed")
            text = text[:context_at] + org_anchor + text[context_at:]
            org_at = context_at
        insert_at = org_at + len(org_anchor)
        hook = '''    scope_plan = plan_scope_message(message, request.session, payload.get("catalog") or [])
    if scope_plan is not None:
        scope_plan = enrich_scope_with_authoritative_catalog(scope_plan, organization, request)
        return JsonResponse(scope_plan)
'''
        text = text[:insert_at] + hook + text[insert_at:]
    elif "enrich_scope_with_authoritative_catalog(scope_plan, organization, request)" not in text:
        old = '''    scope_plan = plan_scope_message(message, request.session, payload.get("catalog") or [])
    if scope_plan is not None:
        return JsonResponse(scope_plan)
'''
        new = '''    scope_plan = plan_scope_message(message, request.session, payload.get("catalog") or [])
    if scope_plan is not None:
        scope_plan = enrich_scope_with_authoritative_catalog(scope_plan, organization, request)
        return JsonResponse(scope_plan)
'''
        if old not in text:
            raise RuntimeError("assistant authoritative scope hook changed")
        text = text.replace(old, new, 1)
    write(rel, text)


def patch_planner() -> None:
    rel = "erp/ai_scope_planner.py"
    text = read(rel)

    old_cover = 'COVER_WORDS = ("abdecken", "abdeckung", "schutzen", "schützen", "abkleben")'
    new_cover = 'COVER_WORDS = ("abdecken", "abgedeckt", "abdeckung", "abdeckarbeiten", "abkleben", "abgeklebt", "schutzen", "schützen", "geschutzt", "geschützt", "geschuetzt")'
    if old_cover in text:
        text = text.replace(old_cover, new_cover, 1)
    elif "abgedeckt" not in text:
        raise RuntimeError("planner cover-word anchor changed")

    if "def _semantic_count_answer(" not in text:
        anchor = '''def _answer_yes_no(text: str) -> bool | None:
'''
        pos = text.find(anchor)
        if pos < 0:
            raise RuntimeError("planner semantic-count insertion anchor changed")
        helper = r'''
COUNT_NOUNS = {
    "furniture_count": ("möbel", "moebel", "mobiliar", "gegenstand", "gegenstände", "gegenstande"),
    "door_count": ("tür", "türen", "tuer", "tueren"),
    "window_count": ("fenster",),
}


def _semantic_count_answer(pending: str, text: str) -> int | None:
    nouns = COUNT_NOUNS.get(pending)
    if not nouns:
        return None
    explicit = _extract_count(text, nouns)
    if explicit is not None:
        return explicit
    normalized = _norm(text)
    for other, other_nouns in COUNT_NOUNS.items():
        if other != pending and _contains(normalized, other_nouns):
            return None
    bare = re.fullmatch(r"\s*(\d+)\s*(?:stk\.?|stuck|stueck|stück|anzahl)?\s*[.!]?\s*", normalized)
    return int(bare.group(1)) if bare else None


def _looks_like_scope_fact(kind: str, text: str) -> bool:
    n = _norm(text)
    if kind == "painting":
        if _contains(n, (
            "bewohnt", "unbewohnt", "möbliert", "mobliert", "leersteh", "möbel", "moebel",
            "mobiliar", "gegenstand", "tür", "tuer", "fenster", "umräum", "umraum",
            "schaden", "schäden", "vorschaden", "mangel", "mängel", "tapet", "untergrund",
            "tragfähig", "tragfahig", "spachtel", "abgedeckt", "abdecken", "abdeckung",
        )):
            return True
        if _contains(n, PAINT_WORDS) or (_contains(n, COVER_WORDS) and _contains(n, FLOOR_WORDS)):
            return True
        return bool(re.search(r"\d+(?:[.,]\d+)?\s*(?:m2|m²|qm|quadratmeter|stunden|std\.?|h)\b", n))
    if kind == "bathroom":
        if _contains(n, (
            "bad", "badezimmer", "fliesen", "wandfliesen", "bodenfliesen", "wasser", "leitung",
            "kaltwasser", "warmwasser", "waschbecken", "waschtisch", "wc", "toilette",
            "badewanne", "dusche", "schaden", "vorschaden",
        )):
            return True
        return bool(re.search(r"\d+(?:[.,]\d+)?\s*(?:m2|m²|qm|quadratmeter|m|lfm)\b", n))
    return False


'''
        text = text[:pos] + helper + text[pos:]

    old_count = '''    if pending in {"furniture_count", "door_count", "window_count"}:
        match = re.search(r"\\d+", n)
        if match:
            facts[pending] = int(match.group())
            state["pending"] = ""
            return True
        return False
'''
    new_count = '''    if pending in {"furniture_count", "door_count", "window_count"}:
        count = _semantic_count_answer(pending, message)
        if count is not None:
            facts[pending] = count
            state["pending"] = ""
            return True
        return False
'''
    if new_count not in text:
        if old_count not in text:
            raise RuntimeError("planner pending count anchor changed")
        text = text.replace(old_count, new_count, 1)

    old_pending = '''    if pending in {"floor_area", "bath_floor_area", "bath_wall_area", "furniture_count", "moving_hours", "door_count", "window_count", "water_line_length"}:
        return bool(re.search(r"\\d", n)) or n in {"offen", "unbekannt", "noch offen", "keine angabe"}
'''
    new_pending = '''    if pending in {"furniture_count", "door_count", "window_count"}:
        return _semantic_count_answer(pending, text) is not None
    if pending in {"floor_area", "bath_floor_area", "bath_wall_area", "moving_hours", "water_line_length"}:
        return bool(re.search(r"\\d", n)) or n in {"offen", "unbekannt", "noch offen", "keine angabe"}
'''
    if new_pending not in text:
        if old_pending not in text:
            raise RuntimeError("planner pending-answer anchor changed")
        text = text.replace(old_pending, new_pending, 1)

    old_gate = '''    if active_kind and not detected:
        pending = str(state.get("pending") or "")
        if not pending or not _looks_like_pending_answer(pending, raw):
            return None
'''
    new_gate = '''    if active_kind and not detected:
        pending = str(state.get("pending") or "")
        if not pending or (
            not _looks_like_pending_answer(pending, raw)
            and not _looks_like_scope_fact(active_kind, raw)
        ):
            return None
'''
    if new_gate not in text:
        if old_gate not in text:
            raise RuntimeError("planner active-scope gate anchor changed")
        text = text.replace(old_gate, new_gate, 1)

    old_damage = '''    if _contains(n, ("keine schaden", "keine schäden", "ohne schaden", "keine mängel", "keine mangel")):
        facts["damage_present"] = False
    elif _contains(n, ("schaden vorhanden", "schäden vorhanden", "vorschaden", "bestandschaden", "mangel vorhanden", "mängel vorhanden")):
        facts["damage_present"] = True
'''
    new_damage = '''    damage_words = ("schaden", "schäden", "vorschaden", "vorschäden", "bestandschaden", "bestandschäden", "mangel", "mängel")
    if _contains(n, damage_words):
        if _contains(n, ("keine schaden", "keine schäden", "ohne schaden", "ohne schäden", "keine mängel", "keine mangel", "nicht vorhanden")):
            facts["damage_present"] = False
        elif (
            _contains(n, ("schaden vorhanden", "schäden vorhanden", "vorschaden", "vorschäden", "bestandschaden", "bestandschäden", "es gibt", "bereits schaden", "bereits schäden"))
            or _answer_yes_no(message) is True
        ):
            facts["damage_present"] = True
'''
    if new_damage not in text:
        if old_damage not in text:
            raise RuntimeError("planner damage parsing anchor changed")
        text = text.replace(old_damage, new_damage, 1)

    start = text.find("def _catalog_score(")
    end = text.find("\ndef _summary(", start)
    if start < 0 or end < 0:
        raise RuntimeError("planner catalog matcher block changed")
    replacement = r'''CATALOG_SEMANTIC_RULES = {
    "paint.wall.primer": {"required": (("grundier",), ("wand", "wande", "fläche", "flache", "untergrund")), "forbidden": ("tapet", "buntstein", "parkett", "abbruch", "entfern")},
    "paint.wall.coat": {"required": (("dispers", "anstrich", "streich"), ("wand", "wande", "fläche", "flache")), "forbidden": ("buntstein", "tapet", "parkett", "abbruch", "entfern", "lackier")},
    "paint.ceiling.primer": {"required": (("grundier",), ("deck", "decke")), "forbidden": ("tapet", "abbruch", "entfern", "buntstein")},
    "paint.ceiling.coat": {"required": (("dispers", "anstrich", "streich"), ("deck", "decke")), "forbidden": ("tapet", "abbruch", "entfern", "buntstein")},
    "paint.substrate.fill": {"required": (("spachtel", "ausgleich", "ausbesser"),), "forbidden": ("abbruch", "entsorg", "parkett")},
    "paint.wallpaper.remove": {"required": (("tapet",), ("entfern", "ablos", "ablös", "abnehm")), "forbidden": ("anstrich", "streich", "grundier")},
    "protect.floor": {"required": (("boden", "fussboden", "fußboden", "untergrund"), ("abdeck", "schutz", "schütz")), "forbidden": ("abbruch", "entsorg", "parkett")},
    "protect.furniture": {"required": (("mobel", "möbel", "mobiliar", "gegenstand"), ("schutz", "schütz", "abdeck")), "forbidden": ("abbruch",)},
    "protect.moving": {"required": (("umraum", "umräum", "umstell", "raumen", "räumen"),), "forbidden": ()},
    "protect.difficulty": {"required": (("erschwern", "zuschlag"),), "forbidden": ()},
    "protect.doors": {"required": (("tur", "tür", "tuer"), ("abkleb", "schutz", "schütz", "abdeck")), "forbidden": ("fenster",)},
    "protect.windows": {"required": (("fenster",), ("abkleb", "schutz", "schütz", "abdeck")), "forbidden": ("tur", "tür", "tuer")},
    "documentation.damage": {"required": (("schad", "vorschad", "bestand"), ("dokument", "aufnahme", "protokoll")), "forbidden": ()},
    "bath.walltile.demolish": {"required": (("flies",), ("wand",), ("abbruch", "abbrech", "entfern", "ausbau")), "forbidden": ("brandschutz", "fallrohr", "damm", "dämm", "herstell", "verleg")},
    "bath.floortile.demolish": {"required": (("flies",), ("boden",), ("abbruch", "abbrech", "entfern", "ausbau")), "forbidden": ("parkett", "herstell", "verleg")},
    "bath.substrate.fill": {"required": (("spachtel", "ausgleich", "vorbereit"),), "forbidden": ("abbruch", "entsorg", "parkett")},
    "bath.substrate.prime": {"required": (("grundier",), ("untergrund", "wand", "flies", "innen")), "forbidden": ("fassad", "dach", "abbruch")},
    "bath.walltile.install": {"required": (("flies",), ("wand",), ("verleg", "herstell", "anbring")), "forbidden": ("abbruch", "abbrech", "entfern", "brandschutz", "fallrohr", "damm", "dämm")},
    "bath.floor.seal": {"required": (("abdicht", "verbundabdicht"), ("boden",)), "forbidden": ("parkett", "abbruch", "entsorg", "ausbau")},
    "bath.floortile.install": {"required": (("flies",), ("boden",), ("verleg", "herstell")), "forbidden": ("abbruch", "abbrech", "entfern", "parkett")},
    "bath.water.cold": {"required": (("kaltwasser", "kalt wasser"), ("leitung",)), "forbidden": ("warmwasser",)},
    "bath.water.hot": {"required": (("warmwasser", "warm wasser"), ("leitung",)), "forbidden": ("kaltwasser",)},
    "bath.fixture.sink": {"required": (("waschbecken", "waschtisch"), ("erneuer", "austausch", "ersetz", "montier")), "forbidden": ("wc", "toilette", "badewanne", "dusche")},
    "bath.fixture.wc": {"required": (("wc", "toilette"), ("erneuer", "austausch", "ersetz", "montier")), "forbidden": ("waschbecken", "waschtisch")},
    "bath.fixture.bath_shower": {"required": (("badewanne", "wanne", "dusche"), ("erneuer", "austausch", "ersetz", "montier")), "forbidden": ()},
}


def _catalog_unit_family(value: str) -> str:
    unit = _norm(value)
    if unit in {"m2", "qm", "quadratmeter"}: return "area"
    if unit in {"m", "lfm", "meter", "laufmeter"}: return "length"
    if unit in {"stk", "stuck", "stueck", "stück"}: return "piece"
    if unit in {"h", "std", "stunde", "stunden"}: return "time"
    if unit in {"psch", "pausch", "pauschal", "pauschale"}: return "flat"
    return unit


def catalog_semantic_match(scope_item: dict[str, Any], catalog_item: dict[str, Any]) -> bool:
    candidate = _norm(f"{catalog_item.get('code','')} {catalog_item.get('name','')} {catalog_item.get('description','')}")
    if not candidate: return False
    expected = _catalog_unit_family(str(scope_item.get("unit") or ""))
    actual = _catalog_unit_family(str(catalog_item.get("unit") or ""))
    if expected and actual and expected != actual: return False
    rule = CATALOG_SEMANTIC_RULES.get(str(scope_item.get("key") or ""))
    if not rule: return False
    for group in rule.get("required") or ():
        if not any(_norm(token) in candidate for token in group): return False
    if any(_norm(token) in candidate for token in (rule.get("forbidden") or ())): return False
    return True


def _catalog_score(catalog_item: dict[str, Any], scope_item: dict[str, Any]) -> int:
    if not catalog_semantic_match(scope_item, catalog_item): return 0
    candidate = _norm(f"{catalog_item.get('code','')} {catalog_item.get('name','')} {catalog_item.get('description','')}")
    terms = list(scope_item.get("catalog_terms") or []) + [scope_item.get("label") or ""]
    best = 180
    for term in terms:
        q = _norm(term)
        if not q: continue
        if q in candidate:
            best = max(best, 320 + len(q)); continue
        q_tokens = [token for token in q.split() if len(token) > 2]
        overlap = sum(1 for token in q_tokens if token in candidate)
        if q_tokens: best = max(best, 180 + int(120 * overlap / len(q_tokens)))
    return best


def _match_catalog(items: list[dict[str, Any]], catalog: list[dict[str, Any]], already: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    actions, matched_items, applied = [], deepcopy(items), set(already)
    for item in matched_items:
        ranked = sorted(((_catalog_score(cat, item), cat) for cat in catalog if isinstance(cat, dict)), key=lambda pair: pair[0], reverse=True)
        if not ranked or ranked[0][0] < 180:
            item["catalog_match"] = None; continue
        score, cat = ranked[0]
        item["catalog_match"] = {"name": str(cat.get("name") or ""), "code": str(cat.get("code") or ""), "unit": str(cat.get("unit") or ""), "score": score, "semantic_safe": True}
        if item["key"] not in applied:
            actions.append({"type": "catalog_add", "target": "", "value": str(cat.get("code") or cat.get("name") or item["label"]), "count": 1, "scope_key": item["key"], "quantity": item["quantity"], "unit": item["unit"], "label": item["label"]})
            applied.add(item["key"])
    return matched_items, actions, applied
'''
    text = text[:start] + replacement + text[end:]
    if MARKER not in text:
        text = f"# {MARKER}\n" + text
    write(rel, text)


def patch_authoritative_catalog() -> None:
    rel = "erp/ai_scope_catalog.py"
    text = read(rel)
    text = re.sub(
        r"from erp\.services\.(?:bo_direct_search|org_price_search) import [^\n]+",
        '''try:
    from erp.services.org_price_search import search_org_prices as _search_prices, serialize_org_price as _serialize_price
except ImportError:
    from erp.services.bo_direct_search import search_bo_prices as _search_prices, serialize_bo_price as _serialize_price''',
        text,
        count=1,
    )
    if "_search_prices" not in text:
        raise RuntimeError("authoritative catalog price-service import anchor changed")
    planner_import = "from erp.ai_scope_planner import catalog_semantic_match\n"
    if planner_import not in text:
        anchor = "from typing import Any\n"
        if anchor not in text:
            raise RuntimeError("authoritative catalog planner import anchor changed")
        text = text.replace(anchor, anchor + "\n" + planner_import, 1)
    start = text.find("def _candidate_score(")
    end = text.find("\ndef _can_see_prices(", start)
    if start < 0 or end < 0:
        raise RuntimeError("authoritative catalog matcher block changed")
    replacement = r'''def _candidate_score(row, scope_item: dict[str, Any]) -> int:
    payload = {"code": str(getattr(row, "code", "") or ""), "name": str(getattr(row, "description", "") or ""), "description": str(getattr(row, "description", "") or ""), "unit": str(getattr(row, "unit", "") or "")}
    if not catalog_semantic_match(scope_item, payload): return 0
    description, target = _norm(payload["description"]), _norm(scope_item.get("label") or "")
    terms = [_norm(term) for term in (scope_item.get("catalog_terms") or []) if _norm(term)]
    score = 180
    if target and target in description: score += 180
    words = {token for token in target.split() if len(token) > 2}
    score += 30 * sum(1 for token in words if token in description)
    for term in terms:
        if term in description: score += 140
        t_words = {token for token in term.split() if len(token) > 2}
        score += 20 * sum(1 for token in t_words if token in description)
    return score


def _best_price_row(organization, scope_item: dict[str, Any]):
    candidates = {}
    queries = list(scope_item.get("catalog_terms") or []) + [scope_item.get("label") or ""]
    for query in queries[:6]:
        query = str(query or "").strip()
        if len(query) < 2: continue
        for row in _search_prices(organization, query, limit=12): candidates[row.pk] = row
    if not candidates: return None
    ranked = sorted(candidates.values(), key=lambda row: (_candidate_score(row, scope_item), -len(str(getattr(row, "description", "") or ""))), reverse=True)
    best = ranked[0]
    return best if _candidate_score(best, scope_item) >= 180 else None

'''
    text = text[:start] + replacement + text[end:]
    text = re.sub(r"_best_(?:bo|org_price)_row\(organization, item\)", "_best_price_row(organization, item)", text)
    text = re.sub(r"(?:serialize_bo_price|serialize_org_price)\(row\)", "_serialize_price(row)", text)
    old_skip = '        if item.get("catalog_match") or key in existing_keys:\n            continue\n'
    new_skip = '''        visible_match = item.get("catalog_match")
        if (isinstance(visible_match, dict) and visible_match.get("semantic_safe")) or key in existing_keys:
            continue
'''
    if new_skip not in text:
        if old_skip in text: text = text.replace(old_skip, new_skip, 1)
        elif "semantic_safe" not in text: raise RuntimeError("authoritative catalog skip anchor changed")
    if MARKER not in text:
        text = f"# {MARKER}\n" + text
    write(rel, text)


def patch_field_authorization_backend() -> None:
    rel = "erp/field_authorization_views.py"
    text = read(rel)
    if "class _AppointmentScopeSession:" not in text:
        anchor = "\n\n@login_required\n@require_POST\ndef authorization_ai(request, pk):\n"
        if anchor not in text:
            raise RuntimeError("field authorization AI anchor changed")
        helper = r'''

class _AppointmentScopeSession:
    def __init__(self, session, event_id: int):
        from .ai_scope_planner import STATE_KEY
        self.session = session
        self.state_key = f"{STATE_KEY}:appointment:{event_id}"
    def get(self, key, default=None):
        from .ai_scope_planner import STATE_KEY
        return self.session.get(self.state_key if key == STATE_KEY else key, default)
    def __setitem__(self, key, value):
        from .ai_scope_planner import STATE_KEY
        self.session[self.state_key if key == STATE_KEY else key] = value
    def pop(self, key, default=None):
        from .ai_scope_planner import STATE_KEY
        return self.session.pop(self.state_key if key == STATE_KEY else key, default)
    @property
    def modified(self): return bool(getattr(self.session, "modified", False))
    @modified.setter
    def modified(self, value):
        try: self.session.modified = bool(value)
        except Exception: pass


def _scope_catalog_candidate(org, scope_item):
    from .ai_scope_planner import _catalog_score, catalog_semantic_match
    terms = list(scope_item.get("catalog_terms") or []) + [scope_item.get("label") or ""]
    tokens, seen = [], set()
    for term in terms:
        for token in re.findall(r"[A-Za-zÄÖÜäöüß]{4,}", str(term or "")):
            folded = token.casefold()
            if folded not in seen: seen.add(folded); tokens.append(token)
    condition = Q()
    for token in tokens[:10]:
        condition |= Q(code__icontains=token) | Q(name__icontains=token) | Q(description__icontains=token)
    if not condition: return None
    candidates = list(m.CatalogItem.objects.filter(organization=org, active=True).filter(condition).order_by("name")[:120])
    ranked = []
    for candidate in candidates:
        payload = {"code": candidate.code, "name": candidate.name, "description": candidate.description, "unit": candidate.unit}
        if catalog_semantic_match(scope_item, payload): ranked.append((_catalog_score(payload, scope_item), candidate))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] >= 180 else None


def _scope_authorization_items(org, scope_items):
    rows, price_fn = [], globals().get("effective_price_for_catalog_item")
    for scope_item in scope_items or []:
        if not isinstance(scope_item, dict): continue
        catalog = _scope_catalog_candidate(org, scope_item)
        price = Decimal("0.00")
        if catalog is not None:
            try:
                raw_price = price_fn(org, catalog) if callable(price_fn) else getattr(catalog, "sales_price", None)
                price = Decimal(str(raw_price or "0"))
            except Exception: price = Decimal("0.00")
        quantity = scope_item.get("quantity")
        rows.append({
            "description": scope_item.get("label") or "",
            "quantity": "" if quantity is None else str(quantity),
            "unit": scope_item.get("unit") or (catalog.unit if catalog else "Stk."),
            "unit_price": str(price if price > Decimal("0") else Decimal("0.00")),
            "tax_rate": str((catalog.tax_rate if catalog else Decimal("19.00")) or Decimal("19.00")),
            "catalog_id": catalog.pk if catalog is not None and price > Decimal("0") else None,
            "catalog_name": catalog.name if catalog is not None and price > Decimal("0") else None,
            "scope_key": scope_item.get("key") or "",
            "catalog_safe": bool(catalog is not None and price > Decimal("0")),
        })
    return rows


def _scope_text(scope_items):
    lines = []
    for item in scope_items or []:
        if isinstance(item, dict): lines.append(f"{item.get('label') or 'Leistung'} – {item.get('quantity_display') or 'offen'} {item.get('unit') or ''}".strip())
    return "\n".join(lines)


'''
        text = text.replace(anchor, helper + anchor, 1)
    start = text.find("@login_required\n@require_POST\ndef authorization_ai(request, pk):")
    end = text.find("\n\n@login_required\n@require_POST\ndef complete_job(", start)
    if start < 0 or end < 0:
        raise RuntimeError("field authorization AI function block changed")
    block = text[start:end]
    needle = '    fallback = {"issue": raw, "scope": raw, "items": [], "ai": False}\n'
    if '"mode": "scope"' not in block:
        if needle not in block:
            raise RuntimeError("field authorization AI fallback anchor changed")
        deterministic = r'''    from .ai_scope_planner import plan_scope_message
    scoped_session = _AppointmentScopeSession(request.session, event.pk)
    scope_plan = plan_scope_message(raw, scoped_session, [])
    if scope_plan is not None:
        scope_items = scope_plan.get("scope_items") or []
        return JsonResponse({
            "ok": True, "mode": "scope", "issue": raw, "scope": _scope_text(scope_items),
            "items": _scope_authorization_items(org, scope_items), "ai": True,
            "reply": scope_plan.get("reply") or "", "scope_question": scope_plan.get("scope_question") or "",
            "scope_complete": bool(scope_plan.get("scope_complete")), "scope_kind": scope_plan.get("scope_kind") or "",
            "scope_items": scope_items,
        })
'''
        block = block.replace(needle, deterministic + needle, 1)
        text = text[:start] + block + text[end:]
    if MARKER not in text:
        text = f"# {MARKER}\n" + text
    write(rel, text)


def patch_field_authorization_ui() -> None:
    rel = "templates/rebuild/appointment_detail.html"
    text = read(rel)
    if "data-auth-scope-planner" not in text:
        anchor = '      <div class="fa-block"><div class="fa-block-head"><div><b>Freizugebender Leistungsumfang</b>'
        if anchor not in text:
            raise RuntimeError("appointment scope UI anchor changed")
        block = r'''      <div class="fa-block fa-ai-scope-planner" data-auth-scope-planner data-auth-scope-url="{% url 'field-authorization-ai' event.pk %}">
        <div class="fa-block-head"><div><b>KI-Leistungsplanung</b><small>Gleiche Fachlogik wie die A+Bau KI oben: Mengen berechnen, Pflichtpositionen ergänzen und fehlende Angaben einzeln abfragen.</small></div></div>
        <div class="fa-ai-scope-chat" data-auth-scope-chat aria-live="polite"><div class="fa-ai-scope-msg is-ai">Beschreibe den Auftrag, z. B. „90 qm Wohnung, alle Wände streichen und Boden abdecken“. Ich frage fehlende Angaben nacheinander ab.</div></div>
        <div class="fa-ai-scope-compose"><textarea class="nx-control" rows="2" data-auth-scope-input placeholder="Auftrag oder Antwort auf die nächste Frage …"></textarea><button class="nx-btn nx-btn-primary" type="button" data-auth-scope-send>✦ Auswerten</button></div>
        <small class="fa-ai-scope-note">Keine unsichere Katalogposition wird automatisch übernommen. Bei unklarem Treffer bleibt der Preis offen.</small>
      </div>

'''
        text = text.replace(anchor, block + anchor, 1)
    write(rel, text)

    js_rel = "static/js/field-authorization.js"
    js = read(js_rel)
    if "function bindAuthorizationScopePlanner(form)" not in js:
        anchor = "\n  function bindAuthorization() {\n"
        if anchor not in js:
            raise RuntimeError("field JS scope planner anchor changed")
        helper = r'''

  function bindAuthorizationScopePlanner(form) {
    const box = $('[data-auth-scope-planner]', form); if (!box) return;
    const url = box.dataset.authScopeUrl, input = $('[data-auth-scope-input]', box), sendButton = $('[data-auth-scope-send]', box), chat = $('[data-auth-scope-chat]', box), scopeTarget = $('[data-scope-target]', form);
    const addMessage = (text, role = 'ai') => { if (!chat || !String(text || '').trim()) return; const node = document.createElement('div'); node.className = `fa-ai-scope-msg is-${role}`; node.textContent = String(text || '').trim(); chat.appendChild(node); chat.scrollTop = chat.scrollHeight; };
    const renderItems = (items) => { if (!chat || !Array.isArray(items) || !items.length) return; const card = document.createElement('div'); card.className = 'fa-ai-scope-items'; items.forEach((item) => { const row = document.createElement('div'); row.className = 'fa-ai-scope-item'; const label = document.createElement('span'); label.textContent = item.label || 'Leistung'; const qty = document.createElement('b'); qty.textContent = `${item.quantity_display || 'offen'} ${item.unit || ''}`.trim(); row.append(label, qty); card.appendChild(row); }); chat.appendChild(card); chat.scrollTop = chat.scrollHeight; };
    const run = async () => {
      const message = String(input?.value || '').trim(); if (!message || !url || sendButton.disabled) return;
      addMessage(message, 'user'); input.value = ''; sendButton.disabled = true; const old = sendButton.textContent; sendButton.textContent = '✦ Prüft …';
      try {
        const fd = new FormData(); fd.append('text', message);
        const res = await fetch(url, {method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf(form)},body:fd});
        const data = await res.json().catch(() => ({})); if (!res.ok || !data.ok) throw new Error(data.error || 'KI-Leistungsplanung nicht erreichbar.');
        if (data.mode === 'scope') {
          addMessage(data.reply || data.scope_question || 'Leistungsansatz aktualisiert.', 'ai'); renderItems(data.scope_items || []); if (scopeTarget) scopeTarget.value = data.scope || ''; form._appendPriceItems?.(data.items || []);
          const unresolved = (data.items || []).filter((item) => !item.catalog_safe).length; if (unresolved) addMessage(`${unresolved} Position(en) haben keinen sicheren Katalogtreffer; der Preis bleibt dort bewusst offen.`, 'ai');
          toast(data.scope_complete ? 'Leistungsplanung vollständig.' : 'Leistungsplanung aktualisiert – nächste Frage beantworten.', 'success');
        } else { addMessage(data.reply || 'Text strukturiert.', 'ai'); if (scopeTarget) scopeTarget.value = data.scope || scopeTarget.value; if (Array.isArray(data.items) && data.items.length) form._appendPriceItems?.(data.items); }
      } catch (err) { addMessage(err.message || 'KI-Leistungsplanung fehlgeschlagen.', 'ai'); toast(err.message || 'KI-Leistungsplanung fehlgeschlagen.', 'error'); }
      finally { sendButton.disabled = false; sendButton.textContent = old; input?.focus(); }
    };
    sendButton?.addEventListener('click', run); input?.addEventListener('keydown', (event) => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); run(); } });
  }
'''
        js = js.replace(anchor, helper + anchor, 1)
    bind_anchor = "    bindPricing(form);\n"
    bind_new = "    bindPricing(form);\n    bindAuthorizationScopePlanner(form);\n"
    if bind_new not in js:
        if bind_anchor not in js:
            raise RuntimeError("field JS scope binding anchor changed")
        js = js.replace(bind_anchor, bind_new, 1)
    old_handler = "issue.value = data.issue || text; $('[data-scope-target]', form).value = data.scope || ''; form._appendPriceItems?.(data.items || []); toast(data.ai ? 'Diktat strukturiert; Katalogpreise wurden nur bei echten Treffern übernommen.' : 'Text übernommen. Preise bitte manuell ergänzen.', 'success');"
    new_handler = "if (data.mode !== 'scope') issue.value = data.issue || text; $('[data-scope-target]', form).value = data.scope || ''; form._appendPriceItems?.(data.items || []); const scopeChat = $('[data-auth-scope-chat]', form); if (data.mode === 'scope' && scopeChat) { const msg = document.createElement('div'); msg.className = 'fa-ai-scope-msg is-ai'; msg.textContent = data.reply || data.scope_question || 'Leistungsansatz aktualisiert.'; scopeChat.appendChild(msg); } toast(data.mode === 'scope' ? (data.scope_complete ? 'Leistungsplanung vollständig.' : 'Leistungsplanung aktualisiert.') : (data.ai ? 'Diktat strukturiert; Katalogpreise wurden nur bei echten Treffern übernommen.' : 'Text übernommen. Preise bitte manuell ergänzen.'), 'success');"
    if new_handler not in js and old_handler in js: js = js.replace(old_handler, new_handler, 1)
    if MARKER not in js: js = js.replace("(() => {", f"(() => {{\n  // {MARKER}", 1)
    write(js_rel, js)

    css_rel = "static/css/field-authorization.css"
    css = read(css_rel)
    if ".fa-ai-scope-planner" not in css:
        css += r'''

/* A+Bau shared KI scope planning inside appointment authorization */
.fa-ai-scope-planner{border-color:rgba(173,137,43,.35)!important;background:linear-gradient(180deg,rgba(255,250,235,.72),rgba(255,255,255,.96))}
.fa-ai-scope-chat{display:grid;gap:8px;max-height:330px;overflow:auto;margin:10px 0;padding:10px;border:1px solid #e5e0d3;border-radius:13px;background:#fff}
.fa-ai-scope-msg{max-width:92%;padding:9px 11px;border-radius:12px;font-size:13px;line-height:1.45;white-space:pre-wrap}.fa-ai-scope-msg.is-ai{justify-self:start;background:#f6f3ea;border:1px solid #e8e0ca}.fa-ai-scope-msg.is-user{justify-self:end;background:#20282d;color:#fff}
.fa-ai-scope-compose{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:end}.fa-ai-scope-compose textarea{resize:vertical;min-height:58px}.fa-ai-scope-note{display:block;margin-top:7px;color:#6f7375}
.fa-ai-scope-items{display:grid;gap:5px;padding:7px 0}.fa-ai-scope-item{display:flex;justify-content:space-between;gap:12px;padding:7px 8px;border-top:1px solid #eee9dd;font-size:12px}.fa-ai-scope-item:first-child{border-top:0}.fa-ai-scope-item b{white-space:nowrap}
@media(max-width:650px){.fa-ai-scope-compose{grid-template-columns:1fr}.fa-ai-scope-compose .nx-btn{width:100%}}
'''
    write(css_rel, css)


def install_tests() -> None:
    write("tests/test_ab_bau_scope_engine_completion.py", r'''from pathlib import Path
from django.test import SimpleTestCase
from erp.ai_scope_planner import catalog_semantic_match, plan_scope_message

class Session(dict): modified = False

class ScopeEngineCompletionTests(SimpleTestCase):
    def test_abgedeckt_triggers_floor_cover_and_occupied_question(self):
        session = Session(); result = plan_scope_message("Wir haben eine Wohnung mit 90 qm. Alle Wände müssen gestrichen werden und der Boden muss abgedeckt werden.", session, [])
        by_key = {item["key"]: item for item in result["scope_items"]}; self.assertEqual(by_key["paint.wall.primer"]["quantity_display"], "225"); self.assertEqual(by_key["protect.floor"]["quantity_display"], "90")
        result = plan_scope_message("Ja, der Untergrund ist geeignet.", session, []); self.assertIn("bewohnt", result["scope_question"])
    def test_off_order_occupied_fact_is_kept_in_scope(self):
        session = Session(); plan_scope_message("90 qm Wohnung, alle Wände streichen", session, []); plan_scope_message("ja", session, []); result = plan_scope_message("Ja, die Wohnung ist bewohnt und möbliert.", session, [])
        self.assertIsNotNone(result); state = session["ab_bau_scope_planner_v1"]; self.assertTrue(state["facts"]["occupied"]); self.assertNotIn("door_count", state["facts"])
    def test_furniture_number_never_becomes_door_number(self):
        session = Session(); plan_scope_message("90 qm Wohnung, alle Wände streichen, Untergrund geeignet", session, []); result = plan_scope_message("12 Möbelstücke", session, [])
        self.assertIsNotNone(result); state = session["ab_bau_scope_planner_v1"]; self.assertEqual(state["facts"]["furniture_count"], 12); self.assertNotEqual(state["facts"].get("door_count"), 12)
    def test_semantic_counts_doors_and_windows(self):
        session = Session(); plan_scope_message("60 qm Wohnung, Wände streichen, Untergrund geeignet", session, []); plan_scope_message("3 Türen", session, []); self.assertEqual(session["ab_bau_scope_planner_v1"]["facts"]["door_count"], 3); plan_scope_message("4 Fenster", session, []); self.assertEqual(session["ab_bau_scope_planner_v1"]["facts"]["window_count"], 4)
    def test_natural_damage_phrase_is_recognized(self):
        session = Session(); plan_scope_message("60 qm Wohnung, Wände streichen, Untergrund geeignet, 2 Türen, 3 Fenster", session, []); result = plan_scope_message("Ja, es gibt bereits Schäden an Türen und Möbeln.", session, []); self.assertTrue(session["ab_bau_scope_planner_v1"]["facts"]["damage_present"]); self.assertTrue(any(item["key"] == "documentation.damage" for item in result["scope_items"]))
    def test_bad_catalog_examples_are_rejected(self):
        cases = [
            ({"key":"paint.wall.coat","unit":"m²"}, {"name":"Buntsteinputz, ca. 2 mm, Wände; Zwischenbeschichtung mit Dispersionsfarbe","unit":"m²"}),
            ({"key":"paint.ceiling.coat","unit":"m²"}, {"name":"Tapeten entfernen Decke","unit":"m²"}),
            ({"key":"bath.walltile.install","unit":"m²"}, {"name":"Brandschutz Dämmwolle ums Fallrohr verlegen","unit":"m²"}),
            ({"key":"bath.floor.seal","unit":"m²"}, {"name":"Abbruch und Entsorgung vorhandene Parkettböden","unit":"m²"}),]
        for scope, candidate in cases: self.assertFalse(catalog_semantic_match(scope, candidate), (scope, candidate))
    def test_good_catalog_examples_are_accepted(self):
        cases = [
            ({"key":"paint.wall.primer","unit":"m²"}, {"name":"Wandflächen einmal lösemittelfrei grundieren","unit":"m²"}),
            ({"key":"paint.wall.coat","unit":"m²"}, {"name":"Wandflächen mit Dispersionsfarbe zweimal streichen","unit":"m²"}),
            ({"key":"bath.floor.seal","unit":"m²"}, {"name":"Boden im Bad mit Verbundabdichtung abdichten","unit":"m²"}),]
        for scope, candidate in cases: self.assertTrue(catalog_semantic_match(scope, candidate), (scope, candidate))
    def test_appointment_ui_uses_shared_scope_engine(self):
        template = Path("templates/rebuild/appointment_detail.html").read_text(encoding="utf-8"); views = Path("erp/field_authorization_views.py").read_text(encoding="utf-8"); js = Path("static/js/field-authorization.js").read_text(encoding="utf-8")
        self.assertIn("data-auth-scope-planner", template); self.assertIn("_AppointmentScopeSession", views); self.assertIn("plan_scope_message(raw, scoped_session, [])", views); self.assertIn('"mode": "scope"', views); self.assertIn("bindAuthorizationScopePlanner", js)
    def test_appointment_scope_state_is_isolated_from_global_state(self):
        views = Path("erp/field_authorization_views.py").read_text(encoding="utf-8"); self.assertIn('f"{STATE_KEY}:appointment:{event_id}"', views)
''')
    write("tests/test_ai_scope_authoritative_catalog_safety.py", r'''from django.test import SimpleTestCase
from erp.ai_scope_planner import catalog_semantic_match
class AuthoritativeCatalogSafetyContractTests(SimpleTestCase):
    def test_known_false_positive_descriptions_fail_semantic_gate(self):
        self.assertFalse(catalog_semantic_match({"key":"bath.floor.seal","unit":"m²"}, {"description":"Abbruch und Entsorgung vorhandene Parkettböden","unit":"m²"}))
        self.assertFalse(catalog_semantic_match({"key":"bath.walltile.install","unit":"m²"}, {"description":"Brandschutz Dämmwolle ums Fallrohr verlegen","unit":"m²"}))
''')


def bump_cache_and_guard() -> None:
    rel = "templates/rebuild/appointment_detail.html"
    text = read(rel)
    text = re.sub(r"(field-authorization\.(?:css|js)' %}\?v=)[^\"'<\s]+", rf"\g<1>{VERSION}", text)
    write(rel, text)
    checks = {
        "erp/ai_scope_planner.py": [MARKER, "abgedeckt", "_semantic_count_answer", "_looks_like_scope_fact", "catalog_semantic_match", "semantic_safe"],
        "erp/ai_scope_catalog.py": [MARKER, "catalog_semantic_match", "_best_price_row", "_search_prices"],
        "erp/assistant_views.py": ["plan_scope_message(message, request.session", "enrich_scope_with_authoritative_catalog"],
        "erp/field_authorization_views.py": [MARKER, "_AppointmentScopeSession", "_scope_authorization_items", '"mode": "scope"', "plan_scope_message(raw, scoped_session, [])"],
        "templates/rebuild/appointment_detail.html": ["data-auth-scope-planner", "KI-Leistungsplanung", VERSION],
        "static/js/field-authorization.js": [MARKER, "bindAuthorizationScopePlanner", "data-auth-scope"],
        "tests/test_ab_bau_scope_engine_completion.py": ["test_abgedeckt_triggers_floor_cover", "test_bad_catalog_examples_are_rejected", "test_appointment_ui_uses_shared_scope_engine"],
    }
    missing = []
    for rel, needles in checks.items():
        content = read(rel)
        for needle in needles:
            if needle not in content: missing.append(f"{rel}: {needle}")
    if missing: raise RuntimeError("A+Bau scope completion guard failed: " + "; ".join(missing))


def main() -> None:
    ensure_scope_runtime()
    patch_planner()
    patch_authoritative_catalog()
    patch_field_authorization_backend()
    patch_field_authorization_ui()
    install_tests()
    bump_cache_and_guard()
    print("A+Bau shared scope engine completed: natural German variants, semantic follow-ups, safe catalog matching, and appointment KI now use one deterministic planning flow.")


if __name__ == "__main__":
    main()
