/* DevPilot standalone game action runtime.
 * Owns the only post-boot wrapper around loadBuildGame and serializes UI actions
 * so low-memory mobile browsers never process overlapping renders.
 */
(() => {
  'use strict';

  if (window.__devpilotGameActionRuntimeReady) return;

  const baseLoad = window.loadBuildGame;
  if (typeof baseLoad !== 'function') return;

  window.__devpilotGameActionRuntimeReady = true;
  window.__devpilotBaseLoadBuildGame = baseLoad;

  let loadInFlight = null;
  let loadRequested = false;
  let renderSequence = 0;
  const actions = new Map();
  const lastTap = new Map();

  const yieldToBrowser = () => new Promise(resolve => window.setTimeout(resolve, 0));

  const emitRendered = reason => {
    renderSequence += 1;
    document.dispatchEvent(new CustomEvent('devpilot:game:rendered', {
      detail: {sequence: renderSequence, reason: String(reason || 'load')},
    }));
  };

  const runLoadCycle = async args => {
    let result;
    do {
      loadRequested = false;
      result = await baseLoad(...args);
      emitRendered('load');
      await yieldToBrowser();
    } while (loadRequested);
    return result;
  };

  window.loadBuildGame = async (...args) => {
    if (loadInFlight) {
      loadRequested = true;
      return loadInFlight;
    }

    loadInFlight = runLoadCycle(args);
    try {
      return await loadInFlight;
    } finally {
      loadInFlight = null;
    }
  };

  const runAction = async (key, action) => {
    const normalizedKey = String(key || 'default');
    const current = actions.get(normalizedKey);
    if (current) return current;

    const promise = (async () => {
      try {
        return await action();
      } finally {
        actions.delete(normalizedKey);
      }
    })();

    actions.set(normalizedKey, promise);
    return promise;
  };

  // Prevent rapid double taps from scheduling duplicate work while still letting
  // normal clicks bubble to the owning handler.
  document.addEventListener('click', event => {
    const button = event.target?.closest?.(
      '[data-play-phase],[data-game-refresh],[data-objective-start],[data-objective-save],[data-objective-new],[data-objective-refresh],#build-game-new'
    );
    if (!button) return;

    const key = button.id
      || button.dataset.playPhase
      || [...button.attributes]
        .find(attribute => attribute.name.startsWith('data-objective-') || attribute.name === 'data-game-refresh')?.name
      || button.textContent
      || 'action';
    const now = Date.now();
    const previous = lastTap.get(key) || 0;
    if (now - previous < 650) {
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    lastTap.set(key, now);
  }, true);

  window.__devpilotGameRunAction = runAction;
  window.__devpilotGameLoadInFlight = () => Boolean(loadInFlight);
  window.__devpilotGameRenderSequence = () => renderSequence;

  // Core render happened before optional enhancements are loaded. Emit one stable
  // render event after installing the coordinator so enhancement modules can mount
  // without observing the DOM continuously.
  window.setTimeout(() => emitRendered('action-runtime-ready'), 0);
})();
