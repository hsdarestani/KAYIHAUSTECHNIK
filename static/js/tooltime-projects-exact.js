(() => {
  "use strict";
  const page = document.querySelector("[data-tooltime-projects-exact]");
  if (!page) return;

  const modal = page.querySelector("[data-project-modal]");
  const title = page.querySelector("[data-project-title]");
  const openModal = () => {
    if (!modal) return;
    modal.hidden = false;
    document.body.classList.add("ttp-modal-lock");
    window.setTimeout(() => title && title.focus(), 0);
  };
  const closeModal = () => {
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove("ttp-modal-lock");
  };
  page.querySelectorAll("[data-project-modal-open]").forEach((button) => button.addEventListener("click", openModal));
  page.querySelectorAll("[data-project-modal-close]").forEach((button) => button.addEventListener("click", closeModal));
  if (page.dataset.modalOpen === "1") openModal();
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal && !modal.hidden) closeModal();
  });

  page.querySelectorAll("[data-auto-filter] select").forEach((select) => {
    select.addEventListener("change", () => select.form && select.form.submit());
  });

  const size = page.querySelector("[data-page-size]");
  if (size) size.addEventListener("change", () => {
    const url = new URL(window.location.href);
    url.searchParams.set("amount", size.value);
    url.searchParams.set("offset", "0");
    window.location.assign(url.toString());
  });

  page.querySelectorAll("[data-project-row]").forEach((row) => {
    const go = () => row.dataset.href && window.location.assign(row.dataset.href);
    row.addEventListener("click", (event) => {
      if (event.target.closest("a,button,input,select,textarea,summary,details,label")) return;
      go();
    });
    row.addEventListener("keydown", (event) => {
      if ((event.key === "Enter" || event.key === " ") && !event.target.closest("a,button,input,select,textarea,summary,details")) {
        event.preventDefault();
        go();
      }
    });
  });

  const storageKey = "ab-bau-tooltime-project-columns-v1";
  let state = {};
  try { state = JSON.parse(window.localStorage.getItem(storageKey) || "{}"); } catch (_) { state = {}; }
  const applyColumn = (name, visible) => {
    page.querySelectorAll(`[data-col="${name}"]`).forEach((cell) => cell.classList.toggle("ttp-col-hidden", !visible));
  };
  page.querySelectorAll("[data-column-toggle]").forEach((input) => {
    const name = input.dataset.columnToggle;
    if (Object.prototype.hasOwnProperty.call(state, name)) input.checked = Boolean(state[name]);
    applyColumn(name, input.checked);
    input.addEventListener("change", () => {
      state[name] = input.checked;
      applyColumn(name, input.checked);
      try { window.localStorage.setItem(storageKey, JSON.stringify(state)); } catch (_) {}
    });
  });
})();
