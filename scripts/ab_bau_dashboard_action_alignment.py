from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU V3 DASHBOARD ACTION ALIGNMENT FIX 2026-09-08"
CSS_REL = "static/css/ab-bau-v3-finance-mobile-pdf-hotfix.css"
BASE_REL = "templates/rebuild/base.html"
LEGACY_CACHE_TEST_REL = "tests/test_ab_bau_v3_catalogue_mobile_header_overflow_fix.py"
CACHE_VERSION = "20260908-dashboard-actions-1"

FIX = r"""

/* A+BAU V3 DASHBOARD ACTION ALIGNMENT FIX 2026-09-08
   Hero actions are links/buttons with the same visual height. Make both controls
   real flex containers so their label (including the leading plus glyph) is
   optically and mechanically centered in both axes at every desktop zoom level. */
body.ab-v3 .ab-v3-hero-actions a,
body.ab-v3 .ab-v3-hero-actions button{
  display:inline-flex!important;
  align-items:center!important;
  justify-content:center!important;
  text-align:center!important;
  line-height:1!important;
  white-space:nowrap!important;
  box-sizing:border-box!important;
}
"""


def install() -> None:
    css_path = ROOT / CSS_REL
    if not css_path.exists():
        raise RuntimeError(f"Dashboard action CSS target missing: {CSS_REL}")
    css = css_path.read_text(encoding="utf-8")
    if MARKER not in css:
        css = css.rstrip() + FIX + "\n"
        css_path.write_text(css, encoding="utf-8")

    base_path = ROOT / BASE_REL
    if not base_path.exists():
        raise RuntimeError(f"Dashboard action cache target missing: {BASE_REL}")
    base = base_path.read_text(encoding="utf-8")
    pattern = r'(/static/css/ab-bau-v3-finance-mobile-pdf-hotfix\.css\?v=)[^\"\']+'
    if not re.search(pattern, base):
        raise RuntimeError("Dashboard action hotfix stylesheet link missing")
    base = re.sub(pattern, rf'\g<1>{CACHE_VERSION}', base)
    base_path.write_text(base, encoding="utf-8")


def align_legacy_cache_contract() -> None:
    """Keep the earlier catalogue regression test aligned with the final cache owner."""
    path = ROOT / LEGACY_CACHE_TEST_REL
    if not path.exists():
        raise RuntimeError(f"Legacy catalogue cache contract missing: {LEGACY_CACHE_TEST_REL}")
    text = path.read_text(encoding="utf-8")
    pattern = r'ab-bau-v3-finance-mobile-pdf-hotfix\.css\?v=20260908-[A-Za-z0-9._-]+'
    replacement = f"ab-bau-v3-finance-mobile-pdf-hotfix.css?v={CACHE_VERSION}"
    if not re.search(pattern, text):
        raise RuntimeError("Legacy catalogue cache assertion anchor missing")
    text = re.sub(pattern, replacement, text)
    path.write_text(text, encoding="utf-8")


def guard() -> None:
    css = (ROOT / CSS_REL).read_text(encoding="utf-8")
    for required in (
        MARKER,
        "body.ab-v3 .ab-v3-hero-actions a,",
        "body.ab-v3 .ab-v3-hero-actions button{",
        "display:inline-flex!important",
        "align-items:center!important",
        "justify-content:center!important",
        "line-height:1!important",
    ):
        if required not in css:
            raise RuntimeError(f"Dashboard action alignment guard failed: {required}")

    expected = f"ab-bau-v3-finance-mobile-pdf-hotfix.css?v={CACHE_VERSION}"
    base = (ROOT / BASE_REL).read_text(encoding="utf-8")
    if expected not in base:
        raise RuntimeError("Dashboard action alignment cache version was not installed")
    legacy_test = (ROOT / LEGACY_CACHE_TEST_REL).read_text(encoding="utf-8")
    if expected not in legacy_test:
        raise RuntimeError("Legacy catalogue cache regression contract is stale")


def main() -> None:
    install()
    align_legacy_cache_contract()
    guard()
    print(f"{MARKER}: Schnell erstellen and + Einsatz planen are centered consistently.")


if __name__ == "__main__":
    main()
