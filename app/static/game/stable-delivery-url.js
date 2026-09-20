/* DevPilot stable game delivery surface — lightweight observer for final public URL. */
(() => {
  'use strict';

  if (window.__devpilotStableDeliveryUrlReady) return;
  window.__devpilotStableDeliveryUrlReady = true;

  const OPERATORS = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);
  const WATCH_MS = 15000;
  const inFlight = new Set();
  const timers = new Map();
  let lastRenderSignature = '';

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
  const endpoint = projectId => `/projects/${encodeURIComponent(projectId)}/delivery`;

  const call = async path => {
    if (typeof window.api !== 'function') throw new Error('Runtime de comunicação indisponível');
    return window.api(path, {timeoutMs: 5000, retry: false});
  };

  function installStyle() {
    if (document.getElementById('stable-delivery-url-style')) return;
    const style = document.createElement('style');
    style.id = 'stable-delivery-url-style';
    style.textContent = `
      .stable-delivery-url{display:grid;gap:10px;margin:14px 0;padding:14px;border:1px solid rgba(95,224,255,.32);border-radius:14px;background:linear-gradient(135deg,rgba(28,100,91,.22),rgba(8,22,39,.82))}
      .stable-delivery-url small{color:#72efc5;font-weight:800;letter-spacing:.08em}.stable-delivery-url strong{font-size:1rem}.stable-delivery-url p{margin:0;color:var(--muted,#9eacc2)}
      .stable-delivery-url-value{display:block;padding:11px 12px;border:1px solid rgba(255,255,255,.1);border-radius:10px;background:rgba(0,0,0,.22);font:600 .78rem ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere;color:#8be9fd;text-decoration:none}
      .stable-delivery-url-actions{display:flex;gap:8px;flex-wrap:wrap}.stable-delivery-url-actions a,.stable-delivery-url-actions button{display:inline-flex;align-items:center;justify-content:center;min-height:44px;text-decoration:none}.stable-delivery-url-error{color:#ffc56e;font-size:.78rem}
      .stable-delivery-url-watch{color:#8be9fd;font-size:.78rem}
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
    const currentStatus = normalized(delivery);
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
    if (currentStatus === 'repairing') {
      if (kicker) kicker.textContent = 'CORREÇÃO AUTOMÁTICA';
      if (heading) heading.textContent = 'Corrigindo o produto final';
      if (status) status.innerHTML = '⏳ <strong>A correção continua em andamento.</strong> Continuo acompanhando automaticamente até o produto e a URL serem validados.';
      if (primary) primary.textContent = '⏳ Aguardando correção';
    } else {
      if (kicker) kicker.textContent = 'PUBLICAÇÃO FINAL';
      if (heading) heading.textContent = 'Finalizando a entrega';
      if (status) status.innerHTML = '⏳ <strong>A publicação ainda não terminou.</strong> Continuo acompanhando automaticamente sem sobrecarregar o navegador.';
      if (primary) primary.textContent = '⏳ Aguardando publicação';
    }
    if (newRound) newRound.hidden = true;
  }

  function render(panel, delivery = {}) {
    installStyle();
    const signature = JSON.stringify([
      normalized(delivery), delivery?.url || '', delivery?.last_error || '', delivery?.repair_task_status || ''
    ]);
    setRoundGate(panel, delivery);
    if (signature === lastRenderSignature && panel.querySelector('.stable-delivery-url')) return;
    lastRenderSignature = signature;

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
      repairing: 'Corrigindo o produto final…',
      provisioning: 'Preparando ambiente de teste…',
      deploying: 'Publicando e validando URL…',
      failed: 'A publicação falhou; a recuperação automática continua no backend.',
      blocked: 'Publicação bloqueada; acompanhando a recuperação automática.',
    }[status] || 'Finalizando publicação…';

    const repairDetail = status === 'repairing' && delivery?.repair_task_status
      ? `<p>Etapa automática: <strong>${esc(delivery.repair_task_status)}</strong>. O deploy só começa quando o produto estiver válido.</p>`
      : '<p>A missão só será marcada como entregue quando o produto real e uma URL HTTPS estiverem validados.</p>';

    node.innerHTML = `
      <small>${status === 'repairing' ? 'VALIDAÇÃO DO PRODUTO' : 'URL DO PROJETO'}</small>
      <strong>${esc(statusText)}</strong>
      ${repairDetail}
      <div class="stable-delivery-url-watch">Continuo acompanhando automaticamente. Esta tela apenas observa o estado; o backend inicia e recupera a entrega após o Gate 7/7.</div>
      ${delivery?.last_error ? `<div class="stable-delivery-url-error">${esc(delivery.last_error)}</div>` : ''}
      ${canOperate() && ['failed', 'blocked'].includes(status) ? '<div class="stable-delivery-url-actions"><button class="game74-secondary" type="button" data-stable-delivery-retry>↻ Tentar entrega novamente</button></div>' : ''}`;

    node.querySelector('[data-stable-delivery-retry]')?.addEventListener('click', () => void retryOnce(panel));
  }

  function clearProjectTimer(projectId) {
    const timer = timers.get(projectId);
    if (timer) window.clearTimeout(timer);
    timers.delete(projectId);
  }

  function schedule(panel, projectId) {
    if (!projectId || delivered(panel.__devpilotLastDelivery)) return;
    clearProjectTimer(projectId);
    const timer = window.setTimeout(() => {
      timers.delete(projectId);
      if (!panel.isConnected) return;
      if (document.hidden) {
        schedule(panel, projectId);
        return;
      }
      void refresh(panel);
    }, WATCH_MS);
    timers.set(projectId, timer);
  }

  async function refresh(panel) {
    const gameState = controller()?.snapshot?.();
    if (!gameState?.done || !gameState.projectId || !panel?.isConnected) return;
    const projectId = String(gameState.projectId);
    if (inFlight.has(projectId)) return;
    if (document.hidden) {
      schedule(panel, projectId);
      return;
    }

    inFlight.add(projectId);
    try {
      const delivery = await call(endpoint(projectId));
      panel.__devpilotLastDelivery = delivery || {};
      render(panel, panel.__devpilotLastDelivery);
      if (delivered(delivery)) clearProjectTimer(projectId);
      else schedule(panel, projectId);
    } catch (error) {
      const fallback = {
        ...(panel.__devpilotLastDelivery || {}),
        last_error: error?.message || 'Não foi possível consultar a publicação agora.',
      };
      panel.__devpilotLastDelivery = fallback;
      render(panel, fallback);
      schedule(panel, projectId);
    } finally {
      inFlight.delete(projectId);
    }
  }

  async function retryOnce(panel) {
    const gameState = controller()?.snapshot?.();
    if (!gameState?.projectId || typeof window.api !== 'function' || !canOperate()) return;
    const projectId = String(gameState.projectId);
    try {
      const delivery = await window.api(`${endpoint(projectId)}/retry`, {
        method: 'POST',
        timeoutMs: 45000,
        retry: false,
      });
      if (panel?.isConnected) {
        panel.__devpilotLastDelivery = delivery || {};
        render(panel, panel.__devpilotLastDelivery);
      }
      document.dispatchEvent(new CustomEvent(
        delivered(delivery) ? 'devpilot:delivery:ready' : 'devpilot:delivery:updated',
        {detail: delivery || {}},
      ));
    } catch (error) {
      if (panel?.isConnected) {
        const fallback = {
          ...(panel.__devpilotLastDelivery || {}),
          last_error: error?.message || 'A tentativa manual de entrega falhou.',
        };
        panel.__devpilotLastDelivery = fallback;
        render(panel, fallback);
      }
    } finally {
      if (panel?.isConnected) void refresh(panel);
    }
  }

  function sync() {
    const gameState = controller()?.snapshot?.();
    const panel = round();
    if (!panel || !gameState?.done || !gameState.projectId) return;
    const projectId = String(gameState.projectId);
    if (!panel.querySelector('.stable-delivery-url')) {
      render(panel, panel.__devpilotLastDelivery || {status: 'provisioning'});
    }
    if (!timers.has(projectId) && !inFlight.has(projectId)) void refresh(panel);
  }

  const acceptDeliveryEvent = event => {
    const panel = round();
    const gameState = controller()?.snapshot?.();
    if (!panel || !gameState?.done || !gameState.projectId || !event?.detail) return;
    panel.__devpilotLastDelivery = event.detail;
    render(panel, event.detail);
    if (delivered(event.detail)) clearProjectTimer(String(gameState.projectId));
    else schedule(panel, String(gameState.projectId));
  };

  document.addEventListener('devpilot:delivery:updated', acceptDeliveryEvent);
  document.addEventListener('devpilot:delivery:ready', acceptDeliveryEvent);
  document.addEventListener('devpilot:game:rendered', sync);
  document.addEventListener('devpilot:game:core-ready', sync);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) sync();
  });
  sync();
})();
