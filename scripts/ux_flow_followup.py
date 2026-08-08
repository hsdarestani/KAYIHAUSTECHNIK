from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected UX follow-up fragment not found in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Moving 3D out of the mandatory project wizard must not remove the AI model editor.
# The dedicated configurator now owns the same natural-language controls that were
# previously embedded in the long wizard.
replace_once(
    "templates/erp/configurator.html",
    '<div class="room-model-editor" data-room-model-editor data-save-url="{% url \'configurator-model-save\' %}" data-measurement-id="{{ selected_measurement.pk }}">',
    '<div class="room-model-editor" data-room-model-editor data-save-url="{% url \'configurator-model-save\' %}" data-ai-url="{% url \'project-room-model-suggestions\' %}" data-measurement-id="{{ selected_measurement.pk }}">',
)

replace_once(
    "templates/erp/configurator.html",
    '''    <div class="model-save-card">
      <label><span>Versionsnotiz</span><input class="form-control" data-model-label placeholder="z. B. Fenster verschoben"></label>''',
    '''    <div class="model-editor-section model-ai-section">
      <div class="model-ai-card"><span class="model-ai-icon">✦</span><div><span class="eyebrow">KAYI AI DESIGN</span><h3>Modell mit KI anpassen</h3><p>Beschreibe Maße, Materialien, Öffnungen oder Sanitärobjekte in normaler Sprache. Das Ergebnis bleibt ein prüfbarer Entwurf.</p></div></div>
      <textarea class="form-control" rows="4" data-model-ai-prompt placeholder="z. B. Wände warmweiß, Boden anthrazit 60 × 120 cm, Walk-in-Dusche rechts"></textarea>
      <div class="model-ai-chips"><button type="button" data-model-ai-chip="Boden anthrazit, Wände warmweiß, Fliesen 60 x 120 cm und warmes Licht">Modernes Bad</button><button type="button" data-model-ai-chip="Helles Bad mit beigen Fliesen, Holz-Waschtisch und mehr Helligkeit">Hell & warm</button><button type="button" data-model-ai-chip="Walk-in-Dusche, Waschtisch und WC sinnvoll im Raum verteilen">Sanitärobjekte</button><button type="button" data-model-ai-chip="Boden im Fischgrätmuster und dunkle Akzentwand">Fischgrät</button></div>
      <button class="btn btn-ai btn-block" type="button" data-model-ai-apply>✦ Modell mit KI anpassen</button>
      <div class="model-ai-feedback" data-model-ai-feedback hidden></div>
      <small class="model-ai-warning">KI-Änderungen werden nicht automatisch bestätigt. Maße und Positionen vor Kalkulation oder Bestellung immer prüfen.</small>
    </div>

    <div class="model-save-card">
      <label><span>Versionsnotiz</span><input class="form-control" data-model-label placeholder="z. B. Fenster verschoben"></label>''',
)

# Unsigned reports are drafts by design. The archive must offer continuation,
# not a final-looking PDF action, until a real customer signature exists.
replace_once(
    "tests/test_workflow_release.py",
    '''        self.assertContains(response, reverse("site-report-pdf", args=[assigned_report.pk]))
        self.assertContains(response, reverse("site-report-pdf", args=[foreign_report.pk]))
        self.assertContains(response, "Max Kunde")''',
    '''        self.assertContains(response, reverse("site-report-pdf", args=[assigned_report.pk]))
        self.assertContains(response, reverse("site-report-edit", args=[foreign_report.pk]))
        self.assertNotContains(response, reverse("site-report-pdf", args=[foreign_report.pk]))
        self.assertContains(response, "Max Kunde")''',
)

# Regression guards: the dedicated configurator must expose the real AI endpoint
# and draft reports must remain editable rather than masquerading as final PDFs.
configurator = Path("templates/erp/configurator.html").read_text(encoding="utf-8")
workflow_tests = Path("tests/test_workflow_release.py").read_text(encoding="utf-8")
for marker in (
    "data-ai-url=\"{% url 'project-room-model-suggestions' %}\"",
    "data-model-ai-prompt",
    "data-model-ai-apply",
    "Modell mit KI anpassen",
):
    if marker not in configurator:
        raise RuntimeError(f"Configurator AI follow-up guard failed: {marker!r}")
if 'reverse("site-report-edit", args=[foreign_report.pk])' not in workflow_tests:
    raise RuntimeError("Draft Leistungsnachweis archive regression was not updated")

print("KAYI UX follow-up fixes applied and verified.")
