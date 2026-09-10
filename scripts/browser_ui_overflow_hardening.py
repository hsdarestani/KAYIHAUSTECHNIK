from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "static/css/kayi-next.css"
MARKER = "A+BAU BROWSER UI OVERFLOW HARDENING 2026-09-10"

CSS = r"""

/* A+BAU BROWSER UI OVERFLOW HARDENING 2026-09-10
   Keep off-canvas UI out of the document scroll width and constrain the
   desktop week calendar to its content column. Mobile keeps its own
   intentional horizontal calendar scroller. */
html,
body {
  max-width: 100%;
  overflow-x: clip;
}

.nx-assistant-drawer[aria-hidden="true"] {
  display: none !important;
}

/* The final document overlay left the one-column editor grid at a fixed
   1376px track inside a narrower application content area. */
.ab-v3-document-editor .tt-document-form {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  grid-template-columns: minmax(0, 1fr) !important;
}

.ab-v3-document-editor .tt-document-form > *,
.ab-v3-document-editor .tt-card,
.ab-v3-document-editor .tt-services,
.ab-v3-document-editor .tt-two,
.ab-v3-document-editor .tt-price-tools {
  min-width: 0;
  max-width: 100%;
}

.nx-calendar-shell,
.nx-calendar-shell > *,
.nx-calendar-toolbar,
.nx-calendar-period,
.nx-calendar-filters {
  min-width: 0;
  max-width: 100%;
}

.nx-calendar-toolbar,
.nx-calendar-period {
  width: 100%;
  flex-wrap: wrap;
}

.nx-calendar-period > span {
  max-width: 100%;
  overflow-wrap: anywhere;
}

@media (min-width: 901px) {
  .nx-week-upgraded {
    width: 100%;
    min-width: 0;
    grid-template-columns: repeat(7, minmax(0, 1fr)) !important;
    overflow-x: hidden;
  }

  .nx-week-upgraded .nx-day {
    min-width: 0 !important;
  }
}
"""

text = TARGET.read_text(encoding="utf-8")
if MARKER not in text:
    TARGET.write_text(text.rstrip() + CSS + "\n", encoding="utf-8")

verified = TARGET.read_text(encoding="utf-8")
for needle in (
    MARKER,
    '.nx-assistant-drawer[aria-hidden="true"]',
    ".ab-v3-document-editor .tt-document-form",
    "grid-template-columns: minmax(0, 1fr) !important",
    "@media (min-width: 901px)",
    "grid-template-columns: repeat(7, minmax(0, 1fr)) !important",
):
    if needle not in verified:
        raise RuntimeError(f"Browser overflow hardening verification failed: {needle}")

print(f"{MARKER}: desktop calendar and off-canvas overflow guards installed.")
