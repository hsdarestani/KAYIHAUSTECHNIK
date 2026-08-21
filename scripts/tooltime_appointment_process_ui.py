from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _replace(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Appointment parity UI: anchor fehlt: {label}")
    return text.replace(old, new, 1)


def patch_form(module) -> None:
    rel = "templates/rebuild/appointment_form.html"
    text = module.read(rel)
    text = text.replace('>Titel</label>{{ form.title }}', '>Terminname</label>{{ form.title }}', 1)
    text = text.replace('<label for="appointment-team-search">Team</label>', '<label for="appointment-team-search">Mitarbeiter hinzufügen</label>', 1)
    text = text.replace('>Wiederholt sich nicht</option>', '>Einmalig</option>', 1)

    old_services = r'''        <section class="tt-appt-card tt-appt-after-save">
          <div class="tt-appt-section-head"><div><span class="tt-appt-step">04</span><h2>Leistungen</h2></div><button class="nx-btn" type="button" disabled>＋ Leistungsgruppe</button></div>
          <div class="tt-appt-empty"><span>＋</span><strong>Leistungen nach dem Speichern ergänzen</strong><p>Leistungspositionen werden am gespeicherten Termin/Projekt dokumentiert, damit keine Scheindaten im Erstellungsformular entstehen.</p></div>
        </section>
'''
    new_services = r'''        <section class="tt-appt-card tt-appt-services-editor" data-service-editor>
          <input type="hidden" name="service_editor_present" value="1">
          {% if source_quote %}<input type="hidden" name="source_quote" value="{{ source_quote.pk }}">{% endif %}
          <div class="tt-appt-section-head"><div><span class="tt-appt-step">04</span><h2>Leistungen</h2></div><button class="nx-btn" type="button" data-add-service-group>＋ Leistungsgruppe hinzufügen</button></div>
          {% if source_quote %}<div class="tt-appt-source-note">Alle Positionen aus dem angenommenen Angebot wurden übernommen und können für diesen Termin angepasst werden.</div>{% endif %}
          <div class="tt-appt-service-groups" data-service-groups>
            {% for group in appointment_service_groups %}
            <div class="tt-appt-service-group" data-service-group data-group-index="{{ forloop.counter0 }}">
              <div class="tt-appt-service-group-head"><input class="next-control" name="service_group_title" value="{{ group.title }}" placeholder="Leistungsgruppe"><button class="nx-btn" type="button" data-add-service-row>＋ Position hinzufügen</button><button class="nx-btn tt-danger-link" type="button" data-remove-service-group>Entfernen</button></div>
              <div class="tt-appt-service-rows" data-service-rows>
                {% for item in group.items %}
                <div class="tt-appt-service-row" data-service-row>
                  <input type="hidden" name="service_group_index" value="{{ forloop.parentloop.counter0 }}">
                  <select class="next-control" name="service_kind" aria-label="Art"><option value="labour" {% if item.kind == 'labour' %}selected{% endif %}>Arbeitszeit</option><option value="material" {% if item.kind == 'material' %}selected{% endif %}>Material</option><option value="mixed" {% if item.kind == 'mixed' %}selected{% endif %}>Mischposition</option><option value="other" {% if item.kind == 'other' %}selected{% endif %}>Sonstiges</option></select>
                  <input class="next-control" name="service_quantity" type="number" step="0.001" value="{{ item.quantity }}" aria-label="Menge">
                  <input class="next-control" name="service_unit" value="{{ item.unit }}" aria-label="Einheit">
                  <input class="next-control tt-service-description" name="service_description" value="{{ item.description }}" placeholder="Bezeichnung" aria-label="Bezeichnung">
                  <select class="next-control" name="service_catalog_id" data-service-catalog aria-label="Katalog"><option value="">Katalog auswählen …</option>{% for c in appointment_catalog %}<option value="{{ c.pk }}" data-kind="{% if c.kind == 'service' %}labour{% elif c.kind == 'material' %}material{% else %}other{% endif %}" data-unit="{{ c.unit }}" data-description="{{ c.name|escape }}" data-purchase="{{ c.purchase_price }}" data-sales="{{ c.sales_price }}" data-tax="{{ c.tax_rate }}" {% if item.catalog_item_id == c.pk %}selected{% endif %}>{{ c.code }} · {{ c.name }}</option>{% endfor %}</select>
                  <input type="hidden" name="service_purchase_price" value="{{ item.purchase_price }}"><input type="hidden" name="service_unit_price" value="{{ item.unit_price }}"><input type="hidden" name="service_tax_rate" value="{{ item.tax_rate }}"><input type="hidden" name="service_mixed_json" value="{{ item.mixed_json|escape }}"><input type="hidden" name="service_source_quote_item_id" value="{{ item.source_quote_item_id|default:'' }}">
                  <button class="nx-btn tt-danger-link" type="button" data-remove-service-row aria-label="Position entfernen">×</button>
                </div>
                {% endfor %}
              </div>
            </div>
            {% empty %}<div class="tt-appt-empty" data-service-empty><span>＋</span><strong>Noch keine Leistungen</strong><p>Leistungsgruppe hinzufügen und Positionen mit Art, Menge, Einheit und Bezeichnung erfassen.</p></div>{% endfor %}
          </div>
        </section>
'''
    text = _replace(text, old_services, new_services, "Leistungen")

    old_report = r'''        <section class="tt-appt-card tt-appt-after-save">
          <div class="tt-appt-section-head"><div><span class="tt-appt-step">05</span><h2>Arbeitsbericht</h2></div></div>
          <textarea class="next-control" rows="5" disabled placeholder="Arbeitsbericht wird nach dem Speichern direkt im Termin erfasst."></textarea>
          <small>Der bestehende Vor-Ort-Arbeitsbericht mit Dokumentation und Unterschrift bleibt unverändert erhalten.</small>
        </section>
'''
    new_report = r'''        <section class="tt-appt-card">
          <div class="tt-appt-section-head"><div><span class="tt-appt-step">05</span><h2>Arbeitsbericht</h2></div></div>
          <textarea class="next-control" name="work_report" rows="5" placeholder="Details, die vor Ort geprüft oder im Arbeitsschein erwähnt werden sollen">{% if request.method == 'POST' %}{{ request.POST.work_report }}{% else %}{{ event.work_report|default:'' }}{% endif %}</textarea>
          <small>Die Vorgabe kann vor Ort ergänzt werden und fließt in die Dokumentation ein.</small>
        </section>
'''
    text = _replace(text, old_report, new_report, "Arbeitsbericht")

    if "const catalogOptions =" not in text:
        end_anchor = "</script>\n{% endblock %}"
        idx = text.rfind(end_anchor)
        if idx < 0:
            raise RuntimeError("Appointment parity UI: script end fehlt")
        js = r'''<script>
(() => {
  const root = document.querySelector('[data-service-editor]');
  if (!root) return;
  const groups = root.querySelector('[data-service-groups]');
  const catalogOptions = `{% for c in appointment_catalog %}<option value="{{ c.pk }}" data-kind="{% if c.kind == 'service' %}labour{% elif c.kind == 'material' %}material{% else %}other{% endif %}" data-unit="{{ c.unit|escapejs }}" data-description="{{ c.name|escapejs }}" data-purchase="{{ c.purchase_price }}" data-sales="{{ c.sales_price }}" data-tax="{{ c.tax_rate }}">{{ c.code|escapejs }} · {{ c.name|escapejs }}</option>{% endfor %}`;
  const rowHtml = (index) => `<div class="tt-appt-service-row" data-service-row><input type="hidden" name="service_group_index" value="${index}"><select class="next-control" name="service_kind" aria-label="Art"><option value="labour">Arbeitszeit</option><option value="material">Material</option><option value="mixed">Mischposition</option><option value="other" selected>Sonstiges</option></select><input class="next-control" name="service_quantity" type="number" step="0.001" value="1" aria-label="Menge"><input class="next-control" name="service_unit" value="Stk." aria-label="Einheit"><input class="next-control tt-service-description" name="service_description" placeholder="Bezeichnung" aria-label="Bezeichnung"><select class="next-control" name="service_catalog_id" data-service-catalog aria-label="Katalog"><option value="">Katalog auswählen …</option>${catalogOptions}</select><input type="hidden" name="service_purchase_price" value="0"><input type="hidden" name="service_unit_price" value="0"><input type="hidden" name="service_tax_rate" value="19"><input type="hidden" name="service_mixed_json" value="[]"><input type="hidden" name="service_source_quote_item_id" value=""><button class="nx-btn tt-danger-link" type="button" data-remove-service-row>×</button></div>`;
  const sync = () => [...groups.querySelectorAll('[data-service-group]')].forEach((group, index) => { group.dataset.groupIndex=String(index); group.querySelectorAll('input[name="service_group_index"]').forEach(input => input.value=String(index)); });
  root.addEventListener('click', event => {
    if (event.target.closest('[data-add-service-group]')) { const index=groups.querySelectorAll('[data-service-group]').length; const node=document.createElement('div'); node.className='tt-appt-service-group'; node.dataset.serviceGroup='1'; node.dataset.groupIndex=String(index); node.innerHTML=`<div class="tt-appt-service-group-head"><input class="next-control" name="service_group_title" placeholder="Leistungsgruppe"><button class="nx-btn" type="button" data-add-service-row>＋ Position hinzufügen</button><button class="nx-btn tt-danger-link" type="button" data-remove-service-group>Entfernen</button></div><div class="tt-appt-service-rows" data-service-rows>${rowHtml(index)}</div>`; groups.appendChild(node); sync(); return; }
    const add=event.target.closest('[data-add-service-row]'); if(add){const group=add.closest('[data-service-group]');group.querySelector('[data-service-rows]').insertAdjacentHTML('beforeend',rowHtml(group.dataset.groupIndex||'0'));return;}
    const remove=event.target.closest('[data-remove-service-row]'); if(remove){remove.closest('[data-service-row]')?.remove();return;}
    const removeGroup=event.target.closest('[data-remove-service-group]'); if(removeGroup){removeGroup.closest('[data-service-group]')?.remove();sync();}
  });
  root.addEventListener('change', event => { const select=event.target.closest('[data-service-catalog]'); if(!select||!select.value)return; const option=select.selectedOptions[0], row=select.closest('[data-service-row]'); row.querySelector('[name="service_kind"]').value=option.dataset.kind||'other'; row.querySelector('[name="service_unit"]').value=option.dataset.unit||'Stk.'; row.querySelector('[name="service_description"]').value=option.dataset.description||option.textContent.trim(); row.querySelector('[name="service_purchase_price"]').value=option.dataset.purchase||'0'; row.querySelector('[name="service_unit_price"]').value=option.dataset.sales||'0'; row.querySelector('[name="service_tax_rate"]').value=option.dataset.tax||'19'; });
  sync();
})();
</script>
'''
        text = text[:idx] + js + text[idx:]
    module.write(rel, text)

    css_rel = "static/css/tooltime-phase10-appointments.css"
    css = module.read(css_rel)
    if "/* A+BAU TOOLTIME APPOINTMENT PROCESS */" not in css:
        css += r'''
/* A+BAU TOOLTIME APPOINTMENT PROCESS */
.tt-appt-source-note{margin:-2px 0 12px;padding:10px 12px;border-radius:10px;background:#f5f8fc;color:#596579;font-size:12px}.tt-appt-service-groups{display:grid;gap:12px}.tt-appt-service-group{display:grid;gap:10px;padding:12px;border:1px solid #e4e8ee;border-radius:13px;background:#fbfcfd}.tt-appt-service-group-head{display:grid;grid-template-columns:minmax(180px,1fr) auto auto;gap:8px}.tt-appt-service-rows{display:grid;gap:8px}.tt-appt-service-row{display:grid;grid-template-columns:115px 90px 90px minmax(180px,1.4fr) minmax(170px,1fr) 38px;gap:7px;align-items:center}.tt-danger-link{color:#9b2d2d!important}.tt-service-description{min-width:0}@media(max-width:1050px){.tt-appt-service-row{grid-template-columns:110px 80px 80px 1fr}.tt-appt-service-row [data-service-catalog]{grid-column:1/-2}}@media(max-width:700px){.tt-appt-service-group-head,.tt-appt-service-row{grid-template-columns:1fr}.tt-appt-service-row [data-service-catalog]{grid-column:auto}}
'''
        module.write(css_rel, css)


def patch_detail(module) -> None:
    rel = "templates/rebuild/appointment_detail.html"
    text = module.read(rel)
    marker = '  {% if project_missing %}\n'
    if "tt-appt-process-services" not in text:
        if marker not in text:
            raise RuntimeError("Appointment parity UI: detail insertion anchor fehlt")
        services = r'''  <section class="tt-appt-process-services" aria-label="Leistungen und Folgeaktionen">
    <div class="tt-appt-process-head"><div><span>Leistungen</span><strong>Leistungsgruppen &amp; Positionen</strong></div>{% if request.user.profile.role != 'technician' and not request.user.profile.is_mobile_worker %}<a class="nx-btn" href="{% url 'next-appointment-edit' event.pk %}">Leistungen bearbeiten</a>{% endif %}</div>
    {% for group in service_groups %}<div class="tt-appt-process-group"><h3>{{ group.title|default:'Leistungsgruppe' }}</h3><div class="tt-appt-process-table"><div class="head"><span>Art</span><span>Menge</span><span>Einheit</span><span>Bezeichnung</span></div>{% for item in group.items.all %}<div><span>{{ item.get_kind_display }}</span><span>{{ item.quantity }}</span><span>{{ item.unit }}</span><strong>{{ item.description }}</strong></div>{% empty %}<p>Keine Positionen.</p>{% endfor %}</div></div>{% empty %}<div class="tt-appt-process-empty">Noch keine Leistungen hinterlegt.</div>{% endfor %}
    {% if request.user.profile.role != 'technician' and not request.user.profile.is_mobile_worker %}<div class="tt-appt-process-actions"><form method="post" action="{% url 'next-appointment-to-quote' event.pk %}">{% csrf_token %}<button class="nx-btn" type="submit">Angebot erstellen</button></form>{% if documented %}<form method="post" action="{% url 'next-appointment-to-invoice' event.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-primary" type="submit">Rechnung erstellen</button></form>{% endif %}</div>{% endif %}
  </section>

'''
        text = text.replace(marker, services + marker, 1)

    text = text.replace('  {% if event.project %}\n  <section class="nx-job-address">', '  {% if event.project or event.customer %}\n  <section class="nx-job-address">', 1)
    text = text.replace('<h2>{{ event.project.customer.display_name }}</h2>', '<h2>{% if event.project %}{{ event.project.customer.display_name }}{% else %}{{ event.customer.display_name }}{% endif %}</h2>', 1)
    old_addr = '<p>{% if event.project.object_location %}{{ event.project.object_location.street }}, {{ event.project.object_location.postal_code }} {{ event.project.object_location.city }}{% elif event.location %}{{ event.location }}{% else %}{{ event.project.customer.street }}, {{ event.project.customer.postal_code }} {{ event.project.customer.city }}{% endif %}</p>'
    new_addr = '<p>{% if event.project and event.project.object_location %}{{ event.project.object_location.street }}, {{ event.project.object_location.postal_code }} {{ event.project.object_location.city }}{% elif event.location %}{{ event.location }}{% elif event.project %}{{ event.project.customer.street }}, {{ event.project.customer.postal_code }} {{ event.project.customer.city }}{% else %}{{ event.customer.street }}, {{ event.customer.postal_code }} {{ event.customer.city }}{% endif %}</p>'
    if old_addr in text:
        text = text.replace(old_addr, new_addr, 1)
    text = text.replace('{% with phone=event.project.customer.mobile|default:event.project.customer.phone %}', '{% if event.project %}{% with phone=event.project.customer.mobile|default:event.project.customer.phone %}', 1)
    text = text.replace('{% endwith %}\n      {% if event.location %}', '{% endwith %}{% else %}{% with phone=event.customer.mobile|default:event.customer.phone %}{% if phone %}<a href="tel:{{ phone }}">☎ Anrufen</a>{% else %}<span></span>{% endif %}{% endwith %}{% endif %}\n      {% if event.location %}', 1)
    text = text.replace('{% if not employee %}disabled{% endif %}>{% if running %}', '{% if not employee or not event.project %}disabled{% endif %}>{% if running %}', 1)
    text = text.replace('value="{{ event.project.customer.display_name }}"', 'value="{% if event.project %}{{ event.project.customer.display_name }}{% else %}{{ event.customer.display_name }}{% endif %}"', 1)
    text = text.replace('placeholder="Was wurde vor Ort gemacht? Zum Beispiel: Rohrbruch lokalisiert, Leitung repariert, Anlage geprüft …"></textarea>', 'placeholder="Was wurde vor Ort gemacht? Zum Beispiel: Rohrbruch lokalisiert, Leitung repariert, Anlage geprüft …">{{ event.work_report }}</textarea>', 1)

    field_old = r'''      <div class="nx-doc-section">
        <div class="nx-grid nx-grid-2">
          <div class="nx-field"><label>Leistungen</label><textarea class="nx-control" name="services" placeholder="Ausgeführte Arbeiten"></textarea></div>
          <div class="nx-field"><label>Material</label><textarea class="nx-control" name="material" placeholder="Verwendetes Material"></textarea></div>
        </div>
      </div>
'''
    field_new = r'''      <div class="nx-doc-section" data-field-services>
        <div class="nx-doc-title"><div><b>Leistungen</b><small>Art, Menge, Einheit und Bezeichnung · Preise werden vor Ort nicht angezeigt</small></div><button class="nx-btn" type="button" data-field-add-service>＋ Hinzufügen</button></div>
        <div class="tt-field-service-list" data-field-service-list>{% for group in service_groups %}{% for item in group.items.all %}<div class="tt-field-service-row" data-field-service-row><input type="hidden" name="document_service_id" value="{{ item.pk }}"><select class="nx-control" name="document_service_kind"><option value="labour" {% if item.kind == 'labour' %}selected{% endif %}>Arbeitszeit</option><option value="material" {% if item.kind == 'material' %}selected{% endif %}>Material</option><option value="mixed" {% if item.kind == 'mixed' %}selected{% endif %}>Mischposition</option><option value="other" {% if item.kind == 'other' %}selected{% endif %}>Sonstiges</option></select><input class="nx-control" name="document_service_quantity" type="number" step="0.001" value="{{ item.quantity }}" aria-label="Menge"><input class="nx-control" name="document_service_unit" value="{{ item.unit }}" aria-label="Einheit"><input class="nx-control" name="document_service_description" value="{{ item.description }}" aria-label="Bezeichnung"><select class="nx-control tt-field-catalog" name="document_service_catalog_id" data-field-catalog aria-label="Katalog"><option value="">Katalog</option>{% for c in appointment_catalog %}<option value="{{ c.pk }}" data-kind="{% if c.kind == 'service' %}labour{% elif c.kind == 'material' %}material{% else %}other{% endif %}" data-unit="{{ c.unit }}" data-description="{{ c.name|escape }}" {% if item.catalog_item_id == c.pk %}selected{% endif %}>{{ c.code }} · {{ c.name }}</option>{% endfor %}</select></div>{% endfor %}{% endfor %}</div>
        <div class="nx-grid nx-grid-2" style="margin-top:10px"><div class="nx-field"><label>Zusätzliche Leistungsnotiz</label><textarea class="nx-control" name="services"></textarea></div><div class="nx-field"><label>Zusätzliche Materialnotiz</label><textarea class="nx-control" name="material"></textarea></div></div>
      </div>
      <template data-field-service-template><div class="tt-field-service-row" data-field-service-row><input type="hidden" name="document_service_id" value=""><select class="nx-control" name="document_service_kind"><option value="labour">Arbeitszeit</option><option value="material">Material</option><option value="other" selected>Sonstiges</option></select><input class="nx-control" name="document_service_quantity" type="number" step="0.001" value="1" aria-label="Menge"><input class="nx-control" name="document_service_unit" value="Stk." aria-label="Einheit"><input class="nx-control" name="document_service_description" placeholder="Bezeichnung" aria-label="Bezeichnung"><select class="nx-control tt-field-catalog" name="document_service_catalog_id" data-field-catalog><option value="">Katalog</option>{% for c in appointment_catalog %}<option value="{{ c.pk }}" data-kind="{% if c.kind == 'service' %}labour{% elif c.kind == 'material' %}material{% else %}other{% endif %}" data-unit="{{ c.unit }}" data-description="{{ c.name|escape }}">{{ c.code }} · {{ c.name }}</option>{% endfor %}</select></div></template>
'''
    if field_new not in text:
        text = _replace(text, field_old, field_new, "mobile Leistungen")

    if "fieldServiceTemplate" not in text:
        script = r'''<script>(()=>{const root=document.querySelector('[data-field-services]'),list=root?.querySelector('[data-field-service-list]'),fieldServiceTemplate=document.querySelector('[data-field-service-template]');root?.querySelector('[data-field-add-service]')?.addEventListener('click',()=>{if(list&&fieldServiceTemplate)list.appendChild(fieldServiceTemplate.content.cloneNode(true));});root?.addEventListener('change',e=>{const select=e.target.closest('[data-field-catalog]');if(!select||!select.value)return;const option=select.selectedOptions[0],row=select.closest('[data-field-service-row]');row.querySelector('[name="document_service_kind"]').value=option.dataset.kind||'other';row.querySelector('[name="document_service_unit"]').value=option.dataset.unit||'Stk.';row.querySelector('[name="document_service_description"]').value=option.dataset.description||option.textContent.trim();});})();</script>
'''
        text += script
    module.write(rel, text)

    css_rel = "static/css/tooltime-phase14-appointment-detail.css"
    css = module.read(css_rel)
    if "/* A+BAU TOOLTIME APPOINTMENT PROCESS */" not in css:
        css += r'''
/* A+BAU TOOLTIME APPOINTMENT PROCESS */
.tt-appt-process-services{display:grid;gap:14px;margin:0 0 18px;padding:20px;border:1px solid #e3e8ef;border-radius:18px;background:#fff}.tt-appt-process-head{display:flex;justify-content:space-between;align-items:center;gap:14px}.tt-appt-process-head>div{display:grid}.tt-appt-process-head span{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#8993a3}.tt-appt-process-group{display:grid;gap:7px}.tt-appt-process-group h3{margin:0;font-size:13px}.tt-appt-process-table{display:grid;border:1px solid #edf0f4;border-radius:11px;overflow:hidden}.tt-appt-process-table>div{display:grid;grid-template-columns:120px 80px 80px 1fr;gap:8px;padding:9px 11px;border-top:1px solid #edf0f4;font-size:12px}.tt-appt-process-table>.head{border-top:0;background:#f7f9fb;color:#768195;font-size:10px;font-weight:800;text-transform:uppercase}.tt-appt-process-actions{display:flex;justify-content:flex-end;gap:8px}.tt-field-service-list{display:grid;gap:8px}.tt-field-service-row{display:grid;grid-template-columns:120px 75px 75px minmax(160px,1fr) minmax(140px,.8fr);gap:7px}.tt-appt-process-empty{padding:12px;border:1px dashed #dce2ea;border-radius:10px;color:#7b8494}@media(max-width:760px){.tt-appt-process-table>div{grid-template-columns:85px 55px 60px 1fr}.tt-field-service-row{grid-template-columns:1fr 1fr}.tt-field-service-row input[name="document_service_description"],.tt-field-service-row select[name="document_service_catalog_id"]{grid-column:1/-1}.tt-appt-process-actions{display:grid}.tt-appt-process-actions .nx-btn{width:100%}}
'''
        module.write(css_rel, css)


def patch_quote_actions(module) -> None:
    rel = "templates/rebuild/document_editor.html"
    text = module.read(rel)
    anchor = '''  {% if document.status == 'accepted' %}<form method="post" action="{% url 'next-quote-order-confirmation' document.pk %}" data-phase7-order-confirmation>{% csrf_token %}<button class="nx-btn" type="submit">{% if tt.phase7_order_confirmation %}Auftragsbestätigung herunterladen{% else %}Auftragsbestätigung erstellen{% endif %}</button></form>{% endif %}'''
    addition = anchor + '''
  {% if document.status == 'accepted' %}<form method="post" action="{% url 'next-quote-to-appointment' document.pk %}" data-quote-to-appointment>{% csrf_token %}<button class="nx-btn" type="submit">Termin erstellen</button></form>{% endif %}'''
    if "data-quote-to-appointment" not in text:
        if anchor not in text:
            raise RuntimeError("Appointment parity UI: accepted quote action anchor fehlt")
        text = text.replace(anchor, addition, 1)
    module.write(rel, text)

    rel = "templates/rebuild/quotes.html"
    text = module.read(rel)
    anchor = '''{% if row.quote.status == 'accepted' %}<form method="post" action="{% url 'next-quote-order-confirmation' row.quote.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-small" type="submit">Auftragsbestätigung</button></form>{% endif %}'''
    addition = anchor + '''{% if row.quote.status == 'accepted' %}<form method="post" action="{% url 'next-quote-to-appointment' row.quote.pk %}">{% csrf_token %}<button class="nx-btn nx-btn-small" type="submit">Termin erstellen</button></form>{% endif %}'''
    if "next-quote-to-appointment" not in text:
        if anchor not in text:
            raise RuntimeError("Appointment parity UI: quote list action anchor fehlt")
        text = text.replace(anchor, addition, 1)
    module.write(rel, text)


def patch_browser_smoke(module) -> None:
    rel = "scripts/production_browser_smoke.py"
    text = module.read(rel)
    marker = "# A+BAU TOOLTIME APPOINTMENT PROCESS BROWSER SMOKE"
    if marker not in text:
        anchor = "            context.close()\n"
        pos = text.rfind(anchor)
        if pos < 0:
            raise RuntimeError("Appointment parity UI: browser smoke anchor fehlt")
        block = r'''            # A+BAU TOOLTIME APPOINTMENT PROCESS BROWSER SMOKE
            response = page.goto(urljoin(base_url, "appointments/new/"), wait_until="domcontentloaded", timeout=30_000)
            if response is None or response.status >= 500:
                fail(f"appointment parity create returned {response.status if response else 'no response'}")
            body = page.locator("body").inner_text()
            for label in ("Terminname", "Mitarbeiter hinzufügen", "Leistungsgruppe hinzufügen", "Position hinzufügen", "Arbeitsbericht"):
                if label not in body:
                    fail(f"appointment parity is missing {label!r}")
            if page.locator('[data-service-editor]').count() != 1:
                fail("appointment service editor is missing")
'''
        text = text[:pos] + block + text[pos:]
    module.write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def run(module) -> None:
    patch_form(module)
    patch_detail(module)
    patch_quote_actions(module)
    patch_browser_smoke(module)
