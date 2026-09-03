/* DevPilot game v88 — one-shot canonical recovery without browser request loops. */
(() => {
  'use strict';
  if (window.__devpilotGameRecoveryV88Ready) return;
  window.__devpilotGameRecoveryV88Ready = true;

  const patched = new WeakSet();
  const inFlight = new Map();

  const request = async (taskId, action = '') => {
    if (typeof window.api !== 'function' || !taskId) throw new Error('Recuperação indisponível.');
    const suffix = action ? `/recovery/${action}` : '/recovery';
    return window.api(`/tasks/${encodeURIComponent(taskId)}${suffix}`, {
      method: action ? 'POST' : 'GET', timeoutMs: 12000, retry: false,
    });
  };

  const orchestratorState = async taskId => {
    if (!taskId) return '';
    const cached = window.__devpilotGameRuntimeStates?.()?.[taskId]?.state;
    if (cached) return String(cached).trim().toLowerCase();
    try {
      const payload = await window.api(`/tasks/${encodeURIComponent(taskId)}/orchestrator`, {
        timeoutMs: 7000,
        retry: false,
      });
      return String(payload?.state || '').trim().toLowerCase();
    } catch (_) {
      return '';
    }
  };

  const publish = (taskId, recovery) => document.dispatchEvent(new CustomEvent(
    'devpilot:game:recovery-state',
    {detail:{taskId,recovery}},
  ));

  const followCanonicalRecovery = async (engine, state, originalRetry) => {
    const taskId = String(state?.taskId || '').trim();
    if (!taskId) throw new Error('Execução com falha sem identificador.');

    // Runtime archived/canceled is not a real execution failure. Let the controller
    // create the single replacement expected for that orchestration state.
    const runtimeState = await orchestratorState(taskId);
    if (runtimeState === 'archived' || runtimeState === 'canceled' || runtimeState === 'cancel_requested') {
      return originalRetry();
    }

    let recovery = await request(taskId).catch(() => null);
    if (!recovery || recovery.state === 'ready_to_recover') recovery = await request(taskId, 'escalate');
    publish(taskId, recovery);

    // Backend/worker owns the recovery lifecycle. The browser only delegates once;
    // flow-keeper observes the task with a bounded cadence instead of polling /recovery.
    if (recovery?.state === 'resolved' || recovery?.state === 'retesting') {
      await window.loadBuildGame?.();
      engine.schedule?.();
    }

    return engine.snapshot?.() || state;
  };

  const patch = () => {
    const engine = window.__devpilotGameControllerV73;
    if (!engine || patched.has(engine) || typeof engine.retry !== 'function') return false;
    const originalRetry = engine.retry.bind(engine);

    engine.retry = async () => {
      const state = engine.snapshot?.();
      if (!state?.failed || !state?.currentPhaseId || state.verifier) return originalRetry();

      const key = `${state.missionId}:${state.currentPhaseId}:${state.taskId}`;
      if (inFlight.has(key)) return inFlight.get(key);

      const promise = followCanonicalRecovery(engine, state, originalRetry)
        .catch(error => {
          console.error('[DevPilot Canonical Recovery]', error);
          throw error;
        })
        .finally(() => window.setTimeout(() => inFlight.delete(key), 1200));

      inFlight.set(key, promise);
      return promise;
    };

    patched.add(engine);
    document.dispatchEvent(new CustomEvent('devpilot:game:recovery-ready'));
    return true;
  };

  document.addEventListener('devpilot:game:core-ready', patch);
  document.addEventListener('devpilot:game:rendered', patch);
  document.addEventListener('devpilot:game:state', patch);
  patch();
})();
