from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "erp" / "tooltime_parity_views.py"
text = path.read_text(encoding="utf-8")

if "HttpResponseBadRequest" in text and "from django.http import HttpResponseBadRequest" not in text:
    if "from django.http import" in text:
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("from django.http import "):
                if "HttpResponseBadRequest" not in line:
                    lines[index] = line + ", HttpResponseBadRequest"
                text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
                break
    else:
        anchor = "from django.contrib import messages\n"
        if anchor not in text:
            raise RuntimeError("Phase 1 import anchor for django.http missing")
        text = text.replace(anchor, anchor + "from django.http import HttpResponseBadRequest\n", 1)

if "@require_POST" in text and "require_POST" not in "\n".join(line for line in text.splitlines() if line.startswith("from django.views.decorators.http import")):
    if "from django.views.decorators.http import " in text:
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("from django.views.decorators.http import "):
                if "require_POST" not in line:
                    lines[index] = line + ", require_POST"
                text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
                break
    else:
        anchor = "from django.http import HttpResponseBadRequest\n"
        if anchor not in text:
            raise RuntimeError("Phase 1 import anchor for require_POST missing")
        text = text.replace(anchor, anchor + "from django.views.decorators.http import require_POST\n", 1)

for needle in ("from django.http import", "HttpResponseBadRequest", "require_POST"):
    if needle not in text:
        raise RuntimeError(f"Phase 1 required import missing after patch: {needle}")

path.write_text(text, encoding="utf-8")
compile(text, str(path), "exec")
print("ToolTime Phase 1 imports installed: POST-only template actions and bad-request handling are available.")
