/* DevPilot game v81 — canonical failure recovery over the backend state machine. */
(() => {
  'use strict';

  if (window.__devpilotGameRecoveryV81Ready) return;
  window.__devpilotGameRecoveryV81Ready = true;

  const patched = new WeakSet();
  const inFlight = new Map();

  const recoveryRequest = async (taskId, action = '') => {
    if (typeof window.api !== 'function' || !taskId) throw new Error('Recuperação indisponível.');
    const suffix = action ? `/recovery/${action}` : '/recovery';
    return window.api(`/tasks/${encodeURIComponent(taskId)}${suffix}`, {
      method: action ? 'POST' : 'GET',
      timeoutMs: 12000,
      retry: false,
    });
  };

  const waitForCanonicalRecovery = async (engine, state) => {
    const taskId = String(state?.taskId || '').trim();
    if (!taskId) throw new Error('Execução com falha sem identificador.');

    let recovery = await recoveryRequest(taskId).catch(() => null);
    if (!recovery || recovery.state === 'ready_to_recover') {
      recovery = await recoveryRequest(taskId, 'escalate');
    }

    document.dispatchEvent(new CustomEvent('devpilot:game:recovery-state', {
      detail: {taskId, recovery},
    }));

    // The worker owns the recovery lifecycle. Never create a second [Jogo] correction task.
    // Once recovery succeeds it requeues the SAME original task; the normal game refresh then
    // sees queued/running/completed and continues to the independent verifier.
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
      if (!state?.failed || !state?.currentPhaseId) return originalRetry();

      // Verifier retries keep the verifier-specific contract. Base phase failures use the
      // backend recovery state machine, which is idempotent and already integrated with worker.
      if (state.verifier) return originalRetry();

      const key = `${state.missionId}:${state.currentPhaseId}:${state.taskId}`;
      if (inFlight.has(key)) return inFlight.get(key);
      const promise = waitForCanonicalRecovery(engine, state)
        .catch(error => {
          console.error('[DevPilot Game Recovery]', error);
          throw error;
        })
        .finally(() => window.setTimeout(() => inFlight.delete(key), 1500));
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
