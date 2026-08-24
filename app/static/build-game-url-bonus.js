/* DevPilot Build Game victory reward: expose a verified test URL after the final phase. */
(() => {
  'use strict';

  const PROJECT_KEY = 'devpilot-build-game-project';
  const OPERATORS = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);
  const inFlight = new Set();

  const escapeHtml = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const safeUrl = value => {
    const candidate = String(value || '').trim();
    return /^https?:\/\//i.test(candidate) ? candidate : '';
  };

  const role = () => String((typeof state !== 'undefined' && state.currentUser?.role) || '').toUpperCase();
  const canOperate = () => OPERATORS.has(role());
  const projectId = () => String(localStorage.getItem(PROJECT_KEY) || '').trim();

  const statusText = status => ({
    pending: 'Bônus disponível para resgate',
    provisioning: 'Preparando ambiente de teste',
    deploying: 'Publicando ambiente de teste',
    ready: 'URL de teste liberada',
    failed: 'A publicação precisa ser repetida',
    blocked: 'Infraestrutura pendente',
  })[status] || 'Preparando bônus';

  const actionFor = status => {
    if (status === 'failed' || status === 'blocked') {
      return {endpoint: 'retry', label: '↻ Tentar gerar URL'};
    }
    if (status === 'deploying' || status === 'provisioning') {
      return {endpoint: 'verify', label: 'Verificar URL'};
    }
    return {endpoint: 'start', label: '🎁 Resgatar bônus e gerar URL'};
  };

  const installStyle = () => {
    if (document.querySelector('#build-game-url-bonus-style')) return;
    const style = document.createElement('style');
    style.id = 'build-game-url-bonus-style';
    style.textContent = `
      .build-game-url-bonus{display:grid;gap:10px;margin-top:15px;padding:15px;border:1px solid rgba(95,224,255,.28);border-radius:14px;background:linear-gradient(135deg,rgba(28,100,91,.24),rgba(8,22,39,.8))}
      .build-game-url-bonus .eyebrow{color:#72efc5}
      .build-game-url-bonus-head{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}
      .build-game-url-bonus-head strong{font-size:1rem}
      .build-game-url-bonus-state{padding:5px 9px;border:1px solid rgba(114,239,197,.25);border-radius:999px;font-size:.68rem;font-weight:800;letter-spacing:.06em;color:#72efc5}
      .build-game-url-bonus p{margin:0;color:var(--muted,#9eacc2)}
      .build-game-url-value{display:block;padding:10px 12px;border:1px solid rgba(255,255,255,.09);border-radius:10px;background:rgba(0,0,0,.2);font:600 .78rem ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere;color:#8be9fd;text-decoration:none}
      .build-game-url-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
      .build-game-url-actions .primary{display:inline-flex;align-items:center;justify-content:center;text-decoration:none}
      .build-game-url-error{font-size:.76rem;color:#ffc56e}
      @media(max-width:800px){.build-game-url-actions>*{width:100%}.build-game-url-bonus-head{align-items:flex-start}}
    `;
    document.head.appendChild(style);
  };

  const rewardHost = panel => {
    let host = panel.querySelector('.build-game-url-bonus');
    if (!host) {
      host = document.createElement('div');
      host.className = 'build-game-url-bonus';
      panel.appendChild(host);
    }
    return host;
  };

  const render = (panel, delivery = {}) => {
    const host = rewardHost(panel);
    const status = String(delivery.status || 'pending').toLowerCase();
    const url = safeUrl(delivery.url);

    if (status === 'ready' && url) {
      host.innerHTML = `
        <span class="eyebrow">🎁 BÔNUS DO JOGO DESBLOQUEADO</span>
        <div class="build-game-url-bonus-head">
          <strong>URL de teste liberada</strong>
          <span class="build-game-url-bonus-state">PRONTO PARA TESTAR</span>
        </div>
        <p>Você venceu o chefe final. O prêmio é o ambiente publicado e validado para testar o sistema construído.</p>
        <a class="build-game-url-value" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>
        <div class="build-game-url-actions"><a class="primary" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Abrir sistema ↗</a></div>
      `;
      return;
    }

    const action = actionFor(status);
    const canRun = canOperate();
    const pendingCopy = status === 'pending'
      ? 'A missão terminou. Resgate o bônus para publicar um ambiente de homologação e receber a URL real do sistema.'
      : status === 'blocked'
        ? 'O bônus continua desbloqueado, mas a infraestrutura cloud precisa estar configurada antes da publicação.'
        : status === 'failed'
          ? 'A tentativa de publicação não terminou. Você pode repetir sem perder o progresso da partida.'
          : 'A publicação já começou. Verifique novamente até o ambiente passar pelos checks de backend, frontend e banco.';

    host.innerHTML = `
      <span class="eyebrow">🎁 BÔNUS DO JOGO DESBLOQUEADO</span>
      <div class="build-game-url-bonus-head">
        <strong>${escapeHtml(statusText(status))}</strong>
        <span class="build-game-url-bonus-state">URL DE TESTE</span>
      </div>
      <p>${escapeHtml(pendingCopy)}</p>
      ${delivery.last_error ? `<div class="build-game-url-error">${escapeHtml(delivery.last_error)}</div>` : ''}
      <div class="build-game-url-actions">
        ${canRun ? `<button class="primary" type="button" data-game-url-action="${action.endpoint}">${escapeHtml(action.label)}</button>` : '<span class="build-game-url-error">Um OWNER, ADMIN ou SUPER_ADMIN deve autorizar a publicação.</span>'}
      </div>
    `;

    host.querySelector('[data-game-url-action]')?.addEventListener('click', event => {
      void runAction(panel, event.currentTarget);
    });
  };

  const fetchDelivery = async id => api(`/projects/${encodeURIComponent(id)}/delivery`);

  const runAction = async (panel, button) => {
    const id = projectId();
    if (!id || !canOperate() || inFlight.has(id)) return;
    const action = String(button?.dataset.gameUrlAction || 'start');
    if (!['start', 'retry', 'verify'].includes(action)) return;

    inFlight.add(id);
    const original = button.textContent;
    button.disabled = true;
    button.textContent = action === 'verify' ? 'Verificando…' : 'Publicando…';
    try {
      const delivery = await api(`/projects/${encodeURIComponent(id)}/delivery/${action}`, {method: 'POST'});
      render(panel, delivery || {});
      if (delivery?.status === 'ready' && safeUrl(delivery.url)) {
        if (typeof toast === 'function') toast('🎁 Bônus liberado: URL de teste pronta.');
      } else if (delivery?.status === 'blocked') {
        if (typeof toast === 'function') toast('Bônus desbloqueado; configure a infraestrutura para gerar a URL.');
      } else if (delivery?.status === 'failed') {
        if (typeof toast === 'function') toast(delivery.last_error || 'A publicação precisa ser repetida.');
      } else if (typeof toast === 'function') {
        toast('Publicação iniciada. Verifique a URL quando os checks terminarem.');
      }
    } catch (error) {
      if (typeof toast === 'function') toast(error?.message || 'Não foi possível gerar a URL de teste.');
      try {
        render(panel, await fetchDelivery(id));
      } catch (_) {
        render(panel, {status: 'failed', last_error: 'Não foi possível consultar a publicação agora.'});
      }
    } finally {
      inFlight.delete(id);
      if (button?.isConnected) {
        button.disabled = false;
        button.textContent = original;
      }
    }
  };

  const hydrate = async panel => {
    const id = projectId();
    if (!id || panel.dataset.gameUrlBonusLoading === '1') return;
    panel.dataset.gameUrlBonusLoading = '1';
    installStyle();
    const host = rewardHost(panel);
    host.innerHTML = '<span class="eyebrow">🎁 BÔNUS DO JOGO</span><strong>Consultando URL de teste…</strong>';
    try {
      render(panel, await fetchDelivery(id));
    } catch (_) {
      render(panel, {status: 'pending'});
    } finally {
      panel.dataset.gameUrlBonusLoading = '0';
    }
  };

  const scan = () => {
    const panel = document.querySelector('#build-game-view .build-game-victory');
    if (!panel || panel.dataset.gameUrlBonusBound === '1') return;
    panel.dataset.gameUrlBonusBound = '1';
    void hydrate(panel);
  };

  const boot = () => {
    scan();
    const root = document.querySelector('#build-game-view') || document.body;
    if (!root || root.dataset.gameUrlBonusObserved === '1') return;
    root.dataset.gameUrlBonusObserved = '1';
    new MutationObserver(scan).observe(root, {childList: true, subtree: true});
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
  window.setTimeout(boot, 700);
})();
