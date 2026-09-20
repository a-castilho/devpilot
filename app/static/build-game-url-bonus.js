/* DevPilot Build Game victory reward: passive view of the backend-verified final URL. */
(() => {
  'use strict';

  if (window.__devpilotBuildGameUrlBonusPassiveReady) return;
  window.__devpilotBuildGameUrlBonusPassiveReady = true;

  const PROJECT_KEY = 'devpilot-build-game-project';
  const WATCH_MS = 15000;
  let timer = 0;
  let loading = false;

  const escapeHtml = value => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const safeUrl = value => /^https:\/\//i.test(String(value || '').trim()) ? String(value || '').trim() : '';
  const normalizedStatus = delivery => String(delivery?.status || 'pending').toLowerCase();
  const missionDelivered = delivery => normalizedStatus(delivery) === 'ready' && Boolean(safeUrl(delivery?.url));
  const projectId = () => String(localStorage.getItem(PROJECT_KEY) || '').trim();
  const victoryPanel = () => document.querySelector('#build-game-view .build-game-victory');

  const ensureHost = panel => {
    let host = panel.querySelector('.build-game-url-bonus');
    if (!host) {
      host = document.createElement('div');
      host.className = 'build-game-url-bonus';
      panel.appendChild(host);
    }
    return host;
  };

  const setMissionGate = (panel, delivery = {}) => {
    const delivered = missionDelivered(delivery);
    const eyebrow = Array.from(panel.children || []).find(element => element.classList?.contains('eyebrow'));
    const heading = Array.from(panel.children || []).find(element => element.tagName === 'H3');
    const summary = Array.from(panel.children || []).find(element => element.tagName === 'P');

    if (summary && !panel.dataset.gameOriginalVictorySummary) {
      panel.dataset.gameOriginalVictorySummary = String(summary.textContent || '').trim();
    }
    const originalSummary = panel.dataset.gameOriginalVictorySummary || '';

    if (delivered) {
      panel.dataset.gameMissionDelivered = '1';
      if (eyebrow) eyebrow.textContent = 'MISSÃO CONCLUÍDA';
      if (heading) heading.textContent = '🏆 Sistema entregue e URL validada';
      if (summary) summary.textContent = `${originalSummary}${originalSummary ? ' ' : ''}URL pública validada e pronta para teste.`;
      return;
    }

    panel.dataset.gameMissionDelivered = '0';
    if (eyebrow) eyebrow.textContent = 'CHEFE FINAL VENCIDO · ENTREGA PENDENTE';
    if (heading) heading.textContent = '🚀 Finalizando publicação e URL';
    if (summary) {
      summary.textContent = `${originalSummary}${originalSummary ? ' ' : ''}A missão só será concluída quando uma URL pública real responder com sucesso.`;
    }
  };

  const render = (panel, delivery = {}) => {
    setMissionGate(panel, delivery);
    const host = ensureHost(panel);
    const url = safeUrl(delivery?.url);
    const status = normalizedStatus(delivery);

    if (missionDelivered(delivery)) {
      host.innerHTML = `
        <span class="eyebrow">🎁 ENTREGA FINAL CONCLUÍDA</span>
        <strong>URL de teste liberada</strong>
        <p>A validação real foi concluída pelo backend.</p>
        <a class="build-game-url-value" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>
        <div class="build-game-url-actions"><a class="primary" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Abrir sistema ↗</a></div>`;
      return;
    }

    const labels = {
      pending: 'Preparando publicação final…',
      repairing: 'Corrigindo o produto final…',
      provisioning: 'Preparando infraestrutura…',
      deploying: 'Publicando e validando URL…',
      blocked: 'Recuperação automática em andamento…',
      failed: 'Nova tentativa automática agendada…',
    };
    host.innerHTML = `
      <span class="eyebrow">🚀 ENTREGA FINAL OBRIGATÓRIA</span>
      <strong>${escapeHtml(labels[status] || 'Finalizando entrega…')}</strong>
      <p>O backend continua o fluxo mesmo com esta aba fechada. Esta tela apenas acompanha o estado persistido.</p>
      ${delivery?.last_error ? `<div class="build-game-url-error">${escapeHtml(delivery.last_error)}</div>` : ''}`;
  };

  const schedule = panel => {
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      timer = 0;
      if (panel?.isConnected && !document.hidden) void refresh(panel);
      else if (panel?.isConnected) schedule(panel);
    }, WATCH_MS);
  };

  const refresh = async panel => {
    const id = projectId();
    if (!id || !panel?.isConnected || loading || typeof api !== 'function') return;
    loading = true;
    try {
      const delivery = await api(`/projects/${encodeURIComponent(id)}/delivery`);
      render(panel, delivery || {});
      if (missionDelivered(delivery)) {
        if (timer) window.clearTimeout(timer);
        timer = 0;
        document.dispatchEvent(new CustomEvent('devpilot:delivery:ready', {detail: delivery}));
      } else {
        schedule(panel);
      }
    } catch (error) {
      render(panel, {status: 'failed', last_error: error?.message || 'Não foi possível consultar a publicação agora.'});
      schedule(panel);
    } finally {
      loading = false;
    }
  };

  const sync = () => {
    const panel = victoryPanel();
    if (!panel) return;
    if (!panel.querySelector('.build-game-url-bonus')) render(panel, {status: 'deploying'});
    if (!timer && !loading) void refresh(panel);
  };

  const accept = event => {
    const panel = victoryPanel();
    if (!panel || !event?.detail) return;
    render(panel, event.detail);
    if (missionDelivered(event.detail)) {
      if (timer) window.clearTimeout(timer);
      timer = 0;
    } else {
      schedule(panel);
    }
  };

  document.addEventListener('devpilot:delivery:updated', accept);
  document.addEventListener('devpilot:delivery:ready', accept);
  document.addEventListener('devpilot:game:rendered', sync);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) sync(); });
  sync();
})();
