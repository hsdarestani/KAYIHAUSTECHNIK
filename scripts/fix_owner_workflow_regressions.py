from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "erp" / "ai_scope_planner.py"
MARKER = "A+Bau final dimension-aware painting math 2026-08-16"

text = TARGET.read_text(encoding="utf-8")
if MARKER not in text:
    text += r'''

# A+Bau final dimension-aware painting math 2026-08-16
# This is intentionally defined last. The source is assembled from several legacy
# overlays; Python resolves these global names at call time, so the final definitions
# below are the authoritative calculation contract without duplicating the whole planner.
_AB_ORIGINAL_READ_EXPLICIT_FACTS = _read_explicit_facts
_AB_ORIGINAL_PAINTING_ITEMS = _painting_items
_AB_ORIGINAL_SUMMARY = _summary


def _ab_extract_linear_meters(message: str, labels: tuple[str, ...]) -> Decimal | None:
    n = _norm(message)
    label = "(?:" + "|".join(re.escape(_norm(value)) for value in labels) + ")"
    for pattern in (
        rf"{label}[^0-9]{{0,24}}(\d+(?:[.,]\d+)?)\s*(?:m|meter)\b",
        rf"(\d+(?:[.,]\d+)?)\s*(?:m|meter)\b[^.;\n]{{0,24}}{label}",
    ):
        match = re.search(pattern, n)
        if match:
            value = _number(match.group(1))
            if value is not None:
                return value
    return None


def _ab_extract_room_dimensions(message: str) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    n = _norm(message)
    # Natural compact room notation: 4 x 5 x 2,5 m (L × B × H).
    triplet = re.search(
        r"(?<![0-9])(?P<l>\d+(?:[.,]\d+)?)\s*[x×]\s*(?P<w>\d+(?:[.,]\d+)?)\s*[x×]\s*(?P<h>\d+(?:[.,]\d+)?)\s*(?:m|meter)\b",
        n,
    )
    if triplet:
        return _number(triplet.group("l")), _number(triplet.group("w")), _number(triplet.group("h"))
    length = _ab_extract_linear_meters(message, ("länge", "laenge", "raumlänge", "raumlaenge"))
    width = _ab_extract_linear_meters(message, ("breite", "raumbreite"))
    height = _ab_extract_linear_meters(
        message,
        ("raumhöhe", "raumhoehe", "deckenhöhe", "deckenhoehe", "wandhöhe", "wandhoehe", "höhe", "hoehe"),
    )
    return length, width, height


def _ab_has_explicit_wall_area(message: str) -> bool:
    return _extract_measure(message, ("wandfläche", "wandflache", "wandfläche gesamt", "wandflache gesamt")) is not None


def _read_explicit_facts(state: dict[str, Any], message: str) -> None:
    _AB_ORIGINAL_READ_EXPLICIT_FACTS(state, message)
    facts = state["facts"]
    length, width, height = _ab_extract_room_dimensions(message)
    if length is not None:
        facts["room_length"] = str(length)
    if width is not None:
        facts["room_width"] = str(width)
    if height is not None and Decimal("1.5") <= height <= Decimal("6"):
        facts["room_height"] = str(height)
    if _ab_has_explicit_wall_area(message):
        facts["wall_area_explicit"] = True


def _ab_wall_quantity(state: dict[str, Any]) -> tuple[Decimal | None, str]:
    facts = state["facts"]
    floor = _area(facts, "floor_area")
    explicit = _area(facts, "wall_area") if facts.get("wall_area_explicit") else None
    if explicit is not None:
        return explicit, "explizit angegebene Wandfläche"
    length = _area(facts, "room_length")
    width = _area(facts, "room_width")
    height = _area(facts, "room_height")
    if length is not None and width is not None and height is not None:
        value = Decimal("2") * (length + width) * height
        return value, f"2 × ({_fmt(length)} m + {_fmt(width)} m) × {_fmt(height)} m Raumhöhe"
    if floor is not None and height is not None:
        # Requested business rule for incomplete room geometry: the supplied floor
        # area is multiplied by the supplied height. This is a Kalkulationsansatz,
        # not a claim that floor area mathematically equals perimeter.
        value = floor * height
        return value, f"{_fmt(floor)} m² Grundfläche × {_fmt(height)} m Raumhöhe (Kalkulationsansatz)"
    if floor is not None:
        value = floor * WALL_AREA_FACTOR
        return value, f"{_fmt(floor)} m² Wohn-/Grundfläche × {_fmt(WALL_AREA_FACTOR)} Standardfaktor"
    return None, "Wandaufmaß noch offen"


def _painting_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    items = _AB_ORIGINAL_PAINTING_ITEMS(state)
    facts = state["facts"]
    flags = state["flags"]
    if not flags.get("paint_walls"):
        return items
    wall_area, wall_basis = _ab_wall_quantity(state)
    ceiling_area = _area(facts, "ceiling_area")
    floor_area = _area(facts, "floor_area")
    if ceiling_area is None and floor_area is not None and flags.get("paint_ceiling"):
        ceiling_area = floor_area
    for item in items:
        key = item.get("key")
        if key in {"paint.wall.primer", "paint.wall.coat", "paint.wallpaper.remove"}:
            item["quantity"] = None if wall_area is None else float(wall_area)
            item["quantity_display"] = _fmt(wall_area)
            item["basis"] = wall_basis
            item["status"] = "berechnet" if wall_area is not None else "Menge offen"
        elif key == "paint.substrate.fill":
            total = (wall_area or Decimal("0")) + (ceiling_area or Decimal("0"))
            value = total if total > 0 else None
            item["quantity"] = None if value is None else float(value)
            item["quantity_display"] = _fmt(value)
            basis = []
            if wall_area is not None:
                basis.append(f"Wände {_fmt(wall_area)} m²")
            if ceiling_area is not None:
                basis.append(f"Decke {_fmt(ceiling_area)} m²")
            item["basis"] = " + ".join(basis) or "zu bearbeitende Fläche nach Aufmaß"
            item["status"] = "berechnet" if value is not None else "Menge offen"
    return items


def _summary(state: dict[str, Any], items: list[dict[str, Any]], question: str) -> str:
    if state.get("kind") != "painting":
        return _AB_ORIGINAL_SUMMARY(state, items, question)
    facts = state["facts"]
    flags = state["flags"]
    parts: list[str] = []
    if flags.get("paint_walls"):
        wall, basis = _ab_wall_quantity(state)
        if wall is not None:
            parts.append(f"Wandfläche automatisch: {basis} = {_fmt(wall)} m².")
    floor = _area(facts, "floor_area")
    if flags.get("paint_ceiling") and floor is not None and _area(facts, "ceiling_area") is None:
        parts.append(f"Deckenfläche automatisch: {_fmt(floor)} m².")
    if question:
        parts.append(QUESTION_TEXT[question])
    else:
        parts.append("Der Leistungsansatz ist mit den bisher bekannten Angaben vollständig. Mengen mit „offen“ müssen vor Preisfreigabe noch aufgemessen werden.")
    return " ".join(parts)
'''
    TARGET.write_text(text, encoding="utf-8")

verify = TARGET.read_text(encoding="utf-8")
for required in (MARKER, "def _ab_wall_quantity", "Kalkulationsansatz", "2 × ("):
    if required not in verify:
        raise RuntimeError(f"Final painting math guard failed: {required}")
print("A+Bau final painting dimension rules installed: explicit Wandfläche > perimeter×height > floor×height > 2.5 fallback.")
