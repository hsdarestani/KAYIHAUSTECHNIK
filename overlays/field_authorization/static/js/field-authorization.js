(() => {
  'use strict';
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const $ = (s, r = document) => r.querySelector(s);
  const money = new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' });
  const num = (v) => Number(String(v ?? '').replace(',', '.')) || 0;
  const csrf = (form) => $('input[name=csrfmiddlewaretoken]', form)?.value || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';

  function toast(message, type = 'info') {
    let el = $('.fa-toast');
    if (!el) { el = document.createElement('div'); el.className = 'fa-toast'; document.body.appendChild(el); }
    el.textContent = message; el.dataset.type = type; el.classList.add('show');
    clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove('show'), 3500);
  }

  function bindCustomerMode() {
    const form = $('[data-quick-job-form]'); if (!form) return;
    const existing = $('[data-existing-customer]', form), fresh = $('[data-new-customer]', form), select = $('[data-customer-select]', form);
    function sync() {
      const mode = $('input[name=customer_mode]:checked', form)?.value || 'existing';
      existing.hidden = mode !== 'existing'; fresh.hidden = mode !== 'new';
      if (select) select.required = mode === 'existing';
    }
    $$('input[name=customer_mode]', form).forEach((r) => r.addEventListener('change', sync)); sync();
    $('[data-customer-filter]', form)?.addEventListener('input', (e) => {
      const q = e.target.value.trim().toLowerCase();
      $$('option', select).forEach((o, i) => { if (i === 0) return; o.hidden = q && !(o.dataset.search || o.textContent.toLowerCase()).includes(q); });
    });
  }

  function speechButton(button) {
    const box = button.closest('.fa-voice-field, .fa-block, form') || document;
    const target = $('[data-voice-target]', box) || $('[data-voice-target]');
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition || !target) { button.hidden = true; return; }
    let active = false, recognition;
    button.addEventListener('click', () => {
      if (active) { recognition?.stop(); return; }
      recognition = new Recognition(); recognition.lang = 'de-DE'; recognition.continuous = true; recognition.interimResults = true;
      const base = target.value.trim();
      recognition.onstart = () => { active = true; button.classList.add('is-listening'); button.textContent = '■'; };
      recognition.onresult = (ev) => {
        let final = '', interim = '';
        for (let i = ev.resultIndex; i < ev.results.length; i++) { const text = ev.results[i][0].transcript; if (ev.results[i].isFinal) final += text + ' '; else interim += text; }
        if (final) { target.value = [base, final.trim()].filter(Boolean).join(base ? ' ' : ''); target.dispatchEvent(new Event('input', { bubbles: true })); }
        target.dataset.interim = interim;
      };
      recognition.onerror = () => toast('Spracherkennung konnte nicht gestartet werden.', 'error');
      recognition.onend = () => { active = false; button.classList.remove('is-listening'); button.textContent = '🎙'; };
      recognition.start();
    });
  }

  function bindPhotos() {
    $$('[data-photo-input]').forEach((input) => input.addEventListener('change', () => {
      const key = input.dataset.photoInput, preview = $(`[data-photo-preview="${key}"]`); if (!preview) return;
      preview.innerHTML = '';
      [...input.files].slice(0, 12).forEach((file, index) => {
        const figure = document.createElement('figure'); const img = document.createElement('img'); const cap = document.createElement('figcaption');
        img.src = URL.createObjectURL(file); img.onload = () => URL.revokeObjectURL(img.src); cap.textContent = `${index + 1}. ${file.name}`; figure.append(img, cap); preview.appendChild(figure);
      });
    }));
  }

  function initSignature(canvas, hidden, clearButton) {
    if (!canvas || !hidden) return;
    const ctx = canvas.getContext('2d'); let drawing = false, dirty = false;
    function resize() {
      const rect = canvas.getBoundingClientRect(), ratio = Math.min(window.devicePixelRatio || 1, 2); const previous = dirty ? canvas.toDataURL() : null;
      canvas.width = Math.max(320, rect.width * ratio); canvas.height = 170 * ratio; ctx.setTransform(ratio, 0, 0, ratio, 0, 0); ctx.lineWidth = 2.2; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = '#172126';
      if (previous) { const image = new Image(); image.onload = () => ctx.drawImage(image, 0, 0, rect.width, 170); image.src = previous; }
    }
    function point(e) { const r = canvas.getBoundingClientRect(); const t = e.touches?.[0] || e; return { x: t.clientX - r.left, y: t.clientY - r.top }; }
    function start(e) { e.preventDefault(); drawing = true; const p = point(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); canvas.setPointerCapture?.(e.pointerId); }
    function move(e) { if (!drawing) return; e.preventDefault(); const p = point(e); ctx.lineTo(p.x, p.y); ctx.stroke(); dirty = true; hidden.value = canvas.toDataURL('image/png'); }
    function end(e) { if (!drawing) return; drawing = false; hidden.value = dirty ? canvas.toDataURL('image/png') : ''; canvas.releasePointerCapture?.(e.pointerId); }
    canvas.addEventListener('pointerdown', start); canvas.addEventListener('pointermove', move); canvas.addEventListener('pointerup', end); canvas.addEventListener('pointercancel', end);
    clearButton?.addEventListener('click', () => { ctx.clearRect(0, 0, canvas.width, canvas.height); dirty = false; hidden.value = ''; });
    resize(); window.addEventListener('resize', resize);
  }

  function newPriceRow(values = {}) {
    const row = document.createElement('div'); row.className = 'fa-price-row'; row.dataset.priceRow = '';
    row.innerHTML = `<input class="nx-control" name="item_description" placeholder="Leistung / Material"><div class="fa-qty"><input class="nx-control" name="item_quantity" type="number" min="0" step="0.01" value="1"><input class="nx-control" name="item_unit" value="Stk."></div><input class="nx-control" name="item_price" type="number" min="0" step="0.01" value="0.00"><select class="nx-control" name="item_tax"><option value="19">19 %</option><option value="7">7 %</option><option value="0">0 %</option></select><button type="button" class="fa-remove-row" data-remove-row>×</button>`;
    $('[name=item_description]', row).value = values.description || '';
    $('[name=item_quantity]', row).value = values.quantity || '1'; $('[name=item_unit]', row).value = values.unit || 'Stk.'; $('[name=item_price]', row).value = values.unit_price || '0.00'; $('[name=item_tax]', row).value = values.tax_rate || '19';
    return row;
  }

  function bindPricing(form) {
    const table = $('[data-price-table]', form); if (!table) return;
    const netEl = $('[data-total-net]', form), taxEl = $('[data-total-tax]', form), grossEl = $('[data-total-gross]', form), capWrap = $('[data-cap-wrap]', form);
    function calc() {
      let net = 0, tax = 0;
      $$('[data-price-row]', table).forEach((row) => { const q = num($('[name=item_quantity]', row)?.value), p = num($('[name=item_price]', row)?.value), t = num($('[name=item_tax]', row)?.value); const n = q * p; net += n; tax += n * t / 100; });
      if (netEl) netEl.textContent = money.format(net); if (taxEl) taxEl.textContent = money.format(tax); if (grossEl) grossEl.textContent = money.format(net + tax);
    }
    table.addEventListener('input', calc); table.addEventListener('change', calc);
    table.addEventListener('click', (e) => { const b = e.target.closest('[data-remove-row]'); if (!b) return; const rows = $$('[data-price-row]', table); if (rows.length > 1) b.closest('[data-price-row]').remove(); else $$('input', rows[0]).forEach(i => { if (i.name === 'item_quantity') i.value = 1; else if (i.name === 'item_unit') i.value = 'Stk.'; else i.value = i.name === 'item_tax' ? i.value : ''; }); calc(); });
    $('[data-add-price-row]', form)?.addEventListener('click', () => { table.appendChild(newPriceRow()); calc(); });
    $$('input[name=pricing_mode]', form).forEach((r) => r.addEventListener('change', () => { const mode = $('input[name=pricing_mode]:checked', form)?.value; if (capWrap) capWrap.hidden = mode === 'fixed'; }));
    form._appendPriceItems = (items) => { $$('[data-price-row]', table).forEach((row) => row.remove()); (items?.length ? items : [{}]).forEach((item) => table.appendChild(newPriceRow(item))); calc(); };
    calc();
  }

  async function postForm(form, statusEl) {
    const button = $('button[type=submit]', form); if (button) button.disabled = true; if (statusEl) { statusEl.textContent = 'Wird sicher gespeichert …'; statusEl.dataset.type = 'working'; }
    try {
      const res = await fetch(form.action, { method: 'POST', headers: { 'X-CSRFToken': csrf(form) }, body: new FormData(form) }); const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || 'Speichern fehlgeschlagen.');
      if (statusEl) { statusEl.textContent = 'Gespeichert.'; statusEl.dataset.type = 'success'; } toast('Dokument sicher gespeichert.', 'success');
      if (data.redirect) window.location.href = data.redirect; else if (data.reload) window.location.reload();
      return data;
    } catch (err) { if (statusEl) { statusEl.textContent = err.message; statusEl.dataset.type = 'error'; } toast(err.message, 'error'); return null; }
    finally { if (button) button.disabled = false; }
  }

  function bindAuthorization() {
    const form = $('[data-authorization-form]'); if (!form) return;
    bindPricing(form);
    form.addEventListener('submit', (e) => { e.preventDefault(); const signature = $('[data-signature-data]', form); if (!signature?.value) { toast('Bitte Kundenunterschrift erfassen.', 'error'); return; } postForm(form, $('[data-auth-status]', form)); });
    $('[data-auth-ai]', form)?.addEventListener('click', async (e) => {
      const btn = e.currentTarget, issue = $('[name=issue]', form), text = issue?.value.trim(); if (!text) { toast('Erst Zustand oder Kundenwunsch diktieren.', 'error'); return; }
      btn.disabled = true; const old = btn.textContent; btn.textContent = '✦ AI analysiert …';
      try { const fd = new FormData(); fd.append('text', text); const res = await fetch(btn.dataset.authAi, { method: 'POST', headers: { 'X-CSRFToken': csrf(form) }, body: fd }); const data = await res.json(); if (!res.ok || !data.ok) throw new Error(data.error || 'AI nicht erreichbar'); issue.value = data.issue || text; $('[data-scope-target]', form).value = data.scope || ''; form._appendPriceItems?.(data.items || []); toast(data.ai ? 'Diktat strukturiert; Katalogpreise wurden nur bei echten Treffern übernommen.' : 'Text übernommen. Preise bitte manuell ergänzen.', 'success'); }
      catch (err) { toast(err.message, 'error'); } finally { btn.disabled = false; btn.textContent = old; }
    });
    initSignature($('[data-signature-canvas]', form), $('[data-signature-data]', form), $('[data-signature-clear]', form));
  }

  function bindCompletion() {
    const form = $('[data-completion-form]'); if (!form) return;
    initSignature($('[data-completion-signature-canvas]', form), $('[data-completion-signature-data]', form), $('[data-completion-signature-clear]', form));
    form.addEventListener('submit', (e) => { e.preventDefault(); postForm(form, $('[data-completion-status]', form)); });
    $('[data-completion-ai]', form)?.addEventListener('click', async (e) => {
      const btn = e.currentTarget, report = $('[name=report_text]', form); if (!report?.value.trim()) { toast('Erst Arbeitsbericht diktieren oder schreiben.', 'error'); return; }
      btn.disabled = true; const fd = new FormData(); fd.append('text', report.value);
      try { const res = await fetch(btn.dataset.completionAi, { method: 'POST', headers: { 'X-CSRFToken': csrf(form) }, body: fd }); const data = await res.json(); if (!res.ok || !data.ok) throw new Error(data.error || 'AI nicht erreichbar'); report.value = data.report || report.value; $('[data-services-target]', form).value = data.services || ''; $('[data-material-target]', form).value = data.material || ''; toast('Arbeitsbericht strukturiert.', 'success'); } catch (err) { toast(err.message, 'error'); } finally { btn.disabled = false; }
    });
  }

  function bindTimeToggle() {
    const button = $('[data-time-toggle]'); if (!button) return;
    button.addEventListener('click', async () => {
      if (button.disabled) return; button.disabled = true;
      try { const res = await fetch(button.dataset.timeToggle, { method: 'POST', headers: { 'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '' } }); const data = await res.json(); if (!res.ok || !data.ok) throw new Error(data.error || 'Zeiterfassung fehlgeschlagen'); window.location.reload(); } catch (err) { toast(err.message, 'error'); button.disabled = false; }
    });
  }

  function bindRevisionToggle() {
    $('[data-toggle-revision]')?.addEventListener('click', () => { const card = $('[data-authorization-card]'); if (card) { card.hidden = !card.hidden; if (!card.hidden) card.scrollIntoView({ behavior: 'smooth', block: 'start' }); } });
  }

  bindCustomerMode(); $$('[data-voice-button]').forEach(speechButton); bindPhotos(); bindAuthorization(); bindCompletion(); bindTimeToggle(); bindRevisionToggle();
})();
