
(() => {
  "use strict";
  const MARK = "A_BAU_V3_FINANCE_MOBILE_PDF_HOTFIX_2026_09_08";
  if (window[MARK]) return;
  window[MARK] = true;
  const body = document.body;
  if (!body) return;

  const menuButton = document.querySelector("[data-nx-menu]");
  const sidebar = document.querySelector(".nx-sidebar");
  const overlay = document.querySelector("[data-nx-menu-overlay]");
  const mobile = () => window.matchMedia("(max-width: 860px)").matches;
  const setMenu = (open) => {
    const next = Boolean(open && mobile());
    body.classList.toggle("nx-menu-open", next);
    menuButton?.setAttribute("aria-expanded", next ? "true" : "false");
    sidebar?.toggleAttribute("data-ab-mobile-open", next);
    if (next) {
      document.querySelector("[data-ab-v3-command].is-open [data-ab-v3-command-close]")?.click();
    }
  };

  document.addEventListener("click", (event) => {
    const more = event.target.closest?.("[data-ab-open-menu]");
    if (!more) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    setMenu(true);
  }, true);

  overlay?.addEventListener("click", () => setMenu(false));
  sidebar?.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => {
    if (mobile()) setMenu(false);
  }));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && body.classList.contains("nx-menu-open")) setMenu(false);
  });
  window.matchMedia("(min-width: 861px)").addEventListener?.("change", (event) => {
    if (event.matches) setMenu(false);
  });

  if (document.querySelector(".ttq-page")) body.classList.add("ab-v3-quotes");
  if (document.querySelector(".tti-page")) body.classList.add("ab-v3-invoices");
  if (document.querySelector(".ttc-page")) body.classList.add("ab-v3-catalogue");
  if (document.querySelector(".tt-document-form")) body.classList.add("ab-v3-document-editor");
  body.dataset.abFinanceMobilePdfHotfix = "ready";
})();
