from __future__ import annotations

import re
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


def dataset_name(attribute: str) -> str:
    parts = attribute.removeprefix("data-").split("-")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def audit_buttons() -> None:
    failures: list[str] = []
    missing_handlers: list[str] = []
    js_corpus = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "static" / "js").rglob("*.js"))
    for path in sorted((ROOT / "templates" / "rebuild").glob("*.html")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"<button\b[^>]*>", text, flags=re.IGNORECASE):
            tag = match.group(0)
            if not re.search(r"\btype\s*=\s*['\"]button['\"]", tag, flags=re.IGNORECASE):
                continue
            lowered = tag.lower()
            if " disabled" in lowered:
                continue
            line = text.count("\n", 0, match.start()) + 1
            data_attrs = re.findall(r"\b(data-[a-z0-9_-]+)(?:\s*=|\s|>)", lowered)
            if not data_attrs and "onclick=" not in lowered and "nx-item-remove" not in lowered:
                failures.append(f"{path.relative_to(ROOT)}:{line}: {tag[:180]}")
                continue
            for attribute in data_attrs:
                camel = dataset_name(attribute)
                if attribute not in js_corpus and f"dataset.{camel}" not in js_corpus:
                    missing_handlers.append(f"{path.relative_to(ROOT)}:{line}: {attribute}")
    if failures:
        raise RuntimeError("Unbound KAYI Next buttons found:\n" + "\n".join(failures[:30]))
    if missing_handlers:
        raise RuntimeError("KAYI Next button data-actions without JavaScript references found:\n" + "\n".join(missing_handlers[:50]))


normalize_tail("static/css/kayi-next.css")
normalize_tail("static/js/kayi-next.js")

css = (ROOT / "static/css/kayi-next.css").read_text(encoding="utf-8")
js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
if "\\n.nx-checkbox-input" in css or "\\n(() =>" in js:
    raise RuntimeError("UI hardening assets still contain escaped line separators")
if ".nx-checkbox-input" not in css or "dataset.nxAddBound" not in js:
    raise RuntimeError("UI hardening assets are incomplete")

audit_buttons()
print("KAYI UI hardening assets and button bindings normalized and verified.")
