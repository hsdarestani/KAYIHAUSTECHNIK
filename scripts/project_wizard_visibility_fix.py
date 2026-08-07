from pathlib import Path
import re


VERSION = "20260807-1945"
CACHE_NAME = "kayi-shell-v18-20260807"


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Expected project-wizard source fragment not found in {path}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_regex_once(path: str, pattern: str, replacement: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if replacement in text:
        return
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"Expected one project-wizard cache fragment in {path}, found {count}")
    target.write_text(updated, encoding="utf-8")


# Step 3 received a layout class in the B&O project-basics change. The original
# rule set display:grid on that class, which appears later than .wizard-step and
# therefore overrode display:none for the inactive pane. Keep the layout gap on
# the step, but only enable the grid display while the step is actually active.
replace_once(
    "static/css/app.css",
    ".wizard-project-basics{display:grid;gap:18px}",
    ".wizard-project-basics{gap:18px}.wizard-step.wizard-project-basics.active{display:grid}",
)

# Force installed PWAs and normal browsers to take the corrected stylesheet
# immediately instead of reusing the v17 shell.
replace_regex_once(
    "templates/erp/base.html",
    r'href="\{% static \'css/app\.css\' %\}(?:\?v=[^"]*)?"',
    f'href="{{% static \'css/app.css\' %}}?v={VERSION}"',
)
replace_regex_once(
    "templates/erp/base.html",
    r'src="\{% static \'js/app\.js\' %\}(?:\?v=[^"]*)?"',
    f'src="{{% static \'js/app.js\' %}}?v={VERSION}"',
)
replace_regex_once(
    "static/js/app.js",
    r'navigator\.serviceWorker\.register\("/sw\.js(?:\?v=[^"]*)?",\s*\{[^}]*scope:\s*"/"[^}]*\}\)\.then\(\(registration\)\s*=>\s*registration\.update\(\)\)\.catch\(\(\)\s*=>\s*\{\}\)',
    f'navigator.serviceWorker.register("/sw.js?v={VERSION}", {{scope: "/", updateViaCache: "none"}}).then((registration) => registration.update()).catch(() => {{}})',
)
replace_regex_once(
    "static/js/sw.js",
    r'const CACHE = "[^"]+";',
    f'const CACHE = "{CACHE_NAME}";',
)
replace_regex_once(
    "static/js/sw.js",
    r'const ASSETS = \[[^\n]+\];',
    f'const ASSETS = ["/static/css/app.css?v={VERSION}", "/static/js/app.js?v={VERSION}", "/static/manifest.webmanifest", "/privacy/", "/terms/"];',
)

# Build-time regression guard: the wizard must have nine panes, only pane 1 may
# start active, and no inactive project-basics selector may set display again.
css = Path("static/css/app.css").read_text(encoding="utf-8")
template = Path("templates/erp/project_wizard.html").read_text(encoding="utf-8")

if ".wizard-step{display:none" not in css:
    raise RuntimeError("Project wizard no longer has a default hidden state")
if ".wizard-step.active{display:block" not in css:
    raise RuntimeError("Project wizard no longer has the normal active state")
if re.search(r"\.wizard-project-basics\{[^}]*display\s*:", css):
    raise RuntimeError("Inactive project basics still overrides wizard-step visibility")
if ".wizard-step.wizard-project-basics.active{display:grid}" not in css:
    raise RuntimeError("Active project basics grid rule is missing")

step_tags = re.findall(
    r'<section class="([^"]*\bwizard-step\b[^"]*)" data-step="([1-9])">',
    template,
)
if len(step_tags) != 9 or [number for classes, number in step_tags if "active" in classes.split()] != ["1"]:
    raise RuntimeError(f"Unexpected project wizard pane structure: {step_tags!r}")

print("Project wizard visibility regression guard passed.")
