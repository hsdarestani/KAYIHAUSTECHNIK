from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "scripts" / "tooltime_customer_project_history_impl.py"
text = IMPL.read_text(encoding="utf-8")

start = text.find("def patch_urls() -> None:\n")
end = text.find("\n\nCUSTOMER_TEMPLATE =", start)
if start < 0 or end < 0:
    raise RuntimeError("Customer/project history wrapper could not locate patch_urls")

patch_urls = r'''def patch_urls() -> None:
    rel = "erp/rebuild_urls.py"
    text = read(rel)

    def insert_after_named_route(anchor_name: str, routes: tuple[tuple[str, str], ...]) -> None:
        nonlocal text
        missing = [line for route_name, line in routes if f'name="{route_name}"' not in text]
        if not missing:
            return
        marker = f'name="{anchor_name}"'
        marker_pos = text.find(marker)
        if marker_pos < 0:
            raise RuntimeError(f"Semantic URL anchor missing: {anchor_name}")
        line_end = text.find("\n", marker_pos)
        if line_end < 0:
            raise RuntimeError(f"URL line boundary missing: {anchor_name}")
        text = text[:line_end + 1] + "".join(missing) + text[line_end + 1:]

    insert_after_named_route(
        "next-customer-detail",
        (
            ("next-customer-quote-create", '    path("customers/<int:pk>/angebot/neu/", views.customer_quote_create, name="next-customer-quote-create"),\n'),
            ("next-customer-invoice-create", '    path("customers/<int:pk>/rechnung/neu/", views.customer_invoice_create, name="next-customer-invoice-create"),\n'),
        ),
    )
    insert_after_named_route(
        "next-project-detail",
        (("next-project-lifecycle", '    path("projects/<int:pk>/aktionen/", views.project_lifecycle, name="next-project-lifecycle"),\n'),),
    )
    write(rel, text)
    compile(text, str(ROOT / rel), "exec")
'''

text = text[:start] + patch_urls + text[end:]
namespace = {"__name__": "__main__", "__file__": str(IMPL), "__package__": None}
exec(compile(text, str(IMPL), "exec"), namespace)
