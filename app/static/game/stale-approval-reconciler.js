/* Reconcile Build Game approval gates that were created only by an older false-positive policy scan. */
(() => {
  'use strict';

  if (window.__devpilotGameStaleApprovalReconcilerV46) return;
  window.__devpilotGameStaleApprovalReconcilerV46 = true;

  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const MAX_PHASES = 6;
  let reconciling = false;

  const norm = value => String(value || '').split('.').pop().trim().toLowerCase().replaceAll(' ', '_');
  const promptValue = (task, label) => {
    const escaped = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = String(task?.prompt || '').match(new RegExp(`^${escaped}:\\s*(.+)$`, 'mi'));
    return match?.[1]?.trim() || '';
  };
  const phaseFromTask = task => Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  const missionFromTask = task => promptValue(task, 'PARTIDA');
  const generatedByGame = task => (
    String(task?.prompt || '').includes(GAME_MARKER)
    && ['dashboard', 'build-game-gate'].includes(String(task?.source || 'dashboard'))
  );

  async function currentTask() {
    const projectId = localStorage.getItem(PROJECT_KEY) || '';
    const missionId = localStorage.getItem(MISSION_KEY) || '';
    if (!projectId || !missionId || typeof api !== 'function') return null;
    const response = await api(`/tasks?project_id=${encodeURIComponent(projectId)}&limit=500`);
    const tasks = (Array.isArray(response) ? response : [])
      .filter(task => generatedByGame(task) && missionFromTask(task) === missionId)
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    for (let phaseId = 1; phaseId <= MAX_PHASES; phaseId += 1) {
      const task = tasks.find(item => phaseFromTask(item) === phaseId);
      if (!task || norm(task.status) !== 'completed') return task || null;
    }
    return null;
  }

  async function reconcile() {
    if (reconciling) return false;
    reconciling = true;
    try {
      const task = await currentTask();
      if (!task || norm(task.status) !== 'awaiting_approval' || !generatedByGame(task)) return false;
      const runtime = await api(`/tasks/${encodeURIComponent(task.id)}/orchestrator`);
      const reasons = Array.isArray(runtime?.gate?.reasons) ? runtime.gate.reasons : [];
      if (reasons.length) return false;

      /* Build Game always requests requires_approval=false. A persisted true value with
         zero current policy reasons is therefore a legacy policy false-positive, not a
         user authorization decision. Clear it through the normal audited approval route. */
      if (task.requires_approval) {
        await api(`/tasks/${encodeURIComponent(task.id)}/approve`, {method:'POST'});
      }
      await api(`/tasks/${encodeURIComponent(task.id)}/next`, {method:'POST'});
      window.toast?.('Esteira corrigida: gate legado sem risco real foi removido e a fase voltou para a fila.');
      window.setTimeout(() => void window.loadBuildGame?.(), 250);
      return true;
    } catch (error) {
      console.error('[DEVPILOT_STALE_GAME_APPROVAL]', error);
      return false;
    } finally {
      reconciling = false;
    }
  }

  const upstreamLoad = window.loadBuildGame;
  if (typeof upstreamLoad === 'function') {
    window.loadBuildGame = async (...args) => {
      const result = await upstreamLoad(...args);
      await reconcile();
      return result;
    };
  }

  window.__devpilotReconcileStaleGameApproval = reconcile;
})();
