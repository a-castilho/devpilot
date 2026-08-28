(() => {
  'use strict';

  const ROLE = 'SUPER_ADMIN';
  const ragUiState = {overview: null, health: null, settings: null, projects: [], selectedProject: '', retrieval: null};

  const html = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const isSuperAdmin = () => String(state.currentUser?.role || '').toUpperCase() === ROLE;

  function ensureStyles() {
    if (document.getElementById('rag-admin-styles')) return;
    const style = document.createElement('style');
    style.id = 'rag-admin-styles';
    style.textContent = `
      .rag-admin-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}
      .rag-card{border:1px solid var(--border,#26354a);border-radius:14px;padding:14px;min-width:0}
      .rag-card strong{display:block;font-size:22px;margin-top:5px}.rag-card small{opacity:.7}
      .rag-layout{display:grid;grid-template-columns:minmax(250px,.8fr) minmax(0,1.7fr);gap:16px;align-items:start}
      .rag-list{display:grid;gap:8px}.rag-project{width:100%;text-align:left;border:1px solid var(--border,#26354a);border-radius:12px;background:transparent;color:inherit;padding:12px;cursor:pointer}
      .rag-project.active{border-color:#36d399;box-shadow:inset 3px 0 #36d399}.rag-project small{display:block;opacity:.68;margin-top:4px}
      .rag-actions{display:flex;gap:8px;flex-wrap:wrap}.rag-actions>*{min-width:120px}
      .rag-health{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px}.rag-health-item{border:1px solid var(--border,#26354a);border-radius:12px;padding:10px}
      .rag-settings{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.rag-settings label{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid var(--border,#26354a);border-radius:10px;padding:10px}
      .rag-retrieval{display:grid;gap:8px;margin-top:12px}.rag-chunk{border:1px solid var(--border,#26354a);border-radius:12px;padding:12px}.rag-chunk pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0 0;max-height:220px;overflow:auto}
      .rag-query-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}.rag-empty{padding:14px;border:1px dashed var(--border,#26354a);border-radius:12px;opacity:.75}
      @media(max-width:900px){.rag-admin-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.rag-layout{grid-template-columns:1fr}.rag-health,.rag-settings{grid-template-columns:1fr}}
      @media(max-width:560px){.rag-admin-grid{grid-template-columns:1fr}.rag-query-row{grid-template-columns:1fr}.rag-actions>*{flex:1 1 auto}}
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
        <div><p>Controle da memória técnica, indexação, cache e recuperação contextual do DEVpilot.</p></div>
        <button class="ghost" id="rag-refresh" type="button">Atualizar</button>
      </div>
      <div class="rag-admin-grid" id="rag-summary"></div>
      <div class="rag-layout">
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">SUPER ADMIN</span><h3>Projetos</h3></div></div>
          <div class="rag-list" id="rag-project-list"><div class="rag-empty">Carregando projetos…</div></div>
        </article>
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">BASE DE CONHECIMENTO</span><h3 id="rag-project-title">Selecione um projeto</h3></div><span class="status" id="rag-status">—</span></div>
          <div class="rag-actions">
            <button class="primary" id="rag-index" type="button">Indexar / Atualizar</button>
            <button class="ghost" id="rag-clear-cache" type="button">Limpar cache</button>
          </div>
          <div class="rag-health" id="rag-health"></div>
          <div style="margin-top:18px">
            <div class="panel-title"><div><span class="eyebrow">CONFIGURAÇÃO</span><h3>Recursos</h3></div></div>
            <div class="rag-settings" id="rag-settings"></div>
          </div>
          <div style="margin-top:18px">
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

  function renderSummary() {
    const target = document.getElementById('rag-summary');
    if (!target) return;
    const health = ragUiState.health || {};
    const settings = ragUiState.settings || {};
    target.innerHTML = `
      <div class="rag-card"><span class="eyebrow">RAG</span><strong>${settings.enabled ? 'ATIVO' : 'DESLIGADO'}</strong><small>estado global</small></div>
      <div class="rag-card"><span class="eyebrow">SAÚDE</span><strong>${html(String(health.status || '—').toUpperCase())}</strong><small>serviço desacoplado</small></div>
      <div class="rag-card"><span class="eyebrow">CACHE</span><strong>${settings.cache_enabled ? 'ATIVO' : 'OFF'}</strong><small>Redis</small></div>
      <div class="rag-card"><span class="eyebrow">PROJETOS</span><strong>${ragUiState.projects.length}</strong><small>disponíveis para indexação</small></div>`;
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
    if (title) title.textContent = project?.name || 'Selecione um projeto';
    if (badge) badge.textContent = project ? (project.organization_id ? 'PRONTO' : 'SEM ORGANIZAÇÃO') : '—';
    document.getElementById('rag-index').disabled = !project?.organization_id;
    document.getElementById('rag-clear-cache').disabled = !project?.organization_id;
    document.getElementById('rag-retrieve').disabled = !project?.organization_id;
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
      <div class="rag-health-item"><small>Cache</small><strong>${html(cache.status || '—')}</strong></div>`;
  }

  function renderSettings() {
    const target = document.getElementById('rag-settings');
    if (!target) return;
    const s = ragUiState.settings || {};
    const toggles = [
      ['enabled','RAG global'],['cache_enabled','Cache'],['git_enabled','Git'],['docs_enabled','Documentação'],['audit_enabled','Auditoria'],['tasks_enabled','Tarefas']
    ];
    target.innerHTML = toggles.map(([key,label]) => `<label><span>${label}</span><input type="checkbox" data-rag-setting="${key}" ${s[key] ? 'checked' : ''}></label>`).join('');
    target.querySelectorAll('[data-rag-setting]').forEach(input => input.addEventListener('change', async () => {
      input.disabled = true;
      try {
        ragUiState.settings = await api('/super-admin/rag/settings', {method:'PATCH', body:JSON.stringify({[input.dataset.ragSetting]: input.checked})});
        toast('Configuração RAG atualizada');
        await loadHealth();
        renderSummary();
        renderSettings();
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
      (chunks.map(chunk => `<div class="rag-chunk"><strong>${html(chunk.source_path || chunk.source_id || chunk.source_type)}</strong><small>${html(chunk.source_type)} · score ${Number(chunk.score || 0).toFixed(3)}</small><pre>${html(chunk.content)}</pre></div>`).join('') || '<div class="rag-empty">Nenhum trecho acima do limiar de similaridade.</div>');
  }

  async function loadHealth() {
    ragUiState.health = await api('/super-admin/rag/health');
    renderHealth();
  }

  async function loadAll(force = false) {
    if (!isSuperAdmin()) return;
    const view = document.getElementById('rag-admin-view');
    if (!force && !view?.classList.contains('active')) return;
    try {
      const [overview, settings, health, projects] = await Promise.all([
        api('/super-admin/rag/overview'), api('/super-admin/rag/settings'), api('/super-admin/rag/health'), api('/ui/projects?limit=100')
      ]);
      ragUiState.overview = overview;
      ragUiState.settings = settings || {};
      ragUiState.health = health || {};
      ragUiState.projects = Array.isArray(projects) ? projects : [];
      if (!ragUiState.selectedProject || !ragUiState.projects.some(item => String(item.id) === String(ragUiState.selectedProject))) {
        ragUiState.selectedProject = ragUiState.projects[0]?.id || '';
      }
      renderSummary(); renderProjects(); renderProject(); renderHealth(); renderSettings();
    } catch (error) { toast(error.message); }
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
      await loadHealth();
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
})();
