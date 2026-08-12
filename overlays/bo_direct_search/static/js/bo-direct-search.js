(() => {
  const root = document.querySelector('[data-bo-direct-search]');
  if (!root) return;
  const input = root.querySelector('[data-bo-query]');
  const results = root.querySelector('[data-bo-results]');
  const status = root.querySelector('[data-bo-status]');
  const table = document.querySelector('[data-document-items]');
  if (!input || !results || !table) return;

  const money = (value) => Number(value || 0).toLocaleString('de-DE', {minimumFractionDigits:2, maximumFractionDigits:2});
  const isABBau = () => table.matches('[data-ab-items]') || !!table.querySelector('.ab-item-row');
  const emit = (field, type = 'input') => field?.dispatchEvent(new Event(type, {bubbles:true}));

  const legacyRecalc = () => {
    if (isABBau()) return;
    let net = 0, tax = 0;
    table.querySelectorAll('tbody tr').forEach((row) => {
      const qty = parseFloat(row.querySelector('[name="item_quantity"]')?.value || 0);
      const price = parseFloat(row.querySelector('[name="item_price"]')?.value || 0);
      const rate = parseFloat(row.querySelector('[name="item_tax"]')?.value || 0);
      const line = qty * price;
      net += line;
      tax += line * rate / 100;
    });
    const discount = parseFloat(document.querySelector('[name="discount_percent"]')?.value || 0);
    net *= 1 - Math.max(0, discount) / 100;
    const set = (key, value) => {
      const el = document.querySelector(`[data-total="${key}"]`);
      if (el) el.textContent = value.toLocaleString('de-DE', {style:'currency', currency:'EUR'});
    };
    set('net', net); set('tax', tax); set('gross', net + tax);
  };

  const bindLegacyRow = (row) => {
    row.querySelector('.nx-item-remove')?.addEventListener('click', () => { row.remove(); legacyRecalc(); });
    row.querySelectorAll('input').forEach((field) => field.addEventListener('input', legacyRecalc));
  };

  const blankLegacyRow = () => Array.from(table.querySelectorAll('tbody tr')).find((row) => {
    const desc = row.querySelector('[name="item_description"]')?.value?.trim();
    const price = parseFloat(row.querySelector('[name="item_price"]')?.value || 0);
    return !desc && price === 0;
  });

  const blankABBauRow = () => Array.from(table.querySelectorAll('.ab-item-row')).find((row) => {
    const desc = row.querySelector('[name="item_description"]')?.value?.trim();
    return !desc;
  });

  const getOrCreateABBauRow = () => {
    let row = blankABBauRow();
    if (row) return row;
    const before = table.querySelectorAll('.ab-item-row').length;
    const add = document.querySelector('[data-ab-add-item]');
    add?.click();
    const rows = Array.from(table.querySelectorAll('.ab-item-row'));
    if (rows.length > before) return rows[rows.length - 1];
    return rows[rows.length - 1] || null;
  };

  const setUnit = (row, value) => {
    const field = row.querySelector('[name="item_unit"]');
    if (!field) return;
    if (field.tagName === 'SELECT' && value && !Array.from(field.options).some((option) => option.value === value || option.textContent === value)) {
      field.add(new Option(value, value));
    }
    field.value = value || 'Stk.';
    emit(field, 'change');
  };

  const addABBauPosition = (item) => {
    const row = getOrCreateABBauRow();
    if (!row) {
      status.textContent = 'Position konnte nicht eingefügt werden. Bitte zuerst „Position hinzufügen“ wählen.';
      return;
    }
    const description = row.querySelector('[name="item_description"]');
    const detail = row.querySelector('[name="item_detail"]');
    const quantity = row.querySelector('[name="item_quantity"]');
    const purchase = row.querySelector('[name="item_purchase_price"]');
    const markup = row.querySelector('[name="item_markup_percent"]');
    const hiddenPrice = row.querySelector('[name="item_price"]');
    const type = row.querySelector('[name="item_type"]');
    const serviceModel = row.nextElementSibling?.querySelector('[name="item_service_model"]');
    const catalogId = row.querySelector('[name="item_catalog_id"]');

    description.value = `${item.code ? item.code + ' · ' : ''}${item.description || ''}`;
    if (detail && !detail.value.trim()) detail.value = item.description || '';
    quantity.value = '1';
    purchase.value = item.price || '0';
    markup.value = '0';
    if (hiddenPrice) hiddenPrice.value = item.price || '0';
    if (type) type.value = 'other';
    if (serviceModel) serviceModel.value = 'normal';
    if (catalogId) catalogId.value = '';
    setUnit(row, item.unit || 'Stk.');
    row.dataset.boReferenceId = item.id || '';
    row.dataset.boReferenceCode = item.code || '';
    row.dataset.boSearchUrl = root.dataset.boSearchUrl || '';
    [description, detail, quantity, purchase, markup, hiddenPrice].forEach((field) => emit(field));
    emit(type, 'change'); emit(serviceModel, 'change');
    row.scrollIntoView({behavior:'smooth', block:'center'});
  };

  const addLegacyPosition = (item) => {
    let row = blankLegacyRow();
    if (!row) {
      row = document.createElement('tr');
      row.innerHTML = '<td><input class="nx-control desc" name="item_description" placeholder="Leistung oder Material"></td><td><input class="nx-control" name="item_quantity" type="number" step="0.001" value="1"></td><td><input class="nx-control" name="item_unit"></td><td><input class="nx-control" name="item_price" type="number" step="0.01"></td><td><input class="nx-control" name="item_tax" type="number" step="0.01"></td><td><button type="button" class="nx-item-remove" aria-label="Position entfernen">×</button></td>';
      table.querySelector('tbody').appendChild(row);
      bindLegacyRow(row);
    }
    row.querySelector('[name="item_description"]').value = `${item.code ? item.code + ' · ' : ''}${item.description}`;
    row.querySelector('[name="item_quantity"]').value = '1';
    row.querySelector('[name="item_unit"]').value = item.unit || 'Stk.';
    row.querySelector('[name="item_price"]').value = item.price || '0';
    row.querySelector('[name="item_tax"]').value = item.tax || '19';
    row.dataset.boReferenceId = item.id || '';
    row.dataset.boReferenceCode = item.code || '';
    row.dataset.boSearchUrl = root.dataset.boSearchUrl || '';
    legacyRecalc();
    row.scrollIntoView({behavior:'smooth', block:'center'});
  };

  const addPosition = (item) => isABBau() ? addABBauPosition(item) : addLegacyPosition(item);

  const render = (items) => {
    results.innerHTML = '';
    if (!items.length) {
      const empty = document.createElement('div');
      empty.className = 'nx-empty';
      empty.textContent = 'Keine bepreiste B&O-Position gefunden. Suche mit anderem Begriff oder VA04-Code.';
      results.appendChild(empty);
      return;
    }
    items.forEach((item) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'nx-quick bo-direct-result';
      const icon = document.createElement('span'); icon.className = 'nx-quick-icon'; icon.textContent = '＋';
      const text = document.createElement('span');
      const title = document.createElement('b'); title.textContent = item.description || item.code;
      const meta = document.createElement('small');
      meta.textContent = `${item.code || 'ohne Code'} · ${money(item.price)} € / ${item.unit || 'Stk.'} · ${item.source || 'B&O'}${item.price_mode === 'EK' ? ' · EK-Fallback' : ''}`;
      text.append(title, meta); button.append(icon, text);
      button.addEventListener('click', () => addPosition(item));
      results.appendChild(button);
    });
  };

  let timer = null;
  let controller = null;
  const search = async () => {
    const query = input.value.trim();
    if (query.length < 2) {
      results.innerHTML = '';
      status.textContent = 'Mindestens 2 Zeichen oder einen VA04-Code eingeben.';
      return;
    }
    controller?.abort(); controller = new AbortController();
    status.textContent = 'B&O-Preisliste wird durchsucht …';
    try {
      const url = new URL(root.dataset.boSearchUrl, window.location.origin);
      url.searchParams.set('q', query);
      const response = await fetch(url, {credentials:'same-origin', headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest'}, signal:controller.signal});
      const raw = await response.text();
      let data = null;
      try { data = raw ? JSON.parse(raw) : {}; } catch (_) { throw new Error('B&O-Suche hat keine gültige Serverantwort erhalten.'); }
      if (!response.ok || !data.ok) throw new Error(data.error || 'B&O-Suche fehlgeschlagen');
      status.textContent = `${data.results.length} bepreiste B&O-Positionen gefunden`;
      render(data.results || []);
    } catch (error) {
      if (error.name === 'AbortError') return;
      status.textContent = error.message || 'B&O-Suche fehlgeschlagen';
      results.innerHTML = '';
    }
  };
  input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 260); });
  input.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); clearTimeout(timer); search(); } });
})();
