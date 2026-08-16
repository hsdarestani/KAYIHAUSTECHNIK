from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

STATE_KEY = "ab_bau_scope_planner_v1"
WALL_AREA_FACTOR = Decimal("2.5")

YES = {"ja", "j", "yes", "y", "richtig", "stimmt", "vorhanden", "machen", "neu", "erneuern"}
NO = {"nein", "n", "no", "nicht", "keine", "kein", "ohne", "bleibt", "erhalten"}
CANCEL = {"abbrechen", "abbruch", "reset", "zurucksetzen", "zurücksetzen", "neues thema", "stop"}

PAINT_WORDS = ("streichen", "gestrichen", "streicht", "anstrich", "anstreichen", "malern", "malen", "dispersionsfarbe", "farbe")
WALL_WORDS = ("wand", "wande", "wände", "waende", "alle wande", "alle wände", "wandflache", "wandfläche")
CEILING_WORDS = ("decke", "decken", "deckenflache", "deckenfläche")
FLOOR_WORDS = ("boden", "fussboden", "fußboden", "untergrund")
COVER_WORDS = ("abdecken", "abdeckung", "schutzen", "schützen", "abkleben")
BATH_WORDS = ("bad", "badezimmer", "komplettbad", "nassraum")
BATH_RENOVATION_WORDS = ("sanieren", "sanierung", "renovieren", "renovierung", "neues bad", "neu machen", "komplett erneuern")

QUESTION_TEXT = {
    "paint_surfaces": "Welche Flächen sollen gestrichen werden: Wände, Decken oder beides?",
    "floor_area": "Wie groß ist die Wohn-/Grundfläche in m²?",
    "substrate_suitable": "Sind alle zu streichenden Untergründe tragfähig, glatt und direkt für Grundierung und Anstrich geeignet?",
    "wallpaper": "Sind Tapeten vorhanden, die vor den Malerarbeiten entfernt werden müssen?",
    "occupied": "Ist die Wohnung während der Arbeiten bewohnt bzw. möbliert?",
    "furniture_count": "Wie viele Möbel/Gegenstände müssen geschützt werden? Bitte als Stückzahl angeben.",
    "moving_hours": "Wie viele Stunden Umräumarbeiten sollen dafür ungefähr angesetzt werden?",
    "door_count": "Wie viele Türen sind vorhanden, die abgeklebt bzw. geschützt werden müssen?",
    "window_count": "Wie viele Fenster sind vorhanden, die abgeklebt bzw. geschützt werden müssen?",
    "damage_present": "Gibt es bereits Schäden an Türen, Möbeln oder anderen Bauteilen, die vor Arbeitsbeginn dokumentiert werden müssen?",
    "bath_floor_area": "Wie groß ist die Bodenfläche des Badezimmers in m²? Wenn noch kein Aufmaß vorliegt, antworte mit „offen“.",
    "bath_wall_area": "Wie groß ist die zu bearbeitende Wand-/Wandfliesenfläche in m²? Wenn sie noch nicht feststeht, antworte mit „offen“.",
    "water_lines_change": "Sollen Kalt-/Warmwasserleitungen umgebaut bzw. neu hergestellt werden, oder bleiben die vorhandenen Leitungen bestehen?",
    "water_line_length": "Wie viele laufende Meter Kalt-/Warmwasserleitung sollen ungefähr neu hergestellt werden? Wenn noch offen, antworte mit „offen“.",
    "sink_replace": "Soll das Waschbecken erneuert werden?",
    "wc_replace": "Soll das WC erneuert werden?",
    "bath_shower_replace": "Soll eine Badewanne oder Dusche erneuert werden? Antworte z. B. mit „Badewanne“, „Dusche“ oder „nein“.",
}

def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ß", "ss")
    return re.sub(r"\s+", " ", text).strip()

def _number(value: str) -> Decimal | None:
    raw = str(value or "").strip().replace(" ", "").replace(",", ".")
    try:
        number = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if number < 0:
        return None
    return number

def _fmt(value: Decimal | int | float | None) -> str:
    if value is None:
        return "offen"
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    d = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if d == d.to_integral():
        return str(int(d))
    return format(d.normalize(), "f").replace(".", ",")

def _contains(text: str, words: tuple[str, ...] | list[str]) -> bool:
    normalized = _norm(text)
    return any(_norm(word) in normalized for word in words)

def _extract_measure(text: str, subjects: tuple[str, ...]) -> Decimal | None:
    n = _norm(text)
    subject = "(?:" + "|".join(re.escape(_norm(s)) for s in subjects) + ")"
    unit = r"(?:m2|m²|qm|quadratmeter)"
    patterns = (
        rf"{subject}[^0-9]{{0,35}}(\d+(?:[.,]\d+)?)\s*{unit}",
        rf"(\d+(?:[.,]\d+)?)\s*{unit}[^.;,\n]{{0,35}}{subject}",
    )
    for pattern in patterns:
        match = re.search(pattern, n, flags=re.I)
        if match:
            return _number(match.group(1))
    return None

def _extract_general_area(text: str) -> Decimal | None:
    n = _norm(text)
    patterns = (
        r"(?:wohnflache|grundflache|wohnung|flache|apartment|haus)[^0-9]{0,40}(\d+(?:[.,]\d+)?)\s*(?:m2|m²|qm|quadratmeter)",
        r"(\d+(?:[.,]\d+)?)\s*(?:m2|m²|qm|quadratmeter)[^.;,\n]{0,35}(?:wohnflache|grundflache|wohnung|flache|apartment|haus)",
        r"(?:wohnung|apartment|haus)\s+(?:mit\s+)?(?:der\s+)?(?:flache\s+von\s+)?(\d+(?:[.,]\d+)?)\s*(?:m2|m²|qm|quadratmeter)",
    )
    for pattern in patterns:
        match = re.search(pattern, n, flags=re.I)
        if match:
            return _number(match.group(1))
    areas = re.findall(r"(\d+(?:[.,]\d+)?)\s*(?:m2|m²|qm|quadratmeter)", n)
    if len(areas) == 1 and _contains(n, ("wohnung", "apartment", "haus", "bad", "badezimmer", "raum")):
        return _number(areas[0])
    return None

def _extract_count(text: str, nouns: tuple[str, ...]) -> int | None:
    n = _norm(text)
    noun = "(?:" + "|".join(re.escape(_norm(x)) for x in nouns) + ")"
    for pattern in (rf"(\d+)\s*{noun}", rf"{noun}[^0-9]{{0,20}}(\d+)"):
        match = re.search(pattern, n)
        if match:
            return int(match.group(1))
    return None

def _answer_yes_no(text: str) -> bool | None:
    tokens = set(re.findall(r"[a-z0-9]+", _norm(text)))
    if tokens & {"nein", "no", "keine", "kein", "nicht", "ohne"}:
        return False
    if tokens & {"ja", "yes", "j", "vorhanden"}:
        return True
    return None

def _new_state(kind: str) -> dict[str, Any]:
    return {"kind": kind, "facts": {}, "flags": {}, "pending": "", "catalog_applied": [], "turn": 0}

def _detect_kind(text: str) -> str:
    n = _norm(text)
    bathroom = _contains(n, BATH_WORDS) and _contains(n, BATH_RENOVATION_WORDS)
    bathroom = bathroom or (_contains(n, ("wandfliesen", "bodenfliesen")) and _contains(n, ("abbrechen", "entfernen", "herstellen", "verfliesen", "fliesen")))
    painting = _contains(n, PAINT_WORDS) or (_contains(n, COVER_WORDS) and _contains(n, FLOOR_WORDS))
    if bathroom:
        return "bathroom"
    if painting:
        return "painting"
    return ""

def _read_explicit_facts(state: dict[str, Any], message: str) -> None:
    n = _norm(message)
    facts = state["facts"]
    flags = state["flags"]
    floor = _extract_general_area(message)
    explicit_wall = _extract_measure(message, ("wandfläche", "wandflache", "wandfläche gesamt", "wandflache gesamt"))
    explicit_ceiling = _extract_measure(message, ("deckenfläche", "deckenflache", "decke"))
    explicit_floor = _extract_measure(message, ("bodenfläche", "bodenflache", "fussboden", "fußboden"))
    if floor is not None:
        facts["floor_area"] = str(floor)
    if explicit_floor is not None:
        facts["floor_area"] = str(explicit_floor)
    if explicit_wall is not None:
        facts["wall_area"] = str(explicit_wall)
    if explicit_ceiling is not None:
        facts["ceiling_area"] = str(explicit_ceiling)
    if _contains(n, PAINT_WORDS):
        if _contains(n, WALL_WORDS) or "alle wande" in n:
            flags["paint_walls"] = True
        if _contains(n, CEILING_WORDS):
            flags["paint_ceiling"] = True
    if _contains(n, COVER_WORDS) and _contains(n, FLOOR_WORDS):
        flags["cover_floor"] = True
    if "unbewohnt" in n or "leersteh" in n or re.search(r"\bleer\b", n):
        facts["occupied"] = False
    elif "bewohnt" in n or "mobliert" in n or "möbliert" in message.casefold():
        facts["occupied"] = True
    door_count = _extract_count(message, ("tür", "türen", "tuer", "tueren"))
    window_count = _extract_count(message, ("fenster",))
    furniture_count = _extract_count(message, ("möbel", "moebel", "gegenstände", "gegenstande"))
    if door_count is not None:
        facts["door_count"] = door_count
    if window_count is not None:
        facts["window_count"] = window_count
    if furniture_count is not None:
        facts["furniture_count"] = furniture_count
    move = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:stunden|std\.?|h)\b[^.;,\n]{0,25}(?:umraum|umräum|mobel|möbel)", n)
    if not move:
        move = re.search(r"(?:umraum|umräum)[^0-9]{0,25}(\d+(?:[.,]\d+)?)\s*(?:stunden|std\.?|h)\b", n)
    if move:
        val = _number(move.group(1))
        if val is not None:
            facts["moving_hours"] = str(val)
    if "untergrund" in n and _contains(n, ("nicht geeignet", "ungeeignet", "schlecht", "spachteln", "ausbessern")):
        facts["substrate_suitable"] = False
    elif "untergrund" in n and _contains(n, ("geeignet", "tragfähig", "tragfahig", "glatt")) and "nicht" not in n:
        facts["substrate_suitable"] = True
    if "tapet" in n:
        if _contains(n, ("keine tapet", "ohne tapet", "nicht vorhanden")):
            facts["wallpaper"] = False
        elif _contains(n, ("entfernen", "ab", "vorhanden", "tapete", "tapeten")):
            facts["wallpaper"] = True
    if _contains(n, ("keine schaden", "keine schäden", "ohne schaden", "keine mängel", "keine mangel")):
        facts["damage_present"] = False
    elif _contains(n, ("schaden vorhanden", "schäden vorhanden", "vorschaden", "bestandschaden", "mangel vorhanden", "mängel vorhanden")):
        facts["damage_present"] = True
    if state["kind"] == "bathroom":
        bath_floor = _extract_measure(message, ("bad", "badezimmer", "bodenfläche", "bodenflache", "bodenfliesen"))
        bath_wall = _extract_measure(message, ("wandfläche", "wandflache", "wandfliesen", "wände", "waende"))
        if bath_floor is not None:
            facts["floor_area"] = str(bath_floor)
        if bath_wall is not None:
            facts["bath_wall_area"] = str(bath_wall)
        water_keep = _contains(n, ("leitungen bleiben", "leitung bleibt", "bestand erhalten", "alten leitungen erhalten", "wasserleitungen erhalten"))
        water_change = _contains(n, ("wasserleitungen umbauen", "leitungen umbauen", "leitungen neu", "wasserleitung neu", "leitungen versetzen", "neu herstellen"))
        if water_keep:
            facts["water_lines_change"] = False
        elif water_change:
            facts["water_lines_change"] = True
        lm = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:lfm|m)\b[^.;,\n]{0,35}(?:wasser|leitung)", n)
        if lm:
            val = _number(lm.group(1))
            if val is not None:
                facts["water_line_length"] = str(val)
        for key, words in {"sink_replace": ("waschbecken", "waschtisch"), "wc_replace": ("wc", "toilette")}.items():
            if _contains(n, words):
                if _contains(n, ("nicht erneuern", "nicht austauschen", "bleibt", "erhalten")):
                    facts[key] = False
                elif _contains(n, ("neu", "erneuern", "austauschen", "ersetzen")):
                    facts[key] = True
        if _contains(n, ("badewanne",)):
            if _contains(n, ("nicht erneuern", "bleibt", "erhalten")):
                facts["bath_shower_replace"] = False
            else:
                facts["bath_shower_replace"] = "Badewanne"
        elif _contains(n, ("dusche",)):
            if _contains(n, ("nicht erneuern", "bleibt", "erhalten")):
                facts["bath_shower_replace"] = False
            else:
                facts["bath_shower_replace"] = "Dusche"

def _apply_pending_answer(state: dict[str, Any], message: str) -> bool:
    pending = state.get("pending") or ""
    if not pending:
        return False
    n = _norm(message)
    facts = state["facts"]
    flags = state["flags"]
    if pending in {"floor_area", "bath_floor_area", "bath_wall_area"}:
        if n in {"offen", "unbekannt", "noch offen", "keine angabe"}:
            if pending == "bath_wall_area":
                facts["bath_wall_area"] = "open"
            else:
                facts["floor_area"] = "open"
            state["pending"] = ""
            return True
        match = re.search(r"(\d+(?:[.,]\d+)?)", n)
        if match:
            value = _number(match.group(1))
            if value is not None:
                if pending == "bath_wall_area":
                    facts["bath_wall_area"] = str(value)
                else:
                    facts["floor_area"] = str(value)
                state["pending"] = ""
                return True
        return False
    if pending == "paint_surfaces":
        walls = _contains(n, WALL_WORDS)
        ceiling = _contains(n, CEILING_WORDS)
        both = _contains(n, ("beides", "beide", "wände und decke", "wande und decke"))
        if walls or both:
            flags["paint_walls"] = True
        if ceiling or both:
            flags["paint_ceiling"] = True
        if walls or ceiling or both:
            state["pending"] = ""
            return True
        return False
    if pending in {"substrate_suitable", "wallpaper", "occupied", "damage_present", "water_lines_change", "sink_replace", "wc_replace"}:
        answer = _answer_yes_no(message)
        if pending == "water_lines_change":
            if _contains(n, ("bleiben", "erhalten", "bestand")):
                answer = False
            elif _contains(n, ("neu", "umbauen", "versetzen", "erneuern")):
                answer = True
        if answer is not None:
            facts[pending] = answer
            state["pending"] = ""
            return True
        return False
    if pending in {"furniture_count", "door_count", "window_count"}:
        match = re.search(r"\d+", n)
        if match:
            facts[pending] = int(match.group())
            state["pending"] = ""
            return True
        return False
    if pending in {"moving_hours", "water_line_length"}:
        if n in {"offen", "unbekannt", "noch offen"} and pending == "water_line_length":
            facts[pending] = "open"
            state["pending"] = ""
            return True
        match = re.search(r"(\d+(?:[.,]\d+)?)", n)
        if match:
            value = _number(match.group(1))
            if value is not None:
                facts[pending] = str(value)
                state["pending"] = ""
                return True
        return False
    if pending == "bath_shower_replace":
        if _contains(n, ("badewanne", "wanne")):
            facts[pending] = "Badewanne"
            state["pending"] = ""
            return True
        if _contains(n, ("dusche",)):
            facts[pending] = "Dusche"
            state["pending"] = ""
            return True
        answer = _answer_yes_no(message)
        if answer is False:
            facts[pending] = False
            state["pending"] = ""
            return True
        return False
    return False

def _area(facts: dict[str, Any], key: str) -> Decimal | None:
    value = facts.get(key)
    if value in {None, "", "open"}:
        return None
    return _number(str(value))

def _item(key: str, label: str, quantity: Decimal | int | float | None, unit: str, basis: str, *catalog_terms: str, status: str | None = None) -> dict[str, Any]:
    return {"key": key, "label": label, "quantity": None if quantity is None else float(quantity), "quantity_display": _fmt(quantity), "unit": unit, "basis": basis, "status": status or ("berechnet" if quantity is not None else "Menge offen"), "catalog_terms": list(catalog_terms) or [label]}

def _painting_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    facts = state["facts"]
    flags = state["flags"]
    floor_area = _area(facts, "floor_area")
    wall_area = _area(facts, "wall_area")
    ceiling_area = _area(facts, "ceiling_area")
    if wall_area is None and floor_area is not None and flags.get("paint_walls"):
        wall_area = floor_area * WALL_AREA_FACTOR
        wall_basis = f"{_fmt(floor_area)} m² Wohn-/Grundfläche × {_fmt(WALL_AREA_FACTOR)}"
    elif wall_area is not None:
        wall_basis = "explizit angegebene Wandfläche"
    else:
        wall_basis = "Wandaufmaß noch offen"
    if ceiling_area is None and floor_area is not None and flags.get("paint_ceiling"):
        ceiling_area = floor_area
        ceiling_basis = f"Deckenfläche = {_fmt(floor_area)} m² Grundfläche"
    elif ceiling_area is not None:
        ceiling_basis = "explizit angegebene Deckenfläche"
    else:
        ceiling_basis = "Deckenaufmaß noch offen"
    items: list[dict[str, Any]] = []
    if flags.get("paint_walls"):
        items += [_item("paint.wall.primer", "Grundierung Wände", wall_area, "m²", wall_basis, "Grundierung Wand", "Wände grundieren", "Grundieren Wand"), _item("paint.wall.coat", "Dispersionsfarbanstrich Wände", wall_area, "m²", wall_basis, "Dispersionsfarbe Wände", "Wandanstrich Dispersionsfarbe", "Wände streichen")]
    if flags.get("paint_ceiling"):
        items += [_item("paint.ceiling.primer", "Grundierung Decke", ceiling_area, "m²", ceiling_basis, "Grundierung Decke", "Decke grundieren"), _item("paint.ceiling.coat", "Dispersionsfarbanstrich Decke", ceiling_area, "m²", ceiling_basis, "Dispersionsfarbe Decke", "Deckenanstrich", "Decke streichen")]
    prep_area = (wall_area or Decimal("0")) + (ceiling_area or Decimal("0"))
    prep_value = prep_area if prep_area > 0 else None
    prep_basis_parts = []
    if wall_area:
        prep_basis_parts.append(f"Wände {_fmt(wall_area)} m²")
    if ceiling_area:
        prep_basis_parts.append(f"Decke {_fmt(ceiling_area)} m²")
    prep_basis = " + ".join(prep_basis_parts) or "zu bearbeitende Fläche nach Aufmaß"
    if facts.get("substrate_suitable") is False:
        items.append(_item("paint.substrate.fill", "Untergrund spachteln / ausbessern", prep_value, "m²", prep_basis, "Untergrund spachteln", "Spachtelarbeiten Untergrund"))
    if facts.get("wallpaper") is True and flags.get("paint_walls"):
        items.append(_item("paint.wallpaper.remove", "Tapete entfernen", wall_area, "m²", wall_basis, "Tapete entfernen", "Tapeten entfernen"))
    if flags.get("cover_floor"):
        items.append(_item("protect.floor", "Boden / Untergrund abdecken", floor_area, "m²", f"Grundfläche {_fmt(floor_area)} m²" if floor_area else "Grundfläche noch offen", "Boden abdecken", "Abdeckarbeiten Boden", "Untergrund abdecken"))
    if facts.get("occupied") is True:
        furniture = facts.get("furniture_count")
        moving = _area(facts, "moving_hours")
        items += [_item("protect.furniture", "Möbel / private Gegenstände schützen", furniture, "Stk", "bewohnter/möblierter Zustand", "Möbel schützen", "Mobiliar schützen"), _item("protect.moving", "Umräumarbeiten", moving, "h", "bewohnter/möblierter Zustand", "Umräumarbeiten", "Möbel umräumen"), _item("protect.difficulty", "Erschwerniszuschlag bewohnter Zustand", 1, "psch", "bewohnter/möblierter Zustand", "Erschwerniszuschlag", "Zuschlag bewohnte Wohnung")]
    if flags.get("paint_walls"):
        if "door_count" in facts:
            items.append(_item("protect.doors", "Türen abkleben / schützen", facts.get("door_count"), "Stk", "angegebene Türanzahl", "Türen abkleben", "Türen schützen"))
        if "window_count" in facts:
            items.append(_item("protect.windows", "Fenster abkleben / schützen", facts.get("window_count"), "Stk", "angegebene Fensteranzahl", "Fenster abkleben", "Fenster schützen"))
    if facts.get("damage_present") is True:
        items.append(_item("documentation.damage", "Bestands-/Schadendokumentation vor Arbeitsbeginn", 1, "psch", "Vorschäden vorhanden", "Schadendokumentation", "Bestandsdokumentation", status="Dokumentation erforderlich"))
    return items

def _bathroom_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    facts = state["facts"]
    floor = _area(facts, "floor_area")
    wall = _area(facts, "bath_wall_area")
    floor_basis = f"Badboden {_fmt(floor)} m²" if floor is not None else "Bodenaufmaß noch offen"
    wall_basis = f"Wandfläche {_fmt(wall)} m²" if wall is not None else "Wand-/Fliesenaufmaß noch offen"
    items = [_item("bath.walltile.demolish", "Wandfliesen abbrechen", wall, "m²", wall_basis, "Wandfliesen abbrechen", "Wandbelag abbrechen"), _item("bath.floortile.demolish", "Bodenfliesen abbrechen", floor, "m²", floor_basis, "Bodenfliesen abbrechen", "Bodenbelag Fliesen abbrechen"), _item("bath.substrate.fill", "Untergrund spachteln / vorbereiten", wall, "m²", wall_basis, "Untergrund spachteln", "Untergrund vorbereiten"), _item("bath.substrate.prime", "Untergrund grundieren", wall, "m²", wall_basis, "Grundieren", "Untergrund grundieren"), _item("bath.walltile.install", "Wandfliesen herstellen", wall, "m²", wall_basis, "Wandfliesen herstellen", "Wandfliesen verlegen"), _item("bath.floor.seal", "Boden abdichten", floor, "m²", floor_basis, "Boden abdichten", "Abdichtung Boden", "Verbundabdichtung"), _item("bath.floortile.install", "Bodenfliesen herstellen", floor, "m²", floor_basis, "Bodenfliesen herstellen", "Bodenfliesen verlegen")]
    if facts.get("water_lines_change") is True:
        length = _area(facts, "water_line_length")
        basis = f"Leitungslänge {_fmt(length)} m" if length else "Leitungslänge noch offen"
        items += [_item("bath.water.cold", "Kaltwasserleitung neu herstellen", length, "m", basis, "Kaltwasserleitung neu", "Kaltwasserleitung herstellen"), _item("bath.water.hot", "Warmwasserleitung neu herstellen", length, "m", basis, "Warmwasserleitung neu", "Warmwasserleitung herstellen")]
    if facts.get("sink_replace") is True:
        items.append(_item("bath.fixture.sink", "Waschbecken erneuern", 1, "Stk", "Sanitärobjekt erneuern", "Waschbecken erneuern", "Waschtisch erneuern"))
    if facts.get("wc_replace") is True:
        items.append(_item("bath.fixture.wc", "WC erneuern", 1, "Stk", "Sanitärobjekt erneuern", "WC erneuern", "Toilette erneuern"))
    bath_shower = facts.get("bath_shower_replace")
    if bath_shower in {"Badewanne", "Dusche"}:
        label = f"{bath_shower} erneuern"
        items.append(_item("bath.fixture.bath_shower", label, 1, "Stk", "Sanitärobjekt erneuern", label, f"{bath_shower} austauschen"))
    if facts.get("damage_present") is True:
        items.append(_item("documentation.damage", "Bestands-/Schadendokumentation vor Arbeitsbeginn", 1, "psch", "Vorschäden vorhanden", "Schadendokumentation", "Bestandsdokumentation", status="Dokumentation erforderlich"))
    return items

def _next_question(state: dict[str, Any]) -> str:
    facts = state["facts"]
    flags = state["flags"]
    kind = state["kind"]
    if kind == "painting":
        if not flags.get("paint_walls") and not flags.get("paint_ceiling") and _contains(state.get("seed", ""), PAINT_WORDS):
            return "paint_surfaces"
        needs_floor = ((flags.get("paint_walls") and "wall_area" not in facts) or (flags.get("paint_ceiling") and "ceiling_area" not in facts) or flags.get("cover_floor"))
        if needs_floor and "floor_area" not in facts:
            return "floor_area"
        if (flags.get("paint_walls") or flags.get("paint_ceiling")) and "substrate_suitable" not in facts:
            return "substrate_suitable"
        if facts.get("substrate_suitable") is False and flags.get("paint_walls") and "wallpaper" not in facts:
            return "wallpaper"
        if flags.get("cover_floor") and "occupied" not in facts:
            return "occupied"
        if facts.get("occupied") is True and "furniture_count" not in facts:
            return "furniture_count"
        if facts.get("occupied") is True and "moving_hours" not in facts:
            return "moving_hours"
        if flags.get("paint_walls") and "door_count" not in facts:
            return "door_count"
        if flags.get("paint_walls") and "window_count" not in facts:
            return "window_count"
        if (flags.get("paint_walls") or flags.get("paint_ceiling") or flags.get("cover_floor")) and "damage_present" not in facts:
            return "damage_present"
        return ""
    if kind == "bathroom":
        if "floor_area" not in facts:
            return "bath_floor_area"
        if "bath_wall_area" not in facts:
            return "bath_wall_area"
        if "water_lines_change" not in facts:
            return "water_lines_change"
        if facts.get("water_lines_change") is True and "water_line_length" not in facts:
            return "water_line_length"
        if "sink_replace" not in facts:
            return "sink_replace"
        if "wc_replace" not in facts:
            return "wc_replace"
        if "bath_shower_replace" not in facts:
            return "bath_shower_replace"
        if "damage_present" not in facts:
            return "damage_present"
        return ""
    return ""

def _catalog_score(catalog_item: dict[str, Any], terms: list[str]) -> int:
    candidate = _norm(f"{catalog_item.get('code','')} {catalog_item.get('name','')}")
    if not candidate:
        return 0
    best = 0
    for term in terms:
        q = _norm(term)
        if not q:
            continue
        if q in candidate:
            best = max(best, 100 + len(q))
            continue
        q_tokens = [t for t in q.split() if len(t) > 2]
        overlap = sum(1 for t in q_tokens if t in candidate)
        if q_tokens:
            best = max(best, int(80 * overlap / len(q_tokens)))
    return best

def _match_catalog(items: list[dict[str, Any]], catalog: list[dict[str, Any]], already: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    actions: list[dict[str, Any]] = []
    matched_items = deepcopy(items)
    applied = set(already)
    for item in matched_items:
        ranked = sorted(((_catalog_score(cat, item["catalog_terms"]), cat) for cat in catalog if isinstance(cat, dict)), key=lambda pair: pair[0], reverse=True)
        if not ranked or ranked[0][0] < 60:
            item["catalog_match"] = None
            continue
        score, cat = ranked[0]
        item["catalog_match"] = {"name": str(cat.get("name") or ""), "code": str(cat.get("code") or ""), "unit": str(cat.get("unit") or ""), "score": score}
        if item["key"] not in applied:
            actions.append({"type": "catalog_add", "target": "", "value": str(cat.get("code") or cat.get("name") or item["label"]), "count": 1, "scope_key": item["key"], "quantity": item["quantity"], "unit": item["unit"], "label": item["label"]})
            applied.add(item["key"])
    return matched_items, actions, applied

def _summary(state: dict[str, Any], items: list[dict[str, Any]], question: str) -> str:
    kind = state["kind"]
    facts = state["facts"]
    flags = state["flags"]
    parts: list[str] = []
    if kind == "painting":
        floor = _area(facts, "floor_area")
        if flags.get("paint_walls") and floor is not None and _area(facts, "wall_area") is None:
            parts.append(f"Wandfläche automatisch: {_fmt(floor)} m² × {_fmt(WALL_AREA_FACTOR)} = {_fmt(floor * WALL_AREA_FACTOR)} m².")
        if flags.get("paint_ceiling") and floor is not None and _area(facts, "ceiling_area") is None:
            parts.append(f"Deckenfläche automatisch: {_fmt(floor)} m².")
    elif kind == "bathroom":
        parts.append("Die erforderliche Grundfolge für die Badsanierung ist bereits als Leistungsansatz aufgenommen.")
    if question:
        parts.append(QUESTION_TEXT[question])
    else:
        parts.append("Der Leistungsansatz ist mit den bisher bekannten Angaben vollständig. Mengen mit „offen“ müssen vor Preisfreigabe noch aufgemessen werden.")
    return " ".join(parts)

def _looks_like_pending_answer(pending: str, text: str) -> bool:
    """Only keep a scope conversation when the new message can answer its question.

    This prevents an unfinished scope from hijacking unrelated assistant commands
    such as customer/project search. Users can still provide several relevant facts
    in one natural-language reply.
    """
    n = _norm(text)
    if not pending:
        return False
    if pending in {"floor_area", "bath_floor_area", "bath_wall_area", "furniture_count", "moving_hours", "door_count", "window_count", "water_line_length"}:
        return bool(re.search(r"\d", n)) or n in {"offen", "unbekannt", "noch offen", "keine angabe"}
    if pending == "paint_surfaces":
        return _contains(n, WALL_WORDS) or _contains(n, CEILING_WORDS) or _contains(n, ("beides", "beide"))
    if pending == "water_lines_change":
        return _answer_yes_no(text) is not None or _contains(n, ("leitung", "wasser", "bestand", "bleiben", "erhalten", "umbauen", "versetzen", "neu"))
    if pending == "bath_shower_replace":
        return _answer_yes_no(text) is not None or _contains(n, ("badewanne", "wanne", "dusche"))
    if pending in {"substrate_suitable", "wallpaper", "occupied", "damage_present", "sink_replace", "wc_replace"}:
        if _answer_yes_no(text) is not None:
            return True
        relevant = {
            "substrate_suitable": ("untergrund", "tragfähig", "tragfahig", "glatt", "spachteln", "ungeeignet"),
            "wallpaper": ("tapete", "tapeten"),
            "occupied": ("bewohnt", "unbewohnt", "möbliert", "mobliert", "leer"),
            "damage_present": ("schaden", "schäden", "mangel", "mängel", "vorschaden"),
            "sink_replace": ("waschbecken", "waschtisch"),
            "wc_replace": ("wc", "toilette"),
        }
        return _contains(n, relevant[pending])
    return False


def _starts_new_scope(state: dict[str, Any], detected: str, text: str) -> bool:
    if not detected or detected != state.get("kind") or state.get("pending"):
        return False
    n = _norm(text)
    if _contains(n, ("neue wohnung", "andere wohnung", "anderes objekt", "neues objekt", "neuer auftrag", "neues projekt")):
        return True
    incoming = _extract_general_area(text)
    existing = _area(state.get("facts") or {}, "floor_area")
    return incoming is not None and existing is not None and incoming != existing

def plan_scope_message(message: str, session: Any, catalog: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Return a deterministic trade-scope plan or None when the message is unrelated.

    The planner intentionally does not price or submit anything. It derives quantities,
    expands mandatory work dependencies, asks exactly one missing technical question at
    a time, and may select matching visible catalog positions as editable draft rows.
    """
    raw = str(message or "").strip()
    normalized = _norm(raw)
    if not raw:
        return None

    if any(cancel in normalized for cancel in CANCEL):
        try:
            session.pop(STATE_KEY, None)
            session.modified = True
        except Exception:
            pass
        return {"ok": True, "reply": "Leistungsplanung zurückgesetzt.", "actions": [], "results": [], "scope_items": [], "scope_complete": True}

    detected = _detect_kind(raw)
    state = deepcopy(session.get(STATE_KEY) or {}) if hasattr(session, "get") else {}
    active_kind = str(state.get("kind") or "")

    # Do not let a previous scope swallow unrelated assistant requests. A message
    # without a fresh trade intent is treated as a continuation only when it can
    # plausibly answer the one currently pending question.
    if active_kind and not detected:
        pending = str(state.get("pending") or "")
        if not pending or not _looks_like_pending_answer(pending, raw):
            return None

    if detected and (detected != active_kind or _starts_new_scope(state, detected, raw)):
        state = _new_state(detected)
        state["seed"] = raw[:1200]
    elif not active_kind:
        if not detected:
            return None
        state = _new_state(detected)
        state["seed"] = raw[:1200]

    state["turn"] = int(state.get("turn") or 0) + 1
    # A pending answer is consumed first; then the same message is also scanned for
    # additional explicit facts, so users may answer several questions at once.
    _apply_pending_answer(state, raw)
    _read_explicit_facts(state, raw)

    if state["kind"] == "painting":
        items = _painting_items(state)
    elif state["kind"] == "bathroom":
        items = _bathroom_items(state)
    else:
        return None

    question = _next_question(state)
    state["pending"] = question

    visible_catalog = [item for item in (catalog or []) if isinstance(item, dict)]
    already = set(state.get("catalog_applied") or [])
    items, actions, applied = _match_catalog(items, visible_catalog, already)
    state["catalog_applied"] = sorted(applied)

    try:
        session[STATE_KEY] = state
        session.modified = True
    except Exception:
        pass

    return {
        "ok": True,
        "reply": _summary(state, items, question),
        "actions": actions,
        "results": [],
        "scope_items": items,
        "scope_question": QUESTION_TEXT.get(question, ""),
        "scope_complete": not bool(question),
        "scope_kind": state["kind"],
    }
