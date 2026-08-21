from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU TOOLTIME INVOICES REGRESSION COMPAT 2026-08-21"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Invoice compatibility target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def patch_route_contract() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)
    exact_import = "from . import tooltime_invoices_exact as invoices_exact\n"
    parity_import = "from . import tooltime_parity_views as tooltime_parity\n"
    if parity_import not in text or exact_import not in text:
        raise RuntimeError("Invoice compatibility imports are missing")

    exact_route = 'path("invoices/", invoices_exact.invoice_list, name="next-invoices")'
    parity_route = 'path("invoices/", tooltime_parity.invoice_list, name="next-invoices")'
    if exact_route in text:
        text = text.replace(exact_route, parity_route, 1)
    elif parity_route not in text:
        raise RuntimeError("Invoice list route could not be reconciled")

    alias = "tooltime_parity.invoice_list = invoices_exact.invoice_list\n"
    if alias not in text:
        anchor = "\n\nurlpatterns = [\n"
        if anchor not in text:
            raise RuntimeError("Invoice URL urlpatterns anchor changed")
        text = text.replace(anchor, f"\n\n# {MARKER}\n{alias}{anchor}", 1)
    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_invoice_actions() -> None:
    rel = "templates/rebuild/invoices.html"
    text = read(rel)
    lifecycle_script = '<script src="{% static \'js/tooltime-parity-lifecycle.js\' %}?v=20260821-invoices-compat" defer></script>\n'
    exact_script = '<script src="{% static \'js/tooltime-invoices-exact.js\' %}?v=20260821-invoices-exact" defer></script>\n'
    if lifecycle_script not in text:
        if exact_script not in text:
            raise RuntimeError("Invoice exact JS anchor changed")
        text = text.replace(exact_script, exact_script + lifecycle_script, 1)

    old = '''{% if row.finalized and row.open > 0 %}<a href="{% url 'next-invoice-edit' row.invoice.pk %}#zahlungen">Zahlung erfassen</a>{% endif %}'''
    new = '''{% if row.finalized and row.open > 0 %}
          <button type="button" data-payment-open data-action="{% url 'next-invoice-payment' row.invoice.pk %}" data-number="{{ row.invoice.number|default:'Rechnung' }}" data-open="{{ row.open }}">Zahlung eintragen</button>
          <form method="post" action="{% url 'next-invoice-dunning' row.invoice.pk %}">{% csrf_token %}<input type="hidden" name="level" value="reminder"><input type="hidden" name="due_days" value="7"><button type="submit">Zahlungserinnerung</button></form>
          <form method="post" action="{% url 'next-invoice-payment-link' row.invoice.pk %}">{% csrf_token %}<button type="submit">Online-Zahlung / QR</button></form>
          <form method="post" action="{% url 'next-invoice-dunning-toggle' row.invoice.pk %}">{% csrf_token %}<button type="submit">Mahn-Automatik aussetzen</button></form>
        {% endif %}'''
    if old in text:
        text = text.replace(old, new, 1)
    elif not all(value in text for value in (
        "Zahlung eintragen", "Zahlungserinnerung", "Online-Zahlung / QR",
        "Mahn-Automatik aussetzen", "data-payment-open", "next-invoice-payment",
        "next-invoice-dunning",
    )):
        raise RuntimeError("Invoice row action anchor changed")

    if "data-payment-modal" not in text:
        modal = r'''
  <div class="tti-payment-modal" data-payment-modal hidden>
    <form class="tti-payment-card" method="post" data-payment-form>{% csrf_token %}
      <header><div><span>Zahlung</span><h2>Zahlung eintragen</h2><p data-payment-caption></p></div><button type="button" data-payment-close aria-label="Schließen">×</button></header>
      <div class="tti-payment-grid">
        <label>Zahlungsdatum<input type="date" name="paid_at" value="{% now 'Y-m-d' %}" required></label>
        <label>Betrag<input type="number" name="amount" min="0.01" step="0.01" data-payment-amount required></label>
        <label>Zahlungsart<select name="method"><option>Überweisung</option><option>Bar</option><option>Karte</option><option>Lastschrift</option><option>Sonstiges</option></select></label>
        <label>Kommentar / Referenz<input name="reference" maxlength="240" placeholder="Optional"></label>
      </div>
      <p>Teilzahlungen sind möglich. Die Rechnung bleibt bis zum vollständigen Ausgleich offen.</p>
      <button class="tti-payment-save" type="submit">Zahlung verbuchen</button>
    </form>
  </div>
'''
        end_marker = "\n</div>\n{% endblock %}"
        end_pos = text.rfind(end_marker)
        if end_pos < 0:
            raise RuntimeError("Invoice page end anchor changed")
        text = text[:end_pos] + modal + text[end_pos:]
    write(rel, text)

    css_rel = "static/css/tooltime-invoices-exact.css"
    css = read(css_rel)
    compat_css = r'''.tti-row-menu form{margin:0}.tti-row-menu button{display:block;width:100%;padding:9px 10px;border:0;border-radius:6px;background:transparent;text-align:left;font:inherit;color:#34475b;white-space:nowrap;cursor:pointer}.tti-row-menu button:hover{background:#f2f5f8}.tti-payment-modal{position:fixed;inset:0;z-index:2000;background:rgba(22,34,48,.38);display:flex;align-items:center;justify-content:center;padding:18px}.tti-payment-modal[hidden]{display:none}.tti-payment-card{width:min(620px,100%);background:#fff;border-radius:14px;box-shadow:0 24px 60px rgba(15,30,45,.25);padding:22px}.tti-payment-card header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:18px}.tti-payment-card header span{font-size:11px;text-transform:uppercase;color:#8190a0;font-weight:800}.tti-payment-card h2{margin:3px 0 3px;font-size:22px}.tti-payment-card header p{margin:0;color:#738294;font-size:12px}.tti-payment-card header button{border:0;background:transparent;font-size:25px;color:#7e8c9b;cursor:pointer}.tti-payment-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.tti-payment-grid label{display:grid;gap:6px;font-size:11px;font-weight:750;color:#5c6b7b}.tti-payment-grid input,.tti-payment-grid select{width:100%;box-sizing:border-box;border:1px solid #d6dee7;border-radius:8px;padding:10px;font:inherit;background:#fff}.tti-payment-card>p{font-size:12px;color:#788696}.tti-payment-save{border:0;border-radius:8px;background:#147de0;color:#fff;padding:10px 15px;font-weight:750;cursor:pointer}@media(max-width:600px){.tti-payment-grid{grid-template-columns:1fr}}'''
    if compat_css not in css:
        write(css_rel, css + compat_css)


def final_guard() -> None:
    urls = read("erp/rebuild_urls.py")
    template = read("templates/rebuild/invoices.html")
    for required in ("tooltime_parity.invoice_list", "invoices_exact.invoice_list", "next-invoices"):
        if required not in urls:
            raise RuntimeError(f"Invoice route regression contract missing: {required}")
    for required in (
        "Zahlung eintragen", "Zahlungserinnerung", "Online-Zahlung / QR",
        "Mahn-Automatik aussetzen", "data-payment-open", "data-payment-modal",
        "next-invoice-payment", "next-invoice-dunning", "next-invoice-payment-link",
        "next-invoice-dunning-toggle", "data-tooltime-invoices-exact",
    ):
        if required not in template:
            raise RuntimeError(f"Invoice action regression contract missing: {required}")


def main() -> None:
    patch_route_contract()
    patch_invoice_actions()
    final_guard()
    print(f"{MARKER}: exact ToolTime invoice list + legacy payment/dunning contracts reconciled.")
    # Projects is deliberately installed after the final finance compatibility layer.
    # This makes the screenshot-verified list/modal the last owner of /projects/ so
    # older CRUD/UI overlays cannot restore the legacy table during assembly.
    runpy.run_path(str(ROOT / "scripts" / "tooltime_projects_exact_parity.py"), run_name="__main__")
    # Appointment navigation is normalized last: Phase 10 and Phase 12 both added
    # their own Kalender/Karte/Liste groups, so the final assembled shell must keep
    # exactly one live ToolTime-style submenu with a visible active state.
    runpy.run_path(str(ROOT / "scripts" / "tooltime_appointment_sidebar_nav_fix.py"), run_name="__main__")
    # Do not re-render the global shell/project detail here. The dedicated final
    # surface pass dropped working finance, B&O report, Room Planner and field hooks.
    # Those operational features remain authoritative while customer parity stays
    # limited to contacts/customer surfaces.


if __name__ == "__main__":
    main()
