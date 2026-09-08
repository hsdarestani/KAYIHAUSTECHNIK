(() => {
  "use strict";

  const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || document.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const readJson = async (response) => {
    const text = await response.text();
    if (!text) return {};
    try { return JSON.parse(text); }
    catch (_) {
      if (!response.ok) return {error: `Serverfehler (${response.status}). Bitte erneut versuchen.`};
      throw new Error("Ungültige Serverantwort. Bitte erneut versuchen.");
    }
  };
  const numberValue = (value) => {
    const normalized = String(value ?? "").trim().replace(/\s/g, "").replace(",", ".");
    const parsed = Number.parseFloat(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const money = new Intl.NumberFormat("de-DE", {style: "currency", currency: "EUR"});
  const decimal = new Intl.NumberFormat("de-DE", {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const compactNumber = new Intl.NumberFormat("de-DE", {maximumFractionDigits: 2});

  /* Core shell */
  const applyTheme = (theme) => {
    if (theme === "system") {
      delete document.documentElement.dataset.theme;
      localStorage.setItem("kayi-theme", "system");
      return;
    }
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("kayi-theme", theme);
  };
  const savedTheme = localStorage.getItem("kayi-theme");
  if (savedTheme && savedTheme !== "system") document.documentElement.dataset.theme = savedTheme;
  $(`[data-force-theme="${savedTheme || "light"}"]`)?.classList.add("active");
  $$("[data-force-theme]").forEach((button) => button.addEventListener("click", () => {
    $$("[data-force-theme]").forEach((item) => item.classList.toggle("active", item === button));
    applyTheme(button.dataset.forceTheme);
  }));
  $("[data-theme-toggle]")?.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
  });

  $$(".nav-item").forEach((link) => {
    const url = new URL(link.href, window.location.origin);
    const path = window.location.pathname;
    const exact = url.pathname === path;
    const resourceMatch = url.pathname.startsWith("/list/") && path.startsWith(url.pathname);
    const sectionMatch = url.pathname !== "/" && path.startsWith(url.pathname) && !url.pathname.startsWith("/projects/new/");
    link.classList.toggle("active", exact || resourceMatch || sectionMatch);
  });
  $("[data-sidebar-toggle]")?.addEventListener("click", () => $("#sidebar")?.classList.toggle("open"));
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".sidebar") && !event.target.closest("[data-sidebar-toggle]")) $("#sidebar")?.classList.remove("open");
    const toggle = event.target.closest("[data-dropdown-toggle]");
    if (toggle) toggle.closest(".dropdown")?.classList.toggle("open");
    else $$(".dropdown.open").forEach((node) => { if (!node.contains(event.target)) node.classList.remove("open"); });
    const dismiss = event.target.closest("[data-dismiss]");
    if (dismiss) dismiss.closest(".alert")?.remove();
  });
  $$("form[data-confirm]").forEach((form) => form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  }));
  window.setTimeout(() => $$(".messages .alert").forEach((node) => node.remove()), 7000);

  /* Web UI navigation must never fall through to DRF's browsable API. */
  const uiProjectUrl = (href) => {
    try {
      const url = new URL(href, window.location.origin);
      const match = url.pathname.match(/^\/api\/projects\/(\d+)\/?$/);
      if (match && url.origin === window.location.origin) return `/projects/${match[1]}/`;
    } catch (_) {}
    return href;
  };
  $$('a[href*="/api/projects/"]').forEach((link) => { link.href = uiProjectUrl(link.href); });

  /* Safe back navigation: stay inside A+Bau and never return to an API page. */
  const canUseReferrer = () => {
    try {
      const referrer = new URL(document.referrer || "", window.location.origin);
      return referrer.origin === window.location.origin && !referrer.pathname.startsWith("/api/") && referrer.href !== window.location.href;
    } catch (_) { return false; }
  };
  $$('[data-smart-back]').forEach((button) => {
    const currentIsRoot = ["/", "/app/"].includes(window.location.pathname);
    button.classList.toggle("is-visible", !currentIsRoot);
    button.addEventListener("click", () => {
      if (canUseReferrer() && window.history.length > 1) window.history.back();
      else window.location.assign(button.dataset.backFallback || "/");
    });
  });

  /* First-run tutorial; replayable from the sidebar and stored per user. */
  const tutorial = $('[data-tutorial-overlay]');
  if (tutorial) {
    const steps = [
      {icon:"⌂", title:"Willkommen bei A+Bau", text:"Der Schnellstart zeigt dir nur die wichtigsten Wege. Du kannst ihn später jederzeit über „Tutorial starten“ wiederholen.", highlight:"Dashboard & Navigation", detail:"Links findest du Projekte, Aufgaben, Termine, Material und kaufmännische Bereiche."},
      {icon:"＋", title:"Projekt sauber anlegen", text:"Der Projektassistent führt von Kunde und Mitarbeitern über Aufmaß und Leistungen bis zum Angebot.", highlight:"Neues Projekt", detail:"Bei B&O/Versicherung wählst du die passende Versicherungspreisliste – Lieferantenlisten wie JOKA gehören nur zu Material."},
      {icon:"PDF", title:"Auftrag und Kalkulation verbinden", text:"Im Bereich Angebot & Kalkulation liegt der Originalauftrag gemeinsam mit Preisliste, Aufmaß und Angebotspositionen.", highlight:"B&O-Auftrags-PDF", detail:"PDF hochladen, ausgelesene Daten prüfen und erst dann auf das Projekt übernehmen."},
      {icon:"◈", title:"3D-Modell bearbeiten", text:"Maße, Fenster, Türen, Farben und Fliesen lassen sich manuell oder per Beschreibung ändern. Jede Änderung bleibt prüfpflichtig.", highlight:"A+Bau KI Live Edit", detail:"Zum Beispiel: Fenster 1 × 1,5 m, Tür gegenüber 74 cm, beige Wände und grauer Boden, Fliesen 60 × 60 cm."},
      {icon:"✓", title:"Prüfen und freigeben", text:"A+Bau verhindert unbemerkte Nullpreise. Mitarbeiter sehen keine Preise; Angebote und Zusatzarbeiten bleiben bis zur Freigabe kontrollierbar.", highlight:"Sicherer Abschluss", detail:"Aufmaß neu berechnen, Angebot prüfen, PDF erstellen und anschließend zur Kundenfreigabe geben."},
    ];
    const userKey = tutorial.dataset.userKey || "guest";
    const storageKey = `kayi-tutorial-v2-${userKey}`;
    let index = 0;
    const renderTutorial = () => {
      const step = steps[index];
      $('[data-tutorial-title]', tutorial).textContent = step.title;
      $('[data-tutorial-text]', tutorial).textContent = step.text;
      $('[data-tutorial-icon]', tutorial).textContent = step.icon;
      $('[data-tutorial-highlight]', tutorial).textContent = step.highlight;
      $('[data-tutorial-detail]', tutorial).textContent = step.detail;
      $('[data-tutorial-progress]', tutorial).style.width = `${((index + 1) / steps.length) * 100}%`;
      const dots = $('[data-tutorial-dots]', tutorial); dots.replaceChildren();
      steps.forEach((_, dotIndex) => { const dot=document.createElement('i'); dot.classList.toggle('active', dotIndex===index); dots.append(dot); });
      $('[data-tutorial-prev]', tutorial).disabled = index === 0;
      $('[data-tutorial-next]', tutorial).textContent = index === steps.length - 1 ? "Loslegen ✓" : "Weiter →";
    };
    const openTutorial = (force = false) => {
      if (!force && localStorage.getItem(storageKey) === "done") return;
      index = 0; renderTutorial(); tutorial.hidden = false; document.body.style.overflow = "hidden";
    };
    const closeTutorial = (complete = false) => {
      if (complete) localStorage.setItem(storageKey, "done");
      tutorial.hidden = true; document.body.style.overflow = "";
    };
    $('[data-tutorial-next]', tutorial).addEventListener('click', () => { if(index < steps.length-1){index += 1; renderTutorial();} else closeTutorial(true); });
    $('[data-tutorial-prev]', tutorial).addEventListener('click', () => { if(index > 0){index -= 1; renderTutorial();} });
    $('[data-tutorial-skip]', tutorial).addEventListener('click', () => closeTutorial(true));
    $$('[data-tutorial-replay]').forEach((button) => button.addEventListener('click', () => openTutorial(true)));
    document.addEventListener('keydown', (event) => { if(event.key === 'Escape' && !tutorial.hidden) closeTutorial(false); });
    window.setTimeout(() => openTutorial(false), 450);
  }


  /* Lightweight searchable dropdowns without external dependencies */
  $$('select[data-searchable="true"]').forEach((select) => {
    if (select.dataset.searchEnhanced === "1") return;
    select.dataset.searchEnhanced = "1";
    const input = document.createElement("input");
    input.type = "search";
    input.className = "form-control select-search";
    input.placeholder = select.dataset.searchPlaceholder || "Liste durchsuchen …";
    input.autocomplete = "off";
    select.parentNode?.insertBefore(input, select);
    input.addEventListener("input", () => {
      const term = input.value.trim().toLocaleLowerCase("de");
      [...select.options].forEach((option) => {
        const keep = !term || option.textContent.toLocaleLowerCase("de").includes(term) || option.selected;
        option.hidden = !keep;
        option.disabled = !keep;
      });
    });
  });

  /* Global search */
  const searchInput = $("#globalSearch");
  const searchResults = $("#searchResults");
  let searchTimer;
  if (searchInput && searchResults) {
    searchInput.addEventListener("input", () => {
      window.clearTimeout(searchTimer);
      const q = searchInput.value.trim();
      if (q.length < 2) { searchResults.hidden = true; searchResults.replaceChildren(); return; }
      searchTimer = window.setTimeout(async () => {
        try {
          const response = await fetch(`/api/search/?q=${encodeURIComponent(q)}`, {headers: {Accept: "application/json"}});
          const data = await readJson(response);
          searchResults.replaceChildren();
          (data.results || []).forEach((result) => {
            const link = document.createElement("a");
            link.href = result.url;
            const type = document.createElement("span"); type.textContent = result.type;
            const info = document.createElement("div");
            const title = document.createElement("b"); title.textContent = result.title;
            const subtitle = document.createElement("small"); subtitle.textContent = result.subtitle || "";
            info.append(title, subtitle); link.append(type, info); searchResults.append(link);
          });
          if (!(data.results || []).length) {
            const empty = document.createElement("div"); empty.className = "empty"; empty.textContent = "Keine Treffer"; searchResults.append(empty);
          }
          searchResults.hidden = false;
        } catch (_) { searchResults.hidden = true; }
      }, 240);
    });
  }

  /* AI chat */
  const aiForm = $("#aiChatForm");
  let activeConversation = null;
  const appendChat = (role, content) => {
    const messages = $("#chatMessages");
    if (!messages) return null;
    $(".chat-welcome", messages)?.remove();
    const row = document.createElement("div"); row.className = `chat-message ${role}`;
    const avatar = document.createElement("span"); avatar.textContent = role === "user" ? "U" : "✦";
    const bubble = document.createElement("div"); bubble.className = "chat-bubble"; bubble.textContent = content;
    row.append(avatar, bubble); messages.append(row); messages.scrollTop = messages.scrollHeight;
    return bubble;
  };
  if (aiForm) {
    aiForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const input = $("#aiMessage");
      const text = input.value.trim();
      if (!text) return;
      appendChat("user", text); input.value = "";
      const pending = appendChat("assistant", "Antwort wird erstellt …");
      try {
        const response = await fetch("/api/ai/chat/", {
          method: "POST",
          headers: {"Content-Type": "application/json", "X-CSRFToken": csrf()},
          body: JSON.stringify({message: text, project_id: $("#aiProject")?.value || null, conversation_id: activeConversation}),
        });
        const data = await readJson(response);
        if (!response.ok) throw new Error(data.error || "AI-Anfrage fehlgeschlagen");
        activeConversation = data.conversation_id;
        pending.textContent = data.answer;
      } catch (error) { pending.textContent = `Fehler: ${error.message}`; }
    });
    $$('[data-prompt]').forEach((button) => button.addEventListener("click", () => { $("#aiMessage").value = button.dataset.prompt; aiForm.requestSubmit(); }));
    $("[data-new-chat]")?.addEventListener("click", () => {
      activeConversation = null;
      $("#chatMessages").replaceChildren();
      const welcome = document.createElement("div"); welcome.className = "chat-welcome";
      welcome.innerHTML = "<h2>Neue Unterhaltung</h2><p>Stellen Sie Ihre Frage mit oder ohne Projektkontext.</p>";
      $("#chatMessages").append(welcome);
    });
    $$('[data-conversation]').forEach((button) => button.addEventListener("click", () => { activeConversation = button.dataset.conversation; }));
  }

  /* Time tracking */
  const geolocation = () => new Promise((resolve) => {
    if (!navigator.geolocation) return resolve({});
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({latitude: position.coords.latitude, longitude: position.coords.longitude}),
      () => resolve({}),
      {enableHighAccuracy: true, timeout: 6000, maximumAge: 120000},
    );
  });
  $("#startTimer")?.addEventListener("click", async () => {
    const selected = $('input[name="mobile-project"]:checked');
    if (!selected) return window.alert("Bitte zuerst ein Projekt auswählen.");
    const coords = await geolocation();
    const response = await fetch("/api/time/start/", {method: "POST", headers: {"Content-Type": "application/json", "X-CSRFToken": csrf()}, body: JSON.stringify({project_id: selected.value, ...coords})});
    const data = await readJson(response);
    if (!response.ok) return window.alert(data.error || "Start nicht möglich.");
    window.location.reload();
  });
  $("#stopTimer")?.addEventListener("click", async () => {
    const note = window.prompt("Kurze Tätigkeitsbeschreibung (optional):", "") ?? "";
    const breakMinutes = window.prompt("Pausenminuten:", "0") ?? "0";
    const response = await fetch("/api/time/stop/", {method: "POST", headers: {"Content-Type": "application/json", "X-CSRFToken": csrf()}, body: JSON.stringify({description: note, break_minutes: Number.parseInt(breakMinutes, 10) || 0})});
    const data = await readJson(response);
    if (!response.ok) return window.alert(data.error || "Stop nicht möglich.");
    window.location.reload();
  });

  /* Dynamic financial formsets */
  $("[data-add-formset]")?.addEventListener("click", () => {
    const container = $(".line-items");
    if (!container) return;
    const prefix = container.dataset.formsetPrefix;
    const total = $(`#id_${prefix}-TOTAL_FORMS`);
    const forms = $$(".line-item", container);
    if (!forms.length || !total) return;
    const index = Number.parseInt(total.value, 10);
    const clone = forms[forms.length - 1].cloneNode(true);
    clone.innerHTML = clone.innerHTML.replace(new RegExp(`${prefix}-(\\d+)-`, "g"), `${prefix}-${index}-`).replace(new RegExp(`id_${prefix}-(\\d+)-`, "g"), `id_${prefix}-${index}-`);
    $$("input,textarea,select", clone).forEach((field) => {
      if (field.type === "checkbox" || field.type === "radio") field.checked = false;
      else if (field.type !== "hidden") field.value = "";
      if (field.name?.endsWith("-position")) field.value = index + 1;
      if (field.name?.endsWith("-quantity")) field.value = "1";
      if (field.name?.endsWith("-tax_rate")) field.value = "19";
    });
    container.append(clone); total.value = index + 1;
  });

  /* Shared measurement calculations */
  const updateMeasurementCalculations = (root = document) => {
    const length = numberValue($("#id_length_m", root)?.value);
    const width = numberValue($("#id_width_m", root)?.value);
    const height = numberValue($("#id_height_m", root)?.value);
    const deductions = numberValue($("#id_deductions_area_m2", root)?.value);
    const waste = numberValue($("#id_waste_percent", root)?.value);
    const floor = length * width;
    const perimeter = 2 * (length + width);
    const wall = Math.max(0, perimeter * height - deductions);
    const factor = 1 + waste / 100;
    const values = {
      floor: floor ? `${decimal.format(floor)} m²` : "–",
      wall: wall ? `${decimal.format(wall)} m²` : "–",
      "floor-waste": floor ? `${decimal.format(floor * factor)} m²` : "–",
      "wall-waste": wall ? `${decimal.format(wall * factor)} m²` : "–",
      perimeter: perimeter ? `${decimal.format(perimeter)} m` : "–",
    };
    Object.entries(values).forEach(([key, value]) => $$(`[data-calc="${key}"]`, root).forEach((node) => { node.textContent = value; }));
    $$('[data-room-dimensions]', root).forEach((node) => {
      node.textContent = length && width && height ? `${decimal.format(length)} × ${decimal.format(width)} × ${decimal.format(height)} m` : "Maße aus dem Aufmaß";
    });
    return {length, width, height, deductions, waste, floor, wall, perimeter};
  };
  $$(".dimension-inputs input, #id_deductions_area_m2, #id_waste_percent").forEach((field) => field.addEventListener("input", () => updateMeasurementCalculations(field.closest("form") || document)));
  updateMeasurementCalculations(document);

  /* Guided photo capture + AI room measurement */
  const initMeasurementExperience = (root) => {
    const photoInput = $("#roomPhotos", root);
    const previews = $("#capturePreviews", root);
    const guide = $("#photoGuide", root);
    const analyzeButton = $("#analyzeRoomPhotos", root);
    const resultBox = $("#aiMeasurementResult", root);
    const statusBox = $("#aiMeasureStatus", root);
    const guideLabels = ["Von der Tür", "Wand 1", "Wand 2", "Wand 3", "Wand 4", "Boden", "Decke", "Anschlüsse", "Fenster/Türen", "Schäden"];

    const refreshPhotos = () => {
      if (!photoInput || !previews) return;
      $$(".capture-preview:not(.saved)", previews).forEach((node) => node.remove());
      [...photoInput.files].slice(0, 10).forEach((file, index) => {
        const figure = document.createElement("figure"); figure.className = "capture-preview";
        const image = document.createElement("img"); image.alt = guideLabels[index] || `Aufnahme ${index + 1}`;
        image.src = URL.createObjectURL(file);
        image.addEventListener("load", () => URL.revokeObjectURL(image.src), {once: true});
        const caption = document.createElement("figcaption"); caption.textContent = guideLabels[index] || file.name;
        figure.append(image, caption); previews.append(figure);
      });
      if (guide) {
        $$(":scope > div", guide).forEach((item, index) => {
          item.classList.toggle("done", index < photoInput.files.length);
          item.classList.toggle("next", index === photoInput.files.length && index < 10);
          const small = $("small", item);
          if (small) small.textContent = index < photoInput.files.length ? "aufgenommen" : index === photoInput.files.length ? "jetzt aufnehmen" : "";
        });
      }
      $$('[data-review="photos"]', root).forEach((node) => { node.textContent = `${photoInput.files.length} Aufnahmen`; });
    };
    photoInput?.addEventListener("change", refreshPhotos);

    analyzeButton?.addEventListener("click", async () => {
      if (!photoInput?.files.length) {
        window.alert("Bitte zuerst mehrere Raumfotos aufnehmen oder auswählen.");
        return;
      }
      analyzeButton.disabled = true;
      const original = analyzeButton.textContent;
      analyzeButton.textContent = "✦ Analyse läuft …";
      if (statusBox) { statusBox.classList.remove("success"); $("span", statusBox).textContent = "Fotos werden sicher ausgewertet …"; }
      try {
        const payload = new FormData();
        [...photoInput.files].slice(0, 10).forEach((file) => payload.append("images", file));
        payload.append("reference_type", $("#id_reference_type", root)?.value || "");
        payload.append("reference_width_cm", $("#id_reference_width_cm", root)?.value || "");
        payload.append("reference_height_cm", $("#id_reference_height_cm", root)?.value || "");
        payload.append("capture_sequence", JSON.stringify(guideLabels.slice(0, photoInput.files.length)));
        const response = await fetch("/api/measurements/analyze/", {method: "POST", headers: {"X-CSRFToken": csrf()}, body: payload});
        const data = await readJson(response);
        if (!response.ok) throw new Error(data.error || "Fotoaufmaß fehlgeschlagen");

        const hasScale = Boolean(data.scale_verified);
        const dimensions = [data.length_m, data.width_m, data.height_m];
        const hasDimensions = hasScale && dimensions.every((value) => typeof value === "number" && value > 0);
        if (hasDimensions) {
          [["#id_length_m", data.length_m], ["#id_width_m", data.width_m], ["#id_height_m", data.height_m]].forEach(([selector, value]) => {
            const input = $(selector, root); if (input) input.value = Number(value).toFixed(3);
          });
          if (typeof data.deductions_area_m2 === "number") {
            const input = $("#id_deductions_area_m2", root); if (input) input.value = Number(data.deductions_area_m2).toFixed(3);
          }
          const method = $("#id_measurement_method", root) || $("#id_method", root);
          if (method) method.value = data.method === "ar_lidar" ? "ar_lidar" : "ai_photo";
          updateMeasurementCalculations(root);
        }
        const confidenceInput = $("#measurementConfidence", root);
        const summaryInput = $("#measurementAiSummary", root);
        const warningsInput = $("#measurementAiWarnings", root);
        const payloadInput = $("#measurementAiPayload", root);
        if (confidenceInput) confidenceInput.value = Number(data.confidence || 0).toFixed(4);
        if (summaryInput) summaryInput.value = data.summary || "";
        if (warningsInput) warningsInput.value = JSON.stringify(data.warnings || []);
        if (payloadInput) payloadInput.value = JSON.stringify(data);

        if (resultBox) {
          resultBox.hidden = false;
          resultBox.replaceChildren();
          const title = document.createElement("b");
          title.textContent = hasDimensions ? "Skalierter KI-Messentwurf" : "Raumstruktur erkannt – keine belastbare Skalierung";
          const summary = document.createElement("p"); summary.textContent = data.summary || "Analyse abgeschlossen.";
          const meta = document.createElement("small");
          meta.textContent = `Konfidenz ${Math.round((data.confidence || 0) * 100)} % · ${hasDimensions ? "Maße übernommen, Prüfung erforderlich" : "Maße wurden bewusst nicht erfunden"}`;
          resultBox.append(title, summary, meta);
          const warnings = [...(data.warnings || []), ...(data.missing_captures || []).map((item) => `Fehlende Aufnahme: ${item}`)];
          if (warnings.length) {
            const list = document.createElement("ul");
            warnings.slice(0, 8).forEach((warning) => { const item = document.createElement("li"); item.textContent = warning; list.append(item); });
            resultBox.append(list);
          }
        }
        if (statusBox) {
          statusBox.classList.add("success");
          $("span", statusBox).textContent = hasDimensions ? "KI-Messentwurf bereit – bitte prüfen" : "Analyse bereit – Referenz/AR für Maße nötig";
        }
      } catch (error) {
        if (resultBox) { resultBox.hidden = false; resultBox.textContent = `Fehler: ${error.message}`; }
        if (statusBox) $("span", statusBox).textContent = "Analyse fehlgeschlagen";
      } finally {
        analyzeButton.disabled = false;
        analyzeButton.textContent = original;
      }
    });
  };
  $$("[data-project-wizard], [data-room-measurement]").forEach(initMeasurementExperience);

  /* Project wizard: keep the navigation driven by the rendered number of steps. */
  const wizard = $("[data-project-wizard]");
  if (wizard) {
    let step = 1;
    let refreshWizardPrices = async () => null;
    let refreshPriceServices = async () => null;
    const steps = $$(".wizard-step", wizard);
    const lastStep = Math.max(1, steps.length);
    const progressButtons = $$("[data-step-target]", wizard);
    const showStep = (next) => {
      step = Math.max(1, Math.min(lastStep, next));
      steps.forEach((panel) => panel.classList.toggle("active", Number(panel.dataset.step) === step));
      progressButtons.forEach((button) => {
        const index = Number(button.dataset.stepTarget);
        button.classList.toggle("active", index === step);
        button.classList.toggle("done", index < step);
      });
      $("[data-wizard-prev]", wizard).disabled = step === 1;
      const nextButton = $("[data-wizard-next]", wizard);
      nextButton.hidden = step === lastStep;
      $("[data-current-step]", wizard).textContent = String(step);
      if (step === 5) refreshPriceServices();
      if (step === 8 || step === 9) { updateQuote(); refreshWizardPrices(); }
      if (step === 9) updateReview();
    };
    progressButtons.forEach((button) => button.addEventListener("click", () => showStep(Number(button.dataset.stepTarget))));
    $("[data-wizard-prev]", wizard).addEventListener("click", () => showStep(step - 1));
    $("[data-wizard-next]", wizard).addEventListener("click", () => showStep(step + 1));

    $$("[data-project-type]", wizard).forEach((button) => button.addEventListener("click", () => {
      $$("[data-project-type]", wizard).forEach((item) => item.classList.toggle("selected", item === button));
      $("#id_project_type", wizard).value = button.dataset.projectType;
    }));
    $$(".customer-type-chips", wizard).forEach((group) => $$("button", group).forEach((button) => button.addEventListener("click", () => {
      $$("button", group).forEach((item) => item.classList.toggle("active", item === button));
    })));
    $$("[data-room-swatch]", wizard).forEach((button) => button.addEventListener("click", () => {
      $$("[data-room-swatch]", wizard).forEach((item) => item.classList.toggle("active", item === button));
      $("#wizardRoomPreview", wizard)?.style.setProperty("--floor", button.dataset.roomSwatch);
    }));

    const updateQuote = () => {
      const checkedServices = [
        ...$$('input[name="services"]:checked', wizard),
        ...$$('input[name="price_items"]:checked', wizard),
      ];
      const checkedMaterials = $$('input[name="materials"]:checked', wizard);
      const services = checkedServices.reduce((sum, input) => sum + numberValue(input.dataset.price), 0);
      const materials = checkedMaterials.reduce((sum, input) => sum + numberValue(input.dataset.price), 0);
      const cost = checkedMaterials.reduce((sum, input) => sum + numberValue(input.dataset.cost), 0);
      const subtotal = services + materials;
      const tax = subtotal * 0.19;
      const gross = subtotal + tax;
      const values = {services, materials, subtotal, tax, gross, cost, margin: subtotal - cost};
      Object.entries(values).forEach(([key, value]) => $$(`[data-quote="${key}"]`, wizard).forEach((node) => { node.textContent = money.format(value); }));
      return {checkedServices, checkedMaterials, ...values};
    };
    refreshWizardPrices = async () => {
      const selected = [
        ...$$('input[name="services"]:checked', wizard),
        ...$$('input[name="price_items"]:checked', wizard),
        ...$$('input[name="materials"]:checked', wizard),
      ];
      const status = $('[data-wizard-price-status]', wizard);
      if (!selected.length) {
        if (status) {
          status.className = 'wizard-price-status idle';
          $('b', status).textContent = 'Noch keine Position ausgewählt.';
          $('small', status).textContent = 'Wähle in Schritt 5 Leistungen oder in Schritt 6 Material aus.';
        }
        updateQuote();
        return;
      }
      const endpoint = wizard.dataset.pricePreviewUrl;
      if (!endpoint) return;
      const body = new URLSearchParams();
      const source = $('#id_price_source', wizard)?.value || '';
      if (source) body.set('price_source', source);
      $$('input[name="services"]:checked', wizard).forEach((input) => body.append('services', input.value));
      $$('input[name="price_items"]:checked', wizard).forEach((input) => body.append('price_items', input.value));
      $$('input[name="materials"]:checked', wizard).forEach((input) => body.append('materials', input.value));
      if (status) {
        status.className = 'wizard-price-status loading';
        $('b', status).textContent = 'Preise werden abgeglichen …';
        $('small', status).textContent = source ? 'Die ausgewählte Preisliste wird verwendet.' : 'Katalogpreise werden geprüft.';
      }
      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'X-CSRFToken': $('input[name="csrfmiddlewaretoken"]', wizard)?.value || '',
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: body.toString(),
        });
        const data = await readJson(response);
        if (!response.ok) throw new Error(data.error || 'Preise konnten nicht geladen werden.');
        (data.items || []).forEach((item) => {
          const rawId = item.selection_type === 'price_item' ? item.price_item_id : item.catalog_id;
          const id = CSS.escape(String(rawId));
          const input = item.selection_type === 'price_item'
            ? $(`input[name="price_items"][value="${id}"]`, wizard)
            : ($(`input[name="services"][value="${id}"]`, wizard) || $(`input[name="materials"][value="${id}"]`, wizard));
          if (!input) return;
          input.dataset.price = item.price || '0';
          if (input.name === 'materials') input.dataset.cost = item.cost || '0';
          const row = input.closest('.selection-row');
          row?.classList.toggle('price-unresolved', !item.price);
          const priceNode = $('em', row);
          if (priceNode) priceNode.textContent = item.price ? `${money.format(numberValue(item.price))} / ${item.unit || 'Stk.'}` : 'Kein Verkaufspreis';
        });
        updateQuote();
        if (status) {
          status.className = `wizard-price-status ${data.unresolved_count ? 'warning' : 'success'}`;
          $('b', status).textContent = data.price_source ? `Preisbasis: ${data.price_source}` : 'Katalogpreise geprüft';
          $('small', status).textContent = `${data.priced_count} bepreist${data.unresolved_count ? ` · ${data.unresolved_count} ohne belastbaren Preis` : ' · alle ausgewählten Positionen bepreist'}`;
        }
      } catch (error) {
        if (status) {
          status.className = 'wizard-price-status error';
          $('b', status).textContent = 'Preisabgleich fehlgeschlagen';
          $('small', status).textContent = error.message || 'Bitte Preisliste erneut wählen.';
        }
      }
    };
    $('#id_price_source', wizard)?.addEventListener('change', () => {
      $$('input[name="services"], input[name="price_items"]', wizard).forEach((input) => { input.checked = false; });
      updateQuote();
      refreshPriceServices();
      refreshWizardPrices();
      refreshServicePicker();
    });
    let selectionAnchor = null;
    wizard.addEventListener("pointerdown", (event) => {
      const input = event.target.closest?.('input[name="services"], input[name="price_items"], input[name="materials"]');
      const row = event.target.closest?.('.selection-row');
      if (!input && !row) return;
      const list = (input || row).closest?.('.selection-list');
      selectionAnchor = {pageY: window.scrollY, list, listY: list?.scrollTop || 0};
    }, true);
    const restoreSelectionPosition = (anchor) => {
      if (!anchor) return;
      requestAnimationFrame(() => requestAnimationFrame(() => {
        if (anchor.list) anchor.list.scrollTop = anchor.listY;
        window.scrollTo({top: anchor.pageY, left: 0, behavior: "auto"});
      }));
    };

    const servicePicker = $('[data-service-picker]', wizard);
    let refreshServicePicker = () => {};
    if (servicePicker) {
      const prompt = $('[data-service-prompt]', servicePicker);
      const analyzeButton = $('[data-service-analyze]', servicePicker);
      const showAllButton = $('[data-service-show-all]', servicePicker);
      const searchInput = $('[data-service-search]', servicePicker);
      const feedback = $('[data-service-feedback]', servicePicker);
      const results = $('[data-service-results]', servicePicker);
      const emptyState = $('[data-service-empty]', servicePicker);
      const catalogList = $('[data-service-list]', servicePicker);
      const priceList = $('[data-price-service-list]', servicePicker);
      const priceNote = $('[data-price-service-note]', servicePicker);
      let suggestedIds = null;
      let priceSourceMode = false;

      const selectedCount = () => (
        $$('input[name="services"]:checked', servicePicker).length
        + $$('input[name="price_items"]:checked', servicePicker).length
      );
      const activeRows = () => priceSourceMode
        ? $$('[data-price-service-row]', priceList)
        : $$('[data-service-row]', catalogList);
      const rowKey = (row) => priceSourceMode
        ? `price_item:${row.dataset.priceItemId}`
        : `catalog:${row.dataset.serviceId}`;

      const filterRows = () => {
        const query = (searchInput.value || "").trim().toLocaleLowerCase("de");
        let visible = 0;
        activeRows().forEach((row) => {
          const input = $('input[name="services"], input[name="price_items"]', row);
          const checked = input?.checked;
          const inSuggestions = suggestedIds === null || suggestedIds.has(rowKey(row));
          const inSearch = !query || (row.dataset.searchText || "").includes(query);
          const show = checked || (inSuggestions && inSearch);
          row.hidden = !show;
          if (show) visible += 1;
        });
        $('[data-service-visible-count]', servicePicker).textContent = String(visible);
        $('[data-service-selected-count]', servicePicker).textContent = String(selectedCount());
        emptyState.hidden = visible > 0;
      };
      refreshServicePicker = filterRows;

      const toggleService = (id, selectionType = 'catalog', checked = true) => {
        const name = selectionType === 'price_item' ? 'price_items' : 'services';
        const input = $(`input[name="${name}"][value="${CSS.escape(String(id))}"]`, servicePicker);
        if (!input) return;
        const anchor = {pageY: window.scrollY, list: input.closest('.selection-list'), listY: input.closest('.selection-list')?.scrollTop || 0};
        input.checked = checked;
        input.dispatchEvent(new Event("change", {bubbles: true}));
        restoreSelectionPosition(anchor);
      };

      const renderPriceRows = (data) => {
        priceList.replaceChildren();
        (data.items || []).forEach((item) => {
          const row = document.createElement('label');
          row.className = 'selection-row';
          row.dataset.priceServiceRow = '1';
          row.dataset.priceItemId = String(item.id);
          row.dataset.searchText = `${item.code || ''} ${item.description || ''} ${item.category || ''}`.toLocaleLowerCase('de');
          const input = document.createElement('input');
          input.type = 'checkbox';
          input.name = 'price_items';
          input.value = String(item.id);
          input.dataset.price = item.price || '0';
          const box = document.createElement('span');
          box.className = 'select-box';
          box.textContent = '✓';
          const text = document.createElement('div');
          const title = document.createElement('b');
          title.textContent = `${item.code || '–'} · ${item.description || 'Leistung'}`;
          const meta = document.createElement('small');
          meta.textContent = [item.category, item.unit].filter(Boolean).join(' · ') || 'Preislistenposition';
          const reason = document.createElement('small');
          reason.className = 'service-match-reason';
          reason.dataset.serviceReason = '1';
          reason.hidden = true;
          text.append(title, meta, reason);
          const price = document.createElement('em');
          price.textContent = `${money.format(numberValue(item.price))} / ${item.unit || 'Stk.'}`;
          row.append(input, box, text, price);
          priceList.append(row);
        });
        if (priceNote) {
          priceNote.hidden = false;
          $('[data-price-service-source]', priceNote).textContent = data.price_source || 'Ausgewählte Preisliste';
          $('[data-price-service-meta]', priceNote).textContent = `${data.count || 0} bepreiste Positionen · Verkaufspreise direkt aus der Preisliste`;
        }
      };

      refreshPriceServices = async () => {
        const source = $('#id_price_source', wizard)?.value || '';
        priceSourceMode = Boolean(source);
        if (catalogList) catalogList.hidden = priceSourceMode;
        if (priceList) priceList.hidden = !priceSourceMode;
        if (priceNote) priceNote.hidden = !priceSourceMode;
        suggestedIds = null;
        results.hidden = true;
        feedback.hidden = true;
        if (!source) {
          filterRows();
          return;
        }
        const endpoint = wizard.dataset.priceItemsUrl;
        if (!endpoint) return;
        priceList.innerHTML = '<div class="empty">Preisliste wird geladen …</div>';
        try {
          const url = new URL(endpoint, window.location.origin);
          url.searchParams.set('price_source', source);
          const response = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
          const data = await readJson(response);
          if (!response.ok) throw new Error(data.error || 'Preisliste konnte nicht geladen werden.');
          renderPriceRows(data);
          filterRows();
        } catch (error) {
          priceList.innerHTML = '';
          const state = document.createElement('div');
          state.className = 'empty';
          state.textContent = error.message || 'Preisliste konnte nicht geladen werden.';
          priceList.append(state);
          $('[data-service-visible-count]', servicePicker).textContent = '0';
          emptyState.hidden = true;
        }
      };

      const renderSuggestions = (matches) => {
        results.replaceChildren();
        if (!matches.length) {
          results.hidden = true;
          return;
        }
        const heading = document.createElement("div");
        heading.className = "service-result-head";
        const label = document.createElement("b");
        label.textContent = `${matches.length} passende Vorschläge`;
        const selectAll = document.createElement("button");
        selectAll.type = "button";
        selectAll.textContent = "Alle Vorschläge auswählen";
        selectAll.addEventListener("click", () => matches.forEach((item) => toggleService(item.id, item.selection_type || 'catalog', true)));
        heading.append(label, selectAll);
        results.append(heading);
        matches.forEach((item) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "service-result-card";
          button.dataset.serviceResult = String(item.id);
          button.innerHTML = `<span>＋</span><div><b></b><small></small><em></em></div>`;
          $("b", button).textContent = `${item.code} · ${item.name}`;
          $("small", button).textContent = item.reason || item.description || "Passender Katalogtreffer";
          $("em", button).textContent = `${money.format(numberValue(item.price))} / ${item.unit}`;
          button.addEventListener("click", () => toggleService(item.id, item.selection_type || 'catalog', true));
          results.append(button);
          const row = item.selection_type === 'price_item'
            ? $(`[data-price-service-row][data-price-item-id="${CSS.escape(String(item.id))}"]`, servicePicker)
            : $(`[data-service-row][data-service-id="${CSS.escape(String(item.id))}"]`, servicePicker);
          if (row) {
            row.classList.add("ai-recommended");
            const reason = $('[data-service-reason]', row);
            reason.textContent = item.reason || "Von A+Bau AI vorgeschlagen";
            reason.hidden = false;
          }
        });
        results.hidden = false;
      };

      const analyze = async () => {
        const value = (prompt.value || "").trim();
        if (value.length < 3) {
          feedback.hidden = false;
          feedback.className = "service-ai-feedback error";
          feedback.textContent = "Bitte kurz beschreiben, welche Arbeiten benötigt werden.";
          prompt.focus({preventScroll: true});
          return;
        }
        analyzeButton.disabled = true;
        const original = analyzeButton.textContent;
        analyzeButton.textContent = priceSourceMode ? "Preisliste wird analysiert …" : "Katalog wird analysiert …";
        feedback.hidden = true;
        try {
          const body = new URLSearchParams({prompt: value, project_type: $("#id_project_type", wizard)?.value || ""});
          const source = $('#id_price_source', wizard)?.value || '';
          if (source) body.set('price_source', source);
          const response = await fetch(servicePicker.dataset.endpoint, {
            method: "POST",
            headers: {
              "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
              "X-CSRFToken": $('input[name="csrfmiddlewaretoken"]', wizard)?.value || "",
              "X-Requested-With": "XMLHttpRequest",
            },
            body: body.toString(),
          });
          const data = await readJson(response);
          if (!response.ok) throw new Error(data.error || "Vorschläge konnten nicht geladen werden.");
          suggestedIds = new Set((data.matches || []).map((item) => `${item.selection_type || 'catalog'}:${item.id}`));
          searchInput.value = "";
          activeRows().forEach((row) => row.classList.remove("ai-recommended"));
          $$('[data-service-reason]', servicePicker).forEach((node) => { node.hidden = true; node.textContent = ""; });
          renderSuggestions(data.matches || []);
          feedback.hidden = false;
          feedback.className = "service-ai-feedback success";
          feedback.textContent = data.warning ? `${data.summary} ${data.warning}` : data.summary;
          filterRows();
        } catch (error) {
          feedback.hidden = false;
          feedback.className = "service-ai-feedback error";
          feedback.textContent = error.message || "Vorschläge konnten nicht geladen werden.";
        } finally {
          analyzeButton.disabled = false;
          analyzeButton.textContent = original;
        }
      };

      analyzeButton.addEventListener("click", analyze);
      prompt.addEventListener("keydown", (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") analyze();
      });
      $$('[data-service-chip]', servicePicker).forEach((chip) => chip.addEventListener("click", () => {
        prompt.value = chip.dataset.serviceChip;
        analyze();
      }));
      showAllButton.addEventListener("click", () => {
        suggestedIds = null;
        searchInput.value = "";
        feedback.hidden = true;
        results.hidden = true;
        filterRows();
      });
      searchInput.addEventListener("input", filterRows);
      filterRows();
      refreshPriceServices();
    }

    wizard.addEventListener("change", (event) => {
      const input = event.target.closest?.('input[name="services"], input[name="price_items"], input[name="materials"]');
      if (!input) return;
      const anchor = selectionAnchor || {pageY: window.scrollY, list: input.closest('.selection-list'), listY: input.closest('.selection-list')?.scrollTop || 0};
      updateQuote();
      refreshWizardPrices();
      refreshServicePicker();
      restoreSelectionPosition(anchor);
      selectionAnchor = null;
    });

    const materialSearch = $('[data-material-search]', wizard);
    if (materialSearch) {
      const materialRows = $$('[data-material-row]', wizard);
      const materialEmpty = $('[data-material-empty]', wizard);
      const filterMaterials = () => {
        const query = materialSearch.value.trim().toLocaleLowerCase('de');
        let visible = 0;
        materialRows.forEach((row) => {
          const show = !query || (row.dataset.searchText || '').includes(query) || $('input[name="materials"]', row)?.checked;
          row.hidden = !show;
          if (show) visible += 1;
        });
        const count = $('[data-material-visible-count]', wizard);
        if (count) count.textContent = String(visible);
        if (materialEmpty) materialEmpty.hidden = visible > 0;
      };
      materialSearch.addEventListener('input', filterMaterials);
      filterMaterials();
    }

    const updateReview = () => {
      const quote = updateQuote();
      const title = $("#id_title", wizard)?.value || "–";
      const customer = $("#id_customer", wizard);
      const room = $("#id_room_name", wizard)?.value || "–";
      const dims = updateMeasurementCalculations(wizard);
      const review = {
        title,
        customer: customer?.selectedOptions?.[0]?.textContent || "–",
        room,
        measurement: dims.length && dims.width && dims.height ? `${decimal.format(dims.length)} × ${decimal.format(dims.width)} × ${decimal.format(dims.height)} m` : "Noch offen",
        photos: `${$("#roomPhotos", wizard)?.files.length || 0} Aufnahmen`,
        items: `${quote.checkedServices.length + quote.checkedMaterials.length} ausgewählt`,
      };
      Object.entries(review).forEach(([key, value]) => $$(`[data-review="${key}"]`, wizard).forEach((node) => { node.textContent = value; }));
    };
    $("#projectWizardForm", wizard).addEventListener("input", () => { if (step === 9) updateReview(); });
    showStep(1);
  }

  /* Settings tabs */
  $$("[data-settings-tabs]").forEach((tabs) => {
    const activate = (key) => {
      $$('[data-settings-target]', tabs).forEach((button) => button.classList.toggle("active", button.dataset.settingsTarget === key));
      $$('[data-settings-pane]', tabs).forEach((pane) => pane.classList.toggle("active", pane.dataset.settingsPane === key));
      history.replaceState(null, "", `${window.location.pathname}#${key}`);
    };
    $$('[data-settings-target]', tabs).forEach((button) => button.addEventListener("click", () => activate(button.dataset.settingsTarget)));
    const initial = window.location.hash.replace("#", "");
    if (initial && $(`[data-settings-pane="${CSS.escape(initial)}"]`, tabs)) activate(initial);
  });

  /* Versioned parametric room model editor */
  $$('[data-room-model-editor]').forEach((editor) => {
    const scene = $('[data-model-scene]', editor) || $('#editableRoomScene', editor);
    if (!scene) return;
    const stateScript = document.getElementById(editor.dataset.stateScript || 'room-model-state');
    const inlineMode = editor.dataset.inlineRoomModel === '1';
    const stateOutput = editor.dataset.stateOutput ? document.getElementById(editor.dataset.stateOutput) : null;
    const touchedOutput = editor.dataset.touchedOutput ? document.getElementById(editor.dataset.touchedOutput) : null;
    const wizardForm = inlineMode ? editor.closest('form') : null;
    let state;
    try { state = JSON.parse(stateScript?.textContent || '{}'); } catch (_) { state = {}; }

    const ensureState = () => {
      state = state && typeof state === 'object' ? state : {};
      state.schema_version = 2;
      state.room = state.room && typeof state.room === 'object' ? state.room : {};
      state.room.length_m ??= '4'; state.room.width_m ??= '3'; state.room.height_m ??= '2.5';
      state.openings = Array.isArray(state.openings) ? state.openings : [];
      state.objects = Array.isArray(state.objects) ? state.objects : [];
      state.materials = state.materials && typeof state.materials === 'object' ? state.materials : {};
      Object.entries({floor:'#3d434b',wall:'#eef2f6',ceiling:'#f8fafc',accent:'#6e8fa8',grout_color:'#c7cdd3',pattern:'straight',tile_width_cm:'60',tile_height_cm:'60'}).forEach(([key,value]) => { state.materials[key] ??= value; });
      state.lighting = state.lighting && typeof state.lighting === 'object' ? state.lighting : {};
      state.lighting.brightness ??= '1'; state.lighting.warmth ??= '35';
      state.view = state.view && typeof state.view === 'object' ? state.view : {};
      state.view.mode ??= 'perspective'; state.view.rotation_deg ??= '0';
    };
    ensureState();
    let dirty = false;

    const colorValid = (value) => /^#[0-9a-f]{6}$/i.test(String(value || '').trim());
    const fixtureNames = {shower:'Dusche',vanity:'Waschtisch',toilet:'WC',bathtub:'Badewanne',radiator:'Heizkörper',cabinet:'Schrank',fixture:'Objekt'};
    const fixtureIcons = {shower:'🚿',vanity:'▤',toilet:'◒',bathtub:'▰',radiator:'♨',cabinet:'▥',fixture:'◇'};
    const fixtureDefaults = {
      shower:{width_m:'1.2',depth_m:'0.9',height_m:'2.1',color:'#9fd8ee'},
      vanity:{width_m:'0.9',depth_m:'0.5',height_m:'0.85',color:'#d9d0c5'},
      toilet:{width_m:'0.4',depth_m:'0.7',height_m:'0.8',color:'#f6f7f8'},
      bathtub:{width_m:'1.7',depth_m:'0.75',height_m:'0.6',color:'#f2f4f6'},
      radiator:{width_m:'0.8',depth_m:'0.15',height_m:'0.7',color:'#e9ecef'},
      cabinet:{width_m:'0.8',depth_m:'0.45',height_m:'1.8',color:'#8a6a4d'},
      fixture:{width_m:'0.6',depth_m:'0.6',height_m:'0.8',color:'#cbd5df'},
    };

    const syncOutputs = (markTouched = false) => {
      if (stateOutput) stateOutput.value = JSON.stringify(state);
      if (markTouched && touchedOutput) touchedOutput.value = '1';
    };
    const syncWizardDimensions = () => {
      if (!wizardForm) return;
      [['length_m','id_length_m'],['width_m','id_width_m'],['height_m','id_height_m']].forEach(([key,id]) => {
        const input = document.getElementById(id);
        if (input && document.activeElement !== input) input.value = state.room[key] ?? '';
      });
    };
    const setStatus = (text, kind = '') => {
      const status = $('[data-model-save-status]', editor);
      if (!status) return;
      status.textContent = text;
      status.classList.remove('dirty', 'success', 'error');
      if (kind) status.classList.add(kind);
    };
    const markDirty = () => {
      dirty = true;
      syncOutputs(true);
      syncWizardDimensions();
      setStatus(inlineMode ? 'Änderungen werden mit dem Projekt gespeichert.' : 'Ungespeicherte Änderungen', 'dirty');
    };
    const roomNumber = (key, fallback) => Math.max(0.1, numberValue(state.room[key]) || fallback);
    const openingArea = () => state.openings.reduce((sum, item) => sum + numberValue(item.width_m) * numberValue(item.height_m), 0);

    const activatePane = (key) => {
      $$('[data-model-tab]', editor).forEach((button) => button.classList.toggle('active', button.dataset.modelTab === key));
      $$('[data-model-pane]', editor).forEach((pane) => pane.classList.toggle('active', pane.dataset.modelPane === key));
    };
    $$('[data-model-tab]', editor).forEach((button) => button.addEventListener('click', () => activatePane(button.dataset.modelTab)));

    const renderOpeningsEditor = () => {
      const list = $('[data-opening-editor-list]', editor);
      if (!list) return;
      list.replaceChildren();
      state.openings.forEach((opening, index) => {
        const row = document.createElement('div');
        row.className = 'opening-editor-row';
        row.innerHTML = `
          <div class="opening-editor-head"><b>${opening.kind === 'door' ? 'Tür' : opening.kind === 'window' ? 'Fenster' : 'Öffnung'} ${index + 1}</b><button type="button" aria-label="Öffnung löschen">×</button></div>
          <div class="form-grid two compact">
            <label><span>Wand</span><select class="form-control" data-opening-field="wall"><option value="back">Hinten</option><option value="left">Links</option><option value="right">Rechts</option><option value="front">Vorne</option></select></label>
            <label><span>Typ</span><select class="form-control" data-opening-field="kind"><option value="door">Tür</option><option value="window">Fenster</option><option value="opening">Durchgang</option></select></label>
            <label><span>Breite m</span><input class="form-control" type="number" min="0.05" max="10" step="0.01" data-opening-field="width_m"></label>
            <label><span>Höhe m</span><input class="form-control" type="number" min="0.05" max="10" step="0.01" data-opening-field="height_m"></label>
            <label><span>Abstand m</span><input class="form-control" type="number" min="0" max="50" step="0.01" data-opening-field="offset_m"></label>
            <label><span>Brüstung m</span><input class="form-control" type="number" min="0" max="10" step="0.01" data-opening-field="sill_m"></label>
          </div>`;
        ['wall','kind','width_m','height_m','offset_m','sill_m'].forEach((key) => {
          const input = row.querySelector(`[data-opening-field="${key}"]`);
          input.value = opening[key] ?? (key === 'sill_m' ? '0' : '');
          input.addEventListener('input', () => { opening[key] = input.value; markDirty(); renderScene(); });
        });
        row.querySelector('.opening-editor-head button').addEventListener('click', () => {
          state.openings.splice(index, 1); markDirty(); renderOpeningsEditor(); renderScene();
        });
        list.append(row);
      });
      if (!state.openings.length) {
        const empty = document.createElement('div'); empty.className = 'empty compact'; empty.innerHTML = '<p>Noch keine Türen, Fenster oder Durchgänge. Oben hinzufügen.</p>'; list.append(empty);
      }
    };

    const renderFixturesEditor = () => {
      const list = $('[data-fixture-editor-list]', editor);
      if (!list) return;
      list.replaceChildren();
      state.objects.forEach((fixture, index) => {
        const row = document.createElement('div');
        row.className = 'fixture-editor-row';
        row.innerHTML = `
          <div class="fixture-editor-head"><span>${fixtureIcons[fixture.kind] || '◇'}</span><div><b>${fixtureNames[fixture.kind] || 'Objekt'} ${index + 1}</b><small>Position, Größe, Drehung und Farbe</small></div><label class="mini-switch"><input type="checkbox" data-fixture-enabled><i></i></label><button type="button" data-fixture-remove aria-label="Objekt löschen">×</button></div>
          <div class="form-grid three compact fixture-position-grid">
            <label><span>X m</span><input class="form-control" type="number" min="0" max="50" step="0.05" data-fixture-field="x_m"></label>
            <label><span>Z m</span><input class="form-control" type="number" min="0" max="50" step="0.05" data-fixture-field="z_m"></label>
            <label><span>Drehung °</span><input class="form-control" type="number" min="0" max="360" step="1" data-fixture-field="rotation_deg"></label>
            <label><span>Breite m</span><input class="form-control" type="number" min="0.05" max="10" step="0.05" data-fixture-field="width_m"></label>
            <label><span>Tiefe m</span><input class="form-control" type="number" min="0.05" max="10" step="0.05" data-fixture-field="depth_m"></label>
            <label><span>Höhe m</span><input class="form-control" type="number" min="0.05" max="10" step="0.05" data-fixture-field="height_m"></label>
          </div>
          <label class="fixture-color-field"><span>Farbe</span><input type="color" data-fixture-color><input class="form-control" maxlength="7" data-fixture-color-text></label>`;
        const enabled = $('[data-fixture-enabled]', row);
        enabled.checked = fixture.enabled !== false;
        enabled.addEventListener('change', () => { fixture.enabled = enabled.checked; markDirty(); renderScene(); });
        ['x_m','z_m','rotation_deg','width_m','depth_m','height_m'].forEach((key) => {
          const input = row.querySelector(`[data-fixture-field="${key}"]`);
          input.value = fixture[key] ?? fixtureDefaults[fixture.kind]?.[key] ?? '';
          input.addEventListener('input', () => { fixture[key] = input.value; markDirty(); renderScene(); });
        });
        const color = $('[data-fixture-color]', row), colorText = $('[data-fixture-color-text]', row);
        const initialColor = colorValid(fixture.color) ? fixture.color : (fixtureDefaults[fixture.kind]?.color || '#cbd5df');
        fixture.color = initialColor; color.value = initialColor; colorText.value = initialColor;
        color.addEventListener('input', () => { fixture.color = color.value; colorText.value = color.value; markDirty(); renderScene(); });
        colorText.addEventListener('change', () => { if (colorValid(colorText.value)) { fixture.color = colorText.value; color.value = colorText.value; markDirty(); renderScene(); } else colorText.value = fixture.color; });
        $('[data-fixture-remove]', row).addEventListener('click', () => { state.objects.splice(index, 1); markDirty(); renderFixturesEditor(); renderScene(); });
        list.append(row);
      });
      if (!state.objects.length) {
        const empty = document.createElement('div'); empty.className = 'empty compact'; empty.innerHTML = '<p>Noch keine Objekte. Dusche, WC oder weitere Ausstattung hinzufügen.</p>'; list.append(empty);
      }
    };

    const openingLabel = (opening) => opening.kind === 'door' ? 'Tür' : opening.kind === 'window' ? 'Fenster' : 'Öffnung';
    const openingOffsetText = (value) => {
      const rounded = Math.round(Math.max(0, value) * 100) / 100;
      return rounded.toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1');
    };
    const setOpeningOffset = (opening, openingIndex, base, value, node = null) => {
      const openingWidth = Math.max(.05, numberValue(opening.width_m));
      const maximum = Math.max(0, base - openingWidth);
      const clamped = Math.max(0, Math.min(maximum, value));
      opening.offset_m = openingOffsetText(clamped);
      const row = $$('[data-opening-editor-list] .opening-editor-row', editor)[openingIndex];
      const input = row?.querySelector('[data-opening-field="offset_m"]');
      if (input && document.activeElement !== input) input.value = opening.offset_m;
      if (node) {
        node.style.left = `${Math.min(84, Math.max(1, clamped / Math.max(.1, base) * 100))}%`;
        node.setAttribute('aria-valuenow', opening.offset_m);
      }
      markDirty();
    };
    const attachOpeningDrag = (node, wall, opening, openingIndex, base) => {
      const maximum = Math.max(0, base - Math.max(.05, numberValue(opening.width_m)));
      node.tabIndex = 0;
      node.setAttribute('role', 'slider');
      node.setAttribute('aria-label', `${openingLabel(opening)} verschieben`);
      node.setAttribute('aria-valuemin', '0');
      node.setAttribute('aria-valuemax', openingOffsetText(maximum));
      node.setAttribute('aria-valuenow', openingOffsetText(numberValue(opening.offset_m)));
      let drag = null;
      node.addEventListener('pointerdown', (event) => {
        if (event.pointerType === 'mouse' && event.button !== 0) return;
        event.preventDefault();
        event.stopPropagation();
        const wallRect = wall?.getBoundingClientRect();
        drag = {
          pointerId: event.pointerId,
          startX: event.clientX,
          startOffset: numberValue(opening.offset_m),
          wallPixels: Math.max(80, wallRect?.width || 0),
        };
        node.setPointerCapture?.(event.pointerId);
        node.classList.add('is-dragging');
        scene.classList.add('is-dragging-opening');
      });
      node.addEventListener('pointermove', (event) => {
        if (!drag || event.pointerId !== drag.pointerId) return;
        event.preventDefault();
        const deltaMeters = ((event.clientX - drag.startX) / drag.wallPixels) * base;
        setOpeningOffset(opening, openingIndex, base, drag.startOffset + deltaMeters, node);
      });
      const finishDrag = (event) => {
        if (!drag || event.pointerId !== drag.pointerId) return;
        try { node.releasePointerCapture?.(event.pointerId); } catch (_) {}
        drag = null;
        node.classList.remove('is-dragging');
        scene.classList.remove('is-dragging-opening');
        renderScene();
      };
      node.addEventListener('pointerup', finishDrag);
      node.addEventListener('pointercancel', finishDrag);
      node.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const step = event.shiftKey ? .25 : .05;
        let next = numberValue(opening.offset_m);
        if (event.key === 'ArrowLeft') next -= step;
        if (event.key === 'ArrowRight') next += step;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = maximum;
        setOpeningOffset(opening, openingIndex, base, next, node);
        renderScene();
      });
    };

    const renderScene = () => {
      const length = roomNumber('length_m', 4), width = roomNumber('width_m', 3), height = roomNumber('height_m', 2.5);
      scene.style.setProperty('--room-length-ratio', String(Math.min(1.5, Math.max(.65, length / 4))));
      scene.style.setProperty('--room-width-ratio', String(Math.min(1.5, Math.max(.65, width / 3))));
      scene.style.setProperty('--room-height-ratio', String(Math.min(1.35, Math.max(.7, height / 2.5))));
      scene.style.setProperty('--model-floor', state.materials.floor);
      scene.style.setProperty('--model-wall', state.materials.wall);
      scene.style.setProperty('--model-ceiling', state.materials.ceiling);
      scene.style.setProperty('--model-accent', state.materials.accent);
      scene.style.setProperty('--model-grout', state.materials.grout_color);
      scene.style.setProperty('--tile-width', `${Math.max(8, numberValue(state.materials.tile_width_cm))}px`);
      scene.style.setProperty('--tile-height', `${Math.max(8, numberValue(state.materials.tile_height_cm))}px`);
      scene.style.setProperty('--model-brightness', String(numberValue(state.lighting.brightness) || 1));
      scene.style.setProperty('--model-warmth', `${Math.max(0, Math.min(100, numberValue(state.lighting.warmth)))}%`);
      scene.style.setProperty('--model-rotation', `${numberValue(state.view.rotation_deg)}deg`);
      scene.dataset.viewMode = state.view.mode || 'perspective';
      scene.classList.toggle('pattern-diagonal', state.materials.pattern === 'diagonal');
      scene.classList.toggle('pattern-herringbone', state.materials.pattern === 'herringbone');
      const setText = (selector, value) => { const node = $(selector, editor); if (node) node.textContent = value; };
      setText('[data-model-dimension="length"]', `${decimal.format(length)} m`);
      setText('[data-model-dimension="width"]', `${decimal.format(width)} m`);
      setText('[data-model-dimension="height"]', `${decimal.format(height)} m`);
      setText('[data-model-calc="floor"]', `${decimal.format(length * width)} m²`);
      setText('[data-model-calc="wall"]', `${decimal.format(2 * (length + width) * height)} m²`);
      setText('[data-model-calc="openings"]', `${decimal.format(openingArea())} m²`);
      setText('[data-model-summary]', `${state.openings.length} Öffnungen · ${state.objects.filter((item) => item.enabled !== false).length} Objekte · ${compactNumber.format(numberValue(state.materials.tile_width_cm))} × ${compactNumber.format(numberValue(state.materials.tile_height_cm))} cm`);
      setText('[data-rotation-output]', `${Math.round(numberValue(state.view.rotation_deg))}°`);
      setText('[data-light-output="brightness"]', `${Math.round((numberValue(state.lighting.brightness) || 1) * 100)}%`);
      setText('[data-light-output="warmth"]', `${Math.round(numberValue(state.lighting.warmth))}%`);

      $$('[data-model-openings]', editor).forEach((wall) => wall.replaceChildren());
      state.openings.forEach((opening, openingIndex) => {
        const wall = $(`[data-model-openings="${CSS.escape(opening.wall || 'back')}"]`, editor) || $('[data-model-openings="back"]', editor);
        const node = document.createElement('span');
        node.className = `model-opening model-opening-${opening.kind || 'opening'}`;
        node.title = `${openingLabel(opening)} verschieben · ${opening.width_m || '–'} × ${opening.height_m || '–'} m`;
        const base = ['left','right'].includes(opening.wall) ? width : length;
        node.style.width = `${Math.min(60, Math.max(8, numberValue(opening.width_m) / Math.max(.1, base) * 100))}%`;
        node.style.height = `${Math.min(88, Math.max(12, numberValue(opening.height_m) / height * 100))}%`;
        node.style.left = `${Math.min(84, Math.max(1, numberValue(opening.offset_m) / Math.max(.1, base) * 100))}%`;
        node.style.bottom = `${Math.min(72, Math.max(0, numberValue(opening.sill_m) / height * 100))}%`;
        if (wall) {
          wall.append(node);
          attachOpeningDrag(node, wall, opening, openingIndex, base);
        }
      });

      const fixtureLayer = $('[data-model-fixtures]', editor); fixtureLayer?.replaceChildren();
      state.objects.filter((item) => item.enabled !== false).forEach((fixture) => {
        const node = document.createElement('span');
        node.className = `model-fixture model-fixture-${fixture.kind || 'fixture'}`;
        node.textContent = fixtureIcons[fixture.kind] || '◇';
        node.title = `${fixtureNames[fixture.kind] || 'Objekt'} · ${fixture.width_m} × ${fixture.depth_m} × ${fixture.height_m} m`;
        node.style.left = `${Math.min(88, Math.max(4, numberValue(fixture.x_m) / length * 100))}%`;
        node.style.bottom = `${Math.min(76, Math.max(4, numberValue(fixture.z_m) / width * 68))}%`;
        node.style.setProperty('--fixture-color', colorValid(fixture.color) ? fixture.color : '#cbd5df');
        node.style.setProperty('--fixture-scale-x', String(Math.min(2.2, Math.max(.55, numberValue(fixture.width_m) / .8))));
        node.style.setProperty('--fixture-scale-y', String(Math.min(2.2, Math.max(.55, numberValue(fixture.height_m) / .9))));
        node.style.setProperty('--fixture-rotation', `${numberValue(fixture.rotation_deg)}deg`);
        fixtureLayer?.append(node);
      });
    };

    const populateControls = () => {
      $$('[data-room-field]', editor).forEach((input) => { input.value = state.room[input.dataset.roomField] ?? ''; });
      $$('[data-model-view]', editor).forEach((button) => button.classList.toggle('active', button.dataset.modelView === state.view.mode));
      const rotation = $('[data-view-rotation]', editor); if (rotation) rotation.value = state.view.rotation_deg;
      $$('[data-model-surface]', editor).forEach((button) => button.classList.toggle('active', state.materials[button.dataset.modelSurface] === button.dataset.value));
      $$('[data-model-pattern]', editor).forEach((button) => button.classList.toggle('active', state.materials.pattern === button.dataset.modelPattern));
      $$('[data-model-material]', editor).forEach((input) => { const key=input.dataset.modelMaterial; input.value=colorValid(state.materials[key])?state.materials[key]:'#ffffff'; const text=$(`[data-model-material-text="${key}"]`,editor); if(text)text.value=input.value; });
      $$('[data-material-number]', editor).forEach((input) => { input.value = state.materials[input.dataset.materialNumber] ?? ''; });
      $$('[data-lighting-field]', editor).forEach((input) => { input.value = state.lighting[input.dataset.lightingField] ?? ''; });
      $$('[data-model-fixture]', editor).forEach((input) => { const fixture=state.objects.find((item)=>item.kind===input.dataset.modelFixture); input.checked=fixture ? fixture.enabled !== false : false; });
      renderOpeningsEditor(); renderFixturesEditor(); renderScene(); syncOutputs(false);
    };

    $$('[data-room-field]', editor).forEach((input) => input.addEventListener('input', () => { state.room[input.dataset.roomField] = input.value; markDirty(); renderScene(); }));
    if (wizardForm) {
      [['id_length_m','length_m'],['id_width_m','width_m'],['id_height_m','height_m']].forEach(([id,key]) => {
        document.getElementById(id)?.addEventListener('input', (event) => {
          if (!event.target.value) return;
          state.room[key] = event.target.value;
          const modelInput = $(`[data-room-field="${key}"]`, editor); if (modelInput) modelInput.value = event.target.value;
          markDirty(); renderScene();
        });
      });
      wizardForm.addEventListener('submit', () => syncOutputs(touchedOutput?.value === '1'));
    }
    $$('[data-model-view]', editor).forEach((button) => button.addEventListener('click', () => { state.view.mode = button.dataset.modelView; populateControls(); markDirty(); }));
    $('[data-view-rotation]', editor)?.addEventListener('input', (event) => { state.view.rotation_deg = event.target.value; markDirty(); renderScene(); });
    $$('[data-model-surface]', editor).forEach((button) => button.addEventListener('click', () => { state.materials[button.dataset.modelSurface] = button.dataset.value; populateControls(); markDirty(); }));
    $$('[data-model-pattern]', editor).forEach((button) => button.addEventListener('click', () => { state.materials.pattern = button.dataset.modelPattern; populateControls(); markDirty(); }));
    $$('[data-model-material]', editor).forEach((input) => input.addEventListener('input', () => { const key=input.dataset.modelMaterial; state.materials[key]=input.value; const text=$(`[data-model-material-text="${key}"]`,editor); if(text)text.value=input.value; markDirty(); renderScene(); }));
    $$('[data-model-material-text]', editor).forEach((input) => input.addEventListener('change', () => { const key=input.dataset.modelMaterialText; if(colorValid(input.value)){state.materials[key]=input.value; const picker=$(`[data-model-material="${key}"]`,editor); if(picker)picker.value=input.value; markDirty(); renderScene();}else input.value=state.materials[key]; }));
    $$('[data-material-number]', editor).forEach((input) => input.addEventListener('input', () => { state.materials[input.dataset.materialNumber]=input.value; markDirty(); renderScene(); }));
    $$('[data-lighting-field]', editor).forEach((input) => input.addEventListener('input', () => { state.lighting[input.dataset.lightingField]=input.value; markDirty(); renderScene(); }));
    $$('[data-model-preset]', editor).forEach((button) => button.addEventListener('click', () => {
      const presets={bright:{floor:'#d8d1c7',wall:'#f3f4f2',ceiling:'#ffffff',accent:'#b7c7d4',grout_color:'#d7d7d2',brightness:'1.25',warmth:'30'},warm:{floor:'#b69b7d',wall:'#eee3d5',ceiling:'#fff8ef',accent:'#8a6a4d',grout_color:'#cfbda9',brightness:'1.1',warmth:'72'},contrast:{floor:'#2f343a',wall:'#e7eaed',ceiling:'#f8fafc',accent:'#22344a',grout_color:'#737b84',brightness:'.9',warmth:'32'},concrete:{floor:'#9da4aa',wall:'#d7dadd',ceiling:'#eef0f2',accent:'#697681',grout_color:'#7e858b',brightness:'1',warmth:'24'}};
      const preset=presets[button.dataset.modelPreset]; if(!preset)return; Object.entries(preset).forEach(([key,value])=>{if(key==='brightness'||key==='warmth')state.lighting[key]=value;else state.materials[key]=value;}); populateControls(); markDirty();
    }));
    $$('[data-add-opening]', editor).forEach((button) => button.addEventListener('click', () => {
      const kind=button.dataset.addOpening; state.openings.push({id:`opening-${Date.now()}`,kind,wall:'back',width_m:kind==='door'?'.9':'1.2',height_m:kind==='door'?'2':'1',offset_m:'.5',sill_m:kind==='door'?'0':'.9'}); markDirty(); renderOpeningsEditor(); renderScene();
    }));
    $$('[data-add-fixture]', editor).forEach((button) => button.addEventListener('click', () => {
      const kind=button.dataset.addFixture, defaults=fixtureDefaults[kind]||fixtureDefaults.fixture;
      state.objects.push({id:`fixture-${kind}-${Date.now()}`,kind,x_m:String(Math.min(roomNumber('length_m',4)-.2,.5+state.objects.length*.35)),z_m:'.5',rotation_deg:'0',enabled:true,...defaults});
      markDirty(); renderFixturesEditor(); renderScene();
    }));
    $$('[data-model-fixture]', editor).forEach((input) => input.addEventListener('change', () => {
      let fixture=state.objects.find((item)=>item.kind===input.dataset.modelFixture); if(!fixture){const kind=input.dataset.modelFixture,defaults=fixtureDefaults[kind]||fixtureDefaults.fixture; fixture={id:`fixture-${kind}`,kind,x_m:'.5',z_m:'.5',rotation_deg:'0',...defaults,enabled:true};state.objects.push(fixture);} fixture.enabled=input.checked; markDirty(); renderFixturesEditor(); renderScene();
    }));

    const applyAi = async () => {
      const prompt=$('[data-model-ai-prompt]',editor), button=$('[data-model-ai-apply]',editor), feedback=$('[data-model-ai-feedback]',editor);
      const value=(prompt?.value||'').trim();
      if(value.length<3){if(feedback){feedback.hidden=false;feedback.className='model-ai-feedback error';feedback.textContent='Bitte die gewünschte Änderung genauer beschreiben.';}prompt?.focus({preventScroll:true});return;}
      button.disabled=true; const original=button.textContent; button.textContent='Modell wird angepasst …'; if(feedback)feedback.hidden=true;
      const previousState=JSON.parse(JSON.stringify(state));
      try{
        const response=await fetch(editor.dataset.aiUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'},body:JSON.stringify({prompt:value,state})});
        const data=await readJson(response); if(!response.ok)throw new Error(data.error||'KI-Änderung fehlgeschlagen.');
        if(!data.state||typeof data.state!=='object'||!data.state.room||!Array.isArray(data.state.openings)||!data.state.materials)throw new Error('Die KI hat keinen gültigen Modellzustand geliefert. Das bisherige Modell wurde beibehalten.');
        state=JSON.parse(JSON.stringify(data.state)); ensureState(); populateControls(); markDirty();
        if(feedback){feedback.hidden=false;feedback.className='model-ai-feedback success';feedback.textContent=[data.summary,...(data.warnings||[])].filter(Boolean).join(' ');}
      }catch(error){state=previousState;ensureState();populateControls();if(feedback){feedback.hidden=false;feedback.className='model-ai-feedback error';feedback.textContent=error.message||'KI-Änderung fehlgeschlagen. Das bisherige Modell wurde beibehalten.';}}
      finally{button.disabled=false;button.textContent=original;}
    };
    $('[data-model-ai-apply]',editor)?.addEventListener('click',applyAi);
    $('[data-model-ai-prompt]',editor)?.addEventListener('keydown',(event)=>{if((event.ctrlKey||event.metaKey)&&event.key==='Enter')applyAi();});
    $$('[data-model-ai-chip]',editor).forEach((chip)=>chip.addEventListener('click',()=>{const prompt=$('[data-model-ai-prompt]',editor);if(prompt)prompt.value=chip.dataset.modelAiChip;applyAi();}));

    $('[data-save-room-model]', editor)?.addEventListener('click', async (event) => {
      const button=event.currentTarget; button.disabled=true; button.textContent='Speichert …';
      try{
        const response=await fetch(editor.dataset.saveUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({measurement_id:Number(editor.dataset.measurementId),label:$('[data-model-label]',editor)?.value||'',state})});
        const data=await readJson(response); if(!response.ok)throw new Error(data.error||'Speichern fehlgeschlagen');
        dirty=false; setStatus(`Version ${data.revision} gespeichert · Aufmaß: ${data.measurement_status_label}`,'success'); button.textContent='Gespeichert ✓';
        window.setTimeout(()=>window.location.assign(`${window.location.pathname}?project=${new URLSearchParams(window.location.search).get('project')||''}&measurement=${editor.dataset.measurementId}&revision=${data.revision_id}`),650);
      }catch(error){setStatus(error.message,'error');button.disabled=false;button.textContent='Neue Modellversion speichern';}
    });

    if(!inlineMode) window.addEventListener('beforeunload',(event)=>{if(dirty){event.preventDefault();event.returnValue='';}});
    populateControls();
  });
  if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js?v=20260810-6", {scope: "/", updateViaCache: "none"}).then((registration) => registration.update()).catch(() => {}));
})();

/* A+Bau workflow release: image annotations, digital signatures and PWA reminders */
document.addEventListener("DOMContentLoaded", () => {
  const editor = document.querySelector("[data-annotation-editor]");
  if (editor) {
    const image = document.getElementById("annotationImage");
    const canvas = document.getElementById("annotationCanvas");
    const output = document.getElementById("annotationsData");
    const ctx = canvas?.getContext("2d");
    let mode = "draw";
    let drawing = false;
    let annotations = [];
    try { annotations = JSON.parse(output?.value || "[]"); } catch (_) { annotations = []; }
    const resize = () => {
      if (!image || !canvas || !ctx) return;
      const rect = image.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(rect.width * devicePixelRatio));
      canvas.height = Math.max(1, Math.round(rect.height * devicePixelRatio));
      canvas.style.width = `${rect.width}px`; canvas.style.height = `${rect.height}px`;
      ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
      render();
    };
    const render = () => {
      if (!canvas || !ctx) return;
      ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
      ctx.lineWidth = 3; ctx.lineCap = "round"; ctx.strokeStyle = "#ff3b30"; ctx.fillStyle = "#ff3b30"; ctx.font = "bold 16px Arial";
      annotations.forEach((a) => {
        if (a.type === "path") {
          ctx.beginPath(); (a.points || []).forEach((p, i) => { const x=p[0]*canvas.clientWidth, y=p[1]*canvas.clientHeight; i?ctx.lineTo(x,y):ctx.moveTo(x,y); }); ctx.stroke();
        } else if (a.type === "text") ctx.fillText(a.text || "Hinweis", a.x*canvas.clientWidth, a.y*canvas.clientHeight);
      });
      if (output) output.value = JSON.stringify(annotations);
    };
    const point = (event) => { const rect=canvas.getBoundingClientRect(); return [(event.clientX-rect.left)/rect.width,(event.clientY-rect.top)/rect.height]; };
    canvas?.addEventListener("pointerdown", (event) => {
      if (mode === "text") { const text=window.prompt("Text oder Maß eingeben:", ""); if(text){const [x,y]=point(event);annotations.push({type:"text",x,y,text});render();} return; }
      drawing=true; canvas.setPointerCapture(event.pointerId); annotations.push({type:"path",points:[point(event)]});
    });
    canvas?.addEventListener("pointermove", (event) => { if(!drawing)return; annotations.at(-1).points.push(point(event)); render(); });
    canvas?.addEventListener("pointerup", () => { drawing=false; render(); });
    document.querySelectorAll("[data-annotation-mode]").forEach((button)=>button.addEventListener("click",()=>{mode=button.dataset.annotationMode;}));
    document.querySelector("[data-annotation-clear]")?.addEventListener("click",()=>{annotations=[];render();});
    image?.addEventListener("load", resize); window.addEventListener("resize", resize); if(image?.complete) resize();
  }

  document.querySelectorAll("[data-signature-form]").forEach((form) => {
    const canvas=form.querySelector("[data-signature-canvas]"), output=form.querySelector("[data-signature-data]"), touched=form.querySelector("[data-signature-touched]");
    if(!canvas||!output)return; const ctx=canvas.getContext("2d"); let drawing=false, dirty=false;
    const resize=()=>{canvas.width=canvas.clientWidth*devicePixelRatio;canvas.height=canvas.clientHeight*devicePixelRatio;ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);ctx.lineWidth=2;ctx.lineCap="round";}; resize();
    const p=e=>{const r=canvas.getBoundingClientRect();return[e.clientX-r.left,e.clientY-r.top]};
    canvas.addEventListener("pointerdown",e=>{drawing=true;dirty=true;if(touched)touched.value="1";const[x,y]=p(e);ctx.beginPath();ctx.moveTo(x,y)});
    canvas.addEventListener("pointermove",e=>{if(!drawing)return;const[x,y]=p(e);ctx.lineTo(x,y);ctx.stroke()});
    canvas.addEventListener("pointerup",()=>drawing=false); form.addEventListener("submit",()=>{output.value=dirty?canvas.toDataURL("image/png"):""});
  });

  document.querySelectorAll("[data-report-lines]").forEach((form) => {
    form.addEventListener("click", (event) => {
      const add = event.target.closest("[data-add-report-line]");
      if (add) {
        const kind = add.dataset.addReportLine;
        const template = form.querySelector(`[data-report-line-template="${kind}"]`);
        const list = form.querySelector(`[data-report-line-list="${kind}"]`);
        if (template && list) list.append(template.content.cloneNode(true));
        return;
      }
      const remove = event.target.closest("[data-remove-report-line]");
      if (remove) remove.closest(".report-line")?.remove();
    });
  });

  const notify = async () => {
    if (!("Notification" in window) || !navigator.serviceWorker) return;
    try {
      const response = await fetch("/api/notifications/feed/", {headers:{"X-Requested-With":"XMLHttpRequest"}});
      if(!response.ok)return;
      const data=await response.json();
      if(data.enabled === false) return;
      if (Notification.permission === "default") {
        const asked = localStorage.getItem("kayi-notification-asked");
        if (!asked) { localStorage.setItem("kayi-notification-asked", "1"); await Notification.requestPermission(); }
      }
      if (Notification.permission !== "granted") return;
      const registration=await navigator.serviceWorker.ready;
      for(const item of data.notifications||[]){
        const key=`kayi-notification-${item.id}`; if(sessionStorage.getItem(key))continue; sessionStorage.setItem(key,"1");
        registration.showNotification(item.title,{body:item.message,icon:"/static/icons/icon-192.svg",data:{url:item.url||"/"}});
      }
    } catch (_) {}
  };
  notify(); window.setInterval(notify, 60000);
});


// A+Bau EVENT FORM REFINED
(() => {
  const eventPath = /^\/events\/(?:new\/|\d+\/edit\/?)/;

  const directText = (node, value) => {
    if (!node) return;
    const explicit = node.querySelector(":scope > span:first-child");
    if (explicit) {
      explicit.textContent = value;
      return;
    }
    const textNode = Array.from(node.childNodes).find(
      (child) => child.nodeType === Node.TEXT_NODE && child.textContent.trim()
    );
    if (textNode) {
      textNode.textContent = `${value} `;
      return;
    }
    const span = document.createElement("span");
    span.className = "event-field-label";
    span.textContent = value;
    node.prepend(span);
  };

  const refineEventForm = () => {
    if (!eventPath.test(window.location.pathname)) return;

    const startsAt = document.querySelector('[name="starts_at"]');
    const endsAt = document.querySelector('[name="ends_at"]');
    const form = startsAt?.closest("form") || endsAt?.closest("form");
    if (!form || form.dataset.eventFormRefined === "1") return;

    form.dataset.eventFormRefined = "1";
    form.classList.add("event-form-refined");
    document.body.classList.add("event-form-page");

    const control = (name) => form.querySelector(`[name="${name}"]`);
    const wrapper = (name) => {
      const element = control(name);
      if (!element) return null;
      return (
        element.closest("label") ||
        element.closest(".form-field") ||
        element.closest(".field") ||
        element.parentElement
      );
    };

    const normalizeField = (name, label, extraClass = "") => {
      const element = control(name);
      const box = wrapper(name);
      if (!element || !box) return null;
      box.classList.add("event-field");
      if (extraClass) {
        box.classList.add(...extraClass.split(/\s+/).filter(Boolean));
      }
      const labelNode = box.matches("label") ? box : box.querySelector("label");
      directText(labelNode || box, `${label}${element.required ? "*" : ""}`);
      return box;
    };

    const makeSection = (title, subtitle, icon, className = "") => {
      const section = document.createElement("section");
      section.className = `event-form-section ${className}`.trim();
      section.innerHTML = `
        <header class="event-form-section-head">
          <span class="event-form-section-icon" aria-hidden="true">${icon}</span>
          <div><h2>${title}</h2><p>${subtitle}</p></div>
        </header>
      `;
      const grid = document.createElement("div");
      grid.className = "event-field-grid";
      section.appendChild(grid);
      return { section, grid };
    };

    const layout = document.createElement("div");
    layout.className = "event-form-layout";
    const main = document.createElement("div");
    main.className = "event-form-main";
    const side = document.createElement("aside");
    side.className = "event-form-side";
    layout.append(main, side);

    const basics = makeSection(
      "Termin",
      "Projektbezug und Bezeichnung auf einen Blick.",
      "▣",
      "event-basics-section"
    );
    const timing = makeSection(
      "Zeit & Ort",
      "Beginn, Ende und Einsatzort kompakt zusammenfassen.",
      "◷",
      "event-timing-section"
    );
    const notes = makeSection(
      "Notizen",
      "Nur die Informationen festhalten, die das Team vor Ort braucht.",
      "✎",
      "event-notes-section"
    );
    const attendees = makeSection(
      "Teilnehmer & Erinnerungen",
      "Beteiligte auswählen und Push-Erinnerungen festlegen.",
      "◎",
      "event-attendees-section"
    );

    const title = normalizeField("title", "Titel", "event-field-full");
    const project = normalizeField("project", "Projekt");
    const type = normalizeField("type", "Typ");
    [title, project, type].filter(Boolean).forEach((node) => basics.grid.appendChild(node));

    const starts = normalizeField("starts_at", "Beginn");
    const ends = normalizeField("ends_at", "Ende");
    const location = normalizeField("location", "Ort", "event-field-full");
    [starts, ends].filter(Boolean).forEach((node) => timing.grid.appendChild(node));

    const allDayControl = control("all_day");
    const allDay = wrapper("all_day");
    if (allDayControl && allDay) {
      allDay.classList.add("event-field", "event-all-day-row", "event-field-full");
      const allDayLabel = allDay.matches("label") ? allDay : allDay.querySelector("label") || allDay;
      Array.from(allDayLabel.childNodes).forEach((child) => {
        if (child.nodeType === Node.TEXT_NODE && child.textContent.trim()) child.textContent = "";
      });
      const span = allDayLabel.querySelector(":scope > span:first-child");
      if (span) span.remove();
      if (!allDayLabel.querySelector(".event-all-day-text")) {
        const text = document.createElement("span");
        text.className = "event-all-day-text";
        text.textContent = "Ganztägig";
        allDayLabel.appendChild(text);
      }
      timing.grid.appendChild(allDay);
    }
    if (location) timing.grid.appendChild(location);

    const notesField = normalizeField("notes", "Notizen", "event-field-full");
    if (notesField) notes.grid.appendChild(notesField);

    const attendeeField = normalizeField("attendees", "Teilnehmer", "event-field-full event-attendee-field");
    if (attendeeField) attendees.grid.appendChild(attendeeField);

    const reminderChecks = Array.from(form.querySelectorAll('input[type="checkbox"]')).filter(
      (item) => item !== allDayControl && /remind|push|notification/i.test(item.name || item.id || "")
    );
    const fallbackReminderChecks = reminderChecks.length
      ? reminderChecks
      : Array.from(form.querySelectorAll('input[type="checkbox"]')).filter((item) => item !== allDayControl);
    const reminderLabels = [];
    fallbackReminderChecks.forEach((item) => {
      const label = item.closest("label");
      if (label && !reminderLabels.includes(label)) reminderLabels.push(label);
    });
    if (reminderLabels.length) {
      const reminderBlock = document.createElement("div");
      reminderBlock.className = "event-field event-field-full";
      const reminderTitle = document.createElement("span");
      reminderTitle.className = "event-field-label";
      reminderTitle.textContent = "Erinnerungen / Push";
      const options = document.createElement("div");
      options.className = "event-reminder-options";
      reminderLabels.forEach((label) => {
        label.classList.add("event-reminder-option");
        options.appendChild(label);
      });
      reminderBlock.append(reminderTitle, options);
      attendees.grid.appendChild(reminderBlock);
    }

    main.append(basics.section, timing.section, notes.section);
    side.append(attendees.section);

    const firstVisible = Array.from(form.children).find(
      (child) => !(child.matches && child.matches('input[type="hidden"]'))
    );
    if (firstVisible) form.insertBefore(layout, firstVisible);
    else form.appendChild(layout);

    form.querySelectorAll(".form-grid, .grid, .fields-grid").forEach((grid) => {
      if (grid.closest(".event-form-layout")) return;
      if (!grid.querySelector('input:not([type="hidden"]), select, textarea, button, a.btn')) {
        grid.classList.add("event-form-orphan-grid");
        grid.hidden = true;
      }
    });

    const submit = form.querySelector('button[type="submit"], input[type="submit"]');
    if (submit) {
      let actionBox = submit.closest(".form-actions, .actions, .button-row, .panel-actions");
      if (!actionBox || actionBox === form) {
        actionBox = document.createElement("div");
        actionBox.appendChild(submit);
      }
      actionBox.classList.add("event-form-actions");
      form.appendChild(actionBox);
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", refineEventForm, { once: true });
  } else {
    refineEventForm();
  }
})();


// A+Bau GLOBAL FORM SYSTEM
(() => {
  const visibleFieldSelector = [
    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"])',
    'select',
    'textarea'
  ].join(',');
  const specializedSelector = [
    '.event-form-refined',
    '[data-inline-room-model]',
    '[data-room-model-editor]',
    '.room-model-editor',
    '.configurator',
    '[data-signature-pad]',
    '.signature-pad',
    '.wizard-shell',
    '.wizard-step'
  ].join(',');
  const navigationSelector = '.topbar, .sidebar, .mobile-nav, nav, [role="navigation"]';

  const fieldWrapper = (control, form) => {
    const candidate = control.closest('label, .form-field, .form-group, .field, .field-row, .input-group');
    return candidate && form.contains(candidate) ? candidate : control.parentElement;
  };

  const markField = (control, form) => {
    const box = fieldWrapper(control, form);
    if (!box || box === form) return null;
    box.classList.add('kayi-field');
    const type = (control.type || '').toLowerCase();
    if (control.tagName === 'TEXTAREA' || type === 'file' || (control.tagName === 'SELECT' && control.multiple)) {
      box.classList.add('kayi-field-full');
    }
    if (type === 'checkbox' || type === 'radio') {
      box.classList.add('kayi-choice-field');
      const label = control.closest('label');
      if (label) label.classList.add('kayi-choice-row');
    }
    return box;
  };

  const markGrids = (form, fieldBoxes) => {
    const parents = new Map();
    fieldBoxes.forEach((box) => {
      if (!box || !box.parentElement || box.parentElement === form) return;
      const parent = box.parentElement;
      if (!parents.has(parent)) parents.set(parent, []);
      parents.get(parent).push(box);
    });
    parents.forEach((boxes, parent) => {
      if (boxes.length >= 2 && !parent.closest(specializedSelector)) {
        parent.classList.add('kayi-balanced-grid');
        if (boxes.length % 2 === 1 && boxes.length >= 3) {
          boxes[boxes.length - 1].classList.add('kayi-field-balance-last');
        }
      }
    });

    const direct = fieldBoxes.filter((box) => box && box.parentElement === form);
    if (direct.length >= 2) form.classList.add('kayi-direct-grid');
  };

  const markActions = (form) => {
    const submitters = Array.from(form.querySelectorAll('button[type="submit"], input[type="submit"], .btn-primary'));
    submitters.forEach((button) => {
      const box = button.closest('.form-actions, .actions, .button-row, .btn-row, .footer-actions') || button.parentElement;
      if (!box || box === form || !form.contains(box)) return;
      const field = box.querySelector(visibleFieldSelector);
      if (!field || field === button) box.classList.add('kayi-form-actions');
    });
  };

  const shouldSkip = (form, controls) => {
    if (form.matches('[data-no-form-polish]')) return 'explicit';
    if (form.matches('.event-form-refined')) return 'event-special';
    if (form.closest(navigationSelector)) return 'navigation';
    if (form.closest(specializedSelector) || form.querySelector(specializedSelector)) return 'specialized';
    if (!controls.length) return 'no-fields';
    return '';
  };

  const polishForm = (form) => {
    if (!(form instanceof HTMLFormElement) || form.dataset.kayiFormAudit) return;
    const controls = Array.from(form.querySelectorAll(visibleFieldSelector)).filter((control) => !control.disabled || control.offsetParent !== null);
    const skipReason = shouldSkip(form, controls);
    if (skipReason) {
      form.dataset.kayiFormAudit = `skip:${skipReason}`;
      return;
    }

    form.dataset.kayiFormAudit = 'polished';
    form.classList.add('kayi-form-polished');
    if (form.closest('.panel, .card, .modal-content, .drawer, .sheet')) form.classList.add('kayi-form-in-card');
    if ((form.method || '').toLowerCase() === 'get' || controls.length <= 2) form.classList.add('kayi-form-compact');

    const boxes = [];
    controls.forEach((control) => {
      const box = markField(control, form);
      if (box && !boxes.includes(box)) boxes.push(box);
    });
    markGrids(form, boxes);
    markActions(form);
    form.querySelectorAll('fieldset').forEach((fieldset) => fieldset.classList.add('kayi-form-fieldset'));
    document.body.classList.add('kayi-has-polished-form');
  };

  const polishAll = (root = document) => {
    if (root instanceof HTMLFormElement) polishForm(root);
    root.querySelectorAll?.('form').forEach(polishForm);
  };

  const start = () => {
    polishAll(document);
    const observer = new MutationObserver((records) => {
      records.forEach((record) => record.addedNodes.forEach((node) => {
        if (node instanceof Element) polishAll(node);
      }));
    });
    observer.observe(document.body, {childList: true, subtree: true});
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
