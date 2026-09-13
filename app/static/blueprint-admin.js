(() => {
  'use strict';

  const ROLE = 'SUPER_ADMIN';
  const stateBp = {items: [], metrics: {}, selected: null, recommendations: [], loading: false};
  const esc = value => String(value ?? '')
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const isAdmin = () => String(window.state?.currentUser?.role || '').toUpperCase() === ROLE;
  const token = () => String(localStorage.getItem('devpilot-token') || '').trim();

  async function api(path, options = {}) {
    const headers = {...(options.headers || {}), Authorization: `Bearer ${token()}`};
    if (options.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {...options, headers, cache: 'no-store'});
    const data = response.status === 204 ? null : await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data?.detail === 'string' ? data.detail : `HTTP ${response.status}`;
      throw new Error(detail);
    }
    return data;
  }

  function installStyles() {
    if (document.getElementById('blueprint-admin-styles')) return;
    const style = document.createElement('style');
    style.id = 'blueprint-admin-styles';
    style.textContent = `
      .bp-admin-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0}.bp-card,.bp-list-item,.bp-detail,.bp-form-card{border:1px solid var(--border,#26354a);border-radius:14px;background:rgba(255,255,255,.015)}.bp-card{padding:14px}.bp-card strong{display:block;font-size:24px;margin-top:5px}.bp-card small{opacity:.68}.bp-layout{display:grid;grid-template-columns:minmax(280px,.85fr) minmax(0,1.55fr);gap:16px;align-items:start}.bp-list{display:grid;gap:8px}.bp-list-item{width:100%;padding:12px;text-align:left;color:inherit;cursor:pointer}.bp-list-item.active{border-color:#36d399;box-shadow:inset 3px 0 #36d399}.bp-list-item small{display:block;opacity:.7;margin-top:4px}.bp-badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.bp-badge{font-size:11px;border:1px solid var(--border,#26354a);border-radius:999px;padding:3px 7px}.bp-detail,.bp-form-card{padding:14px}.bp-detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.bp-kv{border:1px solid var(--border,#26354a);border-radius:10px;padding:10px}.bp-kv small{display:block;opacity:.6}.bp-kv strong{overflow-wrap:anywhere}.bp-actions{display:flex;gap:8px;flex-wrap:wrap}.bp-actions button{min-width:120px}.bp-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.bp-form-grid label{display:grid;gap:5px;font-size:12px}.bp-form-grid .full{grid-column:1/-1}.bp-form-grid textarea{min-height:88px;resize:vertical}.bp-note{padding:10px 12px;border:1px solid var(--border,#26354a);border-radius:12px;margin:10px 0}.bp-note.error{border-color:#be123c}.bp-note.ok{border-color:#16a34a}.bp-recommendations{display:grid;gap:8px;margin-top:10px}.bp-recommendation{border:1px solid var(--border,#26354a);border-radius:12px;padding:10px}.bp-recommendation strong{display:flex;justify-content:space-between;gap:10px}.bp-json{white-space:pre-wrap;overflow-wrap:anywhere;max-height:280px;overflow:auto;font-size:12px;background:rgba(0,0,0,.18);padding:10px;border-radius:10px}.bp-toolbar{display:flex;gap:8px;flex-wrap:wrap}.bp-empty{padding:16px;border:1px dashed var(--border,#26354a);border-radius:12px;opacity:.75}
      @media(max-width:900px){.bp-admin-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.bp-layout,.bp-detail-grid,.bp-form-grid{grid-template-columns:1fr}.bp-form-grid .full{grid-column:auto}}
      @media(max-width:560px){.bp-admin-grid{grid-template-columns:1fr 1fr}.bp-card{padding:10px}.bp-card strong{font-size:19px}.bp-actions button{flex:1 1 auto}.bp-toolbar>*{flex:1 1 auto}}
    `;
    document.head.appendChild(style);
  }

  function ensurePanel() {
    if (!isAdmin() || document.getElementById('blueprints-admin-view')) return;
    const nav = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!nav || !main) return;
    installStyles();

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'nav';
    button.dataset.view = 'blueprints-admin';
    button.dataset.superAdmin = 'true';
    button.textContent = 'Blueprints';
    nav.insertBefore(button, nav.querySelector('[data-view="rag-admin"]') || nav.querySelector('[data-view="cloud-admin"]') || nav.querySelector('[data-view="reports"]') || null);

    const view = document.createElement('section');
    view.className = 'view';
    view.id = 'blueprints-admin-view';
    view.innerHTML = `
      <div class="section-head">
        <div><span class="eyebrow">SUPER ADMIN · REUTILIZAÇÃO</span><h2>Blueprints de projeto</h2><p>Catálogo versionado de arquiteturas reutilizáveis, métricas, seleção automática e cadastro de novas bases.</p></div>
        <div class="bp-toolbar"><button class="ghost" id="bp-refresh">Atualizar</button><button class="primary" id="bp-new">Novo Blueprint</button></div>
      </div>
      <div id="bp-note"></div>
      <div class="bp-admin-grid" id="bp-summary"></div>
      <div class="bp-layout">
        <article class="panel"><div class="panel-title"><div><span class="eyebrow">REGISTRY</span><h3>Blueprints disponíveis</h3></div></div><div class="bp-list" id="bp-list"></div></article>
        <article class="panel"><div id="bp-detail"></div></article>
      </div>
      <div class="bp-form-card" style="margin-top:16px">
        <div class="panel-title"><div><span class="eyebrow">MATCHER</span><h3>Testar seleção automática</h3></div></div>
        <div class="bp-form-grid">
          <label class="full">Descrição do projeto<textarea id="bp-match-description" placeholder="Ex.: SaaS com FastAPI, React, PostgreSQL, login, dashboard e deploy"></textarea></label>
          <label>Stack <input id="bp-match-stack" placeholder="backend=fastapi,frontend=react,database=postgresql"></label>
          <label>Capabilities <input id="bp-match-capabilities" placeholder="auth,dashboard,docker,deploy"></label>
          <label>Tags <input id="bp-match-tags" placeholder="saas,fullstack"></label>
          <label>Score mínimo <input id="bp-match-score" type="number" step="0.05" min="0" max="1" value="0.35"></label>
        </div>
        <div class="bp-actions" style="margin-top:10px"><button class="primary" id="bp-run-match">Executar matcher</button></div>
        <div class="bp-recommendations" id="bp-recommendations"></div>
      </div>
      <div class="bp-form-card" id="bp-create-card" style="margin-top:16px" hidden>
        <div class="panel-title"><div><span class="eyebrow">SUPER ADMIN</span><h3>Cadastrar versão</h3></div></div>
        <div class="bp-form-grid">
          <label>Slug <input id="bp-create-slug" placeholder="fullstack-fastapi-react-postgres"></label>
          <label>Nome <input id="bp-create-name" placeholder="FastAPI + React + PostgreSQL"></label>
          <label>Versão <input id="bp-create-version" value="1.0.0"></label>
          <label>Status <select id="bp-create-status"><option>experimental</option><option>candidate</option><option>stable</option><option>deprecated</option></select></label>
          <label>Tipo <input id="bp-create-kind" value="fullstack"></label>
          <label>Capabilities <input id="bp-create-capabilities" placeholder="auth,docker,health-check"></label>
          <label class="full">Descrição <textarea id="bp-create-description"></textarea></label>
          <label class="full">Stack JSON <textarea id="bp-create-stack">{"backend":"fastapi","frontend":"react","database":"postgresql"}</textarea></label>
          <label class="full">Parâmetros, separados por vírgula <input id="bp-create-parameters" placeholder="project_name,repository_name,database_name"></label>
          <label class="full">Tags <input id="bp-create-tags" placeholder="saas,fullstack"></label>
          <label class="full">Arquivos JSON <textarea id="bp-create-files" placeholder='[{"path":"README.md","content":"# {{ project_name }}"}]'></textarea></label>
        </div>
        <div class="bp-actions" style="margin-top:10px"><button class="primary" id="bp-save">Salvar Blueprint</button><button class="ghost" id="bp-cancel">Cancelar</button></div>
      </div>`;
    main.appendChild(view);

    button.onclick = () => {
      document.querySelectorAll('.view').forEach(item => item.classList.toggle('active', item === view));
      document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button));
      void loadAll();
    };
    view.querySelector('#bp-refresh').onclick = () => loadAll(true);
    view.querySelector('#bp-new').onclick = () => toggleCreate(true);
    view.querySelector('#bp-cancel').onclick = () => toggleCreate(false);
    view.querySelector('#bp-run-match').onclick = runMatcher;
    view.querySelector('#bp-save').onclick = saveBlueprint;
  }

  function note(message = '', kind = '') {
    const target = document.getElementById('bp-note');
    if (!target) return;
    target.innerHTML = message ? `<div class="bp-note ${kind}">${esc(message)}</div>` : '';
  }

  function renderSummary() {
    const target = document.getElementById('bp-summary');
    if (!target) return;
    const metrics = stateBp.metrics || {};
    const total = stateBp.items.length;
    const stable = stateBp.items.filter(item => item.status === 'stable').length;
    const usage = Number(metrics.total_usage || metrics.projects_created || 0);
    const success = Number(metrics.successful_projects || metrics.success || 0);
    const rate = usage ? Math.round(success / usage * 100) : 0;
    target.innerHTML = `
      <div class="bp-card"><span class="eyebrow">CATÁLOGO</span><strong>${total}</strong><small>blueprints ativos</small></div>
      <div class="bp-card"><span class="eyebrow">ESTÁVEIS</span><strong>${stable}</strong><small>preferidos pelo matcher</small></div>
      <div class="bp-card"><span class="eyebrow">USOS</span><strong>${usage}</strong><small>seleções registradas</small></div>
      <div class="bp-card"><span class="eyebrow">SUCESSO</span><strong>${rate}%</strong><small>quando há histórico</small></div>`;
  }

  function renderList() {
    const target = document.getElementById('bp-list');
    if (!target) return;
    if (!stateBp.items.length) {
      target.innerHTML = '<div class="bp-empty">Nenhum Blueprint cadastrado.</div>';
      return;
    }
    target.innerHTML = stateBp.items.map(item => `
      <button class="bp-list-item ${stateBp.selected?.slug === item.slug ? 'active' : ''}" data-slug="${esc(item.slug)}">
        <strong>${esc(item.name)}</strong><small>${esc(item.slug)} · v${esc(item.version)} · ${esc(item.status)}</small>
        <div class="bp-badges">${Object.values(item.stack || {}).slice(0,4).map(value => `<span class="bp-badge">${esc(value)}</span>`).join('')}</div>
      </button>`).join('');
    target.querySelectorAll('[data-slug]').forEach(button => button.onclick = () => selectBlueprint(button.dataset.slug));
  }

  function renderDetail() {
    const target = document.getElementById('bp-detail');
    if (!target) return;
    const item = stateBp.selected;
    if (!item) {
      target.innerHTML = '<div class="bp-empty">Selecione um Blueprint para ver detalhes.</div>';
      return;
    }
    target.innerHTML = `
      <div class="panel-title"><div><span class="eyebrow">BLUEPRINT</span><h3>${esc(item.name)}</h3></div><span class="status">${esc(item.status)}</span></div>
      <div class="bp-detail-grid">
        <div class="bp-kv"><small>Slug</small><strong>${esc(item.slug)}</strong></div>
        <div class="bp-kv"><small>Versão</small><strong>${esc(item.version)}</strong></div>
        <div class="bp-kv"><small>Tipo</small><strong>${esc(item.kind || 'generic')}</strong></div>
        <div class="bp-kv"><small>Arquivos</small><strong>${(item.files || []).length}</strong></div>
      </div>
      <p>${esc(item.description || 'Sem descrição.')}</p>
      <div class="bp-badges">${(item.capabilities || []).map(value => `<span class="bp-badge">${esc(value)}</span>`).join('')}</div>
      <h4>Stack</h4><pre class="bp-json">${esc(JSON.stringify(item.stack || {}, null, 2))}</pre>
      <h4>Parâmetros</h4><pre class="bp-json">${esc(JSON.stringify(item.parameters || [], null, 2))}</pre>
      <h4>Manifest</h4><details><summary>Ver JSON completo</summary><pre class="bp-json">${esc(JSON.stringify(item, null, 2))}</pre></details>`;
  }

  function renderRecommendations() {
    const target = document.getElementById('bp-recommendations');
    if (!target) return;
    target.innerHTML = stateBp.recommendations.length ? stateBp.recommendations.map((item, index) => `
      <div class="bp-recommendation"><strong><span>#${index + 1} ${esc(item.blueprint?.name || item.slug || item.blueprint_slug || '')}</span><span>${Math.round(Number(item.score || 0) * 100)}%</span></strong><small>${esc((item.reasons || []).join(' · '))}</small></div>`).join('') : '';
  }

  function toggleCreate(show) {
    const card = document.getElementById('bp-create-card');
    if (card) card.hidden = !show;
    if (show) card?.scrollIntoView({behavior:'smooth', block:'start'});
  }

  async function loadAll(force = false) {
    if (stateBp.loading && !force) return;
    stateBp.loading = true;
    note('Carregando catálogo de Blueprints...');
    try {
      const [items, metrics] = await Promise.all([api('/api/blueprints?latest_only=true'), api('/api/blueprints/metrics')]);
      stateBp.items = Array.isArray(items) ? items : [];
      stateBp.metrics = metrics || {};
      if (stateBp.selected) stateBp.selected = stateBp.items.find(item => item.slug === stateBp.selected.slug) || null;
      if (!stateBp.selected && stateBp.items.length) stateBp.selected = stateBp.items[0];
      note('');
      renderSummary(); renderList(); renderDetail();
    } catch (error) {
      note(`Falha ao carregar Blueprints: ${error.message}`, 'error');
    } finally {
      stateBp.loading = false;
    }
  }

  async function selectBlueprint(slug) {
    try {
      stateBp.selected = await api(`/api/blueprints/${encodeURIComponent(slug)}`);
      renderList(); renderDetail();
    } catch (error) {
      note(error.message, 'error');
    }
  }

  function csv(value) {
    return String(value || '').split(',').map(item => item.trim()).filter(Boolean);
  }

  function stackValue(value) {
    const result = {};
    csv(value).forEach(item => {
      const [key, ...rest] = item.split('=');
      if (key && rest.length) result[key.trim()] = rest.join('=').trim();
    });
    return result;
  }

  async function runMatcher() {
    try {
      const payload = {
        description: document.getElementById('bp-match-description').value,
        stack: stackValue(document.getElementById('bp-match-stack').value),
        capabilities: csv(document.getElementById('bp-match-capabilities').value),
        tags: csv(document.getElementById('bp-match-tags').value),
        minimum_score: Number(document.getElementById('bp-match-score').value || 0.35),
        limit: 5,
      };
      stateBp.recommendations = await api('/api/blueprints/recommend', {method:'POST', body:JSON.stringify(payload)}) || [];
      renderRecommendations();
      note(stateBp.recommendations.length ? 'Matcher executado com sucesso.' : 'Nenhum Blueprint atingiu o score mínimo.', stateBp.recommendations.length ? 'ok' : '');
    } catch (error) {
      note(`Falha no matcher: ${error.message}`, 'error');
    }
  }

  async function saveBlueprint() {
    try {
      const parseJson = (id, fallback) => {
        const raw = document.getElementById(id).value.trim();
        return raw ? JSON.parse(raw) : fallback;
      };
      const payload = {
        slug: document.getElementById('bp-create-slug').value.trim(),
        name: document.getElementById('bp-create-name').value.trim(),
        version: document.getElementById('bp-create-version').value.trim(),
        description: document.getElementById('bp-create-description').value.trim(),
        kind: document.getElementById('bp-create-kind').value.trim() || 'generic',
        status: document.getElementById('bp-create-status').value,
        stack: parseJson('bp-create-stack', {}),
        capabilities: csv(document.getElementById('bp-create-capabilities').value),
        parameters: csv(document.getElementById('bp-create-parameters').value),
        files: parseJson('bp-create-files', []),
        tags: csv(document.getElementById('bp-create-tags').value),
        metadata: {},
        overwrite: false,
      };
      if (!payload.slug || !payload.name || !payload.version) throw new Error('Slug, nome e versão são obrigatórios.');
      const created = await api('/api/blueprints', {method:'POST', body:JSON.stringify(payload)});
      stateBp.selected = created;
      toggleCreate(false);
      await loadAll(true);
      note(`Blueprint ${created.slug} v${created.version} salvo.`, 'ok');
    } catch (error) {
      note(`Não foi possível salvar: ${error.message}`, 'error');
    }
  }

  function boot() {
    ensurePanel();
    if (!document.getElementById('blueprints-admin-view')) setTimeout(ensurePanel, 700);
  }

  document.addEventListener('devpilot:authenticated-core-ready', boot, {once:true});
  document.addEventListener('devpilot:authenticated-ui-ready', boot, {once:true});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 400), {once:true});
  else setTimeout(boot, 400);
})();
