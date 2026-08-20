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
      .task-command-card{margin:0 0 16px;padding:16px;border:1px solid #29445f;border-radius:14px;background:#081522}
      .task-command-header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
      .task-command-header .eyebrow{margin:0;color:#79aee8}
      .task-command-copy{padding:7px 11px;border:1px solid #345b82;border-radius:9px;background:#10283f;color:#dcecff;font:inherit;font-size:11px;font-weight:800;cursor:pointer}
      .task-command-copy:hover{background:#173754}
      .task-command-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(120px,.35fr);gap:10px}
      .task-command-field{min-width:0;padding:10px 12px;border-radius:10px;background:#050d17}
      .task-command-field-wide{grid-column:1/-1}
      .task-command-label{display:block;margin-bottom:5px;color:#7f93aa;font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
      .task-command-value{display:block;color:#e8f2ff;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;line-height:1.45;white-space:pre-wrap;overflow-wrap:anywhere}
      .task-command-exit-ok{color:#61e7ac}
      .task-command-exit-failed{color:#ff9eb0}
      .task-technical-details{margin-top:12px;border:1px solid var(--line,#26364f);border-radius:12px;background:#07111d}
      .task-technical-details>summary{padding:13px 15px;cursor:pointer;color:#9eb1c8;font-weight:800;font-size:12px;user-select:none}
      .task-log-output{margin:0;max-height:48vh;overflow:auto;padding:16px;border-top:1px solid var(--line,#26364f);background:#050c17;color:#c7d5e8;font-size:11px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}
      .task-result-ok{color:#61e7ac;font-weight:800}
      .task-result-failed{color:#ff9eb0;font-weight:800}
      @media (max-width:720px){
        .task-failure-reason{max-width:190px}
        .task-log-modal-panel{width:calc(100vw - 20px);max-height:88vh;padding:22px 18px}
        .task-client-card{padding:15px}
        .task-client-report{font-size:14px;line-height:1.6}
        .task-command-card{padding:14px}
        .task-command-grid{grid-template-columns:1fr}
        .task-command-field-wide{grid-column:auto}
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
        <section class="task-command-card" id="task-command-card" hidden>
          <div class="task-command-header">
            <span class="eyebrow">COMANDO EXECUTADO</span>
            <button class="task-command-copy" type="button">Copiar comando</button>
          </div>
          <div class="task-command-grid" id="task-command-grid"></div>
        </section>
        <details class="task-technical-details">
          <summary>Ver detalhes técnicos</summary>
          <pre class="task-log-output" id="task-log-output"></pre>
        </details>
      </div>`;
    document.body.appendChild(dialog);
    dialog.querySelector('.task-log-close').onclick = () => dialog.close();
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

  function firstCommandValue(sources, keys) {
    for (const source of sources) {
      if (!source || typeof source !== 'object') continue;
      for (const key of keys) {
        const value = source[key];
        if (value !== undefined && value !== null && String(value).trim() !== '') return value;
      }
    }
    return '';
  }

  function commandData(data) {
    const logs = data?.logs && typeof data.logs === 'object' ? data.logs : {};
    const nested = logs.command && typeof logs.command === 'object' ? logs.command : {};
    const sources = [nested, logs, data];
    return {
      command: firstCommandValue(sources, ['command', 'command_text', 'executed_command', 'cmd']),
      cwd: firstCommandValue(sources, ['cwd', 'working_directory', 'workdir']),
      shell: firstCommandValue(sources, ['shell']),
      exitCode: firstCommandValue(sources, ['exit_code', 'return_code', 'returncode']),
      capturedAt: firstCommandValue(sources, ['captured_at', 'executed_at', 'finished_at']),
    };
  }

  function renderCommandData(card, grid, data) {
    const command = commandData(data);
    const entries = [
      ['Comando', command.command, true],
      ['Diretório', command.cwd, true],
      ['Shell', command.shell, false],
      ['Código de saída', command.exitCode, false],
      ['Registrado em', command.capturedAt, true],
    ].filter(([, value]) => value !== '');

    grid.innerHTML = '';
    card.hidden = !entries.length;
    card.dataset.command = command.command ? String(command.command) : '';
    if (!entries.length) return;

    entries.forEach(([label, value, wide]) => {
      const field = document.createElement('div');
      field.className = `task-command-field${wide ? ' task-command-field-wide' : ''}`;
      const fieldLabel = document.createElement('span');
      fieldLabel.className = 'task-command-label';
      fieldLabel.textContent = label;
      const fieldValue = document.createElement('code');
      fieldValue.className = 'task-command-value';
      if (label === 'Código de saída') {
        fieldValue.classList.add(String(value) === '0' ? 'task-command-exit-ok' : 'task-command-exit-failed');
      }
      fieldValue.textContent = String(value);
      field.append(fieldLabel, fieldValue);
      grid.appendChild(field);
    });
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

  async function openTaskLog(runId, task) {
    const dialog = ensureTaskLogDialog();
    const title = dialog.querySelector('#task-log-title');
    const meta = dialog.querySelector('#task-log-meta');
    const report = dialog.querySelector('#task-client-report');
    const output = dialog.querySelector('#task-log-output');
    const commandCard = dialog.querySelector('#task-command-card');
    const commandGrid = dialog.querySelector('#task-command-grid');
    const copyCommand = dialog.querySelector('.task-command-copy');
    const details = dialog.querySelector('.task-technical-details');

    title.textContent = task?.title || 'Resultado da análise';
    meta.textContent = 'Preparando resultado…';
    report.textContent = 'Carregando análise…';
    output.textContent = '';
    commandCard.hidden = true;
    commandGrid.innerHTML = '';
    details.open = false;
    if (!dialog.open) dialog.showModal();

    try {
      const data = await api(`/task-runs/${runId}`);
      const started = data.started_at ? new Date(data.started_at).toLocaleString('pt-BR') : '—';
      const failed = String(data.status || '').toLowerCase() === 'failed';
      meta.innerHTML = `<span class="${failed ? 'task-result-failed' : 'task-result-ok'}">${esc(statusLabel(data.status))}</span> · tentativa ${esc(data.attempt || 1)} · início ${esc(started)}`;
      renderClientReport(report, clientReport(data));
      renderCommandData(commandCard, commandGrid, data);
      copyCommand.onclick = async () => {
        const command = commandCard.dataset.command || '';
        if (!command) return;
        try {
          await navigator.clipboard.writeText(command);
          copyCommand.textContent = 'Copiado';
          window.setTimeout(() => { copyCommand.textContent = 'Copiar comando'; }, 1400);
        } catch (_) {
          toast('Não foi possível copiar o comando');
        }
      };
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
