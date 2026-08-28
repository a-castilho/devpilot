(() => {
  'use strict';

  if (window.__devpilotTaskWorkflowObservabilityReady) return;
  window.__devpilotTaskWorkflowObservabilityReady = true;

  const taskTableBody = document.querySelector('#tasks-table');
  if (!taskTableBody || typeof api !== 'function') return;

  let runnerState = null;
  let runnerPromise = null;
  let scheduled = false;

  const escapeHtml = value => typeof esc === 'function'
    ? esc(value)
    : String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[char]));

  function taskList() {
    return typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks : [];
  }

  function canSeeRunner() {
    return typeof isSuperAdmin === 'function' && isSuperAdmin();
  }

  function runnerTone(runner) {
    if (!runner) return 'unknown';
    if (runner.status === 'online' && runner.service_enabled) return 'ok';
    if (runner.status === 'online') return 'warn';
    if (runner.status === 'offline') return 'bad';
    return 'unknown';
  }

  function runnerLabel(runner) {
    if (!runner) return 'não consultado';
    if (runner.status === 'online' && runner.service_enabled) return 'online · auto-restart';
    if (runner.status === 'online') return 'online · sem auto-restart';
    if (runner.status === 'offline') return 'offline';
    return 'estado desconhecido';
  }

  function ensureStyles() {
    if (document.querySelector('#devpilot-task-workflow-observability-style')) return;
    const style = document.createElement('style');
    style.id = 'devpilot-task-workflow-observability-style';
    style.textContent = `
      .task-workflow-health{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin:0 0 14px;padding:12px 14px;border:1px solid var(--border,#2a3342);border-radius:12px;background:rgba(255,255,255,.025)}
      .task-workflow-health strong{font-size:13px}
      .task-workflow-health small{opacity:.78;overflow-wrap:anywhere}
      .task-workflow-pill{display:inline-flex;align-items:center;gap:7px;padding:5px 9px;border:1px solid currentColor;border-radius:999px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.035em}
      .task-workflow-pill::before{content:'';width:7px;height:7px;border-radius:50%;background:currentColor;box-shadow:0 0 8px currentColor}
      .task-workflow-pill.ok{color:#63e6be}.task-workflow-pill.warn{color:#ffd43b}.task-workflow-pill.bad{color:#ff8787}.task-workflow-pill.unknown{color:#adb5bd}
      .task-flow-button{white-space:nowrap}
      .task-workflow-row>td{padding-top:0!important}
      .task-workflow-detail{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px 12px;margin:0 0 8px;border:1px solid var(--border,#2a3342);border-radius:10px;background:rgba(0,0,0,.12)}
      .task-workflow-stage{min-width:0;padding:8px;border-radius:8px;background:rgba(255,255,255,.025)}
      .task-workflow-stage b,.task-workflow-stage span{display:block}.task-workflow-stage span{margin-top:3px;font-size:11px;opacity:.75;overflow-wrap:anywhere}
      @media(max-width:700px){.task-workflow-detail{grid-template-columns:1fr}.task-workflow-health{align-items:flex-start;flex-direction:column}}
    `;
    document.head.appendChild(style);
  }

  function ensureHeader() {
    const table = taskTableBody.closest('table');
    const headerRow = table?.querySelector('thead tr');
    if (!headerRow || headerRow.querySelector('[data-task-flow-header]')) return;
    const header = document.createElement('th');
    header.dataset.taskFlowHeader = 'true';
    header.textContent = 'Fluxo';
    headerRow.appendChild(header);
  }

  function healthHost() {
    const table = taskTableBody.closest('table');
    if (!table) return null;
    let host = table.parentElement?.querySelector(':scope > [data-task-workflow-health]');
    if (host) return host;
    host = document.createElement('div');
    host.dataset.taskWorkflowHealth = 'true';
    host.className = 'task-workflow-health';
    table.insertAdjacentElement('beforebegin', host);
    return host;
  }

  function renderHealth() {
    const host = healthHost();
    if (!host) return;
    if (!canSeeRunner()) {
      host.innerHTML = '<strong>Esteira de execução</strong><small>Acompanhe o estado real de cada tarefa. Informações de infraestrutura do runner ficam restritas ao Super Admin.</small>';
      return;
    }
    const tone = runnerTone(runnerState);
    const detail = runnerState?.detail || 'Consultando o serviço supervisionado do GitHub Actions Runner…';
    host.innerHTML = `
      <strong>Esteira de execução</strong>
      <span class="task-workflow-pill ${tone}">Runner ${escapeHtml(runnerLabel(runnerState))}</span>
      <small>${escapeHtml(detail)}</small>
    `;
  }

  async function loadRunner(force = false) {
    if (!canSeeRunner()) return null;
    if (runnerState && !force) return runnerState;
    if (runnerPromise) return runnerPromise;
    runnerPromise = api('/voice/runner-status')
      .then(value => { runnerState = value || null; return runnerState; })
      .catch(error => {
        runnerState = {status: 'unknown', online: false, service_enabled: false, detail: error?.message || 'Falha ao consultar runner'};
        return runnerState;
      })
      .finally(() => { runnerPromise = null; renderHealth(); enhanceRows(); });
    return runnerPromise;
  }

  function taskStatusText(task) {
    const value = String(task?.status || 'unknown').replaceAll('_', ' ');
    return value || 'unknown';
  }

  function detailMarkup(task) {
    const runnerVisible = canSeeRunner();
    const runnerValue = runnerVisible ? runnerLabel(runnerState) : 'restrito ao Super Admin';
    const runnerDetail = runnerVisible ? (runnerState?.detail || 'ainda não consultado') : 'infraestrutura protegida por RBAC';
    return `
      <div class="task-workflow-detail">
        <div class="task-workflow-stage"><b>Tarefa</b><span>${escapeHtml(taskStatusText(task))}</span></div>
        <div class="task-workflow-stage"><b>Runner</b><span>${escapeHtml(runnerValue)} · ${escapeHtml(runnerDetail)}</span></div>
        <div class="task-workflow-stage"><b>CI / PR</b><span>Correlação por execução será adicionada na próxima fatia; nenhum estado é presumido.</span></div>
        <div class="task-workflow-stage"><b>Deploy / Health</b><span>Exibido somente quando houver evidência correlacionada; nenhum sucesso é inferido pela UI.</span></div>
      </div>
    `;
  }

  function toggleDetails(task, row, button) {
    const existing = row.nextElementSibling;
    if (existing?.classList.contains('task-workflow-row')) {
      existing.remove();
      button.textContent = 'Acompanhar';
      button.setAttribute('aria-expanded', 'false');
      return;
    }
    const detailRow = document.createElement('tr');
    detailRow.className = 'task-workflow-row';
    const cell = document.createElement('td');
    cell.colSpan = row.children.length;
    cell.innerHTML = detailMarkup(task);
    detailRow.appendChild(cell);
    row.insertAdjacentElement('afterend', detailRow);
    button.textContent = 'Recolher';
    button.setAttribute('aria-expanded', 'true');
  }

  function enhanceRows() {
    ensureStyles();
    ensureHeader();
    renderHealth();

    const tasks = taskList();
    const rows = [...taskTableBody.querySelectorAll('tr.task-main-row')];
    rows.forEach((row, index) => {
      const taskId = row.dataset.taskId || tasks[index]?.id;
      const task = tasks.find(item => String(item.id) === String(taskId)) || tasks[index];
      if (!task || row.querySelector('.task-flow-cell')) return;
      row.dataset.taskId = task.id || '';
      const cell = document.createElement('td');
      cell.className = 'task-flow-cell';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'link task-flow-button';
      button.textContent = 'Acompanhar';
      button.setAttribute('aria-expanded', 'false');
      button.addEventListener('click', () => toggleDetails(task, row, button));
      cell.appendChild(button);
      row.appendChild(cell);
    });

    taskTableBody.querySelectorAll('tr.task-instructions-row > td').forEach(cell => {
      cell.colSpan = Math.max(Number(cell.colSpan || 5), 7);
    });
    const empty = taskTableBody.querySelector('td.empty');
    if (empty) empty.colSpan = Math.max(Number(empty.colSpan || 5), 7);
  }

  function scheduleEnhancement() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      enhanceRows();
    });
  }

  new MutationObserver(scheduleEnhancement).observe(taskTableBody, {childList: true, subtree: false});
  document.addEventListener('devpilot:feature-ready', event => {
    if (event.detail?.feature === 'tasks') scheduleEnhancement();
  });

  enhanceRows();
  void loadRunner();
})();
