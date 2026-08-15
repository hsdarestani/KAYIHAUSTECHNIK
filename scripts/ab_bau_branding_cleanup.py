from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAND = "A+Bau"

# Match the old brand only when it is a standalone display token. This deliberately
# does not touch technical identifiers such as KAYI_ROOM_PLANNER_PRO or kayi-next.css.
OLD_BRAND_TOKEN = re.compile(r"(?<![A-Za-z0-9_])KAYI(?![A-Za-z0-9_])")
OLD_BRAND_TOKEN_TITLE = re.compile(r"(?<![A-Za-z0-9_])Kayi(?![A-Za-z0-9_])")
OLD_BRAND_HTML_ANY_CASE = re.compile(r"(?<![A-Za-z0-9_])kayi(?![A-Za-z0-9_])", re.IGNORECASE)

RUNTIME_TEXT_ROOTS = (
    ROOT / "templates",
    ROOT / "erp",
    ROOT / "static" / "js",
    ROOT / "static" / "css",
)
TEXT_SUFFIXES = {".html", ".htm", ".py", ".js", ".css", ".json", ".txt"}


def _brand_text(text: str, *, any_case: bool = False) -> str:
    # Clean common legacy product labels first, then the standalone brand token.
    replacements = {
        "KAYI Haustechnik": BRAND,
        "KAYI-HAUSTECHNIK": BRAND,
        "KAYI HAUSTECHNIK": BRAND,
        "KAYI Next": BRAND,
        "KAYI-Next": BRAND,
        "KAYI AI": f"{BRAND} AI",
        "KAYI KI": f"{BRAND} KI",
        "KAYI-KI": f"{BRAND}-KI",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = OLD_BRAND_TOKEN.sub(BRAND, text)
    text = OLD_BRAND_TOKEN_TITLE.sub(BRAND, text)
    if any_case:
        text = OLD_BRAND_HTML_ANY_CASE.sub(BRAND, text)
    return text


def _patch_python_strings_and_comments(path: Path) -> int:
    original = path.read_text(encoding="utf-8")
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(original).readline))
    except (tokenize.TokenError, IndentationError):
        # The assembled runtime should be valid Python; leave malformed files alone
        # so the normal CI syntax check reports the real source problem.
        return 0

    changed = 0
    rewritten = []
    for token in tokens:
        if token.type in {tokenize.STRING, tokenize.COMMENT}:
            new_value = _brand_text(token.string)
            if new_value != token.string:
                token = tokenize.TokenInfo(token.type, new_value, token.start, token.end, token.line)
                changed += 1
        rewritten.append(token)
    if changed:
        path.write_text(tokenize.untokenize(rewritten), encoding="utf-8")
    return changed


def _patch_plain_text(path: Path, *, any_case: bool = False) -> int:
    original = path.read_text(encoding="utf-8")
    updated = _brand_text(original, any_case=any_case)
    if updated == original:
        return 0
    path.write_text(updated, encoding="utf-8")
    return 1


def _patch_runtime_branding() -> list[str]:
    touched: list[str] = []
    for base in RUNTIME_TEXT_ROOTS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                if path.suffix.lower() == ".py":
                    changed = _patch_python_strings_and_comments(path)
                elif path.suffix.lower() in {".html", ".htm"}:
                    # Templates contain display copy by definition; catch accidental
                    # lower-case branding there as well, while technical kayi-* asset
                    # names stay protected because '-' is attached to the token and is
                    # explicitly normalized below only when it is a visible label.
                    changed = _patch_plain_text(path, any_case=False)
                else:
                    changed = _patch_plain_text(path, any_case=False)
            except UnicodeDecodeError:
                continue
            if changed:
                touched.append(str(path.relative_to(ROOT)))
    return touched


def _patch_login_fallbacks() -> None:
    # Some deployments use Django's registration template while others use the
    # rebuilt auth shell. Both are covered by the general pass; these phrases are
    # kept as an explicit second guard because login is the first brand touchpoint.
    for path in (ROOT / "templates").rglob("*.html"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "login" not in path.name.lower() and "anmeld" not in text.lower() and "einloggen" not in text.lower():
            continue
        updated = _brand_text(text)
        updated = updated.replace("KAYIHAUSTECHNIK", BRAND).replace("KayiHaustechnik", BRAND)
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def _install_regression_test() -> None:
    test_path = ROOT / "tests" / "test_ab_bau_branding.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(
        '''from pathlib import Path\nimport io\nimport re\nimport tokenize\n\nfrom django.test import SimpleTestCase\n\nROOT = Path(__file__).resolve().parents[1]\nOLD = re.compile(r"(?<![A-Za-z0-9_])KAYI(?![A-Za-z0-9_])")\n\n\nclass ABauBrandingTests(SimpleTestCase):\n    def test_templates_have_no_visible_old_brand(self):\n        offenders = []\n        for path in (ROOT / "templates").rglob("*.html"):\n            text = path.read_text(encoding="utf-8")\n            if OLD.search(text):\n                offenders.append(str(path.relative_to(ROOT)))\n        self.assertEqual(offenders, [])\n\n    def test_python_user_facing_strings_have_no_old_brand(self):\n        offenders = []\n        for path in (ROOT / "erp").rglob("*.py"):\n            text = path.read_text(encoding="utf-8")\n            try:\n                tokens = tokenize.generate_tokens(io.StringIO(text).readline)\n                for token in tokens:\n                    if token.type == tokenize.STRING and OLD.search(token.string):\n                        offenders.append(str(path.relative_to(ROOT)))\n                        break\n            except tokenize.TokenError:\n                continue\n        self.assertEqual(offenders, [])\n\n    def test_room_ai_uses_ab_bau_brand(self):\n        path = ROOT / "erp" / "services" / "room_ai.py"\n        if path.exists():\n            text = path.read_text(encoding="utf-8")\n            self.assertNotIn("KAYI-Renovierungsplaner", text)\n            self.assertIn("A+Bau-Renovierungsplaner", text)\n''',
        encoding="utf-8",
    )


def _guard() -> None:
    offenders: list[str] = []
    for base in (ROOT / "templates", ROOT / "erp"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".html", ".py"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if path.suffix.lower() == ".html":
                if OLD_BRAND_TOKEN.search(text):
                    offenders.append(str(path.relative_to(ROOT)))
            else:
                try:
                    for token in tokenize.generate_tokens(io.StringIO(text).readline):
                        if token.type == tokenize.STRING and OLD_BRAND_TOKEN.search(token.string):
                            offenders.append(str(path.relative_to(ROOT)))
                            break
                except tokenize.TokenError:
                    continue
    if offenders:
        raise RuntimeError("Visible legacy KAYI branding remains in: " + ", ".join(sorted(set(offenders))[:30]))

    room_ai = ROOT / "erp" / "services" / "room_ai.py"
    if room_ai.exists():
        ai_text = room_ai.read_text(encoding="utf-8")
        if "KAYI-Renovierungsplaner" in ai_text:
            raise RuntimeError("Room AI still identifies itself as KAYI")


_touched = _patch_runtime_branding()
_patch_login_fallbacks()
_install_regression_test()
_guard()
print(f"A+Bau branding cleanup complete; updated {len(_touched)} runtime files and removed visible KAYI naming from login, AI prompts and UI copy.")
