/* DevPilot Build Game delivery gate v73.
 * Creates one independent verifier after each completed base phase.
 */
(() => {
  'use strict';

  if (window.__devpilotDeliveryGateV73Ready) return;
  window.__devpilotDeliveryGateV73Ready = true;

  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const VERIFIER_MARKER = '[DEVPILOT_DELIVERY_VERIFIER_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const MAX_PHASES = 7;
  const TASK_LIMIT = 24;
  const inFlight = new Set();
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

  const verifierPrompt = ({missionId, phaseId, goal, sourceTask}) => `${GAME_MARKER}\n${VERIFIER_MARKER}\n[DEVPILOT_BUILD_GAME_PIPELINE_V2]\n[DEVPILOT_MODE=develop]\nPARTIDA: ${missionId}\nFASE: ${phaseId}/${MAX_PHASES}\nOBJETIVO: ${goal}\nORIGEM_EXECUCAO: ${sourceTask.id}\n\nMISSÃO: VERIFICAR ENTREGA REAL\nVocê é o gate independente da esteira. Não aceite o status completed da execução anterior como prova suficiente. Inspecione o projeto no estado atual e prove que a entrega desta fase existe de verdade e funciona no sistema do cliente.\n\nCONTRATO DE ENTREGA:\n- Leia AGENTS.md, documentação, .devpilot/build-game.md e o diff acumulado da partida.\n- Compare o OBJETIVO com critérios de aceite concretos e preserve o pedido literal do usuário.\n- Verifique artefatos persistentes: código, configuração, migrações, testes e integrações necessários.\n- Execute as verificações reais aplicáveis: teste, lint/typecheck, build e smoke.\n- Quando houver aplicação executável, valide o fluxo real por interface, API, CLI ou mecanismo equivalente.\n- Quando houver banco, confirme schema/migração aplicável e o estado resultante.\n- Quando houver Delivery Target configurado e autorizado, valide o ambiente real com healthcheck/smoke.\n- Registre critério, evidência, comando executado, resultado e pendências em .devpilot/build-game.md.\n- A evidência deve ser reproduzível por outra pessoa; uma mensagem de sucesso sem prova não conta.\n- Se qualquer critério obrigatório não puder ser provado, NÃO conclua.\n\nCRITÉRIO DE APROVAÇÃO:\nA tarefa só pode terminar como completed quando a funcionalidade desta fase estiver materializada no projeto, as verificações aplicáveis passarem e houver evidência reproduzível registrada. Na fase ${MAX_PHASES}, revalide o objetivo completo ponta a ponta contra o Delivery Target quando existir.`;

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
        `/tasks?project_id=${encodeURIComponent(projectId)}&limit=${TASK_LIMIT}`,
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
          const taskStatus = normalize(latest.status);
          if (taskStatus === 'completed') continue;
          if (retryFailed && FAILED.has(taskStatus)) {
            const base = phaseTasks.find(task => !isVerifier(task) && normalize(task.status) === 'completed');
            if (base) return createVerifier({projectId, missionId, phaseId, sourceTask:base});
          }
          break;
        }

        if (normalize(latest.status) !== 'completed') break;
        return createVerifier({projectId, missionId, phaseId, sourceTask:latest});
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
  window.__devpilotDeliveryGateDoesNotWrapLoader = true;
})();
