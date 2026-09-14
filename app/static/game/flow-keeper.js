/* DevPilot game v91 — one bounded failure observer; backend owns repair and retest. */
(() => {
  'use strict';
  if (window.__devpilotGameFlowKeeperV91Ready) return;
  window.__devpilotGameFlowKeeperV91Ready = true;

  const FIRST_FAILURE_DELAY_MS = 250;
  const FAILED_POLL_MS = 8000;
  const HIDDEN_FAILED_POLL_MS = 20000;
  const RECOVERY_RECHECK_MS = 30000;
  const TERMINAL_RECOVERY_STATES = new Set([
    'awaiting_intervention',
    'intervention_required',
    'recovery_exhausted',
  ]);
  const OBSERVED_FAILURE_STATUSES = new Set(['failed', 'blocked', 'canceled', 'cancelled']);

  let timer = 0;
  let busy = false;
  const recoveryChecks = new Map();

  const controller = () => window.__devpilotGameControllerV73;
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const shouldWatchFailure = state => Boolean(
    state && state.missionId && state.goal && state.taskId &&
    OBSERVED_FAILURE_STATUSES.has(normalize(state.taskStatus)) && !state.done
  );
  const isCanceled = state => ['canceled', 'cancelled'].includes(normalize(state?.taskStatus));
  const failureKey = state => [
    state?.missionId || 'mission',
    state?.currentPhaseId || 'phase',
    state?.taskId || 'task',
    state?.verifier ? 'gate' : 'phase',
  ].join(':');
  const recoveryFor = state => window.__devpilotGameRecoveryForTask?.(state?.taskId) || null;
  const recoveryCategory = recovery => normalize(
    recovery?.failure?.category
    || recovery?.recovery_task?.failure?.category
    || recovery?.self_healing?.category
  );
  const systemManagedGitHubRecovery = recovery => Boolean(
    recoveryCategory(recovery) === 'github_auth'
    && (
      String(recovery?.state || '') === 'awaiting_intervention'
      || recovery?.recovery_task?.requires_approval
    )
  );
  const isTerminalRecovery = recovery => Boolean(
    TERMINAL_RECOVERY_STATES.has(String(recovery?.state || ''))
    && !systemManagedGitHubRecovery(recovery)
  );
  const missionTask = (tasks, state) => (Array.isArray(tasks) ? tasks : []).find(task =>
    String(task?.prompt || '').includes(`PARTIDA: ${state.missionId}`) &&
    String(task?.id || '') === String(state.taskId || '')
  );
  const fetchTasks = async state => (
    typeof window.api === 'function' && state.projectId
      ? window.api(`/tasks?project_id=${encodeURIComponent(state.projectId)}&limit=500`, {retry: false})
      : []
  );

  const arm = () => {
    window.clearTimeout(timer);
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldWatchFailure(state) || (!isCanceled(state) && isTerminalRecovery(recoveryFor(state)))) {
      timer = 0;
      return;
    }

    const key = failureKey(state);
    const first = !recoveryChecks.has(key);
    const delay = first
      ? FIRST_FAILURE_DELAY_MS
      : (document.hidden ? HIDDEN_FAILED_POLL_MS : FAILED_POLL_MS);
    timer = window.setTimeout(run, delay);
  };

  async function run() {
    if (busy) return arm();
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldWatchFailure(state)) return arm();

    // Cancellation is not a recoverable execution failure. The original controller safely
    // recreates the same phase/gate; recovery-runtime intentionally falls back to originalRetry.
    if (isCanceled(state)) {
      busy = true;
      const key = failureKey(state);
      try {
        recoveryChecks.set(key, Date.now());
        await engine.retry();
        await engine.refresh?.();
      } catch (error) {
        // Keep the timestamp: an unavailable API must not turn the 250ms first-attempt path
        // into a request storm. The observer retries on the normal bounded cadence.
        recoveryChecks.set(key, Date.now());
        console.error('[DevPilot Game Flow Keeper]', error);
      } finally {
        busy = false;
        arm();
      }
      return;
    }

    const existingRecovery = recoveryFor(state);
    if (isTerminalRecovery(existingRecovery)) return arm();

    busy = true;
    try {
      const key = failureKey(state);
      const now = Date.now();
      const lastRecoveryCheck = recoveryChecks.get(key) || 0;

      // Delegate the failure immediately once. Afterwards only re-read/escalate canonical
      // recovery every 30s. A stale GitHub approval gate is system-managed and gets one
      // bounded re-evaluation through the backend credential bridge before we stop for a
      // genuinely exhausted administrative credential set.
      if (!lastRecoveryCheck || now - lastRecoveryCheck >= RECOVERY_RECHECK_MS) {
        recoveryChecks.set(key, now);
        await engine.retry();

        const recovery = recoveryFor(state);
        if (isTerminalRecovery(recovery)) return;
        const afterRetry = engine.snapshot?.();
        if (!shouldWatchFailure(afterRetry) || String(afterRetry.taskId || '') !== String(state.taskId || '')) return;
      }

      // Observe the same original task while the worker repairs/retests it. A status change
      // reloads the controller, which then advances through the normal seven-stage pipeline.
      const tasks = await fetchTasks(state);
      const remote = missionTask(tasks, state);
      if (remote && normalize(remote.status) !== normalize(state.taskStatus)) {
        await window.loadBuildGame?.();
        engine.schedule?.();
      }

      if (recoveryChecks.size > 64) recoveryChecks.delete(recoveryChecks.keys().next().value);
    } catch (error) {
      console.error('[DevPilot Game Flow Keeper]', error);
    } finally {
      busy = false;
      arm();
    }
  }

  document.addEventListener('devpilot:game:state', arm);
  document.addEventListener('devpilot:game:rendered', arm);
  document.addEventListener('devpilot:game:recovery-state', arm);
  document.addEventListener('visibilitychange', arm);
  document.addEventListener('devpilot:game:core-ready', arm);
  arm();
})();
