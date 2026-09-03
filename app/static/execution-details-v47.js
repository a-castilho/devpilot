(() => {
  'use strict';

  if (window.__devpilotExecutionDetailsV47) return;
  window.__devpilotExecutionDetailsV47 = true;

  const failureCache = new Map();
  const taskCache = new Map();
  const runCache = new Map();
  let latestPromise = null;

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));

  const token = () => String(localStorage.getItem('devpilot-token') || '');

  async function getJson(path) {
    const response = await fetch(`/api${path}`, {
      headers: {Authorization: `Bearer ${token()}`},
      cache: 'no-store',
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = typeof data?.detail === 'string' ? data.detail : 'Não foi possível carregar os dados da execução.';
      throw new Error(message);
    }
    return data;
  }

  function normalizeStatus(value) {
    return String(value || '').split('.').pop().trim().toLowerCase().replaceAll(' ', '_');
  }

  function injectStyle() {
    if (document.getElementById('execution-details-v47-style')) return;
    const style = document.createElement('style');
    style.id = 'execution-details-v47-style';
    style.textContent = `
      #tasks-view .dp-v47-error-summary{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px;align-items:start;margin-top:12px;padding:12px 13px;border:1px solid rgba(255,103,125,.26);border-radius:13px;background:linear-gradient(145deg,rgba(55,18,31,.72),rgba(22,15,28,.74));box-sizing:border-box}
      #tasks-view .dp-v47-error-icon{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:rgba(255,103,125,.13);color:#ff8297;font-weight:950}
      #tasks-view .dp-v47-error-copy{min-width:0}.dp-v47-error-copy small{display:block;color:#c88e9a;font-size:9px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.dp-v47-error-copy strong{display:block;margin-top:4px;color:#ffd8df;font-size:13px;line-height:1.35}.dp-v47-error-copy p{margin:5px 0 0;color:#bdaeb4;font-size:12px;line-height:1.45;overflow-wrap:anywhere}
      #tasks-view .dp-v47-details{display:grid;gap:12px;width:100%;padding:14px;border:1px solid rgba(75,220,235,.20);border-radius:14px;background:linear-gradient(145deg,rgba(6,24,37,.96),rgba(5,15,26,.98));box-sizing:border-box}
      #tasks-view .dp-v47-details-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.dp-v47-details-head small{display:block;color:#5ddbd0;font-size:9px;font-weight:900;letter-spacing:.08em}.dp-v47-details-head strong{display:block;margin-top:4px;color:#f0f8fb;font-size:17px;line-height:1.25}.dp-v47-details-head span{color:#7f9aab;font-size:10px;white-space:nowrap}
      #tasks-view .dp-v47-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.dp-v47-fact{min-width:0;padding:9px;border-radius:10px;background:rgba(255,255,255,.035)}.dp-v47-fact small{display:block;color:#708797;font-size:8px;font-weight:850;text-transform:uppercase}.dp-v47-fact strong{display:block;margin-top:3px;color:#d7e5eb;font-size:11px;overflow-wrap:anywhere}
      #tasks-view .dp-v47-context{padding:10px;border-radius:10px;background:rgba(255,255,255,.025)}.dp-v47-context small{display:block;color:#718b9b;font-size:8px;font-weight:900;text-transform:uppercase}.dp-v47-context p{margin:5px 0 0;color:#b8c7cf;font-size:12px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}
      #tasks-view .dp-v47-error-detail{padding:12px;border:1px solid rgba(255,103,125,.25);border-radius:11px;background:rgba(78,17,33,.35)}.dp-v47-error-detail small{display:block;color:#ff91a4;font-size:9px;font-weight:900;text-transform:uppercase}.dp-v47-error-detail strong{display:block;margin-top:5px;color:#ffe2e7;font-size:14px;line-height:1.35}.dp-v47-error-detail p{margin:6px 0 0;color:#d0b9c0;font-size:12px;line-height:1.5;overflow-wrap:anywhere}.dp-v47-error-detail code{display:inline-block;margin-top:8px;padding:4px 7px;border-radius:7px;background:rgba(0,0,0,.24);color:#d8a6b0;font-size:10px;overflow-wrap:anywhere}
      #tasks-view [data-task-details-row][data-dp-v47-open="1"]{display:block!important;visibility:visible!important;width:100%!important;min-width:0!important;height:auto!important;max-height:none!important;margin:-4px 0 10px!important;padding:0!important;overflow:visible!important}
      #tasks-view [data-task-details-row][data-dp-v47-open="1"]>td{display:block!important;width:100%!important;min-width:0!important;height:auto!important;padding:0 0 10px!important;overflow:visible!important}
      #tasks-view .tasks-v9-details.dp-v47-open{border-color:rgba(67,219,236,.52)!important;background:rgba(67,219,236,.08)!important;color:#8cf1ec!important}
      @media(max-width:520px){#tasks-view .dp-v47-facts{grid-template-columns:1fr}.dp-v47-details{padding:12px}.dp-v47-details-head{display:grid}.dp-v47-details-head span{white-space:normal}}
    `;
    document.head.appendChild(style);
  }

  function userContext(prompt) {
    let text = String(prompt || '').trim();
    const marker = 'Contexto do usuário:';
    if (text.includes(marker)) text = text.split(marker).slice(1).join(marker);
    text = text.replace(/\[DEVPILOT_MODE=[^\]]+\]/gi, '').trim();
    return text.length > 1600 ? `${text.slice(0, 1600).trim()}…` : (text || 'Nenhum contexto adicional registrado.');
  }

  function formatDate(value) {
    if (!value) return '—';
    try { return new Date(value).toLocaleString('pt-BR', {dateStyle:'short', timeStyle:'short'}); }
    catch (_) { return String(value); }
  }

  function friendlyFailure(item) {
    const message = String(item?.failure_reason || item?.failure?.message || '').trim();
    const code = String(item?.failure_code || item?.failure?.code || '').trim();
    const category = String(item?.failure_category || item?.failure?.category || '').trim();
    const requiresAuthorization = Boolean(item?.requires_authorization || item?.failure?.requires_authorization);
    return {
      message: message || 'A execução terminou com falha, mas não registrou uma mensagem específica.',
      code: code || 'EXECUTION_FAILED',
      category,
      requiresAuthorization,
    };
  }

  async function latestFailures() {
    if (latestPromise) return latestPromise;
    latestPromise = getJson('/task-runs/latest?limit=500')
      .then(items => {
        (Array.isArray(items) ? items : []).forEach(item => {
          failureCache.set(String(item.task_id || ''), item);
        });
        return items;
      })
      .finally(() => { latestPromise = null; });
    return latestPromise;
  }

  async function detailForTask(taskId) {
    if (taskCache.has(taskId)) return taskCache.get(taskId);
    const task = await getJson(`/ui/tasks/${encodeURIComponent(taskId)}`);
    taskCache.set(taskId, task);
    return task;
  }

  async function failureForTask(taskId) {
    if (!failureCache.has(taskId)) await latestFailures();
    const summary = failureCache.get(taskId) || null;
    if (!summary?.run_id) return summary;
    const runId = String(summary.run_id);
    if (!runCache.has(runId)) {
      try { runCache.set(runId, await getJson(`/task-runs/${encodeURIComponent(runId)}`)); }
      catch (_) { return summary; }
    }
    const run = runCache.get(runId);
    return {...summary, failure: run?.failure || null};
  }

  function taskById(id) {
    const items = typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks : [];
    return items.find(item => String(item?.id || '') === String(id || '')) || null;
  }

  function projectName(task) {
    if (task?.project_name) return String(task.project_name);
    const projects = typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : [];
    return String(projects.find(item => String(item.id) === String(task?.project_id))?.name || 'Projeto não identificado');
  }

  function closeRows(exceptId = '') {
    document.querySelectorAll('#tasks-view [data-task-details-row]').forEach(row => {
      const id = String(row.dataset.taskDetailsRow || '');
      if (id === exceptId) return;
      row.hidden = true;
      row.dataset.dpV47Open = '0';
      row.dataset.dpDetailsActive = '0';
      row.dataset.dpV13Open = '0';
      row.style.setProperty('display', 'none', 'important');
      const button = document.querySelector(`#tasks-view .tasks-v9-details[data-id="${CSS.escape(id)}"]`);
      if (button) {
        button.classList.remove('dp-v47-open');
        button.textContent = 'Detalhes';
        button.setAttribute('aria-expanded', 'false');
      }
    });
  }

  async function openDetails(button) {
    const id = String(button.dataset.id || '');
    if (!id) return;
    const row = document.querySelector(`#tasks-view [data-task-details-row="${CSS.escape(id)}"]`);
    const panel = document.querySelector(`#tasks-view [data-task-details="${CSS.escape(id)}"]`);
    if (!row || !panel) return;

    const isOpen = row.dataset.dpV47Open === '1' && !row.hidden;
    if (isOpen) {
      closeRows('');
      return;
    }

    closeRows(id);
    row.hidden = false;
    row.dataset.dpV47Open = '1';
    row.dataset.dpDetailsActive = '1';
    row.dataset.dpV13Open = '1';
    row.removeAttribute('aria-hidden');
    row.style.setProperty('display', 'block', 'important');
    button.classList.add('dp-v47-open');
    button.textContent = 'Ocultar';
    button.setAttribute('aria-expanded', 'true');
    panel.innerHTML = '<span class="tasks-v9-detail-loading">Carregando detalhes…</span>';
    panel.setAttribute('aria-busy', 'true');

    try {
      const task = await detailForTask(id);
      const status = normalizeStatus(task?.status);
      const failure = ['failed', 'blocked'].includes(status) ? friendlyFailure(await failureForTask(id)) : null;
      panel.innerHTML = `
        <section class="dp-v47-details">
          <header class="dp-v47-details-head">
            <div><small>DETALHES DA EXECUÇÃO</small><strong>${esc(task?.title || 'Execução')}</strong></div>
            <span>${esc(formatDate(task?.updated_at || task?.created_at))}</span>
          </header>
          ${failure ? `<div class="dp-v47-error-detail" role="alert"><small>ERRO REAL</small><strong>${esc(failure.message)}</strong><p>${failure.requiresAuthorization ? 'Esta falha exige autorização ou ajuste de acesso antes de tentar novamente.' : 'O DevPilot registrou esta causa na última tentativa.'}</p><code>${esc(failure.code)}</code></div>` : ''}
          <div class="dp-v47-facts">
            <div class="dp-v47-fact"><small>Projeto</small><strong>${esc(projectName(task))}</strong></div>
            <div class="dp-v47-fact"><small>Origem</small><strong>${esc(task?.source || 'DevPilot')}</strong></div>
            <div class="dp-v47-fact"><small>Estado</small><strong>${esc(status || '—')}</strong></div>
            <div class="dp-v47-fact"><small>Prioridade</small><strong>${esc(task?.priority ?? '—')}</strong></div>
          </div>
          <div class="dp-v47-context"><small>Contexto</small><p>${esc(userContext(task?.prompt))}</p></div>
        </section>`;
    } catch (error) {
      panel.innerHTML = `<div class="tasks-v9-detail-error" role="alert">${esc(error?.message || 'Não foi possível carregar os detalhes da execução.')}</div>`;
    } finally {
      panel.removeAttribute('aria-busy');
    }
  }

  async function decorateFailures() {
    const failedRows = [...document.querySelectorAll('#tasks-view .tasks-v9-row[data-task-id]')]
      .filter(row => {
        const id = String(row.dataset.taskId || '');
        const task = taskById(id);
        return ['failed', 'blocked'].includes(normalizeStatus(task?.status));
      });
    if (!failedRows.length) return;

    try { await latestFailures(); } catch (_) { return; }

    failedRows.forEach(row => {
      const id = String(row.dataset.taskId || '');
      if (!id || row.querySelector('.dp-v47-error-summary')) return;
      const summary = failureCache.get(id);
      if (!summary) return;
      const failure = friendlyFailure(summary);
      const main = row.querySelector('.tasks-v9-main') || row.firstElementChild;
      if (!main) return;
      const box = document.createElement('div');
      box.className = 'dp-v47-error-summary';
      box.innerHTML = `<span class="dp-v47-error-icon">!</span><div class="dp-v47-error-copy"><small>Motivo da falha</small><strong>${esc(failure.message)}</strong><p>${failure.requiresAuthorization ? 'Precisa de autorização ou ajuste de acesso.' : `Código: ${esc(failure.code)}`}</p></div>`;
      main.appendChild(box);
    });
  }

  function bindCapture() {
    if (document.documentElement.dataset.dpV47DetailsCapture === '1') return;
    document.documentElement.dataset.dpV47DetailsCapture = '1';
    document.addEventListener('click', event => {
      const button = event.target.closest?.('#tasks-view .tasks-v9-details');
      if (!button) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      void openDetails(button);
    }, true);
  }

  function refresh() {
    injectStyle();
    bindCapture();
    window.requestAnimationFrame(() => void decorateFailures());
  }

  document.addEventListener('devpilot:tasks-rendered', refresh);
  document.addEventListener('devpilot:view-changed', event => {
    if (event.detail?.view === 'tasks') refresh();
  });
  document.addEventListener('devpilot:feature-ready', event => {
    if (event.detail?.feature === 'tasks') refresh();
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', refresh, {once:true});
  else refresh();

  console.info('[DevPilot] Execution details V47 · clique único + erro real sanitizado');
})();
