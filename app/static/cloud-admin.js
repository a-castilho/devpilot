(() => {
  const CLOUD_ROLE = 'SUPER_ADMIN';
  const cloudState = {items: [], selected: '', resources: [], renderProvision: null, renderTimer: null};

  const byId = id => document.getElementById(id);
  const isSuperAdmin = () => String(state.currentUser?.role || '').toUpperCase() === CLOUD_ROLE;
  const html = value => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

  function safeUrl(value) {
    try {
      const url = new URL(String(value || ''));
      return ['https:', 'http:'].includes(url.protocol) ? url.href : '';
    } catch { return ''; }
  }

  function ensureStyles() {
    if (byId('cloud-admin-styles')) return;
    const style = document.createElement('style');
    style.id = 'cloud-admin-styles';
    style.textContent = `
      .cloud-admin-grid{display:grid;grid-template-columns:minmax(220px,.75fr) minmax(0,1.6fr);gap:18px;align-items:start}
      .cloud-provider-list{display:grid;gap:10px}
      .cloud-provider{width:100%;text-align:left;border:1px solid var(--border,#26354a);background:transparent;color:inherit;border-radius:14px;padding:13px;cursor:pointer}
      .cloud-provider.active{border-color:#36d399;box-shadow:inset 3px 0 #36d399}
      .cloud-provider-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
      .cloud-provider small{display:block;margin-top:5px;opacity:.7}
      .cloud-admin-form{display:grid;gap:14px}.cloud-admin-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
      .cloud-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:16px}
      .cloud-metric{border:1px solid var(--border,#26354a);border-radius:14px;padding:12px}.cloud-metric strong{display:block;font-size:22px;margin-top:4px}
      .cloud-license-note{display:flex;gap:10px;align-items:flex-start;justify-content:space-between;margin-bottom:16px;border-color:#36d399;background:rgba(54,211,153,.06)}
      .cloud-license-note strong{white-space:nowrap}.cloud-license-note span{opacity:.8;line-height:1.45}
      .cloud-resource-list{display:grid;gap:8px;margin-top:12px}.cloud-resource{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(90px,.7fr) minmax(80px,.5fr) auto;gap:10px;align-items:center;border:1px solid var(--border,#26354a);border-radius:12px;padding:10px 12px}.cloud-resource small{opacity:.68}
      .cloud-empty{padding:16px;border:1px dashed var(--border,#26354a);border-radius:12px;opacity:.75}.cloud-secret-note{font-size:12px;opacity:.72;margin-top:-8px}.cloud-admin-mobile-save{display:none}
      .cloud-render-box{display:none;border:1px solid var(--border,#26354a);border-radius:14px;padding:14px;gap:10px}.cloud-render-box.visible{display:grid}.cloud-render-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.cloud-render-detail{font-size:13px;opacity:.78;line-height:1.5}.cloud-render-actions{display:flex;gap:10px;flex-wrap:wrap}.cloud-render-actions>*{min-height:44px}
      @media(max-width:760px){
        .cloud-admin-grid,.cloud-summary{grid-template-columns:1fr}.cloud-license-note{display:grid}.cloud-resource{grid-template-columns:1fr auto}.cloud-resource .cloud-kind,.cloud-resource .cloud-status{grid-column:1}
        .cloud-admin-actions,.cloud-render-actions{display:grid;grid-template-columns:1fr;gap:10px;width:100%}.cloud-admin-actions>*,.cloud-render-actions>*{width:100%!important;min-width:0}
        #cloud-admin-save{display:none!important}.cloud-admin-mobile-save{display:block!important;width:100%!important;min-height:54px!important;visibility:visible!important;opacity:1!important;position:static!important;pointer-events:auto!important}
      }
    `;
    document.head.appendChild(style);
  }

  function ensurePanel() {
    if (!isSuperAdmin() || byId('cloud-admin-view')) return;
    ensureStyles();
    const nav = document.querySelector('.sidebar nav');
    if (!nav) return;
    const navButton = document.createElement('button');
    navButton.className = 'nav'; navButton.type = 'button'; navButton.dataset.view = 'cloud-admin'; navButton.textContent = 'Clouds';
    nav.insertBefore(navButton, nav.querySelector('[data-view="deploy-admin"]') || nav.querySelector('[data-view="reports"]') || null);

    const section = document.createElement('section');
    section.className = 'view'; section.id = 'cloud-admin-view';
    section.innerHTML = `
      <div class="section-head"><div><p>Credenciais próprias para instalação self-managed/licença do código. Usuários de teste usam a infraestrutura gerenciada do DevPilot automaticamente.</p></div><button class="ghost" type="button" id="cloud-admin-refresh">Atualizar</button></div>
      <div class="panel cloud-license-note"><strong>🔐 Código adquirido / self-managed</strong><span>Cadastre tokens somente quando a instalação precisar operar nas contas cloud do comprador. No teste do DevPilot, o cliente não cadastra, recebe nem visualiza credenciais: o backend usa a cloud gerenciada como experiência de demonstração.</span></div>
      <div id="cloud-admin-summary" class="cloud-summary"></div>
      <div class="cloud-admin-grid">
        <article class="panel"><div class="panel-title"><div><span class="eyebrow">SUPER ADMIN</span><h3>Clouds</h3></div></div><div id="cloud-provider-list" class="cloud-provider-list"><div class="cloud-empty">Carregando clouds...</div></div></article>
        <article class="panel">
          <form id="cloud-admin-form" class="cloud-admin-form">
            <div class="panel-title"><div><span class="eyebrow">CREDENCIAL CRIPTOGRAFADA</span><h3 id="cloud-admin-title">Selecione um cloud</h3></div><span id="cloud-admin-badge" class="status">—</span></div>
            <label id="cloud-scope-wrap">Escopo<input name="scope" maxlength="200" autocomplete="off"></label>
            <label>Token / API key<input name="secret" type="password" minlength="8" maxlength="10000" autocomplete="new-password" data-lpignore="true" data-1p-ignore="true" placeholder="Cole somente para cadastrar ou trocar"></label>
            <div class="cloud-secret-note">O token nunca volta para o navegador. Se já estiver configurado, deixe este campo vazio para mantê-lo.</div>
            <label class="check"><input name="enabled" type="checkbox"> Cloud ativo no DevPilot</label>
            <button class="primary cloud-admin-mobile-save" type="button" id="cloud-admin-save-mobile">Salvar credencial</button>
            <div class="cloud-admin-actions"><button class="primary" type="submit" id="cloud-admin-save">Salvar</button><button class="ghost" type="button" id="cloud-admin-test">Testar conexão</button><button class="ghost" type="button" id="cloud-admin-resources">Carregar recursos</button><button class="ghost" type="button" id="cloud-admin-console">Abrir console</button><button class="ghost" type="button" id="cloud-admin-delete">Remover</button></div>
          </form>
          <div id="cloud-render-box" class="cloud-render-box" style="margin-top:16px">
            <div class="cloud-render-head"><div><span class="eyebrow">HOMOLOGAÇÃO DOCKER</span><h3 style="margin:2px 0 0">Render</h3></div><span id="cloud-render-status" class="status">NÃO INICIADO</span></div>
            <div id="cloud-render-detail" class="cloud-render-detail">O provisionamento é assíncrono: a requisição apenas inicia o serviço. O DevPilot acompanha o deploy sem manter a conexão HTTP aberta.</div>
            <div class="cloud-render-actions"><button class="primary" type="button" id="cloud-render-provision">Provisionar homologação</button><button class="ghost" type="button" id="cloud-render-check">Verificar status</button><a class="ghost" id="cloud-render-open" href="#" target="_blank" rel="noopener" style="display:none">Abrir homologação</a></div>
          </div>
          <div style="margin-top:18px"><div class="panel-title"><div><span class="eyebrow">INVENTÁRIO</span><h3>Recursos do cloud</h3></div><span id="cloud-resource-count" class="status">0</span></div><div id="cloud-resource-list" class="cloud-resource-list"><div class="cloud-empty">Carregue os recursos para visualizar projetos e serviços.</div></div></div>
        </article>
      </div>`;
    const anchor = byId('deploy-admin-view') || byId('reports-view');
    (anchor?.parentNode || document.querySelector('main')).insertBefore(section, anchor || null);
    navButton.addEventListener('click', () => openView(navButton, section));
    byId('cloud-admin-refresh').addEventListener('click', () => loadClouds(true));
    byId('cloud-admin-form').addEventListener('submit', saveCloud);
    byId('cloud-admin-save-mobile').addEventListener('click', () => byId('cloud-admin-form')?.requestSubmit());
    byId('cloud-admin-test').addEventListener('click', testCloud);
    byId('cloud-admin-resources').addEventListener('click', loadResources);
    byId('cloud-admin-console').addEventListener('click', openConsole);
    byId('cloud-admin-delete').addEventListener('click', deleteCloud);
    byId('cloud-render-provision').addEventListener('click', provisionRender);
    byId('cloud-render-check').addEventListener('click', () => checkRenderProvision(true));
  }

  function openView(button, section) {
    if (!isSuperAdmin()) return toast('Acesso exclusivo do Super Admin');
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button));
    if (byId('page-title')) byId('page-title').textContent = 'Clouds';
    loadClouds();
  }

  const current = () => cloudState.items.find(item => item.provider === cloudState.selected) || null;

  function renderSummary() {
    const target = byId('cloud-admin-summary'); if (!target) return;
    const configured = cloudState.items.filter(item => item.configured).length;
    const enabled = cloudState.items.filter(item => item.enabled).length;
    target.innerHTML = `<div class="cloud-metric"><span class="eyebrow">CLOUDS</span><strong>${cloudState.items.length}</strong><small>integráveis</small></div><div class="cloud-metric"><span class="eyebrow">CONFIGURADOS</span><strong>${configured}</strong><small>com credencial salva</small></div><div class="cloud-metric"><span class="eyebrow">ATIVOS</span><strong>${enabled}</strong><small>disponíveis ao DevPilot</small></div>`;
  }

  function renderProviders() {
    const target = byId('cloud-provider-list'); if (!target) return;
    target.innerHTML = cloudState.items.map(item => `<button class="cloud-provider ${item.provider === cloudState.selected ? 'active' : ''}" type="button" data-cloud="${html(item.provider)}"><span class="cloud-provider-head"><strong>${html(item.name)}</strong><span class="status">${item.enabled ? 'ATIVO' : (item.configured ? 'PAUSADO' : 'NOVO')}</span></span><small>${item.configured ? 'credencial protegida no vault' : 'não configurado'}</small><small>${item.scope ? `escopo: ${html(item.scope)}` : 'escopo padrão'}</small></button>`).join('');
    target.querySelectorAll('[data-cloud]').forEach(button => button.addEventListener('click', () => {
      cloudState.selected = button.dataset.cloud; cloudState.resources = []; stopRenderPolling(); renderProviders(); fillForm(); renderResources(); renderRenderProvision();
      if (cloudState.selected === 'render' && current()?.configured) checkRenderProvision(false);
    }));
  }

  function fillForm() {
    const item = current(); const form = byId('cloud-admin-form'); if (!item || !form) return;
    byId('cloud-admin-title').textContent = item.name;
    byId('cloud-admin-badge').textContent = item.configured ? (item.enabled ? 'ATIVO' : 'PAUSADO') : 'NÃO CONFIGURADO';
    form.elements.scope.value = item.scope || ''; form.elements.secret.value = '';
    form.elements.secret.placeholder = item.configured ? 'Token já salvo — deixe vazio para manter' : 'Cole o token / API key';
    form.elements.enabled.checked = Boolean(item.enabled);
    const scopeWrap = byId('cloud-scope-wrap'); if (scopeWrap?.firstChild) scopeWrap.firstChild.textContent = `${item.scope_label || 'Escopo'} `;
    byId('cloud-admin-delete').disabled = !item.configured;
    renderRenderProvision();
  }

  function renderResources() {
    const target = byId('cloud-resource-list'); const count = byId('cloud-resource-count'); if (!target || !count) return;
    count.textContent = String(cloudState.resources.length);
    if (!cloudState.resources.length) { target.innerHTML = '<div class="cloud-empty">Nenhum recurso carregado.</div>'; return; }
    target.innerHTML = cloudState.resources.map(resource => {
      const url = safeUrl(resource.url);
      return `<div class="cloud-resource"><div><strong>${html(resource.name)}</strong><small>${html(resource.id)}</small></div><div class="cloud-kind"><small>tipo</small><div>${html(resource.kind || '—')}</div></div><div class="cloud-status"><small>status</small><div>${html(resource.status || '—')}</div></div><div>${url ? `<a class="ghost" href="${html(url)}" target="_blank" rel="noopener">Abrir</a>` : ''}</div></div>`;
    }).join('');
  }

  function statusLabel(status) {
    return ({ready:'PRONTO',live:'LIVE',build_in_progress:'BUILD',update_in_progress:'ATUALIZANDO',pre_deploy_in_progress:'PRE-DEPLOY',pending:'PENDENTE',timeout:'TIMEOUT',build_failed:'FALHOU',update_failed:'FALHOU',pre_deploy_failed:'FALHOU',canceled:'CANCELADO',not_provisioned:'NÃO CRIADO',existing:'EXISTENTE'})[status] || String(status || 'NÃO INICIADO').toUpperCase();
  }

  function renderRenderProvision() {
    const box = byId('cloud-render-box'); if (!box) return;
    const item = current(); const visible = item?.provider === 'render'; box.classList.toggle('visible', visible); if (!visible) return;
    const data = cloudState.renderProvision;
    const status = byId('cloud-render-status'); const detail = byId('cloud-render-detail'); const open = byId('cloud-render-open'); const provision = byId('cloud-render-provision');
    provision.disabled = !item?.configured || !item?.enabled;
    if (!data) {
      status.textContent = 'NÃO INICIADO'; detail.textContent = item?.configured ? 'Pronto para provisionar. A operação inicia rápido e o acompanhamento ocorre por consultas curtas.' : 'Salve e ative a credencial Render primeiro.'; open.style.display = 'none'; return;
    }
    status.textContent = statusLabel(data.status || data.render_status);
    const elapsed = Number(data.elapsed_seconds || 0); const max = Number(data.max_wait_seconds || 1200);
    const pieces = [];
    if (data.service_id) pieces.push(`serviço ${data.service_id}`);
    if (elapsed) pieces.push(`decorrido ${Math.floor(elapsed/60)}m ${elapsed%60}s`);
    if (!data.terminal && max) pieces.push(`limite ${Math.floor(max/60)} min`);
    if (data.health_status_code) pieces.push(`health HTTP ${data.health_status_code}`);
    if (data.timed_out) pieces.push('o acompanhamento atingiu o limite; o serviço pode continuar processando na Render');
    detail.textContent = pieces.join(' · ') || 'Provisionamento iniciado. Aguardando status da Render.';
    const url = safeUrl(data.url); open.style.display = url ? '' : 'none'; if (url) open.href = url;
  }

  function stopRenderPolling() { if (cloudState.renderTimer) clearTimeout(cloudState.renderTimer); cloudState.renderTimer = null; }
  function scheduleRenderPoll(seconds) { stopRenderPolling(); const delay = Math.max(5, Number(seconds || 5)); cloudState.renderTimer = setTimeout(() => checkRenderProvision(false), delay * 1000); }

  async function provisionRender() {
    const item = current(); if (item?.provider !== 'render') return;
    if (!item.configured) return toast('Salve a credencial Render primeiro');
    if (!item.scope) return toast('Informe e salve o Workspace / Owner ID da Render');
    const button = byId('cloud-render-provision'); const original = button.textContent; button.disabled = true; button.textContent = 'Iniciando...';
    try {
      cloudState.renderProvision = await api('/admin/clouds/render/provision-homologation', {method:'POST'});
      renderRenderProvision(); toast(cloudState.renderProvision.created ? 'Homologação Docker criada. Acompanhamento iniciado.' : 'Homologação encontrada. Acompanhamento iniciado.');
      scheduleRenderPoll(cloudState.renderProvision.poll_after_seconds || 5);
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; button.textContent = original; }
  }

  async function checkRenderProvision(showToast = false) {
    const item = current(); if (item?.provider !== 'render' || !item.configured || !item.enabled) return;
    try {
      const result = await api('/admin/clouds/render/provision-homologation/status'); cloudState.renderProvision = result; renderRenderProvision();
      if (result.ready) { stopRenderPolling(); if (showToast) toast('Homologação Docker pronta'); }
      else if (result.terminal) { stopRenderPolling(); if (showToast || result.timed_out) toast(result.timed_out ? 'Tempo de acompanhamento atingido' : `Deploy finalizado: ${statusLabel(result.status)}`); }
      else { if (showToast) toast(`Render: ${statusLabel(result.status)}`); scheduleRenderPoll(result.next_poll_seconds || 5); }
    } catch (error) { stopRenderPolling(); if (showToast) toast(error.message); }
  }

  async function loadClouds(force = false) {
    if (!isSuperAdmin()) return; const active = byId('cloud-admin-view')?.classList.contains('active'); if (!active && !force) return;
    try {
      cloudState.items = await api('/admin/clouds');
      if (!cloudState.selected || !cloudState.items.some(item => item.provider === cloudState.selected)) cloudState.selected = cloudState.items[0]?.provider || '';
      renderSummary(); renderProviders(); fillForm();
      if (cloudState.selected === 'render' && current()?.configured) checkRenderProvision(false);
    } catch (error) { toast(error.message); }
  }

  function setSaveBusy(busy) {
    [byId('cloud-admin-save'), byId('cloud-admin-save-mobile')].filter(Boolean).forEach(button => { if (!button.dataset.idleLabel) button.dataset.idleLabel = button.textContent; button.disabled = busy; button.textContent = busy ? 'Salvando...' : button.dataset.idleLabel; });
  }

  async function saveCloud(event) {
    event.preventDefault(); const item = current(); if (!item) return toast('Selecione um cloud'); const form = event.currentTarget;
    const payload = {secret: form.elements.secret.value.trim() || null, enabled: form.elements.enabled.checked, scope: form.elements.scope.value.trim()};
    setSaveBusy(true);
    try { await api(`/admin/clouds/${item.provider}`, {method:'PUT', body:JSON.stringify(payload)}); toast(`${item.name} atualizado`); await loadClouds(true); }
    catch (error) { toast(error.message); } finally { setSaveBusy(false); }
  }

  async function testCloud() {
    const item = current(); if (!item?.configured) return toast('Salve a credencial antes de testar'); const button = byId('cloud-admin-test'); const original = button.textContent; button.disabled = true; button.textContent = 'Testando...';
    try { const result = await api(`/admin/clouds/${item.provider}/test`, {method:'POST'}); const detail = result.identity ? ` conectado como ${result.identity}` : (Number.isInteger(result.resource_count) ? ` · ${result.resource_count} recurso(s) visíveis` : ''); toast(`${item.name}: conexão OK${detail}`); }
    catch (error) { toast(error.message); } finally { button.disabled = false; button.textContent = original; }
  }

  async function loadResources() {
    const item = current(); if (!item?.configured) return toast('Configure o cloud primeiro'); if (!item.enabled) return toast('Ative o cloud para listar recursos'); const button = byId('cloud-admin-resources'); const original = button.textContent; button.disabled = true; button.textContent = 'Carregando...';
    try { const result = await api(`/admin/clouds/${item.provider}/resources`); cloudState.resources = Array.isArray(result.resources) ? result.resources : []; renderResources(); toast(`${cloudState.resources.length} recurso(s) carregado(s)`); }
    catch (error) { toast(error.message); } finally { button.disabled = false; button.textContent = original; }
  }

  function openConsole() { const url = safeUrl(current()?.dashboard_url); if (!url) return toast('Console indisponível'); window.open(url, '_blank', 'noopener'); }

  async function deleteCloud() {
    const item = current(); if (!item?.configured) return; if (!window.confirm(`Remover a credencial ${item.name} do DevPilot?`)) return;
    try { await api(`/admin/clouds/${item.provider}`, {method:'DELETE'}); cloudState.resources = []; cloudState.renderProvision = null; stopRenderPolling(); toast(`${item.name}: credencial removida`); await loadClouds(true); renderResources(); }
    catch (error) { toast(error.message); }
  }

  let checks = 0; const waitForRole = () => { checks += 1; if (state.currentUser) return ensurePanel(); if (checks < 40) setTimeout(waitForRole, 250); }; waitForRole();
})();
