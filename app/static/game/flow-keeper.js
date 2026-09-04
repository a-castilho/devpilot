/* DevPilot game v97 — bounded observer; failed repairs start only from user action. */
(() => {
  'use strict';
  if (window.__devpilotGameFlowKeeperV97Ready) return;
  window.__devpilotGameFlowKeeperV97Ready = true;

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
  const isTerminalRecovery = recovery => TERMINAL_RECOVERY_STATES.has(String(recovery?.state || ''));
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

    // Cancelamento é diferente de falha: recriar a mesma etapa continua sendo
    // automático porque foi o próprio usuário que encerrou a execução anterior.
    if (isCanceled(state)) {
      busy = true;
      const key = failureKey(state);
      try {
        recoveryChecks.set(key, Date.now());
        await engine.retry();
        await engine.refresh?.();
      } catch (error) {
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

      // Falha/blocked: somente leia o diagnóstico. Não chame engine.retry()
      // aqui. O único gatilho de correção é o clique em "Corrigir e continuar".
      if (!lastRecoveryCheck || now - lastRecoveryCheck >= RECOVERY_RECHECK_MS) {
        recoveryChecks.set(key, now);
        await window.__devpilotGameReadRecovery?.(state.taskId);
        const recovery = recoveryFor(state);
        if (isTerminalRecovery(recovery)) return;
      }

      // Observe mudanças produzidas depois do clique do usuário ou de uma
      // intervenção externa. O keeper nunca promove ready_to_recover para queued.
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
