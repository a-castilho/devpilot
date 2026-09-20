/* DevPilot Build Game delivery gate v77.
 * Creates independent verifier gates; backend starts and owns final cloud delivery after 7/7.
 */
(() => {
  'use strict';

  if (window.__devpilotDeliveryGateV77Ready) return;
  window.__devpilotDeliveryGateV77Ready = true;

  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const VERIFIER_MARKER = '[DEVPILOT_DELIVERY_VERIFIER_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const MAX_PHASES = 7;
  const inFlight = new Set();
  const deliveryInFlight = new Set();
  const FAILED = new Set(['failed', 'cancelled', 'canceled']);

  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const promptValue = (task, label) => {
    const escaped = String(label || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return String(task?.prompt || '').match(new RegExp(`^${escaped}:\\s*(.+)$`, 'mi'))?.[1]?.trim() || '';
  };
  const phaseFromTask = task => Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  const missionFromTask = task => promptValue(task, 'PARTIDA');
  const goalFromTask = task => promptValue(task, 'OBJETIVO');
  const isGameTask = task => String(task?.prompt || '').includes(GAME_MARKER) || String(task?.title || '').startsWith('[Jogo]');
  const isVerifier = task => String(task?.prompt || '').includes(VERIFIER_MARKER) || String(task?.title || '').startsWith('[Jogo] Gate');

  const verifierPrompt = ({missionId, phaseId, goal, sourceTask}) => `${GAME_MARKER}\n${VERIFIER_MARKER}\n[DEVPILOT_BUILD_GAME_PIPELINE_V2]\n[DEVPILOT_MODE=develop]\nPARTIDA: ${missionId}\nFASE: ${phaseId}/${MAX_PHASES}\nOBJETIVO: ${goal}\nORIGEM_EXECUCAO: ${sourceTask.id}\n\nMISSÃO: VERIFICAR ENTREGA REAL\nVocê é o gate independente da esteira. Não aceite o status completed da execução anterior como prova suficiente. Inspecione o projeto no estado atual e prove que a entrega desta fase existe de verdade.\n\nCONTRATO DE ENTREGA:\n- Leia AGENTS.md, documentação e .devpilot/build-game.md.\n- Compare o OBJETIVO com critérios de aceite concretos.\n- Verifique código, configuração, migrações, testes e integração necessários.\n- Execute as verificações reais aplicáveis: teste, lint/typecheck, build e smoke.\n- Registre critério, evidência, comando e resultado em .devpilot/build-game.md.\n- Se qualquer critério obrigatório não puder ser provado, NÃO conclua.\n\nCRITÉRIO DE APROVAÇÃO:\nA tarefa só pode terminar como completed quando a fase estiver materializada, verificável e sem falhas obrigatórias não resolvidas.`;

  const createVerifier = async ({projectId, missionId, phaseId, sourceTask}) => {
    const goal = goalFromTask(sourceTask);
    if (!goal) return false;
    await window.api('/tasks', {
      method: 'POST',
      timeoutMs: 7000,
      body: JSON.stringify({
        project_id: projectId,
        title: `[Jogo] Gate ${phaseId} · Verificar entrega real`,
        prompt: verifierPrompt({missionId, phaseId, goal, sourceTask}),
        source: 'dashboard',
        priority: Math.min(100, 84 + phaseId * 2),
        requires_approval: false,
      }),
    });
    return true;
  };

  const finalVerifierApproved = missionTasks => {
    for (let phaseId = 1; phaseId <= MAX_PHASES; phaseId += 1) {
      const latest = missionTasks.find(task => phaseFromTask(task) === phaseId);
      if (!latest || !isVerifier(latest) || normalize(latest.status) !== 'completed') return false;
    }
    return true;
  };

  const ensureAutomaticDelivery = async projectId => {
    // Compatibility name: this function is intentionally observer-only.
    // The backend detects Gate 7/7 and owns delivery start/retry/recovery.
    if (!projectId || deliveryInFlight.has(projectId) || typeof window.api !== 'function') return false;
    deliveryInFlight.add(projectId);
    try {
      const current = await window.api(`/projects/${encodeURIComponent(projectId)}/delivery`, {
        timeoutMs: 5000,
        retry: false,
      });
      document.dispatchEvent(new CustomEvent('devpilot:delivery:updated', {detail: current}));
      if (normalize(current?.status) === 'ready') {
        document.dispatchEvent(new CustomEvent('devpilot:delivery:ready', {detail: current}));
        return true;
      }
      return false;
    } catch (error) {
      console.warn('[DevPilot Delivery Observer]', error);
      return false;
    } finally {
      deliveryInFlight.delete(projectId);
    }
  };

  const ensureVerifier = async ({retryFailed = false} = {}) => {
    if (typeof window.api !== 'function') return false;
    const projectId = String(localStorage.getItem(PROJECT_KEY) || '').trim();
    const missionId = String(localStorage.getItem(MISSION_KEY) || '').trim();
    if (!projectId || !missionId) return false;

    const key = `${projectId}:${missionId}`;
    if (inFlight.has(key)) return false;
    inFlight.add(key);
    try {
      const tasks = await window.api(
        `/tasks?project_id=${encodeURIComponent(projectId)}&limit=24`,
        {timeoutMs:4000, retry:false},
      );
      const missionTasks = (Array.isArray(tasks) ? tasks : [])
        .filter(task => isGameTask(task) && missionFromTask(task) === missionId)
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

      for (let phaseId = 1; phaseId <= MAX_PHASES; phaseId += 1) {
        const phaseTasks = missionTasks.filter(task => phaseFromTask(task) === phaseId);
        const latest = phaseTasks[0];
        if (!latest) break;

        if (isVerifier(latest)) {
          const status = normalize(latest.status);
          if (status === 'completed') continue;
          if (retryFailed && FAILED.has(status)) {
            const base = phaseTasks.find(task => !isVerifier(task) && normalize(task.status) === 'completed');
            if (base) return createVerifier({projectId, missionId, phaseId, sourceTask:base});
          }
          break;
        }

        if (normalize(latest.status) !== 'completed') break;
        return createVerifier({projectId, missionId, phaseId, sourceTask:latest});
      }

      if (finalVerifierApproved(missionTasks)) {
        await ensureAutomaticDelivery(projectId);
      }
      return false;
    } finally {
      inFlight.delete(key);
    }
  };

  const run = async () => {
    try {
      const created = await ensureVerifier();
      if (created && typeof window.loadBuildGame === 'function') {
        window.setTimeout(() => void window.loadBuildGame().catch(error => console.warn('[DevPilot Gate Reload]', error)), 150);
      }
    } catch (error) {
      console.warn('[DevPilot Delivery Gate]', error);
    }
  };

  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    window.setTimeout(() => {
      scheduled = false;
      void run();
    }, 300);
  };

  document.addEventListener('devpilot:game:rendered', schedule);
  document.addEventListener('devpilot:game:enhancements-ready', schedule);

  window.__devpilotEnsureDeliveryGate = ensureVerifier;
  window.__devpilotEnsureAutomaticDelivery = ensureAutomaticDelivery;
  window.__devpilotDeliveryGateDoesNotWrapLoader = true;
})();
