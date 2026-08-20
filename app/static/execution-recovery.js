(() => {
  const FAILURE_LABELS = {
    usage_limit: 'Limite do Codex atingido',
    rate_limit: 'Limite temporário do executor',
    auth: 'Autenticação do executor',
    transient: 'Executor temporariamente indisponível',
    partial_changes_detected: 'Alterações parciais detectadas',
    execution: 'Falha de execução',
  };

  function parseDetails(run) {
    try {
      const parsed = JSON.parse(run?.logs || '{}');
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
      return {};
    }
  }

  function ensureActions() {
    const modal = document.querySelector('#result-modal .result-modal') || document.querySelector('#result-modal .modal');
    if (!modal) return null;
    let actions = document.querySelector('#result-recovery-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.id = 'result-recovery-actions';
      actions.className = 'result-recovery-actions';
      modal.appendChild(actions);
    }
    return actions;
  }

  async function retryTask(taskId, button) {
    const original = button?.textContent;
    if (button) {
      button.disabled = true;
      button.textContent = 'Recolocando na fila…';
    }
    try {
      const result = await api(`/tasks/${taskId}/retry`, {method: 'POST'});
      document.querySelector('#result-modal')?.close();
      toast(result.message || 'Tarefa recolocada na fila');
      await load();
    } catch (error) {
      toast(error.message);
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = original;
      }
    }
  }

  const baseRenderTasks = renderTasks;
  renderTasks = function renderTasksWithRecovery() {
    baseRenderTasks();
    const rows = [...document.querySelectorAll('#tasks-table tr')];
    state.tasks.forEach((task, index) => {
      if (!['blocked', 'failed'].includes(task.status)) return;
      const cell = rows[index]?.lastElementChild;
      if (!cell) return;
      const resultButton = `<button class="ghost result" data-id="${task.id}" data-title="${esc(task.title)}">Detalhes</button>`;
      const retryButton = `<button class="primary retry-task" data-id="${task.id}">Reexecutar</button>`;
      cell.innerHTML = `<div class="recovery-actions">${resultButton}${retryButton}</div>`;
    });
    document.querySelectorAll('.result').forEach(button => {
      button.onclick = () => openTaskResult(button.dataset.id, button.dataset.title);
    });
    document.querySelectorAll('.retry-task').forEach(button => {
      button.onclick = () => retryTask(button.dataset.id, button);
    });
  };

  openTaskResult = async function openTaskResultWithRecovery(id, title) {
    try {
      const runs = await api(`/tasks/${id}/runs`);
      const run = runs[0];
      const titleNode = document.querySelector('#result-title');
      const summaryNode = document.querySelector('#result-summary');
      const metaNode = document.querySelector('#result-meta');
      const outputNode = document.querySelector('#result-output');
      const actions = ensureActions();
      titleNode.textContent = title || 'Resultado da tarefa';
      if (actions) actions.innerHTML = '';

      if (!run) {
        summaryNode.textContent = 'Nenhuma execução registrada.';
        metaNode.textContent = '';
        outputNode.textContent = '';
        document.querySelector('#result-modal').showModal();
        return;
      }

      const details = parseDetails(run);
      const failureLabel = FAILURE_LABELS[details.failure_code] || '';
      const provider = details.provider || '—';
      const executor = details.executor || '—';
      const authMode = details.auth_mode === 'api_key'
        ? 'API key isolada'
        : details.auth_mode === 'chatgpt_session'
          ? 'Sessão ChatGPT'
          : details.auth_mode || '—';
      const attempts = Array.isArray(details.attempts) ? details.attempts : [];
      const attemptsText = attempts.length
        ? ` · Tentativas ${attempts.map(item => `${item.provider || 'executor'}:${item.exit_code === 0 ? 'ok' : item.failure_code || 'erro'}`).join(' → ')}`
        : '';

      summaryNode.textContent = failureLabel
        ? `${failureLabel}. ${run.summary || details.summary || ''}`.trim()
        : run.summary || details.summary || 'Execução concluída.';
      metaNode.textContent = [
        `Status: ${run.status}`,
        `Executor: ${executor}`,
        `Provedor: ${provider}`,
        `Autenticação: ${authMode}`,
        details.branch ? `Branch: ${details.branch}` : '',
        details.fallback_used ? 'Fallback: usado' : '',
        details.paid_api_fallback ? 'API: pode consumir créditos' : '',
      ].filter(Boolean).join(' · ') + attemptsText;

      const diagnostic = [];
      if (details.suggested_action) diagnostic.push(`Próxima ação: ${details.suggested_action}`);
      if (details.stdout) diagnostic.push(details.stdout);
      else if (details.output) diagnostic.push(details.output);
      else if (run.logs && !details.summary) diagnostic.push(run.logs);
      outputNode.textContent = diagnostic.join('\n\n') || 'Sem saída detalhada.';

      if (actions && ['blocked', 'failed'].includes(run.status)) {
        const retry = document.createElement('button');
        retry.className = 'primary';
        retry.type = 'button';
        retry.textContent = 'Reexecutar tarefa';
        retry.onclick = () => retryTask(id, retry);
        actions.appendChild(retry);

        if (details.failure_code === 'usage_limit' && !details.fallback_used) {
          const providers = document.createElement('button');
          providers.className = 'ghost';
          providers.type = 'button';
          providers.textContent = 'Abrir Modelos de IA';
          providers.onclick = () => {
            document.querySelector('#result-modal').close();
            showView('providers');
          };
          actions.appendChild(providers);
        }
      }
      document.querySelector('#result-modal').showModal();
    } catch (error) {
      toast(error.message);
    }
  };

  const style = document.createElement('style');
  style.textContent = `
    .status.blocked{color:var(--amber);background:#ffbb5520}
    .recovery-actions,.result-recovery-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .result-recovery-actions{margin-top:2px;padding-top:14px;border-top:1px solid var(--line)}
    .recovery-actions .primary,.recovery-actions .ghost{padding:7px 10px;font-size:11px}
  `;
  document.head.appendChild(style);
})();
