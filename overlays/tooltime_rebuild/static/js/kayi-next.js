(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const body = document.body;
  $('[data-nx-menu]')?.addEventListener('click', () => body.classList.toggle('nx-menu-open'));
  document.addEventListener('click', (event) => {
    if (!body.classList.contains('nx-menu-open')) return;
    if (event.target.closest('.nx-sidebar') || event.target.closest('[data-nx-menu]')) return;
    body.classList.remove('nx-menu-open');
  });

  $$('[data-tabs]').forEach((tabs) => {
    const buttons = $$('[data-tab]', tabs);
    buttons.forEach((button) => button.addEventListener('click', () => {
      const name = button.dataset.tab;
      buttons.forEach((item) => item.classList.toggle('is-active', item === button));
      $$('[data-tab-panel]', tabs.parentElement).forEach((panel) => panel.classList.toggle('is-active', panel.dataset.tabPanel === name));
    }));
  });

  const csrf = () => document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';

  $$('[data-time-toggle]').forEach((button) => {
    button.addEventListener('click', async () => {
      if (button.disabled) return;
      button.disabled = true;
      try {
        const response = await fetch(button.dataset.timeToggle, {method:'POST', headers:{'X-CSRFToken':csrf(), 'X-Requested-With':'XMLHttpRequest'}});
        const data = await response.json();
        if (!data.ok) throw new Error(data.error || 'Fehler');
        button.textContent = data.state === 'running' ? '■ Arbeit stoppen' : '▶ Arbeit starten';
        button.classList.toggle('nx-btn-danger', data.state === 'running');
        button.classList.toggle('nx-btn-accent', data.state !== 'running');
      } catch (error) {
        alert(error.message || 'Zeiterfassung konnte nicht geändert werden.');
      } finally {
        button.disabled = false;
      }
    });
  });

  const addItemRow = (table, values = {}) => {
    const body = table.querySelector('tbody');
    const row = document.createElement('tr');
    row.innerHTML = `
      <td><input class="nx-control desc" name="item_description" value="${String(values.description || '').replace(/"/g,'&quot;')}" placeholder="Leistung oder Material"></td>
      <td><input class="nx-control" name="item_quantity" type="number" step="0.001" value="${values.quantity ?? 1}"></td>
      <td><input class="nx-control" name="item_unit" value="${values.unit || 'Stk.'}"></td>
      <td><input class="nx-control" name="item_price" type="number" step="0.01" value="${values.price ?? 0}"></td>
      <td><input class="nx-control" name="item_tax" type="number" step="0.01" value="${values.tax ?? 19}"></td>
      <td><button type="button" class="nx-item-remove" aria-label="Position entfernen">×</button></td>`;
    row.querySelector('.nx-item-remove').addEventListener('click', () => { row.remove(); recalcDocument(table); });
    $$('input', row).forEach((input) => input.addEventListener('input', () => recalcDocument(table)));
    body.append(row);
    recalcDocument(table);
  };

  const recalcDocument = (table) => {
    let net = 0;
    let tax = 0;
    $$('tbody tr', table).forEach((row) => {
      const qty = parseFloat(row.querySelector('[name="item_quantity"]')?.value || 0);
      const price = parseFloat(row.querySelector('[name="item_price"]')?.value || 0);
      const rate = parseFloat(row.querySelector('[name="item_tax"]')?.value || 0);
      const line = qty * price;
      net += line;
      tax += line * rate / 100;
    });
    const discount = parseFloat(document.querySelector('[name="discount_percent"]')?.value || 0);
    net = net * (1 - Math.max(0, discount) / 100);
    const set = (key, value) => { const el = document.querySelector(`[data-total="${key}"]`); if (el) el.textContent = value.toLocaleString('de-DE',{style:'currency',currency:'EUR'}); };
    set('net', net); set('tax', tax); set('gross', net + tax);
  };

  $$('[data-document-items]').forEach((table) => {
    table.querySelector('[data-add-item]')?.addEventListener('click', () => addItemRow(table));
    $$('tbody tr', table).forEach((row) => {
      row.querySelector('.nx-item-remove')?.addEventListener('click', () => { row.remove(); recalcDocument(table); });
      $$('input', row).forEach((input) => input.addEventListener('input', () => recalcDocument(table)));
    });
    document.querySelector('[name="discount_percent"]')?.addEventListener('input', () => recalcDocument(table));
    recalcDocument(table);
  });

  $$('[data-catalog-item]').forEach((button) => {
    button.addEventListener('click', () => {
      const table = document.querySelector('[data-document-items]');
      if (!table) return;
      addItemRow(table, {
        description: button.dataset.name,
        quantity: 1,
        unit: button.dataset.unit || 'Stk.',
        price: button.dataset.price || 0,
        tax: button.dataset.tax || 19,
      });
    });
  });

  const setupVoice = (root) => {
    const button = $('[data-voice]', root);
    const target = $('[data-voice-target]', root);
    if (!button || !target) return;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      button.title = 'Spracheingabe wird von diesem Browser nicht unterstützt';
      button.disabled = true;
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'de-DE';
    recognition.interimResults = true;
    recognition.continuous = true;
    let base = '';
    recognition.onstart = () => { base = target.value.trim(); button.classList.add('is-listening'); button.textContent = '■'; };
    recognition.onend = () => { button.classList.remove('is-listening'); button.textContent = '🎙'; };
    recognition.onresult = (event) => {
      let transcript = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) transcript += event.results[i][0].transcript;
      target.value = `${base}${base ? ' ' : ''}${transcript}`.trim();
      target.dispatchEvent(new Event('input',{bubbles:true}));
    };
    button.addEventListener('click', () => {
      if (button.classList.contains('is-listening')) recognition.stop(); else recognition.start();
    });
  };
  $$('[data-voice-box]').forEach(setupVoice);

  $$('[data-ai-structure]').forEach((button) => {
    button.addEventListener('click', async () => {
      const root = button.closest('[data-documentation-form]') || document;
      const report = $('[name="report_text"]', root);
      if (!report?.value.trim()) return;
      button.disabled = true;
      const old = button.textContent;
      button.textContent = 'AI strukturiert …';
      const data = new FormData();
      data.append('text', report.value);
      data.append('csrfmiddlewaretoken', csrf());
      try {
        const response = await fetch(button.dataset.aiStructure,{method:'POST',body:data,headers:{'X-Requested-With':'XMLHttpRequest'}});
        const result = await response.json();
        if (!result.ok) throw new Error(result.error || 'AI Fehler');
        report.value = result.report || report.value;
        const services = $('[name="services"]',root); if (services && result.services) services.value = result.services;
        const material = $('[name="material"]',root); if (material && result.material) material.value = result.material;
      } catch (error) { alert(error.message || 'AI konnte den Bericht nicht strukturieren.'); }
      finally { button.disabled = false; button.textContent = old; }
    });
  });

  const setupSignature = (canvas) => {
    const ctx = canvas.getContext('2d');
    let drawing = false;
    const resize = () => {
      const ratio = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      const previous = canvas.toDataURL();
      canvas.width = Math.max(1, rect.width * ratio);
      canvas.height = Math.max(1, rect.height * ratio);
      ctx.scale(ratio, ratio);
      ctx.lineWidth = 2.2; ctx.lineCap = 'round'; ctx.strokeStyle = '#111418';
      if (previous && previous !== 'data:,') { const image = new Image(); image.onload = () => ctx.drawImage(image,0,0,rect.width,rect.height); image.src = previous; }
    };
    resize();
    const point = (event) => { const rect = canvas.getBoundingClientRect(); const p = event.touches?.[0] || event; return {x:p.clientX-rect.left,y:p.clientY-rect.top}; };
    const start = (event) => { drawing = true; const p = point(event); ctx.beginPath(); ctx.moveTo(p.x,p.y); event.preventDefault(); };
    const move = (event) => { if (!drawing) return; const p=point(event); ctx.lineTo(p.x,p.y); ctx.stroke(); event.preventDefault(); };
    const end = () => { drawing = false; const hidden = canvas.parentElement.querySelector('[name="signature_data"]'); if (hidden) hidden.value = canvas.toDataURL('image/png'); };
    canvas.addEventListener('pointerdown',start); canvas.addEventListener('pointermove',move); window.addEventListener('pointerup',end);
    canvas.parentElement.querySelector('[data-signature-clear]')?.addEventListener('click', () => { ctx.clearRect(0,0,canvas.width,canvas.height); const hidden=canvas.parentElement.querySelector('[name="signature_data"]'); if(hidden)hidden.value=''; });
  };
  $$('canvas.nx-signature').forEach(setupSignature);

  const DB_NAME = 'kayi-next-offline';
  const STORE = 'requests';
  const dbOpen = () => new Promise((resolve,reject) => {
    const request = indexedDB.open(DB_NAME,1);
    request.onupgradeneeded = () => { if (!request.result.objectStoreNames.contains(STORE)) request.result.createObjectStore(STORE,{keyPath:'id',autoIncrement:true}); };
    request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
  });
  const queueRequest = async (url, formData) => {
    const values = [];
    for (const [key,value] of formData.entries()) values.push([key,value]);
    const db = await dbOpen();
    await new Promise((resolve,reject)=>{ const tx=db.transaction(STORE,'readwrite'); tx.objectStore(STORE).add({url,values,created:Date.now()}); tx.oncomplete=resolve; tx.onerror=()=>reject(tx.error); });
  };
  const flushQueue = async () => {
    if (!navigator.onLine) return;
    const db = await dbOpen();
    const items = await new Promise((resolve,reject)=>{ const tx=db.transaction(STORE,'readonly'); const req=tx.objectStore(STORE).getAll(); req.onsuccess=()=>resolve(req.result); req.onerror=()=>reject(req.error); });
    for (const item of items) {
      const data = new FormData(); item.values.forEach(([key,value])=>data.append(key,value));
      try {
        const response = await fetch(item.url,{method:'POST',body:data,headers:{'X-Requested-With':'XMLHttpRequest'}});
        if (!response.ok) continue;
        await new Promise((resolve,reject)=>{ const tx=db.transaction(STORE,'readwrite'); tx.objectStore(STORE).delete(item.id); tx.oncomplete=resolve; tx.onerror=()=>reject(tx.error); });
      } catch (_) { break; }
    }
  };
  window.addEventListener('online',flushQueue); flushQueue().catch(()=>{});

  $$('form[data-documentation-form]').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const submit = form.querySelector('[type="submit"]'); if(submit) submit.disabled=true;
      const data = new FormData(form);
      try {
        if (!navigator.onLine) {
          await queueRequest(form.action,data);
          alert('Offline gespeichert. Die Dokumentation wird automatisch synchronisiert, sobald wieder Internet verfügbar ist.');
          return;
        }
        const response = await fetch(form.action,{method:'POST',body:data,headers:{'X-Requested-With':'XMLHttpRequest'}});
        const result = await response.json();
        if (!result.ok) throw new Error(result.error || 'Speichern fehlgeschlagen');
        window.location.href = result.redirect || window.location.href;
      } catch (error) {
        try { await queueRequest(form.action,data); alert('Verbindung unterbrochen. Die Dokumentation wurde lokal gespeichert und wird später synchronisiert.'); }
        catch (_) { alert(error.message || 'Dokumentation konnte nicht gespeichert werden.'); }
      } finally { if(submit) submit.disabled=false; }
    });
  });
})();
