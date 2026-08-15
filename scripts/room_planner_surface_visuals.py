from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_MARKER = "KAYI renovation state persistence 20260815"
JS_MARKER = "KAYI renovation surface renderer 20260815"
VERSION = "20260815-2044-renovation-surfaces"


STATE_PATCH = r'''

# KAYI renovation state persistence 20260815
# Keep the structured KI renovation plan through every normalization/save/revision
# round-trip. Geometry normalization remains authoritative; this wrapper only
# preserves a bounded, explicitly supported renovation payload.
_kayi_geometry_normalize_room_state = normalize_room_state
_kayi_geometry_blank_room_state = blank_room_state


def _kayi_renovation_number(value, *, minimum=0.0, maximum=50.0):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return max(minimum, min(maximum, number))


def _kayi_renovation_text(value, limit=500):
    if value in (None, ""):
        return None
    return str(value).strip()[:limit] or None


def _kayi_sanitize_renovation(value):
    raw = value if isinstance(value, dict) else {}
    raw_intent = raw.get("intent") if isinstance(raw.get("intent"), dict) else {}
    raw_surface = raw.get("surface_plan") if isinstance(raw.get("surface_plan"), dict) else {}
    raw_work = raw.get("work_scope") if isinstance(raw.get("work_scope"), dict) else {}

    floor = raw_surface.get("floor") if isinstance(raw_surface.get("floor"), dict) else {}
    wet = raw_surface.get("wet_zone") if isinstance(raw_surface.get("wet_zone"), dict) else {}
    other = raw_surface.get("other_walls") if isinstance(raw_surface.get("other_walls"), dict) else {}
    ceiling = raw_surface.get("ceiling") if isinstance(raw_surface.get("ceiling"), dict) else {}
    walls = [item for item in (wet.get("applies_to") or []) if item in {"back", "front", "left", "right"}][:4]

    return {
        "intent": {
            "preserve_positions": bool(raw_intent.get("preserve_positions", False)),
            "allow_relayout": bool(raw_intent.get("allow_relayout", False)),
            "replace_sanitary_in_place": bool(raw_intent.get("replace_sanitary_in_place", False)),
        },
        "surface_plan": {
            "floor": {
                "remove_existing": bool(floor.get("remove_existing", False)),
                "finish": _kayi_renovation_text(floor.get("finish"), 120),
                "tile_color": _kayi_renovation_text(floor.get("tile_color"), 80),
                "tile_width_cm": _kayi_renovation_number(floor.get("tile_width_cm"), minimum=1, maximum=300),
                "tile_height_cm": _kayi_renovation_number(floor.get("tile_height_cm"), minimum=1, maximum=300),
            },
            "wet_zone": {
                "present": bool(wet.get("present", False)),
                "height_m": _kayi_renovation_number(wet.get("height_m"), minimum=0, maximum=12),
                "wall_tile_color": _kayi_renovation_text(wet.get("wall_tile_color"), 80),
                "tile_width_cm": _kayi_renovation_number(wet.get("tile_width_cm"), minimum=1, maximum=300),
                "tile_height_cm": _kayi_renovation_number(wet.get("tile_height_cm"), minimum=1, maximum=300),
                "applies_to": walls,
                "basis": _kayi_renovation_text(wet.get("basis"), 500),
            },
            "other_walls": {
                "height_m": _kayi_renovation_number(other.get("height_m"), minimum=0, maximum=12),
                "wall_tile_color": _kayi_renovation_text(other.get("wall_tile_color"), 80),
                "tile_width_cm": _kayi_renovation_number(other.get("tile_width_cm"), minimum=1, maximum=300),
                "tile_height_cm": _kayi_renovation_number(other.get("tile_height_cm"), minimum=1, maximum=300),
                "upper_finish": _kayi_renovation_text(other.get("upper_finish"), 300),
            },
            "ceiling": {
                "finish": _kayi_renovation_text(ceiling.get("finish"), 300),
            },
        },
        "work_scope": {
            "remove_old_wall_coverings": bool(raw_work.get("remove_old_wall_coverings", False)),
            "remove_old_floor_coverings": bool(raw_work.get("remove_old_floor_coverings", False)),
            "door_finish": _kayi_renovation_text(raw_work.get("door_finish"), 300),
            "replace_bathtub": bool(raw_work.get("replace_bathtub", False)),
            "replace_toilet": bool(raw_work.get("replace_toilet", False)),
            "replace_sink": bool(raw_work.get("replace_sink", False)),
            "replace_shower": bool(raw_work.get("replace_shower", False)),
            "notes": [str(item)[:500] for item in (raw_work.get("notes") or [])[:20]],
        },
        "source_command": str(raw.get("source_command") or "")[:4000],
    }


def blank_room_state():
    state = _kayi_geometry_blank_room_state()
    state["renovation"] = _kayi_sanitize_renovation({})
    return state


def normalize_room_state(state, measurement=None, scan=None):
    renovation = _kayi_sanitize_renovation(state.get("renovation") if isinstance(state, dict) else {})
    normalized = _kayi_geometry_normalize_room_state(state, measurement, scan)
    normalized["renovation"] = renovation
    return normalized
'''


JS = r'''

// KAYI renovation surface renderer 20260815
(() => {
  const legacyNormalizeStateForRenovation = normalizeState;
  const legacyRebuildSceneForRenovation = rebuildScene;

  const copyRenovation = (raw, normalized) => {
    if (raw?.renovation && typeof raw.renovation === 'object') {
      normalized.renovation = deepClone(raw.renovation);
    } else {
      normalized.renovation ||= { intent: {}, surface_plan: {}, work_scope: {}, source_command: '' };
    }
    return normalized;
  };

  normalizeState = function normalizeStateWithRenovation(raw) {
    return copyRenovation(raw, legacyNormalizeStateForRenovation(raw));
  };

  // The original normalizeState predates renovation metadata and already ran once
  // before this final runtime layer. Recover the server JSON for the first render.
  try {
    const rawInitial = JSON.parse($('#room-planner-state')?.textContent || '{}');
    copyRenovation(rawInitial, state);
  } catch (_) {
    state.renovation ||= { intent: {}, surface_plan: {}, work_scope: {}, source_command: '' };
  }

  const colorMap = {
    'weiß': '#f5f5f2', 'weiss': '#f5f5f2', 'white': '#f5f5f2',
    'hellgrau': '#d7d9da', 'hell grau': '#d7d9da', 'light grey': '#d7d9da', 'light gray': '#d7d9da',
    'grau': '#afb3b5', 'grey': '#afb3b5', 'gray': '#afb3b5',
    'dunkelgrau': '#686d70', 'anthrazit': '#4d5356', 'schwarz': '#303336',
    'beige': '#d9d0c0', 'sand': '#d8cbb6', 'creme': '#eee8da',
  };
  const resolveColor = (value, fallback) => {
    const text = String(value || '').trim().toLowerCase();
    if (/^#[0-9a-f]{6}$/i.test(text)) return text;
    return colorMap[text] || fallback;
  };
  const finite = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const positive = (value, fallback) => Math.max(0.01, finite(value, fallback));

  function makeTileTexture(baseColor, groutColor = '#aeb2b4') {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = baseColor;
    ctx.fillRect(0, 0, 128, 128);
    const shade = ctx.createLinearGradient(0, 0, 128, 128);
    shade.addColorStop(0, 'rgba(255,255,255,.16)');
    shade.addColorStop(.55, 'rgba(255,255,255,0)');
    shade.addColorStop(1, 'rgba(20,28,32,.045)');
    ctx.fillStyle = shade;
    ctx.fillRect(0, 0, 128, 128);
    ctx.strokeStyle = groutColor;
    ctx.lineWidth = 3;
    ctx.strokeRect(1.5, 1.5, 125, 125);
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy?.() || 1);
    texture.needsUpdate = true;
    return texture;
  }

  function tiledMaterial({ color, grout, tileW, tileH, width, height, offsetX = 0, offsetY = 0, opacity = 0.32 }) {
    const texture = makeTileTexture(color, grout);
    texture.repeat.set(Math.max(0.01, width / tileW), Math.max(0.01, height / tileH));
    texture.offset.set((offsetX / tileW) % 1, (offsetY / tileH) % 1);
    return new THREE.MeshStandardMaterial({
      map: texture,
      color: 0xffffff,
      roughness: 0.68,
      metalness: 0.01,
      transparent: opacity < 1,
      opacity,
      depthWrite: opacity >= 0.95,
      side: THREE.DoubleSide,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
    });
  }

  function paintedMaterial(opacity = 0.12) {
    return new THREE.MeshStandardMaterial({
      color: 0xf5f4ef,
      roughness: 0.94,
      metalness: 0,
      transparent: true,
      opacity,
      depthWrite: false,
      side: THREE.DoubleSide,
      polygonOffset: true,
      polygonOffsetFactor: -2,
      polygonOffsetUnits: -2,
    });
  }

  function addWallPlane(group, wall, a, b, y0, y1, mat) {
    if (b - a < 0.008 || y1 - y0 < 0.008) return;
    const width = b - a;
    const height = y1 - y0;
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, height), mat);
    mesh.receiveShadow = true;
    mesh.castShadow = false;
    mesh.renderOrder = 3;
    if (wall === 'back') mesh.position.set((a + b) / 2, (y0 + y1) / 2, 0.003);
    if (wall === 'front') mesh.position.set((a + b) / 2, (y0 + y1) / 2, state.room.length_m - 0.003);
    if (wall === 'left') {
      mesh.rotation.y = Math.PI / 2;
      mesh.position.set(0.003, (y0 + y1) / 2, (a + b) / 2);
    }
    if (wall === 'right') {
      mesh.rotation.y = Math.PI / 2;
      mesh.position.set(state.room.width_m - 0.003, (y0 + y1) / 2, (a + b) / 2);
    }
    mesh.userData = { role: 'renovation-surface', wall };
    group.add(mesh);
  }

  function wallBandCells(wall, y0, y1) {
    const roomHeight = finite(state.room.height_m, 2.5);
    y0 = clamp(finite(y0), 0, roomHeight);
    y1 = clamp(finite(y1), 0, roomHeight);
    if (y1 <= y0 + 0.005) return [];
    const wallLength = wall === 'back' || wall === 'front' ? finite(state.room.width_m, 3) : finite(state.room.length_m, 4);
    const openings = (state.openings || [])
      .filter((o) => o.enabled !== false && o.wall === wall)
      .map((o) => ({
        a: clamp(finite(o.offset_m), 0, wallLength),
        b: clamp(finite(o.offset_m) + finite(o.width_m, 0.8), 0, wallLength),
        y0: clamp(finite(o.sill_height_m), 0, roomHeight),
        y1: clamp(finite(o.sill_height_m) + finite(o.height_m, 2), 0, roomHeight),
      }))
      .filter((o) => o.b > o.a && o.y1 > o.y0);
    const xs = [...new Set([0, wallLength, ...openings.flatMap((o) => [o.a, o.b])])].sort((a, b) => a - b);
    const ys = [...new Set([y0, y1, ...openings.flatMap((o) => [clamp(o.y0, y0, y1), clamp(o.y1, y0, y1)])])].sort((a, b) => a - b);
    const cells = [];
    for (let xi = 0; xi < xs.length - 1; xi++) {
      const a = xs[xi], b = xs[xi + 1];
      if (b - a < 0.005) continue;
      const xm = (a + b) / 2;
      for (let yi = 0; yi < ys.length - 1; yi++) {
        const cy0 = ys[yi], cy1 = ys[yi + 1];
        if (cy1 <= y0 || cy0 >= y1 || cy1 - cy0 < 0.005) continue;
        const ym = (cy0 + cy1) / 2;
        if (openings.some((o) => xm > o.a + 1e-5 && xm < o.b - 1e-5 && ym > o.y0 + 1e-5 && ym < o.y1 - 1e-5)) continue;
        cells.push({ a, b, y0: Math.max(y0, cy0), y1: Math.min(y1, cy1) });
      }
    }
    return cells;
  }

  function addTiledWallBand(group, wall, y0, y1, config) {
    const color = resolveColor(config?.wall_tile_color, '#f5f5f2');
    const grout = resolveColor(state.materials?.grout_color, '#b9bbba');
    const tileW = positive(finite(config?.tile_width_cm, 30) / 100, 0.3);
    const tileH = positive(finite(config?.tile_height_cm, 60) / 100, 0.6);
    wallBandCells(wall, y0, y1).forEach((cell) => {
      const mat = tiledMaterial({
        color, grout, tileW, tileH,
        width: cell.b - cell.a,
        height: cell.y1 - cell.y0,
        offsetX: cell.a,
        offsetY: cell.y0,
        opacity: 0.34,
      });
      addWallPlane(group, wall, cell.a, cell.b, cell.y0, cell.y1, mat);
    });
  }

  function addPaintedWallBand(group, wall, y0, y1) {
    wallBandCells(wall, y0, y1).forEach((cell) => {
      addWallPlane(group, wall, cell.a, cell.b, cell.y0, cell.y1, paintedMaterial(0.12));
    });
  }

  function finishLooksPainted(value) {
    return /q\s*3|spachtel|streich|paint|anstrich/i.test(String(value || ''));
  }

  function addRenovationSurfaceVisuals() {
    const renovation = state.renovation;
    const surface = renovation?.surface_plan;
    if (!surface || typeof surface !== 'object') return;
    const group = new THREE.Group();
    group.name = 'kayi-renovation-surfaces';
    group.userData = { role: 'renovation-surfaces' };

    const roomW = finite(state.room.width_m, 3);
    const roomL = finite(state.room.length_m, 4);
    const roomH = finite(state.room.height_m, 2.5);
    const floor = surface.floor || {};
    const floorHasTiles = /fliese|tile|keramik|stein/i.test(String(floor.finish || '')) || (floor.tile_width_cm && floor.tile_height_cm);
    if (floorHasTiles) {
      const tileW = positive(finite(floor.tile_width_cm, 60) / 100, 0.6);
      const tileH = positive(finite(floor.tile_height_cm, 60) / 100, 0.6);
      const color = resolveColor(floor.tile_color, '#d7d9da');
      const grout = resolveColor(state.materials?.grout_color, '#b0b2b2');
      const mat = tiledMaterial({ color, grout, tileW, tileH, width: roomW, height: roomL, opacity: 0.96 });
      const plane = new THREE.Mesh(new THREE.PlaneGeometry(roomW, roomL), mat);
      plane.rotation.x = -Math.PI / 2;
      plane.position.set(roomW / 2, 0.006, roomL / 2);
      plane.receiveShadow = true;
      plane.renderOrder = 2;
      plane.userData = { role: 'renovation-surface', surface: 'floor' };
      group.add(plane);
    }

    const wet = surface.wet_zone || {};
    const other = surface.other_walls || {};
    const wetWalls = new Set(Array.isArray(wet.applies_to) ? wet.applies_to : []);
    const wetHeight = clamp(finite(wet.height_m, 0), 0, roomH);
    const otherHeight = clamp(finite(other.height_m, 0), 0, roomH);
    for (const wall of ['back', 'front', 'left', 'right']) {
      const isWet = Boolean(wet.present) && wetWalls.has(wall) && wetHeight > 0.01;
      const bandHeight = isWet ? wetHeight : otherHeight;
      const tileConfig = isWet ? wet : other;
      const hasTilePlan = bandHeight > 0.01 && (tileConfig.wall_tile_color || tileConfig.tile_width_cm || tileConfig.tile_height_cm);
      if (hasTilePlan) addTiledWallBand(group, wall, 0, bandHeight, tileConfig);
      const upperFinish = other.upper_finish || surface.ceiling?.finish || '';
      if (bandHeight < roomH - 0.01 && finishLooksPainted(upperFinish)) {
        addPaintedWallBand(group, wall, bandHeight, roomH);
      }
    }

    if (state.view.show_ceiling && finishLooksPainted(surface.ceiling?.finish)) {
      const mat = paintedMaterial(0.18);
      const ceiling = new THREE.Mesh(new THREE.PlaneGeometry(roomW, roomL), mat);
      ceiling.rotation.x = Math.PI / 2;
      ceiling.position.set(roomW / 2, roomH - 0.004, roomL / 2);
      ceiling.renderOrder = 2;
      ceiling.userData = { role: 'renovation-surface', surface: 'ceiling' };
      group.add(ceiling);
    }

    if (group.children.length) world.add(group);
  }

  rebuildScene = function rebuildSceneWithRenovationSurfaces(options = {}) {
    const result = legacyRebuildSceneForRenovation(options);
    addRenovationSurfaceVisuals();
    return result;
  };

  // Rebuild the already initialized scene so the current KI draft immediately
  // displays tile formats/heights and the smooth Q3+painted zones.
  rebuildScene({ keepCamera: true });
  queueRender();
})();
'''


TEST = r'''from django.test import SimpleTestCase

from erp.services.room_planner_state import blank_room_state, normalize_room_state


class RoomPlannerRenovationSurfaceTests(SimpleTestCase):
    def test_structured_renovation_survives_normalization(self):
        state = blank_room_state()
        state["renovation"] = {
            "intent": {"preserve_positions": True, "allow_relayout": False, "replace_sanitary_in_place": True},
            "surface_plan": {
                "floor": {"finish": "Fliesen", "tile_color": "hellgrau", "tile_width_cm": 60, "tile_height_cm": 60},
                "wet_zone": {"present": True, "height_m": 2.0, "wall_tile_color": "weiß", "tile_width_cm": 30, "tile_height_cm": 60, "applies_to": ["right"], "basis": "Badewanne"},
                "other_walls": {"height_m": 1.4, "wall_tile_color": "weiß", "tile_width_cm": 30, "tile_height_cm": 60, "upper_finish": "Q3 gespachtelt und gestrichen"},
                "ceiling": {"finish": "Q3 gespachtelt und gestrichen"},
            },
            "work_scope": {"replace_bathtub": True, "replace_toilet": True, "replace_sink": True, "door_finish": "geschliffen und lackiert"},
            "source_command": "Bad sanieren",
        }
        normalized = normalize_room_state(state)
        plan = normalized["renovation"]["surface_plan"]
        self.assertEqual(plan["floor"]["tile_width_cm"], 60.0)
        self.assertEqual(plan["wet_zone"]["height_m"], 2.0)
        self.assertEqual(plan["wet_zone"]["applies_to"], ["right"])
        self.assertEqual(plan["other_walls"]["height_m"], 1.4)
        self.assertIn("Q3", plan["other_walls"]["upper_finish"])
        self.assertTrue(normalized["renovation"]["work_scope"]["replace_bathtub"])

    def test_unknown_renovation_payload_is_not_persisted(self):
        state = blank_room_state()
        state["renovation"] = {"unexpected": {"huge": "x" * 10000}, "source_command": "x" * 5000}
        normalized = normalize_room_state(state)
        self.assertNotIn("unexpected", normalized["renovation"])
        self.assertEqual(len(normalized["renovation"]["source_command"]), 4000)
'''


def patch_state_service() -> None:
    path = ROOT / "erp" / "services" / "room_planner_state.py"
    if not path.exists():
        raise RuntimeError("Room Planner state service missing")
    text = path.read_text(encoding="utf-8")
    if STATE_MARKER not in text:
        path.write_text(text.rstrip() + STATE_PATCH + "\n", encoding="utf-8")


def patch_runtime_js() -> None:
    path = ROOT / "static" / "js" / "room-planner.js"
    if not path.exists():
        raise RuntimeError("Room Planner runtime JS missing")
    text = path.read_text(encoding="utf-8")
    if JS_MARKER not in text:
        path.write_text(text.rstrip() + JS + "\n", encoding="utf-8")


def patch_template() -> None:
    path = ROOT / "templates" / "rebuild" / "room_planner.html"
    if not path.exists():
        raise RuntimeError("Room Planner template missing")
    text = path.read_text(encoding="utf-8")
    text, count = re.subn(
        r"(\{%\s*static\s+'js/room-planner\.js'\s*%\}\?v=)[^\"']+",
        rf"\g<1>{VERSION}",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not cache-bust renovation surface renderer")
    path.write_text(text, encoding="utf-8")


def install_test() -> None:
    path = ROOT / "tests" / "test_room_planner_renovation_surfaces.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(TEST, encoding="utf-8")


def guard() -> None:
    state_service = (ROOT / "erp" / "services" / "room_planner_state.py").read_text(encoding="utf-8")
    js = (ROOT / "static" / "js" / "room-planner.js").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "rebuild" / "room_planner.html").read_text(encoding="utf-8")
    for needle in (STATE_MARKER, "_kayi_sanitize_renovation", 'normalized["renovation"] = renovation'):
        if needle not in state_service:
            raise RuntimeError(f"Renovation state persistence missing: {needle}")
    for needle in (JS_MARKER, "CanvasTexture", "addTiledWallBand", "wallBandCells", "kayi-renovation-surfaces", "rebuildSceneWithRenovationSurfaces"):
        if needle not in js:
            raise RuntimeError(f"Renovation 3D surface renderer missing: {needle}")
    if f"room-planner.js' %}}?v={VERSION}" not in template:
        raise RuntimeError("Renovation surface renderer cache-bust missing")
    if not (ROOT / "tests" / "test_room_planner_renovation_surfaces.py").exists():
        raise RuntimeError("Renovation surface regression test missing")


patch_state_service()
patch_runtime_js()
patch_template()
install_test()
guard()
print("Room Planner now persists KI renovation scope and renders floor/wall tile bands plus Q3-painted zones in 3D.")
