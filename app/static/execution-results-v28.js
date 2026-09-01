(() => {
  'use strict';

  if (window.__devpilotExecutionResultsV28) return;
  window.__devpilotExecutionResultsV28 = true;

  const latestCache = { at: 0, value: [] };
  const runCache = new Map();
  const CACHE_MS = 15000;

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));

  function token() {
    return String(localStorage.getItem('devpilot-token') || '');
  }

  async function getJson(path) {
    const response = await fetch(`/api${path}`, {
      headers: { Authorization: `Bearer ${token()}` },
      cache: 'no-store',
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data?.detail === 'string' ? data.detail : 'Falha ao carregar resultado da execução';
      throw new Error(detail);
    }
    return data;
  }

  async function latestRuns(force = false) {
    const now = Date.now();
    if (!force && now - latestCache.at < CACHE_MS && latestCache.value.length) {
      return latestCache.value;
    }
    const value = await getJson('/task-runs/latest?limit=500');
    latestCache.at = now;
    latestCache.value = Array.isArray(value) ? value : [];
    return latestCache.value;
  }

  async function runDetail(runId, force = false) {
    if (!runId) return null;
    if (!force && runCache.has(runId)) return runCache.get(runId);
    const value = await getJson(`/task-runs/${encodeURIComponent(runId)}`);
    runCache.set(runId, value);
    return value;
  }

  function logsObject(run) {
    const logs = run?.logs;
    return logs && typeof logs === 'object' && !Array.isArray(logs) ? logs : {};
  }

  function textValue(value) {
    return typeof value === 'string' ? value.trim() : '';
  }

  function flattenLogs(logs) {
    if (!logs) return '';
    if (typeof logs === 'string') return logs.trim();
    if (typeof logs !== 'object') return String(logs || '').trim();

    const preferred = [
      'result', 'output', 'final', 'final_output', 'answer', 'response',
      'client_report', 'stdout', 'stderr', 'summary', 'message', 'raw',
    ];
    for (const key of preferred) {
      const value = logs[key];
      if (typeof value === 'string' && value.trim()) return value.trim();
    }

    try {
      return JSON.stringify(logs, null, 2);
    } catch (_) {
      return '';
    }
  }

  function isGenericRecoveryText(value) {
    const text = String(value || '').trim().toLowerCase();
    return !text || [
      'a falha ainda não possui uma estratégia automática segura cadastrada.',
      'atenção necessária: a falha ainda não possui uma estratégia automática segura cadastrada.',
      'execution failed',
      'execution completed',
    ].includes(text);
  }

  function failureText(run, latest) {
    const logs = logsObject(run);
    const clientReport = textValue(logs.client_report);
    const stderr = textValue(logs.stderr);
    const raw = textValue(logs.raw);
    const output = textValue(logs.output) || textValue(logs.result) || textValue(logs.final_output);
    const summary = textValue(run?.summary);
    const apiFailure = textValue(run?.failure?.message);
    const latestFailure = textValue(latest?.failure_reason);

    // O worker grava uma resposta contextual por tarefa. Ela é a resposta principal.
    // Erro bruto e autocorreção continuam disponíveis nos detalhes técnicos.
    if (clientReport && !isGenericRecoveryText(clientReport)) return clientReport;
    if (output && !isGenericRecoveryText(output)) return output;
    if (summary && !isGenericRecoveryText(summary)) return summary;
    if (apiFailure && !isGenericRecoveryText(apiFailure)) return apiFailure;
    if (latestFailure && !isGenericRecoveryText(latestFailure)) return latestFailure;
    if (stderr) return stderr;
    if (raw) return raw;
    return apiFailure || latestFailure || summary || 'A execução falhou sem mensagem detalhada.';
  }

  function resultText(run, latest) {
    const status = String(run?.status || latest?.run_status || latest?.task_status || '').toLowerCase();
    if (status === 'failed' || String(latest?.task_status || '').toLowerCase() === 'failed') {
      return failureText(run, latest);
    }

    const logs = logsObject(run);
    const clientReport = textValue(logs.client_report);
    if (clientReport) return clientReport;

    const summary = textValue(run?.summary);
    if (summary) return summary;
    return flattenLogs(run?.logs);
  }

  function technicalText(run, latest) {
    const logs = logsObject(run);
    const pieces = [];
    const status = String(run?.status || latest?.run_status || latest?.task_status || '').toLowerCase();

    if (status === 'failed' || String(latest?.task_status || '').toLowerCase() === 'failed') {
      const original = textValue(logs.stderr) || textValue(logs.raw);
      if (original) pieces.push(`ERRO ORIGINAL\n${original}`);
      const summary = textValue(run?.summary);
      if (summary && summary !== original) pieces.push(`RESUMO DO WORKER\n${summary}`);
      const healing = logs.self_healing;
      if (healing && typeof healing === 'object') {
        try {
          pieces.push(`AUTOCORREÇÃO\n${JSON.stringify(healing, null, 2)}`);
        } catch (_) {
          // Ignora payload não serializável.
        }
      }
      if (pieces.length) return pieces.join('\n\n');
    }

    return resultText(run, latest) || flattenLogs(run?.logs);
  }

  function recommendations(text) {
    const found = [];
    String(text || '').split(/\r?\n/).forEach(raw => {
      const line = raw.trim().replace(/^(?:[-*•]|\d+[.)])\s*/, '');
      const match = line.match(/^(P[0-3])\s*[—–:\-]\s*(.+)$/i);
      if (match) found.push({ priority: match[1].toUpperCase(), title: match[2].trim() });
    });
    const order = { P0: 0, P1: 1, P2: 2, P3: 3 };
    return found
      .filter(item => item.title)
      .sort((a, b) => (order[a.priority] ?? 9) - (order[b.priority] ?? 9))
      .slice(0, 8);
  }

  function trimResult(text, limit = 12000) {
    const value = String(text || '').trim();
    if (value.length <= limit) return value;
    return `${value.slice(0, limit).trim()}\n\n… resultado truncado para exibição.`;
  }

  function resultHtml(taskId, latest, run) {
    const status = String(run?.status || latest?.run_status || latest?.task_status || '').toLowerCase();
    const text = resultText(run, latest);
    const technical = technicalText(run, latest);
    const recs = recommendations(text);
    const failed = status === 'failed' || String(latest?.task_status || '').toLowerCase() === 'failed';

    let main;
    if (failed) {
      const message = failureText(run, latest);
      main = `
        <article class="dp-v28-result-state danger">
          <span>!</span>
          <div><strong>Execução não concluída</strong><p>${esc(message)}</p></div>
        </article>`;
    } else if (text) {
      main = `
        <article class="dp-v28-result-state success">
          <span>✓</span>
          <div><strong>Resultado registrado</strong><p>A execução retornou uma saída real do agente.</p></div>
        </article>`;
    } else if (latest?.run_id) {
      main = `
        <article class="dp-v28-result-state neutral">
          <span>•</span>
          <div><strong>Run sem resumo textual</strong><p>Existe uma execução registrada, mas ela não gravou resumo ou saída textual.</p></div>
        </article>`;
    } else {
      main = `
        <article class="dp-v28-result-state neutral">
          <span>•</span>
          <div><strong>Nenhum Run encontrado</strong><p>Esta execução ainda não possui resultado de worker associado.</p></div>
        </article>`;
    }

    const recHtml = recs.length
      ? `<div class="dp-v28-recs">${recs.map(item => `
          <article><b>${esc(item.priority)}</b><span>${esc(item.title)}</span></article>`).join('')}</div>`
      : '';

    const technicalHtml = technical
      ? `<details class="dp-v28-output">
          <summary>Detalhes técnicos da execução</summary>
          <pre>${esc(trimResult(technical))}</pre>
        </details>`
      : '';

    const links = [
      run?.commit_sha ? `<span><small>Commit</small><code>${esc(run.commit_sha)}</code></span>` : '',
      run?.pull_request_url ? `<a href="${esc(run.pull_request_url)}" target="_blank" rel="noopener noreferrer">Abrir Pull Request</a>` : '',
    ].filter(Boolean).join('');

    return `
      <section class="dp-v28-result" data-execution-result-for="${esc(taskId)}" data-run-id="${esc(latest?.run_id || '')}">
        <header>
          <div><small>RESULTADO DA EXECUÇÃO</small><h3>O que esta execução respondeu</h3></div>
          <span class="dp-v28-run">${esc(run?.status || latest?.run_status || 'sem run')}</span>
        </header>
        ${main}
        ${recHtml}
        ${technicalHtml}
        ${links ? `<footer>${links}</footer>` : ''}
      </section>`;
  }

  function injectStyle() {
    if (document.getElementById('devpilot-execution-results-v28-style')) return;
    const style = document.createElement('style');
    style.id = 'devpilot-execution-results-v28-style';
    style.textContent = `
      .dp-v28-result{display:grid;gap:12px;width:100%;box-sizing:border-box;padding:14px;border:1px solid rgba(53,229,209,.28);border-radius:14px;background:linear-gradient(145deg,rgba(3,28,31,.95),rgba(5,15,26,.98))}
      .dp-v28-result>header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.dp-v28-result>header small{display:block;color:#58dfcb;font-size:9px;font-weight:900;letter-spacing:.1em}.dp-v28-result>header h3{margin:4px 0 0;font-size:22px;line-height:1.1}.dp-v28-run{padding:5px 8px;border-radius:999px;background:rgba(53,229,209,.08);color:#78e4d4;font-size:10px;font-weight:850;text-transform:uppercase}
      .dp-v28-result-state{display:grid;grid-template-columns:42px minmax(0,1fr);gap:10px;padding:11px;border:1px solid rgba(255,255,255,.07);border-radius:11px;background:rgba(2,11,19,.72)}.dp-v28-result-state>span{display:grid;place-items:center;width:36px;height:36px;border-radius:10px;background:rgba(53,229,209,.1);color:#70e4d3;font-weight:900}.dp-v28-result-state.danger>span{background:rgba(255,100,100,.12);color:#ff9292}.dp-v28-result-state strong{display:block;font-size:14px}.dp-v28-result-state p{margin:4px 0 0;color:#9fb2bc;font-size:12px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}
      .dp-v28-recs{display:grid;gap:7px}.dp-v28-recs article{display:grid;grid-template-columns:42px minmax(0,1fr);gap:9px;align-items:start;padding:10px;border-radius:10px;background:rgba(255,255,255,.025)}.dp-v28-recs b{display:grid;place-items:center;min-height:30px;border-radius:8px;background:rgba(53,229,209,.08);color:#6fe2d1;font-size:11px}.dp-v28-recs span{font-size:13px;line-height:1.45}
      .dp-v28-output{border-top:1px solid rgba(255,255,255,.07);padding-top:9px}.dp-v28-output summary{cursor:pointer;color:#8fa6b1;font-size:11px;font-weight:800}.dp-v28-output pre{max-height:360px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;margin:9px 0 0;padding:11px;border-radius:9px;background:#06111b;color:#b8c8cf;font-size:12px;line-height:1.55}
      .dp-v28-result footer{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.dp-v28-result footer span{display:grid;gap:2px}.dp-v28-result footer small{color:#718998;font-size:9px}.dp-v28-result footer code{font-size:10px}.dp-v28-result footer a{color:#70e4d3;font-size:11px;font-weight:800}
      @media(max-width:900px){.dp-v28-result{padding:12px}.dp-v28-result>header h3{font-size:20px}.dp-v28-output pre{max-height:420px;font-size:13px}.dp-v28-result-state p,.dp-v28-recs span{font-size:13px}}
    `;
    document.head.appendChild(style);
  }

  async function enrich(taskId, force = false) {
    const panel = document.querySelector(`[data-task-details="${CSS.escape(taskId)}"]`);
    if (!panel || panel.dataset.v28Loading === '1') return;

    panel.dataset.v28Loading = '1';
    try {
      const latest = (await latestRuns(force)).find(item => String(item.task_id) === String(taskId));
      const existing = panel.querySelector(`[data-execution-result-for="${CSS.escape(taskId)}"]`);
      const expectedRunId = String(latest?.run_id || '');
      if (!force && existing && String(existing.dataset.runId || '') === expectedRunId) return;

      const run = latest?.run_id ? await runDetail(latest.run_id, force) : null;
      const oldDecision = panel.querySelector('.dp-v13-decision');
      const wrapper = document.createElement('div');
      wrapper.innerHTML = resultHtml(taskId, latest || {}, run || {});
      const result = wrapper.firstElementChild;
      if (!result) return;
      if (existing) existing.replaceWith(result);
      else if (oldDecision) oldDecision.replaceWith(result);
      else panel.prepend(result);
      panel.dataset.v28Loaded = '1';
    } catch (error) {
      const oldDecision = panel.querySelector('.dp-v13-decision');
      if (oldDecision) {
        oldDecision.innerHTML = `<div class="tasks-v9-detail-error">${esc(error?.message || 'Não foi possível carregar o resultado da execução.')}</div>`;
      }
    } finally {
      delete panel.dataset.v28Loading;
    }
  }

  function schedule(taskId) {
    if (!taskId) return;
    [0, 80, 220, 500].forEach((delay, index) => {
      window.setTimeout(() => void enrich(taskId, index === 3), delay);
    });
  }

  document.addEventListener('click', event => {
    const button = event.target.closest?.('.tasks-v9-details[data-id], .task-instructions-load[data-id]');
    if (!button) return;
    schedule(String(button.dataset.id || ''));
  }, true);

  document.addEventListener('devpilot:tasks-rendered', () => {
    latestCache.at = 0;
    document.querySelectorAll('.task-details-row:not([hidden]) [data-task-details]').forEach(panel => {
      schedule(String(panel.dataset.taskDetails || ''));
    });
  });

  injectStyle();
  console.info('[DevPilot] Execution Results V28 ativo · resposta contextual por run');
})();
