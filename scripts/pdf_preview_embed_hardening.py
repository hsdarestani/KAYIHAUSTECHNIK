from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU PDF PREVIEW EMBED HARDENING 2026-09-08"
VIEWS_REL = "erp/tooltime_parity_views.py"
TEST_REL = "tests/test_pdf_preview_embed_hardening.py"


def _patch_preview_function(text: str, function_name: str) -> str:
    start = text.find(f"def {function_name}(")
    if start < 0:
        raise RuntimeError(f"PDF preview hardening: {function_name} is missing")
    next_decorator = text.find("\n\n@login_required", start + 1)
    end = next_decorator if next_decorator >= 0 else len(text)
    block = text[start:end]

    if 'response["X-Frame-Options"] = "SAMEORIGIN"' not in block:
        anchor = 'response["Cache-Control"] = "private, no-store"'
        if anchor not in block:
            raise RuntimeError(f"PDF preview hardening: cache header anchor missing in {function_name}")
        replacement = (
            'response["X-Frame-Options"] = "SAMEORIGIN"\n'
            '    response["Content-Security-Policy"] = "frame-ancestors \'self\'"\n'
            f"    {anchor}"
        )
        block = block.replace(anchor, replacement, 1)
        text = text[:start] + block + text[end:]
    return text


def patch_views() -> None:
    path = ROOT / VIEWS_REL
    if not path.exists():
        raise RuntimeError(f"PDF preview hardening target missing: {VIEWS_REL}")
    text = path.read_text(encoding="utf-8")
    text = _patch_preview_function(text, "quote_preview")
    text = _patch_preview_function(text, "invoice_preview")
    path.write_text(text, encoding="utf-8")


def install_test() -> None:
    path = ROOT / TEST_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        r'''from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class PdfPreviewEmbedHardeningTests(SimpleTestCase):
    def test_quote_and_invoice_preview_explicitly_allow_same_origin_embedding(self):
        views = (ROOT / "erp/tooltime_parity_views.py").read_text(encoding="utf-8")
        for function_name in ("quote_preview", "invoice_preview"):
            start = views.index(f"def {function_name}(")
            next_decorator = views.find("\n\n@login_required", start + 1)
            block = views[start: next_decorator if next_decorator >= 0 else len(views)]
            self.assertIn('response["X-Frame-Options"] = "SAMEORIGIN"', block)
            self.assertIn('response["Content-Security-Policy"] = "frame-ancestors \'self\'"', block)
            self.assertIn('content_type="application/pdf"', block)
            self.assertIn('Content-Disposition', block)
            self.assertIn('inline; filename=', block)
''',
        encoding="utf-8",
    )


def guard() -> None:
    views = (ROOT / VIEWS_REL).read_text(encoding="utf-8")
    for function_name in ("quote_preview", "invoice_preview"):
        start = views.find(f"def {function_name}(")
        if start < 0:
            raise RuntimeError(f"PDF preview embed guard: {function_name} missing")
        next_decorator = views.find("\n\n@login_required", start + 1)
        block = views[start: next_decorator if next_decorator >= 0 else len(views)]
        for required in (
            'response["X-Frame-Options"] = "SAMEORIGIN"',
            'response["Content-Security-Policy"] = "frame-ancestors \'self\'"',
            'content_type="application/pdf"',
            'Content-Disposition',
        ):
            if required not in block:
                raise RuntimeError(f"PDF preview embed guard failed for {function_name}: {required}")


def main() -> None:
    patch_views()
    install_test()
    guard()
    print(f"{MARKER}: quote/invoice PDF preview responses explicitly allow same-origin embedding.")


if __name__ == "__main__":
    main()
