/* DevPilot Build Game delivery gate.
 * Verification runs in the background and never wraps or blocks loadBuildGame.
 */
(() => {
  'use strict';

  if (window.__devpilotDeliveryGateReady) return;
  window.__devpilotDeliveryGateReady = true;

  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const VERIFIER_MARKER = '[DEVPILOT_DELIVERY_VERIFIER_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const MAX_PHASES = 7;
  const TASK_LIMIT = 24;
  const inFlight = new Set();
  let scheduled = false;
  let lastRunAt = 0;

  const normalize = value => String(value || '').toLowerCase().replaceAll(' ', '_');
  const promptValue = (task, label) => {
    const escaped = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = String(task?.prompt || '').match(new RegExp(`^${escaped}:\\s*(.+)$`, 'mi'));
    return match?.[1]?.trim() || '';
  };
  const phaseFromTask = task => Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  const missionFromTask = task => promptValue(task, 'PARTIDA');
  const goalFromTask = task => promptValue(task, 'OBJETIVO');
  const isGameTask = task => String(task?.prompt || '').includes(GAME_MARKER);
  const isVerifier = task => String(task?.prompt || '').includes(VERIFIER_MARKER);

  const verifierPrompt = ({missionId, phaseId, goal, sourceTask}) => `${GAME_MARKER}\n${VERIFIER_MARKER}\n[DEVPILOT_BUILD_GAME_PIPELINE_V2]\n[DEVPILOT_MODE=develop]\nPARTIDA: ${missionId}\nFASE: ${phaseId}/${MAX_PHASES}\nOBJETIVO: ${goal}\nORIGEM_EXECUCAO: ${sourceTask.id}\n\nMISSÃO: VERIFICAR ENTREGA REAL\nVocê é o gate independente da esteira. Não aceite o status completed da execução anterior como prova suficiente. Inspecione o projeto no estado atual e prove que a entrega desta fase existe de verdade e funciona no sistema do cliente.\n\nCONTRATO DE ENTREGA:\n- Leia AGENTS.md, documentação, .devpilot/build-game.md e o diff acumulado da partida.\n- Compare o OBJETIVO com critérios de aceite concretos.\n- Verifique artefatos persistentes: código, configuração, migrações, testes e integração necessários ao objetivo.\n- Execute os comandos reais aplicáveis: teste, lint/typecheck, build e smoke.\n- Quando houver aplicação executável, valide o fluxo real por interface, API, CLI ou mecanismo equivalente.\n- Registre critério, evidência, comando executado, resultado e pendências em .devpilot/build-game.md.\n- Se qualquer critério obrigatório não puder ser provado, NÃO conclua.\n\nCRITÉRIO DE APROVAÇÃO DO GATE:\nA tarefa só pode terminar como completed quando a funcionalidade desta fase estiver materializada no projeto, as verificações aplicáveis passarem e houver evidência reproduzível registrada. Na fase ${MAX_PHASES}, revalide o objetivo completo ponta a ponta.`;

  const ensureVerifier = async () => {
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
        {timeoutMs: 3500, retry: false},
      );
      const missionTasks = (Array.isArray(tasks) ? tasks : [])
        .filter(task => isGameTask(task) && missionFromTask(task) === missionId)
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

      for (let phaseId = 1; phaseId <= MAX_PHASES; phaseId += 1) {
        const phaseTasks = missionTasks.filter(task => phaseFromTask(task) === phaseId);
        const latest = phaseTasks[0];
        if (!latest) break;
        if (isVerifier(latest)) {
          if (normalize(latest.status) !== 'completed') break;
          continue;
        }
        if (normalize(latest.status) !== 'completed') break;

        const goal = goalFromTask(latest);
        await window.api('/tasks', {
          method: 'POST',
          timeoutMs: 6000,
          body: JSON.stringify({
            project_id: projectId,
            title: `[Jogo] Gate ${phaseId} · Verificar entrega real`,
            prompt: verifierPrompt({missionId, phaseId, goal, sourceTask: latest}),
            source: 'dashboard',
            priority: Math.min(100, 84 + phaseId * 2),
            requires_approval: false,
          }),
        });
        return true;
      }
      return false;
    } finally {
      inFlight.delete(key);
    }
  };

  const runGate = async () => {
    const now = Date.now();
    if (now - lastRunAt < 1200) return;
    lastRunAt = now;
    try {
      const created = await ensureVerifier();
      if (created && typeof window.loadBuildGame === 'function') {
        window.setTimeout(() => void window.loadBuildGame(), 120);
      }
    } catch (error) {
      console.warn('[DevPilot Delivery Gate]', error);
    }
  };

  const scheduleGate = () => {
    if (scheduled) return;
    scheduled = true;
    window.setTimeout(() => {
      scheduled = false;
      void runGate();
    }, 280);
  };

  document.addEventListener('devpilot:game:rendered', scheduleGate);
  document.addEventListener('devpilot:game:enhancements-ready', scheduleGate);
  window.setTimeout(scheduleGate, 450);

  window.__devpilotEnsureDeliveryGate = ensureVerifier;
  window.__devpilotDeliveryGateDoesNotWrapLoader = true;
})();
