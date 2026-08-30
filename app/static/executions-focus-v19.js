(() => {
  'use strict';

  if (window.__devpilotExecutionsFocusV19) return;
  window.__devpilotExecutionsFocusV19 = true;

  let pending = null;
  let focusTimer = 0;
  let removeTimer = 0;

  const qs = (selector, root = document) => root.querySelector(selector);

  function escapeSelector(value) {
    if (window.CSS?.escape) return window.CSS.escape(String(value));
    return String(value).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
  }

  function injectStyles() {
    if (qs('#devpilot-executions-focus-v19-style')) return;

    const style = document.createElement('style');
    style.id = 'devpilot-executions-focus-v19-style';
    style.textContent = `
      #tasks-view .dp-execution-focus-v19 {
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

      #tasks-view .dp-execution-focus-v19::after {
        content: '';
        pointer-events: none;
        position: absolute;
        inset: -1px;
        border-radius: inherit;
        box-shadow: inset 0 0 24px rgba(71, 226, 208, .055);
        opacity: 1;
      }

      #tasks-view .dp-execution-focus-v19-pulse {
        animation: dpExecutionFocusV19 1.45s ease-out 1;
      }

      @keyframes dpExecutionFocusV19 {
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
        #tasks-view .dp-execution-focus-v19,
        #tasks-view .dp-execution-focus-v19-pulse {
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
    document.querySelectorAll('.dp-execution-focus-v19').forEach(element => {
      element.classList.remove(
        'dp-execution-focus-v19',
        'dp-execution-focus-v19-pulse'
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
        'dp-execution-focus-v19',
        'dp-execution-focus-v19-pulse'
      );

      removeTimer = window.setTimeout(() => {
        target.classList.remove(
          'dp-execution-focus-v19',
          'dp-execution-focus-v19-pulse'
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
      if (attempt < 30) {
        focusTimer = window.setTimeout(() => tryFocus(attempt + 1), 80);
      }
      return;
    }

    const target = targetFor(pending);

    if (!target && attempt < 30) {
      focusTimer = window.setTimeout(() => tryFocus(attempt + 1), 80);
      return;
    }

    const request = pending;
    pending = null;

    if (!focusTarget(target)) {
      pending = request;
    }
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

  document.addEventListener('devpilot:view-changed', () => {
    if (pending) window.setTimeout(() => tryFocus(0), 25);
  });

  document.addEventListener('devpilot:tasks-rendered', () => {
    if (pending) window.setTimeout(() => tryFocus(0), 25);
  });

  injectStyles();
  document.documentElement.dataset.devpilotExecutionFocus = 'v19';
  console.info('[DevPilot] Execution Focus V19 ativo');
})();