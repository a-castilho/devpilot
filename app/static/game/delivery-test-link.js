/* DevPilot game delivery test link — exposes only a validated public delivery URL. */
(() => {
  'use strict';

  if (window.__devpilotGameDeliveryTestLinkReady) return;
  window.__devpilotGameDeliveryTestLinkReady = true;

  const STYLE_ID = 'devpilot-game-delivery-test-link-style';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MAX_VALIDATIONS = 6;
  const VALIDATION_DELAY_MS = 5000;
  const deliveryByProject = new Map();
  const inFlight = new Set();
  const validationAttempts = new Map();
  const timers = new Map();

  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const escapeHtml = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const safeUrl = value => {
    const candidate = String(value || '').trim();
    if (!candidate) return '';
    try {
      const parsed = new URL(candidate);
      const host = parsed.hostname.toLowerCase();
      if (parsed.protocol !== 'https:') return '';
      if (!host.endsWith('.vercel.app') && !host.endsWith('.onrender.com')) return '';
      return parsed.href.replace(/\/$/, '');
    } catch (_) {
      return '';
    }
  };

  const controller = () => window.__devpilotGameControllerV73;
  const snapshot = () => controller()?.snapshot?.() || null;
  const projectId = state => String(state?.projectId || localStorage.getItem(PROJECT_KEY) || '').trim();
  const missionDelivered = delivery => normalize(delivery?.status) === 'ready' && Boolean(safeUrl(delivery?.url));

  const installStyle = () => {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .game-delivery-test-link{display:grid;gap:8px;margin-top:14px;padding:14px;border:1px solid rgba(74,226,210,.34);border-radius:14px;background:rgba(21,102,104,.18)}
      .game-delivery-test-link small{color:#5ee7da;font-size:11px;font-weight:900;letter-spacing:.12em}
      .game-delivery-test-link strong{font-size:15px}
      .game-delivery-test-link p{margin:0;color:#a8bbcd;font-size:12px;line-height:1.45}
      .game-delivery-test-link a{display:flex;min-height:48px;align-items:center;justify-content:center;padding:0 14px;border-radius:12px;background:linear-gradient(135deg,#49d9cb,#42b9ef);color:#06131d!important;text-decoration:none;font-weight:900;text-align:center;overflow-wrap:anywhere}
      .game-delivery-test-url{display:block;color:#80e9e0;font:700 11px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere}
      @media(max-width:800px){.game-delivery-test-link{padding:13px}.game-delivery-test-link a{width:auto}}
    `;
    document.head.appendChild(style);
  };

  const host = () => document.querySelector('[data-stable-round-card]');

  const render = () => {
    installStyle();
    const state = snapshot();
    const card = host();
    if (!state?.done || !card) return false;

    const id = projectId(state);
    if (!id) return false;
    const actions = card.querySelector('.game74-actions');
    if (!actions) return false;

    let panel = card.querySelector('[data-game-delivery-test-link]');
    if (!panel) {
      panel = document.createElement('section');
      panel.className = 'game-delivery-test-link';
      panel.dataset.gameDeliveryTestLink = '1';
      actions.before(panel);
    }

    const delivery = deliveryByProject.get(id) || {};
    const url = safeUrl(delivery.url);
    if (missionDelivered(delivery) && url) {
      panel.innerHTML = `
        <small>LINK PARA TESTE</small>
        <strong>✅ Sistema publicado e validado</strong>
        <span class="game-delivery-test-url">${escapeHtml(url)}</span>
        <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">🧪 Abrir sistema para teste ↗</a>
      `;
      return true;
    }

    const status = normalize(delivery.status || 'pending');
    const message = ({
      pending:'Preparando a publicação do sistema…',
      provisioning:'Preparando infraestrutura para gerar o link…',
      deploying:'Publicando e validando o link de teste…',
      failed:'Corrigindo a publicação para gerar o link de teste…',
      blocked:'Tentando resolver a dependência da publicação…',
    })[status] || 'Gerando e validando o link de teste…';
    panel.innerHTML = `
      <small>LINK PARA TESTE</small>
      <strong>${escapeHtml(message)}</strong>
      <p>A entrega só libera o botão de teste quando a URL pública responder e estiver vinculada a este projeto.</p>
    `;
    return true;
  };

  const requestDelivery = async id => {
    if (typeof api !== 'function') return null;
    let delivery = await api(`/projects/${encodeURIComponent(id)}/delivery`);
    if (missionDelivered(delivery)) return delivery;

    const status = normalize(delivery?.status || 'pending');
    if (['pending', 'failed', 'blocked'].includes(status)) {
      delivery = await api(`/projects/${encodeURIComponent(id)}/delivery/auto`, {method:'POST'});
    } else if (['provisioning', 'deploying', 'ready'].includes(status)) {
      delivery = await api(`/projects/${encodeURIComponent(id)}/delivery/validate-url`, {method:'POST'});
    }
    return delivery;
  };

  const scheduleValidation = id => {
    const attempts = validationAttempts.get(id) || 0;
    if (attempts >= MAX_VALIDATIONS || timers.has(id)) return;
    const timer = window.setTimeout(() => {
      timers.delete(id);
      void hydrate(id);
    }, VALIDATION_DELAY_MS);
    timers.set(id, timer);
  };

  const hydrate = async explicitId => {
    const state = snapshot();
    if (!state?.done) return;
    const id = String(explicitId || projectId(state)).trim();
    if (!id || inFlight.has(id)) return;

    render();
    inFlight.add(id);
    try {
      const delivery = await requestDelivery(id);
      if (delivery) deliveryByProject.set(id, delivery);
      render();
      if (!missionDelivered(delivery)) {
        validationAttempts.set(id, (validationAttempts.get(id) || 0) + 1);
        if (['provisioning', 'deploying', 'ready'].includes(normalize(delivery?.status))) scheduleValidation(id);
      } else {
        validationAttempts.delete(id);
        const timer = timers.get(id);
        if (timer) window.clearTimeout(timer);
        timers.delete(id);
      }
    } catch (error) {
      console.warn('[DevPilot Game] link de teste ainda indisponível:', error?.message || error);
      validationAttempts.set(id, (validationAttempts.get(id) || 0) + 1);
      scheduleValidation(id);
    } finally {
      inFlight.delete(id);
    }
  };

  const refresh = () => {
    const state = snapshot();
    if (!state?.done) return;
    render();
    void hydrate(projectId(state));
  };

  document.addEventListener('devpilot:game:state', refresh);
  document.addEventListener('devpilot:game:rendered', refresh);
  document.addEventListener('devpilot:game:core-ready', refresh);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') refresh();
  });
  new MutationObserver(() => render()).observe(document.body, {childList:true, subtree:true});
  window.__devpilotGameDeliveryTestLinkRender = render;
  window.setTimeout(refresh, 500);
})();
