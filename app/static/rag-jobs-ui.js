(() => {
  'use strict';

  const POLL_MS = 2500;
  let timer = null;

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
  }[char]));

  function selectedProjectId() {
    const active = document.querySelector('[data-rag-project].active, [data-id].active');
    return active?.dataset?.ragProject || active?.dataset?.id || '';
  }

  function ensureJobsPanel() {
    const view = document.getElementById('rag-admin-view');
    if (!view || document.getElementById('rag-jobs-panel')) return;
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
    panel.querySelector('#rag-jobs-refresh')?.addEventListener('click', () => void loadJobs());
  }

  function percent(job) {
    const total = Number(job.progress_total || 0);
    const done = Number(job.progress_done || 0);
    return total > 0 ? Math.max(0, Math.min(100, Math.round((done / total) * 100))) : 0;
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
      return `
        <div class="rag-card">
          <div class="list-row"><strong>${esc(String(job.status || '').toUpperCase())}</strong><small>${esc(job.id)}</small></div>
          <small>${Number(job.progress_done || 0)} / ${Number(job.progress_total || 0)} arquivo(s) · ${progress}% · tentativa ${Number(job.attempts || 0)}/3</small>
          <progress max="100" value="${progress}" style="width:100%;margin-top:8px"></progress>
          ${job.last_error ? `<small style="display:block;margin-top:8px">${esc(job.last_error)}</small>` : ''}
          ${retry ? `<div class="rag-actions" style="margin-top:8px">${retry}</div>` : ''}
        </div>`;
    }).join('');

    target.querySelectorAll('[data-rag-retry]').forEach(button => button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        await api(`/super-admin/rag/jobs/${encodeURIComponent(button.dataset.ragRetry)}/retry`, {method:'POST'});
        toast('Job RAG reenfileirado');
        await loadJobs();
      } catch (error) {
        toast(error.message);
      } finally {
        button.disabled = false;
      }
    }));
  }

  async function loadJobs() {
    const view = document.getElementById('rag-admin-view');
    if (!view?.classList.contains('active')) return;
    ensureJobsPanel();
    const projectId = selectedProjectId();
    try {
      const suffix = projectId ? `?project_id=${encodeURIComponent(projectId)}&limit=20` : '?limit=20';
      const jobs = await api(`/super-admin/rag/jobs${suffix}`);
      renderJobs(Array.isArray(jobs) ? jobs : []);
    } catch (error) {
      const target = document.getElementById('rag-jobs-list');
      if (target) target.innerHTML = `<div class="rag-empty">${esc(error.message)}</div>`;
    }
  }

  function startPolling() {
    if (timer) return;
    timer = window.setInterval(() => void loadJobs(), POLL_MS);
  }

  function init() {
    ensureJobsPanel();
    startPolling();
    document.addEventListener('click', event => {
      if (event.target.closest?.('[data-view="rag-admin"]')) {
        const title = document.getElementById('page-title');
        if (title) title.textContent = 'RAG / Conhecimento';
      }
      if (event.target.closest?.('[data-rag-project], [data-id], #rag-index, [data-view="rag-admin"]')) {
        window.setTimeout(() => void loadJobs(), 200);
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