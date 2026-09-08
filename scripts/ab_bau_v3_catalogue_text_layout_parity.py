from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU V3 CATALOGUE + TEXT LAYOUT PARITY 2026-09-08"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"V3 parity target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _add_data_attribute(text: str, tag_start: int, attribute: str) -> str:
    tag_end = text.find(">", tag_start)
    if tag_end < 0:
        raise RuntimeError(f"Could not close tag while adding {attribute}")
    opening = text[tag_start:tag_end + 1]
    if attribute in opening:
        return text
    opening = opening[:-1] + f" {attribute}>"
    return text[:tag_start] + opening + text[tag_end + 1:]


def install_catalogue_editor() -> None:
    write("templates/rebuild/catalogue_edit.html", r"""{% extends 'rebuild/base.html' %}{% load static %}
{% block title %}{% if item %}Artikel bearbeiten{% else %}Artikel hinzufügen{% endif %} · A+Bau{% endblock %}
{% block content %}
<link rel="stylesheet" href="{% static 'css/tooltime-catalogue-exact.css' %}?v=20260821-catalogue-exact">
<link rel="stylesheet" href="{% static 'css/ab-v3-catalogue-text-layout.css' %}?v=20260908-v3-parity">
<script src="{% static 'js/ab-v3-catalogue-text-layout.js' %}?v=20260908-v3-parity" defer></script>
<div class="abtt-catalogue-editor" data-ab-v3-catalogue-editor>
  <form id="abtt-article-form" method="post" class="abtt-article-form" data-ab-v3-article-form>{% csrf_token %}
    <header class="abtt-editor-head">
      <div class="abtt-editor-title">
        <a class="abtt-close" href="{% url 'next-catalogue' %}" aria-label="Zurück zum Katalog">×</a>
        <div><span class="abtt-eyebrow">Katalog</span><h1>{% if item %}Artikel bearbeiten{% else %}Artikel hinzufügen{% endif %}</h1></div>
      </div>
      <button class="abtt-save" type="submit">Speichern</button>
    </header>
    {% if errors %}<div class="ttc-errors abtt-errors">{% for error in errors %}<div>{{ error }}</div>{% endfor %}</div>{% endif %}
    <div class="abtt-number-block"><label><span>Artikelnummer</span><input name="code" value="{{ values.code }}" placeholder="Optional" autocomplete="off"></label></div>
    <section class="abtt-article-workspace" aria-label="Artikelkalkulation">
      <div class="abtt-pricing-row">
        <label class="abtt-field abtt-type"><span>Artikeltyp</span><select name="type"><option value="material" {% if values.type == 'material' %}selected{% endif %}>Material</option><option value="labor" {% if values.type == 'labor' %}selected{% endif %}>Lohn / Leistung</option><option value="jumbo" {% if values.type == 'jumbo' %}selected{% endif %}>Jumbo</option><option value="other" {% if values.type == 'other' or not values.type %}selected{% endif %}>Sonstiges</option></select></label>
        <label class="abtt-field abtt-quantity"><span>Menge</span><input type="number" min="0" step="0.001" value="1" data-ab-quantity inputmode="decimal"></label>
        <label class="abtt-field abtt-unit"><span>Einheit</span><input name="unit" value="{{ values.unit|default:'Stk.' }}" placeholder="Stk."></label>
        <label class="abtt-field abtt-description"><span>Bezeichnung</span><input name="name" value="{{ values.name }}" placeholder="Material oder Leistung hinzufügen" required autocomplete="off"></label>
        <label class="abtt-field abtt-money"><span>Einkaufspreis</span><div class="abtt-input-prefix"><b>€</b><input type="number" step="0.01" min="0" name="purchase_price" value="{{ values.purchase_price }}" data-ab-purchase inputmode="decimal"></div></label>
        <label class="abtt-field abtt-markup"><span>Aufschlag</span><div class="abtt-input-suffix"><input type="number" step="0.01" min="-100" value="0" data-ab-markup inputmode="decimal"><b>%</b></div></label>
        <div class="abtt-field abtt-output"><span>Aufschlagswert</span><output data-ab-markup-value>0,00 €</output></div>
        <label class="abtt-field abtt-money"><span>Stückpreis</span><div class="abtt-input-prefix"><b>€</b><input type="number" step="0.01" min="0" name="sales_price" value="{{ values.sales_price }}" data-ab-sales inputmode="decimal"></div></label>
        <div class="abtt-field abtt-output abtt-total"><span>Gesamtpreis</span><output data-ab-total>0,00 €</output></div>
      </div>
      <div class="abtt-detail-row">
        <label class="abtt-detail-copy"><span>Beschreibung</span><textarea name="description" rows="4" placeholder="Beschreibung, interne Hinweise oder Leistungsdetails">{{ values.description }}</textarea></label>
        <aside class="abtt-tax-card"><div><span class="abtt-tax-kicker">Weitere Angaben</span><strong>Steuersatz</strong></div><div class="abtt-tax-input"><input type="number" step="0.01" min="0" max="100" name="tax_rate" value="{{ values.tax_rate|default:'19' }}" inputmode="decimal"><span>%</span></div></aside>
      </div>
    </section>
    <footer class="abtt-editor-footer"><a href="{% url 'next-catalogue' %}">Abbrechen</a><button class="abtt-save" type="submit">Speichern</button></footer>
  </form>
</div>
{% endblock %}""")


def patch_settings_surface() -> None:
    rel = "templates/rebuild/tooltime_settings.html"
    text = read(rel)
    layout_marker = '<input type="hidden" name="section" value="layout">'
    marker_pos = text.find(layout_marker)
    if marker_pos < 0:
        raise RuntimeError("V3 text/layout parity: layout form marker missing")

    form_start = text.rfind("<form", 0, marker_pos)
    if form_start < 0:
        raise RuntimeError("V3 text/layout parity: layout form start missing")
    text = _add_data_attribute(text, form_start, "data-ab-v3-layout-form")

    marker_pos = text.find(layout_marker)
    form_start = text.rfind("<form", 0, marker_pos)
    section_start = text.rfind("<section", 0, form_start)
    if section_start < 0:
        raise RuntimeError("V3 text/layout parity: layout section start missing")
    text = _add_data_attribute(text, section_start, "data-ab-v3-layout-card")

    if "data-tooltime-text-template-manager" not in text:
        raise RuntimeError("V3 text/layout parity: complete text-template manager missing")
    legacy_anchor = '<div class="tt-template-settings">'
    legacy_pos = text.find(legacy_anchor)
    if legacy_pos >= 0:
        legacy_section_start = text.rfind("<section", 0, legacy_pos)
        legacy_section_end = text.find("</section>", legacy_pos)
        if legacy_section_start < 0 or legacy_section_end < 0:
            raise RuntimeError("V3 text/layout parity: legacy text-template section bounds missing")
        text = text[:legacy_section_start] + text[legacy_section_end + len("</section>"):]

    if "data-ab-v3-layout-preview" not in text:
        marker_pos = text.find(layout_marker)
        form_close = text.find("</form>", marker_pos)
        if form_close < 0:
            raise RuntimeError("V3 text/layout parity: layout form end missing")
        preview = r"""
<div class="abtt-layout-preview" data-ab-v3-layout-preview aria-label="Dokumentvorschau">
  <div class="abtt-preview-paper">
    <div class="abtt-preview-head" data-ab-preview-logo-wrap>
      {% if organization.logo %}<img src="{{ organization.logo.url }}" alt="{{ organization.name }}" data-ab-preview-logo>{% else %}<span class="abtt-preview-logo-fallback" data-ab-preview-logo>A+</span>{% endif %}
    </div>
    <div class="abtt-preview-body">
      <span class="abtt-preview-sender" data-ab-preview-sender>{{ organization.name }}{% if organization.city %} · {{ organization.city }}{% endif %}</span>
      <i></i><i></i><i class="short"></i><div class="abtt-preview-copy"><i></i><i></i><i></i><i class="short"></i></div>
    </div>
    <div class="abtt-preview-footer" data-ab-preview-footer><i></i><i></i><i></i></div>
  </div>
</div>
"""
        text = text[:form_close] + preview + text[form_close:]

    css_tag = '<link rel="stylesheet" href="{% static \'css/ab-v3-catalogue-text-layout.css\' %}?v=20260908-v3-parity">'
    js_tag = '<script src="{% static \'js/ab-v3-catalogue-text-layout.js\' %}?v=20260908-v3-parity" defer></script>'
    if "ab-v3-catalogue-text-layout.css" not in text:
        block = "{% block content %}"
        if block not in text:
            raise RuntimeError("V3 text/layout parity: settings content block missing")
        text = text.replace(block, block + css_tag, 1)
    if "ab-v3-catalogue-text-layout.js" not in text:
        end = "{% endblock %}"
        pos = text.rfind(end)
        if pos < 0:
            raise RuntimeError("V3 text/layout parity: settings endblock missing")
        text = text[:pos] + js_tag + text[pos:]
    write(rel, text)


def final_guard() -> None:
    catalogue = read("templates/rebuild/catalogue_edit.html")
    settings = read("templates/rebuild/tooltime_settings.html")
    if catalogue.count("data-ab-v3-catalogue-editor") != 1:
        raise RuntimeError("V3 catalogue parity marker must exist exactly once")
    if settings.count("data-ab-v3-layout-preview") != 1:
        raise RuntimeError("V3 text/layout preview must exist exactly once")
    if '<div class="tt-template-settings">' in settings:
        raise RuntimeError("Legacy duplicate text-template editor survived")
    if "data-tooltime-text-template-manager" not in settings:
        raise RuntimeError("Complete text-template manager was lost")
    for required in ("static/css/ab-v3-catalogue-text-layout.css", "static/js/ab-v3-catalogue-text-layout.js"):
        if not (ROOT / required).exists():
            raise RuntimeError(f"V3 parity asset missing: {required}")


def run() -> None:
    install_catalogue_editor()
    patch_settings_surface()
    final_guard()
    print(f"{MARKER}: Katalog-Editor und Texte/Layout auf ToolTime-Workflow-Parität gebracht, A+Bau-V3-Identität und bestehende Backend-Verträge erhalten.")


if __name__ == "__main__":
    run()
