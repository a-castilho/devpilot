/* DevPilot Build Game repair mission: diagnose -> fix -> test -> deploy -> validate. */
(() => {
  'use strict';

  const REPAIR_MARKER = '[DEVPILOT_BUILD_GAME_REPAIR_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const STAGES = Object.freeze([
    {id: 'diagnose', label: 'Diagnosticar', icon: '🔎', mode: 'analyze'},
    {id: 'fix', label: 'Corrigir', icon: '⚔️', mode: 'fix'},
    {id: 'test', label: 'Testar', icon: '🧪', mode: 'test'},
    {id: 'deploy', label: 'Implantar', icon: '🚀', mode: 'develop'},
    {id: 'validate', label: 'Validar produção', icon: '✅', mode: 'analyze'},
  ]);
  const TERMINAL_FAILURES = new Set(['failed', 'blocked', 'cancelled']);
  const ACTIVE = new Set(['awaiting_approval', 'queued', 'running', 'review']);

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[char]);
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const projectId = () => String(localStorage.getItem(PROJECT_KEY) || '').trim();
  const missionId = () => String(localStorage.getItem(MISSION_KEY) || '').trim();

  function promptValue(task, label) {
    const safe = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return String(task?.prompt || '').match(new RegExp(`^${safe}:\\s*(.+)$`, 'mi'))?.[1]?.trim() || '';
  }

  function isRepairTask(task) {
    const prompt = String(task?.prompt || '');
    return prompt.includes(REPAIR_MARKER) && promptValue(task, 'PARTIDA') === missionId();
  }

  function repairStage(task) {
    return promptValue(task, 'ETAPA').toLowerCase();
  }

  function currentProject(view) {
    const id = String(view.querySelector('#build-game-project')?.value || projectId()).trim();
    const projects = typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : [];
    return projects.find(item => String(item?.id) === id) || null;
  }

  function issueSummary(view) {
    const stored = String(view.querySelector('[data-repair-issue]')?.value || '').trim();
    if (stored) return stored;
    const goal = String(view.querySelector('#build-game-goal')?.value || '').trim();
    if (goal) return goal;
    const project = currentProject(view);
    return `Estabilizar a funcionalidade com falha observada em produção no projeto ${project?.name || 'selecionado'}.`;
  }

  function stagePrompt(stage, view) {
    const project = currentProject(view);
    const issue = issueSummary(view);
    const projectName = String(project?.name || view.querySelector('#build-game-project')?.selectedOptions?.[0]?.textContent || 'Projeto').trim();
    const common = `${REPAIR_MARKER}\n[DEVPILOT_MODE=${stage.mode}]\nPARTIDA: ${missionId()}\nETAPA: ${stage.id}\nPROJETO: ${projectId()}\nPROJETO_NOME: ${projectName}\nINCIDENTE: ${issue}\n\nREGRAS GERAIS:\n- Leia AGENTS.md antes de alterar qualquer arquivo.\n- Trabalhe somente no projeto desta partida e preserve isolamento entre tenants/workspaces.\n- Use evidência real: código, logs, respostas HTTP, configuração e testes. Não invente sucesso.\n- Nunca exponha credenciais, tokens, cookies, chaves privadas ou conteúdo de segredos em logs/resultado.\n- Não desabilite autenticação, autorização, testes ou validações para fazer a etapa passar.\n- Registre causa, arquivos alterados, comandos/testes executados e evidências objetivas no resultado.\n`;

    if (stage.id === 'diagnose') return `${common}\nMISSÃO:\nDiagnostique a causa raiz do incidente sem alterar código até haver evidência suficiente. Verifique frontend e backend, console/rede do navegador, DNS/TLS, CORS, variáveis de ambiente, disponibilidade dos serviços externos e diferenças entre local/homologação/produção. Para autenticação gerenciada (ex.: Supabase), diferencie falha de transporte/"Failed to fetch" de resposta HTTP de credenciais inválidas.\n\nCRITÉRIO DE VITÓRIA:\nApresente causa raiz ou hipótese fortemente sustentada, evidências observadas e plano mínimo de correção. Se faltar acesso externo necessário, bloqueie com a autorização exata necessária.`;
    if (stage.id === 'fix') return `${common}\nMISSÃO:\nAplique a menor correção segura para a causa identificada na etapa de diagnóstico. Não regenere o projeto nem reescreva subsistemas saudáveis. Preserve compatibilidade e trate erros de forma explícita.\n\nCRITÉRIO DE VITÓRIA:\nCorreção implementada no código/configuração correta, sem regressões óbvias e pronta para validação automatizada.`;
    if (stage.id === 'test') return `${common}\nMISSÃO:\nValide a correção antes de qualquer deploy. Execute testes focados e regressão relacionada. Para autenticação, cubra login válido, inválido, persistência/refresh de sessão e logout quando aplicável; valide build de produção e conectividade com provedores externos sem imprimir segredos.\n\nCRITÉRIO DE VITÓRIA:\nTestes relevantes e build passam. Falhas não relacionadas devem ser registradas separadamente; falhas relacionadas bloqueiam o deploy.`;
    if (stage.id === 'deploy') return `${common}\nMISSÃO:\nImplante somente a versão que passou na etapa de testes. Use o pipeline/provedor já configurado para o projeto, confirme variáveis de ambiente necessárias sem exibir valores e não crie infraestrutura paralela por conveniência.\n\nCRITÉRIO DE VITÓRIA:\nDeploy concluído pelo fluxo oficial, com identificador/commit da versão implantada e endpoint de produção acessível. Se o provedor exigir autorização humana, pare de forma segura e indique a ação necessária.`;
    return `${common}\nMISSÃO:\nFaça verificação pós-deploy no ambiente real. Confirme que o incidente original não ocorre mais e que a funcionalidade crítica responde como esperado. Para autenticação, valide a rota/tela real de produção e a resposta do provedor; não use apenas mocks ou ambiente local.\n\nCRITÉRIO DE VITÓRIA:\nProdução validada com evidência objetiva. Se ainda houver falha, marque a etapa como falha/bloqueada para que o jogo gere nova correção em vez de declarar vitória.`;
  }

  async function gameApi(path, options = {}) {
    if (typeof api === 'function') return api(path, options);
    const token = localStorage.getItem('devpilot-token') || '';
    const response = await fetch(`/api${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? {Authorization: `Bearer ${token}`} : {}),
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
    return data;
  }

  async function tasksForMission() {
    const id = projectId();
    if (!id || !missionId()) return [];
    const tasks = await gameApi(`/tasks?project_id=${encodeURIComponent(id)}&limit=500`);
    return (Array.isArray(tasks) ? tasks : []).filter(isRepairTask);
  }

  function latestByStage(tasks) {
    const map = new Map();
    [...tasks].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)).forEach(task => {
      const stage = repairStage(task);
      if (stage && !map.has(stage)) map.set(stage, task);
    });
    return map;
  }

  function stageState(stage, index, byStage) {
    const task = byStage.get(stage.id);
    if (task) {
      const status = normalize(task.status);
      if (status === 'completed') return {kind: 'completed', label: 'Concluída', task};
      if (ACTIVE.has(status)) return {kind: 'active', label: 'Em execução', task};
      if (TERMINAL_FAILURES.has(status)) return {kind: 'failed', label: 'Falhou · repetir', task};
      return {kind: 'active', label: status || 'Em andamento', task};
    }
    if (index === 0) return {kind: 'ready', label: 'Pronta'};
    const previous = byStage.get(STAGES[index - 1].id);
    return normalize(previous?.status) === 'completed'
      ? {kind: 'ready', label: 'Liberada'}
      : {kind: 'locked', label: 'Bloqueada'};
  }

  async function createStage(stage, view, button) {
    if (!projectId() || !missionId()) {
      window.toast?.('Inicie uma partida antes da missão de estabilização.');
      return;
    }
    button.disabled = true;
    try {
      const tasks = await tasksForMission();
      const byStage = latestByStage(tasks);
      const index = STAGES.findIndex(item => item.id === stage.id);
      const current = stageState(stage, index, byStage);
      if (!['ready', 'failed'].includes(current.kind)) return;
      await gameApi('/tasks', {
        method: 'POST',
        body: JSON.stringify({
          project_id: projectId(),
          title: `[Jogo] Estabilização · ${stage.label}`,
          prompt: stagePrompt(stage, view),
          source: 'dashboard',
          priority: stage.id === 'deploy' || stage.id === 'validate' ? 92 : 88,
          requires_approval: false,
        }),
      });
      window.toast?.(`${stage.label}: tarefa criada dentro da partida.`);
      await render(view);
    } catch (error) {
      console.error('DevPilot repair mission:', error);
      window.toast?.(`Falha ao criar etapa: ${error.message}`);
    } finally {
      button.disabled = false;
    }
  }

  function installStyle() {
    if (document.querySelector('#build-game-repair-mission-style')) return;
    const style = document.createElement('style');
    style.id = 'build-game-repair-mission-style';
    style.textContent = `
      .build-game-repair{margin:14px 0;padding:16px;border:1px solid rgba(255,190,94,.25);border-radius:16px;background:linear-gradient(145deg,rgba(32,19,5,.72),rgba(4,13,24,.94));box-sizing:border-box}
      .build-game-repair-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}.build-game-repair-head h3{margin:.15rem 0}.build-game-repair-head p{margin:.2rem 0;color:var(--muted,#9eacc2);font-size:.78rem}
      .build-game-repair textarea{width:100%;min-height:68px;resize:vertical;box-sizing:border-box;margin:10px 0 12px;padding:10px 12px;border-radius:12px;border:1px solid rgba(255,255,255,.12);background:rgba(0,0,0,.24);color:inherit}
      .build-game-repair-flow{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}.build-game-repair-step{min-width:0;padding:10px;border:1px solid rgba(255,255,255,.1);border-radius:12px;background:rgba(255,255,255,.035)}
      .build-game-repair-step strong,.build-game-repair-step small{display:block}.build-game-repair-step small{margin:4px 0 8px;color:var(--muted,#9eacc2)}.build-game-repair-step.completed{border-color:rgba(104,240,187,.3)}.build-game-repair-step.failed{border-color:rgba(255,116,116,.35)}.build-game-repair-step.locked{opacity:.58}.build-game-repair-step button{width:100%}
      @media(max-width:900px){.build-game-repair-flow{grid-template-columns:1fr 1fr}}@media(max-width:560px){.build-game-repair-flow{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  async function render(view = document.querySelector('#build-game-view')) {
    if (!view || !view.isConnected) return;
    installStyle();
    const existing = view.querySelector('[data-build-game-repair]');
    if (!projectId() || !missionId()) {
      existing?.remove();
      return;
    }

    let tasks = [];
    try { tasks = await tasksForMission(); } catch (error) { console.error('DevPilot repair mission tasks:', error); }
    const byStage = latestByStage(tasks);
    const issue = existing?.querySelector('[data-repair-issue]')?.value || issueSummary(view);
    const panel = existing || document.createElement('section');
    panel.dataset.buildGameRepair = '1';
    panel.className = 'build-game-repair';
    panel.innerHTML = `<div class="build-game-repair-head"><div><span class="eyebrow">MISSÃO REAL · ESTABILIZAÇÃO</span><h3>Falha encontrada no sistema gerado</h3><p>O jogo não regenera o projeto: diagnostica, corrige, testa, implanta e valida a mesma partida.</p></div></div><textarea data-repair-issue aria-label="Incidente observado" placeholder="Descreva o erro observado na aplicação">${esc(issue)}</textarea><div class="build-game-repair-flow"></div>`;
    const flow = panel.querySelector('.build-game-repair-flow');
    STAGES.forEach((stage, index) => {
      const stateInfo = stageState(stage, index, byStage);
      const cell = document.createElement('div');
      cell.className = `build-game-repair-step ${stateInfo.kind}`;
      const canRun = stateInfo.kind === 'ready' || stateInfo.kind === 'failed';
      cell.innerHTML = `<strong>${stage.icon} ${esc(stage.label)}</strong><small>${esc(stateInfo.label)}</small><button type="button" class="${canRun ? 'primary' : ''}" data-repair-stage="${stage.id}" ${canRun ? '' : 'disabled'}>${stateInfo.kind === 'failed' ? 'Repetir etapa' : stateInfo.kind === 'completed' ? 'Concluída' : stateInfo.kind === 'active' ? 'Em execução' : stateInfo.kind === 'locked' ? 'Aguardando etapa anterior' : stage.label}</button>`;
      flow.appendChild(cell);
    });
    if (!existing) {
      const anchor = view.querySelector('.build-game-score, .build-game-phases, .build-game-board') || view.firstElementChild;
      if (anchor) anchor.insertAdjacentElement('afterend', panel); else view.prepend(panel);
    }
  }

  document.addEventListener('click', event => {
    const button = event.target?.closest?.('[data-build-game-repair] [data-repair-stage]');
    if (!button || button.disabled) return;
    const stage = STAGES.find(item => item.id === button.dataset.repairStage);
    const view = button.closest('#build-game-view');
    if (stage && view) void createStage(stage, view, button);
  });

  function install() {
    if (typeof window.loadBuildGame !== 'function') return window.setTimeout(install, 60);
    if (!window.loadBuildGame.__repairMissionWrapped) {
      const baseLoad = window.loadBuildGame;
      const wrapped = async (...args) => {
        const result = await baseLoad(...args);
        await render();
        return result;
      };
      wrapped.__repairMissionWrapped = true;
      window.loadBuildGame = wrapped;
    }
    installStyle();
    if (document.querySelector('#build-game-view.active')) void render();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once: true});
  else install();
})();
