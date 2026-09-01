/* DevPilot Build Game delivery gate: a completed implementation is not victory until independently verified. */
(() => {
  'use strict';

  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const VERIFIER_MARKER = '[DEVPILOT_DELIVERY_VERIFIER_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const MAX_PHASES = 6;
  const inFlight = new Set();

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

  const verifierPrompt = ({missionId, phaseId, goal, sourceTask}) => `${GAME_MARKER}\n${VERIFIER_MARKER}\n[DEVPILOT_MODE=develop]\nPARTIDA: ${missionId}\nFASE: ${phaseId}/${MAX_PHASES}\nOBJETIVO: ${goal}\nORIGEM_EXECUCAO: ${sourceTask.id}\n\nMISSÃO: VERIFICAR ENTREGA REAL\nVocê é o gate independente da esteira. Não aceite o status completed da execução anterior como prova suficiente. Inspecione o projeto no estado atual e prove que a entrega desta fase existe de verdade e funciona no sistema do cliente.\n\nCONTRATO DE ENTREGA:\n- Leia AGENTS.md, documentação, .devpilot/build-game.md e o diff acumulado da partida.\n- Compare o OBJETIVO com critérios de aceite concretos. Se ainda não existirem, registre-os em .devpilot/build-game.md antes de validar.\n- Verifique artefatos persistentes: código, configuração, migrações, testes e integração necessários ao objetivo.\n- Execute os comandos reais aplicáveis: teste, lint/typecheck, build e smoke. Não declare comando que não foi executado.\n- Quando houver aplicação executável, valide o fluxo real por interface, API, CLI ou mecanismo equivalente; mocks não contam como evidência final.\n- Quando houver banco, confirme schema/migração aplicável. Quando houver deploy configurado e autorizado, confirme healthcheck/smoke do ambiente de entrega.\n- Registre em .devpilot/build-game.md: critério, evidência, comando executado, resultado e pendências.\n- Se qualquer critério obrigatório não puder ser provado, NÃO conclua. Corrija somente o necessário quando for seguro e repita a validação; caso contrário encerre como falha/bloqueio com a causa real.\n- Nunca transforme URL existente, relatório, ausência de erro ou simples status completed em vitória.\n\nCRITÉRIO DE APROVAÇÃO DO GATE:\nA tarefa só pode terminar como completed quando a funcionalidade desta fase estiver materializada no projeto, as verificações aplicáveis passarem e houver evidência reproduzível registrada. Na fase 6, revalide o objetivo completo ponta a ponta e confirme que o resultado está pronto para uso no Delivery Target do projeto.`;

  const ensureVerifier = async () => {
    if (typeof api !== 'function') return false;
    const projectId = localStorage.getItem(PROJECT_KEY) || '';
    const missionId = localStorage.getItem(MISSION_KEY) || '';
    if (!projectId || !missionId) return false;

    const key = `${projectId}:${missionId}`;
    if (inFlight.has(key)) return false;
    inFlight.add(key);
    try {
      const tasks = await api(`/tasks?project_id=${encodeURIComponent(projectId)}&limit=500`);
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
        await api('/tasks', {
          method: 'POST',
          body: JSON.stringify({
            project_id: projectId,
            title: `[Jogo] Gate ${phaseId} · Verificar entrega real`,
            prompt: verifierPrompt({missionId, phaseId, goal, sourceTask: latest}),
            source: 'dashboard',
            priority: Math.min(100, 84 + phaseId * 2),
            requires_approval: false
          })
        });
        return true;
      }
      return false;
    } finally {
      inFlight.delete(key);
    }
  };

  const originalLoad = window.loadBuildGame;
  if (typeof originalLoad !== 'function') return;

  window.loadBuildGame = async (...args) => {
    try {
      await ensureVerifier();
    } catch (error) {
      console.error('[DEVPILOT_DELIVERY_GATE]', error);
      if (typeof toast === 'function') toast(`Gate de entrega: ${error.message}`);
    }
    return originalLoad(...args);
  };

  window.__devpilotEnsureDeliveryGate = ensureVerifier;
})();
