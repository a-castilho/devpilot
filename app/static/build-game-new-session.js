/* DevPilot Build Game: session lifecycle, completed-game history and project persistence. */
(() => {
  'use strict';

  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const GOAL_PREFIX = 'devpilot-build-game-goal';
  const SAVED_MISSION_PREFIX = 'devpilot-build-game-saved-mission';
  const HISTORY_PREFIX = 'devpilot-build-game-history';
  const REOPEN_KEY = 'devpilot-build-game-reopen';
  const TOTAL_XP = 900;
  let previousMissionId = '';

  const projectId = () => String(localStorage.getItem(PROJECT_KEY) || '').trim();
  const missionId = () => String(localStorage.getItem(MISSION_KEY) || '').trim();
  const goalKey = (project, mission) => `${GOAL_PREFIX}:${project || 'none'}:${mission || 'none'}`;
  const savedMissionKey = project => `${SAVED_MISSION_PREFIX}:${project || 'none'}`;
  const historyKey = project => `${HISTORY_PREFIX}:${project || 'none'}`;

  const readHistory = project => {
    if (!project) return [];
    try {
      const value = JSON.parse(localStorage.getItem(historyKey(project)) || '[]');
      return Array.isArray(value) ? value.filter(item => item && item.mission_id) : [];
    } catch (_) {
      return [];
    }
  };

  const writeHistory = (project, history) => {
    if (!project) return;
    localStorage.setItem(historyKey(project), JSON.stringify(history.slice(0, 50)));
  };

  const saveMissionForProject = (project, mission) => {
    if (!project || !mission) return;
    localStorage.setItem(savedMissionKey(project), mission);
    localStorage.setItem(PROJECT_KEY, project);
    localStorage.setItem(MISSION_KEY, mission);
  };

  const currentProgress = () => {
    const view = document.querySelector('#build-game-view');
    if (!view) return {completed: false, phases: 0, xp: 0};

    const score = view.querySelectorAll('.build-game-score strong');
    const phaseText = String(score[0]?.textContent || '');
    const xpText = String(score[1]?.textContent || '');
    const phases = Number((phaseText.match(/(\d+)\s*\/\s*6/) || [])[1] || 0);
    const xp = Number((xpText.match(/(\d+)\s*\//) || [])[1] || 0);
    const passed = view.querySelectorAll('.build-game-phase.passed').length;
    const completed = phases >= 6 || passed >= 6 || Boolean(view.querySelector('.build-game-victory'));
    return {completed, phases, xp};
  };

  const archiveCompletedMission = (project, mission) => {
    if (!project || !mission) return false;
    const progress = currentProgress();
    if (!progress.completed) return false;

    const history = readHistory(project);
    const goal = String(localStorage.getItem(goalKey(project, mission)) || '').trim();
    const previous = history.find(item => item.mission_id === mission);
    const record = {
      mission_id: mission,
      goal,
      phases: Math.max(6, Number(previous?.phases || progress.phases || 0)),
      xp: Math.max(Number(previous?.xp || 0), progress.xp),
      completed_at: previous?.completed_at || new Date().toISOString(),
    };
    writeHistory(project, [record, ...history.filter(item => item.mission_id !== mission)]);
    return true;
  };

  const canStartNewGame = () => {
    const currentMission = missionId();
    if (!currentMission) return true;
    return currentProgress().completed;
  };

  const showNewGameBlocked = () => {
    const view = document.querySelector('#build-game-view');
    if (!view) return;
    let notice = view.querySelector('.build-game-new-blocked');
    if (!notice) {
      notice = document.createElement('div');
      notice.className = 'build-game-new-blocked';
      notice.style.cssText = 'margin-top:10px;padding:10px 12px;border:1px solid rgba(251,191,36,.45);border-radius:12px;background:rgba(120,53,15,.18);color:#fde68a;font-weight:700;line-height:1.35';
      view.querySelector('#build-game-new')?.insertAdjacentElement('afterend', notice);
    }
    notice.textContent = 'Conclua a partida atual antes de iniciar uma nova.';
  };

  const resetVisibleState = () => {
    const view = document.querySelector('#build-game-view');
    if (!view) return;

    view.querySelector('.build-game-new-blocked')?.remove();
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

  const openMission = (project, mission) => {
    if (!project || !mission) return;
    saveMissionForProject(project, mission);
    sessionStorage.setItem(REOPEN_KEY, project);
    window.location.reload();
  };

  const renderPreviousGames = () => {
    const view = document.querySelector('#build-game-view');
    const newButton = view?.querySelector('#build-game-new');
    if (!view || !newButton) return;

    let access = view.querySelector('.build-game-previous-access');
    if (!access) {
      access = document.createElement('section');
      access.className = 'build-game-previous-access';
      access.style.cssText = 'margin-top:12px;border:1px solid rgba(94,234,212,.22);border-radius:16px;background:rgba(2,20,27,.55);overflow:hidden';
      newButton.insertAdjacentElement('afterend', access);
    }

    const project = projectId();
    const items = readHistory(project);
    if (!items.length) {
      access.innerHTML = '<button type="button" data-previous-games-toggle disabled style="width:100%;padding:13px 16px;border:0;background:transparent;color:#789b98;text-align:left;font-weight:800">Partidas anteriores · nenhuma concluída</button>';
      return;
    }

    const options = items.map((item, index) => {
      const date = item.completed_at ? new Date(item.completed_at).toLocaleString('pt-BR') : 'concluída';
      const title = item.goal || `Partida ${items.length - index}`;
      return `<option value="${String(item.mission_id).replace(/&/g, '&amp;').replace(/"/g, '&quot;')}">${String(title).replace(/&/g, '&amp;').replace(/</g, '&lt;')} · ${date}</option>`;
    }).join('');

    access.innerHTML = `
      <button type="button" data-previous-games-toggle aria-expanded="false" style="width:100%;padding:13px 16px;border:0;background:transparent;color:#99f6e4;text-align:left;font-weight:900;display:flex;justify-content:space-between;align-items:center">
        <span>Partidas anteriores · ${items.length}</span><span aria-hidden="true">⌄</span>
      </button>
      <div data-previous-games-panel hidden style="padding:0 14px 14px">
        <label style="display:block;margin-bottom:7px;color:#a7c7c2;font-weight:800">Escolha uma partida concluída</label>
        <select data-previous-game-select style="width:100%;min-height:46px;padding:10px 12px;border-radius:12px;border:1px solid rgba(94,234,212,.28);background:#07352a;color:#fff;font-weight:700">${options}</select>
        <button type="button" data-open-previous-game style="width:100%;margin-top:9px;min-height:44px;border-radius:12px;border:1px solid rgba(94,234,212,.34);background:#0b4a3a;color:#fff;font-weight:900">Abrir partida anterior</button>
      </div>`;
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

  document.addEventListener('click', event => {
    if (!event.target?.closest?.('#build-game-view #build-game-new')) return;
    if (canStartNewGame()) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    showNewGameBlocked();
  }, true);

  document.addEventListener('pointerdown', event => {
    if (!event.target?.closest?.('#build-game-view #build-game-new')) return;
    previousMissionId = missionId();
  }, true);

  document.addEventListener('click', event => {
    if (!event.target?.closest?.('#build-game-view #build-game-new')) return;

    const project = projectId();
    const nextMission = missionId();
    if (previousMissionId) archiveCompletedMission(project, previousMissionId);

    if (project && nextMission) saveMissionForProject(project, nextMission);

    resetVisibleState();
    renderPreviousGames();
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

  document.addEventListener('click', event => {
    const toggle = event.target?.closest?.('[data-previous-games-toggle]');
    if (toggle && !toggle.disabled) {
      const panel = toggle.closest('.build-game-previous-access')?.querySelector('[data-previous-games-panel]');
      if (panel) {
        panel.hidden = !panel.hidden;
        toggle.setAttribute('aria-expanded', String(!panel.hidden));
      }
      return;
    }

    const open = event.target?.closest?.('[data-open-previous-game]');
    if (open) {
      const select = open.closest('.build-game-previous-access')?.querySelector('[data-previous-game-select]');
      const mission = String(select?.value || '').trim();
      if (mission) openMission(projectId(), mission);
    }
  });

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

  const boot = () => {
    reopenSavedGameAfterReload();
    renderPreviousGames();
    window.setTimeout(renderPreviousGames, 250);
  };

  document.addEventListener('devpilot:build-game-loaded', () => {
    const project = projectId();
    const mission = missionId();
    archiveCompletedMission(project, mission);
    renderPreviousGames();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, {once: true});
  } else {
    boot();
  }
})();
