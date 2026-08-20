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
      .task-technical-details{margin-top:12px;border:1px solid var(--line,#26364f);border-radius:12px;background:#07111d}
      .task-technical-details>summary{padding:13px 15px;cursor:pointer;color:#9eb1c8;font-weight:800;font-size:12px;user-select:none}
      .task-log-output{margin:0;max-height:48vh;overflow:auto;padding:16px;border-top:1px solid var(--line,#26364f);background:#050c17;color:#c7d5e8;font-size:11px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}
      .task-result-ok{color:#61e7ac;font-weight:800}
      .task-result-failed{color:#ff9eb0;font-weight:800}
      .task-log-modal-panel{width:min(1180px,calc(100vw - 32px))}
      .task-result-layout{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(340px,.92fr);gap:16px;align-items:start}
      .task-client-card{margin:0;min-width:0;max-height:68vh;overflow:auto}
      .task-proposal-card{min-width:0;padding:18px;border:1px solid #345b78;border-radius:14px;background:linear-gradient(145deg,#0d1d2e,#091522);position:sticky;top:0}
      .task-proposal-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px}
      .task-proposal-head h3{margin:3px 0 0;font-size:18px}
      .task-review-badge{padding:5px 8px;border:1px solid #2b7b70;border-radius:999px;color:#65ead4;background:#12342f;font-size:9px;font-weight:850;white-space:nowrap}
      .task-price-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:14px}
      .task-price-item{padding:11px;border:1px solid #253e57;border-radius:10px;background:#081421}
      .task-price-item span{display:block;color:#8da3bc;font-size:9px;text-transform:uppercase;letter-spacing:.08em}
      .task-price-item strong{display:block;margin-top:5px;color:#edf8ff;font-size:15px;overflow-wrap:anywhere}
      .task-price-item.featured{border-color:#2e8f80;background:linear-gradient(145deg,#10332e,#0a2024)}
      .task-price-item.featured strong{color:#63edd7}
      .task-proposal-meta{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
      .task-proposal-meta span{padding:6px 8px;border-radius:8px;background:#102337;color:#a9bfd5;font-size:10px}
      .task-proposal-phases{display:grid;gap:8px}
      .task-proposal-phase{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:9px;align-items:start;padding:10px;border-top:1px solid #22384e}
      .task-proposal-phase b{display:grid;place-items:center;width:26px;height:26px;border-radius:8px;background:#164b4b;color:#62ead7;font-size:11px}
      .task-proposal-phase strong,.task-proposal-phase small{display:block}
      .task-proposal-phase small{margin-top:3px;color:#849bb4;line-height:1.35}
      .task-proposal-phase>strong{color:#dceafa;font-size:11px;white-space:nowrap}
      .task-proposal-note{margin:13px 0 0;color:#7890aa;font-size:10px;line-height:1.45}
      .task-proposal-actions{display:flex;justify-content:flex-end;margin-top:12px}
      .task-proposal-print{padding:8px 11px;font-size:11px}
      @media (max-width:900px){
        .task-result-layout{grid-template-columns:1fr}
        .task-client-card{max-height:none;overflow:visible}
        .task-proposal-card{position:static}
      }
      @media (max-width:720px){
        .task-failure-reason{max-width:190px}
        .task-log-modal-panel{width:calc(100vw - 20px);max-height:88vh;padding:22px 18px}
        .task-client-card{padding:15px}
        .task-client-report{font-size:14px;line-height:1.6}
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
        <div class="task-result-layout">
          <section class="task-client-card" id="task-client-card">
            <span class="eyebrow">ANÁLISE DE IA · GERADA E REVISADA</span>
            <div class="task-client-report" id="task-client-report"></div>
          </section>
          <aside class="task-proposal-card" id="task-proposal-card" aria-label="Proposta comercial">
            <div class="task-proposal-head">
              <div><span class="eyebrow">PROPOSTA COMERCIAL</span><h3>Investimento recomendado</h3></div>
              <span class="task-review-badge">REVISÃO AUTOMÁTICA</span>
            </div>
            <div id="task-proposal-content">Aguardando dados da análise…</div>
          </aside>
        </div>
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

  function formatMoney(value) {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
      maximumFractionDigits: 0,
    }).format(Math.max(0, Math.round(value)));
  }

  function commercialEstimate(reportText) {
    const text = String(reportText || '');
    const lines = text.replace(/\r/g, '').split('\n');
    const rangePattern = /(\d{1,4})\s*(?:–|—|-)\s*(\d{1,4})\s*h\b/i;
    const totalLine = lines.find(line => /\btotal\b/i.test(line) && rangePattern.test(line));
    const ranges = [];

    if (totalLine) {
      const match = totalLine.match(rangePattern);
      ranges.push([Number(match[1]), Number(match[2])]);
    } else {
      const seen = new Set();
      lines.forEach(line => {
        const match = line.match(rangePattern);
        if (!match) return;
        const key = match[0].replace(/\s/g, '').toLowerCase();
        if (seen.has(key) || ranges.length >= 8) return;
        seen.add(key);
        ranges.push([Number(match[1]), Number(match[2])]);
      });
    }

    let minHours;
    let maxHours;
    if (ranges.length) {
      minHours = ranges.reduce((sum, range) => sum + Math.min(...range), 0);
      maxHours = ranges.reduce((sum, range) => sum + Math.max(...range), 0);
    } else {
      const count = expression => (text.match(expression) || []).length;
      const critical = count(/\bcr[ií]tic[oa]s?\b/gi);
      const high = count(/\balto?s?\b|\balta?s?\b/gi);
      const medium = count(/\bm[eé]di[oa]s?\b/gi);
      const low = count(/\bbaixo?s?\b|\bbaixa?s?\b/gi);
      minHours = 24 + critical * 28 + high * 18 + medium * 10 + low * 5;
      maxHours = 44 + critical * 52 + high * 34 + medium * 20 + low * 10;
    }

    minHours = Math.max(32, Math.min(600, minHours));
    maxHours = Math.max(minHours, Math.min(900, maxHours));
    const hourlyMin = 180;
    const hourlyMax = 280;
    const minimum = minHours * hourlyMin;
    const maximum = maxHours * hourlyMax;
    const average = Math.round(((minimum + maximum) / 2) / 100) * 100;

    const scope = lines
      .filter(line => /^\s*[-*•]\s+/.test(line))
      .map(line => line.replace(/^\s*[-*•]\s+/, '').replace(/\*\*/g, '').trim())
      .filter(Boolean)
      .slice(0, 3);

    return {minHours, maxHours, hourlyMin, hourlyMax, minimum, maximum, average, scope};
  }

  function renderCommercialProposal(target, reportText) {
    const estimate = commercialEstimate(reportText);
    const defaultScopes = [
      'Correção dos riscos críticos e estabilização da operação',
      'Implementação das melhorias priorizadas na análise',
      'Testes, validação técnica e entrega assistida',
    ];
    const scopes = defaultScopes.map((fallback, index) => estimate.scope[index] || fallback);
    const phases = [
      ['01', 'Estabilização', scopes[0], .45],
      ['02', 'Evolução', scopes[1], .35],
      ['03', 'Validação', scopes[2], .20],
    ];

    target.innerHTML = `
      <div class="task-price-summary">
        <div class="task-price-item"><span>Faixa mínima</span><strong>${formatMoney(estimate.minimum)}</strong></div>
        <div class="task-price-item featured"><span>Valor médio</span><strong>${formatMoney(estimate.average)}</strong></div>
        <div class="task-price-item"><span>Faixa máxima</span><strong>${formatMoney(estimate.maximum)}</strong></div>
      </div>
      <div class="task-proposal-meta">
        <span>${estimate.minHours}–${estimate.maxHours} horas</span>
        <span>${formatMoney(estimate.hourlyMin)}–${formatMoney(estimate.hourlyMax)}/h</span>
        <span>3 fases de entrega</span>
      </div>
      <div class="task-proposal-phases">
        ${phases.map(([number, title, scope, share]) => `
          <div class="task-proposal-phase">
            <b>${number}</b>
            <div><strong>${esc(title)}</strong><small>${esc(scope.slice(0, 120))}</small></div>
            <strong>${formatMoney(estimate.average * share)}</strong>
          </div>
        `).join('')}
      </div>
      <p class="task-proposal-note">Estimativa produzida a partir das horas, criticidade e escopo encontrados na análise. Revise premissas e detalhes contratuais antes de enviar ao cliente.</p>
      <div class="task-proposal-actions"><button type="button" class="ghost task-proposal-print">Imprimir proposta</button></div>
    `;
    target.querySelector('.task-proposal-print').onclick = () => window.print();
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
    const proposal = dialog.querySelector('#task-proposal-content');
    const output = dialog.querySelector('#task-log-output');
    const details = dialog.querySelector('.task-technical-details');

    title.textContent = task?.title || 'Resultado da análise';
    meta.textContent = 'Preparando resultado…';
    report.textContent = 'Carregando análise…';
    proposal.textContent = 'Calculando proposta a partir da análise…';
    output.textContent = '';
    details.open = false;
    if (!dialog.open) dialog.showModal();

    try {
      const data = await api(`/task-runs/${runId}`);
      const started = data.started_at ? new Date(data.started_at).toLocaleString('pt-BR') : '—';
      const failed = String(data.status || '').toLowerCase() === 'failed';
      meta.innerHTML = `<span class="${failed ? 'task-result-failed' : 'task-result-ok'}">${esc(statusLabel(data.status))}</span> · tentativa ${esc(data.attempt || 1)} · início ${esc(started)}`;
      const reportText = clientReport(data);
      renderClientReport(report, reportText);
      renderCommercialProposal(proposal, reportText);
      output.textContent = formatTechnicalLog(data);
    } catch (error) {
      meta.textContent = 'Falha ao carregar o resultado';
      const message = error.message || 'Não foi possível consultar esta execução.';
      renderClientReport(report, message);
      proposal.textContent = 'Proposta indisponível até que a análise seja carregada.';
      output.textContent = message;
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
