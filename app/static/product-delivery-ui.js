(() => {
  const statusCache = new Map();

  function role() {
    return String((typeof state !== 'undefined' && state.currentUser?.role) || '').toUpperCase();
  }

  function isSuperAdmin() {
    return role() === 'SUPER_ADMIN';
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
      pending: 'Preparando produto',
      provisioning: 'Preparando infraestrutura',
      deploying: 'Publicando produto',
      ready: 'Produto pronto',
      failed: 'Intervenção administrativa',
      blocked: 'Infraestrutura pendente',
    };
    return labels[value] || 'Preparando produto';
  }

  function checkLabel(name) {
    return {backend: 'Backend', frontend: 'Frontend', database: 'Banco'}[name] || name;
  }

  function deliveryMarkup(delivery) {
    const status = String(delivery?.status || 'pending');
    const checks = Array.isArray(delivery?.checks) ? delivery.checks : [];
    const checkHtml = checks.length
      ? `<div class="product-delivery-checks">${checks.map(check =>
          `<span>${check.ok ? '✅' : '⏳'} ${escapeHtml(checkLabel(check.name))}</span>`
        ).join('')}</div>`
      : '';
    const error = isSuperAdmin() && delivery?.last_error
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

  function actionText(delivery) {
    const status = String(delivery?.status || 'pending');
    if (status === 'ready') return 'Abrir produto';
    if (status === 'failed' || status === 'blocked') return 'Resolver agora';
    if (status === 'deploying' || status === 'provisioning') return 'Verificar agora';
    return 'Iniciar agora';
  }

  async function runAdminAction(project, button) {
    if (!isSuperAdmin()) return;
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
      await renderCards(true);
      await renderAdminAlerts();
      if (delivery?.status === 'ready') toast('Produto pronto e validado.');
      else if (delivery?.status === 'blocked') toast('Cloud pendente. Verifique o aviso administrativo.');
      else if (delivery?.status === 'failed') toast(delivery.last_error || 'A publicação requer intervenção.');
      else toast('Automação retomada.');
    } catch (error) {
      toast(error.message || 'Falha ao retomar a infraestrutura');
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  async function decorateCard(project, card, force = false) {
    if (!project || !card || !String(project.repository_url || '').trim()) return;
    let box = card.querySelector('.product-delivery-box');
    if (!box) {
      box = document.createElement('div');
      box.className = 'product-delivery-box';
      const row = card.querySelector('.list-row') || card;
      row.appendChild(box);
    }

    const delivery = await fetchDelivery(project.id, force);
    box.innerHTML = deliveryMarkup(delivery);

    if (delivery?.status === 'ready' && delivery?.url) {
      const open = document.createElement('button');
      open.type = 'button';
      open.className = 'link product-delivery-action';
      open.textContent = 'Abrir produto';
      open.addEventListener('click', () => window.open(delivery.url, '_blank', 'noopener,noreferrer'));
      box.appendChild(open);
      return;
    }

    if (!isSuperAdmin()) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'link product-delivery-action';
    button.textContent = actionText(delivery);
    button.addEventListener('click', () => runAdminAction(project, button));
    box.appendChild(button);
  }

  async function renderCards(force = false) {
    const host = document.querySelector('#projects-list');
    if (!host) return;
    const cards = host.querySelectorAll('.project-card');
    const jobs = [];
    projects().forEach((project, index) => {
      const card = cards[index] || null;
      if (card) jobs.push(decorateCard(project, card, force));
    });
    await Promise.all(jobs);
  }

  function openCloudAdmin() {
    document.querySelector('[data-view="cloud-admin"]')?.click();
  }

  async function renderAdminAlerts() {
    const host = document.querySelector('#projects-list');
    if (!host) return;
    let banner = document.querySelector('#delivery-admin-alert');

    if (!isSuperAdmin()) {
      banner?.remove();
      return;
    }

    let alerts = [];
    try {
      alerts = await api('/delivery/alerts');
    } catch (_) {
      return;
    }

    if (!Array.isArray(alerts) || !alerts.length) {
      banner?.remove();
      return;
    }

    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'delivery-admin-alert';
      banner.className = 'delivery-admin-alert';
      host.insertAdjacentElement('beforebegin', banner);
    }

    const rows = alerts.slice(0, 5).map(item => {
      const providers = [
        ...(Array.isArray(item.blocked_providers) ? item.blocked_providers : []),
        item.failed_provider || '',
      ].filter(Boolean);
      return `<li><strong>${escapeHtml(item.project_name)}</strong>${providers.length ? ` · ${escapeHtml(providers.join(', '))}` : ''}</li>`;
    }).join('');

    banner.innerHTML = `
      <div>
        <span class="eyebrow">SUPER ADMIN</span>
        <strong>${alerts.length} projeto(s) precisam de atenção na infraestrutura</strong>
        <ul>${rows}</ul>
      </div>
      <button type="button" class="ghost" id="delivery-admin-clouds">Abrir Clouds</button>
    `;
    banner.querySelector('#delivery-admin-clouds')?.addEventListener('click', openCloudAdmin);
  }

  function installStyle() {
    if (document.querySelector('#product-delivery-style')) return;
    const style = document.createElement('style');
    style.id = 'product-delivery-style';
    style.textContent = `
      .product-delivery-box{margin-top:10px;padding-top:10px;border-top:1px solid rgba(127,127,127,.22);display:flex;gap:10px;align-items:center;flex-wrap:wrap}
      .product-delivery-status{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px}
      .product-delivery-ready strong{color:#2fbf71}.product-delivery-failed strong,.product-delivery-blocked strong{color:#d59b2c}
      .product-delivery-checks{display:flex;gap:8px;flex-wrap:wrap}.product-delivery-error{opacity:.78;width:100%}
      .product-delivery-action{margin-left:auto}
      .delivery-admin-alert{margin:0 0 14px;padding:14px 16px;border:1px solid rgba(255,190,70,.35);border-radius:14px;background:rgba(255,190,70,.08);display:flex;justify-content:space-between;gap:16px;align-items:center}
      .delivery-admin-alert strong{display:block;margin:3px 0 6px}.delivery-admin-alert ul{margin:0;padding-left:18px;font-size:12px;opacity:.85}
      @media(max-width:720px){.product-delivery-box{align-items:flex-start}.product-delivery-action{margin-left:0;width:100%}.delivery-admin-alert{align-items:stretch;flex-direction:column}.delivery-admin-alert button{width:100%}}
    `;
    document.head.appendChild(style);
  }

  function install() {
    installStyle();
    const host = document.querySelector('#projects-list');
    if (!host) return;
    if (!host.dataset.productDeliveryObservedV2) {
      host.dataset.productDeliveryObservedV2 = '1';
      new MutationObserver(() => {
        void renderCards(true);
        void renderAdminAlerts();
      }).observe(host, {childList: true, subtree: false});
    }
    void renderCards(true);
    void renderAdminAlerts();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, {once: true});
  } else {
    install();
  }
  window.setTimeout(install, 800);
  window.setInterval(() => {
    statusCache.clear();
    void renderCards(true);
    void renderAdminAlerts();
  }, 15000);
})();
