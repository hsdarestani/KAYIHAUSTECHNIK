from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONSENT = (
    "        profile = self.user.profile\n"
    "        prefs = dict(profile.preferences or {})\n"
    "        prefs.update({\"ai_third_party_consent_at\": \"2026-08-10T00:00:00+00:00\", \"ai_third_party_consent_version\": \"2026-08-10\", \"ai_third_party_consent_revoked_at\": None})\n"
    "        profile.preferences = prefs\n"
    "        profile.save(update_fields=[\"preferences\", \"updated_at\"])\n"
)

TARGETS = {
    "tests/test_ai_resilience.py": (
        "test_ai_chat_does_not_leak_provider_error",
        "test_photo_api_does_not_leak_provider_error",
    ),
    "tests/test_v2.py": (
        "test_ai_photo_analysis_never_skips_human_confirmation",
    ),
}

for relative, names in TARGETS.items():
    path = ROOT / relative
    if not path.exists():
        raise RuntimeError(f"Missing legacy test file: {relative}")
    text = path.read_text(encoding="utf-8")
    for name in names:
        marker = f"# KAYI_STORE_CONSENT_FOR_{name}"
        if marker in text:
            continue
        pattern = re.compile(rf"(?m)^(\s*)def {re.escape(name)}\(([^\n]*)\):\n")
        match = pattern.search(text)
        if not match:
            raise RuntimeError(f"Could not locate legacy AI test {name} in {relative}")
        indent = match.group(1) + "    "
        body = marker + "\n" + CONSENT
        body = "\n".join(indent + line if line else line for line in body.splitlines()) + "\n"
        text = text[: match.end()] + body + text[match.end() :]
    path.write_text(text, encoding="utf-8")

print("Legacy AI regression tests updated for explicit store consent without bypassing the production gate.")
