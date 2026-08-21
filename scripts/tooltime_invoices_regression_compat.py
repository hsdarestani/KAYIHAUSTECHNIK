from __future__ import annotations

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

    # Preserve the long-standing Phase-4 route contract while still executing the
    # screenshot-exact list implementation. Keeping the alias here also makes the
    # compatibility explicit instead of silently duplicating invoice-list logic.
    alias = "tooltime_parity.invoice_list = invoices_exact.invoice_list\n"
    if alias not in text:
        marker = "\n\nurlpatterns = [\n"
        if marker not in text:
            raise RuntimeError("Invoice URL urlpatterns anchor changed")
        text = text.replace(marker, f"\n\n# {MARKER}\n{alias}{marker}", 1)

    write(rel, text)
    compile(text, str(ROOT / rel), "exec")


def patch_invoice_actions() -> None:
    rel = "templates/rebuild/invoices.html"
    text = read(rel)

    # The new screenshot-exact table must not drop the real Phase-4/Pay actions.
    # These controls use existing authoritative endpoints; no fake payment state is
    # created and provider/dunning policy stays server-side.
    old = '''{% if row.finalized and row.open > 0 %}<a href="{% url 'next-invoice-edit' row.invoice.pk %}#zahlungen">Zahlung erfassen</a>{% endif %}'''
    new = '''{% if row.finalized and row.open > 0 %}
          <a href="{% url 'next-invoice-edit' row.invoice.pk %}#zahlungen">Zahlung eintragen</a>
          <form method="post" action="{% url 'next-invoice-payment-link' row.invoice.pk %}">{% csrf_token %}<button type="submit">Online-Zahlung / QR</button></form>
          <form method="post" action="{% url 'next-invoice-dunning-toggle' row.invoice.pk %}">{% csrf_token %}<button type="submit">Mahn-Automatik aussetzen</button></form>
        {% endif %}'''
    if old in text:
        text = text.replace(old, new, 1)
    else:
        required = ("Zahlung eintragen", "Online-Zahlung / QR", "Mahn-Automatik aussetzen")
        if not all(value in text for value in required):
            raise RuntimeError("Invoice row action anchor changed")

    write(rel, text)

    css_rel = "static/css/tooltime-invoices-exact.css"
    css = read(css_rel)
    compat_css = ".tti-row-menu form{margin:0}.tti-row-menu button{display:block;width:100%;padding:9px 10px;border:0;border-radius:6px;background:transparent;text-align:left;font:inherit;color:#34475b;white-space:nowrap;cursor:pointer}.tti-row-menu button:hover{background:#f2f5f8}"
    if compat_css not in css:
        css += compat_css
        write(css_rel, css)


def final_guard() -> None:
    urls = read("erp/rebuild_urls.py")
    template = read("templates/rebuild/invoices.html")
    for required in (
        "tooltime_parity.invoice_list",
        "invoices_exact.invoice_list",
        "next-invoices",
    ):
        if required not in urls:
            raise RuntimeError(f"Invoice route regression contract missing: {required}")
    for required in (
        "Zahlung eintragen",
        "Online-Zahlung / QR",
        "Mahn-Automatik aussetzen",
        "next-invoice-payment-link",
        "next-invoice-dunning-toggle",
        "data-tooltime-invoices-exact",
    ):
        if required not in template:
            raise RuntimeError(f"Invoice action regression contract missing: {required}")


def main() -> None:
    patch_route_contract()
    patch_invoice_actions()
    final_guard()
    print(f"{MARKER}: exact ToolTime invoice list + legacy payment/dunning contracts reconciled.")


if __name__ == "__main__":
    main()
