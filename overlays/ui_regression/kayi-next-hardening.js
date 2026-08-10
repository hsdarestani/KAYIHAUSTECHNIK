// KAYI UI regression hardening 20260810
(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const esc = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const money = (value) => Number(value || 0).toLocaleString("de-DE", {
    style: "currency",
    currency: "EUR",
  });

  const toast = (title, text = "") => {
    let stack = $(".nx-toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "nx-toast-stack";
      document.body.append(stack);
    }
    const node = document.createElement("div");
    node.className = "nx-toast";
    node.innerHTML = `<b>${esc(title)}</b>${text ? `<span>${esc(text)}</span>` : ""}`;
    stack.append(node);
    window.setTimeout(() => node.remove(), 4800);
  };

  const recalcDocument = (table) => {
    let net = 0;
    let tax = 0;
    $$("tbody tr", table).forEach((row) => {
      const qty = Number($("[name='item_quantity']", row)?.value || 0);
      const price = Number($("[name='item_price']", row)?.value || 0);
      const rate = Number($("[name='item_tax']", row)?.value || 0);
      const line = qty * price;
      net += line;
      tax += line * rate / 100;
    });
    const discount = Number(document.querySelector("[name='discount_percent']")?.value || 0);
    const factor = 1 - Math.max(0, Math.min(100, discount)) / 100;
    net *= factor;
    tax *= factor;
    [["net", net], ["tax", tax], ["gross", net + tax]].forEach(([key, value]) => {
      const target = document.querySelector(`[data-total='${key}']`);
      if (target) target.textContent = money(value);
    });
  };

  const wireDocumentRow = (row, table) => {
    $(".nx-item-remove", row)?.addEventListener("click", () => {
      row.remove();
      recalcDocument(table);
    });
    $$('input', row).forEach((input) => input.addEventListener("input", () => recalcDocument(table)));
  };

  const addDocumentRow = (table, values = {}) => {
    const tbody = $("tbody", table);
    if (!tbody) {
      toast("Position konnte nicht hinzugefügt werden", "Die Positionsliste wurde nicht gefunden. Bitte Seite neu laden.");
      return;
    }
    const row = document.createElement("tr");
    row.innerHTML = `<td><input class="nx-control desc" name="item_description" value="${esc(values.description || "")}" placeholder="Leistung oder Material"></td><td><input class="nx-control" name="item_quantity" type="number" min="0" step="0.001" value="${esc(values.quantity ?? 1)}"></td><td><input class="nx-control" name="item_unit" value="${esc(values.unit || "Stk.")}"></td><td><input class="nx-control" name="item_price" type="number" min="0" step="0.01" value="${esc(values.price ?? 0)}"></td><td><input class="nx-control" name="item_tax" type="number" min="0" step="0.01" value="${esc(values.tax ?? 19)}"></td><td><button type="button" class="nx-item-remove" aria-label="Position entfernen">×</button></td>`;
    wireDocumentRow(row, table);
    tbody.append(row);
    recalcDocument(table);
    $(".desc", row)?.focus();
  };

  $$('[data-add-item]').forEach((button) => {
    if (button.dataset.nxAddBound === "1" || button.dataset.nxInlineBound === "1") return;
    const form = button.closest("form") || document;
    const table = $("[data-document-items]", form);
    button.dataset.nxAddBound = "1";
    button.addEventListener("click", () => {
      if (!table) {
        toast("Position kann hier nicht hinzugefügt werden", "Die Positionsliste wurde nicht gefunden. Bitte Seite neu laden.");
        return;
      }
      addDocumentRow(table);
    });
  });

  $$('[data-select-search]').forEach((input) => {
    const select = document.getElementById(input.dataset.selectSearch);
    if (!select) return;
    const status = input.parentElement?.querySelector("[data-select-search-status]");
    const options = Array.from(select.options).map((option) => ({
      option,
      text: option.textContent.trim().toLocaleLowerCase("de-DE"),
      placeholder: !option.value,
    }));
    const apply = () => {
      const query = input.value.trim().toLocaleLowerCase("de-DE");
      let matches = 0;
      let sole = null;
      options.forEach(({ option, text, placeholder }) => {
        const show = placeholder || !query || text.includes(query);
        option.hidden = !show;
        if (show && !placeholder) {
          matches += 1;
          sole = option;
        }
      });
      if (status) status.textContent = query ? `${matches} Kunde${matches === 1 ? "" : "n"} gefunden.` : "Tippen, um die Kundenliste zu filtern.";
      return { matches, sole };
    };
    input.addEventListener("input", apply);
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      const { matches, sole } = apply();
      if (matches === 1 && sole) {
        select.value = sole.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        toast("Kunde ausgewählt", sole.textContent.trim());
      } else if (matches === 0) {
        toast("Kein Kunde gefunden", "Suchbegriff ändern oder einen neuen Kunden anlegen.");
      } else {
        toast("Mehrere Treffer", `${matches} Kunden passen zur Suche. Bitte einen auswählen.`);
      }
    });
  });

  const updateSelectedChips = (select) => {
    let box = select.parentElement?.querySelector(".nx-selected-chips");
    if (!box) {
      box = document.createElement("div");
      box.className = "nx-selected-chips";
      select.insertAdjacentElement("afterend", box);
    }
    const selected = Array.from(select.selectedOptions).filter((option) => option.value);
    box.innerHTML = selected.length
      ? selected.map((option) => `<span class="nx-selected-chip">${esc(option.textContent.trim())}</span>`).join("")
      : '<span class="nx-muted" style="font-size:10px">Noch nichts ausgewählt.</span>';
  };

  $$('select[multiple]').forEach((select) => {
    updateSelectedChips(select);
    select.addEventListener("change", () => updateSelectedChips(select));
  });

  $$('[data-row-href]').forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target.closest("a,button,input,select,textarea,label")) return;
      if (row.dataset.rowHref) window.location.href = row.dataset.rowHref;
    });
  });

  $$('[data-settings-help]').forEach((button) => {
    button.addEventListener("click", () => {
      const context = button.closest("section,article,.card,.panel,.integration-card,li,div");
      const heading = context?.querySelector("h1,h2,h3,h4,strong,b")?.textContent?.trim();
      const subject = heading || button.textContent.trim() || "Diese Einstellung";
      toast(
        `${subject}: keine direkte Aktion`,
        "Für diese Einstellung ist an dieser Stelle keine direkte Aktion hinterlegt. Nutze die zugehörige Integrations- oder Konfigurationsmaske. Falls sie dort nicht verfügbar ist, wende dich an den Support.",
      );
    });
  });

  const catalogList = $("[data-catalog-list]");
  const catalogSearch = $("[data-catalog-search]");
  const catalogSearchButton = $("[data-catalog-search-button]");
  const catalogStatus = $("[data-catalog-search-status]");
  const catalogSelected = $("[data-catalog-selected]");
  const documentTable = $("[data-document-items]");
  if (catalogList && catalogSearch && documentTable) {
    const normalize = (value) => String(value || "").trim().toLocaleLowerCase("de-DE");
    const catalogItems = () => $$("[data-catalog-item]", catalogList);
    const filterCatalog = () => {
      const query = normalize(catalogSearch.value);
      let visible = 0;
      catalogItems().forEach((button) => {
        const haystack = normalize(`${button.dataset.name || ""} ${button.dataset.code || ""} ${button.textContent || ""}`);
        const show = !query || haystack.includes(query);
        button.hidden = !show;
        if (show) visible += 1;
      });
      if (catalogStatus) catalogStatus.textContent = query ? `${visible} Treffer für „${catalogSearch.value.trim()}“.` : "Alle Katalogpositionen werden angezeigt.";
    };
    const syncCatalogSelection = () => {
      const descriptions = $$("[name='item_description']", documentTable).map((input) => normalize(input.value)).filter(Boolean);
      const chosen = [];
      catalogItems().forEach((button) => {
        const name = normalize(button.dataset.name);
        const selected = Boolean(name) && descriptions.includes(name);
        button.classList.toggle("is-selected", selected);
        if (selected && !chosen.includes(button.dataset.name)) chosen.push(button.dataset.name);
      });
      if (catalogSelected) {
        catalogSelected.innerHTML = chosen.length
          ? chosen.map((name) => `<span class="nx-selected-chip">${esc(name)}</span>`).join("")
          : '<span class="nx-muted">Noch keine Katalogposition ausgewählt.</span>';
      }
    };
    catalogSearch.addEventListener("input", filterCatalog);
    catalogSearch.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      filterCatalog();
      const visible = catalogItems().filter((button) => !button.hidden);
      if (visible.length === 1) visible[0].focus();
    });
    catalogSearchButton?.addEventListener("click", (event) => {
      event.preventDefault();
      filterCatalog();
      catalogSearch.focus();
    });
    catalogList.addEventListener("click", (event) => {
      if (event.target.closest("[data-catalog-item]")) window.setTimeout(syncCatalogSelection, 0);
    });
    documentTable.addEventListener("input", syncCatalogSelection);
    documentTable.addEventListener("click", (event) => {
      if (event.target.closest(".nx-item-remove")) window.setTimeout(syncCatalogSelection, 0);
    });
    new MutationObserver(syncCatalogSelection).observe(documentTable.querySelector("tbody") || documentTable, { childList: true, subtree: true });
    syncCatalogSelection();
  }

  $$(".nx-content button[type='button']:not([disabled])").forEach((button) => {
    if (button.classList.contains("nx-item-remove") || button.onclick) return;
    if (Array.from(button.attributes).some((attribute) => attribute.name.startsWith("data-"))) return;
    button.addEventListener("click", () => toast(
      "Aktion noch nicht verfügbar",
      "Für diese Aktion ist hier noch keine Funktion hinterlegt. Nutze die verknüpfte Projektfunktion oder melde den konkreten Schritt an den Support.",
    ));
  });
})();
