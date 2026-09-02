/* DevPilot game v75 — keeps an active round moving even when the first task is not immediately visible in /tasks. */
(() => {
  'use strict';

  if (window.__devpilotGameFlowKeeperV75Ready) return;
  window.__devpilotGameFlowKeeperV75Ready = true;

  const VISIBLE_DELAY_MS = 2500;
  const HIDDEN_DELAY_MS = 8000;
  let timer = 0;
  let busy = false;

  const controller = () => window.__devpilotGameControllerV73;
  const delay = () => document.hidden ? HIDDEN_DELAY_MS : VISIBLE_DELAY_MS;

  const shouldKeepMoving = state => Boolean(
    state &&
    state.missionId &&
    state.goal &&
    !state.done &&
    !state.failed
  );

  const arm = () => {
    window.clearTimeout(timer);
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldKeepMoving(state)) {
      timer = 0;
      return;
    }
    timer = window.setTimeout(run, delay());
  };

  async function run() {
    if (busy) return arm();
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldKeepMoving(state)) return arm();

    busy = true;
    try {
      // The POST that starts a round may finish before the task appears in the list endpoint.
      // While that happens, only reload state; do not create another task.
      if (!state.hasTasks && typeof window.loadBuildGame === 'function') {
        await window.loadBuildGame();
      } else {
        await engine.refresh();
      }
    } catch (error) {
      console.error('[DevPilot Game Flow Keeper]', error);
    } finally {
      busy = false;
      arm();
    }
  }

  document.addEventListener('devpilot:game:state', arm);
  document.addEventListener('devpilot:game:rendered', arm);
  document.addEventListener('visibilitychange', arm);
  document.addEventListener('devpilot:game:core-ready', arm);
  arm();
})();
