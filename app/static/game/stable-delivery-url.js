/* DevPilot stable game delivery bridge — final round only completes with a validated public URL. */
(() => {
  'use strict';

  if (window.__devpilotStableDeliveryUrlReady) return;
  window.__devpilotStableDeliveryUrlReady = true;

  const OPERATORS = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);
  const RETRY_MS = 5000;
  const MAX_VALIDATIONS = 6;
  const inFlight = new Set();
  const timers = new Map();

  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const safeUrl = value => {
    const candidate = String(value || '').trim();
    return /^https:\/\//i.test(candidate) ? candidate : '';
  };
  const role = () => String(
    (typeof state !== 'undefined' && state.currentUser?.role) || window.state?.currentUser?.role || ''
  ).toUpperCase();
  const canOperate = () => OPERATORS.has(role());
  const controller = () => window.__devpilotGameControllerV73;
  const round = () => document.querySelector('#devpilot-game-stable-round-v91 [data-stable-round-card]');
  const normalized = delivery => String(delivery?.status || 'pending').toLowerCase();
  const delivered = delivery => normalized(delivery) === 'ready' && Boolean(safeUrl(delivery?.url));

  const call = async (path, options = {}) => {
    if (typeof window.api !== 'function') throw new Error('Runtime de comunicação indisponível');
    return window.api(path, options);
  };

  const endpoint = (projectId, suffix = '') => `/projects/${encodeURIComponent(projectId)}/delivery${suffix}`;

  function installStyle() {
    if (document.getElementById('stable-delivery-url-style')) return;
    const style = document.createElement('style');
    style.id = 'stable-delivery-url-style';
    style.textContent = `
      .stable-delivery-url{display:grid;gap:10px;margin:14px 0;padding:14px;border:1px solid rgba(95,224,255,.32);border-radius:14px;background:linear-gradient(135deg,rgba(28,100,91,.22),rgba(8,22,39,.82))}
      .stable-delivery-url small{color:#72efc5;font-weight:800;letter-spacing:.08em}.stable-delivery-url strong{font-size:1rem}.stable-delivery-url p{margin:0;color:var(--muted,#9eacc2)}
      .stable-delivery-url-value{display:block;padding:11px 12px;border:1px solid rgba(255,255,255,.1);border-radius:10px;background:rgba(0,0,0,.22);font:600 .78rem ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere;color:#8be9fd;text-decoration:none}
      .stable-delivery-url-actions{display:flex;gap:8px;flex-wrap:wrap}.stable-delivery-url-actions a,.stable-delivery-url-actions button{display:inline-flex;align-items:center;justify-content:center;min-height:44px;text-decoration:none}.stable-delivery-url-error{color:#ffc56e;font-size:.78rem}
      @media(max-width:800px){.stable-delivery-url-actions>*{width:100%}}
    `;
    document.head.appendChild(style);
  }

  function host(panel) {
    let node = panel.querySelector('.stable-delivery-url');
    if (!node) {
      node = document.createElement('section');
      node.className = 'stable-delivery-url';
      node.setAttribute('aria-live', 'polite');
      const actions = panel.querySelector('.game74-actions');
      if (actions) panel.insertBefore(node, actions);
      else panel.appendChild(node);
    }
    return node;
  }

  function setRoundGate(panel, delivery) {
    const ready = delivered(delivery);
    const heading = panel.querySelector('h1');
    const kicker = panel.querySelector('.game74-kicker');
    const status = panel.querySelector('.game74-status');
    const primary = panel.querySelector('.game74-actions .game74-primary');
    const newRound = panel.querySelector('[data-stable-new]');

    if (ready) {
      panel.dataset.deliveryUrlReady = '1';
      if (kicker) kicker.textContent = 'MISSÃO CUMPRIDA';
      if (heading) heading.textContent = 'Entrega concluída';
      if (status) status.innerHTML = '🏆 <strong>Pronto.</strong> Entrega validada e URL pública disponível para teste.';
      if (primary) primary.textContent = '🏆 Entrega pronta';
      if (newRound) newRound.hidden = false;
      return;
    }

    panel.dataset.deliveryUrlReady = '0';
    if (kicker) kicker.textContent = 'PUBLICAÇÃO FINAL';
    if (heading) heading.textContent = 'Finalizando a entrega';
    if (status) status.innerHTML = '🚀 <strong>Quase pronto.</strong> O código passou pelos gates; falta publicar e validar a URL real.';
    if (primary) primary.textContent = '🚀 Publicando e validando URL';
    if (newRound) newRound.hidden = true;
  }

  function render(panel, delivery = {}) {
    installStyle();
    setRoundGate(panel, delivery);
    const node = host(panel);
    const status = normalized(delivery);
    const url = safeUrl(delivery?.url);

    if (delivered(delivery)) {
      node.innerHTML = `
        <small>URL DO PROJETO</small>
        <strong>Projeto disponível para teste</strong>
        <p>A publicação respondeu à validação real de disponibilidade.</p>
        <a class="stable-delivery-url-value" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(url)}</a>
        <div class="stable-delivery-url-actions"><a class="game74-primary" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Abrir projeto ↗</a></div>`;
      return;
    }

    const statusText = {
      pending: 'Preparando publicação…',
      provisioning: 'Preparando ambiente de teste…',
      deploying: 'Publicando e validando URL…',
      failed: 'A publicação falhou; tentando corrigir.',
      blocked: 'Publicação bloqueada; procurando solução automática.',
    }[status] || 'Finalizando publicação…';

    node.innerHTML = `
      <small>URL DO PROJETO</small>
      <strong>${esc(statusText)}</strong>
      <p>A missão só será marcada como entregue quando uma URL HTTPS real estiver validada.</p>
      ${delivery?.last_error ? `<div class="stable-delivery-url-error">${esc(delivery.last_error)}</div>` : ''}
      ${canOperate() && ['failed', 'blocked'].includes(status) ? '<div class="stable-delivery-url-actions"><button class="game74-secondary" type="button" data-stable-delivery-retry>↻ Corrigir publicação</button></div>' : ''}`;

    node.querySelector('[data-stable-delivery-retry]')?.addEventListener('click', () => void refresh(panel, true));
  }

  function schedule(panel, projectId, attempt) {
    if (!projectId || attempt > MAX_VALIDATIONS) return;
    const old = timers.get(projectId);
    if (old) window.clearTimeout(old);
    const timer = window.setTimeout(() => {
      timers.delete(projectId);
      if (panel.isConnected) void refresh(panel, false, attempt);
    }, RETRY_MS);
    timers.set(projectId, timer);
  }

  async function refresh(panel, forceRetry = false, attempt = 1) {
    const state = controller()?.snapshot?.();
    if (!state?.done || !state.projectId) return;
    const projectId = String(state.projectId);
    if (inFlight.has(projectId)) return;
    inFlight.add(projectId);

    try {
      let delivery = await call(endpoint(projectId));
      let status = normalized(delivery);

      if (delivered(delivery)) {
        delivery = await call(endpoint(projectId, '/validate-url'), {method: 'POST'});
        render(panel, delivery || {});
        return;
      }

      if (canOperate() && (status === 'pending' || forceRetry || ['failed', 'blocked'].includes(status))) {
        const action = status === 'pending' && !forceRetry ? '/start' : '/retry';
        delivery = await call(endpoint(projectId, action), {method: 'POST'});
        status = normalized(delivery);
      }

      if (['provisioning', 'deploying'].includes(status)) {
        delivery = await call(endpoint(projectId, '/validate-url'), {method: 'POST'});
      }

      render(panel, delivery || {});
      if (!delivered(delivery) && ['pending', 'provisioning', 'deploying', 'failed', 'blocked'].includes(normalized(delivery))) {
        schedule(panel, projectId, attempt + 1);
      }
    } catch (error) {
      render(panel, {status: 'failed', last_error: error?.message || 'Não foi possível validar a URL agora.'});
      schedule(panel, projectId, attempt + 1);
    } finally {
      inFlight.delete(projectId);
    }
  }

  function sync() {
    const state = controller()?.snapshot?.();
    const panel = round();
    if (!panel || !state?.done || !state.projectId) return;
    if (panel.dataset.deliveryUrlHydrating === '1') return;
    panel.dataset.deliveryUrlHydrating = '1';
    render(panel, {status: 'provisioning'});
    void refresh(panel).finally(() => {
      if (panel.isConnected) panel.dataset.deliveryUrlHydrating = '0';
    });
  }

  let scheduled = false;
  const requestSync = () => {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      sync();
    });
  };

  document.addEventListener('devpilot:game:state', requestSync);
  document.addEventListener('devpilot:game:rendered', requestSync);
  document.addEventListener('devpilot:game:core-ready', requestSync);
  document.addEventListener('visibilitychange', requestSync);
  requestSync();
})();
