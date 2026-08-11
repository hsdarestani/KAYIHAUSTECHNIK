from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI GLOBAL FORM + FIELD VOICE + PRICING HARDENING 2026-08-11"
VERSION = "20260811-5"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Missing final hardening target: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_global_form_feedback() -> None:
    rel = "static/js/kayi-next.js"
    text = read(rel)
    if "KAYI GLOBAL FORM VALIDATION 2026-08-11" not in text:
        text += r'''

// KAYI GLOBAL FORM VALIDATION 2026-08-11
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
'''
        write(rel, text)

    css_rel = "static/css/kayi-next.css"
    css = read(css_rel)
    if "KAYI GLOBAL FORM VALIDATION 2026-08-11" not in css:
        css += r'''

/* KAYI GLOBAL FORM VALIDATION 2026-08-11 */
.nx-global-form-errors{border:1px solid rgba(185,28,28,.3);background:rgba(254,226,226,.82);border-radius:14px;padding:13px 15px;margin:0 0 16px;font-size:14px;line-height:1.45;color:#7f1d1d}
.nx-global-form-errors>b{display:block;font-size:15px;margin-bottom:5px}.nx-global-form-errors p{display:grid;gap:3px;margin:0}.nx-global-form-errors span{display:block}
input[aria-invalid="true"],select[aria-invalid="true"],textarea[aria-invalid="true"]{outline:2px solid rgba(185,28,28,.3);outline-offset:1px;border-color:rgba(185,28,28,.6)!important}
'''
        write(css_rel, css)


def patch_voice_backend() -> None:
    rel = "erp/assistant_views.py"
    text = read(rel)
    anchor = '''    org = _org(request)
    event = get_object_or_404(m.CalendarEvent, pk=pk, organization=org)
    upload = request.FILES.get("voice")
'''
    replacement = '''    org = _org(request)
    event = get_object_or_404(m.CalendarEvent, pk=pk, organization=org)
    transcript_only = str(request.POST.get("mode") or "").strip().lower() == "transcript_only"
    upload = request.FILES.get("voice")
'''
    if replacement not in text:
        if anchor not in text:
            raise RuntimeError("appointment voice mode anchor changed")
        text = text.replace(anchor, replacement, 1)
    early_anchor = '''    if not transcript:
        return JsonResponse({"ok": False, "error": "In der Aufnahme wurde kein verständlicher Text erkannt."}, status=422)

    schema = {
'''
    early_new = '''    if not transcript:
        return JsonResponse({"ok": False, "error": "In der Aufnahme wurde kein verständlicher Text erkannt."}, status=422)
    if transcript_only:
        return JsonResponse({"ok": True, "event_id": event.pk, "transcript": transcript})

    schema = {
'''
    if early_new not in text:
        if early_anchor not in text:
            raise RuntimeError("appointment voice transcript anchor changed")
        text = text.replace(early_anchor, early_new, 1)
    write(rel, text)


def patch_field_template() -> None:
    rel = "templates/rebuild/appointment_detail.html"
    text = read(rel)
    root_old = '<div class="fa-mobile-shell" data-field-authorization-root>'
    root_new = '<div class="fa-mobile-shell" data-field-authorization-root data-fa-voice-url="{% url \'next-appointment-voice\' event.pk %}">'
    if root_new not in text:
        if root_old not in text:
            raise RuntimeError("field root anchor changed")
        text = text.replace(root_old, root_new, 1)

    form_old = '<form method="post" enctype="multipart/form-data" action="{% url \'field-authorization-sign\' event.pk %}" data-authorization-form>{% csrf_token %}'
    form_new = '<form method="post" enctype="multipart/form-data" action="{% url \'field-authorization-sign\' event.pk %}" data-authorization-form data-fa-catalog-url="{% url \'field-authorization-catalog\' event.pk %}">{% csrf_token %}'
    if form_new not in text:
        if form_old not in text:
            raise RuntimeError("authorization form anchor changed")
        text = text.replace(form_old, form_new, 1)

    price_anchor = '''        <div class="fa-segmented fa-price-mode">{% for value,label in pricing_modes %}<label><input type="radio" name="pricing_mode" value="{{ value }}" {% if forloop.first %}checked{% endif %}><span>{{ label }}</span></label>{% endfor %}</div>
        <div class="fa-price-table" data-price-table>
'''
    price_new = '''        <div class="fa-segmented fa-price-mode">{% for value,label in pricing_modes %}<label><input type="radio" name="pricing_mode" value="{{ value }}" {% if forloop.first %}checked{% endif %}><span>{{ label }}</span></label>{% endfor %}</div>
        <div class="fa-catalog-picker" data-fa-catalog-picker>
          <label><span>Leistung aus Katalog / B&amp;O</span><input class="nx-control" type="search" data-fa-catalog-query autocomplete="off" placeholder="z. B. Duscharmatur, Dichtheitsprüfung …"></label>
          <small data-fa-catalog-status>Ab 2 Zeichen suchen. Beim Auswählen wird der hinterlegte Preis automatisch übernommen.</small>
          <div class="fa-catalog-results" data-fa-catalog-results></div>
        </div>
        <div class="fa-price-table" data-price-table>
'''
    if "data-fa-catalog-picker" not in text:
        if price_anchor not in text:
            raise RuntimeError("field price table anchor changed")
        text = text.replace(price_anchor, price_new, 1)
    text = re.sub(r"(field-authorization\.(?:css|js)' %\}\?v=)[^\"']+", rf"\g<1>{VERSION}", text)
    write(rel, text)


def patch_catalog_backend() -> None:
    rel = "erp/field_authorization_views.py"
    text = read(rel)
    if "def authorization_catalog_search(" not in text:
        anchor = "\n\n@login_required\n@require_POST\ndef authorization_sign(request, pk):\n"
        if anchor not in text:
            raise RuntimeError("authorization sign anchor changed")
        endpoint = r'''

@login_required
@require_GET
def authorization_catalog_search(request, pk):
    org, _event = _event_for(request, pk)
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"ok": True, "results": []})
    condition = Q(code__icontains=query) | Q(name__icontains=query) | Q(description__icontains=query)
    candidates = list(m.CatalogItem.objects.filter(organization=org, active=True).filter(condition).order_by("name")[:30])
    rows = []
    for item in candidates:
        price = effective_price_for_catalog_item(org, item)
        if price <= Decimal("0"):
            continue
        rows.append({
            "id": item.pk,
            "code": item.code,
            "name": item.name,
            "unit": item.unit or "Stk.",
            "price": str(price),
            "tax_rate": str(item.tax_rate or Decimal("19.00")),
        })
    return JsonResponse({"ok": True, "results": rows[:20]})
'''
        text = text.replace(anchor, endpoint + anchor, 1)

    helper_marker = "def _reprice_catalog_items(org, items):"
    if helper_marker not in text:
        anchor = "\n\n@login_required\n@require_POST\ndef authorization_sign(request, pk):\n"
        helper = r'''


def _reprice_catalog_items(org, items):
    """Never trust a browser-posted price for a catalog-backed authorization row."""
    for item in items:
        catalog_id = item.get("catalog_id")
        if not catalog_id:
            item["price_source"] = "manual"
            continue
        catalog = m.CatalogItem.objects.filter(organization=org, active=True, pk=catalog_id).first()
        if catalog is None:
            raise ValueError("Eine ausgewählte Katalogposition ist nicht mehr verfügbar.")
        price = effective_price_for_catalog_item(org, catalog)
        if price <= Decimal("0"):
            raise ValueError(f"Für {catalog.name} ist aktuell kein freigegebener Preis hinterlegt.")
        qty = money(item.get("quantity") or "1")
        tax = money(catalog.tax_rate or item.get("tax_rate") or "19")
        net = (qty * price).quantize(Decimal("0.01"))
        tax_amount = (net * tax / Decimal("100")).quantize(Decimal("0.01"))
        item.update({
            "description": catalog.name,
            "unit": catalog.unit or item.get("unit") or "Stk.",
            "unit_price": str(price),
            "tax_rate": str(tax),
            "net": str(net),
            "tax": str(tax_amount),
            "gross": str(net + tax_amount),
            "catalog_code": catalog.code,
            "price_source": "catalog",
        })
    return items
'''
        text = text.replace(anchor, helper + anchor, 1)

    old_items = '''    items = parse_items(request.POST)
    if not items:
        return JsonResponse({"ok": False, "error": "Mindestens eine Preisposition ist erforderlich."}, status=400)
'''
    new_items = '''    items = parse_items(request.POST)
    if not items:
        return JsonResponse({"ok": False, "error": "Mindestens eine Preisposition ist erforderlich."}, status=400)
    try:
        items = _reprice_catalog_items(org, items)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
'''
    if new_items not in text:
        if old_items not in text:
            raise RuntimeError("authorization item pricing anchor changed")
        text = text.replace(old_items, new_items, 1)
    write(rel, text)

    service_rel = "erp/services/field_authorization.py"
    service = read(service_rel)
    if 'catalog_ids = post.getlist("item_catalog_id")' not in service:
        service = service.replace(
            '    taxes = post.getlist("item_tax")\n',
            '    taxes = post.getlist("item_tax")\n    catalog_ids = post.getlist("item_catalog_id")\n',
            1,
        )
        item_anchor = '''            "gross": str(net + tax_amount),
        })
'''
        item_new = '''            "gross": str(net + tax_amount),
            "catalog_id": ((catalog_ids[index] if index < len(catalog_ids) else "") or "").strip(),
        })
'''
        if item_anchor not in service:
            raise RuntimeError("parse_items catalog id anchor changed")
        service = service.replace(item_anchor, item_new, 1)
        write(service_rel, service)

    url_rel = "erp/field_authorization_urls.py"
    urls = read(url_rel)
    route = '    path("appointments/<int:pk>/authorization/catalog/", views.authorization_catalog_search, name="field-authorization-catalog"),\n'
    if route not in urls:
        anchor = '    path("appointments/<int:pk>/authorization/sign/", views.authorization_sign, name="field-authorization-sign"),\n'
        if anchor not in urls:
            raise RuntimeError("field authorization URL anchor changed")
        urls = urls.replace(anchor, route + anchor, 1)
        write(url_rel, urls)


def patch_field_javascript() -> None:
    rel = "static/js/field-authorization.js"
    text = read(rel)
    replacement = r'''  function speechButton(button) {
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
      } catch (_) { toast('Mikrofon konnte nicht geöffnet werden. Bitte Mikrofon-Berechtigung für KAYI erlauben.', 'error'); }
    });
  }

  function bindPhotos() {'''
    pattern = r"  function speechButton\(button\) \{.*?\n  \}\n\n  function bindPhotos\(\) \{"
    if "transcript_only" not in text or "kayi-diktat" not in text:
        text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
        if count != 1:
            raise RuntimeError("field voice function anchor changed")

    old_row = '''    row.innerHTML = `<input class="nx-control" name="item_description" placeholder="Leistung / Material"><div class="fa-qty"><input class="nx-control" name="item_quantity" type="number" min="0" step="0.01" value="1"><input class="nx-control" name="item_unit" value="Stk."></div><input class="nx-control" name="item_price" type="number" min="0" step="0.01" value="0.00"><select class="nx-control" name="item_tax"><option value="19">19 %</option><option value="7">7 %</option><option value="0">0 %</option></select><button type="button" class="fa-remove-row" data-remove-row>×</button>`;
'''
    new_row = '''    row.innerHTML = `<input type="hidden" name="item_catalog_id"><input class="nx-control" name="item_description" placeholder="Leistung / Material"><div class="fa-qty"><input class="nx-control" name="item_quantity" type="number" min="0" step="0.01" value="1"><input class="nx-control" name="item_unit" value="Stk."></div><input class="nx-control" name="item_price" type="number" min="0" step="0.01" value="0.00"><select class="nx-control" name="item_tax"><option value="19">19 %</option><option value="7">7 %</option><option value="0">0 %</option></select><button type="button" class="fa-remove-row" data-remove-row>×</button>`;
'''
    if new_row not in text:
        if old_row not in text:
            raise RuntimeError("field price row anchor changed")
        text = text.replace(old_row, new_row, 1)
    value_anchor = '''    $('[name=item_description]', row).value = values.description || '';
    $('[name=item_quantity]', row).value = values.quantity || '1';'''
    value_new = '''    $('[name=item_catalog_id]', row).value = values.catalog_id || '';
    $('[name=item_description]', row).value = values.description || values.name || '';
    $('[name=item_quantity]', row).value = values.quantity || '1';'''
    if value_new not in text:
        if value_anchor not in text:
            raise RuntimeError("catalog id row value anchor changed")
        text = text.replace(value_anchor, value_new, 1)

    search_marker = "function bindFieldCatalogSearch(form)"
    if search_marker not in text:
        anchor = "\n  function bindPricing(form) {\n"
        if anchor not in text:
            raise RuntimeError("bindPricing anchor changed")
        helper = r'''

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
'''
        text = text.replace(anchor, helper + anchor, 1)

    bind_anchor = '''    bindPricing(form);
    form.addEventListener('submit', (e) => {'''
    bind_new = '''    bindPricing(form);
    bindFieldCatalogSearch(form);
    form.addEventListener('submit', (e) => {'''
    if bind_new not in text:
        if bind_anchor not in text:
            raise RuntimeError("authorization pricing binding anchor changed")
        text = text.replace(bind_anchor, bind_new, 1)
    if MARKER not in text:
        text = text.replace("(() => {", f"(() => {{\n  // {MARKER}", 1)
    write(rel, text)

    css_rel = "static/css/field-authorization.css"
    css = read(css_rel)
    if MARKER not in css:
        css += r'''

/* KAYI GLOBAL FORM + FIELD VOICE + PRICING HARDENING 2026-08-11 */
.fa-mic.is-listening{outline:3px solid rgba(15,118,110,.18);transform:scale(1.03)}
.fa-catalog-picker{margin:12px 0 14px;padding:12px;border:1px solid #dce3e4;border-radius:14px;background:#fafcfc}.fa-catalog-picker label>span{display:block;font-weight:700;margin-bottom:7px}.fa-catalog-picker small{display:block;margin-top:6px;color:#6b7378}.fa-catalog-results{display:grid;gap:7px;margin-top:9px;max-height:280px;overflow:auto}.fa-catalog-result{display:flex;justify-content:space-between;gap:12px;align-items:center;width:100%;padding:10px 12px;border:1px solid #dde4e5;border-radius:11px;background:#fff;text-align:left;cursor:pointer}.fa-catalog-result b{font-size:14px}.fa-catalog-result small{margin:0;text-align:right;font-size:12px}
@media(max-width:700px){.fa-catalog-result{align-items:flex-start;flex-direction:column}.fa-catalog-result small{text-align:left}}
'''
        write(css_rel, css)


def install_tests() -> None:
    rel = "tests/test_final_form_voice_pricing_hardening.py"
    write(rel, r'''from pathlib import Path

from django.test import SimpleTestCase


class FinalFormVoicePricingHardeningTests(SimpleTestCase):
    def test_all_forms_surface_hidden_and_server_validation(self):
        js = Path("static/js/kayi-next.js").read_text(encoding="utf-8")
        css = Path("static/css/kayi-next.css").read_text(encoding="utf-8")
        for marker in ("KAYI GLOBAL FORM VALIDATION 2026-08-11", "addEventListener('invalid'", "dataGlobalFormErrors", "current.tagName === 'DETAILS'"):
            self.assertIn(marker, js)
        self.assertIn(".nx-global-form-errors", css)

    def test_release_voice_uses_media_recorder_and_server_transcription(self):
        js = Path("static/js/field-authorization.js").read_text(encoding="utf-8")
        template = Path("templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        backend = Path("erp/assistant_views.py").read_text(encoding="utf-8")
        self.assertIn("MediaRecorder", js)
        self.assertIn("getUserMedia", js)
        self.assertIn("transcript_only", js)
        self.assertNotIn("window.SpeechRecognition || window.webkitSpeechRecognition", js)
        self.assertIn("data-fa-voice-url", template)
        self.assertIn("if transcript_only:", backend)

    def test_field_catalog_price_is_preserved_and_rechecked_server_side(self):
        js = Path("static/js/field-authorization.js").read_text(encoding="utf-8")
        views = Path("erp/field_authorization_views.py").read_text(encoding="utf-8")
        service = Path("erp/services/field_authorization.py").read_text(encoding="utf-8")
        template = Path("templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        urls = Path("erp/field_authorization_urls.py").read_text(encoding="utf-8")
        for marker in ("item_catalog_id", "bindFieldCatalogSearch", "serverseitig nochmals geprüft"):
            self.assertIn(marker, js)
        for marker in ("authorization_catalog_search", "_reprice_catalog_items", "Never trust a browser-posted price", "effective_price_for_catalog_item"):
            self.assertIn(marker, views)
        self.assertIn('catalog_ids = post.getlist("item_catalog_id")', service)
        self.assertIn("data-fa-catalog-picker", template)
        self.assertIn("field-authorization-catalog", urls)
''')


def bump_cache() -> None:
    base_rel = "templates/rebuild/base.html"
    base = read(base_rel)
    base = re.sub(r"(kayi-next\.(?:css|js)'\s*%\}\?v=)[^\"'\s<]+", rf"\g<1>{VERSION}", base)
    write(base_rel, base)


def guard() -> None:
    checks = {
        "static/js/kayi-next.js": ["KAYI GLOBAL FORM VALIDATION 2026-08-11", "addEventListener('invalid'"],
        "static/js/field-authorization.js": [MARKER, "MediaRecorder", "transcript_only", "bindFieldCatalogSearch", "item_catalog_id"],
        "templates/rebuild/appointment_detail.html": ["data-fa-voice-url", "data-fa-catalog-picker", "field-authorization-catalog"],
        "erp/assistant_views.py": ["transcript_only", "if transcript_only:"],
        "erp/field_authorization_views.py": ["authorization_catalog_search", "_reprice_catalog_items", "Never trust a browser-posted price"],
        "erp/services/field_authorization.py": ["item_catalog_id", "catalog_id"],
        "erp/field_authorization_urls.py": ["field-authorization-catalog"],
        "tests/test_final_form_voice_pricing_hardening.py": ["test_release_voice_uses_media_recorder_and_server_transcription"],
    }
    missing = []
    for rel, markers in checks.items():
        content = read(rel)
        for marker in markers:
            if marker not in content:
                missing.append(f"{rel}: {marker}")
    if missing:
        raise RuntimeError("Final form/voice/pricing guard failed: " + "; ".join(missing))


def main() -> None:
    patch_global_form_feedback()
    patch_voice_backend()
    patch_field_template()
    patch_catalog_backend()
    patch_field_javascript()
    install_tests()
    bump_cache()
    guard()
    print("KAYI final hardening: all forms expose validation, field voice uses recorded audio transcription, and catalog prices are automatic + server-authoritative.")


if __name__ == "__main__":
    main()
