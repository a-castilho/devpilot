/* DevPilot game v78 — passive state watcher with automatic self-repair for failed phases. */
(() => {
  'use strict';

  if (window.__devpilotGameFlowKeeperV78Ready) return;
  window.__devpilotGameFlowKeeperV78Ready = true;

  const VISIBLE_DELAY_MS = 2500;
  const HIDDEN_DELAY_MS = 8000;
  const FAILED_DELAY_MS = 350;
  let timer = 0;
  let busy = false;
  const repairedFailures = new Set();

  const controller = () => window.__devpilotGameControllerV73;
  const delay = state => state?.failed ? FAILED_DELAY_MS : (document.hidden ? HIDDEN_DELAY_MS : VISIBLE_DELAY_MS);
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');

  const shouldKeepMoving = state => Boolean(
    state && state.missionId && state.goal && !state.done
  );

  const failureKey = state => [
    state?.missionId || 'mission',
    state?.currentPhaseId || 'phase',
    state?.taskId || 'task',
    state?.verifier ? 'gate' : 'phase',
    state?.taskStatus || 'failed'
  ].join(':');

  const announceRepairing = state => {
    const message = state?.verifier
      ? 'A validação falhou. Corrigindo e validando novamente…'
      : 'A etapa falhou. Corrigindo automaticamente e continuando…';
    document.querySelectorAll('.game74-live span, [data-game73-status]').forEach(node => {
      node.textContent = message;
      node.classList?.remove?.('game74-error');
    });
    const retry = document.querySelector('[data-game73-retry]');
    if (retry) {
      retry.disabled = true;
      retry.textContent = '↻ Corrigindo automaticamente…';
    }
  };

  const missionTask = (tasks, state) => (Array.isArray(tasks) ? tasks : []).find(task => {
    const prompt = String(task?.prompt || '');
    return prompt.includes(`PARTIDA: ${state.missionId}`) && String(task?.id || '') === String(state.taskId || '');
  });

  const anyMissionTask = (tasks, state) => (Array.isArray(tasks) ? tasks : []).find(task =>
    String(task?.prompt || '').includes(`PARTIDA: ${state.missionId}`)
  );

  const fetchTasks = async state => {
    if (typeof window.api !== 'function' || !state.projectId) return [];
    return window.api(`/tasks?project_id=${encodeURIComponent(state.projectId)}&limit=500`);
  };

  const arm = () => {
    window.clearTimeout(timer);
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldKeepMoving(state)) {
      timer = 0;
      return;
    }
    timer = window.setTimeout(run, delay(state));
  };

  async function repairFailedState(engine, state) {
    const key = failureKey(state);
    announceRepairing(state);

    // One retry request per failed task. If the correction itself fails and creates a
    // new failed task, the task id changes and that new failure gets one retry too.
    // This prevents duplicate task creation while keeping the round self-healing.
    if (!repairedFailures.has(key)) {
      repairedFailures.add(key);
      try {
        await engine.retry();
      } catch (error) {
        repairedFailures.delete(key);
        throw error;
      }
      return;
    }

    // retry() may return before /tasks exposes the replacement task. Keep syncing
    // until the controller sees the new task instead of retrying the same failure.
    await engine.refresh();
  }

  async function run() {
    if (busy) return arm();
    const engine = controller();
    const state = engine?.snapshot?.();
    if (!engine || !shouldKeepMoving(state)) return arm();

    busy = true;
    try {
      if (state.failed) {
        await repairFailedState(engine, state);
        return;
      }

      const tasks = await fetchTasks(state);

      // Start POST can return before /tasks exposes the created task.
      // Poll silently until it is visible; only then synchronize/render once.
      if (!state.hasTasks) {
        if (anyMissionTask(tasks, state) && typeof window.loadBuildGame === 'function') {
          await window.loadBuildGame();
          engine.schedule?.();
        }
        return;
      }

      // While the current task keeps the same status, do absolutely nothing to the DOM.
      // This removes the 2.5s full-screen blink while preserving polling.
      const remote = missionTask(tasks, state);
      if (remote && normalize(remote.status) === normalize(state.taskStatus)) return;

      // A real transition happened (queued→running→completed, gate, next phase, etc.).
      // Let the existing controller synchronize once and advance the real pipeline.
      await engine.refresh();
      engine.schedule?.();
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
