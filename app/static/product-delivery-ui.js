(() => {
  const OPERATORS = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);
  const initialProjectIds = new Set();
  const autoStarted = new Set();
  const statusCache = new Map();
  const processingProjects = new Set();
  let initialized = false;

  function role() {
    return String((typeof state !== 'undefined' && state.currentUser?.role) || '').toUpperCase();
  }

  function canOperate() {
    return OPERATORS.has(role());
  }

  function projects() {
    return typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : [];
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function statusLabel(value) {
    const labels = {
      pending: 'Aguardando publicação',
      provisioning: 'Preparando produto',
      deploying: 'Publicando produto',
      ready: 'Produto pronto',
      failed: 'Falha na publicação',
      blocked: 'Infraestrutura pendente',
    };
    return labels[value] || 'Aguardando publicação';
  }

  function providerLabel(value) {
    return {
      neon: 'Neon',
      render: 'Render',
      vercel: 'Vercel',
      cloud: 'Cloud',
    }[String(value || '').toLowerCase()] || String(value || '');
  }

  function checkLabel(name) {
    return {backend: 'Backend', frontend: 'Frontend', database: 'Banco', public_url: 'URL pública'}[name] || name;
  }

  function deliveryMarkup(delivery, processing = false) {
    const status = String(delivery?.status || 'pending');
    const checks = Array.isArray(delivery?.checks) ? delivery.checks : [];
    const failedProvider = providerLabel(delivery?.failed_provider);
    const blocked = Array.isArray(delivery?.blocked_providers) ? delivery.blocked_providers : [];

    const checkHtml = checks.length
      ? `<div class="product-delivery-checks">${checks.map(check => {
          const code = Number(check.status_code || 0);
          const codeLabel = code ? `HTTP ${code}` : 'sem resposta';
          return `<span class="product-delivery-check ${check.ok ? 'ok' : 'fail'}">${check.ok ? '✅' : '⚠️'} ${escapeHtml(checkLabel(check.name))} <small>${escapeHtml(codeLabel)}</small></span>`;
        }).join('')}</div>`
      : '';

    const providerHtml = failedProvider
      ? `<div class="product-delivery-provider"><span>Falha em</span><strong>${escapeHtml(failedProvider)}</strong></div>`
      : '';

    const blockedHtml = blocked.length
      ? `<div class="product-delivery-provider"><span>Configuração pendente</span><strong>${escapeHtml(blocked.map(providerLabel).join(', '))}</strong></div>`
      : '';

    const error = delivery?.last_error
      ? `<div class="product-delivery-error">${escapeHtml(delivery.last_error)}</div>`
      : '';

    const processingHtml = processing
      ? '<div class="product-delivery-processing" role="status">⏳ Publicação em andamento. Aguarde a resposta do provedor.</div>'
      : '';

    return `
      <div class="product-delivery-status product-delivery-${escapeHtml(status)}">
        <strong>${escapeHtml(processing ? 'Processando publicação' : statusLabel(status))}</strong>
        ${providerHtml}
        ${blockedHtml}
        ${checkHtml}
        ${error}
        ${processingHtml}
      </div>
    `;
  }

  function actionText(delivery) {
    const status = String(delivery?.status || 'pending');
    if (status === 'ready') return 'Abrir produto';
    if (status === 'failed' || status === 'blocked') return 'Tentar novamente';
    if (status === 'deploying' || status === 'provisioning') return 'Verificar publicação';
    return 'Publicar produto';
  }

  async function fetchDelivery(projectId, force = false) {
    if (!force && statusCache.has(projectId)) return statusCache.get(projectId);
    try {
      const result = await api(`/projects/${projectId}/delivery`);
      statusCache.set(projectId, result || {});
      return result || {};
    } catch (_) {
      return {};
    }
  }

  async function runAction(project, button) {
    if (!canOperate() || processingProjects.has(project.id)) return;
    const current = await fetchDelivery(project.id, true);
    if (current.status === 'ready' && current.url) {
      window.open(current.url, '_blank', 'noopener,noreferrer');
      return;
    }

    processingProjects.add(project.id);
    button.disabled = true;
    renderCards();
    try {
      let endpoint = `/projects/${project.id}/delivery/start`;
      if (current.status === 'failed' || current.status === 'blocked') {
        endpoint = `/projects/${project.id}/delivery/retry`;
      } else if (current.status === 'deploying' || current.status === 'provisioning') {
        endpoint = `/projects/${project.id}/delivery/verify`;
      }
      const delivery = await api(endpoint, {method: 'POST'});
      statusCache.set(project.id, delivery || {});
      if (delivery?.status === 'ready') {
        toast('Produto pronto. Frontend, backend e banco foram validados.');
      } else if (delivery?.status === 'blocked') {
        const providers = Array.isArray(delivery.blocked_providers)
          ? delivery.blocked_providers.map(providerLabel).join(', ')
          : '';
        toast(providers ? `Configuração pendente: ${providers}.` : 'A administração precisa concluir a configuração da infraestrutura.');
      } else if (delivery?.status === 'failed') {
        const provider = providerLabel(delivery.failed_provider);
        toast(`${provider ? `${provider}: ` : ''}${delivery.last_error || 'Não foi possível publicar o produto.'}`);
      } else {
        toast('Produto em publicação. Acompanhe o status no card.');
      }
    } catch (error) {
      statusCache.delete(project.id);
      toast(error.message || 'Falha ao publicar o produto');
    } finally {
      processingProjects.delete(project.id);
      renderCards();
    }
  }

  function cardForIndex(host, index) {
    return host.querySelectorAll('.project-card')[index] || null;
  }

  async function decorateCard(project, card) {
    if (!project || !card || !String(project.repository_url || '').trim()) return;
    let box = card.querySelector('.product-delivery-box');
    if (!box) {
      box = document.createElement('div');
      box.className = 'product-delivery-box';
      const row = card.querySelector('.list-row') || card;
      row.appendChild(box);
    }

    const delivery = await fetchDelivery(project.id);
    const processing = processingProjects.has(project.id);
    box.innerHTML = deliveryMarkup(delivery, processing);

    if (!canOperate()) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'link product-delivery-action';
    button.textContent = processing ? 'Processando…' : actionText(delivery);
    button.disabled = processing;
    button.setAttribute('aria-busy', processing ? 'true' : 'false');
    button.addEventListener('click', () => runAction(project, button));
    box.appendChild(button);
  }

  function renderCards() {
    const host = document.querySelector('#projects-list');
    if (!host) return;
    projects().forEach((project, index) => {
      const card = cardForIndex(host, index);
      if (card) void decorateCard(project, card);
    });
  }

  async function startNewProjects() {
    if (!canOperate()) return;
    for (const project of projects()) {
      if (!project?.id || initialProjectIds.has(project.id) || autoStarted.has(project.id)) continue;
      if (!String(project.repository_url || '').trim()) continue;
      autoStarted.add(project.id);
      try {
        const current = await fetchDelivery(project.id, true);
        if (!current.status || current.status === 'pending') {
          processingProjects.add(project.id);
          renderCards();
          const delivery = await api(`/projects/${project.id}/delivery/start`, {method: 'POST'});
          statusCache.set(project.id, delivery || {});
          if (delivery?.status === 'ready') {
            toast(`Produto ${project.name || ''} pronto para abrir.`);
          } else if (delivery?.status === 'blocked') {
            toast('Projeto criado. Infraestrutura cloud precisa ser configurada pelo Super Admin.');
          } else if (delivery?.status === 'failed') {
            const provider = providerLabel(delivery.failed_provider);
            toast(`${provider ? `${provider}: ` : ''}${delivery.last_error || 'Falha na publicação.'}`);
          } else {
            toast('Projeto criado. Publicação do produto iniciada.');
          }
        }
      } catch (error) {
        toast(error.message || 'Projeto criado, mas a publicação precisa ser retomada.');
      } finally {
        processingProjects.delete(project.id);
      }
    }
    renderCards();
  }

  function installStyle() {
    if (document.querySelector('#product-delivery-style')) return;
    const style = document.createElement('style');
    style.id = 'product-delivery-style';
    style.textContent = `
      .product-delivery-box{margin-top:10px;padding-top:10px;border-top:1px solid rgba(127,127,127,.22);display:flex;gap:10px;align-items:center;flex-wrap:wrap}
      .product-delivery-status{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px;width:100%}
      .product-delivery-ready>strong{color:#2fbf71}.product-delivery-failed>strong{color:#e05d5d}.product-delivery-blocked>strong{color:#d59b2c}
      .product-delivery-provider{display:flex;gap:6px;align-items:center;width:100%;padding:8px 10px;border:1px solid rgba(127,127,127,.18);border-radius:10px}.product-delivery-provider span{opacity:.68}.product-delivery-provider strong{font-size:12px}
      .product-delivery-checks{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;width:100%}.product-delivery-check{display:flex;gap:5px;align-items:center;padding:7px 8px;border:1px solid rgba(127,127,127,.18);border-radius:9px}.product-delivery-check small{margin-left:auto;opacity:.62;white-space:nowrap}.product-delivery-check.fail{border-color:rgba(224,93,93,.4)}
      .product-delivery-error{width:100%;padding:9px 10px;border-radius:10px;background:rgba(224,93,93,.08);border:1px solid rgba(224,93,93,.25);line-height:1.4}
      .product-delivery-processing{width:100%;padding:8px 10px;border-radius:10px;background:rgba(71,190,255,.08);border:1px solid rgba(71,190,255,.22)}
      .product-delivery-action{margin-left:auto}
      @media(max-width:720px){.product-delivery-box{align-items:flex-start}.product-delivery-action{margin-left:0;width:100%}.product-delivery-checks{grid-template-columns:1fr}.product-delivery-check{min-width:0}}
    `;
    document.head.appendChild(style);
  }

  function install() {
    installStyle();
    const host = document.querySelector('#projects-list');
    if (!host) return;
    if (!initialized) {
      projects().forEach(project => project?.id && initialProjectIds.add(project.id));
      initialized = true;
    }
    if (!host.dataset.productDeliveryObserved) {
      host.dataset.productDeliveryObserved = '1';
      new MutationObserver(() => {
        renderCards();
        void startNewProjects();
      }).observe(host, {childList: true, subtree: false});
    }
    renderCards();
    void startNewProjects();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, {once: true});
  } else {
    install();
  }
  window.setTimeout(install, 800);
  const refreshVisibleProjects = () => {
    if (document.hidden) return;
    if (!document.querySelector('#projects-view.active')) return;
    renderCards();
  };

  document.addEventListener('visibilitychange', refreshVisibleProjects);
  window.setInterval(refreshVisibleProjects, 30000);
})();
