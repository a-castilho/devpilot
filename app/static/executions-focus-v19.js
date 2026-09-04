(() => {
  'use strict';

  if (window.__devpilotExecutionsFocusV20) return;
  window.__devpilotExecutionsFocusV20 = true;

  let pending = null;
  let focusTimer = 0;
  let removeTimer = 0;

  const qs = (selector, root = document) => root.querySelector(selector);

  function escapeSelector(value) {
    if (window.CSS?.escape) return window.CSS.escape(String(value));
    return String(value).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
  }

  function injectStyles() {
    if (qs('#devpilot-executions-focus-v20-style')) return;

    const style = document.createElement('style');
    style.id = 'devpilot-executions-focus-v20-style';
    style.textContent = `
      #tasks-view .dp-execution-focus-v20 {
        position: relative;
        z-index: 2;
        border-color: rgba(72, 229, 211, .58) !important;
        box-shadow:
          0 0 0 1px rgba(72, 229, 211, .18),
          0 0 22px rgba(51, 220, 205, .20),
          0 0 52px rgba(67, 159, 255, .11) !important;
        transition:
          box-shadow .28s ease,
          border-color .28s ease,
          background-color .28s ease,
          transform .28s ease;
      }

      #tasks-view .dp-execution-focus-v20::after {
        content: '';
        pointer-events: none;
        position: absolute;
        inset: -1px;
        border-radius: inherit;
        box-shadow: inset 0 0 24px rgba(71, 226, 208, .055);
        opacity: 1;
      }

      #tasks-view .dp-execution-focus-v20-pulse {
        animation: dpExecutionFocusV20 1.45s ease-out 1;
      }

      @keyframes dpExecutionFocusV20 {
        0% {
          box-shadow:
            0 0 0 1px rgba(72, 229, 211, .34),
            0 0 8px rgba(51, 220, 205, .10),
            0 0 14px rgba(67, 159, 255, .06);
        }
        42% {
          box-shadow:
            0 0 0 2px rgba(72, 229, 211, .30),
            0 0 34px rgba(51, 220, 205, .30),
            0 0 68px rgba(67, 159, 255, .17);
        }
        100% {
          box-shadow:
            0 0 0 1px rgba(72, 229, 211, .18),
            0 0 22px rgba(51, 220, 205, .20),
            0 0 52px rgba(67, 159, 255, .11);
        }
      }

      @media (prefers-reduced-motion: reduce) {
        #tasks-view .dp-execution-focus-v20,
        #tasks-view .dp-execution-focus-v20-pulse {
          animation: none !important;
          transition: none !important;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function taskIdFromTrigger(trigger) {
    if (!trigger) return '';

    const direct =
      trigger.dataset.taskId ||
      trigger.dataset.executionId ||
      trigger.dataset.executionTaskId ||
      trigger.dataset.focusTaskId ||
      trigger.dataset.taskFocusId ||
      '';

    if (direct) return String(direct);

    const owner = trigger.closest?.('[data-task-id]');
    if (owner?.dataset.taskId) return String(owner.dataset.taskId);

    const href = String(trigger.getAttribute?.('href') || '');
    if (href) {
      try {
        const url = new URL(href, window.location.href);
        return String(
          url.searchParams.get('task') ||
          url.searchParams.get('task_id') ||
          url.searchParams.get('execution') ||
          ''
        );
      } catch (_) {}
    }

    return '';
  }

  function projectIdFromTrigger(trigger) {
    if (!trigger) return '';

    return String(
      trigger.dataset.projectId ||
      trigger.dataset.projectTask ||
      trigger.closest?.('[data-project-id]')?.dataset.projectId ||
      ''
    );
  }

  function targetFor(request = {}) {
    const view = qs('#tasks-view');
    if (!view) return null;

    if (request.taskId) {
      const id = escapeSelector(request.taskId);
      const taskTarget =
        qs(`[data-task-id="${id}"]`, view) ||
        qs(`[data-task-details-row="${id}"]`, view) ||
        qs(`[data-id="${id}"]`, view);

      if (taskTarget) {
        return taskTarget.closest?.('.tasks-v9-row, .task-main-row, article, tr') || taskTarget;
      }
    }

    if (request.projectId) {
      const project = escapeSelector(request.projectId);
      const projectTarget =
        qs(`[data-project-id="${project}"]`, view) ||
        qs(`[data-task-project-id="${project}"]`, view);

      if (projectTarget) {
        return projectTarget.closest?.('.tasks-v9-row, .task-main-row, article, tr') || projectTarget;
      }
    }

    return (
      qs('#tasks-table .tasks-v9-row', view) ||
      qs('#tasks-table .task-main-row', view) ||
      qs('.tasks-v9-table-wrap', view) ||
      qs('.tasks-v9-filters', view) ||
      qs('.tasks-v9-header', view) ||
      view
    );
  }

  function clearPrevious() {
    document.querySelectorAll('.dp-execution-focus-v20').forEach(element => {
      element.classList.remove(
        'dp-execution-focus-v20',
        'dp-execution-focus-v20-pulse'
      );
    });

    window.clearTimeout(removeTimer);
  }

  function focusTarget(target) {
    if (!target) return false;

    clearPrevious();

    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;

    target.scrollIntoView({
      behavior: reduceMotion ? 'auto' : 'smooth',
      block: 'center',
      inline: 'nearest',
    });

    window.setTimeout(() => {
      target.classList.add(
        'dp-execution-focus-v20',
        'dp-execution-focus-v20-pulse'
      );

      removeTimer = window.setTimeout(() => {
        target.classList.remove(
          'dp-execution-focus-v20',
          'dp-execution-focus-v20-pulse'
        );
      }, reduceMotion ? 1500 : 3200);
    }, reduceMotion ? 0 : 180);

    return true;
  }

  function tryFocus(attempt = 0) {
    window.clearTimeout(focusTimer);

    if (!pending) return;

    const view = qs('#tasks-view');
    if (!view?.classList.contains('active')) {
      if (attempt < 30) focusTimer = window.setTimeout(() => tryFocus(attempt + 1), 80);
      return;
    }

    const target = targetFor(pending);
    if (!target && attempt < 30) {
      focusTimer = window.setTimeout(() => tryFocus(attempt + 1), 80);
      return;
    }

    const request = pending;
    pending = null;
    if (!focusTarget(target)) pending = request;
  }

  function requestFocus(options = {}) {
    pending = {
      taskId: String(options.taskId || ''),
      projectId: String(options.projectId || ''),
      source: String(options.source || 'navigation'),
    };

    window.setTimeout(() => tryFocus(0), 30);
    return true;
  }

  function detailRowFor(view, id) {
    const escaped = escapeSelector(id);
    return (
      qs(`[data-task-details-row="${escaped}"]`, view) ||
      qs(`.task-inline-details[data-task-instructions="${escaped}"]`, view)
    );
  }

  function detailButtons(view, id) {
    return [...view.querySelectorAll('.tasks-v9-details[data-id], .task-instructions-load[data-id]')]
      .filter(button => String(button.dataset.id || '') === String(id));
  }

  function forceDetailState(view, id, open) {
    const row = detailRowFor(view, id);
    if (!row) return;

    row.hidden = !open;
    row.setAttribute('aria-hidden', open ? 'false' : 'true');
    row.dataset.dpDetailsActive = open ? '1' : '0';
    row.dataset.dpV13Open = open ? '1' : '0';
    row.style.setProperty('display', open ? 'block' : 'none', 'important');

    detailButtons(view, id).forEach(button => {
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
      button.classList.toggle('dp-details-open', open);
      button.classList.toggle('dp-v13-open', open);
      if (button.classList.contains('tasks-v9-details')) {
        button.textContent = open ? 'Ocultar' : 'Detalhes';
      }
    });
  }

  function syncDetailsStateAfterClick(event) {
    const button = event.target.closest?.(
      '#tasks-view .tasks-v9-details[data-id], #tasks-view .task-instructions-load[data-id]'
    );
    if (!button) return;

    const id = String(button.dataset.id || '');
    const view = qs('#tasks-view');
    if (!id || !view) return;

    const row = detailRowFor(view, id);
    if (!row) return;

    // O renderer já alterou hidden/display no alvo. A partir deste ponto esta ponte
    // transforma esse estado em contrato explícito para o reconciliador V41.
    const open = !row.hidden && row.style.getPropertyValue('display') !== 'none';

    if (open) {
      view.querySelectorAll('[data-task-details-row], .task-inline-details[data-task-instructions]')
        .forEach(other => {
          const otherId = String(other.dataset.taskDetailsRow || other.dataset.taskInstructions || '');
          if (otherId && otherId !== id) forceDetailState(view, otherId, false);
        });
    }

    forceDetailState(view, id, open);

    // MutationObserver/ResizeObserver antigos podem reconciliar no frame seguinte.
    // Reafirmar somente o estado escolhido pelo clique elimina o abre-fecha sem criar polling.
    [0, 32, 120].forEach(delay => {
      window.setTimeout(() => {
        if (!button.isConnected || !row.isConnected) return;
        forceDetailState(view, id, open);
      }, delay);
    });
  }

  window.devpilotFocusExecution = requestFocus;

  document.addEventListener('click', event => {
    const trigger = event.target.closest?.(
      '[data-view="tasks"], [data-execution-link], a[href="#tasks"], a[href*="view=tasks"], a[href*="task_id="], a[href*="execution="]'
    );

    if (!trigger) return;

    requestFocus({
      taskId: taskIdFromTrigger(trigger),
      projectId: projectIdFromTrigger(trigger),
      source: 'click',
    });
  }, true);

  // Bubble phase: roda depois do onclick do renderer e materializa o estado final
  // com hidden + aria + data + display!important, removendo a corrida com V41.
  document.addEventListener('click', syncDetailsStateAfterClick, false);

  document.addEventListener('devpilot:view-changed', () => {
    if (pending) window.setTimeout(() => tryFocus(0), 25);
  });

  document.addEventListener('devpilot:tasks-rendered', () => {
    if (pending) window.setTimeout(() => tryFocus(0), 25);
  });

  injectStyles();
  document.documentElement.dataset.devpilotExecutionFocus = 'v20';
  console.info('[DevPilot] Execution Focus V20 ativo');
})();