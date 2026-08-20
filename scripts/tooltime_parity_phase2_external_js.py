from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 2 SETTINGS JS 2026-08-20"

template_path = ROOT / "templates" / "rebuild" / "tooltime_settings.html"
template = template_path.read_text(encoding="utf-8")

external = '<script src="{% static \'js/tooltime-phase2-settings.js\' %}?v=20260820-2" defer data-phase2-settings-js></script>'
pattern = re.compile(r'<script data-phase2-settings-js>.*?</script>', re.S)
if external not in template:
    template, count = pattern.subn(external, template, count=1)
    if count != 1:
        raise RuntimeError("Phase 2 inline settings script anchor missing")
template_path.write_text(template, encoding="utf-8")

js = r'''(() => {
  "use strict";
  const ROOT_SELECTOR = ".tt-settings";

  const updateNumberPreview = (form, key) => {
    const prefix = form.querySelector(`[data-number-prefix="${key}"]`);
    const start = form.querySelector(`[data-number-start="${key}"]`);
    const output = form.querySelector(`[data-number-preview="${key}"]`);
    if (!prefix || !start || !output) return;
    const rawDigits = String(start.value || "1").replace(/\D/g, "") || "1";
    const requested = Math.max(1, Number.parseInt(rawDigits, 10) || 1);
    const current = Math.max(1, Number.parseInt(output.dataset.currentNext || "1", 10) || 1);
    const value = Math.max(requested, current);
    output.textContent = `${prefix.value || ""}${String(value).padStart(rawDigits.length, "0")}`;
  };

  const updateAllNumberPreviews = (root) => {
    const form = root.querySelector("[data-phase2-numbering] form");
    if (!form) return;
    ["quote", "invoice", "credit", "customer"].forEach((key) => updateNumberPreview(form, key));
  };

  const updatePaymentPreview = (root) => {
    const section = root.querySelector("[data-phase2-documents]");
    if (!section) return;
    const mode = section.querySelector("[data-payment-mode]");
    const days = section.querySelector("[data-payment-days]");
    const preview = section.querySelector("[data-payment-preview]");
    if (!mode || !days || !preview) return;

    if (mode.value === "7" || mode.value === "14") days.value = mode.value;
    if (mode.value === "none" || mode.value === "immediately") days.value = "0";
    days.disabled = mode.value !== "custom";
    const value = Math.max(0, Number.parseInt(days.value || "0", 10) || 0);
    preview.textContent = mode.value === "none"
      ? "Kein Zahlungsziel"
      : value === 0
        ? "Zahlbar sofort"
        : `Zahlbar innerhalb von ${value} Tagen`;
  };

  const initialize = () => {
    const root = document.querySelector(ROOT_SELECTOR);
    if (!root || root.dataset.phase2SettingsReady === "1") return;
    root.dataset.phase2SettingsReady = "1";

    const onInteractiveChange = (event) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const numberForm = target.closest("[data-phase2-numbering] form");
      if (numberForm) {
        ["quote", "invoice", "credit", "customer"].forEach((key) => updateNumberPreview(numberForm, key));
      }
      if (target.closest("[data-phase2-documents]")) updatePaymentPreview(root);
    };

    root.addEventListener("input", onInteractiveChange);
    root.addEventListener("change", onInteractiveChange);
    updateAllNumberPreviews(root);
    updatePaymentPreview(root);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, {once: true});
  } else {
    initialize();
  }
})();
'''
asset = ROOT / "static" / "js" / "tooltime-phase2-settings.js"
asset.parent.mkdir(parents=True, exist_ok=True)
asset.write_text(js, encoding="utf-8")

if "data-phase2-settings-js" not in template or "tooltime-phase2-settings.js" not in template:
    raise RuntimeError("Phase 2 external settings asset is not linked")
for needle in ("updateNumberPreview", "updatePaymentPreview", "DOMContentLoaded", "Kein Zahlungsziel"):
    if needle not in js:
        raise RuntimeError(f"Phase 2 settings runtime missing: {needle}")

print(f"{MARKER}: Nummern- und Zahlungszielvorschau laufen über ein echtes Runtime-Asset.")
