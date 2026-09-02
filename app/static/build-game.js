/* DevPilot Build Game: one-click delivery controller over the real task pipeline. */
(() => {
  'use strict';

  if (window.__devpilotBuildGameEngineV73) return;
  window.__devpilotBuildGameEngineV73 = true;

  const MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const PIPELINE_MARKER = '[DEVPILOT_BUILD_GAME_PIPELINE_V2]';
  const VERIFIER_MARKER = '[DEVPILOT_DELIVERY_VERIFIER_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const GOAL_KEY = 'devpilot-build-game-goal';
  const ACTIVE_STATUSES = new Set(['awaiting_approval', 'queued', 'running', 'review', 'blocked']);
  const FAILED_STATUSES = new Set(['failed', 'cancelled', 'canceled']);

  const phases = [
    {
      id: 1,
      icon: '🧭',
      name: 'Planejamento',
      xp: 100,
      summary: 'Transformar o pedido em plano e critérios de aceite verificáveis.',
      evidence: 'Plano persistido, baseline executado e critérios de aceite ligados ao pedido.',
      mission: `Leia AGENTS.md, documentação e repositório antes de agir. Preserve literalmente o objetivo informado pelo usuário. Registre .devpilot/build-game.md com objetivo, estado inicial, escopo, fora de escopo, critérios de aceite, riscos, arquivos prováveis e comandos reais de instalação, execução, lint, build e testes. Execute a verificação de baseline. Não implemente a funcionalidade nesta etapa e não invente resultado.`
    },
    {
      id: 2,
      icon: '⚙️',
      name: 'Implementação',
      xp: 220,
      summary: 'Construir no projeto a funcionalidade completa descrita pelo usuário.',
      evidence: 'Delta funcional real no repositório ligado aos critérios de aceite.',
      mission: `Implemente a funcionalidade descrita no objetivo e no contrato .devpilot/build-game.md. Entregue uma fatia vertical completa e utilizável, cobrindo modelo de dados, backend, frontend, autorização, validações, migrações e configuração quando aplicáveis. Esta etapa precisa produzir mudança material de comportamento observável. Registre git status --short e git diff --stat e relacione as mudanças aos critérios de aceite.`
    },
    {
      id: 3,
      icon: '▶️',
      name: 'Execução',
      xp: 100,
      summary: 'Subir o sistema real e provar que o novo fluxo pode ser utilizado.',
      evidence: 'Comandos de execução, migrações, health check e smoke com resultado registrado.',
      mission: `Execute o sistema pela forma oficial do repositório, aplique migrações e gere build quando aplicável. Verifique health check, logs e o fluxo principal com dados de teste seguros. Corrija erros de inicialização, integração ou runtime e repita a execução. Registre comandos, serviços envolvidos e resultado observável.`
    },
    {
      id: 4,
      icon: '🧪',
      name: 'Testes',
      xp: 160,
      summary: 'Validar critérios de aceite, regressões, segurança e cenários negativos.',
      evidence: 'Testes focados e suíte aplicável verdes com comandos e resultados reais.',
      mission: `Crie ou atualize testes automáticos que provem os critérios de aceite. Cubra caminho feliz, validações, falhas, autorização, isolamento de dados e regressões aplicáveis. Execute testes, lint, typecheck e build existentes conforme a stack. Corrija falhas e repita até ficar verde. Não silencie testes válidos.`
    },
    {
      id: 5,
      icon: '📚',
      name: 'Documentação',
      xp: 80,
      summary: 'Registrar uso, decisões, configuração e evidências da funcionalidade entregue.',
      evidence: 'Documentação atualizada e contrato da rodada rastreável.',
      mission: `Atualize a documentação para explicar a funcionalidade, configuração, execução, testes e uso. Atualize .devpilot/build-game.md com critérios atendidos, comandos e evidências. Documente limitações reais sem esconder pendências e sem expor segredos.`
    },
    {
      id: 6,
      icon: '🔀',
      name: 'Git',
      xp: 100,
      summary: 'Revisar o delta e deixar a entrega versionada, auditável e reversível.',
      evidence: 'Status e diff revisados, segredos ausentes e commit/branch registrados.',
      mission: `Revise git status --short e git diff, confirme que somente arquivos da rodada foram alterados e verifique que não há credenciais ou artefatos indevidos. Use branch e commit local reversíveis conforme AGENTS.md. Registre branch, commit e diff stat em .devpilot/build-game.md. Push, PR, merge ou deploy só quando já autorizados pelas regras do projeto.`
    },
    {
      id: 7,
      icon: '🏁',
      name: 'Entrega e revisão',
      xp: 140,
      summary: 'Revisar o pedido original e entregar o fluxo funcionando no sistema.',
      evidence: 'Critérios atendidos, smoke final verde e entrega identificada por arquivos, testes e commit.',
      mission: `Faça a revisão final do objetivo literal contra cada critério de aceite em .devpilot/build-game.md. Execute smoke final como o usuário utilizará o fluxo. Revise migrações, segurança, responsividade, documentação, configuração e evidências Git. Atualize .devpilot/build-game.md com ENTREGA DA RODADA: objetivo, o que foi entregue, como testar, arquivos principais, testes, commit/PR quando houver e pendências reais.`
    }
  ];

  let selectedProjectId = localStorage.getItem(PROJECT_KEY) || '';
  let missionId = localStorage.getItem(MISSION_KEY) || '';
  let currentTasks = [];
  let controllerTimer = 0;
  let controllerBusy = false;
  const creationLocks = new Set();

  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const projectById = id => (Array.isArray(state.projects) ? state.projects : []).find(project => String(project.id) === String(id));
  const activeGoalKey = () => `${GOAL_KEY}:${selectedProjectId || 'none'}:${missionId || 'none'}`;
  const newMissionId = () => `game-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const escapeRegExp = value => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const promptValue = (task, label) => String(task?.prompt || '').match(new RegExp(`^${escapeRegExp(label)}:\\s*(.+)$`, 'mi'))?.[1]?.trim() || '';
  const phaseFromTask = task => Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  const missionFromTask = task => promptValue(task, 'PARTIDA');
  const goalFromTask = task => promptValue(task, 'OBJETIVO');
  const isGameTask = task => String(task?.prompt || '').includes(MARKER) || String(task?.title || '').startsWith('[Jogo]');
  const isVerifierTask = task => String(task?.prompt || '').includes(VERIFIER_MARKER) || String(task?.title || '').startsWith('[Jogo] Gate');
  const isPassed = task => Boolean(task) && isVerifierTask(task) && normalize(task.status) === 'completed';
  const isActive = task => ACTIVE_STATUSES.has(normalize(task?.status));
  const isFailed = task => FAILED_STATUSES.has(normalize(task?.status));
  const isAwaitingGate = task => Boolean(task) && !isVerifierTask(task) && normalize(task.status) === 'completed';
  const latestForPhase = (tasks, phaseId) => tasks.find(task => phaseFromTask(task) === phaseId);

  const installStyle = () => {
    if (document.getElementById('build-game-style-v73')) return;
    const style = document.createElement('style');
    style.id = 'build-game-style-v73';
    style.textContent = `
      .build-game-shell{display:grid;gap:14px}
      .build-game-hero,.build-game-round-contract,.build-game-score>div,.build-game-phase,.build-game-victory,.build-game-shell>article.panel{border:1px solid var(--line,#233047);border-radius:16px;background:rgba(7,17,31,.56)}
      .build-game-hero{padding:20px}.build-game-hero p,.build-game-phase p,.build-game-history-row small{color:var(--muted,#9eacc2)}
      .build-game-config{display:grid;grid-template-columns:minmax(180px,.7fr) minmax(280px,1.3fr) auto;gap:10px;margin-top:16px;align-items:end}
      .build-game-config label{display:grid;gap:6px}.build-game-config select,.build-game-config input{min-height:44px;width:100%}
      .build-game-round-contract{padding:14px}.build-game-score{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.build-game-score>div{padding:12px}
      .build-game-progress{height:10px;overflow:hidden;border-radius:999px;background:#ffffff12}.build-game-progress>i{display:block;height:100%;background:linear-gradient(90deg,#58d8ff,#68f0bb)}
      .build-game-map{display:grid;gap:9px}.build-game-phase{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:12px;align-items:center;padding:13px}.build-game-phase.locked{opacity:.5}.build-game-phase.current{border-color:#55dbe0}.build-game-phase.passed{border-color:#4bd69b}
      .build-game-phase-icon{display:grid;place-items:center;width:44px;height:44px;border-radius:13px;background:#ffffff0d}.build-game-phase-copy small{color:#65dfff}.build-game-phase-copy strong{display:block;margin:2px 0}.build-game-phase-copy p{margin:0;font-size:.8rem}.build-game-phase-actions{display:flex;gap:8px;align-items:center}
      .build-game-history-row{display:grid;grid-template-columns:1fr auto;gap:10px;padding:10px 0;border-bottom:1px solid #ffffff0d}
      @media(max-width:800px){.build-game-config{grid-template-columns:1fr}.build-game-score{grid-template-columns:1fr 1fr}.build-game-phase{grid-template-columns:44px 1fr}.build-game-phase-actions{grid-column:1/-1}}
    `;
    document.head.appendChild(style);
  };

  const ensureProjects = async () => {
    if (!Array.isArray(state.projects) || !state.projects.length) state.projects = await api('/projects');
    if (!selectedProjectId || !state.projects.some(project => String(project.id) === String(selectedProjectId))) {
      selectedProjectId = state.projects[0]?.id || '';
    }
    if (selectedProjectId) localStorage.setItem(PROJECT_KEY, selectedProjectId);
  };

  const adoptMissionFromHistory = tasks => {
    const gameTasks = (Array.isArray(tasks) ? tasks : []).filter(isGameTask).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    if (!missionId) {
      missionId = missionFromTask(gameTasks[0]) || newMissionId();
      localStorage.setItem(MISSION_KEY, missionId);
    }
    const missionTasks = gameTasks.filter(task => missionFromTask(task) === missionId);
    const historicalGoal = missionTasks.map(goalFromTask).find(Boolean);
    const storedGoal = localStorage.getItem(activeGoalKey());
    const goal = missionTasks.length ? historicalGoal : storedGoal;
    if (historicalGoal) localStorage.setItem(activeGoalKey(), historicalGoal);
    return {missionTasks, goal: goal || ''};
  };

  const gameState = tasks => {
    const byPhase = new Map(phases.map(phase => [phase.id, latestForPhase(tasks, phase.id)]));
    const current = phases.find(phase => !isPassed(byPhase.get(phase.id)))?.id || phases.length + 1;
    const passed = phases.filter(phase => isPassed(byPhase.get(phase.id))).length;
    const xp = phases.reduce((sum, phase) => sum + (isPassed(byPhase.get(phase.id)) ? phase.xp : 0), 0);
    return {byPhase, current, passed, xp, totalXp: phases.reduce((sum, phase) => sum + phase.xp, 0)};
  };

  const setGoal = value => {
    const goal = String(value || '').trim();
    if (goal) localStorage.setItem(activeGoalKey(), goal);
    else localStorage.removeItem(activeGoalKey());
  };

  const controllerGoal = () => currentTasks.map(goalFromTask).find(Boolean) || localStorage.getItem(activeGoalKey()) || '';

  const snapshot = () => {
    const game = gameState(currentTasks);
    const phase = phases.find(item => item.id === game.current) || null;
    const task = phase ? game.byPhase.get(phase.id) : null;
    return {
      projectId: String(selectedProjectId || ''),
      projectName: projectById(selectedProjectId)?.name || '',
      missionId: String(missionId || ''),
      goal: controllerGoal(),
      hasTasks: currentTasks.length > 0,
      completed: game.passed,
      total: phases.length,
      percent: Math.round(game.passed / phases.length * 100),
      done: game.passed >= phases.length,
      currentPhaseId: phase?.id || 0,
      currentPhaseName: phase?.name || 'Entrega concluída',
      currentPhaseSummary: phase?.summary || '',
      currentPhaseIcon: phase?.icon || '🏆',
      taskId: task?.id || null,
      taskStatus: normalize(task?.status),
      verifier: isVerifierTask(task),
      awaitingGate: isAwaitingGate(task),
      active: isActive(task),
      failed: isFailed(task)
    };
  };

  const emitState = () => {
    const detail = snapshot();
    document.dispatchEvent(new CustomEvent('devpilot:game:state', {detail}));
    return detail;
  };

  const buildPrompt = (phase, goal) => `${MARKER}\n${PIPELINE_MARKER}\n[DEVPILOT_MODE=develop]\nPARTIDA: ${missionId}\nFASE: ${phase.id}/${phases.length}\nOBJETIVO: ${goal}\n\nMISSÃO DA FASE: ${phase.name}\n${phase.mission}\n\nCONTRATO DE PROGRESSÃO REAL:\n- Evidência obrigatória desta etapa: ${phase.evidence}\n- Preserve o objetivo literal da rodada.\n- Registre o estado antes e depois e as verificações realmente executadas.\n- Se a evidência ou critério obrigatório estiver ausente, NÃO marque a tarefa como concluída.\n- Não avance para outra fase nesta tarefa; o controlador do jogo libera a próxima somente após o gate independente.\n\nCRITÉRIO DE VITÓRIA:\nA rodada só termina após as sete etapas, cada uma aprovada pelo gate independente, e a entrega final do pedido do usuário.`;

  const render = (missionTasks, initialGoal) => {
    const view = document.getElementById('build-game-view');
    if (!view) return;
    currentTasks = missionTasks;
    const game = gameState(missionTasks);
    const project = projectById(selectedProjectId);
    const goalLocked = missionTasks.length > 0;
    const goal = goalLocked ? (initialGoal || '') : (localStorage.getItem(activeGoalKey()) || initialGoal || '');
    const percent = Math.round(game.passed / phases.length * 100);
    const projectOptions = (state.projects || []).map(item => `<option value="${esc(item.id)}" ${String(item.id) === String(selectedProjectId) ? 'selected' : ''}>${esc(item.name)}</option>`).join('') || '<option value="">Nenhum projeto cadastrado</option>';
    const phaseCards = phases.map(phase => {
      const task = game.byPhase.get(phase.id);
      const passed = isPassed(task);
      const current = phase.id === game.current;
      const awaitingGate = isAwaitingGate(task);
      const failed = isFailed(task);
      const locked = phase.id > game.current;
      const className = passed ? 'passed' : locked ? 'locked' : current ? 'current' : '';
      let action = '<span>🔒 etapa anterior</span>';
      if (passed) action = '<span class="status completed">aprovada</span>';
      else if (current && awaitingGate) action = '<span class="status review">validando entrega</span>';
      else if (current && isVerifierTask(task) && isActive(task)) action = '<span class="status review">gate em execução</span>';
      else if (current && isActive(task)) action = `<span>${status(task.status)}</span>`;
      else if (current && failed) action = '<span class="status failed">falhou</span>';
      else if (current && !task) action = '<span class="status queued">preparando</span>';
      return `<article class="build-game-phase ${className}"><div class="build-game-phase-icon">${phase.icon}</div><div class="build-game-phase-copy"><small>ETAPA ${phase.id}/${phases.length}</small><strong>${esc(phase.name)}</strong><p>${esc(phase.summary)}</p></div><div class="build-game-phase-actions">${action}</div></article>`;
    }).join('');
    const history = missionTasks.slice(0, 10).map(task => `<div class="build-game-history-row"><div><strong>${esc(task.title)}</strong><small>${new Date(task.created_at).toLocaleString('pt-BR')}</small></div>${status(task.status)}</div>`).join('') || '<div class="empty">A rodada ainda não começou.</div>';

    view.innerHTML = `<div class="build-game-shell"><section class="build-game-hero"><span class="eyebrow">MODO JOGO · ESTEIRA REAL</span><h2>Jogo de construção</h2><p>Uma rodada, uma entrega. O fluxo técnico permanece rastreável em detalhes.</p><div class="build-game-config"><label>Projeto<select id="build-game-project" ${goalLocked ? 'disabled' : ''}>${projectOptions}</select></label><label>Entrega da rodada<input id="build-game-goal" maxlength="500" value="${esc(goal)}" ${goalLocked ? 'readonly' : ''}></label><button class="ghost" type="button" id="build-game-new">Nova rodada</button></div></section><section class="build-game-round-contract"><span>Entrega</span><strong>${esc(goal || 'Defina a entrega da rodada')}</strong></section><section class="build-game-score"><div><span>Progresso</span><strong>${game.passed}/${phases.length}</strong></div><div><span>XP</span><strong>${game.xp}/${game.totalXp}</strong></div><div><span>Projeto</span><strong>${esc(project?.name || '—')}</strong></div></section><div class="build-game-progress"><i style="width:${percent}%"></i></div>${game.passed === phases.length ? `<section class="build-game-victory"><h3>🏆 Entrega concluída</h3><p>${esc(goal)}</p></section>` : ''}<section class="build-game-map">${phaseCards}</section><article class="panel"><div class="panel-title"><h3>Detalhes da esteira</h3></div><div class="build-game-history">${history}</div></article></div>`;

    const projectSelect = view.querySelector('#build-game-project');
    projectSelect?.addEventListener('change', async event => {
      selectedProjectId = event.target.value;
      localStorage.setItem(PROJECT_KEY, selectedProjectId);
      missionId = '';
      localStorage.removeItem(MISSION_KEY);
      await window.loadBuildGame();
    });
    const goalInput = view.querySelector('#build-game-goal');
    if (goalInput && !goalLocked) {
      goalInput.oninput = () => setGoal(goalInput.value);
      goalInput.onchange = () => setGoal(goalInput.value);
    }
    view.querySelector('#build-game-new')?.addEventListener('click', () => void window.__devpilotGameControllerV73?.reset());
  };

  const createPhaseTask = async (phaseId, goal, {force = false} = {}) => {
    const phase = phases.find(item => item.id === phaseId);
    if (!phase) throw new Error('Etapa inválida');
    const cleanGoal = String(goal || '').trim();
    if (!cleanGoal) throw new Error('Descreva a entrega da rodada');
    const key = `${missionId}:${phaseId}:base`;
    if (creationLocks.has(key)) return null;
    if (!force && latestForPhase(currentTasks, phaseId)) return latestForPhase(currentTasks, phaseId);
    creationLocks.add(key);
    try {
      return await api('/tasks', {
        method: 'POST',
        body: JSON.stringify({
          project_id: selectedProjectId,
          title: `[Jogo] Etapa ${phase.id} · ${phase.name}`,
          prompt: buildPrompt(phase, cleanGoal),
          source: 'dashboard',
          priority: Math.min(100, 68 + phase.id * 5),
          requires_approval: false
        })
      });
    } finally {
      creationLocks.delete(key);
    }
  };

  window.loadBuildGame = async () => {
    try {
      await ensureProjects();
      if (!selectedProjectId) {
        render([], '');
        window.__devpilotGameLoadError = null;
        document.dispatchEvent(new CustomEvent('devpilot:game:rendered', {detail:{source:'build-game', empty:true}}));
        emitState();
        return {missionTasks: [], goal: ''};
      }
      const tasks = await api(`/tasks?project_id=${encodeURIComponent(selectedProjectId)}&limit=500`);
      const result = adoptMissionFromHistory(tasks);
      render(result.missionTasks, result.goal);
      window.__devpilotGameLoadError = null;
      document.dispatchEvent(new CustomEvent('devpilot:game:rendered', {detail:{source:'build-game', missionId}}));
      emitState();
      return result;
    } catch (error) {
      const failure = error instanceof Error ? error : new Error(String(error || 'Falha ao carregar o jogo'));
      window.__devpilotGameLoadError = failure;
      toast(failure.message);
      document.dispatchEvent(new CustomEvent('devpilot:game:error', {detail:{message:failure.message}}));
      throw failure;
    }
  };

  const refreshAndAdvance = async () => {
    if (controllerBusy) return snapshot();
    controllerBusy = true;
    try {
      await window.loadBuildGame();
      let stateNow = snapshot();
      if (stateNow.done || stateNow.failed) return emitState();

      if (stateNow.awaitingGate && typeof window.__devpilotEnsureDeliveryGate === 'function') {
        const created = await window.__devpilotEnsureDeliveryGate();
        if (created) {
          await window.loadBuildGame();
          stateNow = snapshot();
        }
      }

      if (!stateNow.done && !stateNow.failed && stateNow.currentPhaseId && !stateNow.taskId) {
        const goal = controllerGoal();
        if (goal) {
          await createPhaseTask(stateNow.currentPhaseId, goal);
          await window.loadBuildGame();
          stateNow = snapshot();
        }
      }
      return emitState();
    } finally {
      controllerBusy = false;
    }
  };

  const schedule = () => {
    window.clearTimeout(controllerTimer);
    const stateNow = snapshot();
    if (!stateNow.missionId || !stateNow.hasTasks || stateNow.done || stateNow.failed) {
      controllerTimer = 0;
      return;
    }
    controllerTimer = window.setTimeout(async () => {
      try { await refreshAndAdvance(); }
      catch (error) { console.error('[DevPilot Game Controller]', error); }
      finally { schedule(); }
    }, document.hidden ? 12000 : 5000);
  };

  const startRound = async ({projectId, goal} = {}) => {
    await ensureProjects();
    const targetProject = String(projectId || selectedProjectId || '').trim();
    const targetGoal = String(goal || '').trim();
    if (!targetProject) throw new Error('Escolha um projeto');
    if (!targetGoal) throw new Error('Descreva a entrega da rodada');
    if (!(state.projects || []).some(project => String(project.id) === targetProject)) throw new Error('Projeto selecionado não encontrado');

    selectedProjectId = targetProject;
    localStorage.setItem(PROJECT_KEY, selectedProjectId);
    missionId = newMissionId();
    localStorage.setItem(MISSION_KEY, missionId);
    currentTasks = [];
    setGoal(targetGoal);
    emitState();

    await createPhaseTask(1, targetGoal, {force:true});
    await window.loadBuildGame();
    schedule();
    return emitState();
  };

  const retry = async () => {
    const stateNow = snapshot();
    if (!stateNow.failed || !stateNow.currentPhaseId) return stateNow;
    if (stateNow.verifier && typeof window.__devpilotEnsureDeliveryGate === 'function') {
      await window.__devpilotEnsureDeliveryGate({retryFailed:true});
    } else {
      await createPhaseTask(stateNow.currentPhaseId, stateNow.goal, {force:true});
    }
    await window.loadBuildGame();
    schedule();
    return emitState();
  };

  const reset = async () => {
    window.clearTimeout(controllerTimer);
    controllerTimer = 0;
    if (missionId) localStorage.removeItem(activeGoalKey());
    missionId = newMissionId();
    localStorage.setItem(MISSION_KEY, missionId);
    currentTasks = [];
    render([], '');
    document.dispatchEvent(new CustomEvent('devpilot:game:rendered', {detail:{source:'controller-reset'}}));
    return emitState();
  };

  window.__devpilotGameControllerV73 = {version:'v73', snapshot, emit:emitState, startRound, refresh:refreshAndAdvance, retry, reset, schedule};

  const openGame = async projectId => {
    if (projectId) {
      selectedProjectId = String(projectId);
      localStorage.setItem(PROJECT_KEY, selectedProjectId);
      missionId = '';
      localStorage.removeItem(MISSION_KEY);
    }
    showView('build-game');
    await window.loadBuildGame();
  };

  const createUi = () => {
    installStyle();
    const nav = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!nav || !main) return;
    let button = nav.querySelector('[data-view="build-game"]');
    if (!button) {
      button = document.createElement('button');
      button.className = 'nav';
      button.type = 'button';
      button.dataset.view = 'build-game';
      button.textContent = '🎮 Jogo';
      nav.appendChild(button);
    }
    let view = document.getElementById('build-game-view');
    if (!view) {
      view = document.createElement('section');
      view.className = 'view';
      view.id = 'build-game-view';
      main.appendChild(view);
    }
    button.onclick = () => openGame();
  };

  document.addEventListener('devpilot:game:core-ready', schedule);
  document.addEventListener('visibilitychange', schedule);

  const boot = () => {
    if (typeof state === 'undefined' || typeof api !== 'function' || typeof showView !== 'function') return window.setTimeout(boot, 50);
    createUi();
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();
})();
