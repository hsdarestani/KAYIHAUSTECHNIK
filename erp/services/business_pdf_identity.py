from __future__ import annotations

import base64

import html
from datetime import date, datetime


def _settings(org):
    raw = getattr(org, "settings", None)
    return raw if isinstance(raw, dict) else {}


def _first(org, *keys, default=""):
    settings = _settings(org)
    for key in keys:
        value = getattr(org, key, None)
        if value not in (None, ""):
            return str(value).strip()
        value = settings.get(key)
        if value not in (None, ""):
            return str(value).strip()
    legal = settings.get("legal") if isinstance(settings.get("legal"), dict) else {}
    for key in keys:
        value = legal.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return default



def _file_data_uri(field):
    # PDF generation must not depend on public MEDIA_URL/reverse-proxy reachability.
    try:
        name = str(getattr(field, "name", "") or "")
        if not name:
            return ""
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext)
        if not mime:
            return ""
        field.open("rb")
        try:
            payload = field.read()
        finally:
            field.close()
        if not payload:
            return ""
        encoded = base64.b64encode(payload).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    except Exception:
        return ""


def business_identity(org):
    street = _first(org, "street", "address_street", "company_street")
    house = _first(org, "house_number", "street_number", "address_number")
    postal = _first(org, "postal_code", "zip", "zipcode", "address_zip")
    city = _first(org, "city", "address_city")
    country = _first(org, "country", "address_country", default="Deutschland")
    return {
        "name": _first(org, "legal_name", "company_name", "name", default="A+Bau"),
        "street": " ".join(part for part in (street, house) if part),
        "city_line": " ".join(part for part in (postal, city) if part),
        "country": country,
        "email": _first(org, "email", "company_email"),
        "phone": _first(org, "phone", "company_phone", "telephone"),
        "website": _first(org, "website", "url"),
        "tax_number": _first(org, "tax_number", "tax_id", "steuer_number", "steuernummer"),
        "vat_id": _first(org, "vat_id", "vat_number", "ust_id", "ustid", "umsatzsteuer_id"),
        "register": _first(org, "commercial_register", "register_number", "handelsregister"),
        "register_court": _first(org, "register_court", "amtsgericht"),
        "managing_director": _first(org, "managing_director", "geschaeftsfuehrer", "geschäftsführer", "owner_name"),
        "iban": _first(org, "iban", "bank_iban"),
        "bic": _first(org, "bic", "bank_bic"),
        "bank": _first(org, "bank_name", "bank"),
    }


def _e(value):
    return html.escape(str(value or ""))


def legal_footer_html(org):
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


def document_reference_html(document, document_kind: str):
    if document is None:
        return ""
    number = getattr(document, "number", "") or ""
    issue = getattr(document, "issue_date", None)
    if isinstance(issue, (date, datetime)):
        issue = issue.strftime("%d.%m.%Y")
    label = "Angebotsnummer" if document_kind.lower().startswith("angebot") else "Rechnungsnummer" if document_kind.lower().startswith("rechnung") else "Dokumentnummer"
    parts = [f"{label}: {number}" if number else "", f"Datum: {issue}" if issue else ""]
    return '<div class="kayi-document-reference">' + ' · '.join(_e(part) for part in parts if part) + '</div>'


def inject_business_pdf_identity(source_html: str, *, org, document=None, document_kind="Dokument") -> str:
    if not source_html or "KAYI_BUSINESS_PDF_IDENTITY_20260820" in source_html:
        return source_html
    identity = business_identity(org)
    contact = " · ".join(part for part in (identity["email"], identity["phone"], identity["website"]) if part)
    layout = _settings(org).get("document_layout") if isinstance(_settings(org).get("document_layout"), dict) else {}
    logo_cfg = layout.get("logo") if isinstance(layout.get("logo"), dict) else {}
    logo_html = ""
    try:
        if logo_cfg.get("show", True) and getattr(org, "logo", None) and org.logo.name:
            position = logo_cfg.get("position") if logo_cfg.get("position") in {"left", "center", "right"} else "right"
            widths = {"small": 70, "medium": 110, "large": 150}
            width = widths.get(logo_cfg.get("size"), 150)
            logo_src = _file_data_uri(org.logo)
            if logo_src:
                logo_html = f'<div class="kayi-document-logo" style="text-align:{position}"><img src="{logo_src}" style="max-width:{width}px;max-height:80px"></div>'
    except Exception:
        logo_html = ""
    letterhead = layout.get("letterhead") if isinstance(layout.get("letterhead"), dict) else {}
    letterhead_html = f'<div class="kayi-letterhead"><img src="{_e(letterhead.get("url"))}"></div>' if letterhead.get("show") and letterhead.get("url") else ""
    header = f'''<!-- KAYI_BUSINESS_PDF_IDENTITY_20260820 -->{letterhead_html}{logo_html}<div class="kayi-business-header"><b>{_e(identity['name'])}</b><span>{_e(contact)}</span></div>{document_reference_html(document, document_kind)}'''
    standard = '''<div class="kayi-document-standard"><span>Alle Beträge gemäß ausgewiesener Umsatzsteuer.</span><span>Zahlungs- und Leistungsbedingungen ergeben sich aus dem jeweiligen Dokument und den vereinbarten Vertragsunterlagen.</span></div>'''
    css = '''<style>.kayi-business-header{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;border-bottom:1px solid #dfe5e7;padding:0 0 7px;margin:0 0 10px;font-size:9px}.kayi-business-header b{font-size:13px}.kayi-business-header span{text-align:right;color:#68737a}.kayi-document-reference{font-size:9px;font-weight:700;margin:-4px 0 10px;color:#465158}.kayi-document-standard{border-top:1px solid #e3e7e8;margin-top:10px;padding-top:6px;font-size:7.5px;color:#6d777e;display:grid;gap:2px}.kayi-legal-footer{border-top:1px solid #dfe5e7;margin-top:7px;padding-top:6px;font-size:7.5px;line-height:1.35;color:#68737a;display:grid;gap:2px}.kayi-custom-footer{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:6px;font-size:7.5px;color:#68737a}.kayi-custom-footer b{display:block;margin-bottom:2px}.kayi-letterhead img{width:100%;max-height:80px;object-fit:contain}.kayi-document-logo{margin-bottom:6px}</style>'''
    if "</head>" in source_html:
        source_html = source_html.replace("</head>", css + "</head>", 1)
    if "<body" in source_html:
        source_html = re_sub_body(source_html, header)
    footer = standard + legal_footer_html(org)
    if "</body>" in source_html:
        source_html = source_html.replace("</body>", footer + "</body>", 1)
    else:
        source_html += footer
    return source_html


def re_sub_body(source_html: str, header: str) -> str:
    import re
    return re.sub(r"(<body[^>]*>)", r"\1" + header, source_html, count=1, flags=re.I)
