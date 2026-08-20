(() => {
  let taskRunGeneration = 0;
  let correctionPollTimer = null;
  let correctionPollInFlight = false;
  let trackedCorrection = null;

  function ensureTaskFailureStyles() {
    if (document.getElementById('task-failure-styles')) return;
    const style = document.createElement('style');
    style.id = 'task-failure-styles';
    style.textContent = `
      .task-status-stack{display:flex;flex-direction:column;align-items:flex-start;gap:7px;min-width:150px}
      .task-failure-reason{display:block;max-width:300px;color:#f1a7b8;line-height:1.35;font-size:11px;white-space:normal;overflow-wrap:anywhere}
      .task-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
      .task-log-link{font-size:12px;font-weight:700;text-decoration:none;white-space:nowrap}
      .task-log-modal-panel{width:min(900px,calc(100vw - 32px));max-height:min(88vh,820px);overflow:auto}
      .task-log-meta{margin:0 0 16px;color:var(--muted,#9aa8bd);font-size:12px}
      .task-client-card{margin:0 0 16px;padding:18px;border:1px solid #24665d;border-radius:14px;background:linear-gradient(145deg,#0b201f,#0b1723)}
      .task-client-card .eyebrow{display:block;margin-bottom:10px;color:#3be4d0}
      .task-client-report{color:#eaf4ff;font-size:14px;line-height:1.65;overflow-wrap:anywhere}
      .task-client-report h3{margin:18px 0 6px;color:#fff;font-size:15px}
      .task-client-report h3:first-child{margin-top:0}
      .task-client-report p{margin:0 0 9px;color:#d7e2ef}
      .task-client-report ul{margin:4px 0 10px;padding-left:20px;color:#d7e2ef}
      .task-client-report li{margin:4px 0}
      .task-technical-details{margin-top:12px;border:1px solid var(--line,#26364f);border-radius:12px;background:#07111d}
      .task-technical-details>summary{padding:13px 15px;cursor:pointer;color:#9eb1c8;font-weight:800;font-size:12px;user-select:none}
      .task-log-output{margin:0;max-height:48vh;overflow:auto;padding:16px;border-top:1px solid var(--line,#26364f);background:#050c17;color:#c7d5e8;font-size:11px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}
      .task-result-ok{color:#61e7ac;font-weight:800}
      .task-result-failed{color:#ff9eb0;font-weight:800}
      .task-correction-panel{margin:0 0 16px;padding:16px;border:1px solid #24649a;border-radius:14px;background:linear-gradient(145deg,#0b1d31,#0b1723)}
      .task-correction-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}
      .task-correction-head strong{display:block;color:#eff7ff;font-size:15px}
      .task-correction-head p{margin:5px 0 0;color:#b5c8dc;font-size:13px;line-height:1.45}
      .task-correction-start{flex:0 0 auto;white-space:nowrap}
      .task-correction-tracking{margin-top:14px}
      .task-correction-tracking[hidden]{display:none}
      .task-correction-state{margin:0;color:#d7e5f4;font-size:13px;line-height:1.45}
      .task-correction-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:13px}
      .task-correction-step{padding:9px 8px;border:1px solid #284056;border-radius:9px;color:#7f98b0;font-size:11px;font-weight:800;line-height:1.25;text-align:center}
      .task-correction-step.current{border-color:#37c4e6;color:#9beaff;background:#0b2a3b}
      .task-correction-step.done{border-color:#2c8f77;color:#7ce9c6;background:#0b2925}
      .task-correction-step.error{border-color:#be5368;color:#ffb3c0;background:#321722}
      .task-correction-result{margin-top:11px;color:#b8cbe0;font-size:12px;line-height:1.45}
      .task-correction-result button{padding:0;border:0;background:transparent;color:#65d9f7;font:inherit;font-weight:800;cursor:pointer;text-decoration:underline}
      @media (max-width:720px){
        .task-failure-reason{max-width:190px}
        .task-log-modal-panel{width:calc(100vw - 20px);max-height:88vh;padding:22px 18px}
        .task-client-card{padding:15px}
        .task-client-report{font-size:14px;line-height:1.6}
        .task-correction-head{display:block}
        .task-correction-start{width:100%;margin-top:12px}
        .task-correction-steps{grid-template-columns:repeat(2,minmax(0,1fr))}
      }
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
        <span class="eyebrow">RESULTADO DA ANÁLISE</span>
        <h2 id="task-log-title">Detalhes da execução</h2>
        <p class="task-log-meta" id="task-log-meta"></p>
        <section class="task-client-card" id="task-client-card">
          <span class="eyebrow">PARA O CLIENTE</span>
          <div class="task-client-report" id="task-client-report"></div>
        </section>
        <section class="task-correction-panel" id="task-correction-panel" hidden>
          <div class="task-correction-head">
            <div>
              <span class="eyebrow">PRÓXIMA AÇÃO</span>
              <strong>Aplicar correção baseada nesta análise</strong>
              <p>O DevPilot cria e inicia uma tarefa de correção com o diagnóstico acima, sem duplicar correções ativas.</p>
            </div>
            <button class="primary task-correction-start" id="task-correction-start" type="button">Corrigir automaticamente</button>
          </div>
          <div class="task-correction-tracking" id="task-correction-tracking" hidden aria-live="polite"></div>
        </section>
        <details class="task-technical-details">
          <summary>Ver detalhes técnicos</summary>
          <pre class="task-log-output" id="task-log-output"></pre>
        </details>
      </div>`;
    document.body.appendChild(dialog);
    dialog.querySelector('.task-log-close').onclick = () => dialog.close();
    dialog.addEventListener('close', stopCorrectionTracking);
    dialog.addEventListener('click', event => {
      if (event.target === dialog) dialog.close();
    });
    return dialog;
  }

  function collectMessageText(value, output) {
    if (!value) return;
    if (typeof value === 'string') {
      const text = value.trim();
      if (text) output.push(text);
      return;
    }
    if (Array.isArray(value)) {
      value.forEach(item => collectMessageText(item, output));
      return;
    }
    if (typeof value !== 'object') return;

    const type = String(value.type || '').toLowerCase();
    if (['agent_message', 'assistant_message', 'output_text'].includes(type)) {
      ['text', 'content', 'message', 'output_text'].forEach(key => {
        if (key in value) collectMessageText(value[key], output);
      });
      return;
    }
    ['item', 'message', 'response', 'output'].forEach(key => {
      if (value[key] && typeof value[key] === 'object') collectMessageText(value[key], output);
    });
  }

  function reportFromStdout(stdout) {
    const candidates = [];
    String(stdout || '').split(/\r?\n/).forEach(raw => {
      const line = raw.trim();
      if (!line.startsWith('{')) return;
      try {
        collectMessageText(JSON.parse(line), candidates);
      } catch (_) {
        // Linha técnica que não é JSON válido: permanece apenas nos detalhes técnicos.
      }
    });

    for (let index = candidates.length - 1; index >= 0; index -= 1) {
      const text = candidates[index].trim();
      if (text.length < 40) continue;
      if (/resumo para o cliente|o que encontramos|recomenda[cç][õo]es/i.test(text)) return text;
    }
    return candidates.length ? candidates[candidates.length - 1] : '';
  }

  function clientReport(data) {
    const logs = data?.logs && typeof data.logs === 'object' ? data.logs : {};
    const explicit = typeof logs.client_report === 'string' ? logs.client_report.trim() : '';
    if (explicit) return explicit;

    const extracted = reportFromStdout(logs.stdout || '');
    if (extracted) return extracted;

    const summary = String(data?.summary || '').trim();
    const generic = /read-only analysis completed|execution completed|isolated disposable worktree/i.test(summary);
    if (summary && !generic) return summary;

    if (String(data?.status || '').toLowerCase() === 'success') {
      return 'A análise foi concluída com sucesso. Esta execução foi gerada antes do novo formato de relatório para cliente. Execute uma nova análise para receber o diagnóstico organizado em resumo, impacto, recomendações e próximo passo.';
    }
    return 'A execução não foi concluída. Abra os detalhes técnicos abaixo para identificar a falha e execute novamente após a correção.';
  }

  function cleanHeading(line) {
    return line
      .replace(/^#{1,6}\s*/, '')
      .replace(/^\*\*(.+)\*\*:?$/, '$1')
      .replace(/:$/, '')
      .trim();
  }

  function isHeading(line) {
    const clean = cleanHeading(line).toLowerCase();
    return [
      'resumo para o cliente',
      'o que encontramos',
      'impacto',
      'recomendações',
      'recomendacoes',
      'próximo passo',
      'proximo passo',
    ].includes(clean) || /^#{1,6}\s+/.test(line);
  }

  function renderClientReport(target, value) {
    target.innerHTML = '';
    const lines = String(value || '').replace(/\r/g, '').split('\n');
    let list = null;

    const appendParagraph = text => {
      if (!text.trim()) return;
      const p = document.createElement('p');
      p.textContent = text.trim().replace(/^\*\*(.+)\*\*$/, '$1');
      target.appendChild(p);
    };

    lines.forEach(raw => {
      const line = raw.trim();
      if (!line) {
        list = null;
        return;
      }
      if (isHeading(line)) {
        list = null;
        const heading = document.createElement('h3');
        heading.textContent = cleanHeading(line);
        target.appendChild(heading);
        return;
      }
      if (/^[-*•]\s+/.test(line) || /^\d+[.)]\s+/.test(line)) {
        if (!list) {
          list = document.createElement('ul');
          target.appendChild(list);
        }
        const item = document.createElement('li');
        item.textContent = line.replace(/^[-*•]\s+/, '').replace(/^\d+[.)]\s+/, '');
        list.appendChild(item);
        return;
      }
      list = null;
      appendParagraph(line);
    });

    if (!target.childNodes.length) appendParagraph('Nenhum resumo para o cliente foi registrado.');
  }

  function formatTechnicalLog(data) {
    const parts = [];
    if (data.summary) parts.push(`RESUMO TÉCNICO\n${data.summary}`);
    if (data.logs && (typeof data.logs !== 'object' || Object.keys(data.logs).length)) {
      let logs = data.logs;
      if (logs && typeof logs === 'object') {
        logs = {...logs};
        delete logs.client_report;
      }
      const rendered = typeof logs === 'string' ? logs : JSON.stringify(logs, null, 2);
      parts.push(`LOG BRUTO\n${rendered}`);
    }
    if (data.commit_sha) parts.push(`COMMIT\n${data.commit_sha}`);
    if (data.pull_request_url) parts.push(`PULL REQUEST\n${data.pull_request_url}`);
    return parts.join('\n\n') || 'Nenhum detalhe técnico foi registrado nesta execução.';
  }

  function statusLabel(value) {
    const normalized = String(value || '').toLowerCase();
    if (normalized === 'success') return 'Concluído';
    if (normalized === 'failed') return 'Falhou';
    if (normalized === 'running') return 'Em execução';
    return value || '—';
  }


  function isAnalysisTask(task) {
    const text = `${task?.title || ''}\n${task?.prompt || ''}`.toLowerCase();
    return /an[aá]lise|auditoria|diagn[oó]stico|analysis-read-only/.test(text);
  }

  function taskStatusLabel(value) {
    const normalized = String(value || '').toLowerCase();
    const labels = {
      awaiting_approval: 'Aguardando aprovação de segurança',
      queued: 'Na fila de execução',
      planning: 'Planejando a correção',
      running: 'Correção em andamento',
      review: 'Pronta para revisão',
      completed: 'Concluída',
      failed: 'Falhou',
      blocked: 'Bloqueada',
    };
    return labels[normalized] || value || 'Aguardando atualização';
  }

  function stopCorrectionTracking() {
    if (correctionPollTimer) window.clearInterval(correctionPollTimer);
    correctionPollTimer = null;
    correctionPollInFlight = false;
    trackedCorrection = null;
  }

  function correctionStepState(taskStatus, position) {
    const status = String(taskStatus || '').toLowerCase();
    if (status === 'failed' || status === 'blocked') {
      return position === 3 ? 'error' : 'done';
    }
    if (status === 'awaiting_approval') return position === 0 ? 'current' : '';
    if (status === 'queued') return position === 0 ? 'done' : position === 1 ? 'current' : '';
    if (status === 'planning' || status === 'running') {
      return position < 2 ? 'done' : position === 2 ? 'current' : '';
    }
    if (status === 'review' || status === 'completed') return 'done';
    return '';
  }

  function renderCorrectionTracking(task, detail) {
    const dialog = ensureTaskLogDialog();
    const target = dialog.querySelector('#task-correction-tracking');
    if (!target || !task) return;
    target.hidden = false;
    target.replaceChildren();

    const stateLine = document.createElement('p');
    stateLine.className = 'task-correction-state';
    stateLine.textContent = `Tarefa gerada: ${taskStatusLabel(task.status)}.`;
    target.appendChild(stateLine);

    const steps = document.createElement('div');
    steps.className = 'task-correction-steps';
    ['Tarefa criada', 'Na fila', 'Correção', 'Resultado'].forEach((label, index) => {
      const step = document.createElement('div');
      step.className = `task-correction-step ${correctionStepState(task.status, index)}`.trim();
      step.textContent = label;
      steps.appendChild(step);
    });
    target.appendChild(steps);

    const result = document.createElement('div');
    result.className = 'task-correction-result';
    if (detail?.failure_reason) {
      result.textContent = `Motivo registrado: ${detail.failure_reason}`;
    } else if (detail?.run_id && ['review', 'completed', 'failed', 'blocked'].includes(String(task.status).toLowerCase())) {
      result.append('A execução registrou um resultado. ');
      const open = document.createElement('button');
      open.type = 'button';
      open.textContent = 'Abrir resultado';
      open.onclick = () => openTaskLog(detail.run_id, task);
      result.appendChild(open);
    } else if (task.requires_approval) {
      result.textContent = 'A política identificou uma ação sensível. A tarefa foi criada, mas precisa de aprovação antes de iniciar.';
    } else {
      result.textContent = 'Acompanhe aqui: a atualização é feita apenas enquanto esta janela estiver aberta.';
    }
    target.appendChild(result);
  }

  async function refreshCorrectionTracking() {
    if (!trackedCorrection || correctionPollInFlight) return;
    const dialog = document.getElementById('task-log-modal');
    if (!dialog?.open) {
      stopCorrectionTracking();
      return;
    }

    correctionPollInFlight = true;
    try {
      const [tasks, details] = await Promise.all([
        api('/tasks?limit=100'),
        api('/task-runs/latest?limit=100'),
      ]);
      const task = tasks.find(item => item.id === trackedCorrection.taskId);
      if (!task) return;
      const detail = details.find(item => item.task_id === task.id);
      trackedCorrection.task = task;
      renderCorrectionTracking(task, detail);

      if (!['queued', 'planning', 'running'].includes(String(task.status).toLowerCase())) {
        if (correctionPollTimer) window.clearInterval(correctionPollTimer);
        correctionPollTimer = null;
      }
    } catch (error) {
      const target = dialog.querySelector('#task-correction-tracking');
      if (target) {
        target.hidden = false;
        target.textContent = `Não foi possível atualizar o acompanhamento: ${error.message || 'erro desconhecido'}`;
      }
      if (correctionPollTimer) window.clearInterval(correctionPollTimer);
      correctionPollTimer = null;
    } finally {
      correctionPollInFlight = false;
    }
  }

  function startCorrectionTracking(task) {
    stopCorrectionTracking();
    trackedCorrection = {taskId: task.id, task};
    renderCorrectionTracking(task, null);
    refreshCorrectionTracking();
    if (['queued', 'planning', 'running'].includes(String(task.status).toLowerCase())) {
      correctionPollTimer = window.setInterval(refreshCorrectionTracking, 4000);
    }
  }

  async function createAutomaticCorrection(runId, sourceTask) {
    const dialog = ensureTaskLogDialog();
    const button = dialog.querySelector('#task-correction-start');
    if (!button || button.disabled) return;

    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Gerando correção…';
    try {
      const correction = await api(`/task-runs/${runId}/correction`, {method: 'POST'});
      button.textContent = correction.reused ? 'Correção já em andamento' : 'Correção iniciada';
      startCorrectionTracking(correction);
      toast(correction.reused ? 'A correção já estava em acompanhamento.' : 'Correção criada e encaminhada automaticamente.');
      load();
    } catch (error) {
      button.disabled = false;
      button.textContent = original;
      toast(error.message || 'Não foi possível gerar a correção.');
    }
  }

  function configureCorrectionPanel(runId, task) {
    const dialog = ensureTaskLogDialog();
    const panel = dialog.querySelector('#task-correction-panel');
    const button = dialog.querySelector('#task-correction-start');
    const tracking = dialog.querySelector('#task-correction-tracking');
    if (!panel || !button || !tracking) return;

    panel.hidden = !isAnalysisTask(task);
    tracking.hidden = true;
    tracking.replaceChildren();
    button.disabled = false;
    button.textContent = 'Corrigir automaticamente';
    button.onclick = () => createAutomaticCorrection(runId, task);
  }

  async function openTaskLog(runId, task) {
    const dialog = ensureTaskLogDialog();
    const title = dialog.querySelector('#task-log-title');
    const meta = dialog.querySelector('#task-log-meta');
    const report = dialog.querySelector('#task-client-report');
    const output = dialog.querySelector('#task-log-output');
    const details = dialog.querySelector('.task-technical-details');

    stopCorrectionTracking();
    configureCorrectionPanel(runId, task);
    title.textContent = task?.title || 'Resultado da análise';
    meta.textContent = 'Preparando resultado…';
    report.textContent = 'Carregando análise…';
    output.textContent = '';
    details.open = false;
    if (!dialog.open) dialog.showModal();

    try {
      const data = await api(`/task-runs/${runId}`);
      const started = data.started_at ? new Date(data.started_at).toLocaleString('pt-BR') : '—';
      const failed = String(data.status || '').toLowerCase() === 'failed';
      meta.innerHTML = `<span class="${failed ? 'task-result-failed' : 'task-result-ok'}">${esc(statusLabel(data.status))}</span> · tentativa ${esc(data.attempt || 1)} · início ${esc(started)}`;
      renderClientReport(report, clientReport(data));
      output.textContent = formatTechnicalLog(data);
    } catch (error) {
      meta.textContent = 'Falha ao carregar o resultado';
      renderClientReport(report, error.message || 'Não foi possível consultar esta execução.');
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
            link.textContent = task.status === 'failed' ? 'Ver diagnóstico' : 'Ver análise';
            link.onclick = event => {
              event.preventDefault();
              openTaskLog(detail.run_id, task);
            };
            logTarget.appendChild(link);
          } else if (task.status === 'failed') {
            const unavailable = document.createElement('small');
            unavailable.textContent = 'Sem diagnóstico';
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
      return `<tr data-task-id="${esc(task.id)}"><td><strong>${esc(task.title)}</strong><br><small>${new Date(task.created_at).toLocaleString('pt-BR')}</small></td><td>${esc(task.source)}</td><td><div class="task-status-stack">${status(task.status)}${failure}</div></td><td>${task.priority}</td><td><div class="task-actions">${approval}<span class="task-log-action"></span></div></td></tr>`;
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

