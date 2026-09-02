/* DevPilot game v80 — continuity layer for multi-project development. */
(() => {
  'use strict';

  if (window.__devpilotGameDevelopmentContinuityV80Ready) return;
  window.__devpilotGameDevelopmentContinuityV80Ready = true;

  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const NEW_ROUND_INTENT_KEY = 'devpilot-game-v80-new-round-intent';
  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const PAGE_SIZE = 100;
  const MAX_PROJECTS = 1000;
  const RECOVERY_POLL_MS = 5000;
  const CANCELLED_RETRY_KEY = 'devpilot-game-v80-cancelled-retry';

  let projectLoadPromise = null;
  let switchBusy = false;
  let staleRepairBusy = false;
  let recoveryBusy = false;
  let recoveryTimer = 0;
  let recoveryData = null;

  const engine = () => window.__devpilotGameControllerV73;
  const gameState = () => window.__devpilotGameState;
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const projectRows = () => Array.isArray(gameState()?.projects) ? gameState().projects : [];
  const projectById = id => projectRows().find(project => String(project?.id) === String(id));
  const isGameTask = task => String(task?.prompt || '').includes(GAME_MARKER) || String(task?.title || '').startsWith('[Jogo]');
  const safeText = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  function installStyle() {
    if (document.getElementById('devpilot-game-continuity-v80-style')) return;
    const style = document.createElement('style');
    style.id = 'devpilot-game-continuity-v80-style';
    style.textContent = `
      .game80-project-switch{display:grid;gap:6px;padding:12px;border:1px solid #244158;border-radius:14px;background:#071724}.game80-project-switch span{color:#7f95aa;font-size:.72rem;font-weight:850;letter-spacing:.05em;text-transform:uppercase}.game80-project-switch select{width:100%;min-height:44px;border:1px solid #294158;border-radius:12px;background:#061421;color:#f4f9ff;padding:10px 12px}
      .game80-continuity{display:grid;gap:8px;padding:13px 15px;border:1px solid #2c4b62;border-radius:14px;background:#0a2131;color:#b8ccda}.game80-continuity strong{color:#fff}.game80-continuity.active{border-color:#2d8d80;background:#0b2b32}.game80-continuity.manual{border-color:#9b6b35;background:#302516}.game80-continuity.error{border-color:#a84b5c;background:#351923}
      .game80-continuity textarea{width:100%;min-height:92px;box-sizing:border-box;border:1px solid #71562f;border-radius:10px;background:#100f10;color:#f4f7fb;padding:10px;resize:vertical}.game80-continuity button{min-height:42px;border:1px solid #3a6c80;border-radius:10px;background:#0b3142;color:#e9f8ff;font-weight:850;padding:8px 12px}.game80-continuity.manual button{border-color:#9b753d;background:#4b3517;color:#ffe6ad}
      @media(max-width:720px){.game80-project-switch,.game80-continuity{width:auto}.game80-continuity button{width:100%}}
    `;
    document.head.appendChild(style);
  }

  async function loadAllProjects() {
    if (projectLoadPromise) return projectLoadPromise;
    if (typeof window.api !== 'function') return projectRows();

    projectLoadPromise = (async () => {
      const merged = new Map(projectRows().map(project => [String(project.id), project]));
      let offset = 0;
      while (offset < MAX_PROJECTS) {
        const page = await window.api(`/ui/projects?limit=${PAGE_SIZE}&offset=${offset}`, {
          timeoutMs: 6000,
          retry: false,
        });
        const rows = Array.isArray(page) ? page : [];
        rows.forEach(project => merged.set(String(project.id), project));
        if (rows.length < PAGE_SIZE) break;
        offset += PAGE_SIZE;
      }

      if (gameState()) gameState().projects = [...merged.values()];
      document.dispatchEvent(new CustomEvent('devpilot:game:projects-ready', {
        detail: {count: merged.size},
      }));
      engine()?.emit?.();
      return projectRows();
    })().catch(error => {
      console.warn('[DevPilot Game Continuity] Falha ao carregar todos os projetos', error);
      return projectRows();
    }).finally(() => {
      projectLoadPromise = null;
    });

    return projectLoadPromise;
  }

  function coreProjectSelect() {
    return document.querySelector('#build-game-project');
  }

  async function switchProject(projectId) {
    const id = String(projectId || '').trim();
    if (!id || switchBusy) return false;
    switchBusy = true;
    try {
      await loadAllProjects();
      const project = projectById(id);
      localStorage.setItem(PROJECT_KEY, id);
      localStorage.removeItem(MISSION_KEY);

      const select = coreProjectSelect();
      if (!select) {
        window.location.reload();
        return true;
      }

      if (!Array.from(select.options).some(option => String(option.value) === id)) {
        select.add(new Option(String(project?.name || id), id));
      }
      select.disabled = false;
      select.value = id;
      select.dispatchEvent(new Event('change', {bubbles: true}));
      return true;
    } finally {
      window.setTimeout(() => { switchBusy = false; }, 100);
    }
  }

  function hasNewRoundIntent() {
    return sessionStorage.getItem(NEW_ROUND_INTENT_KEY) === '1';
  }

  function markNewRoundIntent() {
    sessionStorage.setItem(NEW_ROUND_INTENT_KEY, '1');
  }

  function clearNewRoundIntentWhenStarted(state) {
    if (state?.hasTasks) sessionStorage.removeItem(NEW_ROUND_INTENT_KEY);
  }

  async function repairStaleMission(state) {
    if (!state?.projectId || state.hasTasks || staleRepairBusy || switchBusy) return;
    if (hasNewRoundIntent()) return;
    if (typeof window.api !== 'function') return;

    staleRepairBusy = true;
    try {
      const rows = await window.api(
        `/ui/game-tasks?project_id=${encodeURIComponent(state.projectId)}&limit=80`,
        {timeoutMs: 4500, retry: false},
      );
      if ((Array.isArray(rows) ? rows : []).some(isGameTask)) {
        await switchProject(state.projectId);
      }
    } catch (error) {
      console.warn('[DevPilot Game Continuity] Não foi possível recuperar a rodada anterior', error);
    } finally {
      staleRepairBusy = false;
    }
  }

  function recoveryLabel(data) {
    const state = String(data?.state || '');
    return ({
      ready_to_recover: 'Preparando correção automática…',
      agent_recovery: '⚡ Corrigindo a causa da falha automaticamente…',
      retesting: '▶ Retestando a etapa original…',
      resolved: '✓ Falha corrigida; retomando a rodada…',
      awaiting_intervention: 'A correção precisa de uma informação ou autorização.',
      intervention_required: 'O agente tentou corrigir e precisa de orientação.',
      recovery_exhausted: 'A correção automática terminou, mas a falha ainda precisa de orientação.',
    })[state] || 'Tratando a falha da etapa…';
  }

  function publishRecovery(data) {
    recoveryData = data && typeof data === 'object' ? data : null;
    window.__devpilotGameRecoveryV80 = recoveryData;
    document.dispatchEvent(new CustomEvent('devpilot:game:recovery', {detail: recoveryData || {}}));
    decorate();
  }

  function scheduleRecovery(delay = RECOVERY_POLL_MS) {
    window.clearTimeout(recoveryTimer);
    recoveryTimer = window.setTimeout(() => void recoverCurrentFailure(), delay);
  }

  async function recoverCurrentFailure() {
    if (recoveryBusy || typeof window.api !== 'function') return;
    const controller = engine();
    const state = controller?.snapshot?.();
    if (!controller || !state?.taskId) return;

    const status = normalize(state.taskStatus);
    if (!['failed', 'blocked', 'cancelled', 'canceled'].includes(status)) {
      if (recoveryData) publishRecovery(null);
      return;
    }

    if (status === 'cancelled' || status === 'canceled') {
      const key = `${CANCELLED_RETRY_KEY}:${state.missionId}:${state.currentPhaseId}:${state.verifier ? 'gate' : 'base'}`;
      if (!sessionStorage.getItem(key)) {
        sessionStorage.setItem(key, '1');
        try {
          await controller.retry?.();
        } catch (error) {
          console.warn('[DevPilot Game Continuity] Retry automático cancelado falhou', error);
        }
      }
      return;
    }

    recoveryBusy = true;
    try {
      let data = await window.api(`/tasks/${encodeURIComponent(state.taskId)}/recovery`, {
        timeoutMs: 5000,
        retry: false,
      });

      if (String(data?.state || '') === 'ready_to_recover') {
        data = await window.api(`/tasks/${encodeURIComponent(state.taskId)}/recovery/escalate`, {
          method: 'POST',
          timeoutMs: 7000,
        });
      }

      if (data?.can_resume_original) {
        data = await window.api(`/tasks/${encodeURIComponent(state.taskId)}/recovery/resume`, {
          method: 'POST',
          timeoutMs: 7000,
        });
      }

      publishRecovery(data);
      const recoveryState = String(data?.state || '');
      if (recoveryState === 'resolved' || recoveryState === 'retesting') {
        await controller.refresh?.();
      }

      if (!data?.manual_intervention_required && recoveryState !== 'resolved') {
        scheduleRecovery();
      }
    } catch (error) {
      console.warn('[DevPilot Game Continuity] Recuperação automática indisponível', error);
      publishRecovery({
        state: 'recovery_error',
        manual_intervention_required: false,
        failure: {message: String(error?.message || 'Falha ao consultar recuperação')},
      });
      scheduleRecovery(8000);
    } finally {
      recoveryBusy = false;
    }
  }

  async function submitGuidance(button, textarea, taskId) {
    const instruction = String(textarea?.value || '').trim();
    if (instruction.length < 3 || !taskId) return;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Enviando orientação…';
    try {
      const data = await window.api(`/tasks/${encodeURIComponent(taskId)}/recovery/intervene`, {
        method: 'POST',
        timeoutMs: 7000,
        body: JSON.stringify({instruction}),
      });
      publishRecovery(data);
      textarea.value = '';
      scheduleRecovery(1200);
    } catch (error) {
      window.toast?.(error?.message || 'Não foi possível orientar a recuperação.');
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function projectSwitchMarkup(state) {
    const options = projectRows().map(project => `
      <option value="${safeText(project.id)}" ${String(project.id) === String(state.projectId) ? 'selected' : ''}>${safeText(project.name)}</option>
    `).join('');
    return `<label class="game80-project-switch"><span>Projeto em desenvolvimento</span><select data-game80-project-switch>${options}</select></label>`;
  }

  function recoveryMarkup(state) {
    if (!recoveryData || String(recoveryData?.task_id || state.taskId || '') !== String(state.taskId || '')) return '';
    const manual = Boolean(recoveryData?.manual_intervention_required);
    const failure = String(recoveryData?.failure?.message || '').trim();
    const klass = manual ? 'manual' : String(recoveryData?.state || '') === 'recovery_error' ? 'error' : 'active';
    return `
      <section class="game80-continuity ${klass}" data-game80-recovery>
        <strong>${safeText(recoveryLabel(recoveryData))}</strong>
        ${failure ? `<span>${safeText(failure)}</span>` : ''}
        ${manual ? `
          <textarea data-game80-guidance maxlength="4000" placeholder="Informe somente o que o agente não consegue descobrir sozinho: credencial atualizada, serviço correto, permissão liberada, etc."></textarea>
          <button type="button" data-game80-guidance-submit>Orientar agente e continuar</button>
        ` : '<span>A rodada continua automaticamente assim que a causa for resolvida.</span>'}
      </section>`;
  }

  function decorate() {
    installStyle();
    const controller = engine();
    const state = controller?.snapshot?.();
    const host = document.getElementById('devpilot-game-ui-v73');
    const panel = host?.querySelector('.game74');
    if (!state || !host || !panel) return;

    const newRoundSelect = host.querySelector('[data-game73-project]');
    if (newRoundSelect && newRoundSelect.dataset.game80Continuity !== '1') {
      newRoundSelect.dataset.game80Continuity = '1';
      newRoundSelect.addEventListener('change', () => void switchProject(newRoundSelect.value));
    }

    if (state.hasTasks && !panel.querySelector('[data-game80-project-switch]')) {
      const firstBlock = panel.firstElementChild;
      firstBlock?.insertAdjacentHTML('afterend', projectSwitchMarkup(state));
      panel.querySelector('[data-game80-project-switch]')?.addEventListener('change', event => {
        void switchProject(event.currentTarget.value);
      });
    }

    panel.querySelector('[data-game80-recovery]')?.remove();
    const recovery = recoveryMarkup(state);
    if (recovery) {
      const actions = panel.querySelector('.game74-actions');
      if (actions) actions.insertAdjacentHTML('beforebegin', recovery);
      else panel.insertAdjacentHTML('beforeend', recovery);
      const section = panel.querySelector('[data-game80-recovery]');
      const textarea = section?.querySelector('[data-game80-guidance]');
      section?.querySelector('[data-game80-guidance-submit]')?.addEventListener('click', event => {
        void submitGuidance(event.currentTarget, textarea, state.taskId);
      });
    }
  }

  function handleState(event) {
    const state = event?.detail && typeof event.detail === 'object'
      ? event.detail
      : engine()?.snapshot?.();
    if (!state) return;
    clearNewRoundIntentWhenStarted(state);
    decorate();
    void repairStaleMission(state);

    const status = normalize(state.taskStatus);
    if (['failed', 'blocked', 'cancelled', 'canceled'].includes(status)) {
      scheduleRecovery(300);
    } else if (recoveryData) {
      publishRecovery(null);
    }
  }

  document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest('[data-game73-new], #build-game-new')) markNewRoundIntent();
  }, true);

  document.addEventListener('devpilot:game:state', handleState);
  document.addEventListener('devpilot:game:rendered', () => decorate());
  document.addEventListener('devpilot:game:projects-ready', () => decorate());
  document.addEventListener('devpilot:game:recovery', () => decorate());
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      void loadAllProjects();
      const state = engine()?.snapshot?.();
      if (state) handleState({detail: state});
    }
  });

  window.__devpilotGameSwitchProjectV80 = switchProject;
  window.__devpilotGameRecoverV80 = recoverCurrentFailure;
  window.__devpilotGameLoadAllProjectsV80 = loadAllProjects;

  installStyle();
  window.setTimeout(() => {
    void loadAllProjects();
    const state = engine()?.snapshot?.();
    if (state) handleState({detail: state});
  }, 0);
})();
