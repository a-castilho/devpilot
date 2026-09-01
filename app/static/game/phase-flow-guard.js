/* DevPilot standalone game: one task per phase, continuous progress and inline approval fallback. */
(() => {
  'use strict';

  if (window.__devpilotGamePhaseFlowGuardV55) return;
  window.__devpilotGamePhaseFlowGuardV55 = true;

  const MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const AUTO_REFRESH_STATUSES = new Set(['queued', 'planning', 'running', 'review']);
  const BLOCKING_STATUSES = new Set(['queued', 'planning', 'running', 'review', 'awaiting_approval', 'blocked']);
  const RETRYABLE_STATUSES = new Set(['failed', 'cancelled']);
  const POLL_MS = 2500;
  const launchLocks = new Map();
  let pollTimer = 0;
  let lastSignature = '';
  let syncing = false;

  const normalize = value => String(value || '').split('.').pop().trim().toLowerCase().replaceAll(' ', '_');
  const escapeRegExp = value => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  const promptValue = (task, label) => {
    const match = String(task?.prompt || '').match(new RegExp(`^${escapeRegExp(label)}:\\s*(.+)$`, 'mi'));
    return match?.[1]?.trim() || '';
  };

  const phaseFromTask = task => Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  const missionFromTask = task => promptValue(task, 'PARTIDA');
  const isGameTask = task => String(task?.prompt || '').includes(MARKER);

  const currentProjectId = () => String(
    document.querySelector('#build-game-project')?.value ||
    localStorage.getItem(PROJECT_KEY) ||
    ''
  ).trim();

  const currentMissionId = () => String(localStorage.getItem(MISSION_KEY) || '').trim();

  const phaseFromCard = card => {
    const text = String(card?.querySelector('.build-game-phase-copy small')?.textContent || '');
    return Number(text.match(/(?:FASE|ETAPA)\s+(\d+)\s*\//i)?.[1] || 0);
  };

  const phaseLockKey = phaseId => `${currentProjectId()}:${currentMissionId() || 'pending'}:${phaseId}`;

  async function fetchMissionTasks() {
    const projectId = currentProjectId();
    const missionId = currentMissionId();
    if (!projectId || typeof window.api !== 'function') return [];
    const items = await window.api(`/tasks?project_id=${encodeURIComponent(projectId)}&limit=120`);
    return (Array.isArray(items) ? items : [])
      .filter(isGameTask)
      .filter(task => !missionId || missionFromTask(task) === missionId);
  }

  const latestForPhase = (tasks, phaseId) => tasks.find(task => phaseFromTask(task) === phaseId) || null;

  function taskSignature(tasks) {
    return tasks.slice(0, 12).map(task => `${task.id}:${normalize(task.status)}:${phaseFromTask(task)}`).join('|');
  }

  function statusText(status) {
    const labels = {
      queued: 'NA FILA',
      planning: 'PLANEJANDO',
      running: 'EXECUTANDO',
      review: 'REVISANDO',
      awaiting_approval: 'AGUARDANDO APROVAÇÃO',
      blocked: 'BLOQUEADO',
      completed: 'CONCLUÍDA',
      failed: 'FALHOU',
      cancelled: 'CANCELADA',
    };
    return labels[status] || String(status || '').toUpperCase().replaceAll('_', ' ');
  }

  function installBusyAction(card, task) {
    const status = normalize(task?.status);
    if (!BLOCKING_STATUSES.has(status) || status === 'awaiting_approval') return;
    const actions = card?.querySelector('.build-game-phase-actions');
    if (!actions || !actions.querySelector('[data-play-phase]')) return;
    actions.replaceChildren();

    const chip = document.createElement('span');
    chip.className = `status ${status}`;
    chip.textContent = statusText(status);
    actions.appendChild(chip);

    const waiting = document.createElement('button');
    waiting.type = 'button';
    waiting.className = 'ghost';
    waiting.disabled = true;
    waiting.dataset.gameFlowBusy = '1';
    waiting.textContent = status === 'blocked' ? 'Fluxo bloqueado' : 'Fase em andamento';
    actions.appendChild(waiting);
  }

  async function approveTask(task, button) {
    if (!task?.id || !button || button.dataset.approving === '1') return;
    button.dataset.approving = '1';
    button.disabled = true;
    button.textContent = 'Aprovando…';
    try {
      await window.api(`/tasks/${encodeURIComponent(task.id)}/approve`, {method:'POST'});
      window.toast?.('Fase aprovada. Continuando a missão…');
      await window.loadBuildGame?.();
    } catch (error) {
      window.toast?.(error?.message || 'Não foi possível aprovar a fase.');
      button.disabled = false;
      button.textContent = '✓ Aprovar fase';
      delete button.dataset.approving;
    }
  }

  function installApprovalFallback(card, task) {
    if (normalize(task?.status) !== 'awaiting_approval') return;
    const actions = card?.querySelector('.build-game-phase-actions');
    if (!actions || actions.querySelector('[data-game-inline-approve]')) return;
    actions.classList.add('game-awaiting-inline-approval');
    actions.querySelector('[data-game-refresh]')?.remove();

    const approve = document.createElement('button');
    approve.type = 'button';
    approve.className = 'primary';
    approve.dataset.gameInlineApprove = String(task.id);
    approve.textContent = '✓ Aprovar fase';
    approve.addEventListener('click', () => void approveTask(task, approve));
    actions.appendChild(approve);
  }

  function clearPoll() {
    if (pollTimer) window.clearTimeout(pollTimer);
    pollTimer = 0;
  }

  function schedulePoll(tasks) {
    clearPoll();
    if (document.visibilityState === 'hidden') return;
    if (!tasks.some(task => AUTO_REFRESH_STATUSES.has(normalize(task?.status)))) return;
    pollTimer = window.setTimeout(() => void pollOnce(), POLL_MS);
  }

  async function syncFlowState(providedTasks = null) {
    if (syncing) return providedTasks || [];
    syncing = true;
    try {
      const tasks = providedTasks || await fetchMissionTasks();
      lastSignature = taskSignature(tasks);
      const cards = [...document.querySelectorAll('#build-game-view .build-game-phase')];
      for (const card of cards) {
        const phaseId = phaseFromCard(card);
        if (!phaseId) continue;
        const task = latestForPhase(tasks, phaseId);
        if (!task) continue;
        const status = normalize(task.status);
        if (BLOCKING_STATUSES.has(status)) {
          launchLocks.delete(phaseLockKey(phaseId));
          installBusyAction(card, task);
          installApprovalFallback(card, task);
        } else if (status === 'completed' || RETRYABLE_STATUSES.has(status)) {
          launchLocks.delete(phaseLockKey(phaseId));
        }
      }
      schedulePoll(tasks);
      document.documentElement.dataset.devpilotGameFlow = 'v55';
      return tasks;
    } finally {
      syncing = false;
    }
  }

  async function pollOnce() {
    pollTimer = 0;
    if (document.visibilityState === 'hidden') return;
    try {
      const tasks = await fetchMissionTasks();
      const signature = taskSignature(tasks);
      if (signature !== lastSignature) {
        lastSignature = signature;
        await window.loadBuildGame?.();
        return;
      }
      await syncFlowState(tasks);
    } catch (error) {
      console.warn('[DevPilot Game] Falha no acompanhamento automático da fase', error);
      pollTimer = window.setTimeout(() => void pollOnce(), 5000);
    }
  }

  async function verifyLaunch(key, phaseId, attempt = 0) {
    try {
      const tasks = await fetchMissionTasks();
      const task = latestForPhase(tasks, phaseId);
      if (task && !RETRYABLE_STATUSES.has(normalize(task.status))) {
        launchLocks.delete(key);
        await window.loadBuildGame?.();
        return;
      }
    } catch (_) {}

    if (attempt < 7) {
      window.setTimeout(() => void verifyLaunch(key, phaseId, attempt + 1), 700);
      return;
    }
    launchLocks.delete(key);
    await window.loadBuildGame?.();
  }

  function installLaunchGuard() {
    document.addEventListener('click', event => {
      const button = event.target instanceof Element
        ? event.target.closest('#build-game-view [data-play-phase]')
        : null;
      if (!button) return;

      const phaseId = Number(button.dataset.playPhase || 0);
      if (!phaseId) return;
      const key = phaseLockKey(phaseId);
      if (launchLocks.has(key) || button.dataset.gameFlowLaunching === '1') {
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }

      launchLocks.set(key, Date.now());
      button.dataset.gameFlowLaunching = '1';
      queueMicrotask(() => {
        if (!button.isConnected) return;
        button.disabled = true;
        button.textContent = 'Iniciando fase…';
      });
      window.setTimeout(() => void verifyLaunch(key, phaseId), 450);
    }, true);
  }

  function wrapGameLoader() {
    const upstream = window.loadBuildGame;
    if (typeof upstream !== 'function' || upstream.__devpilotPhaseFlowGuardV55) return;
    const wrapped = async function loadBuildGameWithPhaseFlowGuard(...args) {
      const result = await upstream.apply(this, args);
      await syncFlowState();
      return result;
    };
    wrapped.__devpilotPhaseFlowGuardV55 = true;
    wrapped.__devpilotUpstream = upstream;
    window.loadBuildGame = wrapped;
  }

  installLaunchGuard();
  wrapGameLoader();

  document.addEventListener('devpilot:game:standalone-ready', () => void syncFlowState());
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void syncFlowState();
    else clearPoll();
  });
})();
