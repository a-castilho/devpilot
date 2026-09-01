(() => {
  'use strict';

  if (window.__devpilotTasksRecoveryLayoutV41) return;
  window.__devpilotTasksRecoveryLayoutV41 = true;

  const INTERNAL_SOURCES = new Set(['failure-recovery']);
  const STATUS_LABELS = Object.freeze({
    queued: 'Na fila',
    planning: 'Planejando',
    running: 'Executando',
    review: 'Em revisão',
    awaiting_approval: 'Aguardando aprovação',
    completed: 'Concluída',
    failed: 'Falhou',
    blocked: 'Bloqueada',
  });

  let observer = null;
  let reconcileFrame = 0;

  const tasks = () => (
    typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks : []
  );

  const isInternal = task => INTERNAL_SOURCES.has(String(task?.source || '').trim().toLowerCase());
  const normalizeStatus = value => String(value || '').split('.').pop().trim().toLowerCase().replaceAll(' ', '_');

  function injectStyle() {
    if (document.getElementById('tasks-recovery-layout-v41-style')) return;
    const style = document.createElement('style');
    style.id = 'tasks-recovery-layout-v41-style';
    style.textContent = `
      #tasks-view .tasks-v9-table-wrap{overflow:visible!important;min-width:0!important}
      #tasks-view .tasks-v9-table,#tasks-view .tasks-v9-table tbody{width:100%!important}

      /* Autoridade final: tarefas internas nunca voltam a aparecer mesmo se V40 aplicar display:grid depois. */
      #tasks-view #tasks-table > tr.tasks-render-stable-v40[data-devpilot-internal-task="1"],
      #tasks-view #tasks-table > tr.tasks-v9-row[data-devpilot-internal-task="1"],
      #tasks-view #tasks-table > tr.task-details-row[data-devpilot-internal-task="1"]{display:none!important}

      #tasks-view:not(.tasks-v41-compact) .tasks-v9-table,
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-table tbody{display:block!important}
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-table thead{display:none!important}
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-row{
        display:grid!important;
        grid-template-columns:minmax(260px,1fr) minmax(108px,142px) minmax(148px,max-content)!important;
        align-items:center!important;
        gap:12px 16px!important;
        width:100%!important;
        margin:0 0 10px!important;
        padding:15px 16px!important;
        box-sizing:border-box!important;
        border:1px solid rgba(55,215,255,.17)!important;
        border-radius:14px!important;
        background:linear-gradient(145deg,rgba(8,27,44,.97),rgba(6,18,31,.97))!important;
      }
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-row:has(.tasks-v9-status.failed),
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-row:has(.status.failed){border-color:rgba(255,101,120,.30)!important}
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-row:has(.tasks-v9-status.completed),
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-row:has(.status.completed){border-color:rgba(40,229,165,.24)!important}
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-row>td{
        display:block!important;width:auto!important;min-width:0!important;padding:0!important;
        border:0!important;background:transparent!important;box-shadow:none!important;border-radius:0!important;
      }
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-main{grid-column:1!important;min-width:0!important}
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-state{grid-column:2!important;min-width:0!important;white-space:nowrap!important}
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-actions{grid-column:3!important;min-width:0!important;justify-content:flex-end!important;flex-wrap:wrap!important}
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-title{
        display:-webkit-box!important;max-width:100%!important;overflow:hidden!important;
        -webkit-box-orient:vertical!important;-webkit-line-clamp:2!important;
        white-space:normal!important;word-break:normal!important;overflow-wrap:break-word!important;
        text-overflow:clip!important;line-height:1.28!important;
      }
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-meta{display:flex!important;gap:6px 12px!important;min-width:0!important;flex-wrap:wrap!important}
      #tasks-view:not(.tasks-v41-compact) .tasks-v9-meta>span{white-space:nowrap!important;word-break:normal!important;overflow-wrap:normal!important}
      #tasks-view:not(.tasks-v41-compact) .task-details-row:not([hidden]){display:block!important;width:100%!important;margin:-4px 0 10px!important}
      #tasks-view:not(.tasks-v41-compact) .task-details-row:not([hidden])>td{display:block!important;width:100%!important;padding:0 2px 10px!important}

      #tasks-view.tasks-v41-compact .tasks-v9-table,
      #tasks-view.tasks-v41-compact .tasks-v9-table tbody{display:block!important;width:100%!important}
      #tasks-view.tasks-v41-compact .tasks-v9-table thead{display:none!important}
      #tasks-view.tasks-v41-compact .tasks-v9-row{
        display:grid!important;grid-template-columns:minmax(0,1fr) auto!important;
        gap:10px 12px!important;width:100%!important;margin:0 0 10px!important;padding:14px!important;
        box-sizing:border-box!important;border:1px solid rgba(55,215,255,.18)!important;border-radius:14px!important;
        background:linear-gradient(145deg,rgba(8,27,44,.97),rgba(6,18,31,.97))!important;
      }
      #tasks-view.tasks-v41-compact .tasks-v9-row>td{
        display:block!important;width:auto!important;min-width:0!important;padding:0!important;
        border:0!important;background:transparent!important;box-shadow:none!important;border-radius:0!important;
      }
      #tasks-view.tasks-v41-compact .tasks-v9-main{grid-column:1/-1!important;min-width:0!important}
      #tasks-view.tasks-v41-compact .tasks-v9-state{grid-column:1!important;align-self:center!important;min-width:0!important}
      #tasks-view.tasks-v41-compact .tasks-v9-actions{grid-column:2!important;justify-content:flex-end!important;min-width:0!important}
      #tasks-view.tasks-v41-compact .tasks-v9-title{
        display:-webkit-box!important;-webkit-box-orient:vertical!important;-webkit-line-clamp:3!important;
        overflow:hidden!important;white-space:normal!important;word-break:normal!important;overflow-wrap:break-word!important;
        font-size:15px!important;line-height:1.3!important;
      }
      #tasks-view.tasks-v41-compact .tasks-v9-meta{display:flex!important;flex-wrap:wrap!important;gap:6px 9px!important;min-width:0!important}
      #tasks-view.tasks-v41-compact .tasks-v9-meta>span{max-width:100%!important;white-space:nowrap!important;word-break:normal!important;overflow-wrap:normal!important}
      #tasks-view.tasks-v41-compact .task-details-row:not([hidden]){display:block!important;width:100%!important;margin:-4px 0 10px!important}
      #tasks-view.tasks-v41-compact .task-details-row:not([hidden])>td{display:block!important;width:100%!important;padding:0 0 10px!important}

      #tasks-view.tasks-v41-compact .tasks-v9-source::before,
      #tasks-view.tasks-v41-compact .tasks-v9-priority::before{
        color:#607f98;font-size:8px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;
      }
      #tasks-view.tasks-v41-compact .tasks-v9-source::before{content:'Origem · '}
      #tasks-view.tasks-v41-compact .tasks-v9-priority::before{content:'Prioridade · '}

      @media(max-width:520px){
        #tasks-view.tasks-v41-compact .tasks-v9-row{grid-template-columns:minmax(0,1fr)!important;gap:8px!important;padding:12px!important}
        #tasks-view.tasks-v41-compact .tasks-v9-state,#tasks-view.tasks-v41-compact .tasks-v9-actions{grid-column:1!important}

        /* Renderer legado de 5 células: metadados ficam lado a lado e ações não viram botões gigantes. */
        #tasks-view.tasks-v41-compact #tasks-table > tr[data-tasks-v41-legacy="1"]{
          grid-template-columns:repeat(2,minmax(0,1fr))!important;
        }
        #tasks-view.tasks-v41-compact #tasks-table > tr[data-tasks-v41-legacy="1"] > td:nth-child(1){grid-column:1/-1!important}
        #tasks-view.tasks-v41-compact #tasks-table > tr[data-tasks-v41-legacy="1"] > td:nth-child(2){grid-column:1!important}
        #tasks-view.tasks-v41-compact #tasks-table > tr[data-tasks-v41-legacy="1"] > td:nth-child(4){grid-column:2!important}
        #tasks-view.tasks-v41-compact #tasks-table > tr[data-tasks-v41-legacy="1"] > td:nth-child(3),
        #tasks-view.tasks-v41-compact #tasks-table > tr[data-tasks-v41-legacy="1"] > td:nth-child(5){grid-column:1/-1!important}

        #tasks-view.tasks-v41-compact .tasks-v9-actions,
        #tasks-view.tasks-v41-compact .tasks-v9-actions .task-actions,
        #tasks-view.tasks-v41-compact .tasks-v9-actions .task-operational-actions{
          display:grid!important;
          grid-template-columns:repeat(auto-fit,minmax(118px,1fr))!important;
          gap:8px!important;
          width:100%!important;
          justify-content:stretch!important;
        }
        #tasks-view.tasks-v41-compact .tasks-v9-actions button,
        #tasks-view.tasks-v41-compact .tasks-v9-actions .delete-task{
          width:100%!important;max-width:none!important;min-height:42px!important;
          margin:0!important;padding:8px 10px!important;font-size:12px!important;line-height:1.2!important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function taskById(id) {
    return tasks().find(task => String(task?.id || '') === String(id || '')) || null;
  }

  function normalizeLegacyRow(row) {
    const cells = Array.from(row.children).filter(cell => cell instanceof HTMLTableCellElement);
    const legacy = cells.length >= 5;
    row.dataset.tasksV41Legacy = legacy ? '1' : '0';
    if (!legacy) return;

    cells[1].classList.add('tasks-v9-source');
    cells[2].classList.add('tasks-v9-state');
    cells[3].classList.add('tasks-v9-priority');
    cells[4].classList.add('tasks-v9-actions');

    const chip = cells[2].querySelector('.status, .tasks-v9-status');
    if (chip) {
      const normalized = normalizeStatus(chip.textContent || chip.className);
      if (STATUS_LABELS[normalized]) chip.textContent = STATUS_LABELS[normalized];
    }
  }

  function hideInternalRows() {
    const allTasks = tasks();
    const operational = allTasks.filter(task => !isInternal(task));
    const rows = Array.from(document.querySelectorAll('#tasks-table > tr[data-task-id]'));
    let visible = 0;

    rows.forEach(row => {
      normalizeLegacyRow(row);
      const task = taskById(row.dataset.taskId);
      const internal = Boolean(task && isInternal(task));
      row.dataset.devpilotInternalTask = internal ? '1' : '0';

      const taskId = String(row.dataset.taskId || '');
      const details = document.querySelector(`#tasks-table [data-task-details-row="${CSS.escape(taskId)}"]`);
      if (details) details.dataset.devpilotInternalTask = internal ? '1' : '0';

      if (!internal) visible += 1;
    });

    const count = document.querySelector('#tasks-v9-count');
    if (count && (rows.length || allTasks.length)) {
      count.textContent = `${visible} de ${operational.length} execução(ões) exibida(s)`;
    }
  }

  function updateContainerMode() {
    const view = document.querySelector('#tasks-view');
    if (!view) return;
    const width = Math.round(view.getBoundingClientRect().width || view.clientWidth || 0);
    view.classList.toggle('tasks-v41-compact', width > 0 && width < 760);
    view.dataset.tasksAvailableWidth = String(width);
  }

  function observeView() {
    const view = document.querySelector('#tasks-view');
    if (!view || observer) return;
    if ('ResizeObserver' in window) {
      observer = new ResizeObserver(() => updateContainerMode());
      observer.observe(view);
    } else {
      window.addEventListener('resize', updateContainerMode, {passive:true});
    }
    updateContainerMode();
  }

  function scheduleReconcile() {
    if (reconcileFrame) return;
    reconcileFrame = window.requestAnimationFrame(() => {
      reconcileFrame = 0;
      reconcile();
    });
  }

  function installRendererHook() {
    let upstream = null;
    try { upstream = typeof renderTasks === 'function' ? renderTasks : null; } catch (_) {}
    if (!upstream && typeof window.renderTasks === 'function') upstream = window.renderTasks;
    if (!upstream || upstream.__devpilotV41ReconcileHook) return;

    const wrapped = function renderTasksWithV41Reconcile(...args) {
      const result = upstream.apply(this, args);
      scheduleReconcile();
      return result;
    };
    wrapped.__devpilotV41ReconcileHook = true;
    wrapped.__devpilotV41Upstream = upstream;

    window.renderTasks = wrapped;
    try { renderTasks = wrapped; } catch (_) {}
  }

  function settleReconcile() {
    scheduleReconcile();
    window.setTimeout(scheduleReconcile, 60);
    window.setTimeout(scheduleReconcile, 240);
  }

  function reconcile() {
    observeView();
    updateContainerMode();
    hideInternalRows();
    installRendererHook();
  }

  injectStyle();
  installRendererHook();
  document.addEventListener('devpilot:tasks-rendered', settleReconcile);
  document.addEventListener('devpilot:view-changed', event => {
    if (event.detail?.view === 'tasks') settleReconcile();
  });
  document.addEventListener('devpilot:feature-ready', event => {
    if (['tasks', 'tasksDetails'].includes(event.detail?.feature)) settleReconcile();
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', settleReconcile, {once:true});
  else settleReconcile();
})();
