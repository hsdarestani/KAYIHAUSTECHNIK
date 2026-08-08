from __future__ import annotations

import re
from pathlib import Path

VERSION = "20260809-0300"
CACHE_NAME = "kayi-shell-v22-20260809"


def read(path: str) -> str:
    target = Path(path)
    if not target.exists():
        raise RuntimeError(f"Target does not exist: {path}")
    return target.read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one source fragment in {path}, found {count}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str) -> None:
    text = read(path)
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Expected exactly one regex match in {path}, found {count}: {pattern}")
    write(path, updated)


forms_path = "erp/forms.py"
forms_text = read(forms_path)
labels_block = '''        labels = {
            "name": "Raumname",
            "method": "Aufmaßmethode",
            "length_m": "Länge (m)",
            "width_m": "Breite (m)",
            "height_m": "Höhe (m)",
            "deductions_area_m2": "Abzugsfläche (m²)",
            "waste_percent": "Verschnitt (%)",
            "reference_type": "Referenzobjekt",
            "reference_width_cm": "Referenzbreite (cm)",
            "reference_height_cm": "Referenzhöhe (cm)",
        }
'''
if labels_block not in forms_text:
    marker = '''        fields = (
            "name", "method", "length_m", "width_m", "height_m",
            "deductions_area_m2", "waste_percent", "reference_type",
            "reference_width_cm", "reference_height_cm",
        )
'''
    if marker not in forms_text:
        raise RuntimeError("RoomMeasurementForm fields block was not found")
    forms_text = forms_text.replace(marker, marker + labels_block, 1)
    write(forms_path, forms_text)

replace_once(
    "templates/erp/form.html",
    '<button type="button" class="btn btn-secondary" onclick="history.back()">Abbrechen</button>',
    '<button type="button" class="btn btn-secondary" data-smart-back data-back-fallback="{% url \'dashboard\' %}">Abbrechen</button>',
)

replace_once(
    "templates/erp/configurator.html",
    '<div class="model-wall model-wall-right"><div class="model-openings" data-model-openings="right"></div></div>',
    '<div class="model-wall model-wall-right"><div class="model-openings" data-model-openings="right"></div></div>\n        <div class="model-wall model-wall-front"><div class="model-openings" data-model-openings="front"></div></div>',
)
replace_once(
    "templates/erp/configurator.html",
    '<div class="section-title-row"><div><b>Türen, Fenster & Öffnungen</b><small>Position und Größe je Wand</small></div>',
    '<div class="section-title-row"><div><b>Türen, Fenster & Öffnungen</b><small>Direkt im Modell ziehen oder Position hier exakt eingeben</small></div>',
)

app_path = "static/js/app.js"
app_text = read(app_path)
helper = r'''    const openingLabel = (opening) => opening.kind === 'door' ? 'Tür' : opening.kind === 'window' ? 'Fenster' : 'Öffnung';
    const openingOffsetText = (value) => {
      const rounded = Math.round(Math.max(0, value) * 100) / 100;
      return rounded.toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1');
    };
    const setOpeningOffset = (opening, openingIndex, base, value, node = null) => {
      const openingWidth = Math.max(.05, numberValue(opening.width_m));
      const maximum = Math.max(0, base - openingWidth);
      const clamped = Math.max(0, Math.min(maximum, value));
      opening.offset_m = openingOffsetText(clamped);
      const row = $$('[data-opening-editor-list] .opening-editor-row', editor)[openingIndex];
      const input = row?.querySelector('[data-opening-field="offset_m"]');
      if (input && document.activeElement !== input) input.value = opening.offset_m;
      if (node) {
        node.style.left = `${Math.min(84, Math.max(1, clamped / Math.max(.1, base) * 100))}%`;
        node.setAttribute('aria-valuenow', opening.offset_m);
      }
      markDirty();
    };
    const attachOpeningDrag = (node, wall, opening, openingIndex, base) => {
      const maximum = Math.max(0, base - Math.max(.05, numberValue(opening.width_m)));
      node.tabIndex = 0;
      node.setAttribute('role', 'slider');
      node.setAttribute('aria-label', `${openingLabel(opening)} verschieben`);
      node.setAttribute('aria-valuemin', '0');
      node.setAttribute('aria-valuemax', openingOffsetText(maximum));
      node.setAttribute('aria-valuenow', openingOffsetText(numberValue(opening.offset_m)));
      let drag = null;
      node.addEventListener('pointerdown', (event) => {
        if (event.pointerType === 'mouse' && event.button !== 0) return;
        event.preventDefault();
        event.stopPropagation();
        const wallRect = wall?.getBoundingClientRect();
        drag = {
          pointerId: event.pointerId,
          startX: event.clientX,
          startOffset: numberValue(opening.offset_m),
          wallPixels: Math.max(80, wallRect?.width || 0),
        };
        node.setPointerCapture?.(event.pointerId);
        node.classList.add('is-dragging');
        scene.classList.add('is-dragging-opening');
      });
      node.addEventListener('pointermove', (event) => {
        if (!drag || event.pointerId !== drag.pointerId) return;
        event.preventDefault();
        const deltaMeters = ((event.clientX - drag.startX) / drag.wallPixels) * base;
        setOpeningOffset(opening, openingIndex, base, drag.startOffset + deltaMeters, node);
      });
      const finishDrag = (event) => {
        if (!drag || event.pointerId !== drag.pointerId) return;
        try { node.releasePointerCapture?.(event.pointerId); } catch (_) {}
        drag = null;
        node.classList.remove('is-dragging');
        scene.classList.remove('is-dragging-opening');
        renderScene();
      };
      node.addEventListener('pointerup', finishDrag);
      node.addEventListener('pointercancel', finishDrag);
      node.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const step = event.shiftKey ? .25 : .05;
        let next = numberValue(opening.offset_m);
        if (event.key === 'ArrowLeft') next -= step;
        if (event.key === 'ArrowRight') next += step;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = maximum;
        setOpeningOffset(opening, openingIndex, base, next, node);
        renderScene();
      });
    };

'''
if "const attachOpeningDrag = (node, wall, opening, openingIndex, base)" not in app_text:
    marker = "    const renderScene = () => {\n"
    if marker not in app_text:
        raise RuntimeError("Room model renderScene marker was not found")
    app_text = app_text.replace(marker, helper + marker, 1)

old_opening_block = '''      state.openings.forEach((opening) => {
        const wall = $(`[data-model-openings="${CSS.escape(opening.wall || 'back')}"]`, editor) || $('[data-model-openings="back"]', editor);
        const node = document.createElement('span');
        node.className = `model-opening model-opening-${opening.kind || 'opening'}`;
        node.title = `${opening.kind || 'Öffnung'} ${opening.width_m || '–'} × ${opening.height_m || '–'} m`;
        const base = ['left','right'].includes(opening.wall) ? width : length;
        node.style.width = `${Math.min(60, Math.max(8, numberValue(opening.width_m) / Math.max(.1, base) * 100))}%`;
        node.style.height = `${Math.min(88, Math.max(12, numberValue(opening.height_m) / height * 100))}%`;
        node.style.left = `${Math.min(84, Math.max(1, numberValue(opening.offset_m) / Math.max(.1, base) * 100))}%`;
        node.style.bottom = `${Math.min(72, Math.max(0, numberValue(opening.sill_m) / height * 100))}%`;
        wall?.append(node);
      });
'''
new_opening_block = '''      state.openings.forEach((opening, openingIndex) => {
        const wall = $(`[data-model-openings="${CSS.escape(opening.wall || 'back')}"]`, editor) || $('[data-model-openings="back"]', editor);
        const node = document.createElement('span');
        node.className = `model-opening model-opening-${opening.kind || 'opening'}`;
        node.title = `${openingLabel(opening)} verschieben · ${opening.width_m || '–'} × ${opening.height_m || '–'} m`;
        const base = ['left','right'].includes(opening.wall) ? width : length;
        node.style.width = `${Math.min(60, Math.max(8, numberValue(opening.width_m) / Math.max(.1, base) * 100))}%`;
        node.style.height = `${Math.min(88, Math.max(12, numberValue(opening.height_m) / height * 100))}%`;
        node.style.left = `${Math.min(84, Math.max(1, numberValue(opening.offset_m) / Math.max(.1, base) * 100))}%`;
        node.style.bottom = `${Math.min(72, Math.max(0, numberValue(opening.sill_m) / height * 100))}%`;
        if (wall) {
          wall.append(node);
          attachOpeningDrag(node, wall, opening, openingIndex, base);
        }
      });
'''
if new_opening_block not in app_text:
    if old_opening_block not in app_text:
        raise RuntimeError("3D opening render block was not found")
    app_text = app_text.replace(old_opening_block, new_opening_block, 1)
write(app_path, app_text)

css_path = "static/css/app.css"
css_text = read(css_path)
css_addition = '''\n/* Direct manipulation for room openings */\n.model-opening{cursor:grab;touch-action:none;user-select:none;transition:box-shadow .12s ease,filter .12s ease}\n.model-opening:hover,.model-opening:focus-visible{outline:2px solid rgba(23,105,224,.65);outline-offset:2px;filter:saturate(1.15)}\n.model-opening.is-dragging{cursor:grabbing;box-shadow:0 0 0 4px rgba(23,105,224,.18),inset 0 0 0 3px rgba(255,255,255,.65);transition:none}\n.editable-room-scene.is-dragging-opening{cursor:grabbing}\n.model-wall-front .model-opening{pointer-events:auto}\n'''
if "Direct manipulation for room openings" not in css_text:
    css_text += css_addition
    write(css_path, css_text)

ai_path = "erp/services/ai.py"
ai_text = read(ai_path)
old_ai = (
    '"Öffnungen und Objekte dürfen nur auf Wunsch hinzugefügt, entfernt oder verändert werden. Farben als Hex-Werte "\n'
    '            "zurückgeben. Bei \'beide Fliesen 60x60 cm\' gilt das Format für Wand- und Bodenfliesen.\\n\\nAnfrage:\\n" + request_text\n'
)
new_ai = (
    '"Öffnungen und Objekte dürfen nur auf Wunsch hinzugefügt, entfernt oder verändert werden. Farben als Hex-Werte "\n'
    '            "zurückgeben. Bei \'beide Fliesen 60x60 cm\' gilt das Format für Wand- und Bodenfliesen. "\n'
    '            "Alle für den Nutzer sichtbaren Texte in summary und warnings müssen vollständig auf Deutsch sein.\\n\\nAnfrage:\\n" + request_text\n'
)
if new_ai not in ai_text:
    if old_ai not in ai_text:
        raise RuntimeError("Room model AI instruction block was not found")
    write(ai_path, ai_text.replace(old_ai, new_ai, 1))

regex_once(
    "templates/erp/base.html",
    r'href="\{% static \'css/app\.css\' %\}(?:\?v=[^"]*)?"',
    f'href="{{% static \'css/app.css\' %}}?v={VERSION}"',
)
regex_once(
    "templates/erp/base.html",
    r'src="\{% static \'js/app\.js\' %\}(?:\?v=[^"]*)?"',
    f'src="{{% static \'js/app.js\' %}}?v={VERSION}"',
)
regex_once(
    "static/js/app.js",
    r'navigator\.serviceWorker\.register\("/sw\.js(?:\?v=[^"]*)?",\s*\{scope:\s*"/",\s*updateViaCache:\s*"none"\}\)\.then\(\(registration\)\s*=>\s*registration\.update\(\)\)\.catch\(\(\)\s*=>\s*\{\}\)',
    f'navigator.serviceWorker.register("/sw.js?v={VERSION}", {{scope: "/", updateViaCache: "none"}}).then((registration) => registration.update()).catch(() => {{}})',
)
regex_once("static/js/sw.js", r'const CACHE = "[^"]+";', f'const CACHE = "{CACHE_NAME}";')
regex_once(
    "static/js/sw.js",
    r'const ASSETS = \[[^\n]+\];',
    f'const ASSETS = ["/static/css/app.css?v={VERSION}", "/static/js/app.js?v={VERSION}", "/static/manifest.webmanifest", "/privacy/", "/terms/"];',
)

test_path = Path("tests/test_ashkan_ux_fixes.py")
test_path.write_text('''from pathlib import Path\n\nfrom django.test import SimpleTestCase\n\nfrom erp.forms import RoomMeasurementForm\n\n\nclass AshkanUxRegressionTests(SimpleTestCase):\n    def test_room_measurement_labels_are_german(self):\n        form = RoomMeasurementForm()\n        self.assertEqual(form.fields["length_m"].label, "Länge (m)")\n        self.assertEqual(form.fields["width_m"].label, "Breite (m)")\n        self.assertEqual(form.fields["height_m"].label, "Höhe (m)")\n        self.assertEqual(form.fields["deductions_area_m2"].label, "Abzugsfläche (m²)")\n        self.assertEqual(form.fields["waste_percent"].label, "Verschnitt (%)")\n        self.assertEqual(form.fields["reference_type"].label, "Referenzobjekt")\n\n    def test_generic_cancel_uses_safe_back_navigation(self):\n        template = Path("templates/erp/form.html").read_text(encoding="utf-8")\n        self.assertIn("data-smart-back", template)\n        self.assertNotIn("onclick=\\\"history.back()\\\"", template)\n\n    def test_configurator_has_front_wall_and_drag_hint(self):\n        template = Path("templates/erp/configurator.html").read_text(encoding="utf-8")\n        self.assertIn('data-model-openings="front"', template)\n        self.assertIn("Direkt im Modell ziehen", template)\n\n    def test_room_openings_are_drag_enabled_and_german(self):\n        javascript = Path("static/js/app.js").read_text(encoding="utf-8")\n        self.assertIn("attachOpeningDrag", javascript)\n        self.assertIn("verschieben", javascript)\n        self.assertIn("setPointerCapture", javascript)\n        self.assertNotIn("node.title = `${opening.kind", javascript)\n''', encoding="utf-8")

print("Applied Ashkan UX fixes: safe back, German 3D labels, draggable openings, front wall, and cache refresh.")
