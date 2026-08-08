from __future__ import annotations

from pathlib import Path


CSS_MARKER = "/* KAYI EVENT FORM REFINED */"
JS_MARKER = "// KAYI EVENT FORM REFINED"
ASSET_VERSION = "20260809-0035"


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


css_path = Path("static/css/app.css")
css = css_path.read_text(encoding="utf-8")
if CSS_MARKER not in css:
    css += r'''

/* KAYI EVENT FORM REFINED */
.event-form-page .content {
  width: min(100%, 1280px);
  margin-inline: auto;
  padding-bottom: 44px;
}
.event-form-page .event-form-refined.panel,
.event-form-page .event-form-refined {
  padding: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  overflow: visible !important;
}
.event-form-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 350px;
  gap: 20px;
  align-items: start;
}
.event-form-main,
.event-form-side {
  display: grid;
  gap: 18px;
  min-width: 0;
}
.event-form-side {
  position: sticky;
  top: 88px;
}
.event-form-section {
  min-width: 0;
  padding: 20px;
  border: 1px solid var(--border, #dfe6ef);
  border-radius: 18px;
  background: var(--surface, #fff);
  box-shadow: 0 10px 30px rgba(28, 47, 78, .055);
}
.event-form-section-head {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 18px;
}
.event-form-section-icon {
  display: grid;
  place-items: center;
  flex: 0 0 36px;
  width: 36px;
  height: 36px;
  border-radius: 11px;
  color: #1769d2;
  background: rgba(23, 105, 210, .09);
  font-size: 17px;
  font-weight: 800;
}
.event-form-section-head h2 {
  margin: 0;
  font-size: 16px;
  line-height: 1.25;
}
.event-form-section-head p {
  margin: 4px 0 0;
  color: var(--muted, #748096);
  font-size: 12.5px;
  line-height: 1.45;
}
.event-field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  align-items: start;
}
.event-field-grid.event-field-grid-single {
  grid-template-columns: 1fr;
}
.event-field,
.event-field > label,
.event-field label {
  min-width: 0;
}
.event-field.event-field-full {
  grid-column: 1 / -1;
}
.event-form-page .event-field > label,
.event-form-page .event-field label:not(.event-reminder-option),
.event-form-page label.event-field {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin: 0;
}
.event-form-page .event-field-label,
.event-form-page .event-field > label > span:first-child,
.event-form-page label.event-field > span:first-child {
  color: var(--text, #111827);
  font-size: 12.5px;
  font-weight: 750;
}
.event-form-page .event-form-section input:not([type="checkbox"]):not([type="radio"]),
.event-form-page .event-form-section select,
.event-form-page .event-form-section textarea,
.event-form-page .event-form-section .form-control {
  width: 100%;
  min-width: 0;
  min-height: 44px;
  border-radius: 11px;
}
.event-form-page .event-form-section textarea {
  min-height: 126px;
  max-height: 240px;
  resize: vertical;
}
.event-form-page .event-form-section select[multiple] {
  min-height: 94px;
  max-height: 132px;
}
.event-form-page .event-field-help {
  margin-top: 1px;
  color: var(--muted, #7a879b);
  font-size: 11.5px;
  line-height: 1.4;
}
.event-all-day-row {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 0 12px;
  border: 1px solid var(--border, #dfe6ef);
  border-radius: 11px;
  background: color-mix(in srgb, var(--surface, #fff) 94%, #edf4ff 6%);
}
.event-all-day-row label,
.event-all-day-row.event-field {
  display: flex !important;
  flex-direction: row !important;
  gap: 9px !important;
  align-items: center;
  width: 100%;
  cursor: pointer;
  font-size: 12.5px;
  font-weight: 650;
}
.event-form-page input[type="checkbox"] {
  width: 17px;
  height: 17px;
  accent-color: #1f73d2;
}
.event-reminder-options {
  display: grid;
  gap: 8px;
}
.event-reminder-option {
  display: flex !important;
  flex-direction: row !important;
  gap: 9px !important;
  align-items: center;
  min-height: 38px;
  margin: 0 !important;
  padding: 9px 11px;
  border: 1px solid var(--border, #e1e7ef);
  border-radius: 10px;
  background: var(--surface, #fff);
  color: var(--text, #263244);
  font-size: 12.5px;
  font-weight: 550 !important;
  cursor: pointer;
}
.event-reminder-option:hover {
  border-color: rgba(31, 115, 210, .38);
  background: rgba(31, 115, 210, .035);
}
.event-attendee-field .searchable-select,
.event-attendee-field [data-searchable-wrap] {
  width: 100%;
}
.event-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
  padding: 14px 16px;
  border: 1px solid var(--border, #dfe6ef);
  border-radius: 14px;
  background: var(--surface, #fff);
  box-shadow: 0 8px 24px rgba(28, 47, 78, .05);
}
.event-form-page .event-form-actions .btn,
.event-form-page .event-form-actions button,
.event-form-page .event-form-actions input[type="submit"] {
  min-height: 42px;
}
.event-form-page .event-form-orphan-grid:empty,
.event-form-page .event-form-orphan-grid[hidden] {
  display: none !important;
}
@media (max-width: 1050px) {
  .event-form-layout { grid-template-columns: 1fr; }
  .event-form-side { position: static; }
}
@media (max-width: 700px) {
  .event-form-page .content { padding-inline: 14px; }
  .event-form-section { padding: 16px; border-radius: 15px; }
  .event-field-grid { grid-template-columns: 1fr; gap: 13px; }
  .event-field.event-field-full { grid-column: auto; }
  .event-form-actions { position: sticky; bottom: 8px; z-index: 8; }
}
'''
    css_path.write_text(css, encoding="utf-8")


js_path = Path("static/js/app.js")
js = js_path.read_text(encoding="utf-8")
if JS_MARKER not in js:
    js += r'''

// KAYI EVENT FORM REFINED
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
      if (extraClass) box.classList.add(extraClass);
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
'''
    js_path.write_text(js, encoding="utf-8")


for path in (
    "templates/erp/base.html",
    "templates/registration/login.html",
    "static/js/app.js",
    "static/js/sw.js",
):
    text = read(path)
    text = text.replace("20260808-2225", ASSET_VERSION)
    if path == "static/js/sw.js":
        text = text.replace("kayi-shell-v20-20260808", "kayi-shell-v21-20260809")
    write(path, text)


css = read("static/css/app.css")
js = read("static/js/app.js")
required_css = (
    CSS_MARKER,
    ".event-form-layout",
    ".event-reminder-options",
    "@media (max-width: 700px)",
)
required_js = (
    JS_MARKER,
    'document.body.classList.add("event-form-page")',
    '"Teilnehmer & Erinnerungen"',
    'normalizeField("starts_at", "Beginn")',
    'normalizeField("ends_at", "Ende")',
)
for marker in required_css:
    if marker not in css:
        raise RuntimeError(f"Event form CSS guard failed: {marker!r}")
for marker in required_js:
    if marker not in js:
        raise RuntimeError(f"Event form JS guard failed: {marker!r}")
if ASSET_VERSION not in read("templates/erp/base.html"):
    raise RuntimeError("Event form cache-bust guard failed")

print("KAYI event form layout refined and verified.")
