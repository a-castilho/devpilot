(() => {
  'use strict';

  if (window.__devpilotTaskWorkflowObservabilityReady) return;
  window.__devpilotTaskWorkflowObservabilityReady = true;

  const taskTableBody = document.querySelector('#tasks-table');
  if (!taskTableBody || typeof api !== 'function') return;

  let runnerState = null;
  let runnerPromise = null;
  let latestRunsPromise = null;
  let scheduled = false;
  const latestRunsByTask = new Map();
  const runDetailCache = new Map();
  const workflowEvidenceCache = new Map();
  const workflowEvidencePromises = new Map();
  const deploymentEvidenceCache = new Map();
  const deploymentEvidencePromises = new Map();
  let liveTimer = null;

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
      .task-workflow-health strong{font-size:13px}.task-workflow-health small{opacity:.78;overflow-wrap:anywhere}
      .task-workflow-pill{display:inline-flex;align-items:center;gap:7px;padding:5px 9px;border:1px solid currentColor;border-radius:999px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.035em}
      .task-workflow-pill::before{content:'';width:7px;height:7px;border-radius:50%;background:currentColor;box-shadow:0 0 8px currentColor}
      .task-workflow-pill.ok{color:#63e6be}.task-workflow-pill.warn{color:#ffd43b}.task-workflow-pill.bad{color:#ff8787}.task-workflow-pill.unknown{color:#adb5bd}
      .task-flow-button{white-space:nowrap}.task-workflow-row>td{padding-top:0!important}
      .task-workflow-detail{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px 12px;margin:0 0 8px;border:1px solid var(--border,#2a3342);border-radius:10px;background:rgba(0,0,0,.12)}
      .task-workflow-stage{min-width:0;padding:8px;border-radius:8px;background:rgba(255,255,255,.025)}
      .task-workflow-stage b,.task-workflow-stage span{display:block}.task-workflow-stage span{margin-top:3px;font-size:11px;opacity:.75;overflow-wrap:anywhere}
       .task-workflow-stage a{display:inline-block;margin-top:4px;font-size:11px;overflow-wrap:anywhere}
      .task-workflow-timeline{display:flex;flex-wrap:wrap;gap:6px;margin-top:7px}.task-workflow-timeline span{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border-radius:999px;background:rgba(255,255,255,.04);font-size:10px;opacity:.55}.task-workflow-timeline span.done{opacity:1}.task-workflow-timeline i{width:6px;height:6px;border-radius:50%;background:currentColor}
      .task-workflow-jobs{margin:5px 0 0;padding-left:16px;font-size:11px;opacity:.82}
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
      host.innerHTML = '<strong>Esteira de execução</strong><small>Acompanhe o estado real de cada tarefa; nenhum estado é presumido. Informações de infraestrutura do runner ficam restritas ao Super Admin.</small>';
      return;
    }
    const tone = runnerTone(runnerState);
    const detail = runnerState?.detail || 'Consultando o serviço supervisionado do GitHub Actions Runner…';
    host.innerHTML = `<strong>Esteira de execução</strong><span class="task-workflow-pill ${tone}">Runner ${escapeHtml(runnerLabel(runnerState))}</span><small>${escapeHtml(detail)}</small>`;
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
      .finally(() => { runnerPromise = null; renderHealth(); scheduleEnhancement(); });
    return runnerPromise;
  }

  async function loadLatestRuns(force = false) {
    if (latestRunsByTask.size && !force) return latestRunsByTask;
    if (latestRunsPromise) return latestRunsPromise;
    latestRunsPromise = api('/task-runs/latest?limit=100')
      .then(items => {
        latestRunsByTask.clear();
        (Array.isArray(items) ? items : []).forEach(item => latestRunsByTask.set(String(item.task_id), item));
        return latestRunsByTask;
      })
      .finally(() => { latestRunsPromise = null; scheduleEnhancement(); });
    return latestRunsPromise;
  }

  async function loadRunDetail(runId) {
    if (!runId) return null;
    if (runDetailCache.has(String(runId))) return runDetailCache.get(String(runId));
    const detail = await api(`/task-runs/${encodeURIComponent(runId)}`);
    runDetailCache.set(String(runId), detail || null);
    return detail || null;
  }

  async function loadDeploymentEvidence(taskId, force = false) {
    const key = String(taskId);
    if (deploymentEvidenceCache.has(key) && !force) return deploymentEvidenceCache.get(key);
    if (deploymentEvidencePromises.has(key)) return deploymentEvidencePromises.get(key);
    const promise = api('/tasks/' + encodeURIComponent(taskId) + '/deployment-evidence')
      .then(value => { deploymentEvidenceCache.set(key, value || null); return value || null; })
      .catch(error => {
        const value = {correlated:false, reason:'query_failed', error:error?.message || 'Falha ao consultar deploy', deployment:null};
        deploymentEvidenceCache.set(key, value); return value;
      })
      .finally(() => deploymentEvidencePromises.delete(key));
    deploymentEvidencePromises.set(key, promise); return promise;
  }

  function workflowTimeline(task) {
    const latest = latestRunsByTask.get(String(task.id));
    const detail = latest?.run_id ? runDetailCache.get(String(latest.run_id)) : null;
    const evidence = workflowEvidenceCache.get(String(task.id));
    const deployment = deploymentEvidenceCache.get(String(task.id));
    const items = [['Tarefa criada',true],['Execução',Boolean(latest)],['Commit / PR',Boolean(detail?.commit_sha || detail?.pull_request_url)],['CI / Quality',Boolean(evidence?.correlated)],['Deploy',Boolean(deployment?.correlated || deployment?.deployment)],['Health Check',Boolean(deployment?.deployment?.health_verified || deployment?.deployment?.health_status)],['Concluído',String(task?.status || '').toLowerCase() === 'completed']];
    return '<div class="task-workflow-timeline">' + items.map(item => '<span class="' + (item[1] ? 'done' : '') + '"><i></i>' + escapeHtml(item[0]) + '</span>').join('') + '</div>';
  }

  function deploymentStage(task) {
    const evidence = deploymentEvidenceCache.get(String(task.id));
    if (!evidence) return '<span>Consultando deploy/health pelo commit persistido…</span>';
    if (!evidence.correlated) return '<span>Não correlacionado · ' + escapeHtml(evidence.error || evidence.reason || 'sem deploy para o commit') + '</span>';
    const d = evidence.deployment || {};
    const status = d.health_status || d.status || 'unknown';
    const url = d.url || d.environment_url || '';
    return '<span>' + escapeHtml(status) + '</span>' + (url ? '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">Abrir URL</a>' : '');
  }
  async function loadWorkflowEvidence(taskId, force = false) {
    const key = String(taskId);
    if (workflowEvidenceCache.has(key) && !force) return workflowEvidenceCache.get(key);
    if (workflowEvidencePromises.has(key)) return workflowEvidencePromises.get(key);
    const promise = api(`/tasks/${encodeURIComponent(taskId)}/workflow-evidence`)
      .then(value => {
        workflowEvidenceCache.set(key, value || null);
        return value || null;
      })
      .catch(error => {
        const value = {correlated: false, reason: 'query_failed', error: error?.message || 'Falha ao consultar GitHub Actions', workflow: null, jobs: []};
        workflowEvidenceCache.set(key, value);
        return value;
      })
      .finally(() => workflowEvidencePromises.delete(key));
    workflowEvidencePromises.set(key, promise);
    return promise;
  }

  function taskStatusText(task) {
    return String(task?.status || 'unknown').replaceAll('_', ' ') || 'unknown';
  }

  function executionStage(task) {
    const latest = latestRunsByTask.get(String(task.id));
    if (!latest) return '<span>Nenhuma execução persistida para esta tarefa.</span>';
    const runStatus = latest.run_status || 'sem status';
    return `<span>${escapeHtml(runStatus)}${latest.run_id ? ` · run ${escapeHtml(String(latest.run_id).slice(0, 8))}` : ''}</span>`;
  }

  function codeStage(task) {
    const latest = latestRunsByTask.get(String(task.id));
    if (!latest?.run_id) return '<span>Commit/PR ainda não registrados pela execução.</span>';
    const detail = runDetailCache.get(String(latest.run_id));
    if (!detail) return '<span>Carregando evidências de commit e PR…</span>';
    const parts = [];
    if (detail.commit_sha) parts.push(`<span>Commit ${escapeHtml(String(detail.commit_sha).slice(0, 12))}</span>`);
    if (detail.pull_request_url) parts.push(`<a href="${escapeHtml(detail.pull_request_url)}" target="_blank" rel="noopener noreferrer">Abrir Pull Request</a>`);
    return parts.join('') || '<span>Execução sem commit/PR registrado.</span>';
  }

  function ciStage(task) {
    const evidence = workflowEvidenceCache.get(String(task.id));
    if (!evidence) return '<span>Consultando GitHub Actions pelo commit persistido…</span>';
    if (!evidence.correlated) {
      const reason = evidence.error || evidence.reason || 'sem workflow para o commit';
      return `<span>Não correlacionado · ${escapeHtml(reason)}</span>`;
    }
    const workflow = evidence.workflow || {};
    const conclusion = workflow.conclusion || workflow.status || 'unknown';
    const parts = [`<span>${escapeHtml(workflow.name || 'Workflow')} #${escapeHtml(workflow.run_number || workflow.id || '')} · ${escapeHtml(conclusion)}</span>`];
    if (workflow.html_url) parts.push(`<a href="${escapeHtml(workflow.html_url)}" target="_blank" rel="noopener noreferrer">Abrir workflow</a>`);
    const jobs = Array.isArray(evidence.jobs) ? evidence.jobs : [];
    if (jobs.length) {
      parts.push(`<ul class="task-workflow-jobs">${jobs.map(job => `<li>${escapeHtml(job.name)} · ${escapeHtml(job.conclusion || job.status || 'unknown')}</li>`).join('')}</ul>`);
    }
    return parts.join('');
  }

  function detailMarkup(task) {
    const runnerVisible = canSeeRunner();
    const runnerValue = runnerVisible ? runnerLabel(runnerState) : 'restrito ao Super Admin';
    const runnerDetail = runnerVisible ? (runnerState?.detail || 'ainda não consultado') : 'infraestrutura protegida por RBAC';
    return `
      <div class="task-workflow-detail">
        <div class="task-workflow-stage"><b>Tarefa</b><span>${escapeHtml(taskStatusText(task))}</span></div>
        <div class="task-workflow-stage"><b>Execução</b>${executionStage(task)}</div>
        <div class="task-workflow-stage"><b>Commit / PR</b>${codeStage(task)}</div>
        <div class="task-workflow-stage"><b>Runner</b><span>${escapeHtml(runnerValue)} · ${escapeHtml(runnerDetail)}</span></div>
        <div class="task-workflow-stage"><b>CI</b>${ciStage(task)}</div>
        <div class="task-workflow-stage"><b>Deploy / Health</b>${deploymentStage(task)}</div><div class="task-workflow-stage" style="grid-column:1/-1"><b>Timeline ponta a ponta</b>${workflowTimeline(task)}</div>
      </div>`;
  }

  async function hydrateExpandedTask(task, row) {
    const latest = latestRunsByTask.get(String(task.id));
    if (latest?.run_id && !runDetailCache.has(String(latest.run_id))) {
      try { await loadRunDetail(latest.run_id); } catch (_) { /* mantém estado desconhecido */ }
    }
    if (latest?.run_id) await Promise.all([loadWorkflowEvidence(task.id, true), loadDeploymentEvidence(task.id, true)]);
    const detailRow = row.nextElementSibling;
    if (detailRow?.classList.contains('task-workflow-row')) {
      const cell = detailRow.querySelector('td');
      if (cell) cell.innerHTML = detailMarkup(task);
    }
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
    void hydrateExpandedTask(task, row);
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
      if (!task) return;
      row.dataset.taskId = task.id || '';
      if (!row.querySelector('.task-flow-cell')) {
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
      }
      if (row.nextElementSibling?.classList.contains('task-workflow-row')) void hydrateExpandedTask(task, row);
    });
    taskTableBody.querySelectorAll('tr.task-instructions-row > td').forEach(cell => { cell.colSpan = Math.max(Number(cell.colSpan || 5), 7); });
    const empty = taskTableBody.querySelector('td.empty');
    if (empty) empty.colSpan = Math.max(Number(empty.colSpan || 5), 7);
  }

  function scheduleEnhancement() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => { scheduled = false; enhanceRows(); });
  }

  if (typeof renderTasks === 'function' && !window.__devpilotTaskWorkflowRenderWrapped) {
    window.__devpilotTaskWorkflowRenderWrapped = true;
    const originalRenderTasks = renderTasks;
    renderTasks = function renderTasksWithWorkflowObservability(...args) {
      const result = originalRenderTasks.apply(this, args);
      document.dispatchEvent(new CustomEvent('devpilot:tasks-rendered'));
      return result;
    };
  }

  document.addEventListener('devpilot:feature-ready', event => {
    if (event.detail?.feature === 'tasks') {
      workflowEvidenceCache.clear();
      deploymentEvidenceCache.clear();
      void loadLatestRuns(true);
      scheduleEnhancement();
    }
  });
  document.addEventListener('devpilot:tasks-rendered', scheduleEnhancement);

  enhanceRows();
  void loadLatestRuns();
  void loadRunner();
  function startLiveMonitoring() {
    if (liveTimer) window.clearInterval(liveTimer);
    liveTimer = window.setInterval(async () => {
      try {
        await loadLatestRuns(true);
        for (const task of taskList().slice(0, 100)) {
          const latest = latestRunsByTask.get(String(task.id));
          if (latest?.run_id) { void loadWorkflowEvidence(task.id, true); void loadDeploymentEvidence(task.id, true); }
        }
        scheduleEnhancement();
      } catch (_) {}
    }, 5000);
  }
  startLiveMonitoring();
})();
