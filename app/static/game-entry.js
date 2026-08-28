/* DevPilot visible game entry. The game now runs in an isolated document. */
(() => {
  'use strict';

  if (window.__devpilotGameEntryReady) return;
  window.__devpilotGameEntryReady = true;

  const CARD_ID = 'devpilot-game-entry';
  const STYLE_ID = 'devpilot-game-entry-style';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const GAME_URL = '/game/index.html';

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const link = document.createElement('link');
    link.id = STYLE_ID;
    link.rel = 'stylesheet';
    link.href = '/assets/game-entry.css?v=20260825-1';
    document.head.appendChild(link);
  }

  const hasSession = () => Boolean(String(localStorage.getItem(MISSION_KEY) || '').trim());

  function label() {
    return hasSession() ? 'Continuar partida' : 'Jogar agora';
  }

  function createCard() {
    const overview = document.querySelector('#overview-view');
    if (!overview || document.getElementById(CARD_ID)) return false;
    ensureStyle();

    const card = document.createElement('article');
    card.id = CARD_ID;
    card.className = 'devpilot-game-entry';
    card.innerHTML = `
      <div class="devpilot-game-entry-copy">
        <span class="eyebrow">MODO JOGO · DESENVOLVIMENTO REAL</span>
        <h2>Construa software como uma missão.</h2>
        <p>Fases, XP, testes e entregas reais do projeto. O jogo abre em um runtime separado para não compartilhar timers, observers e listeners do dashboard.</p>
        <div class="devpilot-game-entry-status" aria-live="polite">
          <span data-game-entry-state>${hasSession() ? 'Partida encontrada neste dispositivo' : 'Pronto para uma nova partida'}</span>
          <small data-game-entry-project>${localStorage.getItem(PROJECT_KEY) ? 'Projeto da última partida selecionado' : 'Escolha o projeto ao entrar'}</small>
        </div>
      </div>
      <button type="button" class="primary devpilot-game-entry-action" data-open-game-entry>
        <span aria-hidden="true">🎮</span><strong>${label()}</strong><small>abrir jogo isolado</small>
      </button>
    `;

    const consultant = overview.querySelector('.consultant-promo');
    if (consultant) consultant.insertAdjacentElement('afterend', card);
    else overview.prepend(card);

    card.querySelector('[data-open-game-entry]')?.addEventListener('click', openGame);
    return true;
  }

  function openGame(event) {
    const button = event?.currentTarget || document.querySelector('[data-open-game-entry]');
    if (!(button instanceof HTMLButtonElement) || button.disabled) return;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    window.DevPilotResponses?.loading?.('Abrindo Modo Jogo isolado…', {timeout: 4000});
    try {
      window.DevPilotResponses?.success?.('Modo Jogo pronto. Abrindo runtime isolado.');
      window.location.assign(GAME_URL);
    } catch (error) {
      button.disabled = false;
      button.removeAttribute('aria-busy');
      window.DevPilotResponses?.error?.(error?.message || 'Falha ao abrir o Modo Jogo.');
    }
  }

  function boot() {
    ensureStyle();
    if (createCard()) return;
    const observer = new MutationObserver(() => {
      if (createCard()) observer.disconnect();
    });
    observer.observe(document.body, {childList: true, subtree: true});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
