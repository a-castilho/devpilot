/* DevPilot game v91 — canonical recovery with explicit outcome state for the UI. */
(() => {
  'use strict';
  if (window.__devpilotGameRecoveryV91Ready) return;
  window.__devpilotGameRecoveryV91Ready = true;

  const patched = new WeakSet();
  const inFlight = new Map();
  const recoveryStates = new Map();

  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const canUseCanonicalRecovery = state => ['failed', 'blocked'].includes(normalize(state?.taskStatus));

  const request = async (taskId, action = '', payload = null) => {
    if (typeof window.api !== 'function' || !taskId) throw new Error('Recuperação indisponível.');
    const suffix = action ? `/recovery/${action}` : '/recovery';
    return window.api(`/tasks/${encodeURIComponent(taskId)}${suffix}`, {
      method: action ? 'POST' : 'GET',
      timeoutMs: 12000,
      retry: false,
      ...(payload ? {body: JSON.stringify(payload)} : {}),
    });
  };

  const publish = (taskId, recovery) => {
    const key = String(taskId || '').trim();
    if (key && recovery) recoveryStates.set(key, recovery);
    document.dispatchEvent(new CustomEvent('devpilot:game:recovery-state', {
      detail: {taskId: key, recovery: recovery || null},
    }));
    return recovery;
  };

  const readCanonicalRecovery = async (taskId, {escalate = true} = {}) => {
    let recovery = await request(taskId).catch(() => null);
    if (escalate && (!recovery || recovery.state === 'ready_to_recover')) {
      recovery = await request(taskId, 'escalate');
    }

    // A successful repair can occasionally finish before the worker's original-task requeue is
    // observed. The backend exposes this exact safe condition; resume it instead of reporting a
    // false terminal recovery_exhausted state.
    if (recovery?.can_resume_original) {
      recovery = await request(taskId, 'resume');
    }
    return publish(taskId, recovery);
  };

  const followCanonicalRecovery = async (engine, state) => {
    const taskId = String(state?.taskId || '').trim();
    if (!taskId) throw new Error('Execução com falha sem identificador.');

    const recovery = await readCanonicalRecovery(taskId, {escalate: true});

    // Backend/worker is the only recovery owner. Never manufacture [Jogo] Correção or replacement tasks here.
    // The same failed task is repaired, requeued and retested by the canonical backend flow.
    if (recovery?.state === 'resolved' || recovery?.state === 'retesting') {
      await window.loadBuildGame?.();
      engine.schedule?.();
    }

    // agent_recovery is deliberately not polled here. flow-keeper owns the single bounded
    // observation loop. Manual/terminal states remain visible until the user resolves them.
    return engine.snapshot?.() || state;
  };

  const patch = () => {
    const engine = window.__devpilotGameControllerV73;
    if (!engine || patched.has(engine) || typeof engine.retry !== 'function') return false;
    const originalRetry = engine.retry.bind(engine);

    engine.retry = async () => {
      const state = engine.snapshot?.();
      // Canceled tasks are recreated by the original controller; failed/blocked tasks use the
      // canonical backend repair flow so no duplicate phase/gate is manufactured by the browser.
      if (!state?.currentPhaseId || !canUseCanonicalRecovery(state)) return originalRetry();

      const key = `${state.missionId}:${state.currentPhaseId}:${state.taskId}:${state.verifier ? 'gate' : 'phase'}`;
      if (inFlight.has(key)) return inFlight.get(key);

      const promise = followCanonicalRecovery(engine, state)
        .catch(error => {
          console.error('[DevPilot Canonical Recovery]', error);
          throw error;
        })
        .finally(() => inFlight.delete(key));
      inFlight.set(key, promise);
      return promise;
    };

    patched.add(engine);
    document.dispatchEvent(new CustomEvent('devpilot:game:recovery-ready'));
    return true;
  };

  window.__devpilotGameRecoveryForTask = taskId => recoveryStates.get(String(taskId || '').trim()) || null;
  window.__devpilotGameRefreshRecovery = async taskId => {
    const key = String(taskId || '').trim();
    if (!key) return null;
    return readCanonicalRecovery(key, {escalate: false});
  };

  document.addEventListener('devpilot:game:core-ready', patch);
  document.addEventListener('devpilot:game:rendered', patch);
  document.addEventListener('devpilot:game:state', patch);
  patch();
})();
