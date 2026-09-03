(() => {
  'use strict';

  if (window.__devpilotTasksOperationalV9) {
    window.renderTasks?.();
    return;
  }

  window.__devpilotTasksOperationalV9 = true;
  window.__devpilotTasksLiveSyncV81 = true;

  const LIVE_POLL_MS = 3000;
  const ui = {
    limit: 12,
    detailCache: new Map(),
    loading: false,
    liveBusy: false,
    liveTimer: 0,
    liveSignature: '',
  };

  const TERMINAL = new Set(['awaiting_approval', 'completed', 'failed', 'blocked']);
  const ACTIVE = new Set(['queued', 'planning', 'running', 'review']);
  const ATTENTION = new Set(['awaiting_approval', 'failed', 'blocked']);

  function html(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function notify(message) {
    if (typeof toast === 'function') return toast(message);
    console.info('[DevPilot]', message);
  }

  function normalizeStatus(value) {
    return String(value || '').split('.').pop().toLowerCase().replaceAll(' ', '_');
  }

  function statusLabel(value) {
    const status = normalizeStatus(value);
    return ({
      queued:'Na fila', planning:'Planejando', running:'Executando', review:'Em revisão',
      awaiting_approval:'Aguardando aprovação', completed:'Concluída', failed:'Falhou', blocked:'Bloqueada',
    })[status] || status || '—';
  }

  function taskType(task) {
    const source = String(task?.source || '').toLowerCase();
    const title = String(task?.title || '').toLowerCase();
    if (
      source.includes('analysis') || source.includes('verification') ||
      title.startsWith('análise') || title.startsWith('analise') ||
      title.includes('auditoria') || title.includes('revisão')
    ) return 'analysis';
    return 'execution';
  }

  const taskTypeLabel = task => taskType(task) === 'analysis' ? 'Análise' : 'Execução';

  function projectName(task) {
    if (task?.project_name) return String(task.project_name);
    const projects = typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : [];
    return String(
      projects.find(project => String(project.id) === String(task?.project_id))?.name ||
      'Projeto não identificado'
    );
  }

  function formatDate(value) {
    if (!value) return '';
    try {
      return new Date(value).toLocaleString('pt-BR', {dateStyle:'short', timeStyle:'short'});
    } catch (_) {
      return String(value);
    }
  }

  function userContext(prompt) {
    let text = String(prompt || '').trim();
    const marker = 'Contexto do usuário:';
    if (text.includes(marker)) text = text.split(marker).slice(1).join(marker);
    text = text.replace(/\[DEVPILOT_MODE=[^\]]+\]/gi, '').trim();
    if (text.length > 1400) text = `${text.slice(0, 1400).trim()}…`;
    return text || 'Nenhum contexto adicional registrado.';
  }

  function canDelete(task) {
    const superAdmin = typeof isSuperAdmin === 'function' ? isSuperAdmin() : false;
    return superAdmin && TERMINAL.has(normalizeStatus(task.status));
  }

  function taskMatches(task) {
    const search = String(document.querySelector('#tasks-v9-search')?.value || '').trim().toLowerCase();
    const project = String(document.querySelector('#tasks-v9-project')?.value || '');
    const statusFilter = String(document.querySelector('#tasks-v9-status')?.value || '');
    const typeFilter = String(document.querySelector('#tasks-v9-type')?.value || '');
    const status = normalizeStatus(task.status);
    const type = taskType(task);
    const projectId = String(task.project_id || '');

    if (project && projectId !== project) return false;
    if (typeFilter && type !== typeFilter) return false;
    if (statusFilter === 'active' && !ACTIVE.has(status)) return false;
    if (statusFilter === 'attention' && !ATTENTION.has(status)) return false;
    if (statusFilter === 'completed' && status !== 'completed') return false;

    if (search) {
      const haystack = [task.title, projectName(task), task.source, statusLabel(task.status)]
        .join(' ').toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  }

  function updateProjectFilter(tasks) {
    const select = document.querySelector('#tasks-v9-project');
    if (!select) return;
    const current = select.value;
    const projects = new Map();
    tasks.forEach(task => {
      if (task.project_id) projects.set(String(task.project_id), projectName(task));
    });
    select.innerHTML = [
      '<option value="">Todos</option>',
      ...[...projects.entries()]
        .sort((a, b) => a[1].localeCompare(b[1], 'pt-BR'))
        .map(([id, name]) => `<option value="${html(id)}">${html(name)}</option>`),
    ].join('');
    if (projects.has(current)) select.value = current;
  }

  function statusChip(task) {
    const status = normalizeStatus(task.status);
    return `<span class="tasks-v9-status ${html(status)}">${html(statusLabel(status))}</span>`;
  }

  function renderOperationalTasks() {
    const target = document.querySelector('#tasks-table');
    if (!target) return;

    const tasks = typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks : [];
    updateProjectFilter(tasks);
    const filtered = tasks.filter(taskMatches);
    const count = document.querySelector('#tasks-v9-count');
    if (count) count.textContent = `${filtered.length} de ${tasks.length} execução(ões) exibida(s)`;

    if (!filtered.length) {
      target.innerHTML = `
        <tr><td colspan="3" class="tasks-v9-empty">
          <strong>Nenhuma execução encontrada.</strong>
          <span>Ajuste os filtros ou registre uma nova execução.</span>
        </td></tr>`;
      document.dispatchEvent(new CustomEvent('devpilot:tasks-rendered', {detail:{count:0}}));
      return;
    }

    target.innerHTML = filtered.map(task => {
      const id = String(task.id || '');
      const type = taskType(task);
      const status = normalizeStatus(task.status);
      const approval = status === 'awaiting_approval'
        ? `<button class="primary tasks-v9-approve" type="button" data-id="${html(id)}">Aprovar</button>`
        : '';
      const remove = canDelete(task)
        ? `<button class="danger tasks-v9-delete delete-task" type="button" data-id="${html(id)}">Excluir</button>`
        : '';

      return `
        <tr class="task-main-row tasks-v9-row" data-task-id="${html(id)}">
          <td class="tasks-v9-main">
            <strong class="tasks-v9-title" title="${html(task.title)}">${html(task.title || 'Execução sem título')}</strong>
            <div class="tasks-v9-meta">
              <span class="tasks-v9-project">${html(projectName(task))}</span>
              <span class="task-kind-cell task-kind-badge ${html(type)}">${html(taskTypeLabel(task))}</span>
              <span>Prioridade ${html(task.priority ?? '—')}</span>
              <span>${html(formatDate(task.created_at))}</span>
            </div>
          </td>
          <td class="tasks-v9-state">${statusChip(task)}</td>
          <td class="tasks-v9-actions">
            <button class="ghost tasks-v9-details" type="button" data-id="${html(id)}" aria-expanded="false" aria-controls="execution-details-${html(id)}">Detalhes</button>
            ${approval}${remove}
          </td>
        </tr>
        <tr class="task-details-row task-instructions-row" data-task-details-row="${html(id)}" hidden>
          <td colspan="3"><div id="execution-details-${html(id)}" class="tasks-v9-details-panel" data-task-details="${html(id)}" aria-live="polite"><span class="tasks-v9-detail-loading">Carregando detalhes…</span></div></td>
        </tr>`;
    }).join('');

    bindRows();
    document.dispatchEvent(new CustomEvent('devpilot:tasks-rendered', {detail:{count:filtered.length}}));
  }

  async function fetchDetail(taskId) {
    if (ui.detailCache.has(taskId)) return ui.detailCache.get(taskId);
    const task = await api(`/ui/tasks/${encodeURIComponent(taskId)}`);
    ui.detailCache.set(taskId, task);
    return task;
  }

  async function toggleDetails(button) {
    const id = String(button.dataset.id || '');
    const row = document.querySelector(`[data-task-details-row="${CSS.escape(id)}"]`);
    const panel = document.querySelector(`[data-task-details="${CSS.escape(id)}"]`);
    if (!row || !panel) return;

    const opening = row.hidden;
    if (!opening) {
      row.hidden = true;
      row.style.display = 'none';
      button.textContent = 'Detalhes';
      button.setAttribute('aria-expanded', 'false');
      return;
    }

    document.querySelectorAll('.task-details-row:not([hidden])').forEach(other => {
      if (other === row) return;
      other.hidden = true;
      other.style.display = 'none';
      const otherId = other.dataset.taskDetailsRow;
      const otherButton = document.querySelector(`.tasks-v9-details[data-id="${CSS.escape(otherId)}"]`);
      if (otherButton) {
        otherButton.textContent = 'Detalhes';
        otherButton.setAttribute('aria-expanded', 'false');
      }
    });

    row.hidden = false;
    row.style.display = '';
    button.textContent = 'Ocultar';
    button.setAttribute('aria-expanded', 'true');
    if (panel.dataset.loaded === '1') return;

    panel.setAttribute('aria-busy', 'true');
    try {
      const task = await fetchDetail(id);
      panel.dataset.loaded = '1';
      panel.innerHTML = `
        <div class="tasks-v9-detail-grid">
          <div><small>Projeto</small><strong>${html(projectName(task))}</strong></div>
          <div><small>Origem</small><strong>${html(task.source || 'DevPilot')}</strong></div>
          <div><small>Criada</small><strong>${html(formatDate(task.created_at))}</strong></div>
          <div><small>Atualizada</small><strong>${html(formatDate(task.updated_at))}</strong></div>
        </div>
        <div class="tasks-v9-context"><small>Contexto</small><p>${html(userContext(task.prompt))}</p></div>`;
    } catch (error) {
      panel.innerHTML = `<div class="tasks-v9-detail-error" role="alert">${html(error?.message || 'Não foi possível carregar os detalhes da execução.')}</div>`;
    } finally {
      panel.removeAttribute('aria-busy');
    }
  }

  async function approveTask(button) {
    const id = String(button.dataset.id || '');
    button.disabled = true;
    const text = button.textContent;
    button.textContent = 'Aprovando…';
    try {
      await api(`/tasks/${encodeURIComponent(id)}/approve`, {method:'POST'});
      notify('Execução aprovada');
      await reloadTasks(ui.limit);
    } catch (error) {
      notify(error?.message || 'Não foi possível aprovar a execução');
      button.disabled = false;
      button.textContent = text;
    }
  }

  async function deleteTask(button) {
    const id = String(button.dataset.id || '');
    const task = (state.tasks || []).find(item => String(item.id) === id);
    if (!task) return;
    if (!window.confirm(`Excluir a execução “${task.title}”?\n\nOs runs vinculados serão removidos. Esta ação não pode ser desfeita.`)) return;

    button.disabled = true;
    button.textContent = 'Excluindo…';
    try {
      const token = String(localStorage.getItem('devpilot-token') || '').trim();
      const response = await fetch(`/api/tasks/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers:{Authorization:`Bearer ${token}`},
        cache:'no-store',
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const detail = typeof data?.detail === 'string' ? data.detail : 'Não foi possível excluir a execução';
        throw new Error(detail === 'Active task cannot be deleted' ? 'Execução ativa não pode ser excluída.' : detail);
      }
      state.tasks = (state.tasks || []).filter(item => String(item.id) !== id);
      ui.detailCache.delete(id);
      renderOperationalTasks();
      notify('Execução excluída');
      if (typeof loadDashboard === 'function') window.setTimeout(() => void loadDashboard(), 50);
    } catch (error) {
      notify(error?.message || 'Não foi possível excluir a execução');
      button.disabled = false;
      button.textContent = 'Excluir';
    }
  }

  function bindRows() {
    document.querySelectorAll('.tasks-v9-details').forEach(button => {
      button.onclick = () => void toggleDetails(button);
    });
    document.querySelectorAll('.tasks-v9-approve').forEach(button => {
      button.onclick = () => void approveTask(button);
    });
    document.querySelectorAll('.tasks-v9-delete').forEach(button => {
      button.onclick = () => void deleteTask(button);
    });
  }

  function taskSignature(tasks) {
    return (Array.isArray(tasks) ? tasks : [])
      .map(task => [task.id, task.project_id, normalizeStatus(task.status), task.updated_at || task.created_at || ''].join(':'))
      .join('|');
  }

  function tasksViewIsVisible() {
    return !document.hidden && document.querySelector('#tasks-view')?.classList.contains('active') === true;
  }

  function scheduleLiveSync(delay = LIVE_POLL_MS) {
    window.clearTimeout(ui.liveTimer);
    ui.liveTimer = window.setTimeout(() => void syncLiveTasks(), delay);
  }

  async function syncLiveTasks() {
    if (!tasksViewIsVisible()) return scheduleLiveSync(1500);
    if (ui.liveBusy || ui.loading) return scheduleLiveSync();

    ui.liveBusy = true;
    try {
      const safeLimit = Math.max(1, Math.min(50, Number(ui.limit) || 12));
      const tasks = await api(`/ui/tasks?limit=${safeLimit}`, {retry:false, timeoutMs:5000});
      const rows = Array.isArray(tasks) ? tasks : [];
      const nextSignature = taskSignature(rows);
      if (nextSignature !== ui.liveSignature) {
        ui.liveSignature = nextSignature;
        state.tasks = rows;
        ui.detailCache.clear();
        renderOperationalTasks();
      }
    } catch (error) {
      console.warn('[DevPilot Execuções] sincronização temporariamente indisponível', error);
    } finally {
      ui.liveBusy = false;
      scheduleLiveSync();
    }
  }

  async function reloadTasks(limit = ui.limit) {
    if (ui.loading) return;
    ui.loading = true;
    const refresh = document.querySelector('#tasks-v9-refresh');
    const target = document.querySelector('#tasks-table');
    if (refresh) {
      refresh.disabled = true;
      refresh.setAttribute('aria-busy', 'true');
      refresh.textContent = 'Atualizando…';
    }
    if (target && !(state.tasks || []).length) {
      target.innerHTML = '<tr><td colspan="3" class="tasks-v9-empty">Carregando execuções…</td></tr>';
    }

    try {
      const safeLimit = Math.max(1, Math.min(50, Number(limit) || 12));
      const tasks = await api(`/ui/tasks?limit=${safeLimit}`);
      state.tasks = Array.isArray(tasks) ? tasks : [];
      ui.limit = safeLimit;
      ui.liveSignature = taskSignature(state.tasks);
      ui.detailCache.clear();
      renderOperationalTasks();
    } catch (error) {
      notify(error?.message || 'Falha ao atualizar execuções');
      if (target && !(state.tasks || []).length) {
        target.innerHTML = `<tr><td colspan="3" class="tasks-v9-empty" role="alert">Não foi possível carregar as execuções. Use “Atualizar” para tentar novamente.</td></tr>`;
      }
    } finally {
      ui.loading = false;
      if (refresh) {
        refresh.disabled = false;
        refresh.removeAttribute('aria-busy');
        refresh.textContent = 'Atualizar';
      }
    }
  }

  function toggleIndicators(button) {
    const target = document.querySelector('#task-analytics');
    if (!target) return;
    const opening = target.hidden;
    if (!opening) {
      target.hidden = true;
      button.textContent = 'Indicadores';
      button.setAttribute('aria-expanded', 'false');
      return;
    }
    if (typeof window.renderTaskAnalytics !== 'function') {
      target.hidden = true;
      notify('Os indicadores ainda não estão disponíveis. Tente novamente.');
      return;
    }
    target.hidden = false;
    button.setAttribute('aria-expanded', 'true');
    window.renderTaskAnalytics();
    button.textContent = 'Ocultar indicadores';
  }

  function bindToolbar() {
    const inputs = [
      document.querySelector('#tasks-v9-search'),
      document.querySelector('#tasks-v9-project'),
      document.querySelector('#tasks-v9-status'),
      document.querySelector('#tasks-v9-type'),
    ].filter(Boolean);
    inputs.forEach(input => input.addEventListener(input.tagName === 'INPUT' ? 'input' : 'change', renderOperationalTasks));

    document.querySelector('#tasks-v9-refresh')?.addEventListener('click', () => void reloadTasks(ui.limit));
    document.querySelector('#tasks-v9-more')?.addEventListener('click', () => {
      const next = Math.min(50, ui.limit + 12);
      if (next === ui.limit) return notify('As 50 execuções mais recentes já estão carregadas');
      void reloadTasks(next);
    });
    document.querySelector('#tasks-v9-back')?.addEventListener('click', () => {
      const overview = document.querySelector('[data-view="overview"]');
      if (overview) return overview.click();
      if (typeof setView === 'function') setView('overview');
    });

    const indicators = document.querySelector('#tasks-v9-indicators');
    if (indicators) {
      indicators.setAttribute('aria-expanded', 'false');
      indicators.setAttribute('aria-controls', 'task-analytics');
      indicators.addEventListener('click', () => toggleIndicators(indicators));
    }
  }

  function install() {
    const target = document.querySelector('#tasks-table');
    if (!target) return;
    window.renderTasks = renderOperationalTasks;
    try { renderTasks = renderOperationalTasks; } catch (_) {}
    bindToolbar();

    if (typeof state !== 'undefined' && Array.isArray(state.tasks) && state.tasks.length) {
      ui.liveSignature = taskSignature(state.tasks);
      renderOperationalTasks();
    } else {
      void reloadTasks(ui.limit);
    }
    scheduleLiveSync(500);
  }

  document.addEventListener('visibilitychange', () => scheduleLiveSync(150));
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once:true});
  else install();
})();
