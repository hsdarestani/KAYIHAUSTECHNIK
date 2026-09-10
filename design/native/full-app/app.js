import { Capacitor, registerPlugin } from '@capacitor/core';

const Scanner = registerPlugin('KayiRoomScanner');
const API = 'https://kayi.smarbiz.sbs';
const OFFICE_ROLES = new Set(['admin', 'owner', 'manager', 'office', 'accounting']);
const state = {
  baseUrl: localStorage.getItem('ab.baseUrl') || API,
  token: localStorage.getItem('ab.token') || '',
  user: JSON.parse(localStorage.getItem('ab.user') || 'null'),
  route: 'home', data: {}, capabilities: null, loading: false,
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
  const routes = {home:renderHome, projects:renderProjects, appointments:renderAppointments, customers:renderCustomers, time:renderTime, scanner:renderScanner, commercial:renderCommercial, tasks:renderTasks, more:renderMore, profile:renderProfile};
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

function renderProjects() { return `${pageHead('PROJEKTE', isOffice()?'Alle Projekte':'Meine Projekte', isOffice()?'Aktive Aufträge und Projektstatus.':'Nur dir zugewiesene Projekte.')}<div class="rows cards">${state.data.projects.map(p=>`<article class="project-card"><header><span>${esc(p.number || 'PROJEKT')}</span><em>${esc(p.status || '')}</em></header><h2>${esc(p.title)}</h2><p>${esc(p.customer_name || p.description || '')}</p><footer><button data-scan-project="${p.id}">⌗ Raum aufmessen</button></footer></article>`).join('') || '<div class="empty">Keine Projekte verfügbar.</div>'}</div>`; }
function renderAppointments() { return `${pageHead('KALENDER',isOffice()?'Termine & Einsätze':'Meine Einsätze',isOffice()?'Planung für Team und Baustellen.':'Deine zugewiesenen Termine.')}<div class="rows cards">${state.data.events.map(eventRow).join('') || '<div class="empty">Keine Termine verfügbar.</div>'}</div>`; }
function renderCustomers() { if (!isOffice()) return forbidden(); return `${pageHead('STAMMDATEN','Kunden','Kontakte und zugehörige Projekte.')}<div class="rows cards">${state.data.customers.map(c=>`<article class="row"><span class="circle">${esc((c.company||c.last_name||'?').slice(0,1))}</span><div><b>${esc(c.display_name || c.company || `${c.first_name||''} ${c.last_name||''}`)}</b><small>${esc(c.number || c.email || c.phone || '')}</small></div><span>›</span></article>`).join('') || '<div class="empty">Keine Kunden vorhanden.</div>'}</div>`; }
function renderTasks() { return `${pageHead('AUFGABEN',isOffice()?'Team-Aufgaben':'Meine Aufgaben','Offene Punkte für die Ausführung.')}<div class="rows cards">${state.data.tasks.map(t=>`<article class="row"><span class="task-dot ${esc(t.priority||'')}"></span><div><b>${esc(t.title)}</b><small>${esc(t.project_title || t.status || '')}</small></div><span>›</span></article>`).join('') || '<div class="empty">Keine Aufgaben vorhanden.</div>'}</div>`; }
function renderCommercial() { if(!isOffice()) return forbidden(); return `${pageHead('KAUFMÄNNISCH','Angebote & Rechnungen','Nur für berechtigte Büro-Rollen sichtbar.')}<section class="metrics two">${metric(state.data.quotes.length,'Angebote','gold')}${metric(state.data.invoices.length,'Rechnungen')}</section><section class="menu-list"><button><span>◇</span><div><b>Angebote</b><small>Erstellen, prüfen und versenden</small></div><em>${state.data.quotes.length}</em></button><button><span>€</span><div><b>Rechnungen</b><small>Entwürfe, Fälligkeiten und Zahlungen</small></div><em>${state.data.invoices.length}</em></button></section>`; }
function renderTime() { return `${pageHead('ZEITERFASSUNG','Arbeitszeit','Start und Stopp werden projektbezogen protokolliert.')}<section class="time-card"><div class="time-icon">◷</div><h2>Bereit für den nächsten Einsatz?</h2><p>Wähle im nächsten Schritt ein Projekt und starte die Arbeitszeit.</p><button class="primary" data-time-start>Arbeit starten</button></section>`; }
function renderScanner() { const caps=state.capabilities||{}; return `${pageHead('AUFMASS','Raum erfassen','Der Scanner ist ein Werkzeug innerhalb des vollständigen A+Bau-Workflows.')}<section class="scan-card"><span class="scan-icon">⌗</span><h2>${caps.lidar?'LiDAR bereit':caps.fallback?'Manuelles Aufmaß verfügbar':caps.supported?'Scanner bereit':'Scanner nicht verfügbar'}</h2><p>${esc(caps.provider || Capacitor.getPlatform())}</p><label>Projekt<select id="scan-project"><option value="">Projekt auswählen</option>${state.data.projects.map(p=>`<option value="${p.id}">${esc(p.number)} · ${esc(p.title)}</option>`).join('')}</select></label><button class="primary" data-start-scan ${caps.supported?'':'disabled'}>Raum scannen</button><button class="secondary" data-pending-scans>Nicht hochgeladene Scans</button><div data-scan-result></div></section>`; }
function renderMore() { const office = isOffice(); const items = office ? [['customers','◎','Kunden'],['commercial','€','Angebote & Rechnungen'],['tasks','✓','Aufgaben'],['scanner','⌗','Aufmaß & Scanner'],['profile','⚙','Konto & Einstellungen']] : [['tasks','✓','Aufgaben'],['scanner','⌗','Aufmaß & Scanner'],['profile','⚙','Konto']]; return `${pageHead('MENÜ','Alle Bereiche','Funktionen passend zu deiner Rolle.')}<section class="menu-list">${items.map(([route,icon,title])=>`<button data-route="${route}"><span>${icon}</span><div><b>${title}</b><small>Öffnen</small></div><em>›</em></button>`).join('')}</section>`; }
function renderProfile() { return `${pageHead('KONTO',fullName(),roleName())}<section class="profile-card"><dl><div><dt>Benutzer</dt><dd>${esc(state.user?.username)}</dd></div><div><dt>Organisation</dt><dd>${esc(state.user?.organization || 'A+Bau')}</dd></div><div><dt>Rolle</dt><dd>${esc(roleName())}</dd></div></dl><button class="danger" data-logout>Abmelden</button></section>`; }
const forbidden = () => `${pageHead('BERECHTIGUNG','Nicht verfügbar','Dieser Bereich ist für deine Rolle nicht freigeschaltet.')}<button class="secondary" data-route="home">Zurück zur Startseite</button>`;

async function startScan(projectId) {
  if (!projectId) return toast('Bitte zuerst ein Projekt auswählen.', 'error');
  toast('Aufmaß wird geöffnet …', 'info');
  try { const scan=await Scanner.startScan({roomName:'Raum'}); await Scanner.uploadScan({scanId:scan.scanId,projectId:Number(projectId),apiBaseUrl:state.baseUrl,token:state.token}); toast('Aufmaß gespeichert und zur Prüfung hochgeladen.'); }
  catch(error) { toast(error.message || String(error), 'error'); }
}
async function pendingScans() { try { const data=await Scanner.listPendingScans(); const scans=list(data?.scans || data); const target=document.querySelector('[data-scan-result]'); target.innerHTML=scans.length?`<ul class="pending-list">${scans.map(s=>`<li>${esc(s.roomName||'Raumaufmaß')}<small>${esc(s.createdAt||'Lokal gespeichert')}</small></li>`).join('')}</ul>`:'<p class="empty">Keine ausstehenden Scans.</p>'; } catch(error){toast(error.message,'error');} }
async function logout(callApi=true) { if(callApi) await api('/api/mobile/logout/',{method:'POST'}).catch(()=>{}); state.token='';state.user=null;localStorage.removeItem('ab.token');localStorage.removeItem('ab.user');renderLogin(); }

function bindActions() {
  document.querySelectorAll('[data-route]').forEach(button => button.addEventListener('click',()=>{state.route=button.dataset.route;renderShell();window.scrollTo(0,0);}));
  document.querySelectorAll('[data-scan-project]').forEach(button=>button.addEventListener('click',()=>{state.route='scanner';renderShell();const select=document.querySelector('#scan-project');if(select)select.value=button.dataset.scanProject;}));
  document.querySelector('[data-start-scan]')?.addEventListener('click',()=>startScan(document.querySelector('#scan-project')?.value));
  document.querySelector('[data-pending-scans]')?.addEventListener('click',pendingScans);
  document.querySelector('[data-logout]')?.addEventListener('click',()=>logout(true));
  document.querySelector('[data-time-start]')?.addEventListener('click',()=>toast('Projektwahl und Live-Zeiterfassung folgen in Phase 3.', 'info'));
}

if (state.token && state.user) bootstrap(); else renderLogin();
