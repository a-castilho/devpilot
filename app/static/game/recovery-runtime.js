/* DevPilot game v79 — failure-aware automatic recovery for the real game pipeline. */
(() => {
  'use strict';

  if (window.__devpilotGameRecoveryV79Ready) return;
  window.__devpilotGameRecoveryV79Ready = true;

  const REPAIR_MARKER = '[DEVPILOT_AUTO_REPAIR_V2]';
  const patched = new WeakSet();
  const inFlight = new Set();

  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const failedStatuses = new Set(['failed', 'cancelled', 'canceled']);

  const phaseFromPrompt = prompt => {
    const match = String(prompt || '').match(/^FASE:\s*(\d+)\//mi);
    return Number(match?.[1] || 0);
  };

  const missionFromPrompt = prompt => String(prompt || '').match(/^PARTIDA:\s*(.+)$/mi)?.[1]?.trim() || '';

  const failureContext = task => {
    const keys = [
      'error', 'error_message', 'last_error', 'failure_reason', 'status_reason',
      'detail', 'message', 'result', 'output', 'response', 'summary', 'log', 'logs'
    ];
    const parts = [];
    for (const key of keys) {
      const value = task?.[key];
      if (value === undefined || value === null || value === '') continue;
      const text = typeof value === 'string' ? value : JSON.stringify(value);
      parts.push(`${key}: ${text.slice(0, 1800)}`);
      if (parts.join('\n').length >= 5000) break;
    }
    if (!parts.length) {
      const compact = Object.fromEntries(Object.entries(task || {})
        .filter(([key, value]) => key !== 'prompt' && value !== undefined && value !== null)
        .slice(0, 24));
      parts.push(`registro_da_tarefa: ${JSON.stringify(compact).slice(0, 3500)}`);
    }
    return parts.join('\n').slice(0, 6000);
  };

  const phaseRepairRules = phaseId => phaseId === 1
    ? `REGRAS ESPECÍFICAS DA ETAPA 1 — PLANEJAMENTO:
- Descubra a causa concreta da falha anterior antes de repetir qualquer comando.
- Leia AGENTS.md quando existir; se não existir, siga a documentação e a estrutura real do repositório.
- Garanta que .devpilot/ exista antes de gravar .devpilot/build-game.md.
- Execute somente comandos de baseline que realmente existam para a stack detectada. Não invente npm, pytest, composer, docker ou outro comando ausente do projeto.
- Se faltar uma dependência/configuração local necessária apenas para obter o baseline e houver uma correção segura e reversível, corrija-a e repita a verificação.
- Se testes/lint/build já estiverem vermelhos antes da implementação e a falha for preexistente ou não relacionada ao objetivo, registre a evidência como BASELINE VERMELHO e continue o planejamento; isso, sozinho, NÃO deve reprovar a etapa 1.
- Não implemente ainda a funcionalidade pedida pelo usuário. Nesta etapa corrija apenas impedimentos técnicos do próprio planejamento/baseline.
- A etapa só deve falhar novamente se for realmente impossível inspecionar o repositório, persistir o plano ou produzir critérios de aceite verificáveis.`
    : `REGRAS DE RECUPERAÇÃO:
- Analise primeiro a causa da tentativa anterior.
- Corrija a causa raiz, não apenas o sintoma.
- Reexecute as verificações necessárias e só conclua com evidência real.
- Preserve o objetivo original e o escopo da etapa atual.`;

  const tasksForProject = async projectId => {
    if (typeof window.api !== 'function' || !projectId) return [];
    const rows = await window.api(`/tasks?project_id=${encodeURIComponent(projectId)}&limit=500`);
    return Array.isArray(rows) ? rows : [];
  };

  const findFailedTask = (tasks, state) => {
    const byId = tasks.find(task => String(task?.id || '') === String(state?.taskId || ''));
    if (byId) return byId;
    return tasks.find(task => {
      const prompt = String(task?.prompt || '');
      return missionFromPrompt(prompt) === String(state?.missionId || '') &&
        phaseFromPrompt(prompt) === Number(state?.currentPhaseId || 0) &&
        failedStatuses.has(normalize(task?.status));
    });
  };

  const createCorrection = async (engine, state, failedTask) => {
    const prompt = String(failedTask?.prompt || '').trim();
    if (!prompt) throw new Error('A tarefa que falhou não possui o prompt original para autocorreção.');

    const phaseId = Number(state.currentPhaseId || phaseFromPrompt(prompt) || 0);
    const context = failureContext(failedTask);
    const repairPrompt = `${prompt}\n\n${REPAIR_MARKER}\nTENTATIVA_ANTERIOR: ${failedTask.id || state.taskId || 'desconhecida'}\n\nFALHA OBSERVADA:\n${context}\n\n${phaseRepairRules(phaseId)}\n\nCONTRATO DA CORREÇÃO:\n- Use a resposta/erro acima como entrada obrigatória da correção.\n- Não repita cegamente a mesma ação que falhou.\n- Registre em .devpilot/build-game.md a causa encontrada, a correção aplicada e a nova evidência.\n- Ao terminar, o resultado precisa permitir que o gate independente valide esta mesma etapa.`;

    const title = `[Jogo] Correção etapa ${phaseId} · tentativa ${failedTask.id || state.taskId || ''}`.trim();
    await window.api('/tasks', {
      method: 'POST',
      body: JSON.stringify({
        project_id: state.projectId,
        title,
        prompt: repairPrompt,
        source: 'dashboard',
        priority: Math.min(100, 82 + Math.max(1, phaseId) * 2),
        requires_approval: false
      })
    });

    await window.loadBuildGame?.();
    engine.schedule?.();
    return engine.snapshot?.() || state;
  };

  const patch = () => {
    const engine = window.__devpilotGameControllerV73;
    if (!engine || patched.has(engine) || typeof engine.retry !== 'function') return false;

    const originalRetry = engine.retry.bind(engine);
    engine.retry = async () => {
      const state = engine.snapshot?.();
      if (!state?.failed || !state?.currentPhaseId) return originalRetry();

      // The legacy delivery gate already has its own retry contract. Phase failures
      // are rebuilt here with the previous attempt's actual failure as correction input.
      if (state.verifier) return originalRetry();

      const key = `${state.missionId}:${state.currentPhaseId}:${state.taskId}`;
      if (inFlight.has(key)) return state;
      inFlight.add(key);
      try {
        const tasks = await tasksForProject(state.projectId);
        const failedTask = findFailedTask(tasks, state);
        if (!failedTask) return originalRetry();
        return await createCorrection(engine, state, failedTask);
      } catch (error) {
        console.error('[DevPilot Game Recovery]', error);
        return originalRetry();
      } finally {
        window.setTimeout(() => inFlight.delete(key), 4000);
      }
    };

    patched.add(engine);
    document.dispatchEvent(new CustomEvent('devpilot:game:recovery-ready'));
    return true;
  };

  document.addEventListener('devpilot:game:core-ready', patch);
  document.addEventListener('devpilot:game:rendered', patch);
  document.addEventListener('devpilot:game:state', patch);
  patch();
})();
