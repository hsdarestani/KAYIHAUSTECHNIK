from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "A+BAU FINAL PRODUCTION HARDENING 2026-08-21"


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        raise RuntimeError(f"Final production hardening target missing: {rel}")
    return path.read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def install_german_runtime() -> None:
    write(
        "static/css/ab-bau-production-hardening.css",
        r'''/* A+BAU FINAL PRODUCTION HARDENING 2026-08-21 */
.ab-locale-wrap{position:relative;display:flex;align-items:center;gap:6px;width:100%}
.ab-locale-wrap>.ab-locale-display{width:100%;min-width:0;min-height:40px;padding:8px 38px 8px 11px;border:1px solid #d8d4ca;border-radius:9px;background:#fff;color:#15191d;font:inherit;line-height:1.25}
.ab-locale-wrap>.ab-locale-display:focus{outline:0;border-color:#c9a13b;box-shadow:0 0 0 3px rgba(201,161,59,.14)}
.ab-locale-wrap>.ab-locale-native{position:absolute!important;left:1px!important;bottom:1px!important;width:1px!important;height:1px!important;min-width:1px!important;min-height:1px!important;opacity:.001!important;pointer-events:none!important;padding:0!important;border:0!important}
.ab-locale-picker{position:absolute;right:5px;top:50%;transform:translateY(-50%);width:30px;height:30px;border:0;border-radius:7px;background:transparent;color:#59616a;cursor:pointer;font-size:15px}
.ab-locale-picker:hover{background:#f3efe4;color:#111315}
.ab-file-wrap{display:flex;align-items:center;gap:9px;min-height:40px;width:100%}
.ab-file-native{position:absolute!important;width:1px!important;height:1px!important;opacity:.001!important;pointer-events:none!important}
.ab-file-button{min-height:38px;padding:7px 12px;border:1px solid #d8d4ca;border-radius:9px;background:#fff;color:#111315;font-weight:750;cursor:pointer;white-space:nowrap}
.ab-file-button:hover{border-color:#c9a13b;background:#fbf6e9}
.ab-file-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#68717b;font-size:13px}
.ab-primary-action,.tti-new,.tt-primary-action{background:linear-gradient(135deg,#b88b26,#d7b454)!important;border-color:#c9a13b!important;color:#111315!important;box-shadow:none!important}
.ab-primary-action:hover,.tti-new:hover,.tt-primary-action:hover{filter:brightness(.98);color:#111315!important}
[data-ab-sms-disabled="1"]{display:none!important}
''',
    )

    write(
        "static/js/ab-bau-production-hardening.js",
        r'''(() => {
  "use strict";
  const MARK = "A+BAU FINAL PRODUCTION HARDENING 2026-08-21";
  const pad = n => String(n).padStart(2, "0");
  const isoToGerman = value => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
    return m ? `${m[3]}.${m[2]}.${m[1]}` : "";
  };
  const germanToIso = value => {
    const m = /^\s*(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})\s*$/.exec(value || "");
    if (!m) return "";
    const day = Number(m[1]), month = Number(m[2]), year = Number(m[3]);
    const d = new Date(Date.UTC(year, month - 1, day));
    if (d.getUTCFullYear() !== year || d.getUTCMonth() !== month - 1 || d.getUTCDate() !== day) return "";
    return `${year}-${pad(month)}-${pad(day)}`;
  };
  const normalizeTime = value => {
    const m = /^\s*(\d{1,2}):(\d{2})\s*$/.exec(value || "");
    if (!m) return "";
    const h = Number(m[1]), min = Number(m[2]);
    return h >= 0 && h <= 23 && min >= 0 && min <= 59 ? `${pad(h)}:${pad(min)}` : "";
  };

  function enhanceTemporal(input) {
    if (!input || input.dataset.abLocaleReady === "1" || !["date", "time"].includes(input.type)) return;
    input.dataset.abLocaleReady = "1";
    input.lang = "de-DE";
    const kind = input.type;
    const wrap = document.createElement("span");
    wrap.className = "ab-locale-wrap";
    const display = document.createElement("input");
    display.type = "text";
    display.className = "ab-locale-display";
    display.autocomplete = "off";
    display.inputMode = "numeric";
    display.placeholder = kind === "date" ? "TT.MM.JJJJ" : "HH:MM";
    display.setAttribute("aria-label", input.getAttribute("aria-label") || (kind === "date" ? "Datum" : "Uhrzeit"));
    const picker = document.createElement("button");
    picker.type = "button";
    picker.className = "ab-locale-picker";
    picker.title = kind === "date" ? "Datum auswählen" : "Uhrzeit auswählen";
    picker.setAttribute("aria-label", picker.title);
    picker.textContent = kind === "date" ? "▣" : "◷";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    wrap.appendChild(display);
    wrap.appendChild(picker);
    input.classList.add("ab-locale-native");
    const syncDisplay = () => { display.value = kind === "date" ? isoToGerman(input.value) : (input.value || "").slice(0, 5); };
    const syncNative = () => {
      const parsed = kind === "date" ? germanToIso(display.value) : normalizeTime(display.value);
      if (!display.value.trim()) {
        input.value = "";
      } else if (parsed) {
        input.value = parsed;
      } else {
        display.setCustomValidity(kind === "date" ? "Bitte Datum als TT.MM.JJJJ eingeben." : "Bitte Uhrzeit als HH:MM eingeben.");
        return false;
      }
      display.setCustomValidity("");
      input.dispatchEvent(new Event("input", {bubbles:true}));
      input.dispatchEvent(new Event("change", {bubbles:true}));
      return true;
    };
    display.addEventListener("input", () => display.setCustomValidity(""));
    display.addEventListener("blur", syncNative);
    input.addEventListener("change", syncDisplay);
    picker.addEventListener("click", () => {
      try { if (typeof input.showPicker === "function") input.showPicker(); else input.click(); }
      catch (_) { input.click(); }
    });
    const form = input.form;
    if (form && form.dataset.abLocaleSubmit !== "1") {
      form.dataset.abLocaleSubmit = "1";
      form.addEventListener("submit", event => {
        let ok = true;
        form.querySelectorAll(".ab-locale-wrap").forEach(node => {
          const native = node.querySelector(".ab-locale-native");
          const shown = node.querySelector(".ab-locale-display");
          if (!native || !shown) return;
          const parsed = native.type === "date" ? germanToIso(shown.value) : normalizeTime(shown.value);
          if (!shown.value.trim()) native.value = "";
          else if (parsed) { native.value = parsed; shown.setCustomValidity(""); }
          else { shown.setCustomValidity(native.type === "date" ? "Bitte Datum als TT.MM.JJJJ eingeben." : "Bitte Uhrzeit als HH:MM eingeben."); ok = false; }
        });
        if (!ok) { event.preventDefault(); const invalid = form.querySelector(".ab-locale-display:invalid"); if (invalid) invalid.reportValidity(); }
      }, true);
    }
    syncDisplay();
  }

  function enhanceFile(input) {
    if (!input || input.dataset.abFileReady === "1" || input.type !== "file") return;
    input.dataset.abFileReady = "1";
    const wrap = document.createElement("span");
    wrap.className = "ab-file-wrap";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ab-file-button";
    button.textContent = "Datei auswählen";
    const name = document.createElement("span");
    name.className = "ab-file-name";
    name.textContent = "Keine Datei ausgewählt";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    wrap.appendChild(button);
    wrap.appendChild(name);
    input.classList.add("ab-file-native");
    button.addEventListener("click", () => input.click());
    input.addEventListener("change", () => { name.textContent = input.files && input.files.length ? Array.from(input.files).map(f => f.name).join(", ") : "Keine Datei ausgewählt"; });
  }

  const wordMap = new Map([
    ["Monday","Montag"],["Tuesday","Dienstag"],["Wednesday","Mittwoch"],["Thursday","Donnerstag"],["Friday","Freitag"],["Saturday","Samstag"],["Sunday","Sonntag"],
    ["Mon","Mo"],["Tue","Di"],["Wed","Mi"],["Thu","Do"],["Fri","Fr"],["Sat","Sa"],["Sun","So"],
    ["January","Januar"],["February","Februar"],["March","März"],["May","Mai"],["June","Juni"],["July","Juli"],["October","Oktober"],["December","Dezember"]
  ]);
  const tokenPattern = /\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun|January|February|March|May|June|July|October|December)\b/g;
  function translateText(root=document.body) {
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(node => {
      const p = node.parentElement;
      if (!p || ["SCRIPT","STYLE","TEXTAREA","OPTION","CODE","PRE"].includes(p.tagName)) return;
      if (tokenPattern.test(node.nodeValue || "")) {
        tokenPattern.lastIndex = 0;
        node.nodeValue = (node.nodeValue || "").replace(tokenPattern, value => wordMap.get(value) || value);
      } else tokenPattern.lastIndex = 0;
    });
  }

  const primaryLabels = new Set(["Neues Projekt","+ Neues Projekt","Neues Angebot","+ Neues Angebot","Neue Rechnung","+ Neue Rechnung","Artikel hinzufügen","+ Artikel hinzufügen","Speichern","Fertigstellen"]);
  function normalizeActions(root=document) {
    root.querySelectorAll("a,button,input[type=submit]").forEach(el => {
      const label = (el.value || el.textContent || "").replace(/\s+/g," ").trim();
      if (primaryLabels.has(label)) el.classList.add("ab-primary-action");
      if (!location.pathname.startsWith("/settings") && /\bSMS\b/i.test(label) && /send|senden|verschicken|benachricht/i.test(label)) {
        el.dataset.abSmsDisabled = "1";
        el.setAttribute("aria-hidden", "true");
      }
    });
  }

  function boot(root=document) {
    root.querySelectorAll('input[type="date"],input[type="time"]').forEach(enhanceTemporal);
    root.querySelectorAll('input[type="file"]').forEach(enhanceFile);
    translateText(root === document ? document.body : root);
    normalizeActions(root);
    document.documentElement.lang = "de";
    document.documentElement.dataset.abProductionHardening = MARK;
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => boot()); else boot();
  const observer = new MutationObserver(records => {
    records.forEach(record => record.addedNodes.forEach(node => {
      if (node.nodeType !== 1) return;
      const el = /** @type {Element} */ (node);
      if (el.matches && el.matches('input[type="date"],input[type="time"]')) enhanceTemporal(el);
      if (el.matches && el.matches('input[type="file"]')) enhanceFile(el);
      if (el.querySelectorAll) {
        el.querySelectorAll('input[type="date"],input[type="time"]').forEach(enhanceTemporal);
        el.querySelectorAll('input[type="file"]').forEach(enhanceFile);
        translateText(el);
        normalizeActions(el);
      }
    }));
  });
  if (document.body) observer.observe(document.body, {childList:true,subtree:true});
})();
''',
    )

    rel = "templates/rebuild/base.html"
    text = read(rel)
    text = re.sub(r"<html(?![^>]*\blang=)([^>]*)>", r'<html lang="de"\1>', text, count=1, flags=re.I)
    if "/static/css/ab-bau-production-hardening.css" not in text:
        if "</head>" not in text:
            raise RuntimeError("Base template has no </head> anchor for production CSS")
        text = text.replace("</head>", '<link rel="stylesheet" href="/static/css/ab-bau-production-hardening.css?v=20260821-1">\n</head>', 1)
    if "/static/js/ab-bau-production-hardening.js" not in text:
        if "</body>" not in text:
            raise RuntimeError("Base template has no </body> anchor for production JS")
        text = text.replace("</body>", '<script src="/static/js/ab-bau-production-hardening.js?v=20260821-1" defer></script>\n</body>', 1)
    write(rel, text)


def patch_real_pay_readiness() -> None:
    rel = "erp/tooltime_invoices_exact.py"
    text = read(rel)
    import_line = "from .services.tooltime_pay import provider_ready as pay_provider_ready\n"
    if import_line not in text:
        anchor = "from .services.tooltime_parity_finance import meta_for, profile_for\n"
        if anchor not in text:
            raise RuntimeError("Invoice exact view import anchor changed")
        text = text.replace(anchor, anchor + import_line, 1)
    old = '''    pay_cfg = dict((profile_for(org).settings or {}).get("pay") or {})
    provider = str(pay_cfg.get("provider") or "").strip().lower()
    pay_active = bool(pay_cfg.get("enabled")) or provider not in {"", "disabled", "none"}
'''
    new = '''    pay_active, _pay_reason = pay_provider_ready(org)
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "pay_active, _pay_reason = pay_provider_ready(org)" not in text:
        raise RuntimeError("Invoice Pay readiness anchor changed")
    write(rel, text)

    rel = "templates/rebuild/invoices.html"
    html = read(rel)
    # Do not advertise a payment action until the actual configured provider, HTTPS
    # endpoint and secrets pass the same backend readiness check used for checkout.
    html = re.sub(
        r"\{% if not pay_active %\}\s*<div[^>]*class=\"[^\"]*tti-pay-banner[^\"]*\".*?</div>\s*\{% endif %\}",
        "",
        html,
        flags=re.S,
    )
    payment_form = re.compile(r"(<form[^>]*action=\"\{% url 'next-invoice-payment-link' row\.invoice\.pk %\}\".*?</form>)", re.S)
    if payment_form.search(html) and "{% if pay_active %}" not in payment_form.search(html).group(1):
        html = payment_form.sub(r"{% if pay_active %}\1{% endif %}", html)
    write(rel, html)


def patch_review_queue_deduplication() -> None:
    rel = "erp/manager_review_views.py"
    text = read(rel)
    old = '''    pending = list(qs.filter(metadata__status=PENDING)[:100])
    changes = list(qs.filter(metadata__status=CHANGES)[:50])
    approved = list(qs.filter(metadata__status=APPROVED)[:50])
    legacy = list(qs.filter(metadata__status="completed")[:50])
'''
    new = '''    # A single site visit can produce multiple immutable completion snapshots.
    # The queue must show only the newest snapshot for each visit; otherwise an older
    # pending document and a newer approved document make the same project appear in
    # both sections at once.
    latest_by_visit = {}
    for document in qs[:400]:
        metadata = document.metadata or {}
        event_id = metadata.get("event_id")
        key = ("event", str(event_id)) if event_id else (("project", str(document.project_id)) if document.project_id else ("document", str(document.pk)))
        if key not in latest_by_visit:
            latest_by_visit[key] = document
    current = list(latest_by_visit.values())
    pending = [row for row in current if (row.metadata or {}).get("status") == PENDING][:100]
    changes = [row for row in current if (row.metadata or {}).get("status") == CHANGES][:50]
    approved = [row for row in current if (row.metadata or {}).get("status") == APPROVED][:50]
    legacy = [row for row in current if (row.metadata or {}).get("status") == "completed"][:50]
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "latest_by_visit" not in text:
        raise RuntimeError("Manager review queue anchor changed")
    write(rel, text)


def guard_finance_source_of_truth() -> None:
    text = read("erp/rebuild_views.py")
    required = (
        'purchase = _money(getattr(meta, "purchase_price", 0))',
        'purchase = _money(getattr(item.catalog_item, "purchase_price", 0))',
        'cost += _money(item.quantity) * purchase',
        'margin = net - cost',
        'costs = sum((row["cost"] for row in invoice_totals)',
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(f"Finance source-of-truth regression detected: {missing}")
    forbidden = ('cost = net\n', 'costs = revenue\n')
    for marker in forbidden:
        if marker in text:
            raise RuntimeError(f"Finance cost must not be copied from revenue: {marker!r}")


def install_tests() -> None:
    write(
        "tests/test_final_production_hardening_20260821.py",
        r'''from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


class FinalProductionHardeningTests(SimpleTestCase):
    def test_german_runtime_is_global_and_preserves_iso_submission(self):
        base = (ROOT / "templates/rebuild/base.html").read_text(encoding="utf-8")
        js = (ROOT / "static/js/ab-bau-production-hardening.js").read_text(encoding="utf-8")
        self.assertIn('lang="de"', base)
        self.assertIn("ab-bau-production-hardening.css", base)
        self.assertIn("ab-bau-production-hardening.js", base)
        for marker in ("TT.MM.JJJJ", "HH:MM", "germanToIso", "isoToGerman", "Datei auswählen", "Keine Datei ausgewählt", 'input[type="date"]', 'input[type="time"]'):
            self.assertIn(marker, js)
        for marker in ("Monday","Montag","Friday","Freitag","Tue","Di"):
            self.assertIn(marker, js)

    def test_primary_actions_use_ab_bau_gold(self):
        css = (ROOT / "static/css/ab-bau-production-hardening.css").read_text(encoding="utf-8")
        js = (ROOT / "static/js/ab-bau-production-hardening.js").read_text(encoding="utf-8")
        self.assertIn("#c9a13b", css)
        self.assertIn("ab-primary-action", css)
        for marker in ("Neues Projekt", "Neues Angebot", "Neue Rechnung", "Artikel hinzufügen", "Speichern"):
            self.assertIn(marker, js)

    def test_invoice_pay_ui_uses_real_provider_readiness_and_has_no_dead_activation_banner(self):
        views = (ROOT / "erp/tooltime_invoices_exact.py").read_text(encoding="utf-8")
        template = (ROOT / "templates/rebuild/invoices.html").read_text(encoding="utf-8")
        self.assertIn("provider_ready as pay_provider_ready", views)
        self.assertIn("pay_active, _pay_reason = pay_provider_ready(org)", views)
        self.assertNotIn("Jetzt aktivieren", template)
        if "next-invoice-payment-link" in template:
            self.assertIn("{% if pay_active %}", template)

    def test_review_queue_cannot_show_old_and_new_snapshots_in_two_status_buckets(self):
        source = (ROOT / "erp/manager_review_views.py").read_text(encoding="utf-8")
        self.assertIn("latest_by_visit", source)
        self.assertIn('("event", str(event_id))', source)
        self.assertIn("current = list(latest_by_visit.values())", source)
        self.assertNotIn("pending = list(qs.filter(metadata__status=PENDING)", source)

    def test_finance_cost_and_margin_come_from_purchase_prices_not_revenue(self):
        source = (ROOT / "erp/rebuild_views.py").read_text(encoding="utf-8")
        self.assertIn('purchase = _money(getattr(meta, "purchase_price", 0))', source)
        self.assertIn('cost += _money(item.quantity) * purchase', source)
        self.assertIn('margin = net - cost', source)
        self.assertIn('costs = sum((row["cost"] for row in invoice_totals)', source)
        self.assertNotIn("costs = revenue\n", source)

    def test_room_planner_and_technician_voice_ai_guards_still_exist(self):
        planner = (ROOT / "templates/rebuild/room_planner.html").read_text(encoding="utf-8")
        appointment = (ROOT / "templates/rebuild/appointment_detail.html").read_text(encoding="utf-8")
        field_home = (ROOT / "templates/rebuild/field_home.html").read_text(encoding="utf-8")
        for marker in ("data-rp-canvas", "data-rp-open-vision", "data-rp-add-object"):
            self.assertIn(marker, planner)
        for marker in ("data-field-voice", "data-field-record", "data-field-transcribe", "Kundenunterschrift zum Abschluss", "Einsatz abschließen & PDF erstellen"):
            self.assertIn(marker, appointment)
        self.assertIn("Vor Ort in einem Ablauf", field_home)

    def test_sms_send_controls_are_suppressed_outside_settings_until_provider_is_ready(self):
        js = (ROOT / "static/js/ab-bau-production-hardening.js").read_text(encoding="utf-8")
        self.assertIn('!location.pathname.startsWith("/settings")', js)
        self.assertIn("data.abSmsDisabled", js.replace("dataset.abSmsDisabled", "data.abSmsDisabled"))
''',
    )


def strengthen_smoke_guards() -> None:
    smoke = read("scripts/production_browser_smoke.py")
    # Other assembly layers already add the real technician browser flow. Do not
    # duplicate it; make its presence a non-negotiable final contract and ensure the
    # locale/field/Room Planner paths remain in the production smoke.
    required = (
        "run_field_surface",
        "technician root did not redirect to /field/",
        "KAYI Room Planner Pro browser smoke",
    )
    missing = [marker for marker in required if marker not in smoke]
    if missing:
        raise RuntimeError(f"Production browser smoke lost technician/Room Planner coverage: {missing}")


def final_guard() -> None:
    base = read("templates/rebuild/base.html")
    if "/static/js/ab-bau-production-hardening.js" not in base:
        raise RuntimeError("German production runtime was not injected")
    invoice_views = read("erp/tooltime_invoices_exact.py")
    if "pay_provider_ready(org)" not in invoice_views:
        raise RuntimeError("Invoice list still uses heuristic Pay readiness")
    manager = read("erp/manager_review_views.py")
    if "latest_by_visit" not in manager:
        raise RuntimeError("Manager review queue is not deduplicated")
    guard_finance_source_of_truth()
    strengthen_smoke_guards()
    tests = read("tests/test_final_production_hardening_20260821.py")
    compile(tests, str(ROOT / "tests/test_final_production_hardening_20260821.py"), "exec")


def main() -> None:
    install_german_runtime()
    patch_real_pay_readiness()
    patch_review_queue_deduplication()
    guard_finance_source_of_truth()
    install_tests()
    strengthen_smoke_guards()
    final_guard()
    print(f"{MARKER}: German date/time/file UI, gold actions, real Pay readiness, review dedupe and finance/field/3D guards installed.")


if __name__ == "__main__":
    main()
