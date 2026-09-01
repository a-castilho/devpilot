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

  async function latestRuns() {
    const now = Date.now();
    if (now - latestCache.at < CACHE_MS && latestCache.value.length) {
      return latestCache.value;
    }
    const value = await getJson('/task-runs/latest?limit=500');
    latestCache.at = now;
    latestCache.value = Array.isArray(value) ? value : [];
    return latestCache.value;
  }

  async function runDetail(runId) {
    if (!runId) return null;
    if (runCache.has(runId)) return runCache.get(runId);
    const value = await getJson(`/task-runs/${encodeURIComponent(runId)}`);
    runCache.set(runId, value);
    return value;
  }

  function flattenLogs(logs) {
    if (!logs) return '';
    if (typeof logs === 'string') return logs.trim();
    if (typeof logs !== 'object') return String(logs || '').trim();

    const preferred = [
      'client_report', 'result', 'output', 'final', 'final_output', 'answer', 'response',
      'summary', 'stdout', 'message', 'raw', 'stderr',
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

  function resultText(run) {
    const report = typeof run?.logs?.client_report === 'string' ? run.logs.client_report.trim() : '';
    if (report) return report;
    const summary = String(run?.summary || '').trim();
    if (summary) return summary;
    return flattenLogs(run?.logs);
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
    return `${value.slice(0, limit).trim()}\n\n… saída técnica truncada para exibição.`;
  }

  function statusLabel(value) {
    const status = String(value || '').trim().toLowerCase();
    return ({
      success: 'Concluída',
      completed: 'Concluída',
      failed: 'Falhou',
      blocked: 'Bloqueada',
      running: 'Executando',
      queued: 'Na fila',
      pending: 'Pendente',
    })[status] || value || 'Sem run';
  }

  function fallbackContract(latest, run) {
    const status = String(run?.status || latest?.run_status || latest?.task_status || '').toLowerCase();
    const failure = run?.failure || {};
    const healing = run?.logs?.self_healing || {};
    const kind = String(latest?.task_kind || 'execution');
    const kindLabel = String(latest?.task_kind_label || ({analysis:'Análise',verification:'Validação',recovery:'Recuperação'})[kind] || 'Execução');
    if (status === 'success') {
      return {
        kind,
        kind_label: kindLabel,
        state: 'completed',
        headline: `${kindLabel} concluída`,
        message: 'O run terminou com sucesso e registrou uma saída operacional.',
        next_action: 'Confirme as evidências e o resultado funcional antes de encerrar a missão.',
        evidence: [],
      };
    }
    if (String(healing?.status || '').toLowerCase() === 'resolved') {
      return {
        kind,
        kind_label: kindLabel,
        state: 'retest_required',
        headline: 'Correção aplicada · reteste pendente',
        message: 'A causa detectada foi corrigida, mas esta execução ainda não comprovou o objetivo original.',
        next_action: 'Reteste a execução original. Não trate a autocorreção isolada como entrega concluída.',
        evidence: Array.isArray(healing?.steps) ? healing.steps.slice(-6) : [],
      };
    }
    return {
      kind,
      kind_label: kindLabel,
      state: failure?.requires_authorization ? 'blocked_authorization' : 'failed',
      headline: failure?.requires_authorization ? `${kindLabel} bloqueada por autorização` : `${kindLabel} falhou`,
      message: String(failure?.message || latest?.failure_reason || 'Falha registrada sem mensagem detalhada.'),
      next_action: failure?.requires_authorization
        ? 'Conclua a autorização indicada e retome a mesma missão.'
        : 'Use o protocolo de recuperação, remova a causa raiz e reteste o objetivo original.',
      evidence: [],
    };
  }

  function contractFor(latest, run) {
    const contract = run?.result_contract;
    if (contract && typeof contract === 'object') return contract;
    return fallbackContract(latest, run);
  }

  function stateTone(state) {
    if (state === 'completed') return 'success';
    if (state === 'retest_required') return 'warning';
    if (state === 'blocked_authorization') return 'blocked';
    if (state === 'failed') return 'danger';
    return 'neutral';
  }

  function stateIcon(state) {
    if (state === 'completed') return '✓';
    if (state === 'retest_required') return '↻';
    if (state === 'blocked_authorization') return '🔒';
    if (state === 'failed') return '!';
    return '•';
  }

  function evidenceHtml(contract) {
    const evidence = Array.isArray(contract?.evidence) ? contract.evidence.filter(item => item?.message) : [];
    if (!evidence.length) return '';
    return `
      <section class="dp-v28-product-block dp-v28-evidence">
        <div class="dp-v28-block-title"><small>EVIDÊNCIAS</small><strong>O que foi comprovado</strong></div>
        <div class="dp-v28-evidence-list">${evidence.map(item => `
          <article>
            <span>${esc(String(item.state || 'evidência').replaceAll('_', ' '))}</span>
            <p>${esc(item.message)}</p>
          </article>`).join('')}</div>
      </section>`;
  }

  function resultHtml(taskId, latest, run) {
    const contract = contractFor(latest, run);
    const text = resultText(run);
    const recs = recommendations(text);
    const tone = stateTone(contract.state);
    const kindLabel = String(contract.kind_label || latest?.task_kind_label || 'Execução');

    const main = `
      <article class="dp-v28-result-state ${tone}">
        <span>${stateIcon(contract.state)}</span>
        <div>
          <small>${esc(kindLabel.toUpperCase())}</small>
          <strong>${esc(contract.headline || 'Resultado registrado')}</strong>
          <p>${esc(contract.message || 'Sem mensagem de resultado.')}</p>
        </div>
      </article>`;

    const nextAction = contract.next_action
      ? `<section class="dp-v28-product-block dp-v28-next">
          <div class="dp-v28-block-title"><small>PRÓXIMO PASSO</small><strong>O que acontece agora</strong></div>
          <p>${esc(contract.next_action)}</p>
        </section>`
      : '';

    const recHtml = recs.length
      ? `<section class="dp-v28-product-block dp-v28-recommendations">
          <div class="dp-v28-block-title"><small>RECOMENDAÇÕES</small><strong>Itens extraídos da saída</strong></div>
          <div class="dp-v28-recs">${recs.map(item => `
            <article><b>${esc(item.priority)}</b><span>${esc(item.title)}</span></article>`).join('')}</div>
        </section>`
      : '';

    const technical = text
      ? `<details class="dp-v28-output">
          <summary>Saída técnica (auditoria)</summary>
          <p class="dp-v28-output-help">Registro bruto para diagnóstico. Não use esta seção isoladamente como estado final do produto.</p>
          <pre>${esc(trimResult(text))}</pre>
        </details>`
      : '';

    const links = [
      run?.commit_sha ? `<span><small>Commit</small><code>${esc(run.commit_sha)}</code></span>` : '',
      run?.pull_request_url ? `<a href="${esc(run.pull_request_url)}" target="_blank" rel="noopener noreferrer">Abrir Pull Request ↗</a>` : '',
    ].filter(Boolean).join('');

    return `
      <section class="dp-v28-result dp-v45-product-result" data-execution-result-for="${esc(taskId)}" data-result-state="${esc(contract.state || 'pending')}" data-result-kind="${esc(contract.kind || 'execution')}">
        <header>
          <div>
            <small>${esc(kindLabel.toUpperCase())} · PRODUTO DA MISSÃO</small>
            <h3>${esc(contract.headline || 'Resultado da missão')}</h3>
          </div>
          <span class="dp-v28-run ${esc(tone)}">${esc(statusLabel(run?.status || latest?.run_status || 'sem run'))}</span>
        </header>
        ${main}
        ${nextAction}
        ${evidenceHtml(contract)}
        ${recHtml}
        ${technical}
        ${links ? `<footer>${links}</footer>` : ''}
      </section>`;
  }

  function injectStyle() {
    if (document.getElementById('devpilot-execution-results-v28-style')) return;
    const style = document.createElement('style');
    style.id = 'devpilot-execution-results-v28-style';
    style.textContent = `
      .dp-v28-result{display:grid;gap:13px;width:100%;box-sizing:border-box;padding:15px;border:1px solid rgba(53,229,209,.28);border-radius:16px;background:linear-gradient(145deg,rgba(3,28,31,.96),rgba(5,15,26,.99));box-shadow:inset 0 0 0 1px rgba(255,255,255,.015)}
      .dp-v28-result[data-result-state="retest_required"]{border-color:rgba(255,194,92,.36)}
      .dp-v28-result[data-result-state="failed"]{border-color:rgba(255,100,120,.34)}
      .dp-v28-result[data-result-state="blocked_authorization"]{border-color:rgba(174,126,255,.34)}
      .dp-v28-result>header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,.07)}
      .dp-v28-result>header small{display:block;color:#58dfcb;font-size:9px;font-weight:900;letter-spacing:.12em}.dp-v28-result>header h3{margin:4px 0 0;font-size:22px;line-height:1.12}.dp-v28-run{padding:5px 9px;border-radius:999px;background:rgba(53,229,209,.08);color:#78e4d4;font-size:10px;font-weight:850;text-transform:uppercase;white-space:nowrap}.dp-v28-run.warning{color:#ffd27d;background:rgba(255,194,92,.11)}.dp-v28-run.danger{color:#ff9aa9;background:rgba(255,100,120,.11)}.dp-v28-run.blocked{color:#c5a7ff;background:rgba(174,126,255,.11)}
      .dp-v28-result-state{display:grid;grid-template-columns:42px minmax(0,1fr);gap:11px;padding:12px;border:1px solid rgba(255,255,255,.07);border-radius:12px;background:rgba(2,11,19,.72)}.dp-v28-result-state>span{display:grid;place-items:center;width:36px;height:36px;border-radius:10px;background:rgba(53,229,209,.1);color:#70e4d3;font-weight:900}.dp-v28-result-state.danger>span{background:rgba(255,100,100,.12);color:#ff9292}.dp-v28-result-state.warning>span{background:rgba(255,194,92,.12);color:#ffd27d}.dp-v28-result-state.blocked>span{background:rgba(174,126,255,.12);color:#c5a7ff}.dp-v28-result-state small{display:block;margin-bottom:3px;color:#6e8995;font-size:9px;font-weight:900;letter-spacing:.1em}.dp-v28-result-state strong{display:block;font-size:15px}.dp-v28-result-state p{margin:5px 0 0;color:#a9bac2;font-size:12px;line-height:1.55}
      .dp-v28-product-block{display:grid;gap:9px;padding:12px;border:1px solid rgba(255,255,255,.065);border-radius:12px;background:rgba(255,255,255,.018)}.dp-v28-block-title small{display:block;color:#6e8995;font-size:9px;font-weight:900;letter-spacing:.1em}.dp-v28-block-title strong{display:block;margin-top:2px;font-size:13px}.dp-v28-next p{margin:0;color:#c1d1d7;font-size:13px;line-height:1.55}
      .dp-v28-evidence-list{display:grid;gap:7px}.dp-v28-evidence-list article{display:grid;grid-template-columns:minmax(90px,130px) minmax(0,1fr);gap:9px;align-items:start;padding:9px 10px;border-radius:9px;background:rgba(2,11,19,.65)}.dp-v28-evidence-list span{color:#71e3d2;font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:.06em}.dp-v28-evidence-list p{margin:0;color:#aebfc7;font-size:12px;line-height:1.45}
      .dp-v28-recs{display:grid;gap:7px}.dp-v28-recs article{display:grid;grid-template-columns:42px minmax(0,1fr);gap:9px;align-items:start;padding:10px;border-radius:10px;background:rgba(2,11,19,.58)}.dp-v28-recs b{display:grid;place-items:center;min-height:30px;border-radius:8px;background:rgba(53,229,209,.08);color:#6fe2d1;font-size:11px}.dp-v28-recs span{font-size:13px;line-height:1.45}
      .dp-v28-output{border-top:1px solid rgba(255,255,255,.07);padding-top:10px}.dp-v28-output summary{cursor:pointer;color:#8fa6b1;font-size:11px;font-weight:800}.dp-v28-output-help{margin:7px 0 0;color:#667e8b;font-size:10px;line-height:1.4}.dp-v28-output pre{max-height:360px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;margin:9px 0 0;padding:11px;border-radius:9px;background:#06111b;color:#b8c8cf;font-size:12px;line-height:1.55}
      .dp-v28-result footer{display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding-top:2px}.dp-v28-result footer span{display:grid;gap:2px}.dp-v28-result footer small{color:#718998;font-size:9px}.dp-v28-result footer code{font-size:10px}.dp-v28-result footer a{color:#70e4d3;font-size:11px;font-weight:800}
      @media(max-width:900px){.dp-v28-result{padding:12px}.dp-v28-result>header h3{font-size:19px}.dp-v28-output pre{max-height:420px;font-size:12px}.dp-v28-result-state p,.dp-v28-recs span,.dp-v28-next p{font-size:13px}.dp-v28-evidence-list article{grid-template-columns:1fr}.dp-v28-evidence-list span{margin-bottom:-3px}}
    `;
    document.head.appendChild(style);
  }

  async function enrich(taskId) {
    const panel = document.querySelector(`[data-task-details="${CSS.escape(taskId)}"]`);
    if (!panel || panel.dataset.v28Loading === '1') return;

    panel.dataset.v28Loading = '1';
    try {
      const latest = (await latestRuns()).find(item => String(item.task_id) === String(taskId));
      const run = latest?.run_id ? await runDetail(latest.run_id) : null;
      const current = panel.querySelector(`[data-execution-result-for="${CSS.escape(taskId)}"]`);
      const oldDecision = panel.querySelector('.dp-v13-decision');
      const wrapper = document.createElement('div');
      wrapper.innerHTML = resultHtml(taskId, latest || {}, run || {});
      const result = wrapper.firstElementChild;
      if (!result) return;
      if (current) current.replaceWith(result);
      else if (oldDecision) oldDecision.replaceWith(result);
      else panel.prepend(result);
      panel.dataset.v28Loaded = '1';
    } catch (error) {
      const oldDecision = panel.querySelector('.dp-v13-decision');
      if (oldDecision) {
        oldDecision.innerHTML = `<div class="tasks-v9-detail-error">${esc(error?.message || 'Não foi possível carregar o resultado da missão.')}</div>`;
      }
    } finally {
      delete panel.dataset.v28Loading;
    }
  }

  function schedule(taskId) {
    if (!taskId) return;
    [0, 80, 220, 500].forEach(delay => {
      window.setTimeout(() => void enrich(taskId), delay);
    });
  }

  document.addEventListener('click', event => {
    const button = event.target.closest?.('.tasks-v9-details[data-id], .task-instructions-load[data-id]');
    if (!button) return;
    schedule(String(button.dataset.id || ''));
  }, true);

  document.addEventListener('devpilot:tasks-rendered', () => {
    document.querySelectorAll('.task-details-row:not([hidden]) [data-task-details]').forEach(panel => {
      schedule(String(panel.dataset.taskDetails || ''));
    });
  });

  injectStyle();
  console.info('[DevPilot] Execution Results V45 produto operacional ativo');
})();
