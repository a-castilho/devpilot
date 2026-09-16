/* Autonomous recovery for a game stage that the task pipeline marks blocked. */
(() => {
  'use strict';
  if (window.__devpilotBlockedStageRecoveryReady) return;
  window.__devpilotBlockedStageRecoveryReady = true;

  const MAX_ATTEMPTS = 3;
  const RETRY_DELAY_MS = 1500;
  const attempts = new Map();
  let leaving = false;
  let busy = false;
  let timer = 0;

  const controller = () => window.__devpilotGameControllerV73;
  const keyFor = state => `${state?.missionId || ''}:${state?.currentPhaseId || 0}:${state?.taskId || ''}`;

  const stop = () => {
    leaving = true;
    if (timer) window.clearTimeout(timer);
    timer = 0;
  };

  async function recover() {
    if (leaving || busy || document.hidden) return;
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !state || state.done || state.taskStatus !== 'blocked') return;

    const key = keyFor(state);
    const count = attempts.get(key) || 0;
    if (count >= MAX_ATTEMPTS) return;
    attempts.set(key, count + 1);
    busy = true;
    try {
      await engine.retry();
      await engine.refresh?.();
    } catch (error) {
      console.warn('[DevPilot Stage Recovery]', error);
    } finally {
      busy = false;
    }
  }

  function inspect(event) {
    if (leaving) return;
    const state = event?.detail || controller()?.snapshot?.();
    if (!state || state.done || state.taskStatus !== 'blocked') return;
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      timer = 0;
      void recover();
    }, RETRY_DELAY_MS);
  }

  document.addEventListener('devpilot:game:state', inspect);
  document.addEventListener('devpilot:game:core-ready', inspect);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) inspect(); });
  document.addEventListener('devpilot:game:leaving', stop, {once: true});
  inspect();
})();
