
// KAYI 3D KI assistant polish 20260810
(() => {
  // The 3D room must stay readable from every camera angle. Keep every wall
  // translucent in every view and remove the old on/off control so saved
  // state, KI drafts and photo reconstructions cannot make walls opaque again.
  const forceAlwaysTransparentWalls = () => {
    state.view ||= {};
    state.view.transparent_near_walls = true;
    wallMeshes.forEach((wall) => {
      if (!wall?.material) return;
      wall.material.transparent = true;
      wall.material.opacity = 0.22;
      wall.material.depthWrite = false;
      wall.material.needsUpdate = true;
    });
  };
  updateWallTransparency = forceAlwaysTransparentWalls;
  $('[data-rp-toggle="transparent_near_walls"]', root)?.remove();
  forceAlwaysTransparentWalls();
  queueRender();

  const commandInput = $('[data-rp-ai-command]', root);
  const runButton = $('[data-rp-run-ai]', root);
  const feedback = $('[data-rp-ai-feedback]', root);
  if (!commandInput || !runButton || !root.dataset.aiUrl) return;

  const safeMessage = (error, fallback) => {
    const raw = String(error?.message || '');
    if (/Failed to fetch|NetworkError|Load failed|fetch failed/i.test(raw)) {
      return 'Netzwerkfehler. Bitte Internetverbindung prüfen und erneut versuchen.';
    }
    return raw || fallback;
  };

  const requestJson = async (url, options, fallback) => {
    const response = await fetch(url, {
      credentials: 'same-origin',
      ...options,
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        ...(options?.headers || {}),
      },
    });
    const contentType = (response.headers.get('content-type') || '').toLowerCase();
    const raw = await response.text();
    if (!contentType.includes('application/json')) {
      if (response.status === 403) throw new Error('Sicherheitsprüfung fehlgeschlagen. Bitte Seite einmal neu laden und erneut versuchen.');
      if (response.status === 429) throw new Error('Zu viele KI-Anfragen. Bitte kurz warten und erneut versuchen.');
      if (response.status >= 500) throw new Error('Der KI-Raumassistent ist momentan nicht erreichbar. Bitte später erneut versuchen.');
      throw new Error(fallback);
    }
    let data = {};
    try { data = raw ? JSON.parse(raw) : {}; } catch (_) { throw new Error(fallback); }
    if (!response.ok) {
      const error = new Error(data.error || fallback);
      error.consentRequired = response.status === 428 && Boolean(data.consent_required);
      error.settingsUrl = data.settings_url || '/settings/next/';
      throw error;
    }
    return data;
  };

  const setFeedback = (message, stateName = '') => {
    if (!feedback) return;
    feedback.hidden = false;
    feedback.dataset.state = stateName;
    feedback.innerHTML = message;
  };

  $$('[data-rp-ai-example]', root).forEach((button) => {
    button.addEventListener('click', () => {
      commandInput.value = button.dataset.rpAiExample || button.textContent.trim();
      commandInput.focus();
    });
  });

  runButton.addEventListener('click', async () => {
    const command = commandInput.value.trim();
    if (!command) {
      setFeedback('<strong>Anweisung fehlt.</strong>Beschreibe kurz, was die KI im Raum ändern soll.', 'error');
      commandInput.focus();
      return;
    }
    runButton.disabled = true;
    setFeedback('<strong>KI arbeitet am Raum …</strong>Bestehende Objekte werden berücksichtigt und nicht erwähnte Elemente bleiben erhalten.', 'loading');
    try {
      const data = await requestJson(root.dataset.aiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf(),
        },
        body: JSON.stringify({
          measurement_id: root.dataset.measurementId || null,
          command,
          state,
        }),
      }, 'Der KI-Vorschlag konnte nicht verarbeitet werden.');

      state = normalizeState(data.state || state);
      history = history.slice(0, historyIndex + 1);
      history.push(deepClone(state));
      historyIndex = history.length - 1;
      dirty = true;
      syncControlsFromState();
      rebuildScene({ keepCamera: true });
      renderInspector();
      updateUndoRedo();
      if (saveStatus) {
        saveStatus.textContent = 'KI-Vorschlag noch nicht gespeichert';
        saveStatus.dataset.state = 'dirty';
      }
      const warnings = Array.isArray(data.warnings) && data.warnings.length
        ? `<ul>${data.warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
        : '';
      setFeedback(`<strong>${escapeHtml(data.summary || 'KI-Vorschlag angewendet.')}</strong>${warnings}<small>Prüfe den Vorschlag im 3D-Raum und speichere anschließend bewusst eine neue Version.</small>`, 'success');
      toast('KI-Vorschlag im 3D-Raum angewendet.','success');
    } catch (error) {
      const message = safeMessage(error, 'Der KI-Raumassistent konnte die Änderung nicht ausführen.');
      if (error?.consentRequired) {
        const settingsUrl = String(error.settingsUrl || '/settings/next/').replace(/"/g, '&quot;');
        setFeedback(`<strong>Einwilligung erforderlich.</strong>${escapeHtml(message)}<br><a class="nx-btn" style="margin-top:8px" href="${settingsUrl}">KI-Einwilligung in den Einstellungen öffnen →</a>`, 'error');
      } else {
        setFeedback(`<strong>KI konnte die Änderung nicht anwenden.</strong>${escapeHtml(message)}`, 'error');
      }
      toast(message, 'error');
    } finally {
      runButton.disabled = false;
    }
  });
})();
