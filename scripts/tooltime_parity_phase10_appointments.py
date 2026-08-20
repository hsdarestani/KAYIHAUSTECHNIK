from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 10 APPOINTMENTS 2026-08-20"
CSS_REL = "static/css/tooltime-phase10-appointments.css"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 10 appointment anchor missing: {label}")
    return text.replace(old, new, 1)


def patch_form(module) -> None:
    rel = "erp/rebuild_views.py"
    text = module.read(rel)
    old = '''        if organization:
            self.fields["project"].queryset = m.Project.objects.filter(organization=organization, archived=False)
            self.fields["attendees"].queryset = m.Employee.objects.filter(organization=organization, active=True)
'''
    new = '''        self.fields["project"].widget.attrs.update({"data-appointment-project": "1", "data-searchable": "true"})
        self.fields["attendees"].widget.attrs.update({"data-appointment-team": "1", "data-searchable": "true"})
        if organization:
            projects = (
                m.Project.objects.filter(organization=organization, archived=False)
                .select_related("customer", "object_location")
                .order_by("-updated_at")
            )
            self.fields["project"].queryset = projects
            self.fields["attendees"].queryset = m.Employee.objects.filter(
                organization=organization, active=True
            ).order_by("last_name", "first_name")
            # Non-model presentation querysets: no migration and no duplicate
            # persistence path. They only drive ToolTime-like customer/project UX.
            self.appointment_projects = projects
            self.appointment_customers = m.Customer.objects.filter(
                organization=organization, active=True
            ).order_by("company", "last_name", "first_name", "number")
'''
    text = _replace_once(text, old, new, "AppointmentForm organization querysets")
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def install_template(module) -> None:
    module.write("templates/rebuild/appointment_form.html", r'''{% extends 'rebuild/base.html' %}
{% block title %}Neuer Termin · A+Bau{% endblock %}
{% block content %}
<div class="tt-appt-create" data-appointment-create
     data-initial-customer="{{ request.POST.customer_filter|default:request.GET.customer|default:'' }}"
     data-initial-project="{{ form.project.value|default:'' }}">
  <form method="post" class="tt-appt-form" data-appointment-form novalidate>{% csrf_token %}
    <div class="tt-appt-sticky-head">
      <div class="tt-appt-title-row">
        <a class="tt-appt-back" href="{% url 'next-appointments' %}" aria-label="Zurück">←</a>
        <div><span>Termin erstellen</span><h1>Neuer Termin</h1></div>
      </div>
      <div class="tt-appt-head-actions">
        <a class="nx-btn tt-appt-cancel" href="{% url 'next-appointments' %}">Abbrechen</a>
        <button class="nx-btn nx-btn-primary" type="submit">Speichern</button>
      </div>
    </div>

    {% if form.errors %}<div class="tt-appt-alert" role="alert"><strong>Termin konnte nicht gespeichert werden.</strong><span> Bitte die markierten Felder prüfen.</span></div>{% endif %}
    {% if form.non_field_errors %}<div class="tt-appt-alert">{{ form.non_field_errors }}</div>{% endif %}

    <div class="tt-appt-layout">
      <main class="tt-appt-main">
        <section class="tt-appt-card">
          <div class="tt-appt-section-head"><div><span class="tt-appt-step">01</span><h2>Kunde oder Projekt auswählen</h2></div><small>Projekt ist optional.</small></div>
          <div class="tt-appt-grid tt-appt-grid-2">
            <div class="tt-appt-field">
              <label for="appointment-customer-filter">Kunde</label>
              <input class="next-control" type="search" data-customer-search placeholder="Kunde suchen …" autocomplete="off">
              <select class="next-control" id="appointment-customer-filter" name="customer_filter" data-appointment-customer>
                <option value="">Kein Kunde ausgewählt</option>
                {% for customer in form.appointment_customers %}
                <option value="{{ customer.pk }}" data-address="{{ customer.street|default:''|escape }}{% if customer.postal_code or customer.city %}, {{ customer.postal_code|default:''|escape }} {{ customer.city|default:''|escape }}{% endif %}">{{ customer.display_name }}</option>
                {% endfor %}
              </select>
              <small>Wähle zuerst den Kunden, um passende Projekte einzugrenzen.</small>
            </div>
            <div class="tt-appt-field">
              <label for="appointment-project">Projekt <span>optional</span></label>
              <input class="next-control" type="search" data-project-search placeholder="Projekt suchen …" autocomplete="off">
              <select class="next-control" id="appointment-project" name="project" data-appointment-project-select>
                <option value="">Kein Projekt ausgewählt</option>
                {% for project in form.appointment_projects %}
                <option value="{{ project.pk }}" data-customer-id="{{ project.customer_id|default:'' }}" data-address="{% if project.object_location_id %}{{ project.object_location.street|default:''|escape }}, {{ project.object_location.postal_code|default:''|escape }} {{ project.object_location.city|default:''|escape }}{% elif project.customer_id %}{{ project.customer.street|default:''|escape }}, {{ project.customer.postal_code|default:''|escape }} {{ project.customer.city|default:''|escape }}{% endif %}">{{ project.number }} · {{ project.title }}{% if project.customer_id %} · {{ project.customer.display_name }}{% endif %}</option>
                {% endfor %}
              </select>
              {{ form.project.errors }}
              <small>Ohne Projekt bleibt der Termin allgemein; der Kunde dient dann der Planung und Adressvorschau.</small>
            </div>
          </div>
        </section>

        <section class="tt-appt-card">
          <div class="tt-appt-section-head"><div><span class="tt-appt-step">02</span><h2>Termindetails</h2></div></div>
          <div class="tt-appt-grid tt-appt-grid-2">
            <div class="tt-appt-field tt-appt-span-2"><label for="{{ form.title.id_for_label }}">Titel</label>{{ form.title }}{{ form.title.errors }}</div>
            <div class="tt-appt-field"><label for="{{ form.type.id_for_label }}">Terminart</label>{{ form.type }}{{ form.type.errors }}</div>
            <div class="tt-appt-field">
              <label for="appointment-repeat">Wiederholung</label>
              <select class="next-control" id="appointment-repeat" name="repeat_rule"><option value="none">Wiederholt sich nicht</option></select>
              <small>Serientermine werden erst angeboten, sobald sie persistent im Terminmodell abgebildet sind.</small>
            </div>
          </div>

          <div class="tt-appt-time-grid">
            <div class="tt-appt-time-group"><strong>Von</strong><div><label>Datum<input class="next-control" type="date" data-start-date></label><label>Startzeit<input class="next-control" type="time" data-start-time step="300"></label></div></div>
            <span class="tt-appt-time-arrow">→</span>
            <div class="tt-appt-time-group"><strong>Bis</strong><div><label>Datum<input class="next-control" type="date" data-end-date></label><label>Endzeit<input class="next-control" type="time" data-end-time step="300"></label></div></div>
          </div>
          <div class="tt-appt-native-time" hidden>{{ form.starts_at }}{{ form.ends_at }}{{ form.starts_at.errors }}{{ form.ends_at.errors }}</div>

          <label class="tt-appt-toggle"><span><strong>Ganztägig</strong><small>Zeiten ausblenden, der gespeicherte Zeitraum bleibt erhalten.</small></span>{{ form.all_day }}<i></i></label>

          <div class="tt-appt-field tt-appt-location-input"><label for="{{ form.location.id_for_label }}">Terminort <span>optional überschreiben</span></label>{{ form.location }}{{ form.location.errors }}</div>
        </section>

        <section class="tt-appt-card">
          <div class="tt-appt-section-head"><div><span class="tt-appt-step">03</span><h2>Team & Beschreibung</h2></div></div>
          <div class="tt-appt-field">
            <label for="appointment-team-search">Team</label>
            <input class="next-control" id="appointment-team-search" type="search" data-team-search placeholder="Mitarbeiter suchen …" autocomplete="off">
            {{ form.attendees }}{{ form.attendees.errors }}
            <small>Mehrere Mitarbeiter können dem Termin zugewiesen werden.</small>
          </div>
          <div class="tt-appt-field"><label for="{{ form.notes.id_for_label }}">Beschreibung <span>nur intern</span></label>{{ form.notes }}{{ form.notes.errors }}<small>Diese Notiz dient der internen Vorbereitung des Teams.</small></div>
        </section>

        <section class="tt-appt-card tt-appt-after-save">
          <div class="tt-appt-section-head"><div><span class="tt-appt-step">04</span><h2>Leistungen</h2></div><button class="nx-btn" type="button" disabled>＋ Leistungsgruppe</button></div>
          <div class="tt-appt-empty"><span>＋</span><strong>Leistungen nach dem Speichern ergänzen</strong><p>Leistungspositionen werden am gespeicherten Termin/Projekt dokumentiert, damit keine Scheindaten im Erstellungsformular entstehen.</p></div>
        </section>

        <section class="tt-appt-card tt-appt-after-save">
          <div class="tt-appt-section-head"><div><span class="tt-appt-step">05</span><h2>Arbeitsbericht</h2></div></div>
          <textarea class="next-control" rows="5" disabled placeholder="Arbeitsbericht wird nach dem Speichern direkt im Termin erfasst."></textarea>
          <small>Der bestehende Vor-Ort-Arbeitsbericht mit Dokumentation und Unterschrift bleibt unverändert erhalten.</small>
        </section>

        <section class="tt-appt-card tt-appt-after-save">
          <div class="tt-appt-section-head"><div><span class="tt-appt-step">06</span><h2>Bilder</h2></div><button class="nx-btn" type="button" disabled>Bilder hochladen</button></div>
          <div class="tt-appt-empty tt-appt-images-empty"><span>▧</span><strong>Noch keine Bilder</strong><p>Nach dem Anlegen können Bilder revisionssicher dem Termin bzw. Projekt zugeordnet werden.</p></div>
        </section>
      </main>

      <aside class="tt-appt-side">
        <section class="tt-appt-address-card" data-address-card>
          <div class="tt-appt-pin">⌖</div>
          <div><span>Adresse</span><strong data-address-title>Adresse auswählen</strong><p data-address-text>Wähle links einen Kunden oder ein Projekt. Die Einsatzadresse erscheint hier automatisch.</p></div>
        </section>
        <section class="tt-appt-side-note"><strong>Planung auf einer Seite</strong><p>Kein Wizard: Kunde/Projekt, Zeit, Team und interne Beschreibung werden direkt erfasst.</p></section>
      </aside>
    </div>
  </form>
</div>
{% endblock %}
{% block scripts %}
<script>
(() => {
  const root = document.querySelector('[data-appointment-create]');
  const form = root?.querySelector('[data-appointment-form]');
  if (!root || !form) return;

  const customer = form.querySelector('[data-appointment-customer]');
  const project = form.querySelector('[data-appointment-project-select]');
  const customerSearch = form.querySelector('[data-customer-search]');
  const projectSearch = form.querySelector('[data-project-search]');
  const teamSearch = form.querySelector('[data-team-search]');
  const team = form.querySelector('select[name="attendees"]');
  const nativeStart = form.querySelector('input[name="starts_at"]');
  const nativeEnd = form.querySelector('input[name="ends_at"]');
  const startDate = form.querySelector('[data-start-date]');
  const startTime = form.querySelector('[data-start-time]');
  const endDate = form.querySelector('[data-end-date]');
  const endTime = form.querySelector('[data-end-time]');
  const allDay = form.querySelector('input[name="all_day"]');
  const manualLocation = form.querySelector('input[name="location"]');
  const addressTitle = form.querySelector('[data-address-title]');
  const addressText = form.querySelector('[data-address-text]');

  const norm = (value) => String(value || '').trim().toLowerCase();
  const splitNative = (value) => {
    const text = String(value || '');
    if (!text.includes('T')) return ['', ''];
    const [date, time = ''] = text.split('T');
    return [date, time.slice(0, 5)];
  };
  const [sd, st] = splitNative(nativeStart?.value);
  const [ed, et] = splitNative(nativeEnd?.value);
  if (startDate) startDate.value = sd;
  if (startTime) startTime.value = st;
  if (endDate) endDate.value = ed;
  if (endTime) endTime.value = et;

  const syncNativeTime = () => {
    if (nativeStart && startDate?.value && startTime?.value) nativeStart.value = `${startDate.value}T${startTime.value}`;
    if (nativeEnd && endDate?.value && endTime?.value) nativeEnd.value = `${endDate.value}T${endTime.value}`;
  };

  const initialProject = String(root.dataset.initialProject || '');
  if (project && initialProject && [...project.options].some((option) => option.value === initialProject)) project.value = initialProject;
  let initialCustomer = String(root.dataset.initialCustomer || '');
  if (!initialCustomer && project?.selectedOptions[0]?.dataset.customerId) initialCustomer = project.selectedOptions[0].dataset.customerId;
  if (customer && initialCustomer && [...customer.options].some((option) => option.value === initialCustomer)) customer.value = initialCustomer;

  const selectedAddress = () => {
    const manual = String(manualLocation?.value || '').trim();
    if (manual) return {title: 'Manueller Terminort', address: manual};
    const projectOption = project?.selectedOptions[0];
    if (project?.value && projectOption?.dataset.address) return {title: projectOption.textContent.trim(), address: projectOption.dataset.address};
    const customerOption = customer?.selectedOptions[0];
    if (customer?.value && customerOption?.dataset.address) return {title: customerOption.textContent.trim(), address: customerOption.dataset.address};
    return {title: 'Adresse auswählen', address: 'Wähle links einen Kunden oder ein Projekt. Die Einsatzadresse erscheint hier automatisch.'};
  };

  const updateAddress = () => {
    const data = selectedAddress();
    if (addressTitle) addressTitle.textContent = data.title;
    if (addressText) addressText.textContent = data.address || 'Keine Adresse hinterlegt.';
  };

  const filterProjects = () => {
    if (!project) return;
    const customerId = customer?.value || '';
    const query = norm(projectSearch?.value);
    [...project.options].forEach((option, index) => {
      if (index === 0) return;
      const customerMatch = !customerId || option.dataset.customerId === customerId;
      const queryMatch = !query || norm(option.textContent).includes(query);
      option.hidden = !(customerMatch && queryMatch);
    });
    const selected = project.selectedOptions[0];
    if (project.value && selected?.hidden) project.value = '';
    updateAddress();
  };

  const filterCustomers = () => {
    const query = norm(customerSearch?.value);
    [...(customer?.options || [])].forEach((option, index) => {
      if (index === 0) return;
      option.hidden = Boolean(query) && !norm(option.textContent).includes(query);
    });
  };

  const filterTeam = () => {
    if (!team) return;
    const query = norm(teamSearch?.value);
    [...team.options].forEach((option) => { option.hidden = Boolean(query) && !norm(option.textContent).includes(query); });
  };

  customer?.addEventListener('change', () => { filterProjects(); updateAddress(); });
  project?.addEventListener('change', () => {
    const customerId = project.selectedOptions[0]?.dataset.customerId;
    if (customerId && customer && [...customer.options].some((option) => option.value === customerId)) customer.value = customerId;
    filterProjects();
    updateAddress();
  });
  customerSearch?.addEventListener('input', filterCustomers);
  projectSearch?.addEventListener('input', filterProjects);
  teamSearch?.addEventListener('input', filterTeam);
  manualLocation?.addEventListener('input', updateAddress);
  [startDate, startTime, endDate, endTime].forEach((input) => input?.addEventListener('change', syncNativeTime));
  allDay?.addEventListener('change', () => {
    [startTime, endTime].forEach((input) => { if (input) input.disabled = allDay.checked; });
  });
  form.addEventListener('submit', syncNativeTime);

  filterCustomers();
  filterProjects();
  filterTeam();
  updateAddress();
  if (allDay?.checked) [startTime, endTime].forEach((input) => { if (input) input.disabled = true; });
})();
</script>
{% endblock %}
''')


def install_css(module) -> None:
    module.write(CSS_REL, r'''/* A+BAU TOOLTIME PHASE 10 APPOINTMENTS 2026-08-20 */
.tt-appt-create{max-width:1400px;margin:-24px auto 0;color:#172033}.tt-appt-form{display:block}.tt-appt-sticky-head{position:sticky;top:0;z-index:30;display:flex;align-items:center;justify-content:space-between;gap:20px;margin:0 -26px 24px;padding:17px 26px;border-bottom:1px solid #e5e9ef;background:rgba(255,255,255,.96);backdrop-filter:blur(14px)}.tt-appt-title-row{display:flex;align-items:center;gap:14px}.tt-appt-title-row>div{display:grid;gap:1px}.tt-appt-title-row span{font-size:12px;color:#7b8495}.tt-appt-title-row h1{margin:0;font-size:24px;letter-spacing:-.025em}.tt-appt-back{display:grid;place-items:center;width:40px;height:40px;border:1px solid #dfe4eb;border-radius:11px;color:#263247;text-decoration:none;font-size:20px;background:#fff}.tt-appt-head-actions{display:flex;gap:10px}.tt-appt-cancel{background:#f1f3f6!important;border-color:#f1f3f6!important}.tt-appt-alert{margin-bottom:16px;padding:12px 14px;border:1px solid #f0c8c8;border-radius:12px;background:#fff7f7;color:#9c2f2f}.tt-appt-layout{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:24px;align-items:start}.tt-appt-main{display:grid;gap:18px;min-width:0}.tt-appt-card,.tt-appt-address-card,.tt-appt-side-note{border:1px solid #e3e7ed;border-radius:16px;background:#fff;box-shadow:0 7px 24px rgba(30,42,60,.04)}.tt-appt-card{padding:24px}.tt-appt-section-head{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:20px}.tt-appt-section-head>div{display:flex;align-items:center;gap:10px}.tt-appt-section-head h2{margin:0;font-size:17px;letter-spacing:-.015em}.tt-appt-section-head>small{color:#8a93a2}.tt-appt-step{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:#eef5ff;color:#2c70d6;font-size:11px;font-weight:800}.tt-appt-grid{display:grid;gap:18px}.tt-appt-grid-2{grid-template-columns:repeat(2,minmax(0,1fr))}.tt-appt-span-2{grid-column:1/-1}.tt-appt-field{display:grid;gap:7px;min-width:0}.tt-appt-field>label,.tt-appt-time-group>strong{font-size:12.5px;font-weight:750;color:#2c3442}.tt-appt-field>label span{font-weight:500;color:#8a93a2}.tt-appt-field>small,.tt-appt-card>small{color:#838d9c;font-size:11.5px;line-height:1.45}.tt-appt-field input,.tt-appt-field select,.tt-appt-field textarea,.tt-appt-time-group input{min-height:44px;border-radius:10px}.tt-appt-field select[multiple]{min-height:118px}.tt-appt-time-grid{display:grid;grid-template-columns:1fr auto 1fr;align-items:end;gap:14px;margin-top:22px;padding:18px;border-radius:13px;background:#f8fafc;border:1px solid #edf0f4}.tt-appt-time-group{display:grid;gap:9px}.tt-appt-time-group>div{display:grid;grid-template-columns:1.3fr .9fr;gap:10px}.tt-appt-time-group label{display:grid;gap:5px;color:#7a8494;font-size:11px}.tt-appt-time-arrow{padding-bottom:12px;color:#8993a2;font-size:19px}.tt-appt-toggle{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-top:18px;padding:14px 0;border-top:1px solid #eef1f4;cursor:pointer}.tt-appt-toggle>span{display:grid;gap:2px}.tt-appt-toggle strong{font-size:13px}.tt-appt-toggle small{color:#8a93a2}.tt-appt-toggle input{position:absolute;opacity:0}.tt-appt-toggle i{position:relative;width:43px;height:24px;border-radius:999px;background:#cbd2dc;transition:.2s}.tt-appt-toggle i:after{content:"";position:absolute;top:3px;left:3px;width:18px;height:18px;border-radius:50%;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.18);transition:.2s}.tt-appt-toggle input:checked+i{background:#3478df}.tt-appt-toggle input:checked+i:after{transform:translateX(19px)}.tt-appt-location-input{margin-top:8px}.tt-appt-side{position:sticky;top:92px;display:grid;gap:14px}.tt-appt-address-card{display:flex;gap:14px;padding:20px}.tt-appt-pin{display:grid;place-items:center;flex:0 0 40px;width:40px;height:40px;border-radius:12px;background:#eff5ff;color:#3478df;font-size:21px}.tt-appt-address-card>div:last-child{display:grid;gap:4px;min-width:0}.tt-appt-address-card span{font-size:11px;color:#8993a2;text-transform:uppercase;letter-spacing:.08em}.tt-appt-address-card strong{font-size:14px}.tt-appt-address-card p,.tt-appt-side-note p{margin:0;color:#727d8d;font-size:12px;line-height:1.55}.tt-appt-side-note{padding:18px}.tt-appt-side-note{display:grid;gap:6px}.tt-appt-empty{display:grid;place-items:center;text-align:center;min-height:150px;padding:22px;border:1px dashed #d9dfe7;border-radius:13px;background:#fafbfc}.tt-appt-empty>span{display:grid;place-items:center;width:42px;height:42px;margin-bottom:8px;border-radius:12px;background:#f0f3f7;color:#6f7b8d;font-size:22px}.tt-appt-empty p{max-width:520px;margin:5px 0 0;color:#7d8796;font-size:12px;line-height:1.55}.tt-appt-after-save button[disabled],.tt-appt-after-save textarea[disabled]{opacity:.62;cursor:not-allowed}.tt-appt-images-empty{min-height:210px}.tt-appt-nav-group{display:grid}.tt-appt-subnav{display:grid;gap:2px;margin:-2px 0 6px 34px}.nx-nav .tt-appt-subnav a{padding:6px 8px!important;font-size:11.5px!important;color:#8993a2!important}.nx-nav .tt-appt-subnav a:hover{color:inherit!important}.tt-appt-subnav .is-disabled{opacity:.5;pointer-events:none}@media(max-width:1050px){.tt-appt-layout{grid-template-columns:1fr}.tt-appt-side{position:static;grid-row:1}.tt-appt-address-card{min-height:auto}.tt-appt-time-grid{grid-template-columns:1fr}.tt-appt-time-arrow{display:none}}@media(max-width:700px){.tt-appt-create{margin-top:-18px}.tt-appt-sticky-head{margin:0 -16px 18px;padding:12px 16px}.tt-appt-title-row span{display:none}.tt-appt-title-row h1{font-size:20px}.tt-appt-head-actions .tt-appt-cancel{display:none}.tt-appt-card{padding:18px 16px;border-radius:14px}.tt-appt-grid-2{grid-template-columns:1fr}.tt-appt-span-2{grid-column:auto}.tt-appt-time-group>div{grid-template-columns:1fr 1fr}.tt-appt-section-head{align-items:flex-start}.tt-appt-section-head>small{display:none}}
''')

    base_rel = "templates/rebuild/base.html"
    base = module.read(base_rel)
    css_tag = "  <link rel=\"stylesheet\" href=\"{% static 'css/tooltime-phase10-appointments.css' %}?v=20260820-1\">\n"
    if "tooltime-phase10-appointments.css" not in base:
        if "</head>" not in base:
            raise RuntimeError("Phase 10 base head anchor missing")
        base = base.replace("</head>", css_tag + "</head>", 1)

    appointment_anchor = '<a class="{% if \'appointment\' in request.resolver_match.url_name %}is-active{% endif %}" href="{% url \'next-appointments\' %}"><span class="nx-ico">◫</span>Termine</a>'
    if "tt-appt-nav-group" not in base and appointment_anchor in base:
        appointment_nav = '''<div class="tt-appt-nav-group">
      ''' + appointment_anchor + '''
      <div class="tt-appt-subnav">
        <a href="{% url 'next-appointments' %}?view=week">Kalender</a>
        <a class="is-disabled" aria-disabled="true" title="Kartenansicht folgt auf Basis persistierter Geodaten">Karte</a>
        <a href="{% url 'next-appointments' %}?view=list">Liste</a>
      </div>
      </div>'''
        base = base.replace(appointment_anchor, appointment_nav, 1)
    module.write(base_rel, base)


def install_tests(module) -> None:
    module.write("tests/test_tooltime_phase10_appointments.py", r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class ToolTimePhase10AppointmentContractTests(SimpleTestCase):
    def test_create_form_matches_single_page_tooltime_information_architecture(self):
        template = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        for marker in (
            "Kunde oder Projekt auswählen", "Kunde suchen", "Projekt suchen", "data-address-card",
            "Terminart", "Wiederholt sich nicht", "Ganztägig", "Mitarbeiter suchen", "nur intern",
            "Leistungen", "Arbeitsbericht", "Bilder", "data-start-date", "data-end-time",
        ):
            self.assertIn(marker, template)
        self.assertIn('name="project"', template)
        self.assertIn('name="customer_filter"', template)

    def test_create_form_reuses_existing_persistent_calendar_fields(self):
        views = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn('fields = ["title", "type", "starts_at", "ends_at", "all_day", "location", "notes", "project", "attendees"]', views)
        self.assertIn("appointment_customers", views)
        self.assertIn("appointment_projects", views)
        self.assertNotIn("AppointmentRepeatRule", views)

    def test_phase10_is_responsive_and_does_not_fake_unimplemented_persistence(self):
        css = (ROOT / "static/css/tooltime-phase10-appointments.css").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/appointment_form.html").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:700px)", css)
        self.assertIn("Nach dem Speichern", template)
        self.assertIn("Serientermine werden erst angeboten", template)
''')


def guard(module) -> None:
    views = module.read("erp/rebuild_views.py")
    template = module.read("templates/rebuild/appointment_form.html")
    base = module.read("templates/rebuild/base.html")
    css = module.read(CSS_REL)
    for marker in ("appointment_customers", "appointment_projects", "data-appointment-team"):
        if marker not in views:
            raise RuntimeError(f"Phase 10 AppointmentForm contract missing: {marker}")
    for marker in ("data-appointment-create", "Kunde suchen", "data-address-card", "data-team-search", "Arbeitsbericht", "Bilder"):
        if marker not in template:
            raise RuntimeError(f"Phase 10 appointment template contract missing: {marker}")
    if "tooltime-phase10-appointments.css" not in base or MARKER not in css:
        raise RuntimeError("Phase 10 appointment visual layer missing")
    compile(module.read("tests/test_tooltime_phase10_appointments.py"), str(ROOT / "tests/test_tooltime_phase10_appointments.py"), "exec")


def run(module) -> None:
    patch_form(module)
    install_template(module)
    install_css(module)
    install_tests(module)
    guard(module)
    print(f"{MARKER}: single-page customer/project, address, split-time, team and post-save documentation UX installed without schema changes.")
