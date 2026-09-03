/* DevPilot game v85 — passive watcher with observable automatic self-repair. */
(() => {
  'use strict';

  if (window.__devpilotGameFlowKeeperV85Ready) return;
  window.__devpilotGameFlowKeeperV85Ready = true;

  const VISIBLE_DELAY_MS = 2500;
  const HIDDEN_DELAY_MS = 8000;
  const FAILED_DELAY_MS = 500;
  const REPAIR_CONFIRM_MS = 4500;
  let timer = 0;
  let busy = false;
  const repairAttempts = new Map();

  const controller = () => window.__devpilotGameControllerV73;
  const delay = state => state?.failed ? FAILED_DELAY_MS : (document.hidden ? HIDDEN_DELAY_MS : VISIBLE_DELAY_MS);
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');

  const shouldKeepMoving = state => Boolean(state && state.missionId && state.goal && !state.done);

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
    document.querySelectorAll('.game74-live span, [data-game73-status], #devpilot-game-stable-round-v84 .game74-live span').forEach(node => {
      node.textContent = message;
      node.classList?.remove?.('game74-error');
    });
  };

  const missionTask = (tasks, state) => (Array.isArray(tasks) ? tasks : []).find(task => {
    const prompt = String(task?.prompt || '');
    return prompt.includes(`PARTIDA: ${state.missionId}`) && String(task?.id || '') === String(state.taskId || '');
  });

  const missionTasks = (tasks, state) => (Array.isArray(tasks) ? tasks : []).filter(task =>
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

  const changedAfterRepair = (before, after, tasks) => {
    if (!after) return false;
    if (!after.failed) return true;
    if (String(after.taskId || '') !== String(before.taskId || '')) return true;
    const rows = missionTasks(tasks, before);
    return rows.some(task => String(task?.id || '') !== String(before.taskId || '') && Number(String(task?.prompt || '').match(/^FASE:\s*(\d+)\//mi)?.[1] || 0) === Number(before.currentPhaseId || 0));
  };

  async function repairFailedState(engine, state) {
    const key = failureKey(state);
    announceRepairing(state);
    const previous = repairAttempts.get(key) || {lastAt: 0, count: 0};
    const now = Date.now();

    if (!previous.lastAt || now - previous.lastAt >= REPAIR_CONFIRM_MS) {
      repairAttempts.set(key, {lastAt: now, count: previous.count + 1});
      await engine.retry();
      await new Promise(resolve => window.setTimeout(resolve, 250));
      await engine.refresh();
      const after = engine.snapshot?.();
      const tasks = await fetchTasks(state);
      if (changedAfterRepair(state, after, tasks)) {
        repairAttempts.delete(key);
        return;
      }
      return;
    }

    await engine.refresh();
    const after = engine.snapshot?.();
    const tasks = await fetchTasks(state);
    if (changedAfterRepair(state, after, tasks)) repairAttempts.delete(key);
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
      if (!state.hasTasks) {
        if (missionTasks(tasks, state).length && typeof window.loadBuildGame === 'function') {
          await window.loadBuildGame();
          engine.schedule?.();
        }
        return;
      }

      const remote = missionTask(tasks, state);
      if (remote && normalize(remote.status) === normalize(state.taskStatus)) return;

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
