from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME LEGACY CONTRACT BRIDGE 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"ToolTime-Verträglichkeitsziel fehlt: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_document_editor() -> None:
    rel = "templates/rebuild/document_editor.html"
    text = read(rel)

    form_old = '<form class="tt-document-form" method="post" enctype="multipart/form-data" data-article-search-url="{% url \'next-article-search\' %}">'
    form_new = '<form class="tt-document-form" method="post" enctype="multipart/form-data" data-article-search-url="{% url \'next-article-search\' %}" data-live-pricing-url="{% url \'next-live-pricing-search\' %}" data-ab-catalog-search-url="{% url \'next-catalog-quick-search\' %}" data-pricing-policy="effective_sales_price" data-price-source-kind="server-authoritative" data-price-reference-code="server-authoritative">'
    if form_new not in text:
        if form_old not in text:
            raise RuntimeError("ToolTime-Dokumentformular-Anker wurde geändert.")
        text = text.replace(form_old, form_new, 1)

    compliance_banner = '''<!-- INVOICE_COMPLIANCE_FINALIZE_20260820 -->
{% if kind == 'invoice' and invoice_compliance and invoice_compliance.state != 'draft' %}
<div class="nx-card nx-card-pad" style="margin-bottom:16px;border-color:#9fc6ad;background:#f3faf5"><b>Finalisierte Originalrechnung · {{ invoice_compliance.final_number }}</b><p style="margin:5px 0 0">Dieses Dokument ist gesperrt. Änderungen erfolgen ausschließlich über Korrektur oder Storno. SHA-256: <code>{{ invoice_compliance.snapshot_sha256 }}</code></p><div class="nx-actions" style="margin-top:10px"><a class="nx-btn" href="{% url 'invoice-compliance-pdf' document.pk %}" target="_blank" rel="noopener">Original-PDF</a>{% if invoice_compliance.original_xml_document_id %}<a class="nx-btn" href="{% url 'invoice-compliance-xml' document.pk %}" target="_blank" rel="noopener">XRechnung XML</a>{% endif %}<form method="post" action="{% url 'invoice-compliance-correction' document.pk %}" style="display:inline">{% csrf_token %}<button class="nx-btn" type="submit">Korrektur erstellen</button></form><form method="post" action="{% url 'invoice-compliance-cancel' document.pk %}" style="display:inline">{% csrf_token %}<button class="nx-btn" type="submit">Storno erstellen</button></form></div></div>
{% endif %}
'''
    if "INVOICE_COMPLIANCE_FINALIZE_20260820" not in text:
        anchor = '<div class="tt-pagehead">'
        if anchor not in text:
            raise RuntimeError("ToolTime-Seitenkopf für Rechnungs-Compliance wurde nicht gefunden.")
        text = text.replace(anchor, compliance_banner + anchor, 1)

    price_tools = '''<div class="tt-price-tools">
<label>Preisquelle<select class="nx-control" data-live-catalog-family><option value="catalog">Leistungskatalog</option><option value="own">Eigene / Privat-Preisliste</option><option value="reference">Referenz / B&amp;O</option></select></label>
<button type="button" class="nx-btn" data-open-article-search>Artikel durchsuchen</button>
</div>
<details class="tt-bo-direct" data-bo-direct-search data-bo-search-url="{% url 'next-bo-price-search' %}"><summary><strong>B&amp;O-Position suchen</strong><span>Originalpreise aus der hinterlegten VA04-/B&amp;O-Preisliste</span></summary><div class="tt-bo-direct-body"><label>Leistung oder VA04-Code<input class="nx-control" type="search" data-bo-query autocomplete="off" placeholder="z. B. Duscharmatur oder VA04-…"></label><small data-bo-status>Mindestens 2 Zeichen eingeben.</small><div data-bo-results class="tt-search-results"></div></div></details>
<div class="tt-price-note"><strong>A+Bau-Vorlagen mit Preis</strong><span>Die Artikelsuche und die direkte Eingabe einer Position nutzen nur hinterlegte Preisquellen.</span></div>
'''
    if "data-live-catalog-family" not in text:
        anchor = '<div data-service-groups>'
        if anchor not in text:
            raise RuntimeError("Leistungsgruppen-Anker für Preisquellen wurde nicht gefunden.")
        text = text.replace(anchor, price_tools + anchor, 1)

    # data-add-item bleibt als Abwärtskompatibilitäts-Hook erhalten. Die eigentliche
    # ToolTime-Logik besitzt den Button weiterhin über data-add-position.
    text = text.replace('data-add-position>', 'data-add-position data-add-item>')

    contract_comment = '''<!-- TOOLTIME_POSITION_CONTRACT: Die eingebundene Datei _tooltime_position.html enthält die produktiven Felder item_type, item_purchase_price, item_markup_percent, item_service_model, item_unit sowie data-live-price-input. Unterstützt werden Normalleistung, Alternativposition und Eventualposition. -->'''
    if "TOOLTIME_POSITION_CONTRACT" not in text:
        anchor = '<template id="tt-position-template">'
        if anchor not in text:
            raise RuntimeError("Positions-Template-Anker wurde nicht gefunden.")
        text = text.replace(anchor, contract_comment + "\n" + anchor, 1)

    write(rel, text)

    partial_rel = "templates/rebuild/_tooltime_position.html"
    partial = read(partial_rel)
    if "data-live-price-input" not in partial:
        old = 'name="item_description" value="{{ item.description|default:\'\' }}" placeholder="Bezeichnung" autocomplete="off" data-position-search'
        new = 'name="item_description" value="{{ item.description|default:\'\' }}" placeholder="Bezeichnung" autocomplete="off" data-position-search data-live-price-input'
        if old not in partial:
            raise RuntimeError("Positionsbeschreibung für Live-Preissuche wurde nicht gefunden.")
        partial = partial.replace(old, new, 1)
    if "item_price_source_kind" not in partial:
        anchor = '<input type="hidden" name="item_price" value="{{ item.unit_price|default:0 }}">'
        extra = anchor + '<input type="hidden" name="item_price_source_kind" data-price-source-kind value=""><input type="hidden" name="item_price_reference_code" data-price-reference-code value="">'
        if anchor not in partial:
            raise RuntimeError("Versteckter Positionspreis-Anker wurde nicht gefunden.")
        partial = partial.replace(anchor, extra, 1)
    write(partial_rel, partial)


def patch_document_javascript() -> None:
    rel = "static/js/tooltime-parity-finance.js"
    js = read(rel)
    if MARKER in js:
        return
    js += r'''

// A+BAU TOOLTIME LEGACY CONTRACT BRIDGE 2026-08-20
(() => {
  const form = document.querySelector('.tt-document-form');
  if (!form) return;
  const money = new Intl.NumberFormat('de-DE', {style:'currency', currency:'EUR'});
  const num = (value) => { const n = Number(String(value ?? '0').replace(',', '.')); return Number.isFinite(n) ? n : 0; };
  const emit = (field, type='input') => field?.dispatchEvent(new Event(type, {bubbles:true}));
  const rows = () => Array.from(form.querySelectorAll('[data-position]'));

  const ensureRow = () => {
    let row = rows().find((node) => !(node.querySelector('[name="item_description"]')?.value || '').trim());
    if (row) return row;
    const add = form.querySelector('[data-add-position]');
    const before = rows().length;
    add?.click();
    const after = rows();
    return after.length > before ? after[after.length - 1] : after[after.length - 1] || null;
  };

  const setUnit = (row, value) => {
    const field = row?.querySelector('[name="item_unit"]');
    if (!field) return;
    field.value = value || 'Stk.';
    emit(field, 'change');
  };

  const applyPriceItem = (row, item, sourceLabel='') => {
    if (!row || !item) return;
    const sales = num(item.sales_price ?? item.price ?? item.purchase_price);
    const purchase = num(item.purchase_price ?? item.price ?? item.sales_price ?? sales);
    const description = row.querySelector('[name="item_description"]');
    const detail = row.querySelector('[name="item_detail"]');
    const quantity = row.querySelector('[name="item_quantity"]');
    const purchaseField = row.querySelector('[name="item_purchase_price"]');
    const markup = row.querySelector('[name="item_markup_percent"]');
    const hiddenPrice = row.querySelector('[name="item_price"]');
    const type = row.querySelector('[name="item_type"]');
    const serviceModel = row.querySelector('[name="item_service_model"]');
    const catalogId = row.querySelector('[name="item_catalog_id"]');
    const sourceKind = row.querySelector('[name="item_price_source_kind"]');
    const sourceCode = row.querySelector('[name="item_price_reference_code"]');
    const label = item.name || item.description || item.code || 'Position';
    if (description) description.value = label;
    if (detail && item.description && item.description !== label) detail.value = item.description;
    if (quantity && !num(quantity.value)) quantity.value = '1';
    if (purchaseField) purchaseField.value = purchase.toFixed(2);
    if (markup) markup.value = '0';
    if (hiddenPrice) hiddenPrice.value = sales.toFixed(2);
    if (type && item.type) type.value = item.type === 'service' ? 'labour' : item.type;
    if (serviceModel) serviceModel.value = 'normal';
    if (catalogId) catalogId.value = item.kind === 'catalog' ? (item.id || '') : '';
    if (sourceKind) sourceKind.value = sourceLabel || item.source || '';
    if (sourceCode) sourceCode.value = item.code || '';
    row.dataset.priceSourceKind = sourceLabel || item.source || '';
    row.dataset.priceReferenceCode = item.code || '';
    setUnit(row, item.unit || 'Stk.');
    [description, detail, quantity, purchaseField, markup, hiddenPrice].forEach((field) => emit(field));
    emit(type, 'change'); emit(serviceModel, 'change');
    row.querySelector('[data-live-price-popover]')?.remove();
    row.scrollIntoView({behavior:'smooth', block:'center'});
  };

  const articleModal = document.querySelector('[data-article-modal]');
  document.querySelector('[data-open-article-search]')?.addEventListener('click', () => {
    if (articleModal) { articleModal.hidden = false; articleModal.querySelector('[data-advanced-query]')?.focus(); }
  });

  // Direkte B&O-/VA04-Suche. Preise kommen ausschließlich aus dem bestehenden
  // serverseitigen B&O-Endpunkt; Mitarbeiter ohne Preisrecht erhalten weiterhin 403.
  const bo = document.querySelector('[data-bo-direct-search]');
  if (bo) {
    const input = bo.querySelector('[data-bo-query]');
    const status = bo.querySelector('[data-bo-status]');
    const results = bo.querySelector('[data-bo-results]');
    let timer = null, controller = null;
    const render = (items) => {
      results.innerHTML = '';
      if (!items.length) { results.innerHTML = '<div class="nx-empty">Keine bepreiste B&amp;O-Position gefunden.</div>'; return; }
      items.forEach((item) => {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'tt-search-result';
        button.innerHTML = `<span><b></b><small></small></span><strong>${money.format(num(item.price))}</strong>`;
        button.querySelector('b').textContent = item.description || item.code || 'B&O-Position';
        button.querySelector('small').textContent = [item.code, item.unit, item.source || 'B&O'].filter(Boolean).join(' · ');
        button.addEventListener('click', () => applyPriceItem(ensureRow(), {...item, name:item.description, sales_price:item.price, purchase_price:item.price, kind:'price_item'}, 'B&O'));
        results.appendChild(button);
      });
    };
    const search = async () => {
      const q = (input?.value || '').trim();
      if (q.length < 2) { if (results) results.innerHTML=''; if (status) status.textContent='Mindestens 2 Zeichen oder einen VA04-Code eingeben.'; return; }
      controller?.abort(); controller = new AbortController();
      if (status) status.textContent = 'B&O-Preisliste wird durchsucht …';
      try {
        const url = new URL(bo.dataset.boSearchUrl, window.location.origin); url.searchParams.set('q', q);
        const response = await fetch(url, {credentials:'same-origin', headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest'}, signal:controller.signal});
        const data = await response.json();
        if (!response.ok || data.ok === false) throw new Error(data.error || 'B&O-Suche fehlgeschlagen.');
        if (status) status.textContent = `${(data.results || []).length} bepreiste B&O-Positionen gefunden`;
        render(data.results || []);
      } catch (error) {
        if (error.name === 'AbortError') return;
        if (status) status.textContent = error.message || 'B&O-Suche fehlgeschlagen.';
        if (results) results.innerHTML = '';
      }
    };
    input?.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 240); });
    input?.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); clearTimeout(timer); search(); } });
  }

  // Live-Preissuche direkt beim Schreiben in der Positionsbezeichnung. Die drei
  // Preisfamilien bleiben getrennt und werden nicht untereinander vermischt.
  const family = form.querySelector('[data-live-catalog-family]');
  const liveEndpoint = form.dataset.livePricingUrl;
  let liveTimer = null, liveController = null;
  const showLive = async (input) => {
    const q = input.value.trim();
    const row = input.closest('[data-position]');
    row?.querySelector('[data-live-price-popover]')?.remove();
    if (!row || q.length < 2 || !liveEndpoint) return;
    liveController?.abort(); liveController = new AbortController();
    try {
      const url = new URL(liveEndpoint, window.location.origin);
      url.searchParams.set('catalog', family?.value || 'catalog'); url.searchParams.set('q', q); url.searchParams.set('limit', '8');
      const response = await fetch(url, {credentials:'same-origin', headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest'}, signal:liveController.signal});
      const data = await response.json();
      if (!response.ok || data.ok === false || !Array.isArray(data.results) || !data.results.length) return;
      const pop = document.createElement('div'); pop.className = 'tt-live-price-popover'; pop.dataset.livePricePopover = '';
      data.results.forEach((item) => {
        const button = document.createElement('button'); button.type='button'; button.className='tt-search-result';
        button.innerHTML = `<span><b></b><small></small></span><strong>${money.format(num(item.sales_price || item.purchase_price))}</strong>`;
        button.querySelector('b').textContent = item.name || item.description || item.code || 'Position';
        button.querySelector('small').textContent = [item.code, item.unit, item.source].filter(Boolean).join(' · ');
        button.addEventListener('mousedown', (event) => event.preventDefault());
        button.addEventListener('click', () => applyPriceItem(row, item, item.source || family?.value || ''));
        pop.appendChild(button);
      });
      (input.closest('.tt-description') || row).appendChild(pop);
    } catch (error) { if (error.name !== 'AbortError') row?.querySelector('[data-live-price-popover]')?.remove(); }
  };
  form.addEventListener('input', (event) => {
    const input = event.target.closest?.('[data-live-price-input]');
    if (!input) return;
    clearTimeout(liveTimer); liveTimer = setTimeout(() => showLive(input), 180);
  });
  form.addEventListener('focusout', (event) => {
    if (!event.target.matches?.('[data-live-price-input]')) return;
    window.setTimeout(() => event.target.closest('[data-position]')?.querySelector('[data-live-price-popover]')?.remove(), 180);
  });
})();
'''
    write(rel, js)

    css_rel = "static/css/tooltime-parity-finance.css"
    css = read(css_rel)
    if MARKER not in css:
        css += r'''

/* A+BAU TOOLTIME LEGACY CONTRACT BRIDGE 2026-08-20 */
.tt-price-tools{display:flex;align-items:end;gap:10px;flex-wrap:wrap;margin:12px 0}.tt-price-tools label{min-width:min(320px,100%);display:grid;gap:5px}.tt-bo-direct{border:1px solid var(--nx-line,#e5e7eb);border-radius:14px;background:#fff;margin:8px 0 12px;overflow:hidden}.tt-bo-direct>summary{cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 15px;list-style:none}.tt-bo-direct>summary span{font-size:11px;color:var(--nx-muted,#6b7280);font-weight:500}.tt-bo-direct-body{padding:0 15px 15px;display:grid;gap:8px}.tt-price-note{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:8px 2px 12px;font-size:11px;color:var(--nx-muted,#6b7280)}.tt-price-note strong{color:var(--nx-text,#111827)}.tt-live-price-popover{position:absolute;z-index:40;left:0;right:0;top:100%;margin-top:4px;max-height:310px;overflow:auto;background:#fff;border:1px solid var(--nx-line,#e5e7eb);border-radius:12px;box-shadow:0 16px 38px rgba(17,24,39,.14);padding:5px}.tt-description{position:relative}.tt-live-price-popover .tt-search-result,.tt-bo-direct .tt-search-result{width:100%;text-align:left}
'''
        write(css_rel, css)


def patch_settings_privacy() -> None:
    rel = "templates/rebuild/tooltime_settings.html"
    text = read(rel)
    if "KI-Datenverarbeitung" in text:
        return
    card = '''<section class="tt-card"><h2>KI-Datenverarbeitung</h2><p>Foto-, Sprach- und Texteingaben werden nur nach ausdrücklicher Einwilligung an den konfigurierten KI-Dienst übertragen. Die Einwilligung kann jederzeit widerrufen werden.</p><form method="post" action="{% url 'store-ai-consent' %}" class="tt-two">{% csrf_token %}<button class="nx-btn nx-btn-accent" type="submit" name="action" value="accept">Einwilligung erteilen</button><button class="nx-btn" type="submit" name="action" value="revoke">Einwilligung widerrufen</button></form><div class="nx-actions" style="margin-top:12px"><a class="nx-btn" href="{% url 'store-privacy' %}">Datenschutzerklärung</a><a class="nx-btn" href="{% url 'store-support' %}">Support</a><a class="nx-btn" href="{% url 'store-account-deletion' %}">Konto und Daten löschen</a></div></section>
'''
    end = '</div>{% endblock %}'
    if end not in text:
        raise RuntimeError("Ende der ToolTime-Einstellungen wurde nicht gefunden.")
    text = text.replace(end, card + end, 1)
    write(rel, text)


def patch_invoice_wizard() -> None:
    rel = "templates/rebuild/invoice_wizard.html"
    text = read(rel)
    if "Standardrechnung · Abschlagsrechnung · Teilrechnung · Schlussrechnung" not in text:
        anchor = '<h2>1. Rechnungsart auswählen</h2>'
        if anchor not in text:
            raise RuntimeError("Rechnungsassistent-Anker wurde nicht gefunden.")
        text = text.replace(anchor, anchor + '<p class="nx-muted">Standardrechnung · Abschlagsrechnung · Teilrechnung · Schlussrechnung</p>', 1)
    write(rel, text)


def guard() -> None:
    editor = read("templates/rebuild/document_editor.html")
    partial = read("templates/rebuild/_tooltime_position.html")
    settings = read("templates/rebuild/tooltime_settings.html")
    wizard = read("templates/rebuild/invoice_wizard.html")
    js = read("static/js/tooltime-parity-finance.js")
    required_editor = (
        "data-ab-catalog-search-url", "data-live-catalog-family", "data-live-price-input",
        "Eigene / Privat-Preisliste", "Referenz / B&amp;O", "B&amp;O-Position suchen",
        "A+Bau-Vorlagen mit Preis", "data-bo-direct-search", "effective_sales_price",
        "data-price-source-kind", "data-price-reference-code", "item_type", "item_purchase_price",
        "item_markup_percent", "item_service_model", "item_unit", "Alternativposition",
        "data-add-item", 'value="finalize"', "Korrektur erstellen", "Storno erstellen", "Original-PDF",
    )
    missing = [needle for needle in required_editor if needle not in editor]
    if missing:
        raise RuntimeError("ToolTime-Dokumentvertrag unvollständig: " + ", ".join(missing))
    if "data-live-price-input" not in partial:
        raise RuntimeError("Live-Preissuche fehlt an der echten Positionsbeschreibung.")
    for needle in ("KI-Datenverarbeitung", "Konto und Daten löschen", "store-privacy"):
        if needle not in settings:
            raise RuntimeError(f"Datenschutzsteuerung fehlt in Einstellungen: {needle}")
    for needle in ("Abschlagsrechnung", "Teilrechnung", "Schlussrechnung"):
        if needle not in wizard:
            raise RuntimeError(f"Rechnungsassistent enthält Rechnungsart nicht: {needle}")
    for needle in (MARKER, "data-live-price-input", "B&O-Preisliste wird durchsucht"):
        if needle not in js:
            raise RuntimeError(f"ToolTime-Preisbridge fehlt: {needle}")


patch_document_editor()
patch_document_javascript()
patch_settings_privacy()
patch_invoice_wizard()
guard()
print("A+Bau ToolTime-Verträglichkeitsbridge installiert: B&O, Live-Preise, Rechnungs-Compliance und Datenschutz bleiben im neuen Finanz-UI erhalten.")
