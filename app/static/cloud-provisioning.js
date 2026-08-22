(() => {
  const PROVIDERS = [
    {
      id: 'neon',
      name: 'Neon',
      accountLabel: 'Organization ID (opcional)',
      accountPlaceholder: 'org-...',
      help: 'PostgreSQL gerenciado. O DevPilot cria main + homolog e nunca persiste a DATABASE_URL.',
    },
    {
      id: 'render',
      name: 'Render',
      accountLabel: 'Owner ID',
      accountPlaceholder: 'usr-... ou tea-...',
      help: 'Backend/worker. O Owner ID é obrigatório para criar projetos e serviços.',
    },
    {
      id: 'vercel',
      name: 'Vercel',
      accountLabel: 'Team ID (opcional)',
      accountPlaceholder: 'team_...',
      help: 'Frontend. Sem Team ID, o projeto é criado na conta pessoal do token.',
    },
  ];

  const escCloud = value => String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  })[char]);

  function canManageCloud() {
    return typeof isSuperAdmin === 'function' && isSuperAdmin();
  }

  function ensureStyles() {
    if (document.querySelector('#cloud-provisioning-style')) return;
    const style = document.createElement('style');
    style.id = 'cloud-provisioning-style';
    style.textContent = `
      .cloud-config-button{white-space:nowrap}
      .cloud-config-shell{width:min(760px,calc(100vw - 32px));max-width:760px}
      .cloud-config-intro{margin:0 0 16px;color:var(--muted,#8ea0b7);line-height:1.5}
      .cloud-provider-grid{display:grid;gap:12px}
      .cloud-provider-card{border:1px solid rgba(142,160,183,.18);border-radius:14px;padding:14px;background:rgba(255,255,255,.025)}
      .cloud-provider-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}
      .cloud-provider-head strong{font-size:16px}
      .cloud-provider-state{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#ffd277}
      .cloud-provider-state.ready{color:#72e6a0}
      .cloud-provider-fields{display:grid;grid-template-columns:1fr 1.35fr auto;gap:10px;align-items:end}
      .cloud-provider-fields label{margin:0}
      .cloud-provider-card small{display:block;margin-top:9px;color:var(--muted,#8ea0b7);line-height:1.4}
      .cloud-project-button{margin-left:7px}
      @media(max-width:720px){.cloud-provider-fields{grid-template-columns:1fr}.cloud-provider-fields button{width:100%}}
    `;
    document.head.appendChild(style);
  }

  function ensureDialog() {
    let dialog = document.querySelector('#cloud-config-modal');
    if (dialog) return dialog;

    dialog = document.createElement('dialog');
    dialog.id = 'cloud-config-modal';
    dialog.innerHTML = `
      <form class="modal cloud-config-shell" method="dialog">
        <button class="close" type="button" aria-label="Fechar">×</button>
        <span class="eyebrow">INFRAESTRUTURA GERENCIADA</span>
        <h2>Conectar Neon, Render e Vercel</h2>
        <p class="cloud-config-intro">As credenciais ficam criptografadas no Vault do DevPilot. Projetos novos usam estas conexões para provisionar automaticamente a stack selecionada.</p>
        <div class="cloud-provider-grid" id="cloud-provider-grid"></div>
      </form>
    `;
    document.body.appendChild(dialog);
    dialog.querySelector('.close').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', event => {
      if (event.target === dialog) dialog.close();
    });
    return dialog;
  }

  function renderProviders(statuses = []) {
    const grid = document.querySelector('#cloud-provider-grid');
    if (!grid) return;
    const statusByProvider = Object.fromEntries(statuses.map(item => [item.provider, item]));
    grid.innerHTML = PROVIDERS.map(provider => {
      const current = statusByProvider[provider.id] || {};
      const configured = Boolean(current.configured);
      return `
        <section class="cloud-provider-card" data-cloud-provider="${provider.id}">
          <div class="cloud-provider-head">
            <strong>${escCloud(provider.name)}</strong>
            <span class="cloud-provider-state ${configured ? 'ready' : ''}">${configured ? '● configurado' : '○ pendente'}</span>
          </div>
          <div class="cloud-provider-fields">
            <label>${escCloud(provider.accountLabel)}
              <input name="account_id" value="${escCloud(current.account_id || '')}" placeholder="${escCloud(provider.accountPlaceholder)}" autocomplete="off">
            </label>
            <label>API token
              <input name="token" type="password" placeholder="${configured ? '••••••••••••••••' : 'Cole o token do provedor'}" autocomplete="new-password">
            </label>
            <button class="primary cloud-provider-save" type="button">Salvar</button>
          </div>
          <small>${escCloud(provider.help)}</small>
        </section>
      `;
    }).join('');

    grid.querySelectorAll('.cloud-provider-save').forEach(button => {
      button.addEventListener('click', () => saveProvider(button));
    });
  }

  async function loadProviders() {
    const statuses = await api('/cloud/providers');
    renderProviders(statuses || []);
  }

  async function saveProvider(button) {
    const card = button.closest('[data-cloud-provider]');
    const provider = card?.dataset.cloudProvider;
    const tokenInput = card?.querySelector('input[name="token"]');
    const accountInput = card?.querySelector('input[name="account_id"]');
    const token = String(tokenInput?.value || '').trim();
    const accountId = String(accountInput?.value || '').trim();

    if (!provider || token.length < 8) {
      toast('Informe o API token do provedor');
      return;
    }
    if (provider === 'render' && !accountId) {
      toast('Informe o Owner ID da Render');
      return;
    }

    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Salvando…';
    try {
      await api(`/cloud/providers/${provider}`, {
        method: 'PUT',
        body: JSON.stringify({token, account_id: accountId}),
      });
      if (tokenInput) tokenInput.value = '';
      toast(`${PROVIDERS.find(item => item.id === provider)?.name || provider} conectado ao Vault`);
      await loadProviders();
    } catch (error) {
      toast(error.message || 'Falha ao salvar credencial cloud');
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  async function openCloudConfig() {
    if (!canManageCloud()) {
      toast('Acesso exclusivo do Super Admin');
      return;
    }
    const dialog = ensureDialog();
    renderProviders([]);
    dialog.showModal();
    try {
      await loadProviders();
    } catch (error) {
      toast(error.message || 'Falha ao carregar conexões cloud');
    }
  }

  function installBuilderButton() {
    const hero = document.querySelector('.project-builder-hero');
    if (!hero || hero.querySelector('.cloud-config-button')) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ghost cloud-config-button';
    button.textContent = '☁ Configurar cloud';
    button.addEventListener('click', openCloudConfig);

    const back = hero.querySelector('.project-builder-back');
    if (back) back.insertAdjacentElement('beforebegin', button);
    else hero.appendChild(button);
  }

  async function provisionProject(projectId, button) {
    if (!canManageCloud()) {
      toast('Acesso exclusivo do Super Admin');
      return;
    }
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Provisionando…';
    try {
      const state = await api(`/projects/${projectId}/cloud/provision`, {method: 'POST'});
      if (state.status === 'provisioned') {
        toast('Neon, Render e Vercel provisionados para o projeto');
      } else if (state.missing_credentials?.length) {
        toast(`Cloud pendente: configure ${state.missing_credentials.join(', ')}`);
        openCloudConfig();
      } else {
        const failed = Object.keys(state.errors || {});
        toast(failed.length ? `Provisionamento parcial: ${failed.join(', ')}` : `Cloud: ${state.status}`);
      }
    } catch (error) {
      toast(error.message || 'Falha no provisionamento cloud');
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function decorateProjectCards() {
    if (!canManageCloud() || typeof state === 'undefined' || !Array.isArray(state.projects)) return;
    const host = document.querySelector('#projects-list');
    if (!host) return;
    const cards = [...host.querySelectorAll('.project-card')];
    cards.forEach((card, index) => {
      const project = state.projects[index];
      if (!project || card.querySelector('.cloud-project-button')) return;
      const actions = card.querySelector('.list-row > div:last-child');
      if (!actions) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'link cloud-project-button';
      button.textContent = 'Cloud';
      button.title = 'Provisionar ou retomar Neon, Render e Vercel';
      button.addEventListener('click', () => provisionProject(project.id, button));
      actions.appendChild(button);
    });
  }

  function install() {
    ensureStyles();
    ensureDialog();
    installBuilderButton();
    decorateProjectCards();

    const projectList = document.querySelector('#projects-list');
    if (projectList && !projectList.dataset.cloudObserved) {
      projectList.dataset.cloudObserved = '1';
      new MutationObserver(() => decorateProjectCards()).observe(projectList, {childList: true});
    }

    const builder = document.querySelector('#project-builder-form');
    if (builder && !builder.dataset.cloudObserved) {
      builder.dataset.cloudObserved = '1';
      new MutationObserver(() => installBuilderButton()).observe(builder, {childList: true, subtree: true});
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, {once: true});
  } else {
    install();
  }
  window.setTimeout(install, 800);
})();
