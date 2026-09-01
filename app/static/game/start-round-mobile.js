/* DevPilot standalone game: explicit first-round start action for mobile and desktop. */
(() => {
  'use strict';

  if (window.__devpilotGameStartRoundReady) return;
  window.__devpilotGameStartRoundReady = true;

  const toastMessage = message => {
    if (typeof window.toast === 'function') return window.toast(message);
    const node = document.querySelector('#toast');
    if (!node) return;
    node.textContent = message;
    node.classList.add('show');
    window.setTimeout(() => node.classList.remove('show'), 2200);
  };

  const isInitialRound = view => {
    if (!view) return false;
    if (view.querySelector('.build-game-phase.passed')) return false;
    const progress = String(view.querySelector('.build-game-score strong')?.textContent || '');
    return !progress || /0\s*\/\s*7/.test(progress) || Boolean(view.querySelector('.build-game-phase.current [data-play-phase]'));
  };

  const firstPlayable = view => view?.querySelector('.build-game-phase.current [data-play-phase]:not([disabled])')
    || view?.querySelector('[data-play-phase]:not([disabled])');

  const beginRound = view => {
    const goal = view?.querySelector('#build-game-goal');
    const value = String(goal?.value || '').trim();
    if (!value) {
      goal?.focus();
      goal?.scrollIntoView({behavior:'smooth', block:'center'});
      toastMessage('Descreva a entrega da rodada para iniciar o jogo');
      return false;
    }

    goal.value = value;
    goal.dispatchEvent(new Event('input', {bubbles:true}));
    goal.dispatchEvent(new Event('change', {bubbles:true}));

    const phaseButton = firstPlayable(view);
    if (!phaseButton) {
      toastMessage('A primeira etapa ainda não está disponível. Atualize a partida.');
      return false;
    }

    phaseButton.scrollIntoView({behavior:'smooth', block:'center'});
    phaseButton.click();
    return true;
  };

  const decorate = () => {
    const view = document.querySelector('#build-game-view');
    const button = view?.querySelector('#build-game-new');
    if (!view || !button) return false;

    const initial = isInitialRound(view);
    button.dataset.gameInitialRound = initial ? '1' : '0';
    button.textContent = initial ? 'Iniciar jogo' : 'Nova rodada';
    button.classList.toggle('primary', initial);
    button.classList.toggle('ghost', !initial);
    button.setAttribute('aria-label', initial ? 'Iniciar jogo com a entrega informada' : 'Começar uma nova rodada');

    if (button.dataset.gameStartRoundBound === '1') return true;
    button.dataset.gameStartRoundBound = '1';
    button.addEventListener('click', event => {
      if (button.dataset.gameInitialRound !== '1') return;
      event.preventDefault();
      event.stopImmediatePropagation();
      beginRound(view);
    }, true);
    return true;
  };

  const observer = new MutationObserver(() => decorate());
  observer.observe(document.documentElement, {childList:true, subtree:true});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', decorate, {once:true});
  else decorate();
})();
