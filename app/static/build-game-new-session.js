/* DevPilot Build Game: hard reset the visible/runtime state when starting a new mission. */
(() => {
  'use strict';

  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const GOAL_PREFIX = 'devpilot-build-game-goal';
  const TOTAL_XP = 900;
  let previousMissionId = '';

  const projectId = () => String(localStorage.getItem(PROJECT_KEY) || '').trim();
  const missionId = () => String(localStorage.getItem(MISSION_KEY) || '').trim();
  const goalKey = (project, mission) => `${GOAL_PREFIX}:${project || 'none'}:${mission || 'none'}`;

  const resetVisibleState = () => {
    const view = document.querySelector('#build-game-view');
    if (!view) return;

    const goal = view.querySelector('#build-game-goal');
    if (goal) goal.value = '';

    const score = view.querySelectorAll('.build-game-score strong');
    if (score[0]) score[0].textContent = '0/6 fases';
    if (score[1]) score[1].textContent = `0/${TOTAL_XP} XP`;

    const progress = view.querySelector('.build-game-progress > i');
    if (progress) progress.style.width = '0%';
    view.querySelector('.build-game-progress')?.setAttribute('aria-label', '0% concluído');

    view.querySelector('.build-game-victory')?.remove();
    view.querySelector('.build-game-url-bonus')?.remove();
    view.querySelectorAll('.build-game-phase').forEach((card, index) => {
      card.classList.remove('passed', 'current', 'locked');
      card.classList.add(index === 0 ? 'current' : 'locked');
      card.querySelector('.build-game-subphases')?.remove();
    });

    const history = view.querySelector('.build-game-history');
    if (history) history.innerHTML = '<div class="empty">A partida começa quando você jogar a primeira fase.</div>';
  };

  const refreshNewMission = async () => {
    resetVisibleState();
    if (typeof window.loadBuildGame !== 'function') return;
    try {
      await window.loadBuildGame();
    } catch (error) {
      console.error('DevPilot new game reset:', error);
    }
  };

  document.addEventListener('pointerdown', event => {
    if (!event.target?.closest?.('#build-game-view #build-game-new')) return;
    previousMissionId = missionId();
  }, true);

  document.addEventListener('click', event => {
    if (!event.target?.closest?.('#build-game-view #build-game-new')) return;

    const project = projectId();
    const nextMission = missionId();
    if (previousMissionId && previousMissionId !== nextMission) {
      localStorage.removeItem(goalKey(project, previousMissionId));
    }

    resetVisibleState();
    document.dispatchEvent(new CustomEvent('devpilot:build-game-new-session', {
      detail: {
        project_id: project,
        previous_mission_id: previousMissionId,
        mission_id: nextMission,
      },
    }));

    // The core handler changes its private missionId before this bubbling handler runs.
    // Refresh twice to win races with UI wrappers/subphase hydration without deleting history.
    queueMicrotask(() => void refreshNewMission());
    window.setTimeout(() => void refreshNewMission(), 120);
  });
})();
