/* DevPilot Build Game: hard reset and persist a fresh mission per project. */
(() => {
  'use strict';

  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const GOAL_PREFIX = 'devpilot-build-game-goal';
  const SAVED_MISSION_PREFIX = 'devpilot-build-game-saved-mission';
  const REOPEN_KEY = 'devpilot-build-game-reopen';
  const TOTAL_XP = 900;
  let previousMissionId = '';

  const projectId = () => String(localStorage.getItem(PROJECT_KEY) || '').trim();
  const missionId = () => String(localStorage.getItem(MISSION_KEY) || '').trim();
  const goalKey = (project, mission) => `${GOAL_PREFIX}:${project || 'none'}:${mission || 'none'}`;
  const savedMissionKey = project => `${SAVED_MISSION_PREFIX}:${project || 'none'}`;

  const saveMissionForProject = (project, mission) => {
    if (!project || !mission) return;
    localStorage.setItem(savedMissionKey(project), mission);
    localStorage.setItem(PROJECT_KEY, project);
    localStorage.setItem(MISSION_KEY, mission);
  };

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

  const reopenSavedGameAfterReload = () => {
    const project = String(sessionStorage.getItem(REOPEN_KEY) || '').trim();
    if (!project) return;
    sessionStorage.removeItem(REOPEN_KEY);

    const savedMission = localStorage.getItem(savedMissionKey(project));
    if (savedMission) saveMissionForProject(project, savedMission);

    const open = () => {
      const navButton = document.querySelector('.sidebar nav [data-view="build-game"]');
      if (navButton) return navButton.click();
      window.setTimeout(open, 60);
    };
    open();
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

    if (project && nextMission) saveMissionForProject(project, nextMission);

    resetVisibleState();
    document.dispatchEvent(new CustomEvent('devpilot:build-game-new-session', {
      detail: {
        project_id: project,
        previous_mission_id: previousMissionId,
        mission_id: nextMission,
        persisted: Boolean(project && nextMission),
      },
    }));

    queueMicrotask(() => void refreshNewMission());
    window.setTimeout(() => void refreshNewMission(), 120);
  });

  /*
   * The core project-card handler intentionally resets the private mission state.
   * When a user already created a fresh mission for that project, intercept the
   * project-card navigation, restore the saved mission and reload once so the
   * core build-game closure initializes with the correct mission id.
   */
  document.addEventListener('click', event => {
    const button = event.target?.closest?.('[data-project-build-game]');
    if (!button) return;

    const project = String(button.dataset.projectBuildGame || '').trim();
    const savedMission = localStorage.getItem(savedMissionKey(project));
    if (!project || !savedMission) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    saveMissionForProject(project, savedMission);
    sessionStorage.setItem(REOPEN_KEY, project);
    window.location.reload();
  }, true);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', reopenSavedGameAfterReload, {once: true});
  } else {
    reopenSavedGameAfterReload();
  }
})();
