(() => {
  'use strict';

  const POLL_MS = 4000;
  let timer = null;
  let loading = false;

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
  }[char]));

  const number = value => new Intl.NumberFormat('pt-BR').format(Number(value || 0));

  function formatDate(value) {
    if (!value) return '—';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return esc(value);
    return parsed.toLocaleString('pt-BR', {dateStyle:'short', timeStyle:'medium'});
  }

  function selectedProjectId() {
    const active = document.querySelector('[data-rag-project].active, .rag-project[data-id].active');
    return active?.dataset?.ragProject || active?.dataset?.id || '';
  }

  function selectedProjectName() {
    const active = document.querySelector('[data-rag-project].active, .rag-project[data-id].active');
    return active?.querySelector('strong')?.textContent?.trim() || 'Projeto selecionado';
  }

  function ensureStyles() {
    if (document.getElementById('rag-operational-styles')) return;
    const style = document.createElement('style');
    style.id = 'rag-operational-styles';
    style.textContent = `
      .rag-ops-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px}
      .rag-ops-card{border:1px solid var(--border,#26354a);border-radius:12px;padding:12px;background:rgba(255,255,255,.018);min-width:0}
      .rag-ops-card small{display:block;opacity:.68;margin-bottom:4px}.rag-ops-card strong{display:block;font-size:20px;overflow-wrap:anywhere}
      .rag-ops-status{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;border:1px solid var(--border,#26354a);border-radius:12px;padding:12px;margin-top:10px}
      .rag-ops-status[data-state="ok"]{border-color:#1f9d72}.rag-ops-status[data-state="busy"]{border-color:#38bdf8}.rag-ops-status[data-state="error"]{border-color:#be123c}.rag-ops-status[data-state="empty"]{border-color:#64748b}
      .rag-ops-status strong,.rag-ops-status small{display:block}.rag-ops-status small{opacity:.72;margin-top:3px}
      .rag-ops-project{margin-top:14px;padding-top:14px;border-top:1px solid var(--border,#26354a)}
      .rag-ops-project h4{margin:0 0 4px}.rag-ops-meta{display:flex;gap:12px;flex-wrap:wrap;margin-top:10px;font-size:12px;opacity:.78}
      .rag-job-head{display:flex;align-items:center;justify-content:space-between;gap:10px}.rag-job-state{font-weight:800;letter-spacing:.04em}
      .rag-job-state[data-status="processing"]{color:#38bdf8}.rag-job-state[data-status="completed"]{color:#36d399}.rag-job-state[data-status="failed"]{color:#fb7185}
      .rag-job-progress{width:100%;margin-top:8px}.rag-job-error{display:block;margin-top:8px;white-space:pre-wrap;overflow-wrap:anywhere}
      @media(max-width:900px){.rag-ops-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:560px){.rag-ops-grid{grid-template-columns:1fr}.rag-ops-status{flex-direction:column}.rag-ops-card strong{font-size:18px}}
    `;
    document.head.appendChild(style);
  }

  function ensurePanels() {
    const view = document.getElementById('rag-admin-view');
    if (!view) return;
    ensureStyles();

    if (!document.getElementById('rag-operational-panel')) {
      const panel = document.createElement('article');
      panel.className = 'panel';
      panel.id = 'rag-operational-panel';
      panel.style.marginBottom = '16px';
      panel.innerHTML = `
        <div class="panel-title">
          <div><span class="eyebrow">OPERAÇÃO</span><h3>RAG em tempo real</h3></div>
          <small id="rag-ops-updated">Aguardando dados…</small>
        </div>
        <div id="rag-ops-status" class="rag-ops-status" data-state="empty">
          <div><strong>Carregando operação</strong><small>Consultando métricas e fila.</small></div>
        </div>
        <div class="rag-ops-grid" id="rag-ops-global"></div>
        <div class="rag-ops-project">
          <h4 id="rag-ops-project-title">Projeto selecionado</h4>
          <small>Estado da base de conhecimento deste projeto.</small>
          <div class="rag-ops-grid" id="rag-ops-project-grid"></div>
          <div class="rag-ops-meta" id="rag-ops-project-meta"></div>
        </div>
      `;
      const charts = document.getElementById('rag-charts');
      if (charts?.parentNode) charts.parentNode.insertBefore(panel, charts);
      else view.prepend(panel);
    }

    if (!document.getElementById('rag-jobs-panel')) {
      const panel = document.createElement('article');
      panel.className = 'panel';
      panel.id = 'rag-jobs-panel';
      panel.style.marginTop = '16px';
      panel.innerHTML = `
        <div class="panel-title">
          <div><span class="eyebrow">INDEXAÇÃO</span><h3>Fila RAG</h3></div>
          <button class="ghost" id="rag-jobs-refresh" type="button">Atualizar</button>
        </div>
        <div id="rag-jobs-list" class="rag-list"><div class="rag-empty">Nenhum job carregado.</div></div>
      `;
      view.appendChild(panel);
      panel.querySelector('#rag-jobs-refresh')?.addEventListener('click', () => void loadOperational(true));
    }
  }

  function metricCard(label, value, hint = '') {
    return `<div class="rag-ops-card"><small>${esc(label)}</small><strong>${esc(value)}</strong>${hint ? `<small>${esc(hint)}</small>` : ''}</div>`;
  }

  function operationalState(metrics, jobs) {
    const processing = Number(metrics?.jobs_processing || 0);
    const pending = Number(metrics?.jobs_pending || 0);
    const failed = Number(metrics?.jobs_failed || 0);
    const documents = Number(metrics?.documents || 0);
    if (failed > 0) return {state:'error', title:'Atenção: há falhas de indexação', detail:`${failed} job(s) falharam. Abra a fila para ver o motivo.`};
    if (processing > 0) return {state:'busy', title:'Indexando agora', detail:`${processing} job(s) processando. O painel atualiza automaticamente.`};
    if (pending > 0) return {state:'busy', title:'Na fila para indexação', detail:`${pending} job(s) aguardando o worker RAG.`};
    if (documents > 0) return {state:'ok', title:'Base operacional', detail:`${number(documents)} documento(s) disponíveis para retrieval.`};
    if (jobs.some(job => job.status === 'completed')) return {state:'empty', title:'Indexação concluída sem documentos', detail:'Revise as fontes Git/Documentação do projeto.'};
    return {state:'empty', title:'Base ainda vazia', detail:'Selecione um projeto e use “Indexar agora”.'};
  }

  function renderOperational(globalMetrics, projectMetrics, jobs, errors = []) {
    const globalTarget = document.getElementById('rag-ops-global');
    const projectTarget = document.getElementById('rag-ops-project-grid');
    const metaTarget = document.getElementById('rag-ops-project-meta');
    const statusTarget = document.getElementById('rag-ops-status');
    const updatedTarget = document.getElementById('rag-ops-updated');
    const projectTitle = document.getElementById('rag-ops-project-title');
    if (!globalTarget || !projectTarget || !statusTarget) return;

    const state = operationalState(globalMetrics || {}, jobs || []);
    statusTarget.dataset.state = errors.length ? 'error' : state.state;
    statusTarget.innerHTML = `<div><strong>${esc(errors.length ? 'Carregamento operacional parcial' : state.title)}</strong><small>${esc(errors.length ? errors.join(' · ') : state.detail)}</small></div>`;
    if (updatedTarget) updatedTarget.textContent = `Atualizado ${new Date().toLocaleTimeString('pt-BR')}`;

    globalTarget.innerHTML = [
      metricCard('Documentos indexados', number(globalMetrics?.documents)),
      metricCard('Chunks vetorizados', number(globalMetrics?.chunks)),
      metricCard('Projetos indexados', number(globalMetrics?.indexed_projects)),
      metricCard('Consultas retrieval', number(globalMetrics?.queries_total)),
      metricCard('Na fila', number(globalMetrics?.jobs_pending)),
      metricCard('Indexando', number(globalMetrics?.jobs_processing)),
      metricCard('Concluídos', number(globalMetrics?.jobs_completed)),
      metricCard('Falhas', number(globalMetrics?.jobs_failed)),
    ].join('');

    if (projectTitle) projectTitle.textContent = selectedProjectName();
    if (!selectedProjectId()) {
      projectTarget.innerHTML = '<div class="rag-empty">Selecione um projeto para ver métricas específicas.</div>';
      if (metaTarget) metaTarget.innerHTML = '';
      return;
    }

    projectTarget.innerHTML = [
      metricCard('Documentos', number(projectMetrics?.documents)),
      metricCard('Chunks', number(projectMetrics?.chunks)),
      metricCard('Tokens indexados', number(projectMetrics?.indexed_tokens)),
      metricCard('Trechos recuperados', number(projectMetrics?.chunks_retrieved)),
    ].join('');
    if (metaTarget) metaTarget.innerHTML = `
      <span>Última indexação: <strong>${formatDate(projectMetrics?.last_indexed_at)}</strong></span>
      <span>Última consulta: <strong>${formatDate(projectMetrics?.last_query_at)}</strong></span>
      <span>Tempo médio retrieval: <strong>${Number(projectMetrics?.avg_retrieval_ms || 0).toFixed(1)} ms</strong></span>
    `;
  }

  function percent(job) {
    const total = Number(job.progress_total || 0);
    const done = Number(job.progress_done || 0);
    return total > 0 ? Math.max(0, Math.min(100, Math.round((done / total) * 100))) : 0;
  }

  function statusLabel(status) {
    return ({pending:'NA FILA', processing:'INDEXANDO', completed:'CONCLUÍDO', failed:'FALHOU'})[String(status || '').toLowerCase()] || String(status || '—').toUpperCase();
  }

  function renderJobs(jobs) {
    const target = document.getElementById('rag-jobs-list');
    if (!target) return;
    if (!jobs.length) {
      target.innerHTML = '<div class="rag-empty">Nenhum job de indexação para este projeto.</div>';
      return;
    }
    target.innerHTML = jobs.slice(0, 10).map(job => {
      const progress = percent(job);
      const retry = job.status === 'failed' && Number(job.attempts || 0) < 3
        ? `<button class="ghost" type="button" data-rag-retry="${esc(job.id)}">Tentar novamente</button>` : '';
      const time = job.completed_at || job.started_at || job.created_at;
      return `
        <div class="rag-card">
          <div class="rag-job-head"><span class="rag-job-state" data-status="${esc(job.status)}">${esc(statusLabel(job.status))}</span><small>${formatDate(time)}</small></div>
          <small>${Number(job.progress_done || 0)} / ${Number(job.progress_total || 0)} arquivo(s) · ${progress}% · tentativa ${Number(job.attempts || 0)}/3</small>
          <progress class="rag-job-progress" max="100" value="${progress}"></progress>
          ${job.last_error ? `<small class="rag-job-error">${esc(job.last_error)}</small>` : ''}
          ${retry ? `<div class="rag-actions" style="margin-top:8px">${retry}</div>` : ''}
        </div>`;
    }).join('');

    target.querySelectorAll('[data-rag-retry]').forEach(button => button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        await api(`/super-admin/rag/jobs/${encodeURIComponent(button.dataset.ragRetry)}/retry`, {method:'POST'});
        toast('Job RAG reenfileirado');
        await loadOperational(true);
      } catch (error) {
        toast(error.message);
      } finally {
        button.disabled = false;
      }
    }));
  }

  async function loadOperational(force = false) {
    const view = document.getElementById('rag-admin-view');
    if (!view?.classList.contains('active')) return;
    if (loading && !force) return;
    loading = true;
    ensurePanels();
    const projectId = selectedProjectId();
    const jobsSuffix = projectId ? `?project_id=${encodeURIComponent(projectId)}&limit=20` : '?limit=20';
    const requests = [
      ['metrics', api('/super-admin/rag/metrics')],
      ['jobs', api(`/super-admin/rag/jobs${jobsSuffix}`)],
    ];
    if (projectId) requests.push(['project', api(`/super-admin/rag/projects/${encodeURIComponent(projectId)}/metrics`)]);

    try {
      const settled = await Promise.allSettled(requests.map(item => item[1]));
      const data = {metrics:{}, jobs:[], project:{}};
      const errors = [];
      settled.forEach((result, index) => {
        const key = requests[index][0];
        if (result.status === 'fulfilled') data[key] = result.value || (key === 'jobs' ? [] : {});
        else errors.push(`${key}: ${result.reason?.message || 'indisponível'}`);
      });
      const jobs = Array.isArray(data.jobs) ? data.jobs : [];
      renderOperational(data.metrics || {}, data.project || {}, jobs, errors);
      renderJobs(jobs);
    } finally {
      loading = false;
    }
  }

  function startPolling() {
    if (timer) return;
    timer = window.setInterval(() => void loadOperational(), POLL_MS);
  }

  function init() {
    ensurePanels();
    startPolling();
    document.addEventListener('click', event => {
      if (event.target.closest?.('[data-view="rag-admin"]')) {
        const title = document.getElementById('page-title');
        if (title) title.textContent = 'RAG / Conhecimento';
        window.setTimeout(() => void loadOperational(true), 150);
      }
      if (event.target.closest?.('[data-rag-project], .rag-project[data-id], #rag-index, #rag-retrieve')) {
        window.setTimeout(() => void loadOperational(true), 350);
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
  document.addEventListener('devpilot:dashboard-revealed', init);
  document.addEventListener('devpilot:feature-ready', event => {
    if (event.detail?.feature === 'admin') init();
  });
})();
