(() => {
  'use strict';

  if (window.__devpilotGameInlineApprovalV46) return;
  window.__devpilotGameInlineApprovalV46 = true;

  const MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const STYLE_ID = 'devpilot-game-inline-approval-v46-style';
  const originalApi = window.api;

  const normalize = value => String(value || '').split('.').pop().trim().toLowerCase().replaceAll(' ', '_');
  const escapeRegExp = value => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  function promptValue(task, label) {
    const match = String(task?.prompt || '').match(new RegExp(`^${escapeRegExp(label)}:\\s*(.+)$`, 'mi'));
    return match?.[1]?.trim() || '';
  }

  function phaseFromTask(task) {
    return Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  }

  function missionFromTask(task) {
    return promptValue(task, 'PARTIDA');
  }

  function isGameTask(task) {
    return String(task?.prompt || '').includes(MARKER);
  }

  function installStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .build-game-phase-actions [data-game-inline-approve] {
        min-width: 148px;
        border-color: rgba(55,215,255,.48) !important;
        background: linear-gradient(135deg,#0ca36d,#087a70) !important;
        color: #effff9 !important;
        font-weight: 900 !important;
      }
      .build-game-phase-actions [data-game-inline-approve][aria-busy="true"] {
        opacity: .72;
        cursor: progress;
      }
      @media (max-width:800px) {
        .build-game-phase-actions.game-awaiting-inline-approval {
          display:grid !important;
          grid-template-columns:auto minmax(0,1fr) !important;
          align-items:center !important;
          gap:10px !important;
          width:100% !important;
        }
        .build-game-phase-actions.game-awaiting-inline-approval .status {
          justify-self:start;
          white-space:nowrap;
        }
        .build-game-phase-actions.game-awaiting-inline-approval [data-game-inline-approve] {
          width:100% !important;
          min-height:48px !important;
          min-width:0 !important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function currentProjectId() {
    return String(
      document.querySelector('#build-game-project')?.value ||
      localStorage.getItem(PROJECT_KEY) ||
      ''
    ).trim();
  }

  function currentMissionId() {
    return String(localStorage.getItem(MISSION_KEY) || '').trim();
  }

  function awaitingPhaseCards() {
    return [...document.querySelectorAll('#build-game-view .build-game-phase')].filter(card => {
      const chip = card.querySelector('.status');
      return normalize(chip?.classList?.value?.match(/awaiting_approval/)?.[0] || chip?.textContent) === 'awaiting_approval';
    });
  }

  function phaseFromCard(card) {
    const text = String(card.querySelector('.build-game-phase-copy small')?.textContent || '');
    return Number(text.match(/FASE\s+(\d+)\s*\//i)?.[1] || 0);
  }

  async function latestAwaitingTaskForPhase(phaseId) {
    const projectId = currentProjectId();
    const missionId = currentMissionId();
    if (!projectId || !phaseId || typeof originalApi !== 'function') return null;

    const tasks = await originalApi(`/tasks?project_id=${encodeURIComponent(projectId)}&limit=80`);
    return (Array.isArray(tasks) ? tasks : [])
      .filter(task => isGameTask(task))
      .filter(task => !missionId || missionFromTask(task) === missionId)
      .filter(task => phaseFromTask(task) === phaseId)
      .filter(task => normalize(task?.status) === 'awaiting_approval')
      .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))[0] || null;
  }

  async function approveTask(taskId, button) {
    if (!taskId || !button || button.dataset.approving === '1') return;
    button.dataset.approving = '1';
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    const original = button.textContent;
    button.textContent = 'Aprovando…';

    try {
      await originalApi(`/tasks/${encodeURIComponent(taskId)}/approve`, {method:'POST'});
      window.toast?.('Fase aprovada. A missão continua sem sair do jogo.');
      await window.loadBuildGame?.();
    } catch (error) {
      window.toast?.(error?.message || 'Não foi possível aprovar a fase.');
      button.disabled = false;
      button.textContent = original;
    } finally {
      button.removeAttribute('aria-busy');
      delete button.dataset.approving;
    }
  }

  async function decorateCard(card) {
    if (!(card instanceof Element) || card.dataset.gameApprovalResolved === '1') return;
    const phaseId = phaseFromCard(card);
    if (!phaseId) return;

    const actions = card.querySelector('.build-game-phase-actions');
    if (!actions) return;
    actions.classList.add('game-awaiting-inline-approval');

    const refresh = actions.querySelector('[data-game-refresh]');
    if (refresh) {
      refresh.disabled = true;
      refresh.textContent = 'Preparando aprovação…';
    }

    try {
      const task = await latestAwaitingTaskForPhase(phaseId);
      if (!task?.id) {
        if (refresh) {
          refresh.disabled = false;
          refresh.textContent = 'Atualizar';
        }
        return;
      }

      refresh?.remove();
      if (!actions.querySelector('[data-game-inline-approve]')) {
        const approve = document.createElement('button');
        approve.type = 'button';
        approve.className = 'primary';
        approve.dataset.gameInlineApprove = String(task.id);
        approve.textContent = '✓ Aprovar fase';
        approve.addEventListener('click', () => void approveTask(task.id, approve));
        actions.appendChild(approve);
      }
      card.dataset.gameApprovalResolved = '1';
    } catch (error) {
      if (refresh) {
        refresh.disabled = false;
        refresh.textContent = 'Atualizar';
      }
      console.warn('[DevPilot Game] Falha ao preparar aprovação inline', error);
    }
  }

  async function decorateApprovals() {
    const cards = awaitingPhaseCards();
    if (!cards.length) return;
    for (const card of cards) await decorateCard(card);
  }

  function installLowMemoryTaskLimit() {
    if (typeof originalApi !== 'function' || window.__devpilotGameLowMemoryApiV46) return;
    window.__devpilotGameLowMemoryApiV46 = true;
    const guardedApi = function gameLowMemoryApi(path, options = {}) {
      let safePath = String(path || '');
      if (/^\/tasks\?project_id=.*(?:&|\?)limit=500(?:&|$)/.test(safePath)) {
        safePath = safePath.replace(/limit=500\b/, 'limit=120');
      }
      return originalApi(safePath, options);
    };
    window.api = guardedApi;
    try { api = guardedApi; } catch (_) {}
  }

  function wrapGameLoader() {
    const upstream = window.loadBuildGame;
    if (typeof upstream !== 'function' || upstream.__devpilotInlineApprovalV46) return;

    const wrapped = async function loadBuildGameWithInlineApproval(...args) {
      const result = await upstream.apply(this, args);
      await decorateApprovals();
      return result;
    };
    wrapped.__devpilotInlineApprovalV46 = true;
    wrapped.__devpilotUpstream = upstream;
    window.loadBuildGame = wrapped;
  }

  installStyles();
  installLowMemoryTaskLimit();
  wrapGameLoader();

  document.addEventListener('devpilot:game:standalone-ready', () => void decorateApprovals());
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void decorateApprovals();
  });
})();
