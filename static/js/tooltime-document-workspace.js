(() => {
  "use strict";
  const form = document.querySelector("form.tti-invoice-draft-form");
  if (!form) return;
  document.body.classList.add("tti-invoice-draft-page");
  const main = form.closest("main") || document.querySelector("main");
  if (main) main.classList.add("tti-invoice-draft-main");
  form.querySelectorAll("section.tt-card").forEach((card, index) => card.dataset.ttiCardIndex = String(index));
})();
