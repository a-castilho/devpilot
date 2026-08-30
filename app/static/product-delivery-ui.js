(() => {
  const OPERATORS = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);
  const initialProjectIds = new Set();
  const autoStarted = new Set();
  const statusCache = new Map();
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

  function checkLabel(name) {
    return {backend: 'Backend', frontend: 'Frontend', database: 'Banco'}[name] || name;
  }

  function deliveryMarkup(delivery) {
    const status = String(delivery?.status || 'pending');
    const checks = Array.isArray(delivery?.checks) ? delivery.checks : [];
    const checkHtml = checks.length
      ? `<div class="product-delivery-checks">${checks.map(check =>
          `<span title="HTTP ${Number(check.status_code || 0)}">${check.ok ? '✅' : '⏳'} ${escapeHtml(checkLabel(check.name))}</span>`
        ).join('')}</div>`
      : '';
    const error = delivery?.last_error
      ? `<div class="product-delivery-error">${escapeHtml(delivery.last_error)}</div>`
      : '';
    return `
      <div class="product-delivery-status product-delivery-${escapeHtml(status)}">
        <strong>${escapeHtml(statusLabel(status))}</strong>
        ${checkHtml}
        ${error}
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
    if (!canOperate()) return;
    const current = await fetchDelivery(project.id, true);
    if (current.status === 'ready' && current.url) {
      window.open(current.url, '_blank', 'noopener,noreferrer');
      return;
    }

    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Processando…';
    try {
      let endpoint = `/projects/${project.id}/delivery/start`;
      if (current.status === 'failed' || current.status === 'blocked') {
        endpoint = `/projects/${project.id}/delivery/retry`;
      } else if (current.status === 'deploying' || current.status === 'provisioning') {
        endpoint = `/projects/${project.id}/delivery/verify`;
      }
      const delivery = await api(endpoint, {method: 'POST'});
      statusCache.set(project.id, delivery || {});
      renderCards();
      if (delivery?.status === 'ready') {
        toast('Produto pronto. Frontend, backend e banco foram validados.');
      } else if (delivery?.status === 'blocked') {
        toast('A administração precisa concluir a configuração da infraestrutura.');
      } else if (delivery?.status === 'failed') {
        toast(delivery.last_error || 'Não foi possível publicar o produto.');
      } else {
        toast('Produto em publicação. Acompanhe o status no card.');
      }
    } catch (error) {
      toast(error.message || 'Falha ao publicar o produto');
    } finally {
      button.disabled = false;
      button.textContent = original;
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
    box.innerHTML = deliveryMarkup(delivery);

    if (!canOperate()) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'link product-delivery-action';
    button.textContent = actionText(delivery);
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
          const delivery = await api(`/projects/${project.id}/delivery/start`, {method: 'POST'});
          statusCache.set(project.id, delivery || {});
          if (delivery?.status === 'ready') {
            toast(`Produto ${project.name || ''} pronto para abrir.`);
          } else if (delivery?.status === 'blocked') {
            toast('Projeto criado. Infraestrutura cloud precisa ser configurada pelo Super Admin.');
          } else {
            toast('Projeto criado. Publicação do produto iniciada.');
          }
        }
      } catch (error) {
        toast(error.message || 'Projeto criado, mas a publicação precisa ser retomada.');
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
      .product-delivery-status{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px}
      .product-delivery-ready strong{color:#2fbf71}.product-delivery-failed strong{color:#e05d5d}.product-delivery-blocked strong{color:#d59b2c}
      .product-delivery-checks{display:flex;gap:8px;flex-wrap:wrap}.product-delivery-error{opacity:.78;width:100%}
      .product-delivery-action{margin-left:auto}
      @media(max-width:720px){.product-delivery-box{align-items:flex-start}.product-delivery-action{margin-left:0;width:100%}}
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

    if (!document.querySelector('#projects-view.active')) {
      return;
    }

    renderCards();
  };

  document.addEventListener(
    'visibilitychange',
    refreshVisibleProjects
  );

  window.setInterval(
    refreshVisibleProjects,
    30000
  );
})();
