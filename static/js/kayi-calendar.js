(() => {
  "use strict";

  const getCookie = (name) => {
    const parts = document.cookie ? document.cookie.split(";") : [];
    for (const raw of parts) {
      const item = raw.trim();
      if (item.startsWith(name + "=")) return decodeURIComponent(item.slice(name.length + 1));
    }
    return "";
  };

  const init = () => {
    const root = document.querySelector("[data-calendar-view]");
    if (!root || root.dataset.calendarDispatch !== "1") return;
    const status = root.querySelector("[data-calendar-status]");
    let dragged = null;
    let draggedFrom = null;

    const setStatus = (text, kind = "") => {
      if (!status) return;
      status.textContent = text;
      status.dataset.kind = kind;
    };

    root.querySelectorAll("[data-calendar-event][draggable='true']").forEach((eventCard) => {
      eventCard.addEventListener("dragstart", (event) => {
        dragged = eventCard;
        draggedFrom = eventCard.closest("[data-calendar-drop-date]")?.dataset.calendarDropDate || "";
        eventCard.classList.add("is-dragging");
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", eventCard.dataset.eventId || "");
      });
      eventCard.addEventListener("dragend", () => {
        eventCard.classList.remove("is-dragging");
        root.querySelectorAll(".is-drop-target").forEach((el) => el.classList.remove("is-drop-target"));
        dragged = null;
        draggedFrom = null;
      });
    });

    root.querySelectorAll("[data-calendar-drop-date]").forEach((zone) => {
      zone.addEventListener("dragover", (event) => {
        if (!dragged) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        zone.classList.add("is-drop-target");
      });
      zone.addEventListener("dragleave", (event) => {
        if (!zone.contains(event.relatedTarget)) zone.classList.remove("is-drop-target");
      });
      zone.addEventListener("drop", async (event) => {
        if (!dragged) return;
        event.preventDefault();
        zone.classList.remove("is-drop-target");
        const date = zone.dataset.calendarDropDate;
        if (!date || date === draggedFrom) {
          setStatus("Termin bleibt am bisherigen Tag.");
          return;
        }
        const url = dragged.dataset.moveUrl;
        if (!url) return;
        setStatus("Termin wird verschoben …");
        try {
          const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": getCookie("csrftoken"),
              "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify({ date }),
          });
          const data = await response.json().catch(() => ({}));
          if (!response.ok || !data.ok) throw new Error(data.error || "Termin konnte nicht verschoben werden.");
          setStatus("Termin verschoben. Kalender wird aktualisiert …", "success");
          window.setTimeout(() => window.location.reload(), 260);
        } catch (error) {
          setStatus(error?.message || "Termin konnte nicht verschoben werden.", "error");
        }
      });
    });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
