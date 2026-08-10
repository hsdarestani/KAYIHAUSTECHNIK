// KAYI global KI + field handoff 20260810
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

  // Global KAYI KI assistant.
  const drawer = $('[data-assistant-drawer]');
  const chat = $('[data-assistant-chat]');
  const drawerInput = $('[data-assistant-input]');
  const drawerForm = $('[data-assistant-form]');
  const omniboxForm = $('[data-global-assistant-form]');
  const omniboxInput = $('[data-global-assistant-input]');
  const assistantUrl = drawer?.dataset.assistantUrl;

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

  const routes = {dashboard:'/',customers:'/customers/',projects:'/projects/',appointments:'/appointments/',tasks:'/tasks/',quotes:'/quotes/',invoices:'/invoices/',expenses:'/expenses/',time:'/time/',employees:'/employees/',settings:'/settings/next/',field:'/field/'};

  const applyActions = (actions) => {
    let changed = 0;
    let navigated = false;
    for (const action of actions || []) {
      if (!action || action.type === 'none') continue;
      if (action.type === 'set_field') {
        const field = fieldByTarget(action.target);
        if (!field || field.tagName === 'SELECT') continue;
        if (field.type === 'checkbox') field.checked = /^(1|true|ja|yes)$/i.test(action.value || '');
        else field.value = action.value ?? '';
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
      } else if (action.type === 'catalog_add') {
        const ranked = $$('[data-catalog-item]').map((button) => ({button,score:scoreText(`${button.dataset.name || ''} ${button.textContent}`, action.value)})).sort((a,b)=>b.score-a.score);
        const amount = Math.max(1, Math.min(Number(action.count || 1), 20));
        ranked.filter((item) => item.score > 0).slice(0, amount).forEach((item) => { item.button.click(); item.button.classList.add('nx-ai-filled'); changed += 1; });
      } else if (action.type === 'focus') {
        const field = fieldByTarget(action.target); field?.focus();
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
    addMessage(message,'user');
    if (drawerInput) drawerInput.value = '';
    if (omniboxInput) omniboxInput.value = '';
    const loading = document.createElement('div');
    loading.className = 'nx-assistant-msg is-ai'; loading.textContent = 'KAYI KI denkt …'; chat?.append(loading);
    try {
      const response = await fetch(assistantUrl, {
        method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json','Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf()},
        body:JSON.stringify({message,path:window.location.pathname + window.location.search,title:document.title,fields:collectFields(),catalog:collectCatalog()}),
      });
      const data = await response.json().catch(() => ({}));
      loading.remove();
      if (response.status === 428 && data.settings_url) {
        addMessage(data.error || 'KI-Einwilligung erforderlich.','error');
        const link = document.createElement('a'); link.href = data.settings_url; link.className = 'nx-btn nx-btn-primary'; link.textContent = 'KI in Einstellungen freigeben'; chat?.append(link); return;
      }
      if (!response.ok || !data.ok) throw new Error(data.error || 'KAYI KI konnte die Anfrage nicht ausführen.');
      const applied = applyActions(data.actions || []);
      addMessage(data.reply || 'Erledigt.','ai', applied.changed ? `${applied.changed} Eingabe(n) im aktuellen Entwurf angepasst. Bitte prüfen und anschließend selbst speichern.` : 'Keine irreversible Aktion wurde automatisch ausgeführt.');
    } catch (error) {
      loading.remove(); addMessage(error.message || 'KAYI KI ist momentan nicht erreichbar.','error');
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
        if (navigator.share) { try { await navigator.share({title:'KAYI Arbeitsnachweis',text:'Arbeitsnachweis als PDF',url:absolute}); return; } catch (_) {} }
        try { await navigator.clipboard.writeText(absolute); share.textContent = 'Link kopiert'; } catch (_) { window.open(absolute,'_blank'); }
      }, {once:true});
      box.scrollIntoView({behavior:'smooth',block:'center'});
      return true;
    }
  };
})();
