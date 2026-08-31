/* DevPilot Build Game: gamified, project-scoped delivery with real task gates. */
(() => {
  'use strict';

  const MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const PIPELINE_MARKER = '[DEVPILOT_BUILD_GAME_PIPELINE_V2]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const GOAL_KEY = 'devpilot-build-game-goal';
  const ACTIVE_STATUSES = new Set(['awaiting_approval', 'queued', 'running', 'review', 'blocked']);

  const phases = [
    {
      id: 1,
      icon: '🧭',
      name: 'Planejamento',
      xp: 100,
      summary: 'Transformar o pedido da rodada em plano e critérios de aceite verificáveis.',
      evidence: 'Plano persistido, baseline executado e critérios de aceite ligados ao pedido da rodada.',
      mission: `Leia AGENTS.md, a documentação e o repositório antes de agir. Preserve literalmente o objetivo informado pelo usuário e transforme-o em critérios de aceite objetivos, incluindo regras de negócio, perfis de acesso, fluxos, estados de erro e limites de segurança aplicáveis. Registre o contrato da rodada em .devpilot/build-game.md com: objetivo, estado inicial, escopo, fora de escopo, critérios de aceite, riscos, arquivos prováveis e comandos reais de instalação, execução, lint, build e testes. Execute a verificação de baseline. Não implemente a funcionalidade nesta etapa e não invente resultado.`
    },
    {
      id: 2,
      icon: '⚙️',
      name: 'Implementação',
      xp: 220,
      summary: 'Construir no projeto a funcionalidade completa descrita pelo usuário.',
      evidence: 'Delta funcional real no repositório, ligado a todos os critérios de aceite aplicáveis.',
      mission: `Implemente no projeto selecionado a funcionalidade descrita no objetivo da rodada e no contrato .devpilot/build-game.md. Entregue uma fatia vertical completa e utilizável, cobrindo modelo de dados, backend, frontend, autorização, validações, migrações e configuração quando aplicáveis. No exemplo de login e senha por perfil, isso inclui armazenamento seguro da senha, autenticação, sessão, perfis, autorização por perfil, telas ou contratos de API e cenários de erro. Reutilize a arquitetura do projeto. Esta etapa NÃO pode terminar apenas com análise, relatório, URL, deploy existente ou validação do estado atual: precisa haver mudança material que altere o comportamento observável. Registre o delta com git status --short e git diff --stat e relacione cada mudança aos critérios de aceite. Se a implementação pedida estiver parcial, mantenha a etapa incompleta ou bloqueada.`
    },
    {
      id: 3,
      icon: '▶️',
      name: 'Execução',
      xp: 100,
      summary: 'Subir o sistema real e provar que o novo fluxo pode ser utilizado.',
      evidence: 'Comandos de execução, migrações, health check e smoke do fluxo real com resultado registrado.',
      mission: `Execute o sistema pela forma oficial do repositório, aplique migrações e gere build quando aplicável. Verifique health check, logs e o fluxo principal da funcionalidade da rodada com dados de teste seguros. Corrija erros de inicialização, integração ou runtime encontrados e repita a execução. Registre os comandos realmente executados, os serviços envolvidos e o resultado observável. Esta etapa pode ser concluída sem novo delta somente quando a implementação da etapa anterior executa corretamente e há evidência real de runtime; uma mensagem simulada não conta.`
    },
    {
      id: 4,
      icon: '🧪',
      name: 'Testes',
      xp: 160,
      summary: 'Validar critérios de aceite, regressões, segurança e cenários negativos.',
      evidence: 'Testes focados e suíte aplicável verdes, com comandos e resultados reais.',
      mission: `Crie ou atualize testes automáticos que provem os critérios de aceite da rodada. Cubra caminho feliz, validações, falhas, autorização, isolamento de dados e regressões aplicáveis; para UI, valide o fluxo responsivo e acessível. Execute testes unitários, integração, browser/sistema, lint, typecheck e build existentes conforme a stack. Corrija falhas e repita até ficar verde. Não silencie testes, não remova asserts válidos e não use fallback que transforme falha em sucesso. Se uma verificação obrigatória continuar falhando, a etapa não pode ser concluída.`
    },
    {
      id: 5,
      icon: '📚',
      name: 'Documentação',
      xp: 80,
      summary: 'Registrar uso, decisões, configuração e evidências da funcionalidade entregue.',
      evidence: 'Documentação atualizada e contrato da rodada com critérios e resultados rastreáveis.',
      mission: `Atualize a documentação do projeto para explicar a funcionalidade da rodada, como configurar, executar, testar e usar, quais perfis ou permissões existem e quais decisões técnicas foram tomadas. Atualize .devpilot/build-game.md com os critérios atendidos, comandos e evidências das etapas anteriores. Documente limitações reais sem esconder pendências. Não exponha segredos, tokens ou valores brutos de ambiente. A documentação deve permitir que outra pessoa valide a entrega.`
    },
    {
      id: 6,
      icon: '🔀',
      name: 'Git',
      xp: 100,
      summary: 'Revisar o delta e deixar a entrega versionada, auditável e reversível.',
      evidence: 'Status e diff revisados, segredos ausentes e commit/branch registrados; push ou PR somente com autorização.',
      mission: `Revise git status --short e git diff, confirme que somente arquivos da rodada foram alterados e verifique que não há credenciais ou artefatos indevidos. Use branch e commit local reversíveis conforme AGENTS.md, com mensagem que descreva a entrega. Registre branch, commit e diff stat em .devpilot/build-game.md. Push, Pull Request, merge ou deploy só podem ocorrer quando já autorizados pelas regras do projeto; se a autorização externa for necessária, pare de forma segura e informe exatamente o gate. Não force push e não reescreva mudanças válidas existentes.`
    },
    {
      id: 7,
      icon: '🏁',
      name: 'Entrega e revisão',
      xp: 140,
      summary: 'Revisar o pedido original e entregar o fluxo funcionando no sistema.',
      evidence: 'Todos os critérios atendidos, smoke final verde e entrega identificada por arquivos, testes, commit e URL quando aplicável.',
      mission: `Faça a revisão final do objetivo literal da rodada contra cada critério de aceite registrado em .devpilot/build-game.md. Execute o smoke final do fluxo como o usuário o utilizará, revise migrações, segurança, responsividade, documentação, configuração e evidências Git. Corrija regressões encontradas e repita a validação. Atualize .devpilot/build-game.md com uma seção ENTREGA DA RODADA contendo: objetivo recebido, o que foi entregue no sistema, como testar, arquivos principais, testes executados, commit/PR quando houver e pendências reais. A rodada só vence se a funcionalidade descrita pelo usuário existir de ponta a ponta e todos os critérios estiverem atendidos. URL pública é evidência adicional e nunca substitui implementação ausente.`
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
  const isGameTask = task => {
    const prompt = String(task?.prompt || '');
    return prompt.includes(MARKER) && prompt.includes(PIPELINE_MARKER);
  };

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
      .build-game-config input[readonly]{border-color:rgba(104,240,187,.25);background:rgba(12,42,39,.5);color:#c8fff0;cursor:not-allowed}
      .build-game-goal-note{display:block;margin-top:5px;color:var(--muted,#9eacc2);font-size:.68rem;font-weight:500}
      .build-game-round-contract{padding:14px 16px;border:1px solid rgba(101,223,255,.22);border-radius:14px;background:rgba(8,31,45,.62)}
      .build-game-round-contract span{display:block;color:#65dfff;font-size:.66rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
      .build-game-round-contract strong{display:block;margin-top:5px;overflow-wrap:anywhere}.build-game-round-contract small{display:block;margin-top:5px;color:var(--muted,#9eacc2)}
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
    const historicalGoal = missionTasks.map(goalFromTask).find(Boolean);
    const storedGoal = localStorage.getItem(activeGoalKey());
    const goal = missionTasks.length ? historicalGoal : storedGoal;
    if (historicalGoal) localStorage.setItem(activeGoalKey(), historicalGoal);
    return {missionTasks, goal: goal || ''};
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
    const goalLocked = missionTasks.length > 0;
    const goal = goalLocked ? (initialGoal || '') : (localStorage.getItem(activeGoalKey()) || initialGoal || '');

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
      let action = '<span class="build-game-lock">🔒 Conclua a etapa anterior</span>';
      if (passed) action = `<span>${status('completed')}</span>`;
      else if (unlocked && active) action = `<span>${status(task.status)}</span><button class="ghost" type="button" data-game-refresh>Atualizar</button>`;
      else if (unlocked) action = `<button class="primary" type="button" data-play-phase="${phase.id}">${failed ? '↻ Tentar novamente' : '▶ Jogar fase'}</button>`;
      return `<article class="build-game-phase ${className}">
        <div class="build-game-phase-icon" aria-hidden="true">${phase.icon}</div>
        <div class="build-game-phase-copy"><small>ETAPA ${phase.id}/${phases.length} · +${phase.xp} XP</small><strong>${esc(phase.name)}</strong><p>${esc(phase.summary)}</p></div>
        <div class="build-game-phase-actions">${action}</div>
      </article>`;
    }).join('');

    const history = missionTasks.slice(0, 8).map(task =>
      `<div class="build-game-history-row"><div><strong>Etapa ${phaseFromTask(task)} · ${esc(task.title)}</strong><small>${new Date(task.created_at).toLocaleString('pt-BR')}</small></div>${status(task.status)}</div>`
    ).join('') || '<div class="empty">A rodada começa quando você iniciar o Planejamento.</div>';

    view.innerHTML = `<div class="build-game-shell">
      <section class="build-game-hero">
        <span class="eyebrow">UMA RODADA · UMA ENTREGA REAL</span>
        <h2>Jogo de construção</h2>
        <p>Descreva o que deve ficar pronto. O DevPilot conduz a mesma esteira do desenvolvimento real e só encerra a rodada quando a funcionalidade estiver implementada, testada, versionada e revisada.</p>
        <div class="build-game-config">
          <label>Projeto<select id="build-game-project">${projectOptions}</select></label>
          <label>Entrega da rodada<input id="build-game-goal" maxlength="500" value="${esc(goal)}" placeholder="Ex.: criar login e senha com acesso por perfil" ${goalLocked ? 'readonly aria-readonly="true" data-round-goal-locked="true"' : ''}><small class="build-game-goal-note">${goalLocked ? 'Objetivo fixado pela primeira etapa. Abra uma nova rodada para pedir outra entrega.' : 'Escreva uma funcionalidade objetiva que possa ser implementada e verificada.'}</small></label>
          <button class="ghost" type="button" id="build-game-new">Nova rodada</button>
        </div>
      </section>

      <section class="build-game-round-contract" aria-live="polite">
        <span>Contrato da rodada</span>
        <strong>${esc(goal || 'Descreva a funcionalidade que deve ser entregue.')}</strong>
        <small>Planejamento → Implementação → Execução → Testes → Documentação → Git → Entrega/revisão</small>
      </section>

      <section class="build-game-score" aria-label="Placar da partida">
        <div><span>Progresso</span><strong>${game.passed}/${phases.length} etapas</strong></div>
        <div><span>Experiência</span><strong>${game.xp}/${game.totalXp} XP</strong></div>
        <div><span>Projeto</span><strong>${esc(project?.name || '—')}</strong></div>
      </section>
      <div class="build-game-progress" aria-label="${percent}% concluído"><i style="width:${percent}%"></i></div>

      ${game.passed === phases.length ? `<section class="build-game-victory"><span class="eyebrow">ESTEIRA CONCLUÍDA</span><h3>🏆 Entrega da rodada pronta para o usuário</h3><p>${esc(goal || 'Objetivo da rodada')} · ${game.totalXp} XP conquistados. Implementação, execução, testes, documentação, Git e revisão permanecem rastreáveis.</p></section>` : ''}

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
    if (goalInput && !goalLocked) {
      goalInput.onchange = () => setGoal(goalInput.value);
      goalInput.oninput = () => setGoal(goalInput.value);
    }

    view.querySelector('#build-game-new')?.addEventListener('click', () => {
      if (missionTasks.length && !window.confirm('Começar uma nova rodada? O histórico e a entrega atual serão preservados nas tarefas.')) return;
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
${PIPELINE_MARKER}
[DEVPILOT_MODE=develop]
PARTIDA: ${missionId}
FASE: ${phase.id}/${phases.length}
OBJETIVO: ${goal}

MISSÃO DA FASE: ${phase.name}
${phase.mission}

CONTRATO DE PROGRESSÃO REAL:
- Esta etapa corresponde à etapa real "${phase.name}" da esteira e não pode executar ou antecipar outra etapa sem necessidade técnica registrada.
- Evidência obrigatória desta etapa: ${phase.evidence}
- Preserve o objetivo literal da rodada em todas as decisões; não reduza nem troque o pedido para conseguir concluir.
- Na Implementação deve existir delta funcional persistente. Nas demais etapas, a evidência específica acima é obrigatória mesmo quando nenhum novo delta de código for necessário.
- Registre o estado antes e depois. Quando houver alteração, inclua git status --short e git diff --stat.
- Descreva no resultado o ANTES, a AÇÃO REALIZADA, a EVIDÊNCIA e o DEPOIS observável pelo usuário ou pela API.
- Se a evidência desta etapa ou algum critério de aceite estiver ausente, NÃO marque a tarefa como concluída. Corrija ou encerre como falha/bloqueio com a causa real.
- URL pública é evidência de entrega, não prêmio que substitui código. Nunca conclua uma fase apenas porque uma URL responde.

REGRAS DO JOGO:
- Trabalhe somente no projeto selecionado e respeite AGENTS.md e as regras do repositório.
- Antes de alterar, inspecione o estado atual e preserve mudanças válidas existentes.
- Implemente de verdade; não substitua comportamento real por dados falsos, mocks indevidos ou respostas simuladas.
- Use Git de forma reversível e nunca force push na branch principal.
- Execute as verificações aplicáveis desta fase e registre comandos e evidências no resultado.
- Se uma verificação obrigatória falhar, corrija e execute novamente. Se não for possível corrigir com segurança, reporte a falha claramente; não invente aprovação.
- Não avance para outra fase nesta tarefa. A próxima fase será liberada pelo Jogo de construção somente após esta tarefa ficar concluída.

CRITÉRIO DE VITÓRIA:
A etapa termina somente quando sua evidência obrigatória existe de fato, continua ligada ao objetivo imutável da rodada e as verificações aplicáveis foram executadas sem falhas não resolvidas. A rodada só termina após as sete etapas e a entrega final do pedido do usuário.`;

  const playPhase = async (phaseId, button) => {
    const phase = phases.find(item => item.id === phaseId);
    if (!phase) return;
    await ensureProjects();
    const game = gameState(currentTasks);
    if (phaseId !== game.current) return toast('Conclua a etapa atual antes de avançar');
    const goalInput = document.querySelector('#build-game-goal');
    const goal = String(goalInput?.value || '').trim();
    if (!goal) {
      goalInput?.focus();
      return toast('Descreva o que deve ser entregue nesta rodada');
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
          title: `[Jogo] Etapa ${phase.id} · ${phase.name}`,
          prompt: buildPrompt(phase, goal),
          source: 'dashboard',
          priority: Math.min(100, 68 + phase.id * 5),
          requires_approval: false
        })
      });
      toast(`Etapa ${phase.id} iniciada · ${phase.xp} XP em jogo`);
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
