/* DevPilot stable game delivery observer — rendering only; backend owns deploy/recovery. */
(() => {
  'use strict';

  if (window.__devpilotStableDeliveryUrlReady) return;
  window.__devpilotStableDeliveryUrlReady = true;

  const WATCH_MS = 30000;
  const inFlight = new Set();
  const timers = new Map();
  const lastRenderSignature = new Map();

  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const safeUrl = value => {
    const candidate = String(value || '').trim();
    return /^https:\/\//i.test(candidate) ? candidate : '';
  };
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
    const heading = panel.querySelector('h1');
    const kicker = panel.querySelector('.game74-kicker');
    const status = panel.querySelector('.game74-status');
    const primary = panel.querySelector('.game74-actions .game74-primary');
    const newRound = panel.querySelector('[data-stable-new]');

    panel.dataset.deliveryUrlReady = ready ? '1' : '0';
    panel.dataset.deliveryWatch = ready ? '0' : '1';

    if (ready) {
      if (kicker) kicker.textContent = 'MISSÃO CUMPRIDA';
      if (heading) heading.textContent = 'Entrega concluída';
      if (status) status.innerHTML = '🏆 <strong>Pronto.</strong> Entrega validada e URL pública disponível para teste.';
      if (primary) primary.textContent = '🏆 Entrega pronta';
      if (newRound) newRound.hidden = false;
      return;
    }

    if (kicker) kicker.textContent = 'PUBLICAÇÃO FINAL';
    if (heading) heading.textContent = 'Finalizando a entrega';
    if (status) status.innerHTML = '⏳ <strong>A publicação ainda não terminou.</strong> O backend continua a recuperação; esta tela apenas acompanha o estado.';
    if (primary) primary.textContent = '⏳ Aguardando publicação';
    if (newRound) newRound.hidden = true;
  }

  const signature = delivery => JSON.stringify({
    status: normalized(delivery),
    url: safeUrl(delivery?.url),
    last_error: String(delivery?.last_error || ''),
    gate: String(delivery?.delivery_gate || ''),
  });

  function render(panel, projectId, delivery = {}) {
    const nextSignature = signature(delivery);
    if (lastRenderSignature.get(projectId) === nextSignature && panel.querySelector('.stable-delivery-url')) return;
    lastRenderSignature.set(projectId, nextSignature);

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
      failed: 'A publicação encontrou uma falha; recuperação automática em andamento.',
      blocked: 'Publicação bloqueada; recuperação automática em andamento.',
    }[status] || 'Finalizando publicação…';

    node.innerHTML = `
      <small>URL DO PROJETO</small>
      <strong>${esc(statusText)}</strong>
      <p>A missão só será marcada como entregue quando uma URL HTTPS real estiver validada.</p>
      <div class="stable-delivery-url-watch">A tela apenas observa. O worker continua o deploy e a recuperação mesmo se você sair daqui.</div>
      ${delivery?.last_error ? `<div class="stable-delivery-url-error">${esc(delivery.last_error)}</div>` : ''}
      <div class="stable-delivery-url-actions"><button class="game74-secondary" type="button" data-stable-delivery-refresh>↻ Atualizar estado</button></div>`;

    node.querySelector('[data-stable-delivery-refresh]')?.addEventListener('click', () => void refresh(panel, projectId));
  }

  function clearTimer(projectId) {
    const old = timers.get(projectId);
    if (old) window.clearTimeout(old);
    timers.delete(projectId);
  }

  function schedule(panel, projectId) {
    clearTimer(projectId);
    if (!projectId || document.visibilityState !== 'visible' || !panel.isConnected) return;
    const timer = window.setTimeout(() => {
      timers.delete(projectId);
      if (document.visibilityState === 'visible' && panel.isConnected) void refresh(panel, projectId);
    }, WATCH_MS);
    timers.set(projectId, timer);
  }

  async function refresh(panel, projectId) {
    if (!projectId || document.visibilityState !== 'visible' || inFlight.has(projectId)) return;
    inFlight.add(projectId);
    try {
      const delivery = await call(endpoint(projectId));
      render(panel, projectId, delivery || {});
      if (!delivered(delivery)) schedule(panel, projectId);
      else clearTimer(projectId);
    } catch (error) {
      render(panel, projectId, {status: 'failed', last_error: error?.message || 'Não foi possível consultar a entrega agora.'});
      schedule(panel, projectId);
    } finally {
      inFlight.delete(projectId);
    }
  }

  function sync() {
    if (document.visibilityState !== 'visible') return;
    const state = controller()?.snapshot?.();
    const panel = round();
    if (!panel || !state?.done || !state.projectId) return;
    const projectId = String(state.projectId);
    void refresh(panel, projectId);
  }

  let scheduled = false;
  const requestSync = () => {
    if (scheduled || document.visibilityState !== 'visible') return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      sync();
    });
  };

  document.addEventListener('devpilot:game:state', requestSync);
  document.addEventListener('devpilot:game:rendered', requestSync);
  document.addEventListener('devpilot:game:core-ready', requestSync);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') {
      for (const projectId of timers.keys()) clearTimer(projectId);
      return;
    }
    requestSync();
  });
  requestSync();
})();
