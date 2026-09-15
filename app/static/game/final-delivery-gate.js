/* DevPilot final delivery gate — keep every final-round surface consistent with real delivery readiness. */
(() => {
  'use strict';

  if (window.__devpilotFinalDeliveryGateReady) return;
  window.__devpilotFinalDeliveryGateReady = true;

  const ROOT_SELECTOR = '#devpilot-game-stable-round-v91';
  const CARD_SELECTOR = `${ROOT_SELECTOR} [data-stable-round-card]`;

  const controller = () => window.__devpilotGameControllerV73;
  const stableCard = () => document.querySelector(CARD_SELECTOR);
  const isDone = () => Boolean(controller()?.snapshot?.()?.done);
  const isReady = card => card?.dataset?.deliveryUrlReady === '1';

  function enforceStableCard(card) {
    if (!card || !isDone()) return;
    const ready = isReady(card);
    const kicker = card.querySelector('.game74-kicker');
    const heading = card.querySelector('h1');
    const status = card.querySelector('.game74-status');
    const primary = card.querySelector('.game74-actions .game74-primary');
    const newRound = card.querySelector('[data-stable-new]');

    if (!ready) {
      if (kicker) kicker.textContent = 'PUBLICAÇÃO FINAL';
      if (heading) heading.textContent = 'Finalizando a entrega';
      if (status) status.innerHTML = '🚀 <strong>Quase pronto.</strong> Publicando e validando a URL real do projeto.';
      if (primary) {
        primary.textContent = '🚀 Publicando e validando URL';
        primary.disabled = true;
      }
      if (newRound) {
        newRound.hidden = true;
        newRound.disabled = true;
      }
      return;
    }

    if (newRound) {
      newRound.hidden = false;
      newRound.disabled = false;
    }
  }

  function suppressLegacyFinalCards(primary) {
    if (!isDone()) return;
    document.querySelectorAll('.game74').forEach(card => {
      if (card === primary || card.closest(ROOT_SELECTOR)) return;
      const text = String(card.textContent || '');
      if (!/Entrega concluída|Entrega pronta|MISSÃO CUMPRIDA/i.test(text)) return;
      card.dataset.devpilotLegacyFinalSuppressed = '1';
      card.hidden = true;
      card.setAttribute('aria-hidden', 'true');
      card.style.setProperty('display', 'none', 'important');
    });
  }

  function blockLegacyNewRound(primary) {
    if (!isDone() || isReady(primary)) return;
    document.querySelectorAll('button').forEach(button => {
      if (primary?.contains(button)) return;
      if (!/nova rodada/i.test(String(button.textContent || ''))) return;
      button.disabled = true;
      button.hidden = true;
    });
  }

  function sync() {
    const primary = stableCard();
    if (!primary || !isDone()) return;
    enforceStableCard(primary);
    suppressLegacyFinalCards(primary);
    blockLegacyNewRound(primary);
  }

  let queued = false;
  const schedule = () => {
    if (queued) return;
    queued = true;
    window.requestAnimationFrame(() => {
      queued = false;
      sync();
    });
  };

  document.addEventListener('devpilot:delivery:updated', schedule);
  document.addEventListener('devpilot:delivery:ready', schedule);
  document.addEventListener('devpilot:game:state', schedule);
  document.addEventListener('devpilot:game:rendered', schedule);
  document.addEventListener('devpilot:game:core-ready', schedule);
  document.addEventListener('devpilot:game:enhancements-ready', schedule);
  document.addEventListener('visibilitychange', schedule);
  schedule();
})();
