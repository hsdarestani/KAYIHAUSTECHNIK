from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rw(rel):
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"PDF-Layout-Brücke: Datei fehlt: {rel}")
    return path, path.read_text(encoding="utf-8")


def patch_settings_bridge():
    path, text = rw("erp/tooltime_parity_views.py")
    old = '''            cfg["footer"].update({"show": request.POST.get("footer_show") == "on", "mode": request.POST.get("footer_mode") or "standard", "columns": columns})
        elif section == "numbering":
'''
    new = '''            cfg["footer"].update({"show": request.POST.get("footer_show") == "on", "mode": request.POST.get("footer_mode") or "standard", "columns": columns})
            org_settings = org.settings if isinstance(org.settings, dict) else {}
            org_settings["document_layout"] = {
                "logo": cfg.get("logo", {}),
                "letterhead": cfg.get("letterhead", {}),
                "sender_line": cfg.get("sender_line", {}),
                "footer": cfg.get("footer", {}),
            }
            if letterhead:
                org_settings["document_layout"]["letterhead"]["url"] = doc.file.url
            org.settings = org_settings
            org.save(update_fields=["settings", "updated_at"])
        elif section == "numbering":
'''
    if old not in text:
        raise RuntimeError("PDF-Layout-Brücke: Layout-Speicheranker fehlt.")
    text = text.replace(old, new, 1)
    old_legal = '''            legal = settings.get("invoice_legal") if isinstance(settings.get("invoice_legal"), dict) else {}
            for field in ("vat_id", "website", "bic", "bank_name", "register_court", "register_number", "managing_director", "legal_form", "mobile"):
                legal[field] = (request.POST.get(field) or "").strip()
            settings["invoice_legal"] = legal
'''
    new_legal = '''            legal = settings.get("legal") if isinstance(settings.get("legal"), dict) else {}
            for field in ("vat_id", "website", "bic", "bank_name", "register_court", "register_number", "managing_director", "legal_form", "mobile"):
                legal[field] = (request.POST.get(field) or "").strip()
            legal["tax_number"] = org.tax_id
            legal["street"] = org.address
            settings["legal"] = legal
            settings["invoice_legal"] = legal
'''
    if old_legal not in text:
        raise RuntimeError("PDF-Layout-Brücke: Rechtsangaben-Anker fehlt.")
    text = text.replace(old_legal, new_legal, 1)
    text = text.replace(
        'legal = (org.settings or {}).get("invoice_legal", {}) if isinstance(org.settings, dict) else {}',
        'legal = (org.settings or {}).get("legal", {}) if isinstance(org.settings, dict) else {}',
        1,
    )
    path.write_text(text, encoding="utf-8")


def patch_pdf_helper():
    path, text = rw("erp/services/business_pdf_identity.py")
    text = text.replace(
        '"tax_number": _first(org, "tax_number", "steuer_number", "steuernummer"),',
        '"tax_number": _first(org, "tax_number", "tax_id", "steuer_number", "steuernummer"),',
        1,
    )
    old_footer = '''def legal_footer_html(org):
    d = business_identity(org)
    address = " · ".join(part for part in (d["street"], d["city_line"], d["country"]) if part)
    tax = " · ".join(part for part in (f"Steuernr. {d['tax_number']}" if d['tax_number'] else "", f"USt-IdNr. {d['vat_id']}" if d['vat_id'] else "") if part)
    register = " · ".join(part for part in (f"{d['register_court']} {d['register']}".strip() if d['register'] else "", f"Geschäftsführung: {d['managing_director']}" if d['managing_director'] else "") if part)
    bank = " · ".join(part for part in (d["bank"], f"IBAN {d['iban']}" if d['iban'] else "", f"BIC {d['bic']}" if d['bic'] else "") if part)
    lines = [address, tax, register, bank]
    return '<div class="kayi-legal-footer">' + ''.join(f'<div>{_e(line)}</div>' for line in lines if line) + '</div>'
'''
    new_footer = '''def legal_footer_html(org):
    d = business_identity(org)
    address = " · ".join(part for part in (d["street"], d["city_line"], d["country"]) if part)
    tax = " · ".join(part for part in (f"Steuernr. {d['tax_number']}" if d['tax_number'] else "", f"USt-IdNr. {d['vat_id']}" if d['vat_id'] else "") if part)
    register = " · ".join(part for part in (f"{d['register_court']} {d['register']}".strip() if d['register'] else "", f"Geschäftsführung: {d['managing_director']}" if d['managing_director'] else "") if part)
    bank = " · ".join(part for part in (d["bank"], f"IBAN {d['iban']}" if d['iban'] else "", f"BIC {d['bic']}" if d['bic'] else "") if part)
    lines = [address, tax, register, bank]
    mandatory = '<div class="kayi-legal-footer">' + ''.join(f'<div>{_e(line)}</div>' for line in lines if line) + '</div>'
    layout = _settings(org).get("document_layout") if isinstance(_settings(org).get("document_layout"), dict) else {}
    footer = layout.get("footer") if isinstance(layout.get("footer"), dict) else {}
    if not footer.get("show", True):
        return mandatory
    if footer.get("mode") != "custom" or not footer.get("columns"):
        return mandatory
    columns = []
    for column in footer.get("columns", [])[:4]:
        if not isinstance(column, dict):
            continue
        heading = _e(column.get("heading", ""))
        body = "".join(f"<div>{_e(line)}</div>" for line in (column.get("lines") or [])[:6])
        align = column.get("align") if column.get("align") in {"left", "center", "right"} else "left"
        columns.append(f'<div style="text-align:{align}"><b>{heading}</b>{body}</div>')
    return mandatory + '<div class="kayi-custom-footer">' + ''.join(columns) + '</div>'
'''
    if old_footer not in text:
        raise RuntimeError("PDF-Layout-Brücke: Footer-Anker fehlt.")
    text = text.replace(old_footer, new_footer, 1)

    old_header = '''    identity = business_identity(org)
    contact = " · ".join(part for part in (identity["email"], identity["phone"], identity["website"]) if part)
    header = f'''<!-- KAYI_BUSINESS_PDF_IDENTITY_20260820 --><div class="kayi-business-header"><b>{_e(identity['name'])}</b><span>{_e(contact)}</span></div>{document_reference_html(document, document_kind)}'''
'''
    # The helper itself contains triple-quoted f-string syntax; patch through simpler anchors.
    simple = '    identity = business_identity(org)\n    contact = " · ".join(part for part in (identity["email"], identity["phone"], identity["website"]) if part)\n'
    enriched = '''    identity = business_identity(org)
    contact = " · ".join(part for part in (identity["email"], identity["phone"], identity["website"]) if part)
    layout = _settings(org).get("document_layout") if isinstance(_settings(org).get("document_layout"), dict) else {}
    logo_cfg = layout.get("logo") if isinstance(layout.get("logo"), dict) else {}
    logo_html = ""
    try:
        if logo_cfg.get("show", True) and getattr(org, "logo", None) and org.logo.name:
            position = logo_cfg.get("position") if logo_cfg.get("position") in {"left", "center", "right"} else "right"
            widths = {"small": 70, "medium": 110, "large": 150}
            width = widths.get(logo_cfg.get("size"), 150)
            logo_html = f'<div class="kayi-document-logo" style="text-align:{position}"><img src="{_e(org.logo.url)}" style="max-width:{width}px;max-height:80px"></div>'
    except Exception:
        logo_html = ""
    letterhead = layout.get("letterhead") if isinstance(layout.get("letterhead"), dict) else {}
    letterhead_html = f'<div class="kayi-letterhead"><img src="{_e(letterhead.get("url"))}"></div>' if letterhead.get("show") and letterhead.get("url") else ""
'''
    if simple not in text:
        raise RuntimeError("PDF-Layout-Brücke: Header-Anker fehlt.")
    text = text.replace(simple, enriched, 1)
    text = text.replace(
        "header = f'''<!-- KAYI_BUSINESS_PDF_IDENTITY_20260820 --><div class=\"kayi-business-header\"><b>{_e(identity['name'])}</b><span>{_e(contact)}</span></div>{document_reference_html(document, document_kind)}'''",
        "header = f'''<!-- KAYI_BUSINESS_PDF_IDENTITY_20260820 -->{letterhead_html}{logo_html}<div class=\"kayi-business-header\"><b>{_e(identity['name'])}</b><span>{_e(contact)}</span></div>{document_reference_html(document, document_kind)}'''",
        1,
    )
    text = text.replace(
        ".kayi-legal-footer{border-top:1px solid #dfe5e7;margin-top:7px;padding-top:6px;font-size:7.5px;line-height:1.35;color:#68737a;display:grid;gap:2px}",
        ".kayi-legal-footer{border-top:1px solid #dfe5e7;margin-top:7px;padding-top:6px;font-size:7.5px;line-height:1.35;color:#68737a;display:grid;gap:2px}.kayi-custom-footer{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:6px;font-size:7.5px;color:#68737a}.kayi-custom-footer b{display:block;margin-bottom:2px}.kayi-letterhead img{width:100%;max-height:80px;object-fit:contain}.kayi-document-logo{margin-bottom:6px}",
        1,
    )
    path.write_text(text, encoding="utf-8")


def patch_tests():
    path, text = rw("tests/test_tooltime_finance_parity_batch.py")
    anchor = "    def test_guided_invoice_wizard_exists(self):\n"
    test = '''    def test_legal_settings_reach_pdf_helper(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text()
        helper = (ROOT / "erp/services/business_pdf_identity.py").read_text()
        self.assertIn('settings["legal"] = legal', views)
        self.assertIn('"tax_id"', helper)
        self.assertIn("kayi-custom-footer", helper)
        self.assertIn("kayi-document-logo", helper)

'''
    if test not in text:
        if anchor not in text:
            raise RuntimeError("PDF-Layout-Brücke: Test-Anker fehlt.")
        text = text.replace(anchor, test + anchor, 1)
    path.write_text(text, encoding="utf-8")


def run():
    patch_settings_bridge(); patch_pdf_helper(); patch_tests()
    print("ToolTime-Layout und Rechtsangaben sind mit der PDF-Ausgabe verbunden.")


if __name__ == "__main__":
    run()
