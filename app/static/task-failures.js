(() => {
  let taskRunGeneration = 0;

  function ensureTaskFailureStyles() {
    if (document.getElementById('task-failure-styles')) return;
    const style = document.createElement('style');
    style.id = 'task-failure-styles';
    style.textContent = `
      .task-status-stack{display:flex;flex-direction:column;align-items:flex-start;gap:7px;min-width:150px}
      .task-failure-reason{display:block;max-width:300px;color:#f1a7b8;line-height:1.35;font-size:11px;white-space:normal;overflow-wrap:anywhere}
      .task-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
      .task-log-link{font-size:12px;font-weight:700;text-decoration:none;white-space:nowrap}
      .task-log-modal-panel{width:min(860px,calc(100vw - 32px));max-height:min(82vh,760px)}
      .task-log-meta{margin:0 0 12px;color:var(--muted,#9aa8bd);font-size:12px}
      .task-log-output{margin:0;max-height:58vh;overflow:auto;padding:16px;border:1px solid var(--line,#26364f);border-radius:12px;background:#050c17;color:#dce7f7;font-size:12px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}
      @media (max-width:720px){.task-failure-reason{max-width:190px}.task-log-modal-panel{width:calc(100vw - 20px)}}
    `;
    document.head.appendChild(style);
  }

  function ensureTaskLogDialog() {
    let dialog = document.getElementById('task-log-modal');
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = 'task-log-modal';
    dialog.innerHTML = `
      <div class="modal task-log-modal-panel">
        <button class="close task-log-close" type="button" aria-label="Fechar">×</button>
        <span class="eyebrow">LOG DA EXECUÇÃO</span>
        <h2 id="task-log-title">Detalhes da execução</h2>
        <p class="task-log-meta" id="task-log-meta"></p>
        <pre class="task-log-output" id="task-log-output"></pre>
      </div>`;
    document.body.appendChild(dialog);
    dialog.querySelector('.task-log-close').onclick = () => dialog.close();
    dialog.addEventListener('click', event => {
      if (event.target === dialog) dialog.close();
    });
    return dialog;
  }

  function formatTaskLog(data) {
    const parts = [];
    if (data.summary) parts.push(`RESUMO\n${data.summary}`);
    if (data.logs && (typeof data.logs !== 'object' || Object.keys(data.logs).length)) {
      const rendered = typeof data.logs === 'string' ? data.logs : JSON.stringify(data.logs, null, 2);
      parts.push(`LOG\n${rendered}`);
    }
    if (data.commit_sha) parts.push(`COMMIT\n${data.commit_sha}`);
    if (data.pull_request_url) parts.push(`PULL REQUEST\n${data.pull_request_url}`);
    return parts.join('\n\n') || 'Nenhum conteúdo de log foi registrado nesta execução.';
  }

  async function openTaskLog(runId, task) {
    const dialog = ensureTaskLogDialog();
    const title = dialog.querySelector('#task-log-title');
    const meta = dialog.querySelector('#task-log-meta');
    const output = dialog.querySelector('#task-log-output');
    title.textContent = task?.title || 'Detalhes da execução';
    meta.textContent = 'Carregando log…';
    output.textContent = '';
    if (!dialog.open) dialog.showModal();
    try {
      const data = await api(`/task-runs/${runId}`);
      const started = data.started_at ? new Date(data.started_at).toLocaleString('pt-BR') : '—';
      meta.textContent = `Status: ${data.status || '—'} · tentativa ${data.attempt || 1} · início ${started}`;
      output.textContent = formatTaskLog(data);
    } catch (error) {
      meta.textContent = 'Falha ao carregar o log';
      output.textContent = error.message || 'Não foi possível consultar esta execução.';
    }
  }

  async function hydrateTaskRunDetails(generation) {
    try {
      const details = await api('/task-runs/latest?limit=500');
      if (generation !== taskRunGeneration) return;
      const byTask = new Map(details.map(item => [item.task_id, item]));
      state.tasks.forEach(task => {
        const row = document.querySelector(`#tasks-table tr[data-task-id="${CSS.escape(task.id)}"]`);
        if (!row) return;
        const detail = byTask.get(task.id);
        const reason = row.querySelector('.task-failure-reason');
        const logTarget = row.querySelector('.task-log-action');

        if (reason) {
          const text = detail?.failure_reason || 'Falha registrada sem mensagem detalhada.';
          reason.textContent = text;
          reason.title = text;
        }

        if (logTarget) {
          logTarget.innerHTML = '';
          if (detail?.has_log && detail.run_id) {
            const link = document.createElement('a');
            link.className = 'link task-log-link';
            link.href = detail.log_url || `/api/task-runs/${detail.run_id}`;
            link.textContent = 'Ver log';
            link.onclick = event => {
              event.preventDefault();
              openTaskLog(detail.run_id, task);
            };
            logTarget.appendChild(link);
          } else if (task.status === 'failed') {
            const unavailable = document.createElement('small');
            unavailable.textContent = 'Sem log';
            logTarget.appendChild(unavailable);
          }
        }
      });
    } catch (_) {
      if (generation !== taskRunGeneration) return;
      document.querySelectorAll('.task-failure-reason').forEach(node => {
        node.textContent = 'Detalhe indisponível';
      });
    }
  }

  ensureTaskFailureStyles();

  renderTasks = function renderTasksWithFailureDetails() {
    const table = $('#tasks-table');
    table.innerHTML = state.tasks.map(task => {
      const failure = task.status === 'failed'
        ? '<small class="task-failure-reason">Carregando motivo…</small>'
        : '';
      const approval = task.status === 'awaiting_approval'
        ? `<button class="primary approve" data-id="${task.id}">Aprovar</button>`
        : '';
      return `<tr data-task-id="${esc(task.id)}"><td><strong>${esc(task.title)}</strong><br><small>${new Date(task.created_at).toLocaleString('pt-BR')}</small></td><td>${esc(task.source)}</td><td><div class="task-status-stack">${status(task.status)}${failure}</div></td><td>${task.priority}</td><td><div class="task-actions">${approval}<span class="task-log-action"></span>${!approval ? '' : ''}</div></td></tr>`;
    }).join('') || '<tr><td colspan="5" class="empty">Nenhuma tarefa registrada.</td></tr>';

    $$('.approve').forEach(button => {
      button.onclick = async () => {
        try {
          await api(`/tasks/${button.dataset.id}/approve`, {method: 'POST'});
          toast('Tarefa aprovada e enfileirada');
          load();
        } catch (error) {
          toast(error.message);
        }
      };
    });

    const generation = ++taskRunGeneration;
    hydrateTaskRunDetails(generation);
  };
})();
