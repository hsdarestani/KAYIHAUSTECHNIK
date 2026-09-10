import { Capacitor, registerPlugin } from '@capacitor/core';

const Scanner = registerPlugin('KayiRoomScanner');
// Native navigation contract: data-route="scanner"
const API = 'https://kayi.smarbiz.sbs';
const OFFICE_ROLES = new Set(['admin', 'owner', 'manager', 'office', 'accounting']);
const state = {
  baseUrl: localStorage.getItem('ab.baseUrl') || API,
  token: localStorage.getItem('ab.token') || '',
  user: JSON.parse(localStorage.getItem('ab.user') || 'null'),
  route: 'home', data: {}, capabilities: null, loading: false,
  selectedCustomerId: null, selectedProjectId: null, editingId: null,
};
const root = document.querySelector('#app');
const toastStack = document.querySelector('#toast-stack');
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const list = (payload) => Array.isArray(payload) ? payload : (payload?.results || []);
const isOffice = () => OFFICE_ROLES.has(state.user?.role);
const roleName = () => isOffice() ? 'Büro & Administration' : 'Mitarbeiter';
const fullName = () => state.user?.name || state.user?.username || 'A+Bau';

function toast(message, type = 'success') {
  const node = document.createElement('div');
  node.className = `toast toast-${type}`;
  node.setAttribute('role', type === 'error' ? 'alert' : 'status');
  node.textContent = message;
  toastStack.append(node);
  setTimeout(() => node.remove(), 4500);
}

async function api(path, options = {}) {
  const headers = {Accept:'application/json', ...(options.headers || {})};
  if (state.token) headers.Authorization = `Token ${state.token}`;
  const response = await fetch(state.baseUrl + path, {...options, headers});
  const body = response.status === 204 ? {} : await response.json().catch(() => ({}));
  if (response.status === 401) { logout(false); throw new Error('Sitzung abgelaufen. Bitte erneut anmelden.'); }
  if (!response.ok) throw new Error(body.detail || body.error || 'Aktion konnte nicht abgeschlossen werden.');
  return body;
}

async function login(event) {
  event.preventDefault();
  const form = event.currentTarget;
  setBusy(form, true, 'Anmeldung läuft …');
  try {
    state.baseUrl = form.server.value.replace(/\/$/, '');
    const data = await api('/api/mobile/login/', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:form.username.value, password:form.password.value})});
    state.token = data.token; state.user = data.user;
    localStorage.setItem('ab.baseUrl', state.baseUrl); localStorage.setItem('ab.token', state.token); localStorage.setItem('ab.user', JSON.stringify(state.user));
    await bootstrap(); toast(`Willkommen, ${fullName()}.`);
  } catch (error) { setBusy(form, false, error.message, true); }
}

function setBusy(form, busy, message = '', error = false) {
  form?.setAttribute('aria-busy', String(busy));
  const button = form?.querySelector('button[type="submit"]'); if (button) button.disabled = busy;
  const status = form?.querySelector('[data-status]'); if (status) { status.textContent = message; status.className = `form-status${error ? ' is-error' : ''}`; }
}

async function bootstrap() {
  state.loading = true; renderShell();
  try {
    const common = [api('/api/projects/?ordering=-updated_at&page_size=100'), api('/api/events/?ordering=starts_at&page_size=100'), api('/api/tasks/?ordering=-created_at&page_size=100')];
    const office = isOffice() ? [api('/api/customers/?ordering=-created_at&page_size=100'), api('/api/quotes/?ordering=-created_at&page_size=100'), api('/api/invoices/?ordering=-created_at&page_size=100')] : [Promise.resolve([]), Promise.resolve([]), Promise.resolve([])];
    const [projects, events, tasks, customers, quotes, invoices] = await Promise.all([...common, ...office]);
    state.data = {projects:list(projects), events:list(events), tasks:list(tasks), customers:list(customers), quotes:list(quotes), invoices:list(invoices)};
    state.capabilities = await Scanner.getCapabilities().catch(() => ({supported:false, fallback:false, provider:'web'}));
    state.loading = false; renderShell();
  } catch (error) { state.loading = false; renderShell(); toast(error.message, 'error'); }
}

function renderLogin(message = '') {
  root.innerHTML = `<section class="login-screen"><div class="login-brand"><div class="brand-mark">A+</div><div><h1>A+Bau</h1><p>Die komplette Arbeit in einer App.</p></div></div><form class="login-card" id="login-form"><label>Server<input name="server" type="url" value="${esc(state.baseUrl)}" required></label><label>Benutzername<input name="username" autocomplete="username" required></label><label>Passwort<input name="password" type="password" autocomplete="current-password" required></label><button class="primary" type="submit">Anmelden</button><p class="form-status${message ? ' is-error' : ''}" data-status role="status">${esc(message || 'Mit deinem persönlichen A+Bau-Konto anmelden.')}</p></form></section>`;
  document.querySelector('#login-form').addEventListener('submit', login);
}

function navItems() {
  if (isOffice()) return [['home','⌂','Start'],['projects','▣','Projekte'],['appointments','◫','Termine'],['customers','◎','Kunden'],['more','•••','Mehr']];
  return [['home','⌂','Heute'],['appointments','◫','Einsätze'],['projects','▣','Projekte'],['time','◷','Zeit'],['more','•••','Mehr']];
}

function renderShell() {
  root.innerHTML = `<div class="app-shell"><header class="topbar"><div class="mini-brand"><span>A+</span><div><b>A+Bau</b><small>${esc(roleName())}</small></div></div><button class="avatar" data-route="profile" aria-label="Konto öffnen">${esc(fullName().slice(0,2).toUpperCase())}</button></header><section class="content">${state.loading ? loadingView() : renderRoute()}</section><nav class="bottom-nav" aria-label="Hauptnavigation">${navItems().map(([id,icon,label]) => `<button data-route="${id}" class="${state.route===id?'is-active':''}"><span>${icon}</span>${label}</button>`).join('')}</nav></div>`;
  bindActions();
}

const loadingView = () => '<section class="loading"><div class="spinner"></div><p>Arbeitsbereich wird synchronisiert …</p></section>';
function renderRoute() {
  const routes = {home:renderHome, projects:renderProjects, 'project-detail':renderProjectDetail, 'project-form':renderProjectForm, appointments:renderAppointments, customers:renderCustomers, 'customer-detail':renderCustomerDetail, 'customer-form':renderCustomerForm, time:renderTime, scanner:renderScanner, commercial:renderCommercial, tasks:renderTasks, more:renderMore, profile:renderProfile};
  return (routes[state.route] || renderHome)();
}

function pageHead(kicker, title, text, action = '') { return `<header class="page-head"><div><small>${esc(kicker)}</small><h1>${esc(title)}</h1><p>${esc(text)}</p></div>${action}</header>`; }
function metric(value, label, tone='') { return `<article class="metric ${tone}"><strong>${value}</strong><span>${esc(label)}</span></article>`; }
function renderHome() {
  const today = new Date().toISOString().slice(0,10);
  const todays = state.data.events.filter(x => String(x.starts_at || '').startsWith(today));
  const openTasks = state.data.tasks.filter(x => !['done','completed'].includes(x.status));
  if (isOffice()) return `${pageHead('OPERATIONS',`Guten Tag, ${fullName().split(' ')[0]}.`,'Kunden, Projekte und kaufmännische Arbeit auf einen Blick.','<button class="round-action" data-route="more">＋</button>')}<section class="metrics">${metric(state.data.projects.filter(x=>!['completed','cancelled'].includes(x.status)).length,'Aktive Projekte')}${metric(todays.length,'Termine heute','gold')}${metric(state.data.quotes.filter(x=>!['accepted','rejected'].includes(x.status)).length,'Offene Angebote')}${metric(state.data.invoices.filter(x=>!['paid','cancelled'].includes(x.status)).length,'Offene Rechnungen','danger')}</section>${agenda(todays)}${quickActions(true)}`;
  return `${pageHead('MEINE ARBEIT',`Hallo, ${fullName().split(' ')[0]}.`,'Deine Einsätze, Aufgaben, Zeiten und Projektdaten.')}<section class="metrics two">${metric(todays.length,'Einsätze heute','gold')}${metric(openTasks.length,'Offene Aufgaben')}</section>${agenda(todays)}${quickActions(false)}`;
}

function agenda(events) { return `<section class="panel"><header><h2>Heute</h2><button data-route="appointments">Alle Termine</button></header><div class="rows">${events.slice(0,5).map(eventRow).join('') || '<div class="empty">Heute sind keine Termine eingetragen.</div>'}</div></section>`; }
function eventRow(item) { const time = item.starts_at ? new Date(item.starts_at).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'}) : '—'; return `<article class="row"><time>${esc(time)}</time><div><b>${esc(item.title)}</b><small>${esc(item.location || item.project_title || 'Kein Ort')}</small></div><span>›</span></article>`; }
function quickActions(office) { const actions = office ? [['customers','◎','Kunde'],['projects','▣','Projekt'],['appointments','◫','Termin'],['commercial','€','Angebot']] : [['time','◷','Zeit'],['scanner','⌗','Aufmaß'],['tasks','✓','Aufgaben'],['projects','▣','Projekte']]; return `<section class="quick-grid">${actions.map(([route,icon,label])=>`<button data-route="${route}"><span>${icon}</span><b>${label}</b></button>`).join('')}</section>`; }

function renderProjects() { const action=isOffice()?'<button class="round-action" data-new-project aria-label="Neues Projekt">＋</button>':''; return `${pageHead('PROJEKTE', isOffice()?'Alle Projekte':'Meine Projekte', isOffice()?'Aktive Aufträge und Projektstatus.':'Nur dir zugewiesene Projekte.',action)}<div class="rows cards">${state.data.projects.map(p=>`<article class="project-card"><button class="card-open" data-project-id="${p.id}" aria-label="Projekt ${esc(p.title)} öffnen"><header><span>${esc(p.number || 'PROJEKT')}</span><em>${esc(p.status || '')}</em></header><h2>${esc(p.title)}</h2><p>${esc(p.customer_name || p.description || '')}</p></button><footer><button data-scan-project="${p.id}">⌗ Raum aufmessen</button></footer></article>`).join('') || '<div class="empty">Keine Projekte verfügbar.</div>'}</div>`; }
function renderAppointments() { return `${pageHead('KALENDER',isOffice()?'Termine & Einsätze':'Meine Einsätze',isOffice()?'Planung für Team und Baustellen.':'Deine zugewiesenen Termine.')}<div class="rows cards">${state.data.events.map(eventRow).join('') || '<div class="empty">Keine Termine verfügbar.</div>'}</div>`; }
function renderCustomers() { if (!isOffice()) return forbidden(); return `${pageHead('STAMMDATEN','Kunden','Kontakte und zugehörige Projekte.','<button class="round-action" data-new-customer aria-label="Neuer Kunde">＋</button>')}<div class="rows cards">${state.data.customers.map(c=>`<button class="row row-button" data-customer-id="${c.id}"><span class="circle">${esc((c.company||c.last_name||'?').slice(0,1))}</span><div><b>${esc(c.display_name || c.company || `${c.first_name||''} ${c.last_name||''}`)}</b><small>${esc(c.number || c.email || c.phone || '')}</small></div><span>›</span></button>`).join('') || '<div class="empty">Keine Kunden vorhanden.</div>'}</div>`; }

function selectedCustomer(){return state.data.customers.find(item=>Number(item.id)===Number(state.selectedCustomerId));}
function selectedProject(){return state.data.projects.find(item=>Number(item.id)===Number(state.selectedProjectId));}
function detailActions(kind){if(!isOffice())return '';return `<button class="secondary compact" data-edit-${kind}>Bearbeiten</button>`;}
function renderCustomerDetail(){const c=selectedCustomer();if(!c)return forbidden();const projects=state.data.projects.filter(p=>Number(p.customer)===Number(c.id));return `${pageHead('KUNDE',c.display_name||c.company||`${c.first_name||''} ${c.last_name||''}`,c.number||'',detailActions('customer'))}<section class="detail-card"><dl><div><dt>Firma</dt><dd>${esc(c.company||'—')}</dd></div><div><dt>Ansprechpartner</dt><dd>${esc(`${c.first_name||''} ${c.last_name||''}`.trim()||'—')}</dd></div><div><dt>E-Mail</dt><dd>${c.email?`<a href="mailto:${esc(c.email)}">${esc(c.email)}</a>`:'—'}</dd></div><div><dt>Telefon</dt><dd>${c.phone?`<a href="tel:${esc(c.phone)}">${esc(c.phone)}</a>`:'—'}</dd></div><div><dt>Adresse</dt><dd>${esc([c.street,c.postal_code,c.city].filter(Boolean).join(', ')||'—')}</dd></div><div><dt>Notizen</dt><dd>${esc(c.notes||'—')}</dd></div></dl></section><section class="panel"><header><h2>Projekte</h2>${isOffice()?'<button data-new-project-for-customer>Projekt anlegen</button>':''}</header><div class="rows">${projects.map(p=>`<button class="row row-button" data-project-id="${p.id}"><span class="circle">▣</span><div><b>${esc(p.title)}</b><small>${esc(p.number||p.status||'')}</small></div><span>›</span></button>`).join('')||'<div class="empty">Noch keine Projekte.</div>'}</div></section>`;}
function renderCustomerForm(){if(!isOffice())return forbidden();const c=state.editingId?state.data.customers.find(x=>Number(x.id)===Number(state.editingId)):null;return `${pageHead('KUNDE',c?'Kunde bearbeiten':'Neuer Kunde','Stammdaten vollständig und korrekt erfassen.')}<form class="entity-form" data-customer-form><div class="form-grid"><label>Kundentyp<select name="type"><option value="private" ${c?.type==='private'?'selected':''}>Privatkunde</option><option value="business" ${c?.type==='business'?'selected':''}>Geschäftskunde</option><option value="insurance" ${c?.type==='insurance'?'selected':''}>Versicherung</option><option value="property_manager" ${c?.type==='property_manager'?'selected':''}>Hausverwaltung</option></select></label><label>Firma<input name="company" value="${esc(c?.company||'')}"></label><label>Vorname<input name="first_name" value="${esc(c?.first_name||'')}"></label><label>Nachname<input name="last_name" value="${esc(c?.last_name||'')}"></label><label>E-Mail<input name="email" type="email" value="${esc(c?.email||'')}"></label><label>Telefon<input name="phone" type="tel" value="${esc(c?.phone||'')}"></label><label class="wide">Straße<input name="street" value="${esc(c?.street||'')}"></label><label>PLZ<input name="postal_code" value="${esc(c?.postal_code||'')}"></label><label>Ort<input name="city" value="${esc(c?.city||'')}"></label><label class="wide">Notizen<textarea name="notes" rows="4">${esc(c?.notes||'')}</textarea></label></div><p class="form-hint">Mindestens Firma oder Vor-/Nachname eintragen.</p><button class="primary" type="submit">${c?'Änderungen speichern':'Kunde anlegen'}</button><button class="secondary" type="button" data-cancel-entity>Abbrechen</button></form>`;}

function renderProjectDetail(){const p=selectedProject();if(!p)return forbidden();const customer=state.data.customers.find(c=>Number(c.id)===Number(p.customer));return `${pageHead('PROJEKT',p.title,p.number||'',detailActions('project'))}<section class="detail-card"><dl><div><dt>Kunde</dt><dd>${esc(p.customer_name||customer?.display_name||'—')}</dd></div><div><dt>Status</dt><dd>${esc(p.status||'—')}</dd></div><div><dt>Priorität</dt><dd>${esc(p.priority||'—')}</dd></div><div><dt>Zeitraum</dt><dd>${esc([p.planned_start,p.planned_end].filter(Boolean).join(' – ')||'—')}</dd></div><div><dt>Beschreibung</dt><dd>${esc(p.description||'—')}</dd></div></dl><div class="detail-actions"><button class="secondary" data-scan-project="${p.id}">⌗ Raum aufmessen</button><button class="secondary" data-route="appointments">◫ Termine</button></div></section>`;}
function renderProjectForm(){if(!isOffice())return forbidden();const p=state.editingId?state.data.projects.find(x=>Number(x.id)===Number(state.editingId)):null;const preset=state.selectedCustomerId||p?.customer||'';return `${pageHead('PROJEKT',p?'Projekt bearbeiten':'Neues Projekt','Kunde, Status und Ausführungsdaten festlegen.')}<form class="entity-form" data-project-form><div class="form-grid"><label class="wide">Titel<input name="title" value="${esc(p?.title||'')}" required></label><label class="wide">Kunde<select name="customer" required><option value="">Kunde auswählen</option>${state.data.customers.map(c=>`<option value="${c.id}" ${Number(c.id)===Number(preset)?'selected':''}>${esc(c.display_name||c.company||c.number)}</option>`).join('')}</select></label><label>Auftragsart<select name="job_type"><option value="private" ${p?.job_type!=='insurance'?'selected':''}>Privatauftrag</option><option value="insurance" ${p?.job_type==='insurance'?'selected':''}>Versicherung / B&amp;O</option></select></label><label>Status<select name="status">${[['inquiry','Anfrage'],['planning','Planung'],['quoted','Angebot'],['confirmed','Beauftragt'],['in_progress','In Ausführung'],['waiting','Wartet'],['review','Abnahme'],['invoiced','Abgerechnet'],['completed','Abgeschlossen'],['cancelled','Storniert']].map(([v,l])=>`<option value="${v}" ${p?.status===v?'selected':''}>${l}</option>`).join('')}</select></label><label>Priorität<select name="priority">${[['low','Niedrig'],['normal','Normal'],['high','Hoch'],['urgent','Dringend']].map(([v,l])=>`<option value="${v}" ${(p?.priority||'normal')===v?'selected':''}>${l}</option>`).join('')}</select></label><label>Start<input name="planned_start" type="date" value="${esc(p?.planned_start||'')}"></label><label>Ende<input name="planned_end" type="date" value="${esc(p?.planned_end||'')}"></label><label class="wide">Beschreibung<textarea name="description" rows="5">${esc(p?.description||'')}</textarea></label></div><button class="primary" type="submit">${p?'Änderungen speichern':'Projekt anlegen'}</button><button class="secondary" type="button" data-cancel-entity>Abbrechen</button></form>`;}
function renderTasks() { return `${pageHead('AUFGABEN',isOffice()?'Team-Aufgaben':'Meine Aufgaben','Offene Punkte für die Ausführung.')}<div class="rows cards">${state.data.tasks.map(t=>`<article class="row"><span class="task-dot ${esc(t.priority||'')}"></span><div><b>${esc(t.title)}</b><small>${esc(t.project_title || t.status || '')}</small></div><span>›</span></article>`).join('') || '<div class="empty">Keine Aufgaben vorhanden.</div>'}</div>`; }
function renderCommercial() { if(!isOffice()) return forbidden(); return `${pageHead('KAUFMÄNNISCH','Angebote & Rechnungen','Nur für berechtigte Büro-Rollen sichtbar.')}<section class="metrics two">${metric(state.data.quotes.length,'Angebote','gold')}${metric(state.data.invoices.length,'Rechnungen')}</section><section class="menu-list"><button><span>◇</span><div><b>Angebote</b><small>Erstellen, prüfen und versenden</small></div><em>${state.data.quotes.length}</em></button><button><span>€</span><div><b>Rechnungen</b><small>Entwürfe, Fälligkeiten und Zahlungen</small></div><em>${state.data.invoices.length}</em></button></section>`; }
function renderTime() { return `${pageHead('ZEITERFASSUNG','Arbeitszeit','Start und Stopp werden projektbezogen protokolliert.')}<section class="time-card"><div class="time-icon">◷</div><h2>Bereit für den nächsten Einsatz?</h2><p>Wähle im nächsten Schritt ein Projekt und starte die Arbeitszeit.</p><button class="primary" data-time-start>Arbeit starten</button></section>`; }
function renderScanner() { const caps=state.capabilities||{}; return `${pageHead('AUFMASS','Raum erfassen','Der Scanner ist ein Werkzeug innerhalb des vollständigen A+Bau-Workflows.')}<section class="scan-card"><span class="scan-icon">⌗</span><h2>${caps.lidar?'LiDAR bereit':caps.fallback?'Manuelles Aufmaß verfügbar':caps.supported?'Scanner bereit':'Scanner nicht verfügbar'}</h2><p>${esc(caps.provider || Capacitor.getPlatform())}</p><label>Projekt<select id="scan-project"><option value="">Projekt auswählen</option>${state.data.projects.map(p=>`<option value="${p.id}">${esc(p.number)} · ${esc(p.title)}</option>`).join('')}</select></label><button class="primary" data-start-scan ${caps.supported?'':'disabled'}>Raum scannen</button><button class="secondary" data-pending-scans>Nicht hochgeladene Scans</button><div data-scan-result></div></section>`; }
function renderMore() { const office = isOffice(); const items = office ? [['customers','◎','Kunden'],['commercial','€','Angebote & Rechnungen'],['tasks','✓','Aufgaben'],['scanner','⌗','Aufmaß & Scanner'],['profile','⚙','Konto & Einstellungen']] : [['tasks','✓','Aufgaben'],['scanner','⌗','Aufmaß & Scanner'],['profile','⚙','Konto']]; return `${pageHead('MENÜ','Alle Bereiche','Funktionen passend zu deiner Rolle.')}<section class="menu-list">${items.map(([route,icon,title])=>`<button data-route="${route}"><span>${icon}</span><div><b>${title}</b><small>Öffnen</small></div><em>›</em></button>`).join('')}</section>`; }
function renderProfile() { return `${pageHead('KONTO',fullName(),roleName())}<section class="profile-card"><dl><div><dt>Benutzer</dt><dd>${esc(state.user?.username)}</dd></div><div><dt>Organisation</dt><dd>${esc(state.user?.organization || 'A+Bau')}</dd></div><div><dt>Rolle</dt><dd>${esc(roleName())}</dd></div></dl><button class="danger" data-logout>Abmelden</button></section>`; }
const forbidden = () => `${pageHead('BERECHTIGUNG','Nicht verfügbar','Dieser Bereich ist für deine Rolle nicht freigeschaltet.')}<button class="secondary" data-route="home">Zurück zur Startseite</button>`;

function clearScannerFeedback(){const target=document.querySelector('[data-scan-result]');if(target)target.replaceChildren();}
async function startScan(projectId){clearScannerFeedback();
  if (!projectId) return toast('Bitte zuerst ein Projekt auswählen.', 'error');
  toast('Aufmaß wird geöffnet …', 'info');
  try { const scan=await Scanner.startScan({roomName:'Raum'}); await Scanner.uploadScan({scanId:scan.scanId,projectId:Number(projectId),apiBaseUrl:state.baseUrl,token:state.token}); toast('Aufmaß gespeichert und zur Prüfung hochgeladen.'); }
  catch(error) { toast(error.message || String(error), 'error'); }
}
async function listPending(){clearScannerFeedback();try { const data=await Scanner.listPendingScans(); const scans=list(data?.scans || data); const target=document.querySelector('[data-scan-result]'); target.innerHTML=scans.length?`<ul class="pending-list">${scans.map(s=>`<li>${esc(s.roomName||'Raumaufmaß')}<small>${esc(s.createdAt||'Lokal gespeichert')}</small></li>`).join('')}</ul>`:'<p class="empty">Keine nicht hochgeladenen Scans vorhanden.</p>'; } catch(error){toast(error.message,'error');} }
async function logout(callApi=true) { if(callApi) await api('/api/mobile/logout/',{method:'POST'}).catch(()=>{}); state.token='';state.user=null;localStorage.removeItem('ab.token');localStorage.removeItem('ab.user');renderLogin(); }

function formPayload(form){return Object.fromEntries([...new FormData(form).entries()].map(([key,value])=>[key,String(value).trim()]));}
function upsert(collection,item){const index=collection.findIndex(row=>Number(row.id)===Number(item.id));if(index>=0)collection[index]=item;else collection.unshift(item);}
async function saveCustomer(event){event.preventDefault();const form=event.currentTarget;const payload=formPayload(form);if(!payload.company&&!payload.first_name&&!payload.last_name){toast('Bitte Firma oder einen Namen eintragen.','error');form.querySelector('[name="company"]')?.focus();return;}setBusy(form,true,'Kunde wird gespeichert …');try{const id=state.editingId;const saved=await api(`/api/customers/${id?`${id}/`:''}`,{method:id?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});upsert(state.data.customers,saved);state.selectedCustomerId=saved.id;state.editingId=null;state.route='customer-detail';renderShell();toast(id?'Kundendaten wurden gespeichert.':'Kunde wurde angelegt.');}catch(error){setBusy(form,false,error.message,true);toast(error.message,'error');}}
async function saveProject(event){event.preventDefault();const form=event.currentTarget;const payload=formPayload(form);payload.customer=Number(payload.customer);for(const key of ['planned_start','planned_end'])if(!payload[key])delete payload[key];setBusy(form,true,'Projekt wird gespeichert …');try{const id=state.editingId;const saved=await api(`/api/projects/${id?`${id}/`:''}`,{method:id?'PATCH':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});upsert(state.data.projects,saved);state.selectedProjectId=saved.id;state.editingId=null;state.route='project-detail';renderShell();toast(id?'Projekt wurde gespeichert.':'Projekt wurde angelegt.');}catch(error){setBusy(form,false,error.message,true);toast(error.message,'error');}}

function bindActions() {
  document.querySelectorAll('[data-route]').forEach(button => button.addEventListener('click',()=>{state.route=button.dataset.route;renderShell();window.scrollTo(0,0);}));
  document.querySelectorAll('[data-scan-project]').forEach(button=>button.addEventListener('click',()=>{state.route='scanner';renderShell();const select=document.querySelector('#scan-project');if(select)select.value=button.dataset.scanProject;}));
  document.querySelector('[data-start-scan]')?.addEventListener('click',()=>startScan(document.querySelector('#scan-project')?.value));
  document.querySelector('[data-pending-scans]')?.addEventListener('click',listPending);
  document.querySelector('[data-logout]')?.addEventListener('click',()=>logout(true));
  document.querySelector('[data-time-start]')?.addEventListener('click',()=>toast('Projektwahl und Live-Zeiterfassung folgen in Phase 3.', 'info'));
  document.querySelectorAll('[data-customer-id]').forEach(button=>button.addEventListener('click',()=>{state.selectedCustomerId=Number(button.dataset.customerId);state.route='customer-detail';renderShell();}));
  document.querySelectorAll('[data-project-id]').forEach(button=>button.addEventListener('click',()=>{state.selectedProjectId=Number(button.dataset.projectId);state.route='project-detail';renderShell();}));
  document.querySelector('[data-new-customer]')?.addEventListener('click',()=>{state.editingId=null;state.route='customer-form';renderShell();});
  document.querySelector('[data-edit-customer]')?.addEventListener('click',()=>{state.editingId=state.selectedCustomerId;state.route='customer-form';renderShell();});
  document.querySelector('[data-new-project]')?.addEventListener('click',()=>{state.editingId=null;state.selectedCustomerId=null;state.route='project-form';renderShell();});
  document.querySelector('[data-new-project-for-customer]')?.addEventListener('click',()=>{state.editingId=null;state.route='project-form';renderShell();});
  document.querySelector('[data-edit-project]')?.addEventListener('click',()=>{state.editingId=state.selectedProjectId;state.route='project-form';renderShell();});
  document.querySelector('[data-cancel-entity]')?.addEventListener('click',()=>{state.editingId=null;state.route=state.selectedProjectId?'project-detail':state.selectedCustomerId?'customer-detail':'home';renderShell();});
  document.querySelector('[data-customer-form]')?.addEventListener('submit',saveCustomer);
  document.querySelector('[data-project-form]')?.addEventListener('submit',saveProject);
}

if (state.token && state.user) bootstrap(); else renderLogin();
