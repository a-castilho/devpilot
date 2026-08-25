(() => {
  'use strict';

  const MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const watchers = new Map();
  const taskCache = new Map();

  const token = () => String(localStorage.getItem('devpilot-token') || '').trim();
  const isGameTask = task => String(task?.prompt || '').includes(MARKER);

  async function request(path) {
    const authToken = token();
    const response = await fetch(path, {
      headers: authToken ? {Authorization: `Bearer ${authToken}`} : {},
      cache: 'no-store',
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
    return data;
  }

  function promptValue(task, label) {
    const safe = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return String(task?.prompt || '').match(new RegExp(`^${safe}:\\s*(.+)$`, 'mi'))?.[1]?.trim() || '';
  }

  function phaseFromTask(task) {
    return Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  }

  function currentProjectId() {
    return String(document.querySelector('#build-game-project')?.value || localStorage.getItem(PROJECT_KEY) || '').trim();
  }

  function currentMissionId() {
    return String(localStorage.getItem(MISSION_KEY) || '').trim();
  }

  async function latestGameTasks() {
    const projectId = currentProjectId();
    if (!projectId) return new Map();
    const rows = await request(`/api/tasks?project_id=${encodeURIComponent(projectId)}&limit=500`);
    const missionId = currentMissionId();
    const byPhase = new Map();
    (Array.isArray(rows) ? rows : [])
      .filter(task => isGameTask(task) && (!missionId || promptValue(task, 'PARTIDA') === missionId))
      .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
      .forEach(task => {
        const phase = phaseFromTask(task);
        if (!phase || byPhase.has(phase)) return;
        byPhase.set(phase, task);
        taskCache.set(String(task.id), task);
      });
    return byPhase;
  }

  function cardForPhase(phase) {
    return Array.from(document.querySelectorAll('.build-game-phase')).find(card => {
      const text = card.querySelector('.build-game-phase-copy small')?.textContent || '';
      return text.includes(`FASE ${phase}/`);
    });
  }

  function applyState(task, current) {
    const phase = phaseFromTask(task);
    const card = cardForPhase(phase);
    if (!card) return;
    card.dataset.workflowState = current.game_state;
    card.dataset.workflowTaskId = String(task.id);
    const actions = card.querySelector('.build-game-phase-actions');
    if (!actions) return;

    let badge = actions.querySelector('[data-game-workflow-state]');
    if (!badge) {
      badge = document.createElement('span');
      badge.dataset.gameWorkflowState = '1';
      actions.prepend(badge);
    }
    badge.textContent = current.game_label;

    const playButton = actions.querySelector('[data-play-phase]');
    if (playButton) {
      const blocked = current.requires_authorization || current.game_state === 'SHIELD_BLOCKED';
      playButton.disabled = blocked || !['MISSION_READY', 'SHOT_FAILED'].includes(current.game_state);
      playButton.title = blocked ? 'Conclua a autorização normal antes de continuar' : current.game_label;
    }

    if (current.game_state === 'MISSION_COMPLETE') {
      card.classList.add('passed');
      card.classList.remove('current', 'locked');
    }
    if (current.game_state === 'SHIELD_BLOCKED') card.classList.add('workflow-shielded');
    else card.classList.remove('workflow-shielded');
  }

  async function reconcileTask(task) {
    if (!window.DevPilotGameWorkflow || !task?.id) return;
    try {
      const current = await window.DevPilotGameWorkflow.missionState(task.id);
      applyState(task, current);
      const terminal = ['MISSION_COMPLETE', 'SHOT_FAILED', 'SHIELD_BLOCKED'].includes(current.game_state);
      if (!terminal && !watchers.has(String(task.id))) {
        const stop = window.DevPilotGameWorkflow.watch(task.id, {
          onChange: state => applyState(task, state),
        });
        watchers.set(String(task.id), stop);
      }
    } catch (error) {
      document.dispatchEvent(new CustomEvent('devpilot:game-error', {
        detail: {task_id: task.id, message: error.message},
      }));
    }
  }

  async function reconcile() {
    if (!window.DevPilotGameWorkflow || !document.querySelector('#build-game-view')) return;
    try {
      const byPhase = await latestGameTasks();
      byPhase.forEach(task => void reconcileTask(task));
    } catch (error) {
      document.dispatchEvent(new CustomEvent('devpilot:game-error', {detail: {message: error.message}}));
    }
  }

  document.addEventListener('devpilot:game-workflow-ready', () => void reconcile());
  document.addEventListener('devpilot:game-state', event => {
    const task = taskCache.get(String(event.detail?.task_id || ''));
    if (task) applyState(task, event.detail);
  });
  document.addEventListener('devpilot:feature-ready', event => {
    if (event.detail?.feature === 'game' && !(event.detail?.failures || []).length) setTimeout(() => void reconcile(), 0);
  });
  document.addEventListener('click', event => {
    if (event.target.closest?.('[data-game-refresh], [data-play-phase], [data-view="build-game"]')) {
      setTimeout(() => void reconcile(), 120);
    }
  });

  const originalLoad = window.loadBuildGame;
  if (typeof originalLoad === 'function' && !originalLoad.__workflowWrapped) {
    const wrapped = async (...args) => {
      const result = await originalLoad(...args);
      await reconcile();
      return result;
    };
    wrapped.__workflowWrapped = true;
    window.loadBuildGame = wrapped;
  }

  setTimeout(() => void reconcile(), 0);
})();
