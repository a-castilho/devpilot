(() => {
  const CLOUD_ROLE = 'SUPER_ADMIN';
  const cloudState = {items: [], selected: '', resources: []};

  function isSuperAdmin() {
    return String(state.currentUser?.role || '').toUpperCase() === CLOUD_ROLE;
  }

  function html(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function safeUrl(value) {
    try {
      const url = new URL(String(value || ''));
      return ['https:', 'http:'].includes(url.protocol) ? url.href : '';
    } catch {
      return '';
    }
  }

  function ensureStyles() {
    if (document.getElementById('cloud-admin-styles')) return;
    const style = document.createElement('style');
    style.id = 'cloud-admin-styles';
    style.textContent = `
      .cloud-admin-grid{display:grid;grid-template-columns:minmax(220px,.75fr) minmax(0,1.6fr);gap:18px;align-items:start}
      .cloud-provider-list{display:grid;gap:10px}
      .cloud-provider{width:100%;text-align:left;border:1px solid var(--border,#26354a);background:transparent;color:inherit;border-radius:14px;padding:13px;cursor:pointer}
      .cloud-provider.active{border-color:#36d399;box-shadow:inset 3px 0 #36d399}
      .cloud-provider-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
      .cloud-provider small{display:block;margin-top:5px;opacity:.7}
      .cloud-admin-form{display:grid;gap:14px}
      .cloud-admin-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
      .cloud-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:16px}
      .cloud-metric{border:1px solid var(--border,#26354a);border-radius:14px;padding:12px}
      .cloud-metric strong{display:block;font-size:22px;margin-top:4px}
      .cloud-resource-list{display:grid;gap:8px;margin-top:12px}
      .cloud-resource{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(90px,.7fr) minmax(80px,.5fr) auto;gap:10px;align-items:center;border:1px solid var(--border,#26354a);border-radius:12px;padding:10px 12px}
      .cloud-resource small{opacity:.68}
      .cloud-empty{padding:16px;border:1px dashed var(--border,#26354a);border-radius:12px;opacity:.75}
      .cloud-secret-note{font-size:12px;opacity:.72;margin-top:-8px}
      @media(max-width:760px){
        .cloud-admin-grid{grid-template-columns:1fr}
        .cloud-summary{grid-template-columns:1fr}
        .cloud-resource{grid-template-columns:1fr auto}
        .cloud-resource .cloud-kind,.cloud-resource .cloud-status{grid-column:1}
        .cloud-admin-actions>*{flex:1 1 auto}
      }
    `;
    document.head.appendChild(style);
  }

  function ensurePanel() {
    if (!isSuperAdmin() || document.getElementById('cloud-admin-view')) return;
    ensureStyles();

    const nav = document.querySelector('.sidebar nav');
    if (!nav) return;

    const button = document.createElement('button');
    button.className = 'nav';
    button.type = 'button';
    button.dataset.view = 'cloud-admin';
    button.textContent = 'Clouds';
    nav.insertBefore(
      button,
      nav.querySelector('[data-view="deploy-admin"]') || nav.querySelector('[data-view="reports"]') || null,
    );

    const section = document.createElement('section');
    section.className = 'view';
    section.id = 'cloud-admin-view';
    section.innerHTML = `
      <div class="section-head">
        <div>
          <p>Central do Super Admin para credenciais, conexão e inventário de Vercel, Render, Neon e GitHub.</p>
        </div>
        <button class="ghost" type="button" id="cloud-admin-refresh">Atualizar</button>
      </div>

      <div id="cloud-admin-summary" class="cloud-summary"></div>

      <div class="cloud-admin-grid">
        <article class="panel">
          <div class="panel-title">
            <div><span class="eyebrow">SUPER ADMIN</span><h3>Clouds</h3></div>
          </div>
          <div id="cloud-provider-list" class="cloud-provider-list">
            <div class="cloud-empty">Carregando clouds...</div>
          </div>
        </article>

        <article class="panel">
          <form id="cloud-admin-form" class="cloud-admin-form">
            <div class="panel-title">
              <div>
                <span class="eyebrow">CREDENCIAL CRIPTOGRAFADA</span>
                <h3 id="cloud-admin-title">Selecione um cloud</h3>
              </div>
              <span id="cloud-admin-badge" class="status">—</span>
            </div>

            <label id="cloud-scope-wrap">Escopo
              <input name="scope" maxlength="200" autocomplete="off">
            </label>

            <label>Token / API key
              <input name="secret" type="password" minlength="8" maxlength="10000" autocomplete="new-password"
                placeholder="Cole somente para cadastrar ou trocar">
            </label>
            <div class="cloud-secret-note">
              O token nunca volta para o navegador. Se já estiver configurado, deixe este campo vazio para mantê-lo.
            </div>

            <label class="check"><input name="enabled" type="checkbox"> Cloud ativo no DevPilot</label>

            <div class="cloud-admin-actions">
              <button class="primary" type="submit" id="cloud-admin-save">Salvar</button>
              <button class="ghost" type="button" id="cloud-admin-test">Testar conexão</button>
              <button class="ghost" type="button" id="cloud-admin-resources">Carregar recursos</button>
              <button class="ghost" type="button" id="cloud-admin-console">Abrir console</button>
              <button class="ghost" type="button" id="cloud-admin-delete">Remover</button>
            </div>
          </form>

          <div style="margin-top:18px">
            <div class="panel-title">
              <div><span class="eyebrow">INVENTÁRIO</span><h3>Recursos do cloud</h3></div>
              <span id="cloud-resource-count" class="status">0</span>
            </div>
            <div id="cloud-resource-list" class="cloud-resource-list">
              <div class="cloud-empty">Carregue os recursos para visualizar projetos e serviços.</div>
            </div>
          </div>
        </article>
      </div>
    `;

    const deploy = document.getElementById('deploy-admin-view');
    const reports = document.getElementById('reports-view');
    const anchor = deploy || reports;
    (anchor?.parentNode || document.querySelector('main')).insertBefore(section, anchor || null);

    button.addEventListener('click', () => openView(button, section));
    section.querySelector('#cloud-admin-refresh').addEventListener('click', () => loadClouds(true));
    section.querySelector('#cloud-admin-form').addEventListener('submit', saveCloud);
    section.querySelector('#cloud-admin-test').addEventListener('click', testCloud);
    section.querySelector('#cloud-admin-resources').addEventListener('click', loadResources);
    section.querySelector('#cloud-admin-console').addEventListener('click', openConsole);
    section.querySelector('#cloud-admin-delete').addEventListener('click', deleteCloud);
  }

  function openView(button, section) {
    if (!isSuperAdmin()) return toast('Acesso exclusivo do Super Admin');
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button));
    const title = document.getElementById('page-title');
    if (title) title.textContent = 'Clouds';
    loadClouds();
  }

  function current() {
    return cloudState.items.find(item => item.provider === cloudState.selected) || null;
  }

  function renderSummary() {
    const target = document.getElementById('cloud-admin-summary');
    if (!target) return;
    const configured = cloudState.items.filter(item => item.configured).length;
    const enabled = cloudState.items.filter(item => item.enabled).length;
    target.innerHTML = `
      <div class="cloud-metric"><span class="eyebrow">CLOUDS</span><strong>${cloudState.items.length}</strong><small>integráveis</small></div>
      <div class="cloud-metric"><span class="eyebrow">CONFIGURADOS</span><strong>${configured}</strong><small>com credencial salva</small></div>
      <div class="cloud-metric"><span class="eyebrow">ATIVOS</span><strong>${enabled}</strong><small>disponíveis ao DevPilot</small></div>
    `;
  }

  function renderProviders() {
    const target = document.getElementById('cloud-provider-list');
    if (!target) return;
    target.innerHTML = cloudState.items.map(item => `
      <button class="cloud-provider ${item.provider === cloudState.selected ? 'active' : ''}"
        type="button" data-cloud="${html(item.provider)}">
        <span class="cloud-provider-head">
          <strong>${html(item.name)}</strong>
          <span class="status">${item.enabled ? 'ATIVO' : (item.configured ? 'PAUSADO' : 'NOVO')}</span>
        </span>
        <small>${item.configured ? 'credencial protegida no vault' : 'não configurado'}</small>
        <small>${item.scope ? `escopo: ${html(item.scope)}` : 'escopo padrão'}</small>
      </button>
    `).join('');

    target.querySelectorAll('[data-cloud]').forEach(button => {
      button.addEventListener('click', () => {
        cloudState.selected = button.dataset.cloud;
        cloudState.resources = [];
        renderProviders();
        fillForm();
        renderResources();
      });
    });
  }

  function fillForm() {
    const item = current();
    const form = document.getElementById('cloud-admin-form');
    if (!item || !form) return;
    document.getElementById('cloud-admin-title').textContent = item.name;
    document.getElementById('cloud-admin-badge').textContent = item.configured
      ? (item.enabled ? 'ATIVO' : 'PAUSADO')
      : 'NÃO CONFIGURADO';
    form.elements.scope.value = item.scope || '';
    form.elements.secret.value = '';
    form.elements.secret.placeholder = item.configured
      ? 'Token já salvo — deixe vazio para manter'
      : 'Cole o token / API key';
    form.elements.enabled.checked = Boolean(item.enabled);
    const scopeWrap = document.getElementById('cloud-scope-wrap');
    if (scopeWrap) {
      const textNode = scopeWrap.firstChild;
      if (textNode) textNode.textContent = `${item.scope_label || 'Escopo'} `;
    }
    const remove = document.getElementById('cloud-admin-delete');
    if (remove) remove.disabled = !item.configured;
  }

  function renderResources() {
    const target = document.getElementById('cloud-resource-list');
    const count = document.getElementById('cloud-resource-count');
    if (!target || !count) return;
    count.textContent = String(cloudState.resources.length);
    if (!cloudState.resources.length) {
      target.innerHTML = '<div class="cloud-empty">Nenhum recurso carregado.</div>';
      return;
    }
    target.innerHTML = cloudState.resources.map(resource => {
      const url = safeUrl(resource.url);
      return `
        <div class="cloud-resource">
          <div><strong>${html(resource.name)}</strong><small>${html(resource.id)}</small></div>
          <div class="cloud-kind"><small>tipo</small><div>${html(resource.kind || '—')}</div></div>
          <div class="cloud-status"><small>status</small><div>${html(resource.status || '—')}</div></div>
          <div>${url ? `<a class="ghost" href="${html(url)}" target="_blank" rel="noopener">Abrir</a>` : ''}</div>
        </div>
      `;
    }).join('');
  }

  async function loadClouds(force = false) {
    if (!isSuperAdmin()) return;
    const active = document.getElementById('cloud-admin-view')?.classList.contains('active');
    if (!active && !force) return;
    try {
      cloudState.items = await api('/admin/clouds');
      if (!cloudState.selected || !cloudState.items.some(item => item.provider === cloudState.selected)) {
        cloudState.selected = cloudState.items[0]?.provider || '';
      }
      renderSummary();
      renderProviders();
      fillForm();
    } catch (error) {
      toast(error.message);
    }
  }

  async function saveCloud(event) {
    event.preventDefault();
    const item = current();
    if (!item) return toast('Selecione um cloud');
    const form = event.currentTarget;
    const payload = {
      secret: form.elements.secret.value.trim() || null,
      enabled: form.elements.enabled.checked,
      scope: form.elements.scope.value.trim(),
    };
    const button = document.getElementById('cloud-admin-save');
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Salvando...';
    try {
      await api(`/admin/clouds/${item.provider}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      toast(`${item.name} atualizado`);
      await loadClouds(true);
    } catch (error) {
      toast(error.message);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  async function testCloud() {
    const item = current();
    if (!item?.configured) return toast('Salve a credencial antes de testar');
    const button = document.getElementById('cloud-admin-test');
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Testando...';
    try {
      const result = await api(`/admin/clouds/${item.provider}/test`, {method: 'POST'});
      const detail = result.identity
        ? ` conectado como ${result.identity}`
        : (Number.isInteger(result.resource_count) ? ` · ${result.resource_count} recurso(s) visíveis` : '');
      toast(`${item.name}: conexão OK${detail}`);
    } catch (error) {
      toast(error.message);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  async function loadResources() {
    const item = current();
    if (!item?.configured) return toast('Configure o cloud primeiro');
    if (!item.enabled) return toast('Ative o cloud para listar recursos');
    const button = document.getElementById('cloud-admin-resources');
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Carregando...';
    try {
      const result = await api(`/admin/clouds/${item.provider}/resources`);
      cloudState.resources = Array.isArray(result.resources) ? result.resources : [];
      renderResources();
      toast(`${cloudState.resources.length} recurso(s) carregado(s)`);
    } catch (error) {
      toast(error.message);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function openConsole() {
    const item = current();
    const url = safeUrl(item?.dashboard_url);
    if (!url) return toast('Console indisponível');
    window.open(url, '_blank', 'noopener');
  }

  async function deleteCloud() {
    const item = current();
    if (!item?.configured) return;
    if (!window.confirm(`Remover a credencial ${item.name} do DevPilot?`)) return;
    try {
      await api(`/admin/clouds/${item.provider}`, {method: 'DELETE'});
      cloudState.resources = [];
      toast(`${item.name}: credencial removida`);
      await loadClouds(true);
      renderResources();
    } catch (error) {
      toast(error.message);
    }
  }

  let checks = 0;
  const waitForRole = () => {
    checks += 1;
    if (state.currentUser) {
      ensurePanel();
      return;
    }
    if (checks < 40) setTimeout(waitForRole, 250);
  };
  waitForRole();
})();
