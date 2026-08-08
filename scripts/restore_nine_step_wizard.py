from __future__ import annotations

import base64
import gzip
import hashlib
import re
from pathlib import Path

PAYLOAD_DIR = Path("scripts/nine_step_wizard_payload")
EXPECTED_PARTS = {
    "part01": (2000, "546a2ef1a8c25f6d376a93e2e30f5f9043e770083e05dddc68779a50a0928415"),
    "part02": (2000, "53d66f14ca6b2c163b01e61e8b20dc893b75b9bdb91d5561c6ca7408162cc130"),
    "part03": (2000, "dbd31c8b11f7ff5ef7f15ab2887ac65c1f9e64552510007592853e54e229e27a"),
    "part04": (2000, "96862aef47c0c23f74219c995ea1a6c38d3825c949ff9c036d4d60c5a0274116"),
    "part05": (2000, "fd018e7ac4f6768bdc759353eb58294636b33514ff45b1a2ea23d1e67cec7c30"),
    "part06": (636, "6c83904657d6d54df1738fc2ceb1f9e4948f876b772c0cf636c1e0e4415a2d96"),
}
EXPECTED_PAYLOAD_SHA256 = "3a13784708a3d7b508b1be2a7231af962863fa2b2586ad02256d2a4381eec6fe"
TEMPLATE_SHA256 = "77b796c3fc67d4ff599e89f67e82e910f9f2e0faded3d1422627aacf65c0274b"


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected nine-step restore fragment not found in {path}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


parts = sorted(PAYLOAD_DIR.glob("part*"))
if [part.name for part in parts] != list(EXPECTED_PARTS):
    raise RuntimeError(f"Unexpected nine-step payload parts: {[part.name for part in parts]!r}")

encoded_parts: list[str] = []
for part in parts:
    text = part.read_text(encoding="utf-8").strip()
    expected_length, expected_sha = EXPECTED_PARTS[part.name]
    actual_sha = hashlib.sha256(text.encode()).hexdigest()
    if len(text) != expected_length or actual_sha != expected_sha:
        raise RuntimeError(
            f"Nine-step payload {part.name} integrity failed: length={len(text)} sha={actual_sha}"
        )
    encoded_parts.append(text)

payload_text = "".join(encoded_parts)
payload_sha = hashlib.sha256(payload_text.encode()).hexdigest()
if payload_sha != EXPECTED_PAYLOAD_SHA256:
    raise RuntimeError(
        f"Nine-step payload integrity failed: expected {EXPECTED_PAYLOAD_SHA256}, got {payload_sha}"
    )

template_bytes = gzip.decompress(base64.b64decode(payload_text, validate=True))
actual_template_sha = hashlib.sha256(template_bytes).hexdigest()
if actual_template_sha != TEMPLATE_SHA256:
    raise RuntimeError(
        f"Nine-step wizard template integrity failed: expected {TEMPLATE_SHA256}, got {actual_template_sha}"
    )
Path("templates/erp/project_wizard.html").write_bytes(template_bytes)

replace_once(
    "erp/views.py",
    "Projekt {project.number} über den 3-Schritte-Assistenten angelegt.",
    "Projekt {project.number} über den 9-Schritte-Assistenten angelegt.",
)
replace_once(
    "static/js/app.js",
    '{icon:"＋", title:"Projekt in 3 Schritten starten", text:"Der Assistent legt zuerst Auftrag, Kunde, Projektdaten und Team an. Aufmaß, Leistungen, Material und Angebot folgen danach als klare nächste Schritte im Projekt.", highlight:"3-Schritte-Projektstart", detail:"Bei B&O/Versicherung kannst du den Originalauftrag direkt beim Start hochladen; KAYI verbindet ihn anschließend mit der passenden Preisliste."},',
    '{icon:"＋", title:"Projekt sauber anlegen", text:"Der Projektassistent führt von Kunde und Mitarbeitern über Aufmaß und Leistungen bis zum Angebot.", highlight:"Neues Projekt", detail:"Bei B&O/Versicherung wählst du die passende Versicherungspreisliste – Lieferantenlisten wie JOKA gehören nur zu Material."},',
)
replace_once(
    "static/js/app.js",
    '{icon:"◈", title:"3D nur bei Bedarf", text:"Das 3D-Modell ist kein Pflichtschritt mehr. Öffne es im Projekt, wenn Raumgeometrie, Materialien oder Varianten wirklich relevant sind.", highlight:"Optionaler 3D-Konfigurator", detail:"Im Konfigurator kannst du Maße, Öffnungen, Farben und Objekte weiterhin manuell oder mit KAYI AI anpassen; jede Änderung bleibt prüfpflichtig."},',
    '{icon:"◈", title:"3D-Modell bearbeiten", text:"Maße, Fenster, Türen, Farben und Fliesen lassen sich manuell oder per Beschreibung ändern. Jede Änderung bleibt prüfpflichtig.", highlight:"KAYI AI Live Edit", detail:"Zum Beispiel: Fenster 1 × 1,5 m, Tür gegenüber 74 cm, beige Wände und grauer Boden, Fliesen 60 × 60 cm."},',
)
replace_once(
    "tests/test_workflow_release.py",
    '''        self.assertContains(wizard, "3-Schritte-Projektassistent")
        self.assertNotContains(wizard, "9-Schritte-Projektassistent")
        self.assertEqual(wizard.content.decode().count('data-step="'), 3)''',
    '''        self.assertContains(wizard, "9-Schritte-Projektassistent")
        self.assertNotContains(wizard, "10-Schritte-Projektassistent")
        self.assertEqual(wizard.content.decode().count('data-step="'), 9)''',
)
replace_once(
    "tests/test_v2.py",
    '        self.assertContains(response, "3-Schritte-Projektassistent")',
    '        self.assertContains(response, "9-Schritte-Projektassistent")',
)
replace_once(
    "tests/test_room_model_editor.py",
    '''    def test_project_wizard_keeps_material_and_3d_tools_outside_core_creation_flow(self):
        response = self.client.get(reverse("project-create"))
        self.assertContains(response, "3-Schritte-Projektassistent")
        self.assertNotContains(response, 'class="material-source-grid"')
        self.assertNotContains(response, 'data-inline-room-model="1"')
        self.assertNotContains(response, 'data-model-ai-apply')

        project = self.client.get(reverse("project-detail", args=[self.project.pk]))
        self.assertContains(project, "3D-Modell optional")
        self.assertContains(project, reverse("configurator") + f"?project={self.project.pk}")

        configurator = self.client.get(
            reverse("configurator") + f"?project={self.project.pk}&measurement={self.measurement.pk}"
        )
        self.assertContains(configurator, "data-room-model-editor")
        self.assertContains(configurator, reverse("configurator-model-save"))
        self.assertContains(configurator, reverse("project-room-model-suggestions"))''',
    '''    def test_project_wizard_renders_responsive_material_sources_and_inline_editor(self):
        response = self.client.get(reverse("project-create"))
        self.assertContains(response, "9-Schritte-Projektassistent")
        self.assertContains(response, 'class="material-source-grid"')
        self.assertContains(response, 'data-inline-room-model="1"')
        self.assertContains(response, 'data-model-ai-apply')
        self.assertContains(response, 'data-model-openings="front"')
        self.assertContains(response, reverse("project-room-model-suggestions"))
        self.assertContains(response, reverse("project-wizard-price-preview"))''',
)

for path in (
    "templates/erp/base.html",
    "templates/registration/login.html",
    "static/js/app.js",
    "static/js/sw.js",
):
    text = read(path).replace("20260808-2100", "20260808-2225")
    if path == "static/js/sw.js":
        text = text.replace('kayi-shell-v19-20260808', 'kayi-shell-v20-20260808')
    write(path, text)

wizard = read("templates/erp/project_wizard.html")
steps = re.findall(
    r'<section class="([^\"]*\bwizard-step\b[^\"]*)" data-step="([1-9])">',
    wizard,
)
if len(steps) != 9 or [number for classes, number in steps if "active" in classes.split()] != ["1"]:
    raise RuntimeError(f"Nine-step wizard structure guard failed: {steps!r}")
required = (
    "9-Schritte-Projektassistent",
    'id="projectWizardForm"',
    'data-step="4"',
    'data-step="5"',
    'data-step="6"',
    'data-step="7"',
    'data-step="8"',
    'data-step="9"',
    'class="material-source-grid"',
    'data-inline-room-model="1"',
    'data-model-ai-apply',
    'data-quote="gross"',
    '<b data-current-step>1</b> / 9',
)
for marker in required:
    if marker not in wizard:
        raise RuntimeError(f"Nine-step wizard marker missing: {marker!r}")
if "3-Schritte-Projektassistent" in wizard:
    raise RuntimeError("Simplified three-step wizard still rendered after restore")

print("KAYI full nine-step project wizard restored and verified.")
