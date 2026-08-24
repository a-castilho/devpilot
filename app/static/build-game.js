/* DevPilot Build Game: gamified, project-scoped delivery with real task gates. */
(() => {
  'use strict';

  const MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const GOAL_KEY = 'devpilot-build-game-goal';
  const ACTIVE_STATUSES = new Set(['awaiting_approval', 'queued', 'running', 'review', 'blocked']);

  const phases = [
    {
      id: 1,
      icon: '🗺️',
      name: 'Mapa da missão',
      xp: 100,
      summary: 'Entender o sistema, definir vitória e deixar a base verificável.',
      mission: `Leia AGENTS.md, documentação e o repositório antes de agir. Transforme o objetivo da partida em critérios de aceite objetivos e registre o plano em .devpilot/build-game.md. Detecte a stack, os comandos reais de instalação, build, lint e testes. Execute uma verificação de baseline. Se houver bloqueios que impeçam a missão, corrija somente o necessário e repita a verificação. Não invente resultado nem marque sucesso sem evidência executada.`
    },
    {
      id: 2,
      icon: '⚙️',
      name: 'Primeiro circuito',
      xp: 120,
      summary: 'Construir a menor fatia funcional de ponta a ponta.',
      mission: `Implemente a menor fatia vertical realmente utilizável que avance o objetivo da partida. Reutilize a arquitetura e padrões do projeto. Inclua ou atualize testes automáticos para o comportamento criado. Execute os testes relevantes e o smoke mínimo. Não altere requisitos só para fazer o teste passar; corrija a implementação quando houver falha.`
    },
    {
      id: 3,
      icon: '🛡️',
      name: 'Regras blindadas',
      xp: 140,
      summary: 'Fechar regras de negócio, limites de acesso e cenários negativos.',
      mission: `Implemente as regras de negócio restantes para o objetivo da partida e valide fronteiras de autorização, autenticação, isolamento de dados e validação de entrada quando existirem no sistema. Crie testes positivos e negativos. Não exponha segredos, não use credenciais reais em fixtures e não introduza bypass para satisfazer testes.`
    },
    {
      id: 4,
      icon: '🎮',
      name: 'Interface jogável',
      xp: 160,
      summary: 'Deixar o fluxo principal claro, utilizável e resistente a erro.',
      mission: `Finalize a experiência do fluxo principal relacionado ao objetivo: interface web/mobile ou contrato de API, conforme a stack real. Cubra carregamento, vazio, sucesso e erro; preserve acessibilidade e responsividade quando houver UI. Rode testes de interface/API existentes e adicione cobertura para o fluxo alterado. Não apresente dados fictícios como reais.`
    },
    {
      id: 5,
      icon: '🧪',
      name: 'Batalha de testes',
      xp: 180,
      summary: 'Enfrentar a suíte completa e corrigir falhas reais.',
      mission: `Execute a suíte completa aplicável ao projeto: testes unitários, integração, sistema/smoke, lint, typecheck e build quando existirem. Corrija as falhas causadas ou expostas pela implementação desta partida e repita os comandos até obter evidência real. Não silencie testes, não remova asserts válidos, não use fallback que transforme falha em sucesso e não declare aprovação de comando que não foi executado.`
    },
    {
      id: 6,
      icon: '🏁',
      name: 'Chefe final',
      xp: 200,
      summary: 'Validar prontidão de entrega e encerrar a missão com evidência.',
      mission: `Faça a revisão final do objetivo da partida contra os critérios de aceite registrados em .devpilot/build-game.md. Execute build e smoke final; revise migrações, configuração, segurança, documentação e deploy quando aplicáveis. Corrija regressões encontradas e repita a validação. Atualize .devpilot/build-game.md com evidências finais e pendências reais. A missão só vence se os critérios de aceite estiverem atendidos e as verificações aplicáveis estiverem aprovadas.`
    }
  ];

  let selectedProjectId = localStorage.getItem(PROJECT_KEY) || '';
  let missionId = localStorage.getItem(MISSION_KEY) || '';
  let currentTasks = [];

  const normalize = value => String(value || '').toLowerCase().replaceAll(' ', '_');
  const projectById = id => (Array.isArray(state.projects) ? state.projects : []).find(p => String(p.id) === String(id));
  const activeGoalKey = () => `${GOAL_KEY}:${selectedProjectId || 'none'}:${missionId || 'none'}`;
  const newMissionId = () => `game-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const escapeRegExp = value => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  const promptValue = (task, label) => {
    const match = String(task?.prompt || '').match(new RegExp(`^${escapeRegExp(label)}:\\s*(.+)$`, 'mi'));
    return match?.[1]?.trim() || '';
  };

  const phaseFromTask = task => Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  const missionFromTask = task => promptValue(task, 'PARTIDA');
  const goalFromTask = task => promptValue(task, 'OBJETIVO');
  const isGameTask = task => String(task?.prompt || '').includes(MARKER);

  const installStyle = () => {
    if (document.querySelector('#build-game-style')) return;
    const style = document.createElement('style');
    style.id = 'build-game-style';
    style.textContent = `
      .build-game-shell{display:grid;gap:16px}
      .build-game-hero{position:relative;overflow:hidden;padding:22px;border:1px solid rgba(94,234,212,.22);border-radius:20px;background:radial-gradient(circle at 88% 10%,rgba(93,199,255,.16),transparent 34%),linear-gradient(145deg,rgba(8,24,39,.96),rgba(7,15,29,.98))}
      .build-game-hero:after{content:'XP';position:absolute;right:22px;top:14px;font-size:clamp(3.5rem,10vw,8rem);font-weight:900;color:rgba(255,255,255,.025);pointer-events:none}
      .build-game-hero h2{margin:5px 0 8px;font-size:clamp(1.55rem,4vw,2.45rem)}
      .build-game-hero p{max-width:760px;margin:0;color:var(--muted,#9eacc2)}
      .build-game-config{display:grid;grid-template-columns:minmax(180px,.7fr) minmax(280px,1.3fr) auto;gap:10px;margin-top:18px;align-items:end}
      .build-game-config label{display:grid;gap:6px;font-size:.76rem;color:var(--muted,#9eacc2)}
      .build-game-config select,.build-game-config input{min-height:44px;width:100%}
      .build-game-score{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
      .build-game-score>div{padding:14px;border:1px solid var(--line,#233047);border-radius:14px;background:rgba(7,17,31,.56)}
      .build-game-score span{display:block;font-size:.68rem;color:var(--muted,#9eacc2);text-transform:uppercase;letter-spacing:.08em}
      .build-game-score strong{display:block;margin-top:4px;font-size:1.4rem}
      .build-game-progress{height:10px;overflow:hidden;border-radius:999px;background:rgba(255,255,255,.07)}
      .build-game-progress>i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#58d8ff,#68f0bb);transition:width .25s ease}
      .build-game-map{display:grid;gap:10px}
      .build-game-phase{display:grid;grid-template-columns:52px minmax(0,1fr) auto;gap:13px;align-items:center;padding:14px;border:1px solid var(--line,#233047);border-radius:16px;background:rgba(7,17,31,.48)}
      .build-game-phase.current{border-color:rgba(91,224,255,.58);box-shadow:0 0 0 1px rgba(91,224,255,.08),0 12px 30px rgba(0,0,0,.16)}
      .build-game-phase.passed{border-color:rgba(104,240,187,.3)}
      .build-game-phase.locked{opacity:.52}
      .build-game-phase-icon{display:grid;place-items:center;width:46px;height:46px;border-radius:14px;background:rgba(255,255,255,.05);font-size:1.35rem}
      .build-game-phase-copy{min-width:0}.build-game-phase-copy small{display:block;color:#65dfff;font-size:.68rem;font-weight:800;letter-spacing:.08em}.build-game-phase-copy strong{display:block;margin:3px 0;font-size:1rem}.build-game-phase-copy p{margin:0;color:var(--muted,#9eacc2);font-size:.78rem}
      .build-game-phase-actions{display:flex;align-items:center;gap:8px;justify-content:flex-end}.build-game-phase-actions button{min-width:120px}.build-game-lock{font-size:.74rem;color:var(--muted,#9eacc2)}
      .build-game-history{display:grid;gap:8px}.build-game-history-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;padding:11px 0;border-bottom:1px solid rgba(255,255,255,.06)}.build-game-history-row:last-child{border-bottom:0}.build-game-history-row small{display:block;color:var(--muted,#9eacc2);margin-top:3px}
      .build-game-victory{padding:18px;border:1px solid rgba(104,240,187,.34);border-radius:16px;background:linear-gradient(135deg,rgba(31,110,86,.22),rgba(7,17,31,.62))}.build-game-victory h3{margin:4px 0 7px}.build-game-victory p{margin:0;color:var(--muted,#9eacc2)}
      @media(max-width:800px){.build-game-config{grid-template-columns:1fr}.build-game-score{grid-template-columns:1fr 1fr}.build-game-score>div:last-child{grid-column:1/-1}.build-game-phase{grid-template-columns:44px minmax(0,1fr)}.build-game-phase-actions{grid-column:1/-1;justify-content:stretch}.build-game-phase-actions button{width:100%}}
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
    const gameTasks = tasks.filter(isGameTask).sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    if (!missionId) {
      missionId = missionFromTask(gameTasks[0]) || newMissionId();
      localStorage.setItem(MISSION_KEY, missionId);
    }
    const missionTasks = gameTasks.filter(task => missionFromTask(task) === missionId);
    const storedGoal = localStorage.getItem(activeGoalKey());
    const historicalGoal = missionTasks.map(goalFromTask).find(Boolean);
    const projectGoal = projectById(selectedProjectId)?.description || '';
    return {missionTasks, goal: storedGoal || historicalGoal || projectGoal};
  };

  const latestForPhase = (tasks, phaseId) => tasks.find(task => phaseFromTask(task) === phaseId);
  const isPassed = task => normalize(task?.status) === 'completed';
  const isActive = task => ACTIVE_STATUSES.has(normalize(task?.status));

  const gameState = tasks => {
    const byPhase = new Map(phases.map(phase => [phase.id, latestForPhase(tasks, phase.id)]));
    const current = phases.find(phase => !isPassed(byPhase.get(phase.id)))?.id || phases.length + 1;
    const passed = phases.filter(phase => isPassed(byPhase.get(phase.id))).length;
    const xp = phases.reduce((sum, phase) => sum + (isPassed(byPhase.get(phase.id)) ? phase.xp : 0), 0);
    const totalXp = phases.reduce((sum, phase) => sum + phase.xp, 0);
    return {byPhase, current, passed, xp, totalXp};
  };

  const setGoal = value => {
    const goal = String(value || '').trim();
    if (goal) localStorage.setItem(activeGoalKey(), goal);
    else localStorage.removeItem(activeGoalKey());
  };

  const render = (missionTasks, initialGoal) => {
    const view = document.querySelector('#build-game-view');
    if (!view) return;
    currentTasks = missionTasks;
    const game = gameState(missionTasks);
    const project = projectById(selectedProjectId);
    const percent = Math.round(game.passed / phases.length * 100);
    const goal = localStorage.getItem(activeGoalKey()) || initialGoal || '';

    const projectOptions = (state.projects || []).map(item =>
      `<option value="${esc(item.id)}" ${String(item.id) === String(selectedProjectId) ? 'selected' : ''}>${esc(item.name)}</option>`
    ).join('') || '<option value="">Nenhum projeto cadastrado</option>';

    const phaseCards = phases.map(phase => {
      const task = game.byPhase.get(phase.id);
      const passed = isPassed(task);
      const active = isActive(task);
      const unlocked = phase.id <= game.current;
      const failed = ['failed', 'cancelled'].includes(normalize(task?.status));
      const className = passed ? 'passed' : (!unlocked ? 'locked' : phase.id === game.current ? 'current' : '');
      let action = '<span class="build-game-lock">🔒 Conclua a fase anterior</span>';
      if (passed) action = `<span>${status('completed')}</span>`;
      else if (unlocked && active) action = `<span>${status(task.status)}</span><button class="ghost" type="button" data-game-refresh>Atualizar</button>`;
      else if (unlocked) action = `<button class="primary" type="button" data-play-phase="${phase.id}">${failed ? '↻ Tentar novamente' : '▶ Jogar fase'}</button>`;
      return `<article class="build-game-phase ${className}">
        <div class="build-game-phase-icon" aria-hidden="true">${phase.icon}</div>
        <div class="build-game-phase-copy"><small>FASE ${phase.id}/${phases.length} · +${phase.xp} XP</small><strong>${esc(phase.name)}</strong><p>${esc(phase.summary)}</p></div>
        <div class="build-game-phase-actions">${action}</div>
      </article>`;
    }).join('');

    const history = missionTasks.slice(0, 8).map(task =>
      `<div class="build-game-history-row"><div><strong>Fase ${phaseFromTask(task)} · ${esc(task.title)}</strong><small>${new Date(task.created_at).toLocaleString('pt-BR')}</small></div>${status(task.status)}</div>`
    ).join('') || '<div class="empty">A partida começa quando você jogar a primeira fase.</div>';

    view.innerHTML = `<div class="build-game-shell">
      <section class="build-game-hero">
        <span class="eyebrow">DEV + TESTE · PROGRESSÃO REAL</span>
        <h2>Jogo de construção</h2>
        <p>Construa um sistema por fases. Cada fase cria uma tarefa real no DevPilot, exige validação e só libera a próxima quando a execução anterior termina como concluída.</p>
        <div class="build-game-config">
          <label>Projeto<select id="build-game-project">${projectOptions}</select></label>
          <label>Objetivo da partida<input id="build-game-goal" maxlength="500" value="${esc(goal)}" placeholder="Ex.: criar cadastro de clientes com login e testes"></label>
          <button class="ghost" type="button" id="build-game-new">Nova partida</button>
        </div>
      </section>

      <section class="build-game-score" aria-label="Placar da partida">
        <div><span>Progresso</span><strong>${game.passed}/${phases.length} fases</strong></div>
        <div><span>Experiência</span><strong>${game.xp}/${game.totalXp} XP</strong></div>
        <div><span>Projeto</span><strong>${esc(project?.name || '—')}</strong></div>
      </section>
      <div class="build-game-progress" aria-label="${percent}% concluído"><i style="width:${percent}%"></i></div>

      ${game.passed === phases.length ? `<section class="build-game-victory"><span class="eyebrow">MISSÃO CONCLUÍDA</span><h3>🏆 Sistema passou pelo chefe final</h3><p>${esc(goal || 'Objetivo da partida')} · ${game.totalXp} XP conquistados. O histórico técnico permanece nas tarefas e no repositório.</p></section>` : ''}

      <section class="build-game-map">${phaseCards}</section>

      <article class="panel">
        <div class="panel-title"><div><span class="eyebrow">LOG DA PARTIDA</span><h3>Últimas jogadas</h3></div><button class="link" type="button" data-game-refresh>Atualizar</button></div>
        <div class="build-game-history">${history}</div>
      </article>
    </div>`;

    const projectSelect = view.querySelector('#build-game-project');
    if (projectSelect) projectSelect.onchange = async event => {
      selectedProjectId = event.target.value;
      localStorage.setItem(PROJECT_KEY, selectedProjectId);
      missionId = '';
      localStorage.removeItem(MISSION_KEY);
      await window.loadBuildGame();
    };

    const goalInput = view.querySelector('#build-game-goal');
    if (goalInput) {
      goalInput.onchange = () => setGoal(goalInput.value);
      goalInput.oninput = () => setGoal(goalInput.value);
    }

    view.querySelector('#build-game-new')?.addEventListener('click', () => {
      if (missionTasks.length && !window.confirm('Começar uma nova partida? O histórico atual será preservado nas tarefas.')) return;
      missionId = newMissionId();
      localStorage.setItem(MISSION_KEY, missionId);
      localStorage.removeItem(activeGoalKey());
      window.loadBuildGame();
    });

    view.querySelectorAll('[data-game-refresh]').forEach(button => button.onclick = () => window.loadBuildGame());
    view.querySelectorAll('[data-play-phase]').forEach(button => {
      button.onclick = () => playPhase(Number(button.dataset.playPhase), button);
    });
  };

  const buildPrompt = (phase, goal) => `${MARKER}
[DEVPILOT_MODE=develop]
PARTIDA: ${missionId}
FASE: ${phase.id}/${phases.length}
OBJETIVO: ${goal}

MISSÃO DA FASE: ${phase.name}
${phase.mission}

REGRAS DO JOGO:
- Trabalhe somente no projeto selecionado e respeite AGENTS.md e as regras do repositório.
- Antes de alterar, inspecione o estado atual e preserve mudanças válidas existentes.
- Implemente de verdade; não substitua comportamento real por dados falsos, mocks indevidos ou respostas simuladas.
- Use Git de forma reversível e nunca force push na branch principal.
- Execute as verificações aplicáveis desta fase e registre comandos e evidências no resultado.
- Se uma verificação obrigatória falhar, corrija e execute novamente. Se não for possível corrigir com segurança, reporte a falha claramente; não invente aprovação.
- Não avance para outra fase nesta tarefa. A próxima fase será liberada pelo Jogo de construção somente após esta tarefa ficar concluída.

CRITÉRIO DE VITÓRIA:
A fase termina somente quando a entrega descrita acima existe no repositório e as verificações aplicáveis foram executadas sem falhas não resolvidas.`;

  const playPhase = async (phaseId, button) => {
    const phase = phases.find(item => item.id === phaseId);
    if (!phase) return;
    await ensureProjects();
    const game = gameState(currentTasks);
    if (phaseId !== game.current) return toast('Conclua a fase atual antes de avançar');
    const goalInput = document.querySelector('#build-game-goal');
    const goal = String(goalInput?.value || '').trim();
    if (!goal) {
      goalInput?.focus();
      return toast('Defina o objetivo da partida');
    }
    setGoal(goal);
    if (!missionId) {
      missionId = newMissionId();
      localStorage.setItem(MISSION_KEY, missionId);
    }
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Iniciando…';
    try {
      const task = await api('/tasks', {
        method: 'POST',
        body: JSON.stringify({
          project_id: selectedProjectId,
          title: `[Jogo] Fase ${phase.id} · ${phase.name}`,
          prompt: buildPrompt(phase, goal),
          source: 'dashboard',
          priority: Math.min(100, 68 + phase.id * 5),
          requires_approval: false
        })
      });
      toast(`Fase ${phase.id} iniciada · ${phase.xp} XP em jogo`);
      await window.loadBuildGame();
      if (typeof load === 'function') load();
      return task;
    } catch (error) {
      toast(error.message);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  };

  window.loadBuildGame = async () => {
    try {
      await ensureProjects();
      if (!selectedProjectId) return render([], '');
      const tasks = await api(`/tasks?project_id=${encodeURIComponent(selectedProjectId)}&limit=500`);
      const {missionTasks, goal} = adoptMissionFromHistory(tasks);
      render(missionTasks, goal);
    } catch (error) {
      toast(error.message);
    }
  };

  const openGame = async projectId => {
    if (projectId) {
      selectedProjectId = String(projectId);
      localStorage.setItem(PROJECT_KEY, selectedProjectId);
      missionId = '';
      localStorage.removeItem(MISSION_KEY);
    }
    showView('build-game');
    const title = document.querySelector('#page-title');
    if (title) title.textContent = 'Jogo de construção';
    await window.loadBuildGame();
  };

  const enhanceProjectCards = () => {
    document.querySelectorAll('#projects-list [data-project-task]').forEach(taskButton => {
      const actions = taskButton.parentElement;
      if (!actions || actions.querySelector('[data-project-build-game]')) return;
      const button = document.createElement('button');
      button.className = 'link';
      button.type = 'button';
      button.dataset.projectBuildGame = taskButton.dataset.projectTask;
      button.textContent = 'Jogar';
      button.onclick = () => openGame(button.dataset.projectBuildGame);
      actions.insertBefore(button, taskButton);
    });
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
      button.textContent = '🎮 Jogo de construção';
      const providers = nav.querySelector('[data-view="providers"]');
      nav.insertBefore(button, providers || null);
    }

    let view = document.querySelector('#build-game-view');
    if (!view) {
      view = document.createElement('section');
      view.className = 'view';
      view.id = 'build-game-view';
      const tasksView = document.querySelector('#tasks-view');
      if (tasksView) tasksView.insertAdjacentElement('afterend', view);
      else main.appendChild(view);
    }

    button.onclick = () => openGame();
    enhanceProjectCards();
    const projects = document.querySelector('#projects-list');
    if (projects) new MutationObserver(enhanceProjectCards).observe(projects, {childList: true, subtree: true});
  };

  const boot = () => {
    if (typeof state === 'undefined' || typeof api !== 'function' || typeof showView !== 'function') return setTimeout(boot, 50);
    createUi();
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
