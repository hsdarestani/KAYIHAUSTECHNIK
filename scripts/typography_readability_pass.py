from __future__ import annotations

import re
import runpy
from pathlib import Path

CSS_PATH = Path("static/css/kayi-next.css")
MARKER = "/* KAYI READABILITY PASS 2026-08-10 */"
CACHE_VERSION = "20260810-9"

CSS = r'''

/* KAYI READABILITY PASS 2026-08-10 */
/* Preserve the compact product feel, but remove sub-12px UI text from normal workflows. */
body.nx-body {
  font-size: 15px;
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

.nx-brand strong { font-size: 17px; }
.nx-brand small { font-size: 12px; line-height: 1.35; }
.nx-nav-label { font-size: 11px; letter-spacing: .11em; }
.nx-nav a { font-size: 14px; line-height: 1.35; padding-top: 12px; padding-bottom: 12px; }
.nx-sidebar-foot { font-size: 12px; line-height: 1.55; }

.nx-search input,
.nx-control,
.next-control,
.nx-body input,
.nx-body select,
.nx-body textarea {
  font-size: 14px;
  line-height: 1.4;
}

.nx-btn,
.nx-body button {
  font-size: 13px;
  line-height: 1.3;
}

.nx-kicker { font-size: 11px; }
.nx-pagehead p { font-size: 15px; line-height: 1.5; }
.nx-card-head h2 { font-size: 19px; }
.nx-card-head h3 { font-size: 16px; }
.nx-card-head p { font-size: 13px; line-height: 1.5; }
.nx-stat small,
.nx-stat em { font-size: 12px; }

.nx-field > label,
.nx-body form label,
.nx-body .form-label {
  font-size: 13px;
  line-height: 1.35;
}

.nx-body form small,
.nx-body .helptext,
.nx-body .nx-help,
.nx-body .form-help,
.nx-body .nx-muted,
.nx-body .muted {
  font-size: 12px;
  line-height: 1.5;
}

.nx-table th { font-size: 11px; line-height: 1.3; }
.nx-table td { font-size: 13px; line-height: 1.4; }
.nx-table strong { font-size: 14px; }
.nx-badge { font-size: 11px; }
.nx-meta { font-size: 12px; }
.nx-tabs button,
.nx-tabs a { font-size: 12px; }

.nx-quick b { font-size: 13px; }
.nx-quick small { font-size: 12px; line-height: 1.45; }
.nx-event-time,
.nx-event b { font-size: 13px; }
.nx-event small { font-size: 12px; }
.nx-day-head { font-size: 13px; }
.nx-day-head small { font-size: 11px; }
.nx-cal-event time { font-size: 11px; }
.nx-cal-event b { font-size: 12px; }
.nx-cal-event small { font-size: 11px; }

.nx-mobile-tabs button { font-size: 12px; }
.nx-job-time { font-size: 13px; }
.nx-job-card h3 { font-size: 15px; }
.nx-job-card p { font-size: 12px; line-height: 1.45; }
.nx-job-address small { font-size: 12px; }
.nx-job-address p { font-size: 13px; }
.nx-job-actions a,
.nx-job-actions button { font-size: 12px; }
.nx-doc-title b { font-size: 14px; }
.nx-doc-title small { font-size: 12px; }
.nx-item-table th { font-size: 11px; }
.nx-item-table td { font-size: 13px; }

/* Financial editor / catalog panel. These selectors intentionally include both current and fallback names. */
.nx-catalog-card,
.nx-catalog-item,
.catalog-card,
.catalog-item,
[data-catalog-item] {
  font-size: 13px;
  line-height: 1.4;
}
.nx-catalog-card b,
.nx-catalog-item b,
.catalog-card b,
.catalog-item b,
[data-catalog-item] b,
[data-catalog-item] strong {
  font-size: 13.5px;
  line-height: 1.35;
}
.nx-catalog-card small,
.nx-catalog-item small,
.catalog-card small,
.catalog-item small,
[data-catalog-item] small {
  font-size: 11.5px;
  line-height: 1.4;
}

/* Quick-job / field forms can contain legacy helper classes outside .nx-field. */
.nx-body .field-label,
.nx-body .field-caption,
.nx-body .section-label,
.nx-body .form-section label {
  font-size: 13px;
}
.nx-body .field-help,
.nx-body .field-caption small,
.nx-body .section-help,
.nx-body .form-section small {
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 900px) {
  body.nx-body { font-size: 15px; }
  .nx-nav a { font-size: 14px; }
  .nx-body input,
  .nx-body select,
  .nx-body textarea { font-size: 16px; } /* avoids mobile browser zoom and remains readable */
  .nx-btn,
  .nx-body button { font-size: 13px; }
}
'''


def bump_cache_versions(root: Path) -> int:
    changed = 0
    pattern = re.compile(r"(\{\%\s*static\s+['\"]css/kayi-next\.css['\"]\s*\%\}\?v=)([^'\"\s<]+)")
    for path in root.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        updated = pattern.sub(rf"\g<1>{CACHE_VERSION}", text)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def main() -> None:
    if not CSS_PATH.exists():
        raise SystemExit(f"Missing assembled stylesheet: {CSS_PATH}")
    css = CSS_PATH.read_text(encoding="utf-8")
    if MARKER not in css:
        CSS_PATH.write_text(css.rstrip() + CSS, encoding="utf-8")
    template_count = bump_cache_versions(Path("templates"))
    final_css = CSS_PATH.read_text(encoding="utf-8")
    required = [
        MARKER,
        ".nx-nav a { font-size: 14px",
        ".nx-field > label",
        "[data-catalog-item]",
        "font-size: 16px; } /* avoids mobile browser zoom",
    ]
    missing = [token for token in required if token not in final_css]
    if missing:
        raise SystemExit(f"Typography pass verification failed: {missing}")

    prepatch = Path(__file__).with_name("prepatch_project_context.py")
    final_quality = Path(__file__).with_name("final_readability_project_guidance.py")
    if not prepatch.exists() or not final_quality.exists():
        raise SystemExit("Missing final readability/recovery assembly helpers")
    try:
        runpy.run_path(str(prepatch), run_name="__main__")
        runpy.run_path(str(final_quality), run_name="__main__")
    except Exception as exc:
        # Surface the exact assembly failure as a GitHub Actions annotation so a
        # deterministic overlay mismatch cannot hide behind a generic exit code.
        detail = str(exc).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=KAYI final UX assembly failed::{detail}")
        raise
    print(f"KAYI readability typography installed; cache-busted templates: {template_count}")


if __name__ == "__main__":
    main()
