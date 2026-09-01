/* DevPilot standalone game: one-tap round launcher for mobile and desktop. */
(() => {
  'use strict';

  if (window.__devpilotGameStartRoundV54Ready) return;
  window.__devpilotGameStartRoundV54Ready = true;

  const MISSION_KEY = 'devpilot-build-game-mission';
  let internalReset = false;
  let launching = false;

  const toastMessage = message => {
    if (typeof window.toast === 'function') return window.toast(message);
    const node = document.querySelector('#toast');
    if (!node) return;
    node.textContent = message;
    node.classList.add('show');
    window.setTimeout(() => node.classList.remove('show'), 2600);
  };

  const viewNode = () => document.querySelector('#build-game-view');
  const goalNode = view => view?.querySelector('#build-game-goal');
  const firstPlayable = view => view?.querySelector('.build-game-phase.current [data-play-phase]:not([disabled])')
    || view?.querySelector('[data-play-phase]:not([disabled])');
  const hasRoundHistory = view => Boolean(view?.querySelector('.build-game-phase.passed'));

  const syncGoal = (goal, value) => {
    if (!goal) return false;
    goal.value = value;
    goal.dispatchEvent(new Event('input', {bubbles:true}));
    goal.dispatchEvent(new Event('change', {bubbles:true}));
    return true;
  };

  const waitForFreshRound = (previousMission, timeoutMs = 5000) => new Promise(resolve => {
    const started = Date.now();
    const check = () => {
      const view = viewNode();
      const goal = goalNode(view);
      const playable = firstPlayable(view);
      const currentMission = String(localStorage.getItem(MISSION_KEY) || '');
      if (view && goal && playable && currentMission && currentMission !== previousMission) {
        resolve({view, goal, playable});
        return;
      }
      if (Date.now() - started >= timeoutMs) {
        resolve(null);
        return;
      }
      window.setTimeout(check, 70);
    };
    check();
  });

  async function launchRound(button, view) {
    if (launching) return false;
    const goal = goalNode(view);
    const value = String(goal?.value || '').trim();
    if (!value) {
      goal?.focus();
      goal?.scrollIntoView?.({behavior:'smooth', block:'center'});
      toastMessage('Descreva a entrega da rodada para iniciar o jogo');
      return false;
    }

    launching = true;
    button.setAttribute('aria-busy', 'true');
    const originalText = button.textContent;
    button.textContent = 'Iniciando rodada…';

    try {
      const playable = firstPlayable(view);
      if (!hasRoundHistory(view) && playable) {
        syncGoal(goal, value);
        playable.scrollIntoView?.({behavior:'smooth', block:'center'});
        playable.click();
        return true;
      }

      const previousMission = String(localStorage.getItem(MISSION_KEY) || '');
      internalReset = true;
      const originalConfirm = window.confirm;
      try {
        window.confirm = () => true;
        button.click();
      } finally {
        window.confirm = originalConfirm;
        internalReset = false;
      }

      const fresh = await waitForFreshRound(previousMission);
      if (!fresh) {
        toastMessage('A nova rodada não ficou pronta. Toque em Atualizar e tente novamente.');
        return false;
      }

      syncGoal(fresh.goal, value);
      fresh.playable.scrollIntoView?.({behavior:'smooth', block:'center'});
      fresh.playable.click();
      return true;
    } catch (error) {
      console.error('[DevPilot Game] Falha ao iniciar rodada', error);
      toastMessage(error?.message || 'Não foi possível iniciar a rodada');
      return false;
    } finally {
      launching = false;
      if (button.isConnected) {
        button.removeAttribute('aria-busy');
        button.textContent = originalText || '▶ Iniciar rodada';
      }
      window.setTimeout(decorate, 0);
    }
  }

  function decorate() {
    const view = viewNode();
    const button = view?.querySelector('#build-game-new');
    if (!view || !button) return false;
    button.dataset.gameRoundLauncher = 'v54';
    button.textContent = '▶ Iniciar rodada';
    button.classList.add('primary');
    button.classList.remove('ghost');
    button.setAttribute('aria-label', 'Iniciar uma rodada com a entrega informada');
    return true;
  }

  document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target.closest('#build-game-view #build-game-new') : null;
    if (!target || internalReset) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    void launchRound(target, viewNode());
  }, true);

  const upstream = window.loadBuildGame;
  if (typeof upstream === 'function' && !upstream.__devpilotRoundLauncherV54) {
    const wrapped = async function loadBuildGameWithRoundLauncher(...args) {
      const result = await upstream.apply(this, args);
      window.requestAnimationFrame(decorate);
      return result;
    };
    wrapped.__devpilotRoundLauncherV54 = true;
    wrapped.__devpilotUpstream = upstream;
    window.loadBuildGame = wrapped;
  }

  document.addEventListener('devpilot:game:standalone-ready', decorate);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', decorate, {once:true});
  else decorate();
})();
