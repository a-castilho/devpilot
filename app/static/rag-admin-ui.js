(() => {
  'use strict';

  const ROLE = 'SUPER_ADMIN';
  const ragUiState = {
    overview: null,
    health: null,
    settings: null,
    projects: [],
    selectedProject: '',
    retrieval: null,
    partialErrors: []
  };

  const html = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const isSuperAdmin = () => String(state.currentUser?.role || '').toUpperCase() === ROLE;
  const boolPercent = values => values.length ? Math.round(values.filter(Boolean).length / values.length * 100) : 0;
  const statusPercent = status => ['healthy', 'ok', 'ready'].includes(String(status || '').toLowerCase()) ? 100 : String(status || '').toLowerCase() === 'degraded' ? 55 : String(status || '').toLowerCase() === 'disabled' ? 20 : 0;

  function ensureStyles() {
    if (document.getElementById('rag-admin-styles')) return;
    const style = document.createElement('style');
    style.id = 'rag-admin-styles';
    style.textContent = `
      .rag-admin-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}
      .rag-card{border:1px solid var(--border,#26354a);border-radius:14px;padding:14px;min-width:0;background:rgba(255,255,255,.015)}
      .rag-card strong{display:block;font-size:22px;margin-top:5px}.rag-card small{opacity:.7}
      .rag-layout{display:grid;grid-template-columns:minmax(240px,.72fr) minmax(0,1.8fr);gap:16px;align-items:start}
      .rag-list{display:grid;gap:8px}.rag-project{width:100%;text-align:left;border:1px solid var(--border,#26354a);border-radius:12px;background:transparent;color:inherit;padding:12px;cursor:pointer}
      .rag-project.active{border-color:#36d399;box-shadow:inset 3px 0 #36d399}.rag-project small{display:block;opacity:.68;margin-top:4px}
      .rag-actions{display:flex;gap:8px;flex-wrap:wrap}.rag-actions>*{min-width:120px}
      .rag-health{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px}.rag-health-item{border:1px solid var(--border,#26354a);border-radius:12px;padding:10px}
      .rag-settings{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.rag-settings label{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid var(--border,#26354a);border-radius:10px;padding:10px}
      .rag-retrieval{display:grid;gap:8px;margin-top:12px}.rag-chunk{border:1px solid var(--border,#26354a);border-radius:12px;padding:12px}.rag-chunk pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0 0;max-height:220px;overflow:auto}
      .rag-query-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}.rag-empty{padding:14px;border:1px dashed var(--border,#26354a);border-radius:12px;opacity:.75}
      .rag-chart-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0 0 16px}
      .rag-chart{border:1px solid var(--border,#26354a);border-radius:14px;padding:14px;min-width:0}.rag-chart h4{margin:0 0 4px}.rag-chart p{margin:0 0 12px;opacity:.68;font-size:12px}
      .rag-bar-row{display:grid;grid-template-columns:minmax(90px,.8fr) minmax(90px,1.4fr) auto;align-items:center;gap:8px;margin:8px 0;font-size:12px}
      .rag-bar-track{height:10px;border-radius:999px;background:rgba(148,163,184,.14);overflow:hidden}.rag-bar{height:100%;border-radius:inherit;background:linear-gradient(90deg,#2dd4bf,#38bdf8);min-width:2px}
      .rag-chart-value{font-variant-numeric:tabular-nums;font-weight:700}.rag-status-note{padding:10px 12px;border-radius:12px;border:1px solid var(--border,#26354a);margin-bottom:12px;font-size:13px}
      .rag-status-note.warn{border-color:#a16207}.rag-status-note.error{border-color:#be123c}.rag-status-note.ok{border-color:#15803d}
      .rag-section{margin-top:18px}.rag-section details>summary{cursor:pointer;font-weight:700;margin-bottom:12px}
      .rag-scorebar{margin-top:8px;height:7px;border-radius:999px;background:rgba(148,163,184,.14);overflow:hidden}.rag-scorebar>span{display:block;height:100%;background:linear-gradient(90deg,#34d399,#22d3ee)}
      @media(max-width:900px){.rag-admin-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.rag-layout{grid-template-columns:1fr}.rag-health,.rag-settings,.rag-chart-grid{grid-template-columns:1fr}}
      @media(max-width:560px){.rag-admin-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.rag-card{padding:11px}.rag-card strong{font-size:18px}.rag-query-row{grid-template-columns:1fr}.rag-actions>*{flex:1 1 auto}.rag-project small:nth-of-type(1){display:none}.rag-bar-row{grid-template-columns:90px 1fr auto}}
    `;
    document.head.appendChild(style);
  }

  function ensurePanel() {
    if (!isSuperAdmin() || document.getElementById('rag-admin-view')) return;
    ensureStyles();
    const nav = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!nav || !main) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'nav';
    button.dataset.view = 'rag-admin';
    button.dataset.superAdmin = 'true';
    button.textContent = 'RAG / Conhecimento';
    nav.insertBefore(button, nav.querySelector('[data-view="cloud-admin"]') || nav.querySelector('[data-view="reports"]') || null);

    const section = document.createElement('section');
    section.className = 'view';
    section.id = 'rag-admin-view';
    section.innerHTML = `
      <div class="section-head">
        <div><p>Saúde, cobertura, indexação e recuperação contextual em uma visão operacional.</p></div>
        <button class="ghost" id="rag-refresh" type="button">Atualizar</button>
      </div>
      <div id="rag-load-note"></div>
      <div class="rag-admin-grid" id="rag-summary"></div>
      <div class="rag-chart-grid" id="rag-charts"></div>
      <div class="rag-layout">
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">PROJETO</span><h3>Base monitorada</h3></div></div>
          <div class="rag-list" id="rag-project-list"><div class="rag-empty">Carregando projetos…</div></div>
        </article>
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">BASE DE CONHECIMENTO</span><h3 id="rag-project-title">Selecione um projeto</h3></div><span class="status" id="rag-status">—</span></div>
          <div class="rag-actions">
            <button class="primary" id="rag-index" type="button">Indexar agora</button>
            <button class="ghost" id="rag-clear-cache" type="button">Limpar cache</button>
          </div>
          <div class="rag-health" id="rag-health"></div>
          <div class="rag-section">
            <details>
              <summary>Configuração avançada</summary>
              <div class="rag-settings" id="rag-settings"></div>
            </details>
          </div>
          <div class="rag-section">
            <div class="panel-title"><div><span class="eyebrow">TESTE</span><h3>Retrieval</h3></div></div>
            <div class="rag-query-row"><input id="rag-query" maxlength="1000" placeholder="Ex.: como resolvemos o travamento do modo jogo?"><button class="primary" id="rag-retrieve" type="button">Consultar</button></div>
            <div class="rag-retrieval" id="rag-retrieval"><div class="rag-empty">Faça uma consulta para visualizar as fontes recuperadas.</div></div>
          </div>
        </article>
      </div>
    `;
    main.appendChild(section);

    button.addEventListener('click', () => openView(button, section));
    section.querySelector('#rag-refresh').addEventListener('click', () => loadAll(true));
    section.querySelector('#rag-index').addEventListener('click', indexSelected);
    section.querySelector('#rag-clear-cache').addEventListener('click', clearCache);
    section.querySelector('#rag-retrieve').addEventListener('click', retrieve);
  }

  function openView(button, section) {
    if (!isSuperAdmin()) return toast('Acesso exclusivo do Super Admin');
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button));
    const title = document.getElementById('page-title');
    if (title) title.textContent = 'RAG / Conhecimento';
    void loadAll();
  }

  function selected() {
    return ragUiState.projects.find(project => String(project.id) === String(ragUiState.selectedProject)) || null;
  }

  function bar(label, value, suffix = '%') {
    const safe = Math.max(0, Math.min(100, Number(value || 0)));
    return `<div class="rag-bar-row"><span>${html(label)}</span><div class="rag-bar-track"><div class="rag-bar" style="width:${safe}%"></div></div><span class="rag-chart-value">${safe}${suffix}</span></div>`;
  }

  function renderSummary() {
    const target = document.getElementById('rag-summary');
    if (!target) return;
    const health = ragUiState.health || {};
    const settings = ragUiState.settings || {};
    const linked = ragUiState.projects.filter(project => project.organization_id).length;
    target.innerHTML = `
      <div class="rag-card"><span class="eyebrow">RAG</span><strong>${settings.enabled ? 'ATIVO' : 'DESLIGADO'}</strong><small>estado global</small></div>
      <div class="rag-card"><span class="eyebrow">SAÚDE</span><strong>${html(String(health.status || '—').toUpperCase())}</strong><small>serviço</small></div>
      <div class="rag-card"><span class="eyebrow">CACHE</span><strong>${settings.cache_enabled ? 'ATIVO' : 'OFF'}</strong><small>Redis</small></div>
      <div class="rag-card"><span class="eyebrow">COBERTURA</span><strong>${linked}/${ragUiState.projects.length}</strong><small>projetos vinculados</small></div>`;
  }

  function renderCharts() {
    const target = document.getElementById('rag-charts');
    if (!target) return;
    const settings = ragUiState.settings || {};
    const health = ragUiState.health || {};
    const repo = health.repository || {};
    const cache = health.cache || {};
    const projectTotal = ragUiState.projects.length;
    const linked = ragUiState.projects.filter(project => project.organization_id).length;
    const coverage = projectTotal ? Math.round(linked / projectTotal * 100) : 0;
    const resourceKeys = ['enabled','cache_enabled','git_enabled','docs_enabled','audit_enabled','tasks_enabled'];
    const resources = boolPercent(resourceKeys.map(key => Boolean(settings[key])));
    target.innerHTML = `
      <article class="rag-chart"><h4>Cobertura dos projetos</h4><p>Percentual de projetos aptos a usar a base RAG.</p>${bar('Vinculados', coverage)}</article>
      <article class="rag-chart"><h4>Saúde das dependências</h4><p>Visão rápida do serviço e componentes externos.</p>${bar('RAG', statusPercent(health.status))}${bar('Vector DB', statusPercent(repo.status))}${bar('Cache', settings.cache_enabled ? statusPercent(cache.status) : 0)}</article>
      <article class="rag-chart"><h4>Recursos habilitados</h4><p>Proporção das capacidades administrativas atualmente ligadas.</p>${bar('Ativos', resources)}</article>`;
  }

  function renderProjects() {
    const target = document.getElementById('rag-project-list');
    if (!target) return;
    target.innerHTML = ragUiState.projects.map(project => `
      <button type="button" class="rag-project ${String(project.id) === String(ragUiState.selectedProject) ? 'active' : ''}" data-rag-project="${html(project.id)}">
        <strong>${html(project.name)}</strong><small>${html(project.repository_url || '')}</small><small>${html(project.default_branch || 'main')} · ${project.organization_id ? 'organização vinculada' : 'sem organização'}</small>
      </button>`).join('') || '<div class="rag-empty">Nenhum projeto disponível.</div>';
    target.querySelectorAll('[data-rag-project]').forEach(button => button.addEventListener('click', () => {
      ragUiState.selectedProject = button.dataset.ragProject;
      ragUiState.retrieval = null;
      renderProjects();
      renderProject();
    }));
  }

  function renderProject() {
    const project = selected();
    const title = document.getElementById('rag-project-title');
    const badge = document.getElementById('rag-status');
    const enabled = Boolean(ragUiState.settings?.enabled);
    if (title) title.textContent = project?.name || 'Selecione um projeto';
    if (badge) badge.textContent = !project ? '—' : !project.organization_id ? 'SEM ORGANIZAÇÃO' : enabled ? 'PRONTO' : 'RAG DESATIVADO';
    document.getElementById('rag-index').disabled = !project?.organization_id || !enabled;
    document.getElementById('rag-clear-cache').disabled = !project?.organization_id;
    document.getElementById('rag-retrieve').disabled = !project?.organization_id || !enabled;
    renderRetrieval();
  }

  function renderHealth() {
    const target = document.getElementById('rag-health');
    if (!target) return;
    const health = ragUiState.health || {};
    const repo = health.repository || {};
    const cache = health.cache || {};
    target.innerHTML = `
      <div class="rag-health-item"><small>RAG</small><strong>${html(health.status || '—')}</strong></div>
      <div class="rag-health-item"><small>Vector DB</small><strong>${html(repo.status || '—')}</strong></div>
      <div class="rag-health-item"><small>Cache</small><strong>${html(cache.status || (ragUiState.settings?.cache_enabled ? '—' : 'disabled'))}</strong></div>`;
  }

  function renderSettings() {
    const target = document.getElementById('rag-settings');
    if (!target) return;
    const s = ragUiState.settings || {};
    const toggles = [['enabled','RAG global'],['cache_enabled','Cache'],['git_enabled','Git'],['docs_enabled','Documentação'],['audit_enabled','Auditoria'],['tasks_enabled','Tarefas']];
    target.innerHTML = toggles.map(([key,label]) => `<label><span>${label}</span><input type="checkbox" data-rag-setting="${key}" ${s[key] ? 'checked' : ''}></label>`).join('');
    target.querySelectorAll('[data-rag-setting]').forEach(input => input.addEventListener('change', async () => {
      input.disabled = true;
      try {
        ragUiState.settings = await api('/super-admin/rag/settings', {method:'PATCH', body:JSON.stringify({[input.dataset.ragSetting]: input.checked})});
        toast('Configuração RAG atualizada');
        await loadHealth();
        renderSummary(); renderCharts(); renderSettings(); renderProject();
      } catch (error) {
        input.checked = !input.checked;
        toast(error.message);
      } finally { input.disabled = false; }
    }));
  }

  function renderRetrieval() {
    const target = document.getElementById('rag-retrieval');
    if (!target) return;
    const result = ragUiState.retrieval;
    if (!result) {
      target.innerHTML = '<div class="rag-empty">Faça uma consulta para visualizar as fontes recuperadas.</div>';
      return;
    }
    const chunks = Array.isArray(result.chunks) ? result.chunks : [];
    target.innerHTML = `<div class="rag-card"><small>Modo ${html(result.mode)} · cache ${result.cache_hit ? 'hit' : 'miss'} · ${Number(result.retrieval_time_ms || 0).toFixed(1)} ms</small></div>` +
      (chunks.map(chunk => {
        const score = Math.max(0, Math.min(100, Math.round(Number(chunk.score || 0) * 100)));
        return `<div class="rag-chunk"><strong>${html(chunk.source_path || chunk.source_id || chunk.source_type)}</strong><small>${html(chunk.source_type)} · score ${Number(chunk.score || 0).toFixed(3)}</small><div class="rag-scorebar"><span style="width:${score}%"></span></div><pre>${html(chunk.content)}</pre></div>`;
      }).join('') || '<div class="rag-empty">Nenhum trecho acima do limiar de similaridade.</div>');
  }

  function renderLoadNote() {
    const target = document.getElementById('rag-load-note');
    if (!target) return;
    if (!ragUiState.partialErrors.length) {
      const disabled = ragUiState.settings && !ragUiState.settings.enabled;
      target.innerHTML = disabled ? '<div class="rag-status-note warn">RAG desativado por configuração. Ative “RAG global” em Configuração avançada para indexar e consultar.</div>' : '';
      return;
    }
    target.innerHTML = `<div class="rag-status-note error"><strong>Carregamento parcial.</strong> ${html(ragUiState.partialErrors.join(' · '))}</div>`;
  }

  async function loadHealth() {
    try {
      ragUiState.health = await api('/super-admin/rag/health');
    } catch (error) {
      ragUiState.health = {status:'error'};
      throw error;
    } finally {
      renderHealth(); renderCharts();
    }
  }

  async function loadAll(force = false) {
    if (!isSuperAdmin()) return;
    const view = document.getElementById('rag-admin-view');
    if (!force && !view?.classList.contains('active')) return;

    const requests = [
      ['overview', api('/super-admin/rag/overview')],
      ['settings', api('/super-admin/rag/settings')],
      ['health', api('/super-admin/rag/health')],
      ['projects', api('/ui/projects?limit=100')]
    ];
    const settled = await Promise.allSettled(requests.map(([, request]) => request));
    ragUiState.partialErrors = [];
    settled.forEach((result, index) => {
      const key = requests[index][0];
      if (result.status === 'fulfilled') {
        if (key === 'projects') ragUiState.projects = Array.isArray(result.value) ? result.value : [];
        else ragUiState[key] = result.value || {};
      } else {
        ragUiState.partialErrors.push(`${key}: ${result.reason?.message || 'indisponível'}`);
      }
    });

    if (!ragUiState.selectedProject || !ragUiState.projects.some(item => String(item.id) === String(ragUiState.selectedProject))) {
      ragUiState.selectedProject = ragUiState.projects[0]?.id || '';
    }
    renderLoadNote(); renderSummary(); renderCharts(); renderProjects(); renderProject(); renderHealth(); renderSettings();
  }

  async function indexSelected() {
    const project = selected();
    if (!project) return;
    const button = document.getElementById('rag-index');
    const original = button.textContent;
    button.disabled = true; button.textContent = 'Indexando…';
    try {
      const result = await api(`/super-admin/rag/projects/${encodeURIComponent(project.id)}/index`, {method:'POST'});
      toast(`RAG atualizado: ${result.indexed ?? 0} documento(s), ${result.skipped ?? 0} sem alteração`);
      await loadAll(true);
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; button.textContent = original; }
  }

  async function clearCache() {
    const project = selected();
    if (!project?.organization_id) return;
    try {
      await api(`/super-admin/rag/cache/${encodeURIComponent(project.organization_id)}/${encodeURIComponent(project.id)}`, {method:'DELETE'});
      toast('Cache RAG do projeto limpo');
    } catch (error) { toast(error.message); }
  }

  async function retrieve() {
    const project = selected();
    const input = document.getElementById('rag-query');
    const query = String(input?.value || '').trim();
    if (!project || !query) return toast('Digite uma consulta para testar o RAG');
    const button = document.getElementById('rag-retrieve');
    const original = button.textContent;
    button.disabled = true; button.textContent = 'Consultando…';
    try {
      ragUiState.retrieval = await api(`/super-admin/rag/projects/${encodeURIComponent(project.id)}/retrieve`, {method:'POST', body:JSON.stringify({query})});
      renderRetrieval();
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; button.textContent = original; }
  }

  function init() { ensurePanel(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true}); else init();
  document.addEventListener('devpilot:dashboard-revealed', init);
  document.addEventListener('devpilot:feature-ready', event => { if (event.detail?.feature === 'admin') init(); });
})();
