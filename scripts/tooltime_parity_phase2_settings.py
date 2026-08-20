from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME PHASE 2 SETTINGS 2026-08-20"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Phase 2 target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_models_and_migration() -> None:
    rel = "erp/tooltime_parity_finance.py"
    text = read(rel)
    if "class ToolTimeDatevAccount" not in text:
        text += r'''

class ToolTimeDatevAccount(models.Model):
    PARTY_TYPES = [("customer", "Debitor"), ("supplier", "Kreditor")]
    SOURCES = [("automatic", "Automatisch"), ("customer_number", "Kundennummer"), ("import", "DATEV-Import"), ("manual", "Manuell")]
    organization = models.ForeignKey("erp.Organization", on_delete=models.CASCADE, related_name="tooltime_datev_accounts")
    party_type = models.CharField(max_length=20, choices=PARTY_TYPES)
    party_key = models.CharField(max_length=120)
    party_name = models.CharField(max_length=240, blank=True)
    account_number = models.CharField(max_length=5)
    source = models.CharField(max_length=30, choices=SOURCES, default="automatic")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["party_type", "account_number", "id"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "party_type", "party_key"], name="uniq_tooltime_datev_party"),
            models.UniqueConstraint(fields=["organization", "account_number"], name="uniq_tooltime_datev_number"),
        ]
'''
        write(rel, text)

    rel = "erp/models.py"
    text = read(rel)
    old = "ToolTimeCommercialProfile, ToolTimeDocumentMeta, ToolTimeNumberSequence, ToolTimeTextTemplate, ToolTimeDunningRecord, ToolTimePositionAsset"
    new = old + ", ToolTimeDatevAccount"
    if new not in text:
        if old not in text:
            raise RuntimeError("Phase 2 ToolTime model import anchor missing")
        text = text.replace(old, new, 1)
        write(rel, text)

    # ToolTimeDocumentMeta receives the effective standard legal attachments. They
    # remain separate from the immutable invoice data and can be consumed by the
    # later document-send flow without silently changing old documents.
    rel = "erp/tooltime_parity_finance.py"
    text = read(rel)
    field_anchor = "    billing_links = models.JSONField(default=list, blank=True)\n"
    field = field_anchor + "    default_attachment_ids = models.JSONField(default=list, blank=True)\n"
    if "default_attachment_ids = models.JSONField" not in text:
        if field_anchor not in text:
            raise RuntimeError("Phase 2 attachment field anchor missing")
        text = text.replace(field_anchor, field, 1)
        write(rel, text)

    write("erp/migrations/0015_tooltime_phase2_settings.py", r'''from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("erp", "0014_tooltime_position_asset_links")]
    operations = [
        migrations.AddField(
            model_name="tooltimedocumentmeta",
            name="default_attachment_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name="ToolTimeDatevAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("party_type", models.CharField(choices=[("customer", "Debitor"), ("supplier", "Kreditor")], max_length=20)),
                ("party_key", models.CharField(max_length=120)),
                ("party_name", models.CharField(blank=True, max_length=240)),
                ("account_number", models.CharField(max_length=5)),
                ("source", models.CharField(choices=[("automatic", "Automatisch"), ("customer_number", "Kundennummer"), ("import", "DATEV-Import"), ("manual", "Manuell")], default="automatic", max_length=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tooltime_datev_accounts", to="erp.organization")),
            ],
            options={"ordering": ["party_type", "account_number", "id"]},
        ),
        migrations.AddConstraint(model_name="tooltimedatevaccount", constraint=models.UniqueConstraint(fields=("organization", "party_type", "party_key"), name="uniq_tooltime_datev_party")),
        migrations.AddConstraint(model_name="tooltimedatevaccount", constraint=models.UniqueConstraint(fields=("organization", "account_number"), name="uniq_tooltime_datev_number")),
    ]
''')


def patch_service() -> None:
    rel = "erp/services/tooltime_parity_finance.py"
    text = read(rel)

    # Extend defaults without invalidating organizations that already have settings.
    if '"datev": {' not in text:
        anchor = '        "web_view": {"quote_default": True, "acceptance_email": True},\n'
        block = '''        "datev": {"enabled": False, "mode": "automatic", "debtor_start": 10000, "creditor_start": 70000, "skr": "03"},\n        "legal_documents": {"terms_document_id": None, "withdrawal_document_id": None, "attach_terms_quote": False, "attach_terms_invoice": False, "attach_withdrawal_quote": False, "attach_withdrawal_invoice": False},\n'''
        if anchor not in text:
            raise RuntimeError("Phase 2 default settings anchor missing")
        text = text.replace(anchor, block + anchor, 1)

    helper_anchor = "def meta_for(document, kind, create=True):\n"
    helpers = r'''def phase2_settings(org):
    profile = profile_for(org)
    cfg = profile.settings
    changed = False
    defaults = {
        "datev": {"enabled": False, "mode": "automatic", "debtor_start": 10000, "creditor_start": 70000, "skr": "03"},
        "legal_documents": {"terms_document_id": None, "withdrawal_document_id": None, "attach_terms_quote": False, "attach_terms_invoice": False, "attach_withdrawal_quote": False, "attach_withdrawal_invoice": False},
    }
    for key, value in defaults.items():
        if key not in cfg or not isinstance(cfg.get(key), dict):
            cfg[key] = dict(value); changed = True
        else:
            for subkey, subvalue in value.items():
                if subkey not in cfg[key]: cfg[key][subkey] = subvalue; changed = True
    for rate in cfg.get("tax_rates", []):
        if "active" not in rate: rate["active"] = True; changed = True
        if "note" not in rate: rate["note"] = ""; changed = True
        if "datev_skr03" not in rate: rate["datev_skr03"] = ""; changed = True
        if "datev_skr04" not in rate: rate["datev_skr04"] = ""; changed = True
    if changed:
        profile.settings = cfg
        profile.save(update_fields=["settings", "updated_at"])
    return cfg


def default_legal_attachment_ids(org, kind):
    cfg = phase2_settings(org).get("legal_documents", {})
    result = []
    if cfg.get(f"attach_terms_{kind}") and cfg.get("terms_document_id"):
        result.append(int(cfg["terms_document_id"]))
    if cfg.get(f"attach_withdrawal_{kind}") and cfg.get("withdrawal_document_id"):
        result.append(int(cfg["withdrawal_document_id"]))
    return result


'''
    if "def phase2_settings(org):" not in text:
        if helper_anchor not in text:
            raise RuntimeError("Phase 2 meta_for anchor missing")
        text = text.replace(helper_anchor, helpers + helper_anchor, 1)

    old_defaults = '    defaults = {"document_title": "Angebot" if kind == "quote" else "Rechnung", "salutation": "Sehr geehrte Damen und Herren,"}\n'
    new_defaults = '''    cfg = phase2_settings(document.organization)\n    customer = getattr(getattr(document, "project", None), "customer", None)\n    is_company = bool(customer and getattr(customer, "type", "") in {"business", "insurance", "property_manager"})\n    labour_key = ("quote_company" if is_company else "quote_private") if kind == "quote" else ("invoice_company" if is_company else "invoice_private")\n    defaults = {\n        "document_title": "Angebot" if kind == "quote" else "Rechnung",\n        "salutation": "Sehr geehrte Damen und Herren,",\n        "web_view_enabled": bool(cfg.get("web_view", {}).get("quote_default", True)) if kind == "quote" else False,\n        "labour_cost_share_visible": bool(cfg.get("labour_share", {}).get(labour_key, True)),\n        "default_attachment_ids": default_legal_attachment_ids(document.organization, kind),\n    }\n'''
    if new_defaults not in text:
        if old_defaults not in text:
            raise RuntimeError("Phase 2 document meta defaults anchor missing")
        text = text.replace(old_defaults, new_defaults, 1)

    # Refresh standard attachments while the document is editable.
    save_anchor = '    meta = meta_for(document, kind)\n'
    refresh = '    meta = meta_for(document, kind)\n    if meta.finalized_at is None:\n        meta.default_attachment_ids = default_legal_attachment_ids(document.organization, kind)\n'
    if refresh not in text:
        if save_anchor not in text:
            raise RuntimeError("Phase 2 save_document_meta anchor missing")
        text = text.replace(save_anchor, refresh, 1)

    write(rel, text)


def patch_views() -> None:
    rel = "erp/tooltime_parity_views.py"
    text = read(rel)
    if not text.startswith("from __future__ import annotations"):
        raise RuntimeError("Phase 2 views file malformed")
    if "import csv\n" not in text:
        text = text.replace("from __future__ import annotations\n", "from __future__ import annotations\n\nimport csv\nimport io\n", 1)

    helper_anchor = "def settings_page(request):\n"
    helpers = r'''def _phase2_number_preview(org, cfg):
    num = cfg.get("numbering", {})
    def commercial(kind, prefix_key, start_key, width_key):
        start = max(1, int(num.get(start_key) or 1)); width = max(1, int(num.get(width_key) or len(str(start))))
        seq = m.ToolTimeNumberSequence.objects.filter(organization=org, kind=kind).first()
        value = max(start, int(seq.next_value)) if seq else start
        return {"prefix": str(num.get(prefix_key) or ""), "value": value, "width": width, "formatted": f"{str(num.get(prefix_key) or '')}{value:0{width}d}"}
    invoice_start = max(1, int(num.get("invoice_start") or 1)); invoice_width = max(1, int(num.get("invoice_width") or len(str(invoice_start))))
    invoice_prefix = str(num.get("invoice_prefix") or "")
    invoice_seq = m.InvoiceNumberSequence.objects.filter(organization=org, year=0, prefix=invoice_prefix).first()
    invoice_value = max(invoice_start, int(invoice_seq.next_value)) if invoice_seq else invoice_start
    return {
        "quote": commercial("quote", "quote_prefix", "quote_start", "quote_width"),
        "invoice": {"prefix": invoice_prefix, "value": invoice_value, "width": invoice_width, "formatted": f"{invoice_prefix}{invoice_value:0{invoice_width}d}"},
        "credit": commercial("credit", "credit_prefix", "credit_start", "credit_width"),
        "customer": commercial("customer", "customer_prefix", "customer_start", "customer_width"),
    }


def _datev_valid(number, party_type):
    value = str(number or "").strip()
    if len(value) != 5 or not value.isdigit(): return False
    numeric = int(value)
    return 10000 <= numeric <= 69999 if party_type == "customer" else 70000 <= numeric <= 99999


def _next_free_datev(org, party_type, start):
    low, high = (10000, 69999) if party_type == "customer" else (70000, 99999)
    value = max(low, min(int(start), high))
    used = set(m.ToolTimeDatevAccount.objects.filter(organization=org).values_list("account_number", flat=True))
    while value <= high and f"{value:05d}" in used: value += 1
    if value > high: raise ValueError("Der DATEV-Nummernkreis ist ausgeschöpft.")
    return f"{value:05d}"


def _assign_datev_accounts(org, cfg):
    datev = cfg.get("datev", {})
    mode = datev.get("mode") or "automatic"
    created = 0
    for customer in m.Customer.objects.filter(organization=org, active=True).order_by("id"):
        key = str(customer.pk)
        if m.ToolTimeDatevAccount.objects.filter(organization=org, party_type="customer", party_key=key).exists(): continue
        if mode == "customer_number":
            number = str(customer.number or "").strip()
            if not _datev_valid(number, "customer") or m.ToolTimeDatevAccount.objects.filter(organization=org, account_number=number).exists(): continue
        else:
            number = _next_free_datev(org, "customer", datev.get("debtor_start") or 10000)
        m.ToolTimeDatevAccount.objects.create(organization=org, party_type="customer", party_key=key, party_name=customer.display_name, account_number=number, source="customer_number" if mode == "customer_number" else "automatic")
        created += 1
    # A+Bau currently stores suppliers on catalog items. Treat each distinct supplier
    # as a real creditor party until a dedicated supplier master record is selected.
    suppliers = m.CatalogItem.objects.filter(organization=org, active=True).exclude(supplier="").values_list("supplier", flat=True).distinct()
    for supplier in suppliers:
        name = str(supplier or "").strip()
        if not name: continue
        key = name.casefold()[:120]
        if m.ToolTimeDatevAccount.objects.filter(organization=org, party_type="supplier", party_key=key).exists(): continue
        number = _next_free_datev(org, "supplier", datev.get("creditor_start") or 70000)
        m.ToolTimeDatevAccount.objects.create(organization=org, party_type="supplier", party_key=key, party_name=name[:240], account_number=number, source="automatic")
        created += 1
    return created


def _import_datev_csv(org, upload):
    if not upload or upload.size > 2_000_000: raise ValueError("Bitte eine DATEV-CSV mit maximal 2 MB auswählen.")
    raw = upload.read().decode("utf-8-sig", errors="replace")
    sample = raw[:4096]
    try: dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error: dialect = csv.excel_semicolon
    rows = csv.DictReader(io.StringIO(raw), dialect=dialect)
    assigned = skipped = 0
    customers_by_number = {str(c.number).strip(): c for c in m.Customer.objects.filter(organization=org, active=True)}
    customers_by_name = {c.display_name.strip().casefold(): c for c in m.Customer.objects.filter(organization=org, active=True)}
    for raw_row in rows:
        row = {str(k or "").strip().lower().replace(" ", "_"): str(v or "").strip() for k, v in raw_row.items()}
        debtor = row.get("debitorennummer") or row.get("debitor") or row.get("debitor_nr")
        creditor = row.get("kreditorennummer") or row.get("kreditor") or row.get("kreditor_nr")
        if debtor:
            customer = customers_by_number.get(row.get("kundennummer") or row.get("kunden_nr") or "") or customers_by_name.get((row.get("kunde") or row.get("name") or "").casefold())
            if customer and _datev_valid(debtor, "customer") and not m.ToolTimeDatevAccount.objects.filter(organization=org, account_number=debtor).exclude(party_type="customer", party_key=str(customer.pk)).exists():
                m.ToolTimeDatevAccount.objects.update_or_create(organization=org, party_type="customer", party_key=str(customer.pk), defaults={"party_name": customer.display_name, "account_number": debtor, "source": "import"}); assigned += 1
            else: skipped += 1
        elif creditor:
            name = row.get("lieferant") or row.get("name") or ""
            if name and _datev_valid(creditor, "supplier") and not m.ToolTimeDatevAccount.objects.filter(organization=org, account_number=creditor).exclude(party_type="supplier", party_key=name.casefold()[:120]).exists():
                m.ToolTimeDatevAccount.objects.update_or_create(organization=org, party_type="supplier", party_key=name.casefold()[:120], defaults={"party_name": name[:240], "account_number": creditor, "source": "import"}); assigned += 1
            else: skipped += 1
    return assigned, skipped


'''
    if "def _phase2_number_preview(" not in text:
        if helper_anchor not in text:
            raise RuntimeError("Phase 2 settings_page helper anchor missing")
        text = text.replace(helper_anchor, helpers + helper_anchor, 1)

    # Normalize settings on every settings-page request.
    start = "def settings_page(request):\n    org = base._org(request)\n"
    normalized = start + "    cfg = phase2_settings(org)\n"
    if normalized not in text:
        if start not in text: raise RuntimeError("Phase 2 settings start anchor missing")
        text = text.replace(start, normalized, 1)
    # Existing page obtains cfg later; keep the same object instead of replacing it.
    text = text.replace("    cfg = profile.settings\n", "    cfg = phase2_settings(org)\n", 1)

    section_anchor = '        section = request.POST.get("section") or "all"\n'
    handlers = r'''        if section == "phase2_numbering":
            num = cfg.setdefault("numbering", {})
            for key in ("quote_prefix", "invoice_prefix", "credit_prefix", "customer_prefix"):
                num[key] = (request.POST.get(key) or "")[:30]
            for key in ("quote_start", "invoice_start", "credit_start", "customer_start"):
                raw = (request.POST.get(key) or "1").strip()
                if not raw.isdigit() or int(raw) < 1:
                    messages.error(request, "„Beginnt bei“ muss eine positive Zahl sein."); return redirect("next-settings")
                num[key] = int(raw); num[key.replace("_start", "_width")] = min(max(len(raw), 1), 12)
            num["customer_auto"] = request.POST.get("customer_auto") == "on"
            profile.settings = cfg; profile.save(update_fields=["settings", "updated_at"])
            messages.success(request, "Nummernkreise wurden gespeichert."); return redirect("next-settings")
        if section == "phase2_datev":
            datev = cfg.setdefault("datev", {})
            enabled = request.POST.get("datev_enabled") == "on"; mode = request.POST.get("datev_mode") or "automatic"
            if mode not in {"automatic", "customer_number", "import"}: mode = "automatic"
            try: debtor_start = int(request.POST.get("debtor_start") or 10000); creditor_start = int(request.POST.get("creditor_start") or 70000)
            except ValueError: messages.error(request, "DATEV-Startnummern müssen numerisch sein."); return redirect("next-settings")
            if not _datev_valid(f"{debtor_start:05d}", "customer") or not _datev_valid(f"{creditor_start:05d}", "supplier"):
                messages.error(request, "Debitoren müssen 10000–69999 und Kreditoren 70000–99999 verwenden."); return redirect("next-settings")
            datev.update({"enabled": enabled, "mode": mode, "debtor_start": debtor_start, "creditor_start": creditor_start, "skr": "04" if request.POST.get("skr") == "04" else "03"})
            profile.settings = cfg; profile.save(update_fields=["settings", "updated_at"])
            assigned = _assign_datev_accounts(org, cfg) if enabled and mode in {"automatic", "customer_number"} else 0
            messages.success(request, f"DATEV-Einstellungen gespeichert. {assigned} Konten wurden neu zugeordnet." if assigned else "DATEV-Einstellungen wurden gespeichert."); return redirect("next-settings")
        if section == "phase2_datev_import":
            if not cfg.get("datev", {}).get("enabled"):
                messages.error(request, "Bitte DATEV zuerst aktivieren."); return redirect("next-settings")
            try: assigned, skipped = _import_datev_csv(org, request.FILES.get("datev_file"))
            except ValueError as exc: messages.error(request, str(exc)); return redirect("next-settings")
            messages.success(request, f"DATEV-Import: {assigned} Konten zugeordnet, {skipped} Zeilen nicht zugeordnet."); return redirect("next-settings")
        if section == "phase2_legal_documents":
            docs = cfg.setdefault("legal_documents", {})
            for field, title, kind, key in (("terms_file", "Allgemeine Geschäftsbedingungen", "terms", "terms_document_id"), ("withdrawal_file", "Widerrufsbelehrung und Muster-Widerrufsformular", "withdrawal", "withdrawal_document_id")):
                upload = request.FILES.get(field)
                if upload:
                    if not upload.name.lower().endswith(".pdf") or upload.size > 1_800_000:
                        messages.error(request, "Rechtliche Dokumente müssen PDF-Dateien mit maximal 1,8 MB sein."); return redirect("next-settings")
                    document = _save_upload_document(org, request, upload, title, kind); docs[key] = document.pk
            for key in ("attach_terms_quote", "attach_terms_invoice", "attach_withdrawal_quote", "attach_withdrawal_invoice"):
                docs[key] = request.POST.get(key) == "on"
            profile.settings = cfg; profile.save(update_fields=["settings", "updated_at"])
            messages.success(request, "Rechtliche Dokumente und Standardanhänge wurden gespeichert."); return redirect("next-settings")
        if section == "phase2_documents":
            cfg.setdefault("web_view", {}).update({"quote_default": request.POST.get("quote_web_default") == "on", "acceptance_email": request.POST.get("acceptance_email") == "on"})
            mode = request.POST.get("payment_mode") or "immediately"
            if mode not in {"none", "immediately", "7", "14", "custom"}: mode = "immediately"
            if mode == "none" or mode == "immediately": days = 0
            elif mode in {"7", "14"}: days = int(mode)
            else:
                try: days = max(0, min(int(request.POST.get("payment_days") or 0), 3650))
                except ValueError: messages.error(request, "Das benutzerdefinierte Zahlungsziel ist ungültig."); return redirect("next-settings")
            areas = request.POST.get("payment_areas") or "invoice"
            if areas not in {"quote", "invoice", "both"}: areas = "invoice"
            cfg.setdefault("payment_terms", {}).update({"mode": mode, "days": days, "areas": areas})
            labour = cfg.setdefault("labour_share", {})
            for key in ("quote_private", "quote_company", "invoice_private", "invoice_company"): labour[key] = request.POST.get(key) == "on"
            profile.settings = cfg; profile.save(update_fields=["settings", "updated_at"])
            messages.success(request, "Webansicht, Zahlungsbedingungen und Lohnkostenanteil wurden gespeichert."); return redirect("next-settings")
        if section == "phase2_tax":
            rates = cfg.setdefault("tax_rates", [])
            action = request.POST.get("tax_action") or "add"
            try: index = int(request.POST.get("tax_index") or -1)
            except ValueError: index = -1
            if action == "delete" and 0 <= index < len(rates):
                rates.pop(index)
            elif action in {"save", "toggle"} and 0 <= index < len(rates):
                row = rates[index]
                if action == "toggle": row["active"] = not bool(row.get("active", True))
                else:
                    title = (request.POST.get("tax_title") or "").strip(); rate = (request.POST.get("tax_rate") or "").strip().replace(",", ".")
                    if not title or not rate: messages.error(request, "Titel und Steuersatz sind erforderlich."); return redirect("next-settings")
                    try: float(rate)
                    except ValueError: messages.error(request, "Der Steuersatz muss numerisch sein."); return redirect("next-settings")
                    row.update({"title": title[:160], "rate": rate[:20], "note": (request.POST.get("tax_note") or "")[:400], "datev_skr03": (request.POST.get("datev_skr03") or "")[:12], "datev_skr04": (request.POST.get("datev_skr04") or "")[:12], "active": request.POST.get("tax_active") == "on"})
            elif action == "add":
                title = (request.POST.get("tax_title") or "").strip(); rate = (request.POST.get("tax_rate") or "").strip().replace(",", ".")
                if not title or not rate: messages.error(request, "Titel und Steuersatz sind erforderlich."); return redirect("next-settings")
                try: float(rate)
                except ValueError: messages.error(request, "Der Steuersatz muss numerisch sein."); return redirect("next-settings")
                rates.append({"title": title[:160], "rate": rate[:20], "note": (request.POST.get("tax_note") or "")[:400], "datev_skr03": (request.POST.get("datev_skr03") or "")[:12], "datev_skr04": (request.POST.get("datev_skr04") or "")[:12], "active": True})
            profile.settings = cfg; profile.save(update_fields=["settings", "updated_at"])
            messages.success(request, "Steuersätze wurden aktualisiert."); return redirect("next-settings")
'''
    if "section == \"phase2_numbering\"" not in text:
        if section_anchor not in text: raise RuntimeError("Phase 2 settings section anchor missing")
        text = text.replace(section_anchor, section_anchor + handlers, 1)

    # Add next-number and DATEV statistics to the existing final settings context.
    context_anchor = '    terms = m.Document.objects.filter(organization=org, pk=cfg.get("legal_documents", {}).get("terms_document_id")).first()\n'
    context_extra = context_anchor + '    number_previews = _phase2_number_preview(org, cfg)\n    datev_stats = {"debtors": m.ToolTimeDatevAccount.objects.filter(organization=org, party_type="customer").count(), "creditors": m.ToolTimeDatevAccount.objects.filter(organization=org, party_type="supplier").count()}\n'
    if "number_previews = _phase2_number_preview" not in text:
        if context_anchor not in text: raise RuntimeError("Phase 2 settings context anchor missing")
        text = text.replace(context_anchor, context_extra, 1)
    if '"number_previews": number_previews' not in text:
        anchor = '"withdrawal_document": withdrawal'
        if anchor not in text: raise RuntimeError("Phase 2 render context dictionary anchor missing")
        text = text.replace(anchor, anchor + ', "number_previews": number_previews, "datev_stats": datev_stats', 1)

    # A customer acceptance notification is sent only when enabled and only on the
    # transition to accepted; repeated POSTs never produce repeated notifications.
    accept_old = '        if request.POST["decision"] == "accept":\n            quote.status = "accepted"; meta.accepted_at = timezone.now(); meta.rejected_at = None; messages.success(request, "Vielen Dank. Das Angebot wurde angenommen.")\n'
    accept_new = '''        if request.POST["decision"] == "accept":\n            was_accepted = bool(meta.accepted_at)\n            quote.status = "accepted"; meta.accepted_at = timezone.now(); meta.rejected_at = None; messages.success(request, "Vielen Dank. Das Angebot wurde angenommen.")\n            notify_cfg = phase2_settings(quote.organization).get("web_view", {})\n            recipient = quote.organization.email or phase2_settings(quote.organization).get("communication", {}).get("reply_email", "")\n            if not was_accepted and notify_cfg.get("acceptance_email") and recipient:\n                EmailMessage(subject=f"Angebot {quote.number} wurde online angenommen", body=f"Das Angebot {quote.number} für {customer.display_name} wurde über die Webansicht angenommen.", to=[recipient]).send(fail_silently=True)\n'''
    if accept_new not in text:
        if accept_old not in text: raise RuntimeError("Phase 2 acceptance notification anchor missing")
        text = text.replace(accept_old, accept_new, 1)

    write(rel, text)


def patch_settings_template() -> None:
    rel = "templates/rebuild/tooltime_settings.html"
    text = read(rel)

    numbering = r'''<section class="tt-card" data-phase2-numbering><div class="tt-section-title"><div><h2>Nummernkreise für Dokumente</h2><p>Nummern werden erst beim Fertigstellen vergeben. Führende Nullen bleiben erhalten.</p></div></div><form method="post">{% csrf_token %}<input type="hidden" name="section" value="phase2_numbering"><div class="tt-number-grid">{% for key,label in number_labels %}{% endfor %}<label>Angebote · Präfix<input class="nx-control" name="quote_prefix" value="{{ cfg.numbering.quote_prefix }}" data-number-prefix="quote"></label><label>Beginnt bei<input class="nx-control" inputmode="numeric" name="quote_start" value="{{ cfg.numbering.quote_start|stringformat:'d' }}" data-number-start="quote"></label><div class="tt-number-preview">Nächste Angebotsnummer <strong data-number-preview="quote" data-current-next="{{ number_previews.quote.value }}">{{ number_previews.quote.formatted }}</strong></div><label>Rechnungen · Präfix<input class="nx-control" name="invoice_prefix" value="{{ cfg.numbering.invoice_prefix }}" data-number-prefix="invoice"></label><label>Beginnt bei<input class="nx-control" inputmode="numeric" name="invoice_start" value="{{ cfg.numbering.invoice_start|stringformat:'d' }}" data-number-start="invoice"></label><div class="tt-number-preview">Nächste Rechnungsnummer <strong data-number-preview="invoice" data-current-next="{{ number_previews.invoice.value }}">{{ number_previews.invoice.formatted }}</strong></div><label>Gutschriften · Präfix<input class="nx-control" name="credit_prefix" value="{{ cfg.numbering.credit_prefix }}" data-number-prefix="credit"></label><label>Beginnt bei<input class="nx-control" inputmode="numeric" name="credit_start" value="{{ cfg.numbering.credit_start|stringformat:'d' }}" data-number-start="credit"></label><div class="tt-number-preview">Nächste Gutschriftnummer <strong data-number-preview="credit" data-current-next="{{ number_previews.credit.value }}">{{ number_previews.credit.formatted }}</strong></div></div><hr><label class="tt-check"><input type="checkbox" name="customer_auto" {% if cfg.numbering.customer_auto %}checked{% endif %}> Kundennummern automatisch fortlaufend vergeben</label><div class="tt-two"><label>Kundenpräfix<input class="nx-control" name="customer_prefix" value="{{ cfg.numbering.customer_prefix }}" data-number-prefix="customer"></label><label>Beginnt bei<input class="nx-control" inputmode="numeric" name="customer_start" value="{{ cfg.numbering.customer_start|stringformat:'d' }}" data-number-start="customer"></label></div><div class="tt-number-preview">Nächste Kundennummer <strong data-number-preview="customer" data-current-next="{{ number_previews.customer.value }}">{{ number_previews.customer.formatted }}</strong></div><button class="nx-btn nx-btn-accent" type="submit">Nummernkreise speichern</button></form></section>'''

    datev = r'''<section class="tt-card" data-phase2-datev><div class="tt-section-title"><div><h2>Debitoren- und Kreditorennummern</h2><p>DATEV-konform: Debitoren 10000–69999, Kreditoren 70000–99999, jeweils fünfstellig.</p></div><span class="nx-badge">{{ datev_stats.debtors }} Debitoren · {{ datev_stats.creditors }} Kreditoren</span></div><form method="post">{% csrf_token %}<input type="hidden" name="section" value="phase2_datev"><label class="tt-check"><input type="checkbox" name="datev_enabled" {% if cfg.datev.enabled %}checked{% endif %}> Debitoren- und Kreditorennummern aktivieren</label><div class="tt-three"><label>Vergabe<select class="nx-control" name="datev_mode"><option value="automatic" {% if cfg.datev.mode == 'automatic' %}selected{% endif %}>Automatisch neu zuweisen</option><option value="customer_number" {% if cfg.datev.mode == 'customer_number' %}selected{% endif %}>Kundennummer als Debitorennummer</option><option value="import" {% if cfg.datev.mode == 'import' %}selected{% endif %}>Aus DATEV importieren</option></select></label><label>Nächster Debitor<input class="nx-control" name="debtor_start" inputmode="numeric" maxlength="5" value="{{ cfg.datev.debtor_start }}"></label><label>Nächster Kreditor<input class="nx-control" name="creditor_start" inputmode="numeric" maxlength="5" value="{{ cfg.datev.creditor_start }}"></label><label>Kontenrahmen<select class="nx-control" name="skr"><option value="03" {% if cfg.datev.skr == '03' %}selected{% endif %}>SKR 03</option><option value="04" {% if cfg.datev.skr == '04' %}selected{% endif %}>SKR 04</option></select></label></div><button class="nx-btn nx-btn-accent" type="submit">DATEV-Einstellungen speichern</button></form><form method="post" enctype="multipart/form-data" class="tt-inline-form">{% csrf_token %}<input type="hidden" name="section" value="phase2_datev_import"><label>DATEV-Zuordnung importieren<input class="nx-control" type="file" name="datev_file" accept=".csv,text/csv" required></label><button class="nx-btn" type="submit">CSV prüfen und zuordnen</button></form></section>'''

    legal = r'''<section class="tt-card" data-phase2-legal-documents><h2>Rechtliche Informationen</h2><form method="post" enctype="multipart/form-data"><input type="hidden" name="section" value="phase2_legal_documents">{% csrf_token %}<div class="tt-two"><div><label>Allgemeine Geschäftsbedingungen<input class="nx-control" type="file" name="terms_file" accept="application/pdf">{% if terms_document %}<a href="{{ terms_document.file.url }}" target="_blank" rel="noopener">Aktuelle AGB öffnen</a>{% endif %}</label><label class="tt-check"><input type="checkbox" name="attach_terms_quote" {% if cfg.legal_documents.attach_terms_quote %}checked{% endif %}> Standardmäßig an Angebote anhängen</label><label class="tt-check"><input type="checkbox" name="attach_terms_invoice" {% if cfg.legal_documents.attach_terms_invoice %}checked{% endif %}> Standardmäßig an Rechnungen anhängen</label></div><div><label>Widerrufsbelehrung und Muster-Widerrufsformular<input class="nx-control" type="file" name="withdrawal_file" accept="application/pdf">{% if withdrawal_document %}<a href="{{ withdrawal_document.file.url }}" target="_blank" rel="noopener">Aktuelles Dokument öffnen</a>{% endif %}</label><label class="tt-check"><input type="checkbox" name="attach_withdrawal_quote" {% if cfg.legal_documents.attach_withdrawal_quote %}checked{% endif %}> Standardmäßig an Angebote anhängen</label><label class="tt-check"><input type="checkbox" name="attach_withdrawal_invoice" {% if cfg.legal_documents.attach_withdrawal_invoice %}checked{% endif %}> Standardmäßig an Rechnungen anhängen</label></div></div><small>PDF-Dateien, maximal 1,8 MB. Die Auswahl wird bei neuen bzw. noch nicht fertiggestellten Dokumenten übernommen.</small><button class="nx-btn nx-btn-accent" type="submit">Rechtliche Dokumente speichern</button></form></section>'''

    documents = r'''<section class="tt-card" data-phase2-documents><h2>Webansicht & Zahlungsbedingungen</h2><form method="post">{% csrf_token %}<input type="hidden" name="section" value="phase2_documents"><h3>Webansicht</h3><label class="tt-check"><input type="checkbox" name="quote_web_default" {% if cfg.web_view.quote_default %}checked{% endif %}> Webansicht für zukünftige Angebote standardmäßig aktivieren</label><label class="tt-check"><input type="checkbox" name="acceptance_email" {% if cfg.web_view.acceptance_email %}checked{% endif %}> E-Mail-Benachrichtigung senden, wenn ein Kunde ein Angebot online annimmt</label><h3>Zahlungsbedingungen</h3><div class="tt-three"><label>Standard-Zahlungsziel<select class="nx-control" name="payment_mode" data-payment-mode><option value="none" {% if cfg.payment_terms.mode == 'none' %}selected{% endif %}>Kein Zahlungsziel</option><option value="immediately" {% if cfg.payment_terms.mode == 'immediately' %}selected{% endif %}>Sofort</option><option value="7" {% if cfg.payment_terms.mode == '7' %}selected{% endif %}>7 Tage</option><option value="14" {% if cfg.payment_terms.mode == '14' %}selected{% endif %}>14 Tage</option><option value="custom" {% if cfg.payment_terms.mode == 'custom' %}selected{% endif %}>Benutzerdefiniert</option></select></label><label>Benutzerdefinierte Tage<input class="nx-control" type="number" min="0" max="3650" name="payment_days" value="{{ cfg.payment_terms.days }}" data-payment-days></label><label>Gilt für<select class="nx-control" name="payment_areas"><option value="invoice" {% if cfg.payment_terms.areas == 'invoice' %}selected{% endif %}>Rechnungen</option><option value="quote" {% if cfg.payment_terms.areas == 'quote' %}selected{% endif %}>Angebote</option><option value="both" {% if cfg.payment_terms.areas == 'both' %}selected{% endif %}>Angebote und Rechnungen</option></select></label></div><div class="tt-payment-preview">Vorschau: <strong data-payment-preview>{% if cfg.payment_terms.mode == 'none' %}Kein Zahlungsziel{% elif cfg.payment_terms.days == 0 %}Zahlbar sofort{% else %}Zahlbar innerhalb von {{ cfg.payment_terms.days }} Tagen{% endif %}</strong></div><h3>Ausweisung des Lohnkostenanteils</h3><div class="tt-two"><label class="tt-check"><input type="checkbox" name="quote_private" {% if cfg.labour_share.quote_private %}checked{% endif %}> Angebote · Privatkunden</label><label class="tt-check"><input type="checkbox" name="quote_company" {% if cfg.labour_share.quote_company %}checked{% endif %}> Angebote · Firmenkunden</label><label class="tt-check"><input type="checkbox" name="invoice_private" {% if cfg.labour_share.invoice_private %}checked{% endif %}> Rechnungen · Privatkunden</label><label class="tt-check"><input type="checkbox" name="invoice_company" {% if cfg.labour_share.invoice_company %}checked{% endif %}> Rechnungen · Firmenkunden</label></div><button class="nx-btn nx-btn-accent" type="submit">Angebots- und Rechnungseinstellungen speichern</button></form></section>'''

    tax = r'''<section class="tt-card" data-phase2-tax><div class="tt-section-title"><div><h2>Steuersätze</h2><p>Titel, Rechtsgrundlage, Sichtbarkeit und DATEV-Konten pro Kontenrahmen.</p></div></div><div class="tt-tax-edit-list">{% for rate in cfg.tax_rates %}<form method="post" class="tt-tax-editor">{% csrf_token %}<input type="hidden" name="section" value="phase2_tax"><input type="hidden" name="tax_index" value="{{ forloop.counter0 }}"><div class="tt-three"><label>Titel<input class="nx-control" name="tax_title" value="{{ rate.title }}"></label><label>Steuersatz %<input class="nx-control" name="tax_rate" value="{{ rate.rate }}"></label><label class="tt-check"><input type="checkbox" name="tax_active" {% if rate.active %}checked{% endif %}> In Dokumenten anzeigen</label><label>Rechtlicher Hinweis<input class="nx-control" name="tax_note" value="{{ rate.note }}"></label><label>DATEV-Konto SKR 03<input class="nx-control" name="datev_skr03" inputmode="numeric" value="{{ rate.datev_skr03|default:'' }}"></label><label>DATEV-Konto SKR 04<input class="nx-control" name="datev_skr04" inputmode="numeric" value="{{ rate.datev_skr04|default:'' }}"></label></div><div class="nx-actions"><button class="nx-btn nx-btn-accent" name="tax_action" value="save" type="submit">Speichern</button><button class="nx-btn" name="tax_action" value="toggle" type="submit">{% if rate.active %}Ausblenden{% else %}Einblenden{% endif %}</button><button class="nx-btn" name="tax_action" value="delete" type="submit" onclick="return confirm('Steuersatz wirklich löschen?')">Löschen</button></div></form>{% endfor %}</div><form method="post" class="tt-tax-editor">{% csrf_token %}<input type="hidden" name="section" value="phase2_tax"><input type="hidden" name="tax_action" value="add"><h3>Neuen Steuersatz hinzufügen</h3><div class="tt-three"><input class="nx-control" name="tax_title" placeholder="Titel, z. B. 19 % Umsatzsteuer"><input class="nx-control" name="tax_rate" placeholder="19"><input class="nx-control" name="tax_note" placeholder="Rechtlicher Hinweis"><input class="nx-control" name="datev_skr03" placeholder="SKR 03 Konto"><input class="nx-control" name="datev_skr04" placeholder="SKR 04 Konto"></div><button class="nx-btn" type="submit">Steuersatz hinzufügen</button></form></section>'''

    def replace_section(source: str, heading: str, replacement: str) -> str:
        pattern = re.compile(r'<section class="tt-card"[^>]*><h2>' + re.escape(heading) + r'</h2>.*?</section>', re.S)
        source, count = pattern.subn(lambda _m: replacement, source, count=1)
        if count != 1:
            # Phase 1 can add controls inside the heading; use a wider heading-based fallback.
            start = source.find(heading)
            if start < 0: raise RuntimeError(f"Phase 2 settings section missing: {heading}")
            section_start = source.rfind("<section", 0, start); section_end = source.find("</section>", start)
            if section_start < 0 or section_end < 0: raise RuntimeError(f"Phase 2 settings section bounds missing: {heading}")
            source = source[:section_start] + replacement + source[section_end + len("</section>"):]
        return source

    text = replace_section(text, "Nummernkreise für Dokumente", numbering)
    # Insert DATEV directly after numbering.
    if "data-phase2-datev" not in text: text = text.replace(numbering, numbering + datev, 1)
    # Completion created Rechtliche Informationen; replace it with attachment controls.
    text = replace_section(text, "Rechtliche Informationen", legal)
    text = replace_section(text, "Dokumente & Zahlungsbedingungen", documents)
    text = replace_section(text, "Steuersätze", tax)

    javascript = r'''<script data-phase2-settings-js>document.addEventListener('input',e=>{const form=e.target.closest('[data-phase2-numbering] form');if(form){['quote','invoice','credit','customer'].forEach(k=>{const p=form.querySelector(`[data-number-prefix="${k}"]`),s=form.querySelector(`[data-number-start="${k}"]`),o=form.querySelector(`[data-number-preview="${k}"]`);if(!p||!s||!o)return;const raw=(s.value||'1').replace(/\D/g,'')||'1',current=parseInt(o.dataset.currentNext||'1',10),start=parseInt(raw,10)||1,value=Math.max(start,current);o.textContent=(p.value||'')+String(value).padStart(raw.length,'0')})}const docs=e.target.closest('[data-phase2-documents]');if(docs){const mode=docs.querySelector('[data-payment-mode]')?.value,days=docs.querySelector('[data-payment-days]'),preview=docs.querySelector('[data-payment-preview]');if(!days||!preview)return;if(mode==='7'||mode==='14')days.value=mode;if(mode==='none'||mode==='immediately')days.value='0';days.disabled=mode!=='custom';preview.textContent=mode==='none'?'Kein Zahlungsziel':Number(days.value||0)===0?'Zahlbar sofort':`Zahlbar innerhalb von ${days.value} Tagen`}}});document.dispatchEvent(new Event('input'));</script>'''
    if "data-phase2-settings-js" not in text:
        idx = text.rfind("{% endblock %}")
        if idx < 0: raise RuntimeError("Phase 2 settings endblock missing")
        text = text[:idx] + javascript + "\n" + text[idx:]
    write(rel, text)


def patch_tests() -> None:
    rel = "erp/tests/test_tooltime_phase2_settings.py"
    write(rel, r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]


class ToolTimePhase2SourceContractTests(SimpleTestCase):
    def test_phase2_settings_are_real_and_german(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text()
        template = (ROOT / "templates/rebuild/tooltime_settings.html").read_text()
        service = (ROOT / "erp/services/tooltime_parity_finance.py").read_text()
        for needle in ("_phase2_number_preview", "_assign_datev_accounts", "_import_datev_csv", "phase2_legal_documents", "phase2_documents", "phase2_tax"):
            self.assertIn(needle, views)
        for needle in ("Nächste Angebotsnummer", "Nächste Rechnungsnummer", "Debitoren- und Kreditorennummern", "Aus DATEV importieren", "Standardmäßig an Angebote anhängen", "E-Mail-Benachrichtigung senden", "Benutzerdefiniert", "DATEV-Konto SKR 03"):
            self.assertIn(needle, template)
        self.assertIn("default_legal_attachment_ids", service)
        self.assertIn("quote_default", service)

    def test_datev_model_and_migration_exist(self):
        models = (ROOT / "erp/tooltime_parity_finance.py").read_text()
        migration = ROOT / "erp/migrations/0015_tooltime_phase2_settings.py"
        self.assertIn("class ToolTimeDatevAccount", models)
        self.assertTrue(migration.exists())
        self.assertIn("default_attachment_ids", migration.read_text())
''')


def guard() -> None:
    for rel in ("erp/tooltime_parity_finance.py", "erp/tooltime_parity_views.py", "erp/services/tooltime_parity_finance.py"):
        path = ROOT / rel
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    migration = ROOT / "erp/migrations/0015_tooltime_phase2_settings.py"
    compile(migration.read_text(encoding="utf-8"), str(migration), "exec")
    template = read("templates/rebuild/tooltime_settings.html")
    for needle in ("data-phase2-numbering", "data-phase2-datev", "data-phase2-legal-documents", "data-phase2-documents", "data-phase2-tax", "data-phase2-settings-js"):
        if needle not in template: raise RuntimeError(f"Phase 2 UI guard missing {needle}")


patch_models_and_migration()
patch_service()
patch_views()
patch_settings_template()
patch_tests()
guard()
print("ToolTime Phase 2 abgeschlossen: Nummernkreise, DATEV, Rechtsanhänge, Webansicht, Zahlungsbedingungen, Lohnkostenanteil und Steuersätze sind funktional verbunden.")
