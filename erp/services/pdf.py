from __future__ import annotations

from io import BytesIO
from decimal import Decimal
from xml.sax.saxutils import escape as xml_escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


def money(value) -> str:
    return f"{Decimal(value):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _header(story, org, title, number):
    styles = getSampleStyleSheet()
    story.append(Paragraph(org.legal_name or org.name, styles["Title"]))
    if org.address:
        story.append(Paragraph(org.address.replace("\n", "<br/>"), styles["Normal"]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(f"{title} {number}", styles["Heading1"]))


def build_quote_pdf(quote) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    right = ParagraphStyle("right", parent=styles["Normal"], alignment=TA_RIGHT)
    story = []
    _header(story, quote.organization, "Angebot", quote.number)
    customer = quote.project.customer
    story.append(Paragraph(f"<b>{customer.display_name}</b><br/>{customer.street}<br/>{customer.postal_code} {customer.city}", styles["Normal"]))
    story.append(Spacer(1, 7 * mm))
    if quote.intro_text:
        story.append(Paragraph(quote.intro_text.replace("\n", "<br/>"), styles["Normal"]))
        story.append(Spacer(1, 5 * mm))
    data = [["Pos.", "Leistung", "Menge", "EP", "Gesamt"]]
    for item in quote.items.all():
        data.append([str(item.position), Paragraph(item.description.replace("\n", "<br/>"), styles["Normal"]), f"{item.quantity} {item.unit}", money(item.unit_price), money(item.net_total)])
    table = Table(data, colWidths=[14 * mm, 86 * mm, 28 * mm, 27 * mm, 27 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172033")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#d8dde8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f7fb")]),
    ]))
    story.extend([table, Spacer(1, 6 * mm)])
    totals = Table([
        ["Netto", money(quote.net_total)],
        ["MwSt.", money(quote.tax_total)],
        [Paragraph("<b>Gesamt</b>", right), Paragraph(f"<b>{money(quote.gross_total)}</b>", right)],
    ], colWidths=[140 * mm, 42 * mm])
    totals.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#c6a15b"))]))
    story.append(totals)
    if quote.outro_text:
        story.extend([Spacer(1, 8 * mm), Paragraph(quote.outro_text.replace("\n", "<br/>"), styles["Normal"])])
    doc.build(story)
    return buffer.getvalue()


def build_invoice_pdf(invoice) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = []
    _header(story, invoice.organization, "Rechnung", invoice.number)
    customer = invoice.project.customer
    story.append(Paragraph(f"<b>{customer.display_name}</b><br/>{customer.street}<br/>{customer.postal_code} {customer.city}", styles["Normal"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Rechnungsdatum: {invoice.issue_date:%d.%m.%Y}<br/>Fällig am: {invoice.due_date:%d.%m.%Y}", styles["Normal"]))
    story.append(Spacer(1, 7 * mm))
    if invoice.intro_text:
        story.append(Paragraph(invoice.intro_text.replace("\n", "<br/>"), styles["Normal"]))
        story.append(Spacer(1, 5 * mm))
    data = [["Pos.", "Leistung", "Menge", "EP", "Gesamt"]]
    for item in invoice.items.all():
        data.append([str(item.position), Paragraph(item.description.replace("\n", "<br/>"), styles["Normal"]), f"{item.quantity} {item.unit}", money(item.unit_price), money(item.net_total)])
    table = Table(data, colWidths=[14 * mm, 86 * mm, 28 * mm, 27 * mm, 27 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172033")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#d8dde8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f7fb")]),
    ]))
    story.extend([table, Spacer(1, 6 * mm)])
    totals = Table([["Netto", money(invoice.net_total)], ["MwSt.", money(invoice.tax_total)], ["Gesamt", money(invoice.gross_total)]], colWidths=[140 * mm, 42 * mm])
    totals.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#c6a15b"))]))
    story.append(totals)
    if invoice.outro_text:
        story.extend([Spacer(1, 8 * mm), Paragraph(invoice.outro_text.replace("\n", "<br/>"), styles["Normal"])])
    doc.build(story)
    return buffer.getvalue()


def _signature_image(data_uri):
    if not data_uri or "," not in data_uri:
        return None
    try:
        import base64
        from reportlab.platypus import Image
        raw = base64.b64decode(data_uri.split(",", 1)[1])
        image = Image(BytesIO(raw), width=55 * mm, height=22 * mm)
        return image
    except Exception:
        return None


def build_change_order_pdf(order) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = []
    _header(story, order.organization, "Zusatzarbeit", order.number)
    customer = order.project.customer
    story.append(Paragraph(f"<b>{customer.display_name}</b><br/>{customer.street}<br/>{customer.postal_code} {customer.city}", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"<b>Projekt:</b> {order.project.number} · {order.project.title}", styles["Normal"]))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(f"<b>{order.title}</b>", styles["Heading2"]))
    story.append(Paragraph(order.description.replace("\n", "<br/>") or "–", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))
    table = Table([
        ["Netto", money(order.amount_net)],
        [f"MwSt. {order.tax_rate}%", money(order.amount_gross - order.amount_net)],
        ["Gesamt", money(order.amount_gross)],
    ], colWidths=[120 * mm, 62 * mm])
    table.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#c6a15b")), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
    story.append(table)
    if order.signed_at:
        story.append(Spacer(1, 10 * mm))
        story.append(Paragraph(f"Digital bestätigt durch <b>{order.signed_name}</b> am {order.signed_at:%d.%m.%Y %H:%M}", styles["Normal"]))
        signature = _signature_image(order.signature_data)
        if signature:
            story.append(signature)
    else:
        story.append(Spacer(1, 10 * mm))
        story.append(Paragraph("Freigabe ausstehend. Der Kunde bestätigt diese Zusatzarbeit digital über den sicheren Freigabelink.", styles["Normal"]))
    doc.build(story)
    return buffer.getvalue()


def _bando_report_order_data(project):
    for document in project.documents.order_by("-created_at"):
        metadata = document.metadata or {}
        if metadata.get("source_order") or metadata.get("provider") == "B&O":
            parsed = metadata.get("bando_order") or metadata.get("parsed_order") or {}
            if isinstance(parsed, dict):
                return parsed
    return {}


def _pdf_text(value) -> str:
    return xml_escape(str(value or "")).replace("\n", "<br/>")


def _bando_yes_no(value):
    if value is True:
        return "X", ""
    if value is False:
        return "", "X"
    return "", ""


def _build_bando_site_report_pdf(report, *, include_prices=True) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm, topMargin=13 * mm, bottomMargin=13 * mm)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("bando-body", parent=styles["Normal"], fontSize=9.5, leading=12)
    small = ParagraphStyle("bando-small", parent=body, fontSize=8.5, leading=10)
    heading = ParagraphStyle("bando-heading", parent=styles["Heading2"], fontSize=12.5, leading=15, spaceAfter=4)
    story = []
    project = report.project
    customer = project.customer
    location = project.object_location
    order = _bando_report_order_data(project)
    order_number = order.get("auftrag") or project.external_reference or project.number
    order_date = order.get("datum") or (report.created_at.strftime("%d.%m.%Y") if report.created_at else "")
    tenant = order.get("mieter") or customer.display_name
    address = order.get("adresse") or (
        f"{location.street}, {location.postal_code} {location.city}" if location else
        f"{customer.street}, {customer.postal_code} {customer.city}".strip(", ")
    )
    room = order.get("raum") or ""
    damage = order.get("schaden") or project.description or report.report_text
    hazard = order.get("schadstoff")

    # Page 1: repair order + customer's signed performance confirmation.
    header = Table([
        [Paragraph("<b>Reparaturauftrag / Leistungsnachweis</b>", styles["Title"]), Paragraph("<b>B&O SERVICE</b>", ParagraphStyle("brand", parent=styles["Heading1"], alignment=TA_RIGHT, textColor=colors.HexColor("#163061")))],
        [Paragraph(_pdf_text(report.organization.name), body), Paragraph(f"Unser Auftrag: <b>{_pdf_text(order_number)}</b><br/>Datum: {_pdf_text(order_date)}", ParagraphStyle("meta-right", parent=small, alignment=TA_RIGHT))],
    ], colWidths=[112 * mm, 70 * mm])
    header.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
    story.extend([header, Spacer(1, 4 * mm)])
    story.append(Paragraph("<b>für den Mieter / Kunden</b>", heading))
    customer_rows = [["Name", Paragraph(_pdf_text(tenant or "–"), body)], ["Adresse", Paragraph(_pdf_text(address or "–"), body)]]
    if location and location.floor:
        customer_rows.append(["Etage", Paragraph(_pdf_text(location.floor), body)])
    if customer.phone or customer.mobile:
        customer_rows.append(["Telefon", Paragraph(_pdf_text(customer.mobile or customer.phone), body)])
    customer_table = Table(customer_rows, colWidths=[34 * mm, 145 * mm])
    customer_table.setStyle(TableStyle([("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"), ("VALIGN", (0,0), (-1,-1), "TOP"), ("BOTTOMPADDING", (0,0), (-1,-1), 3)]))
    story.extend([customer_table, Spacer(1, 4 * mm)])

    story.append(Paragraph("<b>Beschreibung des Auftrags</b>", heading))
    description_rows = [["Bereich / Raum", Paragraph(_pdf_text(room or "–"), body)], ["Was ist zu reparieren", Paragraph(_pdf_text(damage or "–"), body)]]
    if hazard:
        description_rows.append(["Schadstoffhinweis", Paragraph(_pdf_text(hazard), small)])
    description_table = Table(description_rows, colWidths=[42 * mm, 137 * mm])
    description_table.setStyle(TableStyle([("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"), ("VALIGN", (0,0), (-1,-1), "TOP"), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    story.extend([description_table, Spacer(1, 4 * mm)])

    yes_sat, no_sat = _bando_yes_no(report.execution_satisfied)
    yes_punctual, no_punctual = _bando_yes_no(report.employee_punctual)
    execution = Table([
        [Paragraph("<b>Ausführung</b>", body), "Ja", "Nein"],
        ["Mit der Ausführung bin ich zufrieden", yes_sat, no_sat],
        ["Der Servicemitarbeiter war pünktlich", yes_punctual, no_punctual],
        ["Ausführungsdauer der Reparatur", Paragraph(_pdf_text(report.repair_duration or "–"), body), ""],
        ["Mieterverschulden", "X" if report.tenant_fault else "", ""],
    ], colWidths=[132 * mm, 23 * mm, 23 * mm])
    execution.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("ALIGN", (1,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("GRID", (0,1), (-1,-1), .35, colors.HexColor("#cfd6df")),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f2f5f8")), ("BOTTOMPADDING", (0,0), (-1,-1), 6), ("TOPPADDING", (0,0), (-1,-1), 6),
    ]))
    story.extend([execution, Spacer(1, 5 * mm)])
    if report.report_text:
        story.extend([Paragraph("<b>Bericht / Notizen vor Ort</b>", heading), Paragraph(_pdf_text(report.report_text), body), Spacer(1, 4 * mm)])
    if report.voice_file:
        story.append(Paragraph(f"Sprachnotiz im Projekt gespeichert: {_pdf_text(report.voice_file.name)}", small))
        story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("<b>Bestätigung der Leistung</b>", heading))
    if report.signed_at:
        story.append(Paragraph(f"Digital bestätigt durch <b>{_pdf_text(report.signed_name)}</b> am {report.signed_at:%d.%m.%Y %H:%M}.", body))
        signature = _signature_image(report.customer_signature)
        if signature:
            signature.drawHeight = 20 * mm
            signature.drawWidth = min(signature.drawWidth, 62 * mm)
            story.append(Spacer(1, 2 * mm))
            story.append(signature)
        story.append(Paragraph("Datum, Unterschrift", small))
    else:
        story.append(Spacer(1, 12 * mm))
        story.append(Paragraph("__________________________________________<br/>Datum, Unterschrift", small))
    story.extend([Spacer(1, 3 * mm), Paragraph("Ohne unterschriebenen Leistungsnachweis kann die kaufmännische Weiterverarbeitung des B&O-Auftrags nicht abgeschlossen werden.", small)])

    # Page 2: actual service/material quantities. Prices are never editable in the field UI.
    story.append(PageBreak())
    page2_header = Table([
        [Paragraph(f"<b>{_pdf_text(report.organization.name)}</b><br/>{_pdf_text(tenant)}<br/>{_pdf_text(address)}", body), Paragraph("<b>B&O SERVICE</b>", ParagraphStyle("brand2", parent=styles["Heading1"], alignment=TA_RIGHT, textColor=colors.HexColor("#163061")))],
        [Paragraph("<b>Aufmass / Regiebericht für Reparatur</b>", styles["Heading1"]), Paragraph(f"Unser Auftrag: <b>{_pdf_text(order_number)}</b><br/>Datum: {_pdf_text(order_date)}", ParagraphStyle("meta-right2", parent=small, alignment=TA_RIGHT))],
    ], colWidths=[112 * mm, 70 * mm])
    page2_header.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
    story.extend([page2_header, Spacer(1, 6 * mm)])

    service_data = [["Leist.-Nr.", "Leistungen", "Menge"]]
    for line in report.service_lines or []:
        service_data.append([
            _pdf_text(line.get("code")),
            Paragraph(_pdf_text(line.get("description")), small),
            _pdf_text(f"{line.get('quantity') or ''} {line.get('unit') or ''}".strip()),
        ])
    if len(service_data) == 1:
        service_data.append(["", "", ""])
    service_table = Table(service_data, colWidths=[32 * mm, 112 * mm, 35 * mm], repeatRows=1, minRowHeights=[9 * mm] + [10 * mm] * (len(service_data)-1))
    service_table.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f2f5f8")),
        ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#cfd6df")), ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
    ]))
    story.extend([service_table, Spacer(1, 11 * mm)])

    material_data = [["Mat.-Nr.", "Material", "Menge"] + (["Preis"] if include_prices else [])]
    for line in report.material_lines or []:
        row = [
            _pdf_text(line.get("code")),
            Paragraph(_pdf_text(line.get("description")), small),
            _pdf_text(f"{line.get('quantity') or ''} {line.get('unit') or ''}".strip()),
        ]
        if include_prices:
            price = line.get("price")
            row.append(money(price) if price not in (None, "") else "")
        material_data.append(row)
    if len(material_data) == 1:
        material_data.append(["", "", ""] + ([""] if include_prices else []))
    col_widths = [30 * mm, 119 * mm, 30 * mm] if not include_prices else [30 * mm, 94 * mm, 30 * mm, 25 * mm]
    material_table = Table(material_data, colWidths=col_widths, repeatRows=1, minRowHeights=[9 * mm] + [10 * mm] * (len(material_data)-1))
    material_style = [
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f2f5f8")),
        ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#cfd6df")), ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
    ]
    if include_prices:
        material_style.append(("ALIGN", (-1,1), (-1,-1), "RIGHT"))
    material_table.setStyle(TableStyle(material_style))
    story.append(material_table)
    doc.build(story)
    return buffer.getvalue()


def build_site_report_pdf(report, *, include_prices=True) -> bytes:
    if getattr(report, "kind", "generic") == "bando":
        return _build_bando_site_report_pdf(report, include_prices=include_prices)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = []
    _header(story, report.organization, report.title, f"#{report.pk}")
    project = report.project
    story.append(Paragraph(f"<b>Projekt:</b> {project.number} · {project.title}<br/><b>Kunde:</b> {project.customer.display_name}<br/><b>Auftrag:</b> {project.get_job_type_display()}", styles["Normal"]))
    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph((report.report_text or "Kein Berichtstext.").replace("\n", "<br/>"), styles["Normal"]))
    if report.voice_file:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(f"Sprachnotiz gespeichert: {report.voice_file.name}", styles["Normal"]))
    try:
        from reportlab.platypus import Image
        media = report.project.work_media.filter(kind="photo", stage__in=["before", "after"]).order_by("stage", "created_at")[:8]
        rows = []
        for item in media:
            try:
                image = Image(item.file.path, width=72 * mm, height=50 * mm, kind="proportional")
                rows.append([Paragraph(f"<b>{item.get_stage_display()}</b><br/>{item.caption or item.title}", styles["Normal"]), image])
            except Exception:
                continue
        if rows:
            story.append(Spacer(1, 8 * mm))
            story.append(Paragraph("Vorher / Nachher Dokumentation", styles["Heading2"]))
            media_table = Table(rows, colWidths=[80 * mm, 82 * mm])
            media_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#d8dde8")), ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f6f7fb")])]))
            story.append(media_table)
    except Exception:
        pass
    if report.signed_at:
        story.append(Spacer(1, 10 * mm))
        story.append(Paragraph(f"Vor Ort digital bestätigt durch <b>{report.signed_name}</b> am {report.signed_at:%d.%m.%Y %H:%M}", styles["Normal"]))
        signature = _signature_image(report.customer_signature)
        if signature:
            story.append(signature)
    doc.build(story)
    return buffer.getvalue()
