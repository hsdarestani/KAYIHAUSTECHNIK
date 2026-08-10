from __future__ import annotations

import re
import runpy
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "KAYI UI regression hardening 20260810"
JS_MARKER = "// KAYI UI regression hardening 20260810"
GENERIC_CHECKBOX_MARKER = "KAYI global checkbox size contract"


def normalize_css_tail(rel: str) -> None:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        raise RuntimeError(f"UI hardening marker missing from {rel}")
    before, marker, after = text.partition(MARKER)
    tail = (marker + after).replace("\\n", "\n")
    path.write_text(before + tail, encoding="utf-8")


def install_clean_js_tail() -> None:
    path = ROOT / "static/js/kayi-next.js"
    text = path.read_text(encoding="utf-8")
    if JS_MARKER not in text:
        raise RuntimeError("Malformed KAYI Next hardening tail marker is missing")
    prefix = text.split(JS_MARKER, 1)[0].rstrip()
    if prefix.endswith("//"):
        prefix = prefix[:-2].rstrip()
    while prefix.endswith("\\n") or prefix.endswith("\\r"):
        prefix = prefix[:-2].rstrip()
    clean = (ROOT / "overlays/ui_regression/kayi-next-hardening.js").read_text(encoding="utf-8").strip()
    path.write_text(prefix + "\n\n" + clean + "\n", encoding="utf-8")


def dataset_name(attribute: str) -> str:
    parts = attribute.removeprefix("data-").split("-")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def has_js_reference(tag: str, handler_corpus: str) -> bool:
    id_match = re.search(r"\bid\s*=\s*['\"]([^'\"]+)['\"]", tag, flags=re.IGNORECASE)
    if id_match and id_match.group(1) in handler_corpus:
        return True
    data_attrs = re.findall(r"\b(data-[a-z0-9_-]+)(?:\s*=|\s|>)", tag.lower())
    for attribute in data_attrs:
        camel = dataset_name(attribute)
        if attribute in handler_corpus or f"dataset.{camel}" in handler_corpus:
            return True
    class_match = re.search(r"\bclass\s*=\s*['\"]([^'\"]+)['\"]", tag, flags=re.IGNORECASE)
    if class_match:
        generic = {
            "btn", "button", "active", "selected", "primary", "secondary", "small",
            "btn-primary", "btn-secondary", "btn-small", "nx-btn", "nx-btn-primary",
            "nx-btn-ghost", "form-control",
        }
        for token in class_match.group(1).split():
            if token in generic or token.startswith("btn-") or token.startswith("nx-btn"):
                continue
            if token in handler_corpus:
                return True
    return False


def inside_script(text: str, offset: int) -> bool:
    open_pos = text.rfind("<script", 0, offset)
    close_pos = text.rfind("</script", 0, offset)
    return open_pos > close_pos


def audit_buttons() -> None:
    failures: list[str] = []
    static_js = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "static" / "js").rglob("*.js"))
    template_paths = sorted((ROOT / "templates").rglob("*.html"))
    # Inline scripts are real handlers too. Include all template source in the
    # reference corpus, while excluding button-like HTML strings *inside* script
    # tags from the server-rendered button inventory.
    template_corpus = "\n".join(path.read_text(encoding="utf-8") for path in template_paths)
    handler_corpus = static_js + "\n" + template_corpus
    for path in template_paths:
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"<button\b[^>]*>", text, flags=re.IGNORECASE):
            if inside_script(text, match.start()):
                continue
            tag = match.group(0)
            if not re.search(r"\btype\s*=\s*['\"]button['\"]", tag, flags=re.IGNORECASE):
                continue
            lowered = tag.lower()
            if " disabled" in lowered or "onclick=" in lowered or "nx-item-remove" in lowered:
                continue
            if has_js_reference(tag, handler_corpus):
                continue
            line = text.count("\n", 0, match.start()) + 1
            failures.append(f"{path.relative_to(ROOT)}:{line}: {tag[:200]}")
    if failures:
        raise RuntimeError("Visible type=button controls without a JavaScript/inline binding were found:\n" + "\n".join(failures[:60]))


def check_js_syntax() -> None:
    node = shutil.which("node")
    if not node:
        print("Node not installed on this host; browser CI remains the JavaScript syntax gate.")
        return
    target = ROOT / "static/js/kayi-next.js"
    result = subprocess.run([node, "--check", str(target)], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("kayi-next.js syntax check failed:\n" + result.stdout + result.stderr)


runpy.run_path(str(ROOT / "scripts" / "document_position_runtime_fallback.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "static_cache_bust_hardening.py"), run_name="__main__")
runpy.run_path(str(ROOT / "scripts" / "ai_service_coverage_hardening.py"), run_name="__main__")
normalize_css_tail("static/css/kayi-next.css")
install_clean_js_tail()

css_path = ROOT / "static/css/kayi-next.css"
css = css_path.read_text(encoding="utf-8")
if GENERIC_CHECKBOX_MARKER not in css:
    css += '''
/* KAYI global checkbox size contract */
.nx-content input[type="checkbox"]{width:20px!important;height:20px!important;min-width:20px!important;min-height:20px!important;max-width:20px!important;max-height:20px!important;padding:0!important;margin:0!important;box-shadow:none!important;accent-color:var(--nx-accent);cursor:pointer}
.nx-content select[multiple]{min-height:96px;max-height:132px}
'''
    css_path.write_text(css, encoding="utf-8")

js = (ROOT / "static/js/kayi-next.js").read_text(encoding="utf-8")
base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
editor = (ROOT / "templates/rebuild/document_editor.html").read_text(encoding="utf-8")
ai = (ROOT / "erp/services/ai.py").read_text(encoding="utf-8")
if "\\n.nx-checkbox-input" in css:
    raise RuntimeError("UI hardening CSS still contains escaped line separators")
if ".nx-checkbox-input" not in css or 'input[type="checkbox"]' not in css or "dataset.nxAddBound" not in js:
    raise RuntimeError("UI hardening assets are incomplete")
if "?v=20260810-6" not in base or "KAYI document position runtime fallback 20260810" not in editor:
    raise RuntimeError("KAYI runtime/cache fallback contract is incomplete")
if "Fliesen-, Platten- oder Belagsposition" not in ai or "Coverage-Prinzip" not in ai:
    raise RuntimeError("AI explicit-trade coverage contract is incomplete")

check_js_syntax()
audit_buttons()
print("KAYI UI hardening assets, runtime fallbacks, AI coverage, app-wide button bindings and JavaScript syntax verified.")
