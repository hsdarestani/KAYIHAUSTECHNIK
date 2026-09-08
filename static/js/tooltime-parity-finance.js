// A+BAU TOOLTIME FINANCE PARITY 2026-08-20
(() => {
  const form=document.querySelector('.tt-document-form'); if(!form)return;
  const money=new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR'}); const num=v=>{const n=Number(String(v??0).replace(',','.'));return Number.isFinite(n)?n:0};
  const modal=(sel,on=true)=>{const el=document.querySelector(sel);if(el)el.hidden=!on};
  const groupOf=el=>el.closest('[data-service-group]');
  function syncGroups(){document.querySelectorAll('[data-service-group]').forEach((g,gi)=>{const title=g.querySelector('.tt-group-title')?.value||`Leistungsgruppe ${gi+1}`;let sum=0;g.querySelectorAll('[data-position]').forEach((row,ri)=>{row.querySelector('[data-group-hidden]').value=title;row.querySelector('[data-position-number]').textContent=`${gi+1}.${ri+1}`;sum+=num(row.querySelector('[data-line-total]')?.dataset.raw)});const out=g.querySelector('[data-group-total]');if(out)out.textContent=money.format(sum)});}
  function calc(){let net=0,cost=0;document.querySelectorAll('[data-position]').forEach(row=>{const qty=num(row.querySelector('[name=item_quantity]')?.value),purchase=num(row.querySelector('[name=item_purchase_price]')?.value),markup=num(row.querySelector('[name=item_markup_percent]')?.value);const unit=purchase*(1+markup/100),markupValue=unit-purchase,total=qty*unit;row.querySelector('[name=item_price]').value=unit.toFixed(2);const map=[["[data-markup-value]",markupValue],["[data-unit-price]",unit],["[data-line-total]",total]];map.forEach(([s,v])=>{const o=row.querySelector(s);if(o){o.textContent=money.format(v);o.dataset.raw=String(v)}});if(row.querySelector('[name=item_service_model]').value==='normal'){net+=total;cost+=qty*purchase}});const dtype=form.querySelector('[name=discount_type]')?.value||'percent',dv=num(form.querySelector('[name=discount_value]')?.value);const discount=dtype==='fixed'?Math.min(net,dv):net*dv/100;const taxable=Math.max(0,net-discount);const taxText=form.querySelector('[name=document_tax_code] option:checked')?.textContent||'19';const rate=taxText.includes('19 %')?19:(taxText.includes('7 %')?7:0);const gross=taxable*(1+rate/100);document.querySelector('[data-summary-net]').textContent=money.format(taxable);document.querySelector('[data-summary-cost]').textContent=money.format(cost);document.querySelector('[data-summary-margin]').textContent=money.format(taxable-cost);document.querySelector('[data-summary-gross]').textContent=money.format(gross);syncGroups()}
  form.addEventListener('input',calc);form.addEventListener('change',calc);calc();
  function newPosition(group){const tpl=document.querySelector('#tt-position-template');const node=tpl.content.firstElementChild.cloneNode(true);group.querySelector('[data-group-body]').appendChild(node);syncGroups();calc();return node}
  document.addEventListener('click',e=>{const b=e.target.closest('[data-add-position]');if(b){newPosition(groupOf(b));return}if(e.target.closest('[data-delete-position]')){e.target.closest('[data-position]').remove();syncGroups();calc();return}if(e.target.closest('[data-add-group]')){const shell=document.createElement('section');shell.className='tt-service-group';shell.dataset.serviceGroup='';shell.innerHTML='<header><button type="button" class="tt-collapse" data-collapse>▾</button><span class="tt-grip" draggable="true">⠿</span><input class="tt-group-title" value="Neue Leistungsgruppe"><strong data-group-total>0,00 €</strong><button type="button" class="tt-menu" data-group-menu>•••</button></header><div class="tt-group-body" data-group-body></div><button type="button" class="tt-add-position" data-add-position>＋ Position hinzufügen</button>';document.querySelector('[data-service-groups]').appendChild(shell);newPosition(shell);return}if(e.target.closest('[data-collapse]')){const g=groupOf(e.target);const body=g.querySelector('[data-group-body]');body.hidden=!body.hidden;return}if(e.target.closest('[data-group-action]')){const button=e.target.closest('[data-group-action]'),g=groupOf(button),a=button.dataset.groupAction;button.closest('details')?.removeAttribute('open');if(a==='rename'){const input=g.querySelector('.tt-group-title');input.focus();input.select()}else if(a==='copy'){const clone=g.cloneNode(true);g.after(clone)}else if(a==='margin'){window.ttMarginScope=g;modal('[data-margin-modal]',true)}else if(a==='up'&&g.previousElementSibling){g.parentNode.insertBefore(g,g.previousElementSibling)}else if(a==='down'&&g.nextElementSibling){g.parentNode.insertBefore(g.nextElementSibling,g)}else if(a==='delete'&&confirm('Leistungsgruppe wirklich löschen?')){g.remove()}syncGroups();calc();return}if(e.target.closest('[data-browse-articles]')){window.ttTargetRow=e.target.closest('[data-position]');modal('[data-article-modal]',true);document.querySelector('[data-advanced-query]')?.focus();searchAdvanced();return}if(e.target.closest('[data-close-modal]')){e.target.closest('.tt-modal').hidden=true;return}if(e.target.closest('[data-template-open]')){window.ttTemplateKind=e.target.closest('[data-template-open]').dataset.templateOpen;modal('[data-template-modal]',true);return}const choice=e.target.closest('[data-template-choice]');if(choice&&choice.dataset.kind===window.ttTemplateKind){if(choice.dataset.kind==='intro'){form.querySelector('[name=document_salutation]').value=choice.dataset.salutation||form.querySelector('[name=document_salutation]').value;form.querySelector('[name=intro_text]').value=choice.dataset.body||''}else form.querySelector('[name=closing_text]').value=choice.dataset.body||'';modal('[data-template-modal]',false);return}if(e.target.closest('[data-adjust-markups]')){window.ttMarginScope=form;modal('[data-margin-modal]',true);return}if(e.target.closest('[data-open-dunning]')){modal('[data-dunning-modal]',true);return}const copy=e.target.closest('[data-copy-link]');if(copy){navigator.clipboard?.writeText(copy.dataset.link);copy.textContent='Link kopiert';setTimeout(()=>copy.textContent='Webansicht kopieren',1400);return}});
  const customerSelect=document.querySelector('[data-customer-preview]'),projectSelect=document.querySelector('[data-project-preview]'),top=document.querySelector('.tt-document-top');
  const setAddress=(value)=>{const p=document.querySelector('[data-address-preview]');if(p)p.innerHTML=value?`<strong>Adresse</strong><span>${value}</span>`:'<span>Bitte zuerst einen Kunden oder ein Projekt auswählen.</span>'};
  customerSelect?.addEventListener('change',e=>{const opt=e.target.selectedOptions[0];setAddress(opt?.dataset.address||'');if(projectSelect){[...projectSelect.options].forEach(o=>{if(!o.value)return;o.hidden=!!e.target.value&&o.dataset.customerId!==e.target.value});if(projectSelect.selectedOptions[0]?.hidden)projectSelect.value=''}});
  projectSelect?.addEventListener('change',e=>{const opt=e.target.selectedOptions[0];if(opt?.dataset.customerId&&customerSelect){customerSelect.value=opt.dataset.customerId}setAddress(opt?.dataset.address||customerSelect?.selectedOptions[0]?.dataset.address||'')});
  document.querySelector('[data-new-customer]')?.addEventListener('click',()=>modal('[data-customer-modal]',true));document.querySelector('[data-new-project]')?.addEventListener('click',()=>{if(!customerSelect?.value){alert('Bitte zuerst einen Kunden auswählen.');return}modal('[data-project-modal]',true)});
  const csrf=()=>form.querySelector('[name=csrfmiddlewaretoken]')?.value||'';
  document.querySelector('[data-quick-customer-form]')?.addEventListener('submit',async e=>{e.preventDefault();const error=e.target.querySelector('[data-quick-error]');if(error)error.textContent='';try{const r=await fetch(top.dataset.quickCustomerUrl,{method:'POST',headers:{'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'},body:new FormData(e.target)}),d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'Kunde konnte nicht angelegt werden.');const o=new Option(`${d.customer.number} · ${d.customer.name}`,d.customer.id,true,true);o.dataset.address=d.customer.address||'';customerSelect.appendChild(o);customerSelect.dispatchEvent(new Event('change',{bubbles:true}));modal('[data-customer-modal]',false);e.target.reset()}catch(err){if(error)error.textContent=err.message}});
  document.querySelector('[data-quick-project-form]')?.addEventListener('submit',async e=>{e.preventDefault();const fd=new FormData(e.target);fd.set('customer_id',customerSelect.value);const error=e.target.querySelector('[data-quick-error]');if(error)error.textContent='';try{const r=await fetch(top.dataset.quickProjectUrl,{method:'POST',headers:{'X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'},body:fd}),d=await r.json();if(!r.ok||!d.ok)throw new Error(d.error||'Projekt konnte nicht angelegt werden.');const o=new Option(`${d.project.number} · ${d.project.title}`,d.project.id,true,true);o.dataset.customerId=String(d.project.customer_id);o.dataset.address=d.project.address||'';projectSelect.appendChild(o);projectSelect.dispatchEvent(new Event('change',{bubbles:true}));modal('[data-project-modal]',false);e.target.reset()}catch(err){if(error)error.textContent=err.message}});
  document.querySelector('[data-margin-form]')?.addEventListener('submit',e=>{e.preventDefault();const scope=window.ttMarginScope||form,type=e.target.elements.position_type.value,markup=e.target.elements.markup.value;scope.querySelectorAll('[data-position]').forEach(row=>{if(type==='all'||row.querySelector('[name=item_type]')?.value===type){row.querySelector('[name=item_markup_percent]').value=markup}});modal('[data-margin-modal]',false);e.target.reset();calc()});
  let draggedGroup=null;
  document.addEventListener('dragstart',e=>{const grip=e.target.closest('.tt-grip');if(grip){draggedGroup=grip.closest('[data-service-group]');e.dataTransfer.effectAllowed='move'}});
  document.addEventListener('dragover',e=>{if(draggedGroup&&e.target.closest('[data-service-group]'))e.preventDefault()});
  document.addEventListener('drop',e=>{if(!draggedGroup)return;const target=e.target.closest('[data-service-group]');if(!target||target===draggedGroup)return;e.preventDefault();const rect=target.getBoundingClientRect();target.parentNode.insertBefore(draggedGroup,e.clientY>rect.top+rect.height/2?target.nextSibling:target);draggedGroup=null;syncGroups();calc()});
  const endpoint=form.dataset.articleSearchUrl;let searchTimer=null;async function query(q,source='all',type='all'){const url=new URL(endpoint,location.origin);url.searchParams.set('q',q);url.searchParams.set('source',source);url.searchParams.set('type',type);try{const r=await fetch(url,{headers:{'X-Requested-With':'XMLHttpRequest'}});const d=await r.json();return d.ok?d.results:[]}catch(_){return[]}}
  function apply(row,item){row.querySelector('[name=item_description]').value=item.name||'';row.querySelector('[name=item_unit]').value=item.unit||'Stk.';row.querySelector('[name=item_purchase_price]').value=Number(item.purchase||item.sales||0).toFixed(2);row.querySelector('[name=item_markup_percent]').value='0';row.querySelector('[name=item_price]').value=Number(item.sales||item.purchase||0).toFixed(2);row.querySelector('[name=item_catalog_id]').value=item.kind==='catalog'?(item.id||''):'';row.querySelector('.tt-typeahead')?.remove();calc()}
  async function inlineSearch(input){const q=input.value.trim(),row=input.closest('[data-position]');row.querySelector('.tt-typeahead')?.remove();if(q.length<2)return;const rows=await query(q);if(input.value.trim()!==q)return;const pop=document.createElement('div');pop.className='tt-typeahead';rows.slice(0,8).forEach(item=>{const b=document.createElement('button');b.type='button';b.className='tt-search-result';b.innerHTML=`<span><strong>${item.name}</strong><small>${[item.code,item.unit,item.source].filter(Boolean).join(' · ')}</small></span><strong>${money.format(num(item.sales))}</strong>`;b.addEventListener('mousedown',ev=>ev.preventDefault());b.addEventListener('click',()=>apply(row,item));pop.appendChild(b)});const all=document.createElement('button');all.type='button';all.className='tt-browse';all.textContent='Artikel durchsuchen';all.addEventListener('click',()=>{window.ttTargetRow=row;modal('[data-article-modal]',true);document.querySelector('[data-advanced-query]').value=q;searchAdvanced()});pop.appendChild(all);input.parentElement.appendChild(pop)}
  form.addEventListener('input',e=>{if(e.target.matches('[data-position-search]')){clearTimeout(searchTimer);searchTimer=setTimeout(()=>inlineSearch(e.target),180)}});
  async function searchAdvanced(){const q=document.querySelector('[data-advanced-query]')?.value||'',source=document.querySelector('[data-advanced-source]')?.value||'all',type=document.querySelector('[data-advanced-type]')?.value||'all',out=document.querySelector('[data-advanced-results]');if(!out)return;out.innerHTML='<p>Artikel werden gesucht …</p>';const rows=await query(q,source,type);out.innerHTML='';rows.forEach(item=>{const b=document.createElement('button');b.type='button';b.className='tt-search-result';b.innerHTML=`<span><strong>${item.name}</strong><small>${[item.code,item.unit,item.source].filter(Boolean).join(' · ')}</small></span><strong>${money.format(num(item.sales))}</strong>`;b.addEventListener('click',()=>{apply(window.ttTargetRow,item);modal('[data-article-modal]',false)});out.appendChild(b)});if(!rows.length)out.innerHTML='<p>Keine passenden Artikel gefunden.</p>'}
  ['[data-advanced-query]','[data-advanced-source]','[data-advanced-type]'].forEach(s=>document.querySelector(s)?.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(searchAdvanced,180)}));
  let dragged=null;document.addEventListener('dragstart',e=>{const row=e.target.closest('[data-position]');if(row){dragged=row;e.dataTransfer.effectAllowed='move'}});document.addEventListener('dragover',e=>{if(dragged&&e.target.closest('[data-group-body]'))e.preventDefault()});document.addEventListener('drop',e=>{if(!dragged)return;const target=e.target.closest('[data-position]'),body=e.target.closest('[data-group-body]');if(!body)return;e.preventDefault();if(target&&target!==dragged)body.insertBefore(dragged,target);else body.appendChild(dragged);dragged=null;syncGroups();calc()});
})();

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

// A+BAU V3 QUOTE EDITOR RUNTIME FIX 2026-09-08
(() => {
  'use strict';
  const editor = document.querySelector('.tt-document-form');
  if (!editor) return;
  const top = document.querySelector('.tt-document-top');
  const customerSelect = document.querySelector('[data-customer-select]');
  const projectSelect = document.querySelector('[data-project-select]');
  const projectForm = document.querySelector('[data-quick-project-form]');
  const templateModal = document.querySelector('[data-template-modal]');
  const money = new Intl.NumberFormat('de-DE', {style:'currency', currency:'EUR'});
  const num = value => {
    const parsed = Number(String(value ?? '0').replace(',', '.'));
    return Number.isFinite(parsed) ? parsed : 0;
  };

  // Own template opening in capture phase so older finance/V3 click handlers never
  // open a second chooser behind the first one. Close any stale sibling modal first.
  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-template-open]');
    if (!trigger) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    document.querySelectorAll('.tt-modal').forEach(modal => {
      if (modal !== templateModal) modal.hidden = true;
    });
    window.ttTemplateKind = trigger.dataset.templateOpen || 'intro';
    if (templateModal) templateModal.hidden = false;
  }, true);

  const showProjectError = message => {
    const error = projectForm?.querySelector('[data-quick-error]');
    if (error) error.textContent = message || '';
  };

  const csrf = () => editor.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

  const createProject = ({url, title, customerId}) => new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', new URL(url, window.location.origin).href, true);
    xhr.withCredentials = true;
    xhr.setRequestHeader('X-CSRFToken', csrf());
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded;charset=UTF-8');
    xhr.timeout = 15000;
    xhr.onload = () => {
      let data = null;
      try { data = JSON.parse(xhr.responseText || '{}'); } catch (_) {}
      if (xhr.status >= 200 && xhr.status < 300 && data?.ok) {
        resolve(data);
        return;
      }
      const fallback = xhr.status === 403
        ? 'Sitzung abgelaufen. Bitte die Seite neu laden und erneut versuchen.'
        : `Projekt konnte nicht angelegt werden${xhr.status ? ` (HTTP ${xhr.status})` : ''}.`;
      reject(new Error(data?.error || fallback));
    };
    xhr.onerror = () => reject(new Error('Projekt konnte wegen eines Netzwerkfehlers nicht angelegt werden. Bitte erneut versuchen.'));
    xhr.ontimeout = () => reject(new Error('Die Projektanlage hat zu lange gedauert. Bitte erneut versuchen.'));
    const body = new URLSearchParams({title, customer_id: customerId, csrfmiddlewaretoken: csrf()});
    xhr.send(body.toString());
  });

  // Replace the older fetch-based quick-project owner. The production symptom was
  // the browser-level TypeError "Failed to fetch"; same-origin XHR keeps cookies and
  // CSRF deterministic and surfaces the actual server/network failure to the user.
  projectForm?.addEventListener('submit', async event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    const title = projectForm.elements.title?.value?.trim() || '';
    const customerId = customerSelect?.value || '';
    if (!customerId) { showProjectError('Bitte zuerst einen Kunden auswählen.'); return; }
    if (!title) { showProjectError('Bitte einen Projekttitel eingeben.'); return; }
    const url = top?.dataset.quickProjectUrl || '';
    if (!url) { showProjectError('Die Projekt-Schnittstelle ist nicht verfügbar.'); return; }
    const submit = projectForm.querySelector('[type=submit]');
    if (submit) submit.disabled = true;
    showProjectError('');
    try {
      const data = await createProject({url, title, customerId});
      const option = new Option(`${data.project.number} · ${data.project.title}`, data.project.id, true, true);
      option.dataset.customerId = String(data.project.customer_id);
      option.dataset.address = data.project.address || '';
      projectSelect?.appendChild(option);
      projectSelect?.dispatchEvent(new Event('change', {bubbles:true}));
      const modal = projectForm.closest('.tt-modal');
      if (modal) modal.hidden = true;
      projectForm.reset();
    } catch (error) {
      showProjectError(error?.message || 'Projekt konnte nicht angelegt werden.');
    } finally {
      if (submit) submit.disabled = false;
    }
  }, true);

  const summaryValue = (selector, value) => {
    const output = document.querySelector(selector);
    if (output) output.textContent = money.format(value);
  };

  function updateBreakdown() {
    const costs = {material:0, labour:0, other:0};
    const markups = {material:0, labour:0, other:0};
    editor.querySelectorAll('[data-position]').forEach(row => {
      const quantity = num(row.querySelector('[name=item_quantity]')?.value);
      const purchase = num(row.querySelector('[name=item_purchase_price]')?.value);
      const markupPercent = num(row.querySelector('[name=item_markup_percent]')?.value);
      const type = row.querySelector('[name=item_type]')?.value || 'other';
      const bucket = type === 'material' ? 'material' : (type === 'labour' ? 'labour' : 'other');
      costs[bucket] += quantity * purchase;
      markups[bucket] += quantity * purchase * markupPercent / 100;
    });
    summaryValue('[data-summary-cost-material]', costs.material);
    summaryValue('[data-summary-cost-labour]', costs.labour);
    summaryValue('[data-summary-cost-other]', costs.other);
    summaryValue('[data-summary-markup-material]', markups.material);
    summaryValue('[data-summary-markup-labour]', markups.labour);
    summaryValue('[data-summary-markup-other]', markups.other);
  }

  function ensurePositionHeaders() {
    editor.querySelectorAll('[data-service-group]').forEach(group => {
      if (group.querySelector(':scope > .tt-position-columns')) return;
      const body = group.querySelector(':scope > [data-group-body]');
      if (!body) return;
      const header = document.createElement('div');
      header.className = 'tt-position-columns';
      header.setAttribute('aria-hidden', 'true');
      header.innerHTML = '<span></span><span>Nr.</span><span>Typ</span><span>Menge</span><span>Einheit</span><span>Beschreibung</span><span>Einkaufspreis</span><span>Aufschlag</span><span>Aufschlagwert</span><span>VK</span><span>Einzelpreis</span><span>Gesamtpreis</span><span></span>';
      body.before(header);
    });
  }

  editor.addEventListener('input', updateBreakdown);
  editor.addEventListener('change', updateBreakdown);
  const groups = editor.querySelector('[data-service-groups]');
  if (groups) new MutationObserver(() => { ensurePositionHeaders(); updateBreakdown(); }).observe(groups, {childList:true, subtree:true});
  ensurePositionHeaders();
  updateBreakdown();
})();

