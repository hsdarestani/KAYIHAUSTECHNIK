// A+Bau AI scope authoritative catalog 2026-08-16
// A+Bau deterministic trade scope planner 2026-08-16
(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const body = document.body;
  // A+BAU_MOBILE_NAV
  const mobileMenuButton = $('[data-nx-menu]');
  const mobileMenuOverlay = $('[data-nx-menu-overlay]');
  const mobileSidebar = $('.nx-sidebar');
  const mobileViewport = () => window.matchMedia('(max-width: 860px)').matches;
  const setMobileMenu = (open) => {
    const next = Boolean(open && mobileViewport());
    body.classList.toggle('nx-menu-open', next);
    mobileMenuButton?.setAttribute('aria-expanded', next ? 'true' : 'false');
    if (next && $('[data-assistant-drawer][aria-hidden="false"]')) $('[data-assistant-close]')?.click();
  };
  mobileMenuButton?.addEventListener('click', () => setMobileMenu(!body.classList.contains('nx-menu-open')));
  mobileMenuOverlay?.addEventListener('click', () => setMobileMenu(false));
  mobileSidebar?.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
    if (mobileViewport()) setMobileMenu(false);
  }));
  document.addEventListener('click', (event) => {
    if (!body.classList.contains('nx-menu-open')) return;
    if (event.target.closest('.nx-sidebar') || event.target.closest('[data-nx-menu]')) return;
    setMobileMenu(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && body.classList.contains('nx-menu-open')) setMobileMenu(false);
  });
  const desktopMenuQuery = window.matchMedia('(min-width: 861px)');
  const resetMobileMenu = (event) => { if (event.matches) setMobileMenu(false); };
  if (desktopMenuQuery.addEventListener) desktopMenuQuery.addEventListener('change', resetMobileMenu);
  else desktopMenuQuery.addListener?.(resetMobileMenu);

  $$('[data-ab-brand-image]').forEach((image) => {
    const frame = image.closest('.ab-brand-logo');
    const syncLogo = () => frame?.classList.toggle('is-missing', !image.complete || image.naturalWidth === 0);
    image.addEventListener('load', syncLogo);
    image.addEventListener('error', syncLogo);
    syncLogo();
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
    if (button.dataset.abTimeBound === '1') return;
    button.dataset.abTimeBound = '1';
    button.addEventListener('click', async () => {
      if (button.disabled) return;
      button.disabled = true;
      const old = button.textContent;
      button.textContent = 'Wird gespeichert …';
      try {
        const response = await fetch(button.dataset.timeToggle, {method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'}});
        const raw = await response.text();
        let data = null;
        try { data = raw ? JSON.parse(raw) : {}; } catch (_) {
          if (response.redirected || response.status === 401 || response.status === 403 || /text\/html/i.test(response.headers.get('content-type') || '')) throw new Error('Die Sitzung oder Berechtigung ist abgelaufen. Bitte Seite neu laden und erneut versuchen.');
          throw new Error('Die Zeiterfassung hat keine gültige Serverantwort erhalten.');
        }
        if (!response.ok || !data.ok) throw new Error(data?.error || `Zeiterfassung fehlgeschlagen (${response.status}).`);
        button.textContent = data.state === 'running' ? '■ Arbeit stoppen' : '▶ Arbeit starten';
        button.classList.toggle('nx-btn-danger', data.state === 'running');
        button.classList.toggle('nx-btn-accent', data.state !== 'running');
      } catch (error) {
        button.textContent = old;
        alert(error.message || 'Zeiterfassung konnte nicht geändert werden.');
      } finally { button.disabled = false; }
    });
  });

  const abMoney = new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR'});
  const abNum = (value) => { const n = Number(String(value ?? '').replace(',','.')); return Number.isFinite(n) ? n : 0; };
  const abEscape = (value) => String(value ?? '').replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const abUnits = ['Stk.','m','m²','m³','kg','t','l','Std.','Tag','Woche','Pauschal','Satz','Rolle','Packung','Rohr'];
  const abUnitOptions = (selected='Stk.') => abUnits.map((u)=>`<option ${u===selected?'selected':''}>${u}</option>`).join('');

  const abRenumber = (table) => $$('.ab-item-row', table).forEach((row,index)=>{ const pos=$('.ab-pos',row); if(pos)pos.textContent=String(index+1); });
  const abRowPair = (row) => { const next=row.nextElementSibling; return next?.classList.contains('ab-item-subrow') ? next : null; };
  const abRemoveRow = (row, table) => { abRowPair(row)?.remove(); row.remove(); abRenumber(table); abRecalc(table); };
  const abRowHtml = (v={}) => `<tr class="ab-item-row" draggable="true"><td class="ab-drag-cell"><button type="button" class="ab-drag" title="Position verschieben">⋮⋮</button></td><td class="ab-pos"></td><td><select class="nx-control" name="item_type"><option value="material" ${v.type==='material'||!v.type?'selected':''}>Material</option><option value="labour" ${v.type==='labour'?'selected':''}>Arbeitsleistung</option><option value="mixed" ${v.type==='mixed'?'selected':''}>Gemischte Leistung</option><option value="other" ${v.type==='other'?'selected':''}>Sonstiges</option></select></td><td><input class="nx-control ab-num" name="item_quantity" type="number" min="0" step="0.001" value="${abEscape(v.quantity ?? 1)}"></td><td><select class="nx-control" name="item_unit">${abUnitOptions(v.unit||'Stk.')}</select></td><td class="ab-title-cell"><input type="hidden" name="item_catalog_id" value="${abEscape(v.catalogId||'')}"><input type="hidden" name="item_group" value=""><input type="hidden" name="item_price" value="0"><input class="nx-control" name="item_description" value="${abEscape(v.description||'')}" placeholder="Bezeichnung"><textarea class="nx-control ab-detail" name="item_detail" rows="2" placeholder="Beschreibung (optional)">${abEscape(v.detail||'')}</textarea></td><td><input class="nx-control ab-num" name="item_purchase_price" type="number" min="0" step="0.01" value="${abEscape(v.purchase ?? 0)}"></td><td><div class="ab-suffix"><input class="nx-control ab-num" name="item_markup_percent" type="number" step="0.01" value="${abEscape(v.markup ?? 0)}"><span>%</span></div></td><td><output data-line-markup>0,00 €</output></td><td><output data-line-unit-price>0,00 €</output></td><td><output data-line-total>0,00 €</output></td><td><button type="button" class="nx-item-remove" aria-label="Position entfernen">×</button></td></tr><tr class="ab-item-subrow"><td></td><td></td><td colspan="10"><label>Preismodell <select class="nx-control ab-service-model" name="item_service_model"><option value="normal">Normalleistung</option><option value="alternative">Alternativposition</option><option value="contingent">Eventualposition</option></select></label></td></tr>`;

  const abBindRow = (row, table) => {
    row.querySelector('.nx-item-remove')?.addEventListener('click',()=>abRemoveRow(row,table));
    $$('input,select,textarea',row).forEach((el)=>el.addEventListener('input',()=>abRecalc(table)));
    const sub=abRowPair(row); $$('select',sub||document.createElement('div')).forEach((el)=>el.addEventListener('change',()=>abRecalc(table)));
    row.addEventListener('dragstart',(e)=>{ row.classList.add('is-dragging'); e.dataTransfer.effectAllowed='move'; e.dataTransfer.setData('text/plain','position'); });
    row.addEventListener('dragend',()=>{row.classList.remove('is-dragging');abRenumber(table);abRecalc(table);});
  };
  const abInsertRow = (table, values={}) => { const body=$('tbody',table); const temp=document.createElement('tbody'); temp.innerHTML=abRowHtml(values); const row=temp.children[0], sub=temp.children[1]; body.append(row,sub); abBindRow(row,table); abRenumber(table); abRecalc(table); row.querySelector('[name=item_description]')?.focus(); return row; };

  const abRecalc = (table) => {
    let net=0,cost=0,alternative=0,contingent=0;
    $$('.ab-item-row',table).forEach((row)=>{
      const qty=Math.max(0,abNum($('[name=item_quantity]',row)?.value)); const purchase=Math.max(0,abNum($('[name=item_purchase_price]',row)?.value)); const markup=abNum($('[name=item_markup_percent]',row)?.value); const unit=Math.max(0,purchase*(1+markup/100)); const line=qty*unit; const markupValue=Math.max(0,unit-purchase); const model=abRowPair(row)?.querySelector('[name=item_service_model]')?.value || 'normal';
      $('[name=item_price]',row).value=unit.toFixed(2); $('[data-line-markup]',row).textContent=abMoney.format(markupValue); $('[data-line-unit-price]',row).textContent=abMoney.format(unit); $('[data-line-total]',row).textContent=abMoney.format(line);
      if(model==='alternative') alternative+=line; else if(model==='contingent') contingent+=line; else {net+=line; cost+=qty*purchase;}
    });
    const type=document.querySelector('[name=discount_type]')?.value||'percent'; const dval=Math.max(0,abNum(document.querySelector('[name=discount_value]')?.value)); const discount=Math.min(net,type==='fixed'?dval:net*dval/100); const after=Math.max(0,net-discount); const code=document.querySelector('[name=document_tax_code]')?.value||'19'; const rate=code==='7'?7:(code==='19'?19:0); const tax=after*rate/100; const margin=after-cost; const marginPct=after?margin/after*100:0;
    const set=(key,val,percent=false)=>{const el=document.querySelector(`[data-total="${key}"]`);if(el)el.textContent=percent?`${val.toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2})} %`:abMoney.format(val);};
    set('net',after);set('cost',cost);set('margin',margin);set('margin-percent',marginPct,true);set('alternative',alternative);set('contingent',contingent);set('discount',discount);set('tax',tax);set('gross',after+tax);
  };

  $$('[data-ab-items]').forEach((table)=>{
    $$('.ab-item-row',table).forEach((row)=>abBindRow(row,table));
    if(!$('.ab-item-row',table)) abInsertRow(table,{});
    $$('[data-ab-add-item]').forEach((button)=>button.addEventListener('click',()=>abInsertRow(table,{})));
    table.addEventListener('dragover',(e)=>{e.preventDefault();const dragging=$('.ab-item-row.is-dragging',table);if(!dragging)return;const target=e.target.closest('.ab-item-row');if(!target||target===dragging)return;const pair=abRowPair(dragging);const rect=target.getBoundingClientRect();const before=e.clientY<rect.top+rect.height/2;const targetPair=abRowPair(target);if(before){target.before(dragging);dragging.after(pair);}else{(targetPair||target).after(dragging);dragging.after(pair);}});
    let pointerRow=null;
    table.addEventListener('pointerdown',(e)=>{const handle=e.target.closest('.ab-drag');if(!handle)return;pointerRow=handle.closest('.ab-item-row');pointerRow?.setPointerCapture?.(e.pointerId);pointerRow?.classList.add('is-pointer-dragging');e.preventDefault();});
    table.addEventListener('pointermove',(e)=>{if(!pointerRow)return;const hit=document.elementFromPoint(e.clientX,e.clientY)?.closest('.ab-item-row');if(!hit||hit===pointerRow||!table.contains(hit))return;const pair=abRowPair(pointerRow), hitPair=abRowPair(hit);const r=hit.getBoundingClientRect();if(e.clientY<r.top+r.height/2){hit.before(pointerRow);pointerRow.after(pair);}else{(hitPair||hit).after(pointerRow);pointerRow.after(pair);}});
    const finish=()=>{if(!pointerRow)return;pointerRow.classList.remove('is-pointer-dragging');pointerRow=null;abRenumber(table);abRecalc(table);}; table.addEventListener('pointerup',finish);table.addEventListener('pointercancel',finish);
    document.querySelector('[name=discount_type]')?.addEventListener('change',()=>abRecalc(table));document.querySelector('[name=discount_value]')?.addEventListener('input',()=>abRecalc(table));document.querySelector('[name=document_tax_code]')?.addEventListener('change',()=>abRecalc(table));
    abRenumber(table);abRecalc(table);
  });

  const abUseCatalogButton = (button) => {const table=$('[data-ab-items]');if(!table)return;const kind=button.dataset.kind||'material';const type=kind==='service'?'labour':(kind==='material'?'material':'other');const purchase=abNum(button.dataset.purchase)>0?button.dataset.purchase:(button.dataset.sales||0);abInsertRow(table,{catalogId:button.dataset.id,description:button.dataset.name,detail:button.dataset.description,unit:button.dataset.unit,purchase,type});};
  document.addEventListener('click',(event)=>{const button=event.target.closest('[data-ab-catalog]');if(!button)return;abUseCatalogButton(button);});
  const abCatalogShell=$('[data-ab-catalog-shell]'),abCatalogInput=$('[data-ab-catalog-search]'),abCatalogList=$('[data-ab-catalog-list]'),abCatalogStatus=$('[data-ab-catalog-status]');
  const abCatalogInitial=abCatalogList?.innerHTML||'';let abCatalogTimer=null,abCatalogController=null;
  const abCatalogButton=(item)=>{const button=document.createElement('button');button.type='button';button.className='ab-catalog-item';button.dataset.abCatalog='';button.dataset.id=item.id||'';button.dataset.name=item.name||'';button.dataset.description=item.description||'';button.dataset.unit=item.unit||'Stk.';button.dataset.purchase=item.purchase||'0';button.dataset.sales=item.sales||'0';button.dataset.kind=item.kind||'material';const span=document.createElement('span'),title=document.createElement('b'),meta=document.createElement('small'),price=document.createElement('strong');title.textContent=item.name||item.code||'Position';meta.textContent=`${item.code||'ohne Code'} · ${item.unit||'Stk.'}`;price.textContent=abMoney.format(abNum(item.sales));span.append(title,meta);button.append(span,price);return button;};
  const abCatalogSearch=async()=>{if(!abCatalogInput||!abCatalogList||!abCatalogShell)return;const q=abCatalogInput.value.trim();if(q.length<2){abCatalogController?.abort();abCatalogList.innerHTML=abCatalogInitial;if(abCatalogStatus)abCatalogStatus.textContent='Schnellzugriff: bereits bepreiste Vorlagen. Suche ab 2 Zeichen.';return;}abCatalogController?.abort();abCatalogController=new AbortController();if(abCatalogStatus)abCatalogStatus.textContent='Vorlagen werden gesucht …';try{const url=new URL(abCatalogShell.dataset.abCatalogSearchUrl,window.location.origin);url.searchParams.set('q',q);const response=await fetch(url,{credentials:'same-origin',headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest'},signal:abCatalogController.signal});const raw=await response.text();let data={};try{data=raw?JSON.parse(raw):{};}catch(_){throw new Error('Katalogsuche hat keine gültige Serverantwort erhalten.');}if(!response.ok||data.ok===false)throw new Error(data.error||'Katalogsuche fehlgeschlagen.');abCatalogList.innerHTML='';(data.results||[]).forEach((item)=>abCatalogList.appendChild(abCatalogButton(item)));if(!(data.results||[]).length)abCatalogList.innerHTML='<div class="nx-empty">Keine bepreiste A+Bau-Vorlage gefunden. Für Originalpreise bitte die B&O-Suche darüber verwenden.</div>';if(abCatalogStatus)abCatalogStatus.textContent=`${(data.results||[]).length} passende Vorlagen`; }catch(error){if(error.name==='AbortError')return;if(abCatalogStatus)abCatalogStatus.textContent=error.message||'Katalogsuche fehlgeschlagen.';}};
  abCatalogInput?.addEventListener('input',()=>{clearTimeout(abCatalogTimer);abCatalogTimer=setTimeout(abCatalogSearch,260);});
  abCatalogInput?.addEventListener('keydown',(event)=>{if(event.key==='Enter'){event.preventDefault();clearTimeout(abCatalogTimer);abCatalogSearch();}});
  const legalTexts={standard:'Wir freuen uns, wenn unser Angebot Ihre Zustimmung findet. Für Rückfragen stehen wir Ihnen jederzeit gerne zur Verfügung.',widerruf:'Widerruf und vorzeitiger Arbeitsbeginn: Bitte prüfen und ergänzen Sie hier die für Ihren Betrieb und den konkreten Vertrag erforderliche Widerrufsbelehrung sowie die ausdrückliche Zustimmung zum vorzeitigen Arbeitsbeginn.',zahlung:'Zahlungsbedingungen: Der Rechnungsbetrag ist innerhalb des vereinbarten Zahlungsziels ohne Abzug fällig. Vereinbartes Skonto gilt nur bei fristgerechtem Zahlungseingang.',ausfuehrung:'Ausführungsbedingungen: Termine und Ausführungsbeginn werden nach Auftragsbestätigung abgestimmt. Änderungen des Leistungsumfangs werden vor Ausführung dokumentiert und freigegeben.'};
  $('[data-legal-template]')?.addEventListener('change',(e)=>{const target=$('[data-closing-text]');if(target&&e.target.value&&legalTexts[e.target.value])target.value=legalTexts[e.target.value];});

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

// A+Bau UI regression hardening 20260810
(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const esc = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const money = (value) => Number(value || 0).toLocaleString("de-DE", {
    style: "currency",
    currency: "EUR",
  });

  const toast = (title, text = "") => {
    let stack = $(".nx-toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "nx-toast-stack";
      document.body.append(stack);
    }
    const node = document.createElement("div");
    node.className = "nx-toast";
    node.innerHTML = `<b>${esc(title)}</b>${text ? `<span>${esc(text)}</span>` : ""}`;
    stack.append(node);
    window.setTimeout(() => node.remove(), 4800);
  };

  const recalcDocument = (table) => {
    let net = 0;
    let tax = 0;
    $$("tbody tr", table).forEach((row) => {
      const qty = Number($("[name='item_quantity']", row)?.value || 0);
      const price = Number($("[name='item_price']", row)?.value || 0);
      const rate = Number($("[name='item_tax']", row)?.value || 0);
      const line = qty * price;
      net += line;
      tax += line * rate / 100;
    });
    const discount = Number(document.querySelector("[name='discount_percent']")?.value || 0);
    const factor = 1 - Math.max(0, Math.min(100, discount)) / 100;
    net *= factor;
    tax *= factor;
    [["net", net], ["tax", tax], ["gross", net + tax]].forEach(([key, value]) => {
      const target = document.querySelector(`[data-total='${key}']`);
      if (target) target.textContent = money(value);
    });
  };

  const wireDocumentRow = (row, table) => {
    $(".nx-item-remove", row)?.addEventListener("click", () => {
      row.remove();
      recalcDocument(table);
    });
    $$('input', row).forEach((input) => input.addEventListener("input", () => recalcDocument(table)));
  };

  const addDocumentRow = (table, values = {}) => {
    const tbody = $("tbody", table);
    if (!tbody) {
      toast("Position konnte nicht hinzugefügt werden", "Die Positionsliste wurde nicht gefunden. Bitte Seite neu laden.");
      return;
    }
    const row = document.createElement("tr");
    row.innerHTML = `<td><input class="nx-control desc" name="item_description" value="${esc(values.description || "")}" placeholder="Leistung oder Material"></td><td><input class="nx-control" name="item_quantity" type="number" min="0" step="0.001" value="${esc(values.quantity ?? 1)}"></td><td><input class="nx-control" name="item_unit" value="${esc(values.unit || "Stk.")}"></td><td><input class="nx-control" name="item_price" type="number" min="0" step="0.01" value="${esc(values.price ?? 0)}"></td><td><input class="nx-control" name="item_tax" type="number" min="0" step="0.01" value="${esc(values.tax ?? 19)}"></td><td><button type="button" class="nx-item-remove" aria-label="Position entfernen">×</button></td>`;
    wireDocumentRow(row, table);
    tbody.append(row);
    recalcDocument(table);
    $(".desc", row)?.focus();
  };

  $$('[data-add-item]').forEach((button) => {
    if (button.dataset.nxAddBound === "1" || button.dataset.nxInlineBound === "1") return;
    const form = button.closest("form") || document;
    const table = $("[data-document-items]", form);
    button.dataset.nxAddBound = "1";
    button.addEventListener("click", () => {
      if (!table) {
        toast("Position kann hier nicht hinzugefügt werden", "Die Positionsliste wurde nicht gefunden. Bitte Seite neu laden.");
        return;
      }
      addDocumentRow(table);
    });
  });

  $$('[data-select-search]').forEach((input) => {
    const select = document.getElementById(input.dataset.selectSearch);
    if (!select) return;
    const status = input.parentElement?.querySelector("[data-select-search-status]");
    const options = Array.from(select.options).map((option) => ({
      option,
      text: option.textContent.trim().toLocaleLowerCase("de-DE"),
      placeholder: !option.value,
    }));
    const apply = () => {
      const query = input.value.trim().toLocaleLowerCase("de-DE");
      let matches = 0;
      let sole = null;
      options.forEach(({ option, text, placeholder }) => {
        const show = placeholder || !query || text.includes(query);
        option.hidden = !show;
        if (show && !placeholder) {
          matches += 1;
          sole = option;
        }
      });
      if (status) status.textContent = query ? `${matches} Kunde${matches === 1 ? "" : "n"} gefunden.` : "Tippen, um die Kundenliste zu filtern.";
      return { matches, sole };
    };
    input.addEventListener("input", apply);
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      const { matches, sole } = apply();
      if (matches === 1 && sole) {
        select.value = sole.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        toast("Kunde ausgewählt", sole.textContent.trim());
      } else if (matches === 0) {
        toast("Kein Kunde gefunden", "Suchbegriff ändern oder einen neuen Kunden anlegen.");
      } else {
        toast("Mehrere Treffer", `${matches} Kunden passen zur Suche. Bitte einen auswählen.`);
      }
    });
  });

  const updateSelectedChips = (select) => {
    let box = select.parentElement?.querySelector(".nx-selected-chips");
    if (!box) {
      box = document.createElement("div");
      box.className = "nx-selected-chips";
      select.insertAdjacentElement("afterend", box);
    }
    const selected = Array.from(select.selectedOptions).filter((option) => option.value);
    box.innerHTML = selected.length
      ? selected.map((option) => `<span class="nx-selected-chip">${esc(option.textContent.trim())}</span>`).join("")
      : '<span class="nx-muted" style="font-size:10px">Noch nichts ausgewählt.</span>';
  };

  $$('select[multiple]').forEach((select) => {
    updateSelectedChips(select);
    select.addEventListener("change", () => updateSelectedChips(select));
  });

  $$('[data-row-href]').forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target.closest("a,button,input,select,textarea,label")) return;
      if (row.dataset.rowHref) window.location.href = row.dataset.rowHref;
    });
  });

  $$('[data-settings-help]').forEach((button) => {
    button.addEventListener("click", () => {
      const context = button.closest("section,article,.card,.panel,.integration-card,li,div");
      const heading = context?.querySelector("h1,h2,h3,h4,strong,b")?.textContent?.trim();
      const subject = heading || button.textContent.trim() || "Diese Einstellung";
      toast(
        `${subject}: keine direkte Aktion`,
        "Für diese Einstellung ist an dieser Stelle keine direkte Aktion hinterlegt. Nutze die zugehörige Integrations- oder Konfigurationsmaske. Falls sie dort nicht verfügbar ist, wende dich an den Support.",
      );
    });
  });

  const catalogList = $("[data-catalog-list]");
  const catalogSearch = $("[data-catalog-search]");
  const catalogSearchButton = $("[data-catalog-search-button]");
  const catalogStatus = $("[data-catalog-search-status]");
  const catalogSelected = $("[data-catalog-selected]");
  const documentTable = $("[data-document-items]");
  if (catalogList && catalogSearch && documentTable) {
    const normalize = (value) => String(value || "").trim().toLocaleLowerCase("de-DE");
    const catalogItems = () => $$("[data-catalog-item]", catalogList);
    const filterCatalog = () => {
      const query = normalize(catalogSearch.value);
      let visible = 0;
      catalogItems().forEach((button) => {
        const haystack = normalize(`${button.dataset.name || ""} ${button.dataset.code || ""} ${button.textContent || ""}`);
        const show = !query || haystack.includes(query);
        button.hidden = !show;
        if (show) visible += 1;
      });
      if (catalogStatus) catalogStatus.textContent = query ? `${visible} Treffer für „${catalogSearch.value.trim()}“.` : "Alle Katalogpositionen werden angezeigt.";
    };
    const syncCatalogSelection = () => {
      const descriptions = $$("[name='item_description']", documentTable).map((input) => normalize(input.value)).filter(Boolean);
      const chosen = [];
      catalogItems().forEach((button) => {
        const name = normalize(button.dataset.name);
        const selected = Boolean(name) && descriptions.includes(name);
        button.classList.toggle("is-selected", selected);
        if (selected && !chosen.includes(button.dataset.name)) chosen.push(button.dataset.name);
      });
      if (catalogSelected) {
        catalogSelected.innerHTML = chosen.length
          ? chosen.map((name) => `<span class="nx-selected-chip">${esc(name)}</span>`).join("")
          : '<span class="nx-muted">Noch keine Katalogposition ausgewählt.</span>';
      }
    };
    catalogSearch.addEventListener("input", filterCatalog);
    catalogSearch.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      filterCatalog();
      const visible = catalogItems().filter((button) => !button.hidden);
      if (visible.length === 1) visible[0].focus();
    });
    catalogSearchButton?.addEventListener("click", (event) => {
      event.preventDefault();
      filterCatalog();
      catalogSearch.focus();
    });
    catalogList.addEventListener("click", (event) => {
      if (event.target.closest("[data-catalog-item]")) window.setTimeout(syncCatalogSelection, 0);
    });
    documentTable.addEventListener("input", syncCatalogSelection);
    documentTable.addEventListener("click", (event) => {
      if (event.target.closest(".nx-item-remove")) window.setTimeout(syncCatalogSelection, 0);
    });
    new MutationObserver(syncCatalogSelection).observe(documentTable.querySelector("tbody") || documentTable, { childList: true, subtree: true });
    syncCatalogSelection();
  }

  $$(".nx-content button[type='button']:not([disabled])").forEach((button) => {
    if (button.classList.contains("nx-item-remove") || button.onclick) return;
    if (Array.from(button.attributes).some((attribute) => attribute.name.startsWith("data-"))) return;
    button.addEventListener("click", () => toast(
      "Aktion noch nicht verfügbar",
      "Für diese Aktion ist hier noch keine Funktion hinterlegt. Nutze die verknüpfte Projektfunktion oder melde den konkreten Schritt an den Support.",
    ));
  });
})();

// A+Bau global KI + field handoff 20260810
// A+Bau AI CONTROL + SEARCH FIX 2026-08-11
// A+Bau STATEFUL ENTITY CHAT 2026-08-11
(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const csrf = () => $('input[name="csrfmiddlewaretoken"]')?.value || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

  // Profile menu: the previous avatar was only a decorative div.
  const profile = $('[data-profile]');
  const profileToggle = $('[data-profile-toggle]');
  const profileMenu = $('[data-profile-menu]');
  const closeProfile = () => { if (profileMenu) profileMenu.hidden = true; profileToggle?.setAttribute('aria-expanded','false'); };
  profileToggle?.addEventListener('click', (event) => {
    event.stopPropagation();
    if (!profileMenu) return;
    profileMenu.hidden = !profileMenu.hidden;
    profileToggle.setAttribute('aria-expanded', profileMenu.hidden ? 'false' : 'true');
  });
  document.addEventListener('click', (event) => { if (profile && !profile.contains(event.target)) closeProfile(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeProfile(); });

  // Global A+Bau KI assistant.
  const drawer = $('[data-assistant-drawer]');
  const chat = $('[data-assistant-chat]');
  const drawerInput = $('[data-assistant-input]');
  const drawerForm = $('[data-assistant-form]');
  const omniboxForm = $('[data-global-assistant-form]');
  const omniboxInput = $('[data-global-assistant-input]');
  const assistantUrl = drawer?.dataset.assistantUrl;
  const assistantExecuteUrl = drawer?.dataset.assistantExecuteUrl;

  const assistantHistoryKey = 'kayi-assistant-history-v3';
  let assistantHistory = [];
  try {
    const stored = JSON.parse(sessionStorage.getItem(assistantHistoryKey) || '[]');
    if (Array.isArray(stored)) assistantHistory = stored.filter((item) => item && ['user','assistant'].includes(item.role) && item.content).slice(-12);
  } catch (_) { assistantHistory = []; }
  const rememberAssistantTurn = (role, content) => {
    const value = String(content || '').trim();
    if (!value || !['user','assistant'].includes(role)) return;
    assistantHistory.push({role,content:value.slice(0,900)});
    assistantHistory = assistantHistory.slice(-12);
    try { sessionStorage.setItem(assistantHistoryKey, JSON.stringify(assistantHistory)); } catch (_) {}
  };

  const openAssistant = (prefill = '') => {
    if (!drawer) return;
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden','false');
    if (prefill && drawerInput) drawerInput.value = prefill;
    setTimeout(() => drawerInput?.focus(), 30);
  };
  const closeAssistant = () => { drawer?.classList.remove('is-open'); drawer?.setAttribute('aria-hidden','true'); };
  $('[data-assistant-open]')?.addEventListener('click', () => openAssistant());
  $('[data-assistant-close]')?.addEventListener('click', closeAssistant);
  $$('[data-assistant-suggestion]').forEach((button) => button.addEventListener('click', () => {
    openAssistant(button.dataset.assistantSuggestion || button.textContent.trim());
  }));

  const addMessage = (text, kind = 'ai', note = '') => {
    if (!chat) return;
    const box = document.createElement('div');
    box.className = `nx-assistant-msg is-${kind}`;
    box.innerHTML = `${escapeHtml(text)}${note ? `<span class="nx-assistant-action-note">${escapeHtml(note)}</span>` : ''}`;
    chat.append(box);
    chat.scrollTop = chat.scrollHeight;
  };

  // A_BAU_CONFIRMED_WORKFLOW_UI
  const addWorkflowPlan = (data) => {
    if (!chat || !data?.plan || !data?.plan_token) return;
    const card = document.createElement('section');
    card.className = 'nx-assistant-workflow';
    const title = document.createElement('b'); title.textContent = data.plan.title || 'Geplanter Ablauf';
    const intro = document.createElement('p'); intro.textContent = data.plan.confirmation_text || 'Diese Schritte jetzt ausführen?';
    const list = document.createElement('ol');
    (data.plan.steps || []).forEach((step) => { const li = document.createElement('li'); li.textContent = step.summary || step.type; list.append(li); });
    const note = document.createElement('small'); note.textContent = 'Noch wurde nichts gespeichert. Mit einer Bestätigung werden alle Schritte als ein zusammenhängender Ablauf ausgeführt; bei einem Fehler wird der Ablauf zurückgerollt.';
    const actions = document.createElement('div'); actions.className = 'nx-assistant-workflow-actions';
    const cancel = document.createElement('button'); cancel.type = 'button'; cancel.className = 'nx-btn'; cancel.textContent = 'Abbrechen';
    const confirm = document.createElement('button'); confirm.type = 'button'; confirm.className = 'nx-btn nx-btn-primary'; confirm.textContent = 'Alles bestätigen & ausführen';
    cancel.addEventListener('click', () => { card.remove(); addMessage('Ablauf abgebrochen. Es wurde nichts gespeichert.','ai'); });
    confirm.addEventListener('click', async () => {
      if (!assistantExecuteUrl || confirm.disabled) return;
      confirm.disabled = true; cancel.disabled = true; const old = confirm.textContent; confirm.textContent = 'Wird ausgeführt …';
      try {
        const response = await fetch(assistantExecuteUrl,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf()},body:JSON.stringify({plan_token:data.plan_token,confirmed:true})});
        const result = await response.json().catch(()=>({}));
        if (!response.ok || !result.ok) throw new Error(result.error || 'Der bestätigte Ablauf konnte nicht ausgeführt werden.');
        card.classList.add('is-done'); actions.remove(); note.textContent = '✓ Bestätigt und ausgeführt.';
        addMessage(result.reply || 'Ablauf erfolgreich ausgeführt.','ai');
        if (Array.isArray(result.created) && result.created.length) {
          const links = document.createElement('div'); links.className = 'nx-assistant-created-links';
          result.created.forEach((item) => { const a=document.createElement('a'); a.className='nx-btn'; a.href=item.url || '#'; a.textContent=`${item.created === false ? 'Öffnen' : 'Neu'}: ${item.label || item.number || 'Datensatz'}`; links.append(a); });
          chat?.append(links); chat.scrollTop = chat.scrollHeight;
        }
      } catch (error) {
        confirm.disabled = false; cancel.disabled = false; confirm.textContent = old;
        addMessage(error.message || 'Der Ablauf konnte nicht ausgeführt werden.','error');
      }
    });
    actions.append(cancel,confirm); card.append(title,intro,list,note,actions); chat.append(card); chat.scrollTop = chat.scrollHeight;
  };

  const fieldLabel = (field) => {
    if (field.id) {
      const label = document.querySelector(`label[for="${CSS.escape(field.id)}"]`);
      if (label) return label.textContent.trim();
    }
    return field.closest('.nx-field')?.querySelector('label')?.textContent?.trim() || field.name || '';
  };

  const collectFields = () => $$('input[name],select[name],textarea[name]')
    .filter((field) => !field.closest('[data-assistant-drawer]') && !field.closest('[data-global-assistant-form]'))
    .filter((field) => !['csrfmiddlewaretoken','signature_data','voice_transcript','voice_note'].includes(field.name))
    .filter((field) => field.type !== 'hidden' && field.type !== 'file')
    .slice(0, 80)
    .map((field) => ({
      name: field.name,
      label: fieldLabel(field),
      type: field.tagName === 'SELECT' ? 'select' : (field.type || field.tagName.toLowerCase()),
      value: field.type === 'checkbox' ? (field.checked ? 'true' : 'false') : String(field.value || '').slice(0, 800),
      options: field.tagName === 'SELECT' ? Array.from(field.options).slice(0,100).map((option) => ({value:option.value,label:option.textContent.trim()})) : [],
    }));

  const collectCatalog = () => $$('[data-catalog-item]').slice(0,160).map((button) => {
    const small = button.querySelector('small')?.textContent || '';
    const code = small.split('·')[0]?.trim() || '';
    return {name:button.dataset.name || button.querySelector('b')?.textContent?.trim() || button.textContent.trim(),code,unit:button.dataset.unit || '',price:button.dataset.price || ''};
  });

  const normalize = (value) => String(value || '').toLocaleLowerCase('de-DE').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9äöüß]+/g,' ').trim();
  const tokens = (value) => normalize(value).split(/\s+/).filter((token) => token.length > 1);
  const scoreText = (candidate, query) => {
    const c = normalize(candidate); const q = normalize(query);
    if (!q) return 0;
    if (c === q) return 1000;
    if (c.includes(q)) return 500 + q.length;
    return tokens(q).reduce((score, token) => score + (c.includes(token) ? 20 + token.length : 0), 0);
  };

  const fieldByTarget = (target) => {
    if (!target) return null;
    let field = document.querySelector(`[name="${CSS.escape(target)}"]`);
    if (field) return field;
    const wanted = normalize(target);
    return $$('input[name],select[name],textarea[name]').find((item) => normalize(fieldLabel(item)) === wanted) || null;
  };


  const parseBoolean = (value) => {
    const normalized = normalize(value);
    if (['1','true','ja','yes','on','an','aktiv','checked','markiert'].includes(normalized)) return true;
    if (['0','false','nein','no','off','aus','inaktiv','unchecked','nicht markiert'].includes(normalized)) return false;
    return null;
  };

  const pad2 = (value) => String(value).padStart(2,'0');
  const normalizeControlValue = (field, rawValue) => {
    const raw = String(rawValue ?? '').trim();
    if (!raw) return '';
    if (field.type === 'date') {
      const iso = raw.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
      if (iso) return `${iso[1]}-${pad2(iso[2])}-${pad2(iso[3])}`;
      const de = raw.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})/);
      if (de) return `${de[3]}-${pad2(de[2])}-${pad2(de[1])}`;
    }
    if (field.type === 'datetime-local') {
      const iso = raw.match(/^(\d{4})-(\d{1,2})-(\d{1,2})[T\s](\d{1,2}):(\d{2})/);
      if (iso) return `${iso[1]}-${pad2(iso[2])}-${pad2(iso[3])}T${pad2(iso[4])}:${iso[5]}`;
      const de = raw.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})[ ,]+(\d{1,2}):(\d{2})/);
      if (de) return `${de[3]}-${pad2(de[2])}-${pad2(de[1])}T${pad2(de[4])}:${de[5]}`;
    }
    if (field.type === 'time') {
      const time = raw.match(/^(\d{1,2}):(\d{2})/);
      if (time) return `${pad2(time[1])}:${time[2]}`;
    }
    if (field.type === 'number' || field.type === 'range') return raw.replace(',','.');
    return raw;
  };

  const setControlValue = (field, rawValue) => {
    if (field.type === 'checkbox') {
      const parsed = parseBoolean(rawValue);
      if (parsed === null) return false;
      field.checked = parsed;
      return true;
    }
    if (field.type === 'radio') {
      const group = $$(`input[type="radio"][name="${CSS.escape(field.name)}"]`);
      const ranked = group.map((item) => ({item,score:scoreText(`${item.value} ${fieldLabel(item)}`, rawValue)})).sort((a,b)=>b.score-a.score);
      if (!ranked[0]?.score) return false;
      ranked[0].item.checked = true;
      field = ranked[0].item;
      return true;
    }
    const normalized = normalizeControlValue(field, rawValue);
    field.value = normalized;
    if (normalized && ['date','datetime-local','time','number','range'].includes(field.type) && !field.value) return false;
    return true;
  };

  const routes = {dashboard:'/',customers:'/customers/',projects:'/projects/',appointments:'/appointments/',tasks:'/tasks/',quotes:'/quotes/',invoices:'/invoices/',expenses:'/expenses/',time:'/time/',employees:'/employees/',settings:'/settings/next/',field:'/field/'};


  const entityRouteLabels = {customers:'Kunde',projects:'Projekt',employees:'Mitarbeiter',appointments:'Termin'};
  const entityRecordUrl = (item) => {
    const route = routes[item?.route];
    const id = String(item?.id || '').trim();
    if (!route || !/^\d+$/.test(id)) return '';
    return `${route}${id}/`;
  };
  const addEntityResults = (results) => {
    if (!chat || !Array.isArray(results) || !results.length) return;
    const list = document.createElement('div');
    list.className = 'nx-assistant-results';
    results.slice(0,12).forEach((item) => {
      const href = entityRecordUrl(item);
      if (!href) return;
      const link = document.createElement('a');
      link.className = 'nx-assistant-result';
      link.href = href;
      const kind = entityRouteLabels[item.route] || 'Eintrag';
      link.innerHTML = `<span class="nx-assistant-result-kind">${escapeHtml(kind)}</span><b>${escapeHtml(item.label || kind)}</b>${item.detail ? `<small>${escapeHtml(item.detail)}</small>` : ''}`;
      list.append(link);
    });
    if (list.childElementCount) { chat.append(list); chat.scrollTop = chat.scrollHeight; }
  };


  // A+Bau deterministic trade scope planner.
  const setScopeQuantityNearCatalog = (button, action) => {
    if (!button || action?.quantity === null || action?.quantity === undefined) return;
    const quantity = String(action.quantity);
    const candidates = [];
    const row = button.closest('tr,[data-selected-item],[data-document-row],.nx-position-row,.position-row,.catalog-row');
    if (row) candidates.push(row);
    const labelled = $$('tr,[data-selected-item],[data-document-row],.nx-position-row,.position-row').filter((node) => {
      const haystack = normalize(node.textContent || '');
      return haystack.includes(normalize(action.label || '')) || haystack.includes(normalize(action.value || ''));
    });
    candidates.push(...labelled.slice(-3));
    for (const scope of candidates) {
      const input = scope.querySelector('input[data-quantity],input[data-menge],input[name*="quantity" i],input[name*="qty" i],input[name*="menge" i]');
      if (!input) continue;
      input.value = quantity;
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new Event('change',{bubbles:true}));
      input.classList.add('nx-ai-filled');
      break;
    }
  };

  const addScopeItems = (items, complete = false) => {
    if (!chat || !Array.isArray(items) || !items.length) return;
    const card = document.createElement('section');
    card.className = 'nx-ai-scope-card';
    const title = document.createElement('div');
    title.className = 'nx-ai-scope-head';
    title.innerHTML = `<b>Leistungsansatz</b><span>${complete ? 'vollständig' : 'wird ergänzt'}</span>`;
    card.append(title);
    const list = document.createElement('div');
    list.className = 'nx-ai-scope-list';
    items.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'nx-ai-scope-row';
      const qty = item.quantity_display || (item.quantity ?? 'offen');
      // A+Bau unmatched catalog and desktop sidebar polish 2026-08-18
      const match = item.catalog_match?.name
        ? `<small class="nx-ai-scope-match">Katalog: ${escapeHtml(item.catalog_match.name)}</small>`
        : `<span class="nx-ai-scope-unresolved"><small>Keine sichere Katalogposition gefunden.</small><button type="button" class="nx-ai-scope-choose" data-scope-catalog-choose>Position wählen</button></span>`;
      row.innerHTML = `<div><b>${escapeHtml(item.label || 'Leistung')}</b><small>${escapeHtml(item.basis || '')}</small>${match}</div><strong>${escapeHtml(qty)} ${escapeHtml(item.unit || '')}</strong>`;
      const chooseCatalog = row.querySelector('[data-scope-catalog-choose]');
      chooseCatalog?.addEventListener('click', () => {
        const drawer = row.closest('[data-assistant-drawer]') || document;
        const findCatalogButton = (root) => Array.from(root.querySelectorAll('button,[role="button"]')).find((node) => normalize(node.textContent || '').includes(normalize('Katalog wählen')));
        const catalogButton = findCatalogButton(drawer) || (drawer !== document ? findCatalogButton(document) : null);
        if (catalogButton) { catalogButton.click(); catalogButton.focus?.(); }
      });
      list.append(row);
    });
    card.append(list);
    chat.append(card);
    chat.scrollTop = chat.scrollHeight;
  };

  const applyActions = (actions) => {
    let changed = 0;
    let navigated = false;
    for (const action of actions || []) {
      if (!action || action.type === 'none') continue;
      if (action.type === 'set_field') {
        const field = fieldByTarget(action.target);
        if (!field || field.tagName === 'SELECT') continue;
        if (window.ABBauPreserveTypedText?.(field, action.value)) continue;
        if (!setControlValue(field, action.value)) continue;
        field.dispatchEvent(new Event('input',{bubbles:true}));
        field.dispatchEvent(new Event('change',{bubbles:true}));
        field.classList.add('nx-ai-filled'); changed += 1;
      } else if (action.type === 'select_option') {
        const field = fieldByTarget(action.target);
        if (!field || field.tagName !== 'SELECT') continue;
        const ranked = Array.from(field.options).map((option) => ({option,score:scoreText(option.textContent, action.value)})).sort((a,b)=>b.score-a.score);
        if (ranked[0]?.score > 0) {
          field.value = ranked[0].option.value;
          field.dispatchEvent(new Event('change',{bubbles:true}));
          field.classList.add('nx-ai-filled'); changed += 1;
        }
      } else if (action.type === 'bo_catalog_add') {
        if (action.item && typeof window.ABBauAddPricedPosition === 'function') {
          const inserted = window.ABBauAddPricedPosition(action.item, action.quantity ?? null);
          if (inserted) changed += 1;
        }
      } else if (action.type === 'catalog_add') {
        const ranked = $$('[data-catalog-item]').map((button) => ({button,score:scoreText(`${button.dataset.name || ''} ${button.textContent}`, action.value)})).sort((a,b)=>b.score-a.score);
        const amount = Math.max(1, Math.min(Number(action.count || 1), 20));
        ranked.filter((item) => item.score > 0).slice(0, amount).forEach((item) => { item.button.click(); item.button.classList.add('nx-ai-filled'); changed += 1; if (action.scope_key) setTimeout(() => setScopeQuantityNearCatalog(item.button, action), 0); });
      } else if (action.type === 'focus') {
        const field = fieldByTarget(action.target); field?.focus();
      } else if (action.type === 'navigate_record' && routes[action.target]) {
        const recordId = String(action.value || '').trim();
        if (!/^\d+$/.test(recordId)) continue;
        window.location.assign(`${routes[action.target]}${recordId}/`);
        navigated = true; break;
      } else if (action.type === 'navigate' && routes[action.target]) {
        const query = String(action.value || '').trim();
        window.location.assign(routes[action.target] + (query ? `?q=${encodeURIComponent(query)}` : ''));
        navigated = true; break;
      }
    }
    return {changed,navigated};
  };

  const runAssistant = async (message) => {
    message = String(message || '').trim();
    if (!message || !assistantUrl) return;
    openAssistant();
    const priorHistory = assistantHistory.slice(-10);
    addMessage(message,'user');
    rememberAssistantTurn('user', message);
    if (drawerInput) drawerInput.value = '';
    if (omniboxInput) omniboxInput.value = '';
    const loading = document.createElement('div');
    loading.className = 'nx-assistant-msg is-ai'; loading.textContent = 'A+Bau KI denkt …'; chat?.append(loading);
    try {
      const response = await fetch(assistantUrl, {
        method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json','Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf()},
        body:JSON.stringify({message,path:window.location.pathname + window.location.search,title:document.title,fields:collectFields(),catalog:collectCatalog(),history:priorHistory}),
      });
      const data = await response.json().catch(() => ({}));
      loading.remove();
      if (response.status === 428 && data.settings_url) {
        addMessage(data.error || 'KI-Einwilligung erforderlich.','error');
        const link = document.createElement('a'); link.href = data.settings_url; link.className = 'nx-btn nx-btn-primary'; link.textContent = 'KI in Einstellungen freigeben'; chat?.append(link); return;
      }
      if (!response.ok || !data.ok) throw new Error(data.error || 'A+Bau KI konnte die Anfrage nicht ausführen.');
      if (data.requires_confirmation && data.mode === 'workflow_plan' && data.plan_token) {
        addMessage(data.reply || 'Ich habe den Ablauf vorbereitet. Bitte einmal prüfen und bestätigen.','ai');
        addWorkflowPlan(data);
        return;
      }
      const applied = applyActions(data.actions || []);
      const replyText = data.reply || 'Erledigt.';
      addMessage(replyText,'ai', applied.changed ? `${applied.changed} Eingabe(n) im aktuellen Entwurf angepasst. Bitte prüfen und anschließend selbst speichern.` : '');
      rememberAssistantTurn('assistant', replyText);
      if (!applied.navigated) addScopeItems(data.scope_items || [], Boolean(data.scope_complete));
      if (!applied.navigated) addEntityResults(data.results || []);
    } catch (error) {
      loading.remove(); addMessage(error.message || 'A+Bau KI ist momentan nicht erreichbar.','error');
    }
  };

  omniboxForm?.addEventListener('submit', (event) => { event.preventDefault(); runAssistant(omniboxInput?.value); });
  drawerForm?.addEventListener('submit', (event) => { event.preventDefault(); runAssistant(drawerInput?.value); });

  // Real field voice capture: record the file, transcribe it and fill the report.
  $$('[data-field-voice]').forEach((box) => {
    const consent = $('[data-field-voice-consent]', box);
    const record = $('[data-field-record]', box);
    const transcribe = $('[data-field-transcribe]', box);
    const status = $('[data-field-record-status]', box);
    const preview = $('[data-field-voice-preview]', box);
    const fileInput = $('[data-field-voice-file]', box);
    const form = box.closest('[data-documentation-form]');
    const transcriptInput = $('[name="voice_transcript"]', form || document);
    let recorder = null; let stream = null; let chunks = [];

    const setStatus = (text, live = false) => { if (status) { status.textContent = text; status.classList.toggle('is-live', live); } };
    if (!window.MediaRecorder || !navigator.mediaDevices?.getUserMedia) {
      if (record) record.disabled = true;
      setStatus('Audioaufnahme wird von diesem Gerät/Browser nicht unterstützt.');
      return;
    }

    record?.addEventListener('click', async () => {
      if (recorder?.state === 'recording') { recorder.stop(); return; }
      if (!consent?.checked) { setStatus('Bitte zuerst die Zustimmung zur Sprachaufnahme bestätigen.'); consent?.focus(); return; }
      try {
        stream = await navigator.mediaDevices.getUserMedia({audio:true});
        chunks = [];
        const preferred = MediaRecorder.isTypeSupported?.('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : '';
        recorder = new MediaRecorder(stream, preferred ? {mimeType:preferred} : undefined);
        recorder.ondataavailable = (event) => { if (event.data?.size) chunks.push(event.data); };
        recorder.onstop = () => {
          const mime = recorder.mimeType || 'audio/webm';
          const blob = new Blob(chunks,{type:mime});
          const extension = mime.includes('ogg') ? 'ogg' : 'webm';
          const file = new File([blob],`einsatz-${Date.now()}.${extension}`,{type:mime});
          const transfer = new DataTransfer(); transfer.items.add(file); if (fileInput) fileInput.files = transfer.files;
          if (preview) { preview.src = URL.createObjectURL(blob); preview.hidden = false; }
          if (transcribe) transcribe.hidden = false;
          setStatus(`Aufnahme bereit · ${Math.max(1,Math.round(blob.size/1024))} KB`);
          stream?.getTracks().forEach((track) => track.stop()); stream = null;
        };
        recorder.start(500);
        record.textContent = '■ Aufnahme stoppen';
        setStatus('Aufnahme läuft …', true);
        recorder.addEventListener('stop', () => { record.textContent = '🎙 Neue Aufnahme'; }, {once:true});
      } catch (_) { setStatus('Mikrofon konnte nicht geöffnet werden. Bitte Browser-Berechtigung prüfen.'); }
    });

    transcribe?.addEventListener('click', async () => {
      const file = fileInput?.files?.[0]; if (!file) return;
      transcribe.disabled = true; const old = transcribe.textContent; transcribe.textContent = '✦ KI wertet aus …';
      const data = new FormData(); data.append('voice',file); data.append('csrfmiddlewaretoken',csrf());
      try {
        const response = await fetch(box.dataset.transcribeUrl,{method:'POST',credentials:'same-origin',body:data,headers:{'Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf()}});
        const result = await response.json().catch(()=>({}));
        if (response.status === 428 && result.settings_url) throw new Error(`${result.error} Öffne Einstellungen: ${result.settings_url}`);
        if (!response.ok || !result.ok) throw new Error(result.error || 'Sprachaufnahme konnte nicht ausgewertet werden.');
        const report = $('[name="report_text"]',form); const services = $('[name="services"]',form); const material = $('[name="material"]',form);
        if (report) report.value = result.report || result.transcript || '';
        if (services && result.services) services.value = result.services;
        if (material && result.material) material.value = result.material;
        if (transcriptInput) transcriptInput.value = result.transcript || '';
        setStatus('KI-Auswertung übernommen. Bericht, Leistungen und Material bitte kurz prüfen.');
      } catch (error) { setStatus(error.message || 'Sprachaufnahme konnte nicht ausgewertet werden.'); }
      finally { transcribe.disabled = false; transcribe.textContent = old; }
    });
  });

  // Fix signature clear button scope and make the final handoff result actionable.
  $$('[data-signature-clear]').forEach((button) => button.addEventListener('click', () => {
    const section = button.closest('.nx-doc-section'); const canvas = section?.querySelector('canvas.nx-signature');
    if (!canvas) return; const ctx = canvas.getContext('2d'); ctx.clearRect(0,0,canvas.width,canvas.height);
    const hidden = section.querySelector('[name="signature_data"]'); if (hidden) hidden.value = '';
  }));

  window.KAYIFieldHandoff = {
    showResult(result) {
      const box = $('[data-handoff-result]'); if (!box || !result?.pdf_url) return false;
      box.hidden = false;
      const open = $('[data-handoff-pdf]',box); if (open) open.href = result.pdf_url;
      const share = $('[data-handoff-share]',box);
      share?.addEventListener('click', async () => {
        const absolute = new URL(result.pdf_url, window.location.origin).href;
        if (navigator.share) { try { await navigator.share({title:'A+Bau Arbeitsnachweis',text:'Arbeitsnachweis als PDF',url:absolute}); return; } catch (_) {} }
        try { await navigator.clipboard.writeText(absolute); share.textContent = 'Link kopiert'; } catch (_) { window.open(absolute,'_blank'); }
      }, {once:true});
      box.scrollIntoView({behavior:'smooth',block:'center'});
      return true;
    }
  };
})();


// A+Bau GLOBAL FORM VALIDATION 2026-08-11
(() => {
  const formLabel = (field) => {
    if (field?.id) {
      const label = document.querySelector(`label[for="${CSS.escape(field.id)}"]`);
      if (label) return label.textContent.trim();
    }
    return field?.closest('.nx-field,.fa-field,.fa-block')?.querySelector('label,b')?.textContent?.trim() || field?.name || 'Eingabe';
  };
  const reveal = (node) => {
    let current = node?.parentElement;
    while (current) {
      if (current.tagName === 'DETAILS') current.open = true;
      current = current.parentElement;
    }
  };
  const summary = (form, messages) => {
    if (!form || !messages?.length) return;
    let box = form.querySelector(':scope > [data-global-form-errors]');
    if (!box) {
      box = document.createElement('div');
      box.dataset.globalFormErrors = '';
      box.className = 'nx-global-form-errors';
      box.setAttribute('role','alert');
      box.setAttribute('aria-live','assertive');
      form.prepend(box);
    }
    const unique = [...new Set(messages.filter(Boolean))].slice(0,10);
    box.innerHTML = `<b>Bitte Eingaben prüfen.</b><p>${unique.map((m) => `<span>${String(m).replace(/[&<>]/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}</span>`).join('')}</p>`;
    box.hidden = false;
  };
  document.addEventListener('invalid', (event) => {
    const field = event.target;
    const form = field?.form;
    if (!form || form.closest('[data-assistant-drawer]')) return;
    reveal(field);
    field.setAttribute('aria-invalid','true');
    const message = `${formLabel(field)}: ${field.validationMessage || 'Bitte dieses Feld prüfen.'}`;
    const existing = [...(form._kayiInvalidMessages || [])]; existing.push(message); form._kayiInvalidMessages = existing;
    summary(form, existing);
    setTimeout(() => {
      const first = form.querySelector('[aria-invalid="true"]');
      first?.scrollIntoView({behavior:'smooth',block:'center'});
      first?.focus({preventScroll:true});
    }, 0);
  }, true);
  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (form instanceof HTMLFormElement) form._kayiInvalidMessages = [];
  }, true);
  document.addEventListener('input', (event) => {
    const field = event.target;
    if (field?.matches?.('input,select,textarea') && field.validity?.valid) field.removeAttribute('aria-invalid');
  }, true);
  const surfaceServerErrors = () => {
    document.querySelectorAll('form').forEach((form) => {
      const errorNodes = [...form.querySelectorAll('.errorlist li,[data-field-error],.invalid-feedback')].filter((el) => el.textContent.trim());
      if (!errorNodes.length) return;
      errorNodes.forEach(reveal);
      summary(form, errorNodes.map((el) => el.textContent.trim()));
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', surfaceServerErrors);
  else surfaceServerErrors();
})();

/* A+Bau ToolTime customer contacts parity 20260821 */
(() => {
  const page = document.querySelector('.tt-customers-page');
  const modal = document.querySelector('[data-customer-modal]');
  const openModal = () => {
    if (!modal) return;
    modal.hidden = false;
    document.documentElement.classList.add('tt-customer-modal-open');
    const first = modal.querySelector('input:not([type="hidden"]),select,textarea,button');
    window.setTimeout(() => first?.focus(), 30);
  };
  const closeModal = () => {
    if (!modal) return;
    modal.hidden = true;
    document.documentElement.classList.remove('tt-customer-modal-open');
  };
  document.querySelectorAll('[data-customer-modal-show]').forEach((button) => button.addEventListener('click', openModal));
  document.querySelectorAll('[data-customer-modal-close]').forEach((button) => button.addEventListener('click', closeModal));
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && modal && !modal.hidden) closeModal(); });
  if (page?.dataset.customerModalOpen === '1') openModal();

  const form = document.querySelector('[data-customer-modal-form]');
  const syncType = () => {
    if (!form) return;
    const value = form.querySelector('input[name="type"]:checked')?.value || 'business';
    const business = value === 'business';
    form.querySelectorAll('[data-company-only]').forEach((node) => { node.hidden = !business; });
  };
  form?.querySelectorAll('input[name="type"]').forEach((radio) => radio.addEventListener('change', syncType));
  syncType();

  const details = document.querySelector('[data-customer-details]');
  const syncDetails = () => {
    const label = details?.querySelector('[data-details-label]');
    if (label) label.textContent = details.open ? 'Details ausblenden' : 'Details anzeigen';
  };
  details?.addEventListener('toggle', syncDetails);
  syncDetails();

  document.querySelectorAll('[data-customer-row]').forEach((row) => {
    const go = () => { if (row.dataset.href) window.location.href = row.dataset.href; };
    row.addEventListener('click', (event) => {
      if (event.target.closest('a,button,summary,details,input,select,textarea,label')) return;
      go();
    });
    row.addEventListener('keydown', (event) => {
      if ((event.key === 'Enter' || event.key === ' ') && !event.target.closest('a,button,summary,details')) { event.preventDefault(); go(); }
    });
  });

  document.querySelectorAll('[data-row-menu]').forEach((menu) => {
    menu.addEventListener('toggle', () => {
      if (!menu.open) return;
      document.querySelectorAll('[data-row-menu][open]').forEach((other) => { if (other !== menu) other.removeAttribute('open'); });
    });
  });

  document.querySelectorAll('[data-contacts-group]').forEach((group) => {
    const toggle = group.querySelector('[data-contacts-toggle]');
    toggle?.addEventListener('click', () => group.classList.toggle('is-collapsed'));
  });
})();


  // A+BAU PROJECT TEAM PICKER 2026-08-12
  (() => {
    const select = document.querySelector('.nx-project-form select[name="members"]');
    if (!select || select.dataset.abTeamEnhanced === '1') return;
    select.dataset.abTeamEnhanced = '1';
    select.classList.add('ab-team-native');
    const field = select.closest('.nx-field');
    if (!field) return;
    const label = field.querySelector(':scope > label');
    if (label) label.textContent = 'Projektteam';

    const picker = document.createElement('div');
    picker.className = 'ab-team-picker';
    picker.innerHTML = `
      <div class="ab-team-picker-head">
        <div><strong>Mitarbeiter auswählen</strong><small>Mehrere Personen sind möglich. Klicke auf eine Karte zum Auswählen.</small></div>
        <button type="button" class="ab-team-clear">Auswahl löschen</button>
      </div>
      <div class="ab-team-selected" aria-live="polite"></div>
      <label class="ab-team-search"><span>⌕</span><input type="search" placeholder="Mitarbeiter suchen …" autocomplete="off"></label>
      <div class="ab-team-list"></div>`;
    select.after(picker);

    const list = picker.querySelector('.ab-team-list');
    const selected = picker.querySelector('.ab-team-selected');
    const search = picker.querySelector('.ab-team-search input');
    const clear = picker.querySelector('.ab-team-clear');
    const cards = [];

    const initials = (label) => label.trim().split(/\s+/).slice(0,2).map((part)=>part[0]||'').join('').toUpperCase() || 'MA';
    const refresh = () => {
      let count = 0;
      cards.forEach(({option, card, check}) => {
        card.classList.toggle('is-selected', option.selected);
        check.textContent = option.selected ? '✓' : '';
        if (option.selected) count += 1;
      });
      selected.innerHTML = '';
      const chosen = Array.from(select.selectedOptions);
      if (!chosen.length) {
        selected.innerHTML = '<span class="ab-team-empty">Noch niemand ausgewählt</span>';
      } else {
        chosen.forEach((option) => {
          const chip = document.createElement('button');
          chip.type = 'button'; chip.className = 'ab-team-chip';
          chip.innerHTML = `<span>${initials(option.textContent)}</span>${option.textContent}<b>×</b>`;
          chip.addEventListener('click', () => { option.selected = false; select.dispatchEvent(new Event('change',{bubbles:true})); refresh(); });
          selected.appendChild(chip);
        });
      }
      picker.dataset.selectedCount = String(count);
    };

    Array.from(select.options).forEach((option) => {
      if (!option.value) return;
      const card = document.createElement('button');
      card.type = 'button'; card.className = 'ab-team-card';
      card.dataset.search = option.textContent.toLocaleLowerCase('de-DE');
      card.innerHTML = `<span class="ab-team-avatar">${initials(option.textContent)}</span><span class="ab-team-person"><strong></strong><small>Als Teammitglied hinzufügen</small></span><span class="ab-team-check"></span>`;
      card.querySelector('.ab-team-person strong').textContent = option.textContent;
      const check = card.querySelector('.ab-team-check');
      card.addEventListener('click', () => { option.selected = !option.selected; select.dispatchEvent(new Event('change',{bubbles:true})); refresh(); });
      list.appendChild(card); cards.push({option, card, check});
    });

    search.addEventListener('input', () => {
      const query = search.value.trim().toLocaleLowerCase('de-DE');
      cards.forEach(({card}) => { card.hidden = !!query && !card.dataset.search.includes(query); });
    });
    clear.addEventListener('click', () => {
      Array.from(select.options).forEach((option) => { option.selected = false; });
      select.dispatchEvent(new Event('change',{bubbles:true})); refresh();
    });
    select.addEventListener('change', refresh);
    refresh();
  })();

// A+Bau PR106 final contract repair 2026-08-16

// KAYI 10-MINUTE TIME GRID 2026-08-20
(() => {
  const STEP_SECONDS = 600;
  const roundMinutes = (minutes) => Math.max(0, Math.min(1430, Math.round(minutes / 10) * 10));
  const normalize = (field) => {
    if (!(field instanceof HTMLInputElement) || !['time','datetime-local'].includes(field.type)) return;
    field.step = String(STEP_SECONDS);
    const raw = field.value;
    if (!raw) return;
    if (field.type === 'time') {
      const m = raw.match(/^(\d{2}):(\d{2})/); if (!m) return;
      const total = roundMinutes(Number(m[1]) * 60 + Number(m[2]));
      const next = `${String(Math.floor(total / 60)).padStart(2,'0')}:${String(total % 60).padStart(2,'0')}`;
      if (next !== raw.slice(0,5)) field.value = next;
      return;
    }
    const m = raw.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/); if (!m) return;
    const total = roundMinutes(Number(m[2]) * 60 + Number(m[3]));
    const next = `${m[1]}T${String(Math.floor(total / 60)).padStart(2,'0')}:${String(total % 60).padStart(2,'0')}`;
    if (next !== raw.slice(0,16)) field.value = next;
  };
  const apply = (root=document) => root.querySelectorAll?.('input[type="time"],input[type="datetime-local"]').forEach((field) => { field.step = String(STEP_SECONDS); });
  document.addEventListener('change', (event) => normalize(event.target), true);
  document.addEventListener('blur', (event) => normalize(event.target), true);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => apply()); else apply();
  new MutationObserver((records) => records.forEach((record) => record.addedNodes.forEach((node) => { if (node.nodeType === 1) { if (node.matches?.('input[type="time"],input[type="datetime-local"]')) node.step=String(STEP_SECONDS); apply(node); } }))).observe(document.documentElement, {childList:true, subtree:true});
})();

// KAYI DIRECT POSITION LIVE PRICING 2026-08-20
(() => {
  const form = document.querySelector('[data-ab-commercial-form][data-live-pricing-url]');
  if (!form) return;
  const endpoint = form.dataset.livePricingUrl;
  const familySelect = form.querySelector('[data-live-catalog-family]');
  const panel = form.querySelector('[data-ab-catalog-list]');
  const panelSearch = form.querySelector('[data-ab-catalog-search]');
  const money = new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR'});
  let family = familySelect?.value || 'catalog';
  let timer = null;
  let requestSerial = 0;

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g,(ch)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const num = (value) => { const n=Number(String(value ?? '0').replace(',','.')); return Number.isFinite(n)?n:0; };
  const rowFor = (input) => input.closest('.ab-item-row');
  const setValue = (el, value) => { if (!el) return; el.value = value ?? ''; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); };

  const applyResult = (row, item) => {
    if (!row || !item) return;
    const price = num(item.sales_price || item.purchase_price);
    const purchase = num(item.purchase_price || item.sales_price || price);
    setValue(row.querySelector('[name=item_description]'), item.name || item.description || '');
    const detail = row.querySelector('[name=item_detail]'); if (detail && item.description && item.description !== item.name) setValue(detail, item.description);
    const unit = row.querySelector('[name=item_unit]'); if (unit && item.unit) { const option=[...unit.options].find(o=>o.value===item.unit||o.textContent.trim()===item.unit); if(option) setValue(unit, option.value); }
    setValue(row.querySelector('[name=item_purchase_price]'), purchase.toFixed(2));
    setValue(row.querySelector('[name=item_markup_percent]'), '0');
    setValue(row.querySelector('[name=item_price]'), price.toFixed(2));
    const catalogId = row.querySelector('[name=item_catalog_id]'); if (catalogId) catalogId.value = item.kind === 'catalog' ? (item.id || '') : '';
    row.dataset.priceSource = item.source || family;
    row.querySelector('[data-live-price-popover]')?.remove();
  };

  const fetchRows = async (q='', limit=30) => {
    const serial = ++requestSerial;
    const url = new URL(endpoint, window.location.origin); url.searchParams.set('catalog',family); url.searchParams.set('limit',String(limit)); if(q) url.searchParams.set('q',q);
    try { const response=await fetch(url,{headers:{'X-Requested-With':'XMLHttpRequest'}}); const data=await response.json(); if(serial!==requestSerial) return []; return data.ok&&Array.isArray(data.results)?data.results:[]; }
    catch (_) { return []; }
  };

  const resultButton = (item, row) => {
    const button=document.createElement('button'); button.type='button'; button.className='ab-live-price-option';
    button.innerHTML=`<span><b>${esc(item.name||item.description||'Position')}</b><small>${esc([item.code,item.unit,item.source].filter(Boolean).join(' · '))}</small></span><strong>${money.format(num(item.sales_price||item.purchase_price))}</strong>`;
    button.addEventListener('mousedown',(e)=>e.preventDefault());
    button.addEventListener('click',()=>applyResult(row,item));
    return button;
  };

  const showInline = async (input) => {
    const q=input.value.trim(); const row=rowFor(input); row?.querySelector('[data-live-price-popover]')?.remove(); if(q.length<2||!row) return;
    const rows=await fetchRows(q,8); if(!document.body.contains(input)||input.value.trim()!==q) return;
    const pop=document.createElement('div'); pop.className='ab-live-price-popover'; pop.dataset.livePricePopover='';
    rows.forEach(item=>pop.appendChild(resultButton(item,row)));
    if(!rows.length){ const empty=document.createElement('div'); empty.className='ab-live-price-empty'; empty.textContent='Keine passende Preisposition gefunden.'; pop.appendChild(empty); }
    input.parentElement.style.position='relative'; input.parentElement.appendChild(pop);
  };

  form.addEventListener('input',(event)=>{ const input=event.target.closest?.('[data-live-price-input]'); if(!input)return; clearTimeout(timer); timer=setTimeout(()=>showInline(input),180); });
  form.addEventListener('keydown',(event)=>{ const input=event.target.closest?.('[data-live-price-input]'); if(!input)return; const pop=rowFor(input)?.querySelector('[data-live-price-popover]'); if((event.key==='Enter'||event.key==='Tab')&&pop){ const first=pop.querySelector('.ab-live-price-option'); if(first){ if(event.key==='Enter')event.preventDefault(); first.click(); } } });
  form.addEventListener('focusout',(event)=>{ const input=event.target.closest?.('[data-live-price-input]'); if(input)setTimeout(()=>rowFor(input)?.querySelector('[data-live-price-popover]')?.remove(),160); });

  const renderPanel = async (q='') => {
    if(!panel)return; panel.innerHTML='<div class="nx-muted" style="padding:12px 16px">Preise werden geladen …</div>';
    const rows=await fetchRows(q,50); panel.innerHTML='';
    if(!rows.length){panel.innerHTML='<div class="nx-empty">Keine Positionen in dieser Preisquelle gefunden.</div>';return;}
    rows.forEach(item=>{ const button=document.createElement('button'); button.type='button'; button.className='ab-catalog-item'; button.innerHTML=`<span><b>${esc(item.name||item.description)}</b><small>${esc([item.code,item.unit,item.source].filter(Boolean).join(' · '))}</small></span><strong>${money.format(num(item.sales_price||item.purchase_price))}</strong>`; button.addEventListener('click',()=>{ const table=form.querySelector('[data-ab-items]'); const target=[...table.querySelectorAll('.ab-item-row')].find(r=>!r.querySelector('[name=item_description]')?.value.trim())||table.querySelector('.ab-item-row:last-of-type'); if(target) applyResult(target,item); }); panel.appendChild(button); });
  };

  familySelect?.addEventListener('change',()=>{ family=familySelect.value||'catalog'; if(panelSearch)panelSearch.value=''; renderPanel(''); });
  panelSearch?.addEventListener('input',(event)=>{ clearTimeout(timer); timer=setTimeout(()=>renderPanel(event.target.value.trim()),180); });
  renderPanel('');
})();
