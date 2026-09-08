(() => {
  // A+Bau scope engine completion 2026-08-18
  // A+Bau GLOBAL FORM + FIELD VOICE + PRICING HARDENING 2026-08-11
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
    const root = button.closest('[data-field-authorization-root]') || $('[data-field-authorization-root]');
    const voiceUrl = root?.dataset.faVoiceUrl;
    if (!target || !voiceUrl) { button.hidden = true; return; }
    let recorder = null, stream = null, chunks = [];

    const send = async (file) => {
      button.disabled = true; const old = button.textContent; button.textContent = '✦';
      try {
        const fd = new FormData(); fd.append('voice', file); fd.append('mode', 'transcript_only');
        const res = await fetch(voiceUrl, {method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf(button.closest('form') || document)},body:fd});
        const data = await res.json().catch(()=>({}));
        if (res.status === 428 && data.settings_url) throw new Error('KI-Sprachverarbeitung bitte zuerst in den Einstellungen freigeben.');
        if (!res.ok || !data.ok) throw new Error(data.error || 'Sprachaufnahme konnte nicht verarbeitet werden.');
        const transcript = String(data.transcript || '').trim();
        if (!transcript) throw new Error('Kein verständlicher Text erkannt.');
        target.value = [target.value.trim(), transcript].filter(Boolean).join(target.value.trim() ? ' ' : '');
        target.dispatchEvent(new Event('input',{bubbles:true}));
        target.dispatchEvent(new Event('change',{bubbles:true}));
        toast('Sprachaufnahme übernommen.', 'success');
      } catch (err) { toast(err.message || 'Sprachaufnahme fehlgeschlagen.', 'error'); }
      finally { button.disabled = false; button.textContent = old === '■' ? '🎙' : old; }
    };

    const fileFallback = () => {
      const input = document.createElement('input'); input.type = 'file'; input.accept = 'audio/*'; input.setAttribute('capture','microphone'); input.hidden = true;
      input.addEventListener('change', () => { const file = input.files?.[0]; if (file) send(file); input.remove(); }, {once:true});
      document.body.appendChild(input); input.click();
    };

    button.addEventListener('click', async () => {
      if (recorder?.state === 'recording') { recorder.stop(); return; }
      if (!window.MediaRecorder || !navigator.mediaDevices?.getUserMedia) { fileFallback(); return; }
      try {
        stream = await navigator.mediaDevices.getUserMedia({audio:true}); chunks = [];
        const preferred = MediaRecorder.isTypeSupported?.('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
        recorder = new MediaRecorder(stream, preferred ? {mimeType:preferred} : undefined);
        recorder.ondataavailable = (event) => { if (event.data?.size) chunks.push(event.data); };
        recorder.onstop = async () => {
          const mime = recorder.mimeType || 'audio/webm'; const blob = new Blob(chunks,{type:mime});
          stream?.getTracks().forEach((track)=>track.stop()); stream = null; button.classList.remove('is-listening'); button.textContent = '🎙';
          const ext = mime.includes('ogg') ? 'ogg' : (mime.includes('mp4') ? 'm4a' : 'webm');
          await send(new File([blob], `kayi-diktat-${Date.now()}.${ext}`, {type:mime}));
        };
        recorder.start(400); button.classList.add('is-listening'); button.textContent = '■';
        toast('Aufnahme läuft – zum Stoppen erneut tippen.', 'info');
      } catch (_) { toast('Mikrofon konnte nicht geöffnet werden. Bitte Mikrofon-Berechtigung für A+Bau erlauben.', 'error'); }
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
    row.innerHTML = `<input type="hidden" name="item_catalog_id"><input class="nx-control" name="item_description" placeholder="Leistung / Material"><div class="fa-qty"><input class="nx-control" name="item_quantity" type="number" min="0" step="0.01" value="1"><input class="nx-control" name="item_unit" value="Stk."></div><input class="nx-control" name="item_price" type="number" min="0" step="0.01" value="0.00"><select class="nx-control" name="item_tax"><option value="19">19 %</option><option value="7">7 %</option><option value="0">0 %</option></select><button type="button" class="fa-remove-row" data-remove-row>×</button>`;
    $('[name=item_catalog_id]', row).value = values.catalog_id || '';
    $('[name=item_description]', row).value = values.description || values.name || '';
    $('[name=item_quantity]', row).value = values.quantity || '1'; $('[name=item_unit]', row).value = values.unit || 'Stk.'; $('[name=item_price]', row).value = values.unit_price || '0.00'; $('[name=item_tax]', row).value = values.tax_rate || '19';
    return row;
  }


  function bindFieldCatalogSearch(form) {
    const input = $('[data-fa-catalog-query]', form), results = $('[data-fa-catalog-results]', form), status = $('[data-fa-catalog-status]', form);
    const url = form?.dataset.faCatalogUrl; if (!input || !results || !url) return;
    let timer = null, controller = null;
    const render = (rows) => {
      results.innerHTML = '';
      rows.forEach((row) => {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'fa-catalog-result';
        button.innerHTML = `<b>${String(row.name || '').replace(/[&<>]/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}</b><small>${String(row.code || '')} · ${money.format(num(row.price))} / ${String(row.unit || 'Stk.')}</small>`;
        button.addEventListener('click', () => {
          const table = $('[data-price-table]', form); if (!table) return;
          const blank = $$('[data-price-row]', table).find((r) => !$('[name=item_description]', r)?.value.trim());
          const newRow = newPriceRow({catalog_id:row.id,description:row.name,quantity:'1',unit:row.unit,unit_price:row.price,tax_rate:row.tax_rate});
          if (blank) blank.replaceWith(newRow); else table.appendChild(newRow);
          table.dispatchEvent(new Event('input',{bubbles:true})); input.value = ''; results.innerHTML = ''; status.textContent = 'Katalogpreis übernommen; beim Speichern wird er serverseitig nochmals geprüft.';
        }); results.appendChild(button);
      });
      if (!rows.length) status.textContent = 'Keine bepreiste Katalogposition gefunden.';
    };
    input.addEventListener('input', () => {
      clearTimeout(timer); const q = input.value.trim(); results.innerHTML = '';
      if (q.length < 2) { status.textContent = 'Ab 2 Zeichen suchen.'; return; }
      timer = setTimeout(async () => {
        controller?.abort(); controller = new AbortController(); status.textContent = 'Suche …';
        try {
          const res = await fetch(`${url}?q=${encodeURIComponent(q)}`,{credentials:'same-origin',headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest'},signal:controller.signal});
          const data = await res.json(); if (!res.ok || !data.ok) throw new Error(data.error || 'Katalogsuche fehlgeschlagen.'); render(data.results || []);
        } catch (err) { if (err.name !== 'AbortError') status.textContent = err.message; }
      }, 220);
    });
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
      const res = await fetch(form.action, { method: 'POST', credentials: 'same-origin', headers: { 'Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken': csrf(form) }, body: new FormData(form) }); const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || 'Speichern fehlgeschlagen.');
      if (statusEl) { statusEl.textContent = 'Gespeichert.'; statusEl.dataset.type = 'success'; } toast('Dokument sicher gespeichert.', 'success');
      if (form.matches('[data-completion-form]') && data.pdf_url && window.KAYIFieldHandoff?.showResult(data)) { if (button) button.hidden = true; return data; }
      if (data.redirect) window.location.href = data.redirect; else if (data.reload) window.location.reload();
      return data;
    } catch (err) { if (statusEl) { statusEl.textContent = err.message; statusEl.dataset.type = 'error'; } toast(err.message, 'error'); return null; }
    finally { if (button) button.disabled = false; }
  }


  function bindAuthorizationScopePlanner(form) {
    const box = $('[data-auth-scope-planner]', form); if (!box) return;
    const url = box.dataset.authScopeUrl, input = $('[data-auth-scope-input]', box), sendButton = $('[data-auth-scope-send]', box), chat = $('[data-auth-scope-chat]', box), scopeTarget = $('[data-scope-target]', form);
    const addMessage = (text, role = 'ai') => { if (!chat || !String(text || '').trim()) return; const node = document.createElement('div'); node.className = `fa-ai-scope-msg is-${role}`; node.textContent = String(text || '').trim(); chat.appendChild(node); chat.scrollTop = chat.scrollHeight; };
    const renderItems = (items) => { if (!chat || !Array.isArray(items) || !items.length) return; const card = document.createElement('div'); card.className = 'fa-ai-scope-items'; items.forEach((item) => { const row = document.createElement('div'); row.className = 'fa-ai-scope-item'; const label = document.createElement('span'); label.textContent = item.label || 'Leistung'; const qty = document.createElement('b'); qty.textContent = `${item.quantity_display || 'offen'} ${item.unit || ''}`.trim(); row.append(label, qty); card.appendChild(row); }); chat.appendChild(card); chat.scrollTop = chat.scrollHeight; };
    const run = async () => {
      const message = String(input?.value || '').trim(); if (!message || !url || sendButton.disabled) return;
      addMessage(message, 'user'); input.value = ''; sendButton.disabled = true; const old = sendButton.textContent; sendButton.textContent = '✦ Prüft …';
      try {
        const fd = new FormData(); fd.append('text', message);
        const res = await fetch(url, {method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf(form)},body:fd});
        const data = await res.json().catch(() => ({})); if (!res.ok || !data.ok) throw new Error(data.error || 'KI-Leistungsplanung nicht erreichbar.');
        if (data.mode === 'scope') {
          addMessage(data.reply || data.scope_question || 'Leistungsansatz aktualisiert.', 'ai'); renderItems(data.scope_items || []); if (scopeTarget) scopeTarget.value = data.scope || ''; form._appendPriceItems?.(data.items || []);
          const unresolved = (data.items || []).filter((item) => !item.catalog_safe).length; if (unresolved) addMessage(`${unresolved} Position(en) haben keinen sicheren Katalogtreffer; der Preis bleibt dort bewusst offen.`, 'ai');
          toast(data.scope_complete ? 'Leistungsplanung vollständig.' : 'Leistungsplanung aktualisiert – nächste Frage beantworten.', 'success');
        } else { addMessage(data.reply || 'Text strukturiert.', 'ai'); if (scopeTarget) scopeTarget.value = data.scope || scopeTarget.value; if (Array.isArray(data.items) && data.items.length) form._appendPriceItems?.(data.items); }
      } catch (err) { addMessage(err.message || 'KI-Leistungsplanung fehlgeschlagen.', 'ai'); toast(err.message || 'KI-Leistungsplanung fehlgeschlagen.', 'error'); }
      finally { sendButton.disabled = false; sendButton.textContent = old; input?.focus(); }
    };
    sendButton?.addEventListener('click', run); input?.addEventListener('keydown', (event) => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); run(); } });
  }

  function bindAuthorization() {
    const form = $('[data-authorization-form]'); if (!form) return;
    bindPricing(form);
    bindAuthorizationScopePlanner(form);
    bindFieldCatalogSearch(form);
    form.addEventListener('submit', (e) => { e.preventDefault(); const signature = $('[data-signature-data]', form); if (!signature?.value) { toast('Bitte Kundenunterschrift erfassen.', 'error'); return; } postForm(form, $('[data-auth-status]', form)); });
    $('[data-auth-ai]', form)?.addEventListener('click', async (e) => {
      const btn = e.currentTarget, issue = $('[name=issue]', form), text = issue?.value.trim(); if (!text) { toast('Erst Zustand oder Kundenwunsch diktieren.', 'error'); return; }
      btn.disabled = true; const old = btn.textContent; btn.textContent = '✦ KI analysiert …';
      try { const fd = new FormData(); fd.append('text', text); const res = await fetch(btn.dataset.authAi, { method: 'POST', headers: { 'X-CSRFToken': csrf(form) }, body: fd }); const data = await res.json(); if (!res.ok || !data.ok) throw new Error(data.error || 'KI nicht erreichbar'); if (data.mode !== 'scope') issue.value = data.issue || text; $('[data-scope-target]', form).value = data.scope || ''; form._appendPriceItems?.(data.items || []); const scopeChat = $('[data-auth-scope-chat]', form); if (data.mode === 'scope' && scopeChat) { const msg = document.createElement('div'); msg.className = 'fa-ai-scope-msg is-ai'; msg.textContent = data.reply || data.scope_question || 'Leistungsansatz aktualisiert.'; scopeChat.appendChild(msg); } toast(data.mode === 'scope' ? (data.scope_complete ? 'Leistungsplanung vollständig.' : 'Leistungsplanung aktualisiert.') : (data.ai ? 'Diktat strukturiert; Katalogpreise wurden nur bei echten Treffern übernommen.' : 'Text übernommen. Preise bitte manuell ergänzen.'), 'success'); }
      catch (err) { toast(err.message, 'error'); } finally { btn.disabled = false; btn.textContent = old; }
    });
    initSignature($('[data-signature-canvas]', form), $('[data-signature-data]', form), $('[data-signature-clear]', form));
  }

  function bindCompletion() {
    const form = $('[data-completion-form]'); if (!form) return;
    initSignature($('[data-completion-signature-canvas]', form), $('[data-completion-signature-data]', form), $('[data-completion-signature-clear]', form));
    form.addEventListener('submit', (e) => { e.preventDefault(); const reviewed = $('[data-customer-reviewed]', form); const signature = $('[data-completion-signature-data]', form); if (!reviewed?.checked) { toast('Bitte den Abschluss gemeinsam mit dem Kunden prüfen.', 'error'); return; } if (!signature?.value) { toast('Bitte Kundenunterschrift zum Abschluss erfassen.', 'error'); return; } postForm(form, $('[data-completion-status]', form)); });
    $('[data-completion-ai]', form)?.addEventListener('click', async (e) => {
      const btn = e.currentTarget, report = $('[name=report_text]', form); if (!report?.value.trim()) { toast('Erst Arbeitsbericht diktieren oder schreiben.', 'error'); return; }
      btn.disabled = true; const fd = new FormData(); fd.append('text', report.value);
      try { const res = await fetch(btn.dataset.completionAi, { method: 'POST', headers: { 'X-CSRFToken': csrf(form) }, body: fd }); const data = await res.json(); if (!res.ok || !data.ok) throw new Error(data.error || 'KI nicht erreichbar'); report.value = data.report || report.value; $('[data-services-target]', form).value = data.services || ''; $('[data-material-target]', form).value = data.material || ''; toast('Arbeitsbericht strukturiert.', 'success'); } catch (err) { toast(err.message, 'error'); } finally { btn.disabled = false; }
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

  bindCustomerMode(); $$('[data-voice-button]').forEach(speechButton); bindPhotos(); bindAuthorization(); bindCompletion(); /* global kayi-next.js owns Zeiterfassung */ bindRevisionToggle();
})();


// A+Bau ANDROID VOICE CAPTURE HOTFIX 2026-08-11
(() => {
  'use strict';
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const endpoint = '/field/voice/transcribe/';
  const states = new WeakMap();

  const csrf = (root = document) => $('input[name="csrfmiddlewaretoken"]', root)?.value || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
  const toast = (message, type = 'info') => {
    let el = $('.fa-toast');
    if (!el) { el = document.createElement('div'); el.className = 'fa-toast'; document.body.appendChild(el); }
    el.textContent = message; el.dataset.type = type; el.classList.add('show');
    clearTimeout(el._voiceTimer); el._voiceTimer = setTimeout(() => el.classList.remove('show'), 4300);
  };
  const targetFor = (button) => {
    const box = button.closest('.fa-voice-field,.fa-block,form') || document;
    return $('[data-voice-target]', box) || $('[data-voice-target]');
  };
  const appendTranscript = (target, transcript) => {
    const before = String(target.value || '').trim();
    target.value = [before, String(transcript || '').trim()].filter(Boolean).join(before ? ' ' : '');
    target.dispatchEvent(new Event('input', {bubbles:true}));
    target.dispatchEvent(new Event('change', {bubbles:true}));
    target.focus({preventScroll:true});
  };
  const sendVoice = async (button, target, file) => {
    const old = button.textContent;
    button.disabled = true; button.textContent = '✦';
    try {
      const data = new FormData(); data.append('voice', file); data.append('csrfmiddlewaretoken', csrf(button.closest('form') || document));
      const response = await fetch(endpoint, {
        method:'POST', credentials:'same-origin', body:data,
        headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf(button.closest('form') || document)},
      });
      const result = await response.json().catch(()=>({}));
      if (response.status === 428) throw new Error(result.error || 'Bitte KI-Verarbeitung zuerst in den Einstellungen freigeben.');
      if (!response.ok || !result.ok) throw new Error(result.error || 'Sprachaufnahme konnte nicht verarbeitet werden.');
      appendTranscript(target, result.transcript);
      toast('Sprachaufnahme übernommen.', 'success');
    } catch (error) {
      toast(error.message || 'Sprachaufnahme konnte nicht verarbeitet werden.', 'error');
    } finally {
      button.disabled = false; button.textContent = old === '■' ? '🎙' : old;
    }
  };
  const nativeAudioCapture = (button, target) => {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = 'audio/*'; input.setAttribute('capture','microphone'); input.hidden = true;
    input.addEventListener('change', async () => {
      const file = input.files?.[0];
      if (file) await sendVoice(button, target, file);
      input.remove();
    }, {once:true});
    document.body.appendChild(input);
    try { input.click(); } catch (_) { toast('Bitte Mikrofon in den Website-Einstellungen erlauben oder eine Audiodatei auswählen.', 'error'); }
  };

  const handleVoiceButton = async (button) => {
    const target = targetFor(button);
    if (!target) { toast('Zielfeld für die Spracheingabe wurde nicht gefunden.', 'error'); return; }
    const current = states.get(button);
    if (current?.recorder?.state === 'recording') { current.recorder.stop(); return; }
    if (!window.MediaRecorder || !navigator.mediaDevices?.getUserMedia) {
      nativeAudioCapture(button, target); return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio:true});
      const chunks = [];
      const preferred = MediaRecorder.isTypeSupported?.('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
      const recorder = new MediaRecorder(stream, preferred ? {mimeType:preferred} : undefined);
      states.set(button, {recorder, stream});
      recorder.ondataavailable = (event) => { if (event.data?.size) chunks.push(event.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        states.delete(button); button.classList.remove('is-listening'); button.textContent = '🎙';
        const mime = recorder.mimeType || 'audio/webm';
        const ext = mime.includes('ogg') ? 'ogg' : (mime.includes('mp4') ? 'm4a' : 'webm');
        const blob = new Blob(chunks, {type:mime});
        if (!blob.size) { toast('Keine Audiodaten aufgenommen.', 'error'); return; }
        await sendVoice(button, target, new File([blob], `kayi-diktat-${Date.now()}.${ext}`, {type:mime}));
      };
      recorder.start(400); button.classList.add('is-listening'); button.textContent = '■';
      toast('Aufnahme läuft – zum Stoppen erneut tippen.', 'info');
    } catch (error) {
      states.delete(button); button.classList.remove('is-listening'); button.textContent = '🎙';
      toast('Browser-Mikrofon blockiert – A+Bau öffnet jetzt die Audioaufnahme des Geräts.', 'info');
      nativeAudioCapture(button, target);
    }
  };

  const preparePanelFile = (box, file) => {
    const input = $('[data-field-voice-file]', box), preview = $('[data-field-voice-preview]', box), transcribe = $('[data-field-transcribe]', box), status = $('[data-field-record-status]', box);
    if (input && file && input.files?.[0] !== file) {
      try { const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files; } catch (_) {}
    }
    if (preview && file) { preview.src = URL.createObjectURL(file); preview.hidden = false; }
    if (transcribe) transcribe.hidden = false;
    if (status) { status.textContent = 'Aufnahme bereit. Jetzt mit KI auswerten.'; status.classList.remove('is-live'); }
  };
  const bindPanelInput = (box) => {
    const input = $('[data-field-voice-file]', box); if (!input || input.dataset.androidVoiceBound === '1') return input;
    input.dataset.androidVoiceBound = '1'; input.accept = 'audio/*'; input.setAttribute('capture','microphone');
    input.addEventListener('change', () => { const file = input.files?.[0]; if (file) preparePanelFile(box, file); });
    return input;
  };
  const handlePanelRecord = async (button) => {
    const box = button.closest('[data-field-voice]'); if (!box) return;
    const consent = $('[data-field-voice-consent]', box), status = $('[data-field-record-status]', box), input = bindPanelInput(box);
    if (!consent?.checked) { toast('Bitte zuerst der Sprachaufnahme zustimmen.', 'error'); consent?.focus(); return; }
    const current = states.get(button);
    if (current?.recorder?.state === 'recording') { current.recorder.stop(); return; }
    if (!window.MediaRecorder || !navigator.mediaDevices?.getUserMedia) { input?.click(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio:true}); const chunks = [];
      const preferred = MediaRecorder.isTypeSupported?.('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
      const recorder = new MediaRecorder(stream, preferred ? {mimeType:preferred} : undefined);
      states.set(button, {recorder,stream});
      recorder.ondataavailable = (event) => { if (event.data?.size) chunks.push(event.data); };
      recorder.onstop = () => {
        stream.getTracks().forEach((track)=>track.stop()); states.delete(button); button.textContent = '🎙 Neue Aufnahme';
        const mime = recorder.mimeType || 'audio/webm', ext = mime.includes('ogg') ? 'ogg' : (mime.includes('mp4') ? 'm4a' : 'webm');
        const file = new File([new Blob(chunks,{type:mime})], `einsatz-${Date.now()}.${ext}`, {type:mime}); preparePanelFile(box,file);
      };
      recorder.start(400); button.textContent = '■ Aufnahme stoppen'; if (status) { status.textContent='Aufnahme läuft …'; status.classList.add('is-live'); }
    } catch (_) {
      if (status) status.textContent = 'Browser-Mikrofon blockiert. Audioaufnahme des Geräts wird geöffnet …';
      toast('Browser-Mikrofon blockiert – Audioaufnahme des Geräts wird geöffnet.', 'info'); input?.click();
    }
  };

  // Capture phase intentionally wins over every legacy SpeechRecognition/getUserMedia listener.
  document.addEventListener('click', (event) => {
    const voiceButton = event.target.closest?.('[data-voice-button]');
    const panelRecord = event.target.closest?.('[data-field-record]');
    if (!voiceButton && !panelRecord) return;
    event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation();
    if (voiceButton) handleVoiceButton(voiceButton);
    else handlePanelRecord(panelRecord);
  }, true);

  const enable = () => {
    $$('[data-voice-button]').forEach((button) => { button.hidden = false; button.disabled = false; button.title = 'Spracheingabe'; });
    $$('[data-field-voice]').forEach(bindPanelInput);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', enable); else enable();
})();
