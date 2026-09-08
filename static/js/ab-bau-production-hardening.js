(() => {
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
