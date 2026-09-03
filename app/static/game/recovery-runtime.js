/* DevPilot game v86 — game delegates failures exclusively to backend failure recovery. */
(() => {
  'use strict';
  if (window.__devpilotGameRecoveryV86Ready) return;
  window.__devpilotGameRecoveryV86Ready = true;

  const patched = new WeakSet();
  const inFlight = new Map();
  const POLL_MS = 3500;

  const request = async (taskId, action = '') => {
    if (typeof window.api !== 'function' || !taskId) throw new Error('Recuperação indisponível.');
    const suffix = action ? `/recovery/${action}` : '/recovery';
    return window.api(`/tasks/${encodeURIComponent(taskId)}${suffix}`, {
      method: action ? 'POST' : 'GET', timeoutMs: 12000, retry: false,
    });
  };

  const publish = (taskId, recovery) => document.dispatchEvent(new CustomEvent('devpilot:game:recovery-state', {detail:{taskId,recovery}}));

  const followCanonicalRecovery = async (engine, state) => {
    const taskId = String(state?.taskId || '').trim();
    if (!taskId) throw new Error('Execução com falha sem identificador.');

    let recovery = await request(taskId).catch(() => null);
    if (!recovery || recovery.state === 'ready_to_recover') recovery = await request(taskId, 'escalate');
    publish(taskId, recovery);

    // Backend/worker is the only recovery owner. Never manufacture [Jogo] Correção or replacement tasks here.
    if (recovery?.state === 'resolved' || recovery?.state === 'retesting') {
      await window.loadBuildGame?.();
      engine.schedule?.();
      return engine.snapshot?.() || state;
    }

    if (recovery?.state === 'agent_recovery') {
      window.setTimeout(async () => {
        try { publish(taskId, await request(taskId)); await window.loadBuildGame?.(); }
        catch (_) {}
      }, POLL_MS);
    }

    // awaiting_intervention/intervention_required are shown only when the canonical backend says so.
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
      const promise = followCanonicalRecovery(engine, state)
        .catch(error => { console.error('[DevPilot Canonical Recovery]', error); throw error; })
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
