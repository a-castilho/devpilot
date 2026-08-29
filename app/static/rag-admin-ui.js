(() => {
  'use strict';

  const ROLE = 'SUPER_ADMIN';
  const s = {overview:null, health:null, settings:null, projects:[], selectedProject:'', retrieval:null, partialErrors:[]};
  const html = value => String(value ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const isAdmin = () => String(state.currentUser?.role || '').toUpperCase() === ROLE;
  const enabled = () => Boolean(s.settings?.enabled);
  const selected = () => s.projects.find(project => String(project.id) === String(s.selectedProject)) || null;
  const pct = status => ['healthy','ok','ready'].includes(String(status || '').toLowerCase()) ? 100 : String(status || '').toLowerCase() === 'degraded' ? 55 : 0;
  const boolPct = values => values.length ? Math.round(values.filter(Boolean).length / values.length * 100) : 0;
  const num = (value, digits=2) => Number(value || 0).toFixed(digits);

  function styles() {
    if (document.getElementById('rag-admin-styles')) return;
    const el = document.createElement('style');
    el.id = 'rag-admin-styles';
    el.textContent = `
      .rag-admin-grid,.rag-chart-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}.rag-chart-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
      .rag-card,.rag-chart,.rag-health-item{border:1px solid var(--border,#26354a);border-radius:14px;padding:14px;min-width:0;background:rgba(255,255,255,.015)}.rag-card strong{display:block;font-size:22px;margin-top:5px}.rag-card small,.rag-chart p{opacity:.7}
      .rag-layout{display:grid;grid-template-columns:minmax(240px,.72fr) minmax(0,1.8fr);gap:16px;align-items:start}.rag-list{display:grid;gap:8px}.rag-project{width:100%;text-align:left;border:1px solid var(--border,#26354a);border-radius:12px;background:transparent;color:inherit;padding:12px;cursor:pointer}.rag-project.active{border-color:#36d399;box-shadow:inset 3px 0 #36d399}.rag-project small{display:block;opacity:.68;margin-top:4px}
      .rag-actions{display:flex;gap:8px;flex-wrap:wrap}.rag-actions>*{min-width:120px}.rag-health{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}.rag-settings{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.rag-setting{display:flex;justify-content:space-between;align-items:center;gap:12px;border:1px solid var(--border,#26354a);border-radius:10px;padding:10px}.rag-setting input[type=number]{width:110px;min-width:90px}.rag-setting-copy small{display:block;opacity:.65;margin-top:3px}
      .rag-bar-row{display:grid;grid-template-columns:90px 1fr auto;align-items:center;gap:8px;margin:8px 0;font-size:12px}.rag-bar-track,.rag-scorebar{height:9px;border-radius:999px;background:rgba(148,163,184,.14);overflow:hidden}.rag-bar,.rag-scorebar>span{display:block;height:100%;background:linear-gradient(90deg,#2dd4bf,#38bdf8)}.rag-chart-value{font-weight:700}.rag-status-note{padding:10px 12px;border-radius:12px;border:1px solid var(--border,#26354a);margin-bottom:12px;font-size:13px}.rag-status-note.info{border-color:#475569;background:rgba(71,85,105,.08)}.rag-status-note.warn{border-color:#d97706;background:rgba(217,119,6,.08)}.rag-status-note.error{border-color:#be123c}.rag-section{margin-top:18px}.rag-section details>summary{cursor:pointer;font-weight:700;margin-bottom:12px}.rag-query-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}.rag-retrieval{display:grid;gap:8px;margin-top:12px}.rag-retrieval-meta{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;opacity:.8}.rag-retrieval-meta span{border:1px solid var(--border,#26354a);border-radius:999px;padding:4px 8px}.rag-chunk{border:1px solid var(--border,#26354a);border-radius:12px;padding:12px}.rag-chunk.diagnostic{opacity:.72;border-style:dashed}.rag-chunk-head{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}.rag-chunk pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:220px;overflow:auto}.rag-empty{padding:14px;border:1px dashed var(--border,#26354a);border-radius:12px;opacity:.75}.rag-subtitle{font-size:12px;font-weight:800;letter-spacing:.04em;margin-top:6px}
      @media(max-width:900px){.rag-admin-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.rag-chart-grid,.rag-layout,.rag-health,.rag-settings{grid-template-columns:1fr}}
      @media(max-width:560px){.rag-card{padding:11px}.rag-card strong{font-size:18px}.rag-query-row{grid-template-columns:1fr}.rag-actions>*{flex:1 1 auto}.rag-project small:first-of-type{display:none}.rag-setting input[type=number]{width:88px}}
    `;
    document.head.appendChild(el);
  }

  function panel() {
    if (!isAdmin() || document.getElementById('rag-admin-view')) return;
    styles();
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

    const view = document.createElement('section');
    view.className = 'view';
    view.id = 'rag-admin-view';
    view.innerHTML = `
      <div class="section-head"><div><p>Saúde, cobertura, indexação e recuperação contextual em uma visão operacional.</p></div><button class="ghost" id="rag-refresh">Atualizar</button></div>
      <div id="rag-load-note"></div><div class="rag-admin-grid" id="rag-summary"></div><div class="rag-chart-grid" id="rag-charts"></div>
      <div class="rag-layout">
        <article class="panel"><div class="panel-title"><div><span class="eyebrow">PROJETO</span><h3>Base monitorada</h3></div></div><div class="rag-list" id="rag-project-list"></div></article>
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">BASE DE CONHECIMENTO</span><h3 id="rag-project-title">Selecione um projeto</h3></div><span class="status" id="rag-status">—</span></div>
          <div class="rag-actions"><button class="primary" id="rag-enable">Ativar RAG</button><button class="primary" id="rag-index">Indexar agora</button><button class="ghost" id="rag-clear-cache">Limpar cache</button></div>
          <div class="rag-health" id="rag-health"></div>
          <div class="rag-section"><details><summary>Configuração avançada</summary><div class="rag-settings" id="rag-settings"></div></details></div>
          <div class="rag-section"><div class="panel-title"><div><span class="eyebrow">TESTE</span><h3>Retrieval</h3></div></div>
            <div class="rag-query-row"><input id="rag-query" maxlength="1000" placeholder="Ex.: o que faz o projeto a-castilho?"><button class="primary" id="rag-retrieve">Consultar</button></div>
            <div class="rag-retrieval" id="rag-retrieval"></div>
          </div>
        </article>
      </div>`;
    main.appendChild(view);

    button.onclick = () => {
      document.querySelectorAll('.view').forEach(item => item.classList.toggle('active', item === view));
      document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button));
      void loadAll();
    };
    view.querySelector('#rag-refresh').onclick = () => loadAll(true);
    view.querySelector('#rag-enable').onclick = activate;
    view.querySelector('#rag-index').onclick = indexSelected;
    view.querySelector('#rag-clear-cache').onclick = clearCache;
    view.querySelector('#rag-retrieve').onclick = retrieve;
    view.querySelector('#rag-query').addEventListener('keydown', event => {
      if (event.key === 'Enter') void retrieve();
    });
  }

  const bar = (label, value) => {
    const n = Math.max(0, Math.min(100, Number(value || 0)));
    return `<div class="rag-bar-row"><span>${html(label)}</span><div class="rag-bar-track"><span class="rag-bar" style="width:${n}%"></span></div><span class="rag-chart-value">${n}%</span></div>`;
  };

  function render() {
    renderNote(); renderSummary(); renderCharts(); renderProjects(); renderProject(); renderHealth(); renderSettings(); renderRetrieval();
  }

  function renderNote() {
    const target = document.getElementById('rag-load-note');
    if (!target) return;
    if (s.partialErrors.length) {
      target.innerHTML = `<div class="rag-status-note error"><strong>Carregamento parcial.</strong> ${html(s.partialErrors.join(' · '))}</div>`;
      return;
    }
    target.innerHTML = !enabled()
      ? '<div class="rag-status-note info"><strong>RAG desativado por configuração.</strong> Ative quando quiser indexar e consultar a base de conhecimento. Isto não é uma falha do sistema.</div>'
      : '';
  }

  function renderSummary() {
    const target = document.getElementById('rag-summary');
    if (!target) return;
    const linked = s.projects.filter(project => project.organization_id).length;
    const healthLabel = enabled() ? String(s.health?.status || '—').toUpperCase() : 'NÃO AVALIADA';
    const cacheStatus = !enabled() ? 'NÃO AVALIADO' : String(s.health?.cache?.status || (s.settings?.cache_enabled ? '—' : 'disabled')).toUpperCase();
    target.innerHTML = `
      <div class="rag-card"><span class="eyebrow">RAG</span><strong>${enabled() ? 'ATIVO' : 'DESATIVADO'}</strong><small>estado global</small></div>
      <div class="rag-card"><span class="eyebrow">SAÚDE</span><strong>${html(healthLabel)}</strong><small>${enabled() ? 'serviço' : 'RAG inativo'}</small></div>
      <div class="rag-card"><span class="eyebrow">CACHE</span><strong>${html(cacheStatus)}</strong><small>${cacheStatus === 'DISABLED' ? 'opcional · sem Redis' : 'Redis'}</small></div>
      <div class="rag-card"><span class="eyebrow">COBERTURA</span><strong>${linked}/${s.projects.length}</strong><small>projetos vinculados</small></div>`;
  }

  function renderCharts() {
    const target = document.getElementById('rag-charts');
    if (!target) return;
    const total = s.projects.length;
    const linked = s.projects.filter(project => project.organization_id).length;
    const coverage = total ? Math.round(linked / total * 100) : 0;
    const keys = ['enabled','cache_enabled','git_enabled','docs_enabled','audit_enabled','tasks_enabled'];
    const resources = boolPct(keys.map(key => Boolean(s.settings?.[key])));
    const cacheHealth = ['disabled',''].includes(String(s.health?.cache?.status || '').toLowerCase()) ? 100 : pct(s.health?.cache?.status);
    const health = enabled()
      ? `${bar('RAG',pct(s.health?.status))}${bar('Vector DB',pct(s.health?.repository?.status))}${bar('Cache',s.settings?.cache_enabled ? cacheHealth : 100)}`
      : '<div class="rag-empty">Não avaliado enquanto o RAG estiver desativado.</div>';
    target.innerHTML = `
      <article class="rag-chart"><h4>Cobertura dos projetos</h4><p>Projetos vinculados à base.</p>${bar('Vinculados',coverage)}</article>
      <article class="rag-chart"><h4>Saúde das dependências</h4><p>Cache é opcional e não degrada o RAG quando não configurado.</p>${health}</article>
      <article class="rag-chart"><h4>Recursos habilitados</h4><p>Capacidades administrativas ligadas.</p>${bar('Ativos',resources)}</article>`;
  }

  function renderProjects() {
    const target = document.getElementById('rag-project-list');
    if (!target) return;
    target.innerHTML = s.projects.map(project => `
      <button class="rag-project ${String(project.id) === String(s.selectedProject) ? 'active' : ''}" data-id="${html(project.id)}">
        <strong>${html(project.name)}</strong><small>${html(project.repository_url || '')}</small>
        <small>${html(project.default_branch || 'main')} · ${project.organization_id ? 'organização vinculada' : 'sem organização'}</small>
      </button>`).join('') || '<div class="rag-empty">Nenhum projeto disponível.</div>';
    target.querySelectorAll('[data-id]').forEach(button => button.onclick = () => {
      s.selectedProject = button.dataset.id;
      s.retrieval = null;
      render();
      document.dispatchEvent(new CustomEvent('devpilot:rag-project-changed'));
    });
  }

  function renderProject() {
    const project = selected();
    const badge = document.getElementById('rag-status');
    const title = document.getElementById('rag-project-title');
    const on = enabled();
    if (title) title.textContent = project?.name || 'Selecione um projeto';
    if (badge) badge.textContent = !project ? '—' : !project.organization_id ? 'SEM ORGANIZAÇÃO' : on ? 'PRONTO' : 'DESATIVADO';
    const enable = document.getElementById('rag-enable');
    if (enable) enable.hidden = on;
    const index = document.getElementById('rag-index');
    const clear = document.getElementById('rag-clear-cache');
    const retrieveButton = document.getElementById('rag-retrieve');
    if (index) index.disabled = !project?.organization_id || !on;
    if (clear) clear.disabled = !project?.organization_id;
    if (retrieveButton) retrieveButton.disabled = !project?.organization_id || !on;
  }

  function renderHealth() {
    const target = document.getElementById('rag-health');
    if (!target) return;
    if (!enabled()) {
      target.innerHTML = '<div class="rag-health-item"><small>RAG</small><strong>DESATIVADO</strong></div><div class="rag-health-item"><small>Vector DB</small><strong>NÃO AVALIADO</strong></div><div class="rag-health-item"><small>Cache</small><strong>NÃO AVALIADO</strong></div><div class="rag-health-item"><small>Embedding</small><strong>NÃO AVALIADO</strong></div>';
      return;
    }
    const embedding = s.health?.embedding || s.health?.repository?.embedding || {};
    const provider = embedding.provider === 'local_hash' ? 'LOCAL HASH' : String(embedding.provider || '—').toUpperCase();
    const model = embedding.model ? ` · ${embedding.model}` : '';
    target.innerHTML = `
      <div class="rag-health-item"><small>RAG</small><strong>${html(s.health?.status || '—')}</strong></div>
      <div class="rag-health-item"><small>Vector DB</small><strong>${html(s.health?.repository?.status || '—')}</strong></div>
      <div class="rag-health-item"><small>Cache</small><strong>${html(s.health?.cache?.status || (s.settings?.cache_enabled ? '—' : 'disabled'))}</strong></div>
      <div class="rag-health-item"><small>Embedding</small><strong>${html(provider)}</strong><small>${html(model)}</small></div>`;
  }

  async function patchSetting(key, value, input) {
    if (input) input.disabled = true;
    try {
      s.settings = await api('/super-admin/rag/settings', {method:'PATCH', body:JSON.stringify({[key]:value})});
      try { s.health = await api('/super-admin/rag/health'); } catch {}
      s.retrieval = null;
      render();
      toast('Configuração RAG atualizada');
    } catch (error) {
      toast(error.message);
      await loadAll(true);
    } finally {
      if (input) input.disabled = false;
    }
  }

  function renderSettings() {
    const target = document.getElementById('rag-settings');
    if (!target) return;
    const toggles = [
      ['enabled','RAG global'],['cache_enabled','Cache'],['git_enabled','Git'],
      ['docs_enabled','Documentação'],['audit_enabled','Auditoria'],['tasks_enabled','Tarefas']
    ];
    const configured = Number(s.settings?.similarity_threshold ?? 0.7);
    const effective = Number(s.health?.retrieval?.effective_threshold ?? configured);
    target.innerHTML = toggles.map(([key,label]) => `
      <label class="rag-setting"><span>${html(label)}</span><input type="checkbox" data-setting="${key}" ${s.settings?.[key] ? 'checked' : ''}></label>`).join('') + `
      <label class="rag-setting"><span class="rag-setting-copy"><strong>Top K</strong><small>Máximo de trechos retornados</small></span><input type="number" min="1" max="10" step="1" value="${Number(s.settings?.top_k || 5)}" data-number-setting="top_k"></label>
      <label class="rag-setting"><span class="rag-setting-copy"><strong>Limiar de similaridade</strong><small>Configurado ${num(configured)} · efetivo ${num(effective)}${effective !== configured ? ' (calibrado para Local Hash)' : ''}</small></span><input type="number" min="0" max="1" step="0.01" value="${configured}" data-number-setting="similarity_threshold"></label>`;

    target.querySelectorAll('[data-setting]').forEach(input => input.onchange = () => patchSetting(input.dataset.setting, input.checked, input));
    target.querySelectorAll('[data-number-setting]').forEach(input => input.onchange = () => {
      const key = input.dataset.numberSetting;
      const value = key === 'top_k' ? Number.parseInt(input.value,10) : Number.parseFloat(input.value);
      if (!Number.isFinite(value)) { toast('Valor inválido'); renderSettings(); return; }
      void patchSetting(key, value, input);
    });
  }

  function chunkCard(chunk, diagnostic=false) {
    const score = Math.max(0, Math.min(100, Math.round(Number(chunk.score || 0) * 100)));
    return `<div class="rag-chunk ${diagnostic ? 'diagnostic' : ''}">
      <div class="rag-chunk-head"><strong>${html(chunk.source_path || chunk.source_id || chunk.source_type)}</strong><small>${html(chunk.source_type)} · score ${Number(chunk.score || 0).toFixed(3)}</small></div>
      <div class="rag-scorebar"><span style="width:${score}%"></span></div><pre>${html(chunk.content)}</pre></div>`;
  }

  function renderRetrieval() {
    const target = document.getElementById('rag-retrieval');
    if (!target) return;
    if (!s.retrieval) {
      target.innerHTML = '<div class="rag-empty">Faça uma consulta para visualizar as fontes recuperadas.</div>';
      return;
    }
    const chunks = Array.isArray(s.retrieval.chunks) ? s.retrieval.chunks : [];
    const candidates = Array.isArray(s.retrieval.candidates) ? s.retrieval.candidates : [];
    const embedding = s.retrieval.embedding || {};
    const provider = embedding.provider === 'local_hash' ? 'Local Hash' : (embedding.provider || '—');
    const configured = Number(s.retrieval.configured_threshold || 0);
    const effective = Number(s.retrieval.effective_threshold || 0);
    const indexState = s.retrieval.index_state || {};
    const meta = `<div class="rag-retrieval-meta"><span>modo ${html(s.retrieval.mode || '—')}</span><span>embedding ${html(provider)}${embedding.model ? ` / ${html(embedding.model)}` : ''}</span><span>limiar ${num(effective,3)}${configured !== effective ? ` (config. ${num(configured,3)})` : ''}</span><span>${s.retrieval.cache_hit ? 'cache hit' : 'cache miss'}</span><span>${num(s.retrieval.retrieval_time_ms,1)} ms</span></div>`;
    const reindex = indexState.reindex_required
      ? '<div class="rag-status-note warn"><strong>Reindexação necessária.</strong> O provider/modelo de embeddings mudou. Use “Indexar agora” antes de confiar no retrieval.</div>'
      : indexState.legacy_vectors > 0
        ? `<div class="rag-status-note info">${Number(indexState.legacy_vectors)} vetor(es) legados detectados. A próxima indexação grava a assinatura do provider para detectar futuras trocas de modelo.</div>`
        : '';
    if (chunks.length) {
      target.innerHTML = meta + reindex + chunks.map(chunk => chunkCard(chunk)).join('');
      return;
    }
    const diagnostic = candidates.length
      ? `<div class="rag-subtitle">CANDIDATOS ABAIXO DO LIMIAR / DIAGNÓSTICO</div>${candidates.map(chunk => chunkCard(chunk,true)).join('')}`
      : '';
    target.innerHTML = meta + reindex + '<div class="rag-empty">Nenhum trecho acima do limiar.</div>' + diagnostic;
  }

  async function activate() {
    try {
      s.settings = await api('/super-admin/rag/settings', {method:'PATCH', body:JSON.stringify({enabled:true})});
      try { s.health = await api('/super-admin/rag/health'); } catch {}
      render(); toast('RAG ativado');
    } catch (error) { toast(error.message); }
  }

  async function loadAll(force=false) {
    if (!isAdmin()) return;
    const view = document.getElementById('rag-admin-view');
    if (!force && !view?.classList.contains('active')) return;
    const requests = [
      ['overview',api('/super-admin/rag/overview')],
      ['settings',api('/super-admin/rag/settings')],
      ['health',api('/super-admin/rag/health')],
      ['projects',api('/ui/projects?limit=100')]
    ];
    const settled = await Promise.allSettled(requests.map(item => item[1]));
    s.partialErrors = [];
    settled.forEach((result,index) => {
      const key = requests[index][0];
      if (result.status === 'fulfilled') {
        if (key === 'projects') s.projects = Array.isArray(result.value) ? result.value : [];
        else s[key] = result.value || {};
      } else s.partialErrors.push(`${key}: ${result.reason?.message || 'indisponível'}`);
    });
    if (!s.projects.some(project => String(project.id) === String(s.selectedProject))) s.selectedProject = s.projects[0]?.id || '';
    render();
  }

  async function indexSelected() {
    const project = selected();
    if (!project || !enabled()) return;
    const button = document.getElementById('rag-index');
    if (button) button.disabled = true;
    try {
      const result = await api(`/super-admin/rag/projects/${encodeURIComponent(project.id)}/index`, {method:'POST'});
      toast(result.created ? 'Indexação RAG enfileirada' : 'Indexação RAG já está em andamento');
      s.retrieval = null;
      await loadAll(true);
    } catch (error) { toast(error.message); }
    finally { renderProject(); }
  }

  async function clearCache() {
    const project = selected();
    if (!project?.organization_id) return;
    try {
      await api(`/super-admin/rag/cache/${encodeURIComponent(project.organization_id)}/${encodeURIComponent(project.id)}`, {method:'DELETE'});
      s.retrieval = null;
      renderRetrieval();
      toast('Cache RAG do projeto limpo');
    } catch (error) { toast(error.message); }
  }

  async function retrieve() {
    const project = selected();
    const input = document.getElementById('rag-query');
    const button = document.getElementById('rag-retrieve');
    const query = String(input?.value || '').trim();
    if (!project?.organization_id || !query || !enabled()) return;
    if (button) button.disabled = true;
    try {
      s.retrieval = await api(`/super-admin/rag/projects/${encodeURIComponent(project.id)}/retrieve`, {
        method:'POST', body:JSON.stringify({query, diagnostic:true})
      });
      renderRetrieval();
    } catch (error) {
      s.retrieval = null;
      renderRetrieval();
      toast(error.message);
    } finally { if (button) button.disabled = false; }
  }

  function init() {
    panel();
    if (document.getElementById('rag-admin-view')?.classList.contains('active')) void loadAll(true);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
  document.addEventListener('devpilot:dashboard-revealed', init);
  document.addEventListener('devpilot:feature-ready', event => { if (event.detail?.feature === 'admin') init(); });
})();
