(() => {
  'use strict';

  if (window.__devpilotTasksOperationalV9) {
    window.renderTasks?.();
    return;
  }

  window.__devpilotTasksOperationalV9 = true;

  const ui = {
    limit: 12,
    detailCache: new Map(),
    loading: false,
  };

  const TERMINAL = new Set([
    'awaiting_approval',
    'completed',
    'failed',
    'blocked',
  ]);

  const ACTIVE = new Set([
    'queued',
    'planning',
    'running',
    'review',
  ]);

  const ATTENTION = new Set([
    'awaiting_approval',
    'failed',
    'blocked',
  ]);

  function html(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function notify(message) {
    if (typeof toast === 'function') {
      toast(message);
      return;
    }

    console.info('[DevPilot]', message);
  }

  function normalizeStatus(value) {
    return String(value || '')
      .split('.')
      .pop()
      .toLowerCase()
      .replaceAll(' ', '_');
  }

  function statusLabel(value) {
    const status = normalizeStatus(value);

    const labels = {
      queued: 'Na fila',
      planning: 'Planejando',
      running: 'Executando',
      review: 'Em revisão',
      awaiting_approval: 'Aguardando aprovação',
      completed: 'Concluída',
      failed: 'Falhou',
      blocked: 'Bloqueada',
    };

    return labels[status] || status || '—';
  }

  function taskType(task) {
    const source = String(task?.source || '').toLowerCase();
    const title = String(task?.title || '').toLowerCase();

    if (
      source.includes('analysis') ||
      source.includes('verification') ||
      title.startsWith('análise') ||
      title.startsWith('analise') ||
      title.includes('auditoria') ||
      title.includes('revisão')
    ) {
      return 'analysis';
    }

    return 'execution';
  }

  function taskTypeLabel(task) {
    return taskType(task) === 'analysis'
      ? 'Análise'
      : 'Execução';
  }

  function projectName(task) {
    if (task?.project_name) {
      return String(task.project_name);
    }

    const projects =
      typeof state !== 'undefined' &&
      Array.isArray(state.projects)
        ? state.projects
        : [];

    return String(
      projects.find(
        project =>
          String(project.id) ===
          String(task?.project_id)
      )?.name ||
      'Projeto não identificado'
    );
  }

  function formatDate(value) {
    if (!value) return '';

    try {
      return new Date(value).toLocaleString(
        'pt-BR',
        {
          dateStyle: 'short',
          timeStyle: 'short',
        }
      );
    } catch (_) {
      return String(value);
    }
  }

  function userContext(prompt) {
    let text = String(prompt || '').trim();

    const marker = 'Contexto do usuário:';

    if (text.includes(marker)) {
      text = text.split(marker).slice(1).join(marker);
    }

    text = text
      .replace(/\[DEVPILOT_MODE=[^\]]+\]/gi, '')
      .trim();

    if (text.length > 1400) {
      text = `${text.slice(0, 1400).trim()}…`;
    }

    return text || 'Nenhum contexto adicional registrado.';
  }

  function canDelete(task) {
    const status = normalizeStatus(task.status);

    const superAdmin =
      typeof isSuperAdmin === 'function'
        ? isSuperAdmin()
        : false;

    return superAdmin && TERMINAL.has(status);
  }

  function taskMatches(task) {
    const search =
      String(
        document.querySelector(
          '#tasks-v9-search'
        )?.value || ''
      )
        .trim()
        .toLowerCase();

    const project =
      String(
        document.querySelector(
          '#tasks-v9-project'
        )?.value || ''
      );

    const statusFilter =
      String(
        document.querySelector(
          '#tasks-v9-status'
        )?.value || ''
      );

    const typeFilter =
      String(
        document.querySelector(
          '#tasks-v9-type'
        )?.value || ''
      );

    const status = normalizeStatus(task.status);
    const type = taskType(task);
    const projectId = String(task.project_id || '');

    if (
      project &&
      projectId !== project
    ) {
      return false;
    }

    if (
      typeFilter &&
      type !== typeFilter
    ) {
      return false;
    }

    if (statusFilter === 'active' && !ACTIVE.has(status)) {
      return false;
    }

    if (
      statusFilter === 'attention' &&
      !ATTENTION.has(status)
    ) {
      return false;
    }

    if (
      statusFilter === 'completed' &&
      status !== 'completed'
    ) {
      return false;
    }

    if (search) {
      const haystack = [
        task.title,
        projectName(task),
        task.source,
        statusLabel(task.status),
      ]
        .join(' ')
        .toLowerCase();

      if (!haystack.includes(search)) {
        return false;
      }
    }

    return true;
  }

  function updateProjectFilter(tasks) {
    const select =
      document.querySelector('#tasks-v9-project');

    if (!select) return;

    const current = select.value;

    const projects = new Map();

    tasks.forEach(task => {
      if (!task.project_id) return;

      projects.set(
        String(task.project_id),
        projectName(task)
      );
    });

    const options = [
      '<option value="">Todos</option>',
      ...[...projects.entries()]
        .sort((a, b) =>
          a[1].localeCompare(
            b[1],
            'pt-BR'
          )
        )
        .map(
          ([id, name]) =>
            `<option value="${html(id)}">${html(name)}</option>`
        ),
    ];

    select.innerHTML = options.join('');

    if (projects.has(current)) {
      select.value = current;
    }
  }

  function statusChip(task) {
    const status = normalizeStatus(task.status);

    return `
      <span class="tasks-v9-status ${html(status)}">
        ${html(statusLabel(status))}
      </span>
    `;
  }

  function renderOperationalTasks() {
    const target =
      document.querySelector('#tasks-table');

    if (!target) return;

    const tasks =
      typeof state !== 'undefined' &&
      Array.isArray(state.tasks)
        ? state.tasks
        : [];

    updateProjectFilter(tasks);

    const filtered =
      tasks.filter(taskMatches);

    const count =
      document.querySelector('#tasks-v9-count');

    if (count) {
      count.textContent =
        `${filtered.length} de ${tasks.length} tarefa(s) exibida(s)`;
    }

    if (!filtered.length) {
      target.innerHTML = `
        <tr>
          <td colspan="3" class="tasks-v9-empty">
            Nenhuma tarefa corresponde aos filtros.
          </td>
        </tr>
      `;

      return;
    }

    /*
     * Fecha qualquer detalhe remanescente antes de redesenhar.
     * Isso evita estado visual herdado de renderizações anteriores.
     */
    target
      .querySelectorAll(
        '.task-details-row, .task-instructions-row'
      )
      .forEach(row => {
        row.hidden = true;
        row.style.display = 'none';
      });

    target.innerHTML = filtered.map(task => {
      const id = String(task.id || '');
      const type = taskType(task);
      const status = normalizeStatus(task.status);

      const approval =
        status === 'awaiting_approval'
          ? `
            <button
              class="primary tasks-v9-approve"
              type="button"
              data-id="${html(id)}"
            >
              Aprovar
            </button>
          `
          : '';

      const remove = canDelete(task)
        ? `
          <button
            class="danger tasks-v9-delete delete-task"
            type="button"
            data-id="${html(id)}"
          >
            Excluir
          </button>
        `
        : '';

      return `
        <tr
          class="task-main-row tasks-v9-row"
          data-task-id="${html(id)}"
        >
          <td class="tasks-v9-main">

            <strong
              class="tasks-v9-title"
              title="${html(task.title)}"
            >
              ${html(task.title || 'Tarefa sem título')}
            </strong>

            <div class="tasks-v9-meta">

              <span class="tasks-v9-project">
                ${html(projectName(task))}
              </span>

              <span
                class="task-kind-cell task-kind-badge ${html(type)}"
              >
                ${html(taskTypeLabel(task))}
              </span>

              <span>
                Prioridade ${html(task.priority ?? '—')}
              </span>

              <span>
                ${html(formatDate(task.created_at))}
              </span>

            </div>
          </td>

          <td class="tasks-v9-state">
            ${statusChip(task)}
          </td>

          <td class="tasks-v9-actions">

            <button
              class="ghost tasks-v9-details"
              type="button"
              data-id="${html(id)}"
              aria-expanded="false"
            >
              Detalhes
            </button>

            ${approval}
            ${remove}

          </td>
        </tr>

        <tr
          class="task-details-row task-instructions-row"
          data-task-details-row="${html(id)}"
          hidden
        >
          <td colspan="3">
            <div
              class="tasks-v9-details-panel"
              data-task-details="${html(id)}"
            >
              <span class="tasks-v9-detail-loading">
                Carregando detalhes…
              </span>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    bindRows();

    document.dispatchEvent(
      new CustomEvent(
        'devpilot:tasks-rendered',
        {
          detail: {
            count: filtered.length,
          },
        }
      )
    );
  }

  async function fetchDetail(taskId) {
    if (ui.detailCache.has(taskId)) {
      return ui.detailCache.get(taskId);
    }

    const task =
      await api(
        `/ui/tasks/${encodeURIComponent(taskId)}`
      );

    ui.detailCache.set(taskId, task);

    return task;
  }

  async function toggleDetails(button) {
    const id = String(button.dataset.id || '');

    const row = document.querySelector(
      `[data-task-details-row="${CSS.escape(id)}"]`
    );

    const panel = document.querySelector(
      `[data-task-details="${CSS.escape(id)}"]`
    );

    if (!row || !panel) return;

    const opening = row.hidden;

    if (!opening) {
      row.hidden = true;
      row.style.display = 'none';

      button.textContent = 'Detalhes';
      button.setAttribute(
        'aria-expanded',
        'false'
      );

      return;
    }

    /*
     * Fecha qualquer outro detalhe aberto.
     */
    document
      .querySelectorAll(
        '.task-details-row:not([hidden])'
      )
      .forEach(other => {
        if (other === row) return;

        other.hidden = true;
        other.style.display = 'none';

        const otherId =
          other.dataset.taskDetailsRow;

        const otherButton =
          document.querySelector(
            `.tasks-v9-details[data-id="${CSS.escape(otherId)}"]`
          );

        if (otherButton) {
          otherButton.textContent = 'Detalhes';
          otherButton.setAttribute(
            'aria-expanded',
            'false'
          );
        }
      });

    row.hidden = false;
    row.style.display = '';

    button.textContent = 'Ocultar';
    button.setAttribute(
      'aria-expanded',
      'true'
    );

    if (panel.dataset.loaded === '1') {
      return;
    }

    panel.innerHTML =
      '<span class="tasks-v9-detail-loading">Carregando detalhes…</span>';

    try {
      const task = await fetchDetail(id);

      panel.dataset.loaded = '1';

      panel.innerHTML = `
        <div class="tasks-v9-detail-grid">

          <div>
            <small>Projeto</small>
            <strong>
              ${html(projectName(task))}
            </strong>
          </div>

          <div>
            <small>Origem</small>
            <strong>
              ${html(task.source || 'DevPilot')}
            </strong>
          </div>

          <div>
            <small>Criada</small>
            <strong>
              ${html(formatDate(task.created_at))}
            </strong>
          </div>

          <div>
            <small>Atualizada</small>
            <strong>
              ${html(formatDate(task.updated_at))}
            </strong>
          </div>

        </div>

        <div class="tasks-v9-context">
          <small>Contexto</small>
          <p>
            ${html(userContext(task.prompt))}
          </p>
        </div>
      `;

    } catch (error) {
      panel.innerHTML = `
        <div class="tasks-v9-detail-error">
          ${html(
            error?.message ||
            'Não foi possível carregar os detalhes.'
          )}
        </div>
      `;
    }
  }

  async function approveTask(button) {
    const id = String(button.dataset.id || '');

    button.disabled = true;
    const text = button.textContent;
    button.textContent = 'Aprovando…';

    try {
      await api(
        `/tasks/${encodeURIComponent(id)}/approve`,
        {
          method: 'POST',
        }
      );

      notify('Tarefa aprovada');

      await reloadTasks(ui.limit);

    } catch (error) {
      notify(
        error?.message ||
        'Não foi possível aprovar a tarefa'
      );

      button.disabled = false;
      button.textContent = text;
    }
  }

  async function deleteTask(button) {
    const id = String(button.dataset.id || '');

    const task =
      (state.tasks || []).find(
        item => String(item.id) === id
      );

    if (!task) return;

    const confirmed = window.confirm(
      `Excluir a tarefa “${task.title}”?\n\n` +
      'As execuções vinculadas serão removidas. ' +
      'Esta ação não pode ser desfeita.'
    );

    if (!confirmed) return;

    button.disabled = true;
    button.textContent = 'Excluindo…';

    try {
      const token = String(
        localStorage.getItem(
          'devpilot-token'
        ) || ''
      ).trim();

      const response = await fetch(
        `/api/tasks/${encodeURIComponent(id)}`,
        {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${token}`,
          },
          cache: 'no-store',
        }
      );

      if (!response.ok) {
        const data =
          await response.json()
            .catch(() => ({}));

        const detail =
          typeof data?.detail === 'string'
            ? data.detail
            : 'Não foi possível excluir a tarefa';

        throw new Error(
          detail === 'Active task cannot be deleted'
            ? 'Tarefa ativa não pode ser excluída.'
            : detail
        );
      }

      state.tasks = (state.tasks || [])
        .filter(
          item =>
            String(item.id) !== id
        );

      ui.detailCache.delete(id);

      renderOperationalTasks();

      notify('Tarefa excluída');

      if (
        typeof loadDashboard === 'function'
      ) {
        window.setTimeout(
          () => void loadDashboard(),
          50
        );
      }

    } catch (error) {
      notify(
        error?.message ||
        'Não foi possível excluir a tarefa'
      );

      button.disabled = false;
      button.textContent = 'Excluir';
    }
  }

  function bindRows() {
    document
      .querySelectorAll('.tasks-v9-details')
      .forEach(button => {
        button.onclick =
          () => void toggleDetails(button);
      });

    document
      .querySelectorAll('.tasks-v9-approve')
      .forEach(button => {
        button.onclick =
          () => void approveTask(button);
      });

    document
      .querySelectorAll('.tasks-v9-delete')
      .forEach(button => {
        button.onclick =
          () => void deleteTask(button);
      });
  }

  async function reloadTasks(limit = ui.limit) {
    if (ui.loading) return;

    ui.loading = true;

    const refresh =
      document.querySelector(
        '#tasks-v9-refresh'
      );

    if (refresh) {
      refresh.disabled = true;
      refresh.textContent = 'Atualizando…';
    }

    try {
      const safeLimit =
        Math.max(
          1,
          Math.min(
            50,
            Number(limit) || 12
          )
        );

      const tasks =
        await api(
          `/ui/tasks?limit=${safeLimit}`
        );

      state.tasks =
        Array.isArray(tasks)
          ? tasks
          : [];

      ui.limit = safeLimit;

      renderOperationalTasks();

    } catch (error) {
      notify(
        error?.message ||
        'Falha ao atualizar tarefas'
      );

    } finally {
      ui.loading = false;

      if (refresh) {
        refresh.disabled = false;
        refresh.textContent = 'Atualizar';
      }
    }
  }

  async function toggleIndicators(button) {
    const target =
      document.querySelector(
        '#task-analytics'
      );

    if (!target) return;

    const opening = target.hidden;

    target.hidden = !opening;

    if (!opening) {
      button.textContent = 'Indicadores';
      return;
    }

    button.disabled = true;
    button.textContent = 'Carregando…';

    try {
      if (
        typeof window.renderTaskAnalytics !==
        'function'
      ) {
        await new Promise((resolve, reject) => {
          const existing =
            document.querySelector(
              'script[data-tasks-v9-analytics]'
            );

          if (existing) {
            existing.addEventListener(
              'load',
              resolve,
              {once:true}
            );

            window.setTimeout(
              resolve,
              500
            );

            return;
          }

          const script =
            document.createElement('script');

          script.src =
            '/assets/task-analytics.js?v=tasks-v9';

          script.async = true;
          script.dataset.tasksV9Analytics = '1';

          script.onload = resolve;
          script.onerror = reject;

          document.head.appendChild(script);
        });
      }

      window.renderTaskAnalytics?.();

      button.textContent =
        'Ocultar indicadores';

    } catch (error) {
      target.hidden = true;

      notify(
        'Não foi possível carregar indicadores'
      );

      button.textContent = 'Indicadores';

    } finally {
      button.disabled = false;
    }
  }

  function bindToolbar() {
    const search =
      document.querySelector(
        '#tasks-v9-search'
      );

    const project =
      document.querySelector(
        '#tasks-v9-project'
      );

    const status =
      document.querySelector(
        '#tasks-v9-status'
      );

    const type =
      document.querySelector(
        '#tasks-v9-type'
      );

    [search, project, status, type]
      .filter(Boolean)
      .forEach(input => {
        const event =
          input.tagName === 'INPUT'
            ? 'input'
            : 'change';

        input.addEventListener(
          event,
          renderOperationalTasks
        );
      });

    document
      .querySelector('#tasks-v9-refresh')
      ?.addEventListener(
        'click',
        () => void reloadTasks(ui.limit)
      );

    document
      .querySelector('#tasks-v9-more')
      ?.addEventListener(
        'click',
        () => {
          const next =
            Math.min(
              50,
              ui.limit + 12
            );

          if (next === ui.limit) {
            notify(
              'As 50 tarefas mais recentes já estão carregadas'
            );
            return;
          }

          void reloadTasks(next);
        }
      );

    document
      .querySelector('#tasks-v9-back')
      ?.addEventListener(
        'click',
        () => {
          const overview =
            document.querySelector(
              '[data-view="overview"]'
            );

          if (overview) {
            overview.click();
            return;
          }

          if (
            typeof setView === 'function'
          ) {
            setView('overview');
          }
        }
      );

    const indicators =
      document.querySelector(
        '#tasks-v9-indicators'
      );

    indicators?.addEventListener(
      'click',
      () => void toggleIndicators(indicators)
    );
  }

  function install() {
    const target =
      document.querySelector('#tasks-table');

    if (!target) return;

    /*
     * renderTasks passa a ter um único dono visual.
     */
    window.renderTasks =
      renderOperationalTasks;

    try {
      renderTasks =
        renderOperationalTasks;
    } catch (_) {}

    bindToolbar();

    if (
      typeof state !== 'undefined' &&
      Array.isArray(state.tasks) &&
      state.tasks.length
    ) {
      renderOperationalTasks();
    } else {
      void reloadTasks(ui.limit);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      install,
      {once:true}
    );
  } else {
    install();
  }
})();
