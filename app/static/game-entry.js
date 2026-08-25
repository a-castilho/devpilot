/* DevPilot visible game entry. Lightweight core UI; the game bundle remains lazy. */
(() => {
  'use strict';

  if (window.__devpilotGameEntryReady) return;
  window.__devpilotGameEntryReady = true;

  const CARD_ID = 'devpilot-game-entry';
  const STYLE_ID = 'devpilot-game-entry-style';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const PROJECT_KEY = 'devpilot-build-game-project';

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
        <p>Fases, XP, testes e entregas reais do projeto. Cada avanço exige evidência técnica antes de liberar a próxima etapa.</p>
        <div class="devpilot-game-entry-status" aria-live="polite">
          <span data-game-entry-state>${hasSession() ? 'Partida encontrada neste dispositivo' : 'Pronto para uma nova partida'}</span>
          <small data-game-entry-project>${localStorage.getItem(PROJECT_KEY) ? 'Projeto da última partida selecionado' : 'Escolha o projeto ao entrar'}</small>
        </div>
      </div>
      <button type="button" class="primary devpilot-game-entry-action" data-open-game-entry>
        <span aria-hidden="true">🎮</span><strong>${label()}</strong><small>abrir cockpit</small>
      </button>
    `;

    const consultant = overview.querySelector('.consultant-promo');
    if (consultant) consultant.insertAdjacentElement('afterend', card);
    else overview.prepend(card);

    card.querySelector('[data-open-game-entry]')?.addEventListener('click', openGame);
    return true;
  }

  async function openGame(event) {
    const button = event?.currentTarget || document.querySelector('[data-open-game-entry]');
    if (!(button instanceof HTMLButtonElement) || button.disabled) return;

    const original = button.innerHTML;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    button.innerHTML = '<span aria-hidden="true">•</span><strong>Carregando jogo…</strong><small>preparando cockpit</small>';
    window.DevPilotResponses?.loading?.('Carregando Modo Jogo…', {timeout: 10000});

    try {
      const ok = await window.__devpilotLoadFeature?.('game');
      if (!ok) throw new Error('O módulo de jogo não pôde ser carregado por completo.');

      const target = document.querySelector('.nav[data-view="build-game"], .nav[data-view="game"]');
      if (!target) throw new Error('A navegação do Modo Jogo não ficou disponível.');
      target.click();
      window.DevPilotResponses?.success?.('Modo Jogo pronto. Boa missão.');
    } catch (error) {
      window.DevPilotResponses?.error?.(error?.message || 'Falha ao abrir o Modo Jogo.');
    } finally {
      button.disabled = false;
      button.removeAttribute('aria-busy');
      button.innerHTML = original.replace(/>Jogar agora</, `>${label()}<`).replace(/>Continuar partida</, `>${label()}<`);
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

  document.addEventListener('devpilot:game:entered', () => {
    document.querySelector('[data-open-game-entry] strong')?.replaceChildren(document.createTextNode('Continuar partida'));
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
