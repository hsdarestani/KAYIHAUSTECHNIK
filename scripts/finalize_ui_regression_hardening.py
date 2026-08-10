from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI UI regression hardening 20260810"


def normalize_tail(rel: str) -> None:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        raise RuntimeError(f"UI hardening marker missing from {rel}")
    before, marker, after = text.partition(MARKER)
    tail = (marker + after).replace("\\n", "\n")
    path.write_text(before + tail, encoding="utf-8")


normalize_tail("static/css/kayi-next.css")
normalize_tail("static/js/kayi-next.js")

css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
if "\\n.nx-checkbox-input" in css or "\\n(() =>" in js:
    raise RuntimeError("UI hardening assets still contain escaped line separators")
if ".nx-checkbox-input" not in css or "dataset.nxAddBound" not in js:
    raise RuntimeError("UI hardening assets are incomplete")

print("KAYI UI hardening assets normalized and verified.")
