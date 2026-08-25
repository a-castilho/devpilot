(() => {
  'use strict';

  const MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const watchers = new Map();

  const normalize = value => String(value || '').toLowerCase().replaceAll(' ', '_');
  const isGameTask = task => String(task?.prompt || '').includes(MARKER);

  function phaseFromTask(task) {
    const match = String(task?.prompt || '').match(/^FASE:\s*(\d+)\//mi);
    return Number(match?.[1] || 0);
  }

  function latestGameTasks() {
    const tasks = Array.isArray(window.state?.tasks) ? window.state.tasks : [];
    const byPhase = new Map();
    tasks.filter(isGameTask).forEach(task => {
      const phase = phaseFromTask(task);
      if (!phase) return;
      const previous = byPhase.get(phase);
      if (!previous || new Date(task.created_at || 0) > new Date(previous.created_at || 0)) byPhase.set(phase, task);
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
      if (!['MISSION_COMPLETE', 'SHOT_FAILED', 'SHIELD_BLOCKED'].includes(current.game_state) && !watchers.has(String(task.id))) {
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

  function reconcile() {
    if (!window.DevPilotGameWorkflow) return;
    latestGameTasks().forEach(task => void reconcileTask(task));
  }

  document.addEventListener('devpilot:game-workflow-ready', reconcile);
  document.addEventListener('devpilot:game-state', event => {
    const taskId = event.detail?.task_id;
    const task = Array.isArray(window.state?.tasks)
      ? window.state.tasks.find(item => String(item.id) === String(taskId))
      : null;
    if (task) applyState(task, event.detail);
  });
  document.addEventListener('devpilot:feature-ready', event => {
    if (event.detail?.feature === 'game' && !(event.detail?.failures || []).length) setTimeout(reconcile, 0);
  });
  document.addEventListener('click', event => {
    if (event.target.closest?.('[data-game-refresh], [data-play-phase], [data-view="build-game"]')) {
      setTimeout(reconcile, 100);
    }
  });

  const originalLoad = window.loadBuildGame;
  if (typeof originalLoad === 'function' && !originalLoad.__workflowWrapped) {
    const wrapped = async (...args) => {
      const result = await originalLoad(...args);
      reconcile();
      return result;
    };
    wrapped.__workflowWrapped = true;
    window.loadBuildGame = wrapped;
  }

  setTimeout(reconcile, 0);
})();
