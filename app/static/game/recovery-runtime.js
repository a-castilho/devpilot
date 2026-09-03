/* DevPilot game v82 — canonical failure recovery over the backend state machine. */
(() => {
  'use strict';

  if (window.__devpilotGameRecoveryV82Ready) return;
  window.__devpilotGameRecoveryV82Ready = true;

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

  const waitForCanonicalRecovery = async (engine, state, originalRetry) => {
    const taskId = String(state?.taskId || '').trim();
    if (!taskId) throw new Error('Execução com falha sem identificador.');

    // Archived/canceled runtime rows are intentionally invisible to the worker even when
    // tasks.status is still queued. They cannot enter failure-recovery because the persisted
    // Task row did not fail. Create exactly one replacement phase through the controller.
    const runtimeState = await orchestratorState(taskId);
    if (runtimeState === 'archived' || runtimeState === 'canceled' || runtimeState === 'cancel_requested') {
      return originalRetry();
    }

    let recovery = await recoveryRequest(taskId).catch(() => null);
    if (!recovery || recovery.state === 'ready_to_recover') {
      recovery = await recoveryRequest(taskId, 'escalate');
    }

    document.dispatchEvent(new CustomEvent('devpilot:game:recovery-state', {
      detail: {taskId, recovery},
    }));

    // The worker owns normal failed-task recovery. Once recovery succeeds it requeues the SAME
    // original task; the normal game refresh then sees queued/running/completed and continues.
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

      if (state.verifier) return originalRetry();

      const key = `${state.missionId}:${state.currentPhaseId}:${state.taskId}`;
      if (inFlight.has(key)) return inFlight.get(key);
      const promise = waitForCanonicalRecovery(engine, state, originalRetry)
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
