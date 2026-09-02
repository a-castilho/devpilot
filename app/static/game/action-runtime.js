/* DevPilot standalone game action runtime.
 * Installs only after the core game has rendered. It serializes refreshes and
 * drops overlapping reload requests so low-memory browsers can always paint.
 */
(() => {
  'use strict';

  if (window.__devpilotGameActionRuntimeReady) return;

  const baseLoad = window.loadBuildGame;
  if (typeof baseLoad !== 'function') return;

  window.__devpilotGameActionRuntimeReady = true;
  window.__devpilotBaseLoadBuildGame = baseLoad;

  let loadInFlight = null;
  let renderSequence = 0;
  let coalescedLoadCount = 0;
  const actions = new Map();
  const lastTap = new Map();

  const yieldToBrowser = () => new Promise(resolve => window.setTimeout(resolve, 0));

  const emitRendered = reason => {
    renderSequence += 1;
    document.dispatchEvent(new CustomEvent('devpilot:game:rendered', {
      detail: {sequence: renderSequence, reason: String(reason || 'load')},
    }));
  };

  window.loadBuildGame = async (...args) => {
    if (loadInFlight) {
      coalescedLoadCount += 1;
      return loadInFlight;
    }

    // Schedule the actual loader on the next microtask. Assigning loadInFlight
    // first also protects against a synchronous/re-entrant loadBuildGame call.
    const currentLoad = Promise.resolve().then(async () => {
      const result = await baseLoad(...args);
      emitRendered('load');
      await yieldToBrowser();
      return result;
    });

    loadInFlight = currentLoad;
    try {
      return await currentLoad;
    } finally {
      if (loadInFlight === currentLoad) loadInFlight = null;
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
  // the first normal click reach the owning handler.
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
  window.__devpilotGameCoalescedLoadCount = () => coalescedLoadCount;
  window.__devpilotGameActionRuntimeVersion = 'v60-core-first';

  window.setTimeout(() => emitRendered('action-runtime-ready'), 0);
})();
