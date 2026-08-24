/* Project-scoped automatic system tests: run, create and safely recreate. */
(() => {
  const MARKER = '[DEVPILOT_SYSTEM_TESTS_V1]';
  const STORAGE_KEY = 'devpilot-system-tests-project';
  let selectedProjectId = localStorage.getItem(STORAGE_KEY) || '';

  const actionConfig = {
    run: {
      title: 'Rodar testes automáticos de sistema',
      priority: 65,
      requiresApproval: false,
      prompt: `${MARKER}
MODO: RUN

Execute a suíte automática de testes de sistema, integração e smoke já existente neste projeto.

Regras obrigatórias:
- Leia AGENTS.md e as instruções do projeto antes de executar.
- Detecte a stack e o framework de testes existentes; se existir .devpilot/system-tests-manifest.json, use o comando registrado nele.
- Execute somente testes e verificações não destrutivas. Não modifique arquivos, código de produção, banco persistente ou infraestrutura.
- Não use credenciais reais em saída, logs ou fixtures.
- Se não existir suíte automática de sistema, não invente resultado: informe claramente que ela ainda precisa ser criada.
- Retorne os comandos executados, quantidade de testes aprovados/falhos/ignorados, falhas com evidência e próximos passos.
- Considere aprovado somente o que foi efetivamente executado.`
    },
    create: {
      title: 'Criar testes automáticos de sistema',
      priority: 75,
      requiresApproval: true,
      prompt: `${MARKER}
MODO: CREATE

Crie uma suíte automática de testes de sistema para este projeto.

Regras obrigatórias:
- Leia AGENTS.md, documentação e configuração do repositório antes de alterar arquivos.
- Detecte a stack, os comandos de execução e o framework de testes já adotado. Reutilize o framework existente sempre que possível.
- Cubra os fluxos críticos reais do projeto com testes de sistema, integração e smoke adequados à arquitetura encontrada.
- Não altere comportamento funcional do produto apenas para fazer os testes passarem.
- Use somente fixtures/dados sintéticos claramente identificados como teste; nunca apresente dados inventados como produção.
- Preserve todos os testes manuais ou previamente existentes.
- Registre os arquivos gerados e o comando de execução em .devpilot/system-tests-manifest.json, incluindo "generator": "DevPilot" e "version": 1.
- Rode a suíte criada quando o ambiente permitir e reporte comandos, aprovados, falhos, ignorados e limitações.
- Nunca oculte uma falha: se algo não puder ser testado, registre explicitamente a razão.`
    },
    recreate: {
      title: 'Recriar testes automáticos de sistema',
      priority: 80,
      requiresApproval: true,
      prompt: `${MARKER}
MODO: RECREATE

Recrie e atualize a suíte automática de testes de sistema deste projeto.

Regras obrigatórias:
- Leia AGENTS.md, documentação, stack atual e .devpilot/system-tests-manifest.json antes de alterar arquivos.
- Preserve testes manuais e testes que não tenham sido gerados pelo DevPilot.
- Se o manifesto existir, substitua/atualize somente a suíte e os arquivos que ele identifica como gerados pelo DevPilot.
- Se o manifesto não existir, trate os testes atuais como manuais: não os apague; crie uma suíte DevPilot isolada e passe a registrá-la no manifesto.
- Reavalie os fluxos críticos conforme o código atual e remova do conjunto DevPilot apenas testes que ficaram comprovadamente obsoletos.
- Não altere comportamento funcional do produto apenas para fazer os testes passarem.
- Use somente fixtures/dados sintéticos claramente identificados como teste.
- Atualize .devpilot/system-tests-manifest.json com arquivos, framework, comando e "generator": "DevPilot", "version": 1.
- Rode a suíte recriada quando o ambiente permitir e reporte comandos, aprovados, falhos, ignorados e limitações.
- Nunca transforme falha em sucesso por fallback, mock indevido ou supressão de erro.`
    }
  };

  const style = `
    .system-tests-shell{display:grid;gap:18px}
    .system-tests-hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(230px,340px);gap:20px;align-items:end;padding:22px;border:1px solid var(--line,#233047);border-radius:18px;background:linear-gradient(145deg,rgba(27,42,67,.72),rgba(9,17,31,.94))}
    .system-tests-hero h2{margin:5px 0 8px;font-size:clamp(1.5rem,4vw,2.25rem)}
    .system-tests-hero p{margin:0;color:var(--muted,#9eacc2);max-width:760px}
    .system-tests-project label{display:grid;gap:7px;font-size:.8rem;color:var(--muted,#9eacc2)}
    .system-tests-project select{width:100%;min-height:44px}
    .system-tests-actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
    .system-tests-action{min-height:54px;border-radius:14px}
    .system-tests-action[data-system-tests-action="recreate"]{border-color:#d68b37}
    .system-tests-current{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:center}
    .system-tests-current h3,.system-tests-history h3{margin:4px 0}
    .system-tests-current p{margin:4px 0;color:var(--muted,#9eacc2)}
    .system-tests-history-list{display:grid;gap:10px;margin-top:14px}
    .system-tests-run{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:center;padding:14px;border:1px solid var(--line,#233047);border-radius:14px;background:rgba(7,17,31,.46)}
    .system-tests-run-main{min-width:0}
    .system-tests-run-main strong{display:block;margin-bottom:4px}
    .system-tests-run-main small{color:var(--muted,#9eacc2)}
    .system-tests-run-actions{display:flex;gap:8px;align-items:center}
    .system-tests-note{font-size:.82rem;color:var(--muted,#9eacc2);margin:0}
    @media(max-width:720px){
      .system-tests-hero{grid-template-columns:1fr;padding:16px}
      .system-tests-actions{grid-template-columns:1fr}
      .system-tests-current,.system-tests-run{grid-template-columns:1fr}
      .system-tests-run-actions{justify-content:space-between}
    }
  `;

  const installStyle = () => {
    if (document.querySelector('#system-tests-style')) return;
    const el = document.createElement('style');
    el.id = 'system-tests-style';
    el.textContent = style;
    document.head.appendChild(el);
  };

  const selectedProject = () =>
    (Array.isArray(state.projects) ? state.projects : []).find(project => String(project.id) === String(selectedProjectId));

  const ensureProjects = async () => {
    if (!Array.isArray(state.projects) || !state.projects.length) {
      state.projects = await api('/projects');
    }
    const select = document.querySelector('#system-tests-project');
    if (!select) return;
    if (!selectedProjectId || !state.projects.some(project => String(project.id) === String(selectedProjectId))) {
      selectedProjectId = state.projects[0]?.id || '';
    }
    select.innerHTML = state.projects.map(project =>
      `<option value="${esc(project.id)}" ${String(project.id) === String(selectedProjectId) ? 'selected' : ''}>${esc(project.name)}</option>`
    ).join('') || '<option value="">Nenhum projeto cadastrado</option>';
    select.disabled = !state.projects.length;
    if (selectedProjectId) localStorage.setItem(STORAGE_KEY, selectedProjectId);
  };

  const systemTasks = tasks =>
    (Array.isArray(tasks) ? tasks : []).filter(task => String(task.prompt || '').includes(MARKER));

  const operationLabel = task => {
    const prompt = String(task.prompt || '');
    if (prompt.includes('MODO: RECREATE')) return 'Recriar';
    if (prompt.includes('MODO: CREATE')) return 'Criar';
    return 'Rodar';
  };

  const renderHistory = tasks => {
    const target = document.querySelector('#system-tests-history-list');
    const current = document.querySelector('#system-tests-current');
    if (!target || !current) return;
    const items = systemTasks(tasks);
    const latest = items[0];

    current.innerHTML = latest
      ? `<div><span class="eyebrow">ÚLTIMA OPERAÇÃO</span><h3>${esc(operationLabel(latest))} testes automáticos</h3><p>${new Date(latest.created_at).toLocaleString('pt-BR')} · prioridade ${Number(latest.priority || 0)}</p></div><div>${status(latest.status)}</div>`
      : '<div><span class="eyebrow">ESTADO</span><h3>Nenhum teste automático registrado</h3><p>Crie a primeira suíte para o projeto selecionado ou rode uma suíte já existente no repositório.</p></div>';

    target.innerHTML = items.map(task =>
      `<article class="system-tests-run">
        <div class="system-tests-run-main">
          <strong>${esc(operationLabel(task))} · ${esc(task.title)}</strong>
          <small>${new Date(task.created_at).toLocaleString('pt-BR')} · prioridade ${Number(task.priority || 0)}</small>
        </div>
        <div class="system-tests-run-actions">
          ${status(task.status)}
          ${task.status === 'awaiting_approval' ? `<button class="primary system-tests-approve" data-task-id="${esc(task.id)}">Aprovar</button>` : ''}
        </div>
      </article>`
    ).join('') || '<div class="empty">Nenhuma execução de testes registrada para este projeto.</div>';

    target.querySelectorAll('.system-tests-approve').forEach(button => {
      button.onclick = async () => {
        button.disabled = true;
        try {
          await api(`/tasks/${button.dataset.taskId}/approve`, {method:'POST'});
          toast('Testes aprovados e enviados para a fila');
          await window.loadSystemTests();
          load();
        } catch (error) {
          toast(error.message);
        } finally {
          button.disabled = false;
        }
      };
    });
  };

  window.loadSystemTests = async () => {
    try {
      await ensureProjects();
      if (!selectedProjectId) {
        renderHistory([]);
        return;
      }
      const project = selectedProject();
      const label = document.querySelector('#system-tests-project-context');
      if (label) {
        label.textContent = project
          ? `${project.name} · branch ${project.default_branch || 'main'}`
          : 'Projeto selecionado';
      }
      const tasks = await api(`/tasks?project_id=${encodeURIComponent(selectedProjectId)}&limit=500`);
      renderHistory(tasks);
    } catch (error) {
      toast(error.message);
    }
  };

  const requestAction = async (mode, button) => {
    const config = actionConfig[mode];
    if (!config) return;
    await ensureProjects();
    if (!selectedProjectId) return toast('Selecione um projeto');
    const project = selectedProject();
    const original = button.textContent;
    button.disabled = true;
    button.textContent = mode === 'run' ? 'Enfileirando…' : 'Registrando…';
    try {
      const task = await api('/tasks', {
        method:'POST',
        body:JSON.stringify({
          project_id:selectedProjectId,
          title:`[Testes de sistema] ${config.title}`,
          prompt:config.prompt,
          source:'dashboard',
          priority:config.priority,
          requires_approval:config.requiresApproval
        })
      });
      const action = mode === 'run' ? 'Execução registrada' : `${mode === 'create' ? 'Criação' : 'Recriação'} registrada`;
      toast(task.status === 'awaiting_approval' ? `${action}; aprove para iniciar` : `${action} para ${project?.name || 'o projeto'}`);
      await window.loadSystemTests();
      load();
    } catch (error) {
      toast(error.message);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  };

  const createUi = () => {
    installStyle();
    const nav = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!nav || !main) return;

    let navButton = nav.querySelector('[data-view="system-tests"]');
    if (!navButton) {
      navButton = document.createElement('button');
      navButton.className = 'nav';
      navButton.type = 'button';
      navButton.dataset.view = 'system-tests';
      navButton.textContent = 'Testes de sistemas';
      const providers = nav.querySelector('[data-view="providers"]');
      nav.insertBefore(navButton, providers || null);
    }

    let view = document.querySelector('#system-tests-view');
    if (!view) {
      view = document.createElement('section');
      view.className = 'view';
      view.id = 'system-tests-view';
      view.innerHTML = `
        <div class="system-tests-shell">
          <section class="system-tests-hero">
            <div>
              <span class="eyebrow">QUALIDADE · PROJETO SELECIONADO</span>
              <h2>Testes de sistemas</h2>
              <p>Rode a suíte existente ou peça ao DevPilot para criar e recriar testes automáticos respeitando a stack, o AGENTS.md e os testes manuais do projeto.</p>
            </div>
            <div class="system-tests-project">
              <label>Projeto
                <select id="system-tests-project" aria-label="Projeto para testes de sistemas"></select>
              </label>
              <p class="system-tests-note" id="system-tests-project-context">Selecione um projeto.</p>
            </div>
          </section>

          <div class="system-tests-actions">
            <button class="ghost system-tests-action" type="button" data-system-tests-action="run">▶ Rodar testes automáticos</button>
            <button class="primary system-tests-action" type="button" data-system-tests-action="create">+ Criar testes automáticos</button>
            <button class="ghost system-tests-action" type="button" data-system-tests-action="recreate">↻ Recriar testes automáticos</button>
          </div>

          <article class="panel system-tests-current" id="system-tests-current">
            <div><span class="eyebrow">ESTADO</span><h3>Carregando testes…</h3></div>
          </article>

          <article class="panel system-tests-history">
            <div class="panel-title">
              <div><span class="eyebrow">HISTÓRICO</span><h3>Execuções e gerações</h3></div>
              <button class="link" type="button" id="system-tests-refresh">Atualizar</button>
            </div>
            <div class="system-tests-history-list" id="system-tests-history-list"></div>
          </article>
        </div>`;
      const tasksView = document.querySelector('#tasks-view');
      if (tasksView) tasksView.insertAdjacentElement('afterend', view);
      else main.appendChild(view);
    }

    navButton.onclick = () => {
      showView('system-tests');
      const title = document.querySelector('#page-title');
      if (title) title.textContent = 'Testes de sistemas';
      window.loadSystemTests();
    };

    view.querySelector('#system-tests-project').onchange = event => {
      selectedProjectId = event.target.value;
      if (selectedProjectId) localStorage.setItem(STORAGE_KEY, selectedProjectId);
      else localStorage.removeItem(STORAGE_KEY);
      window.loadSystemTests();
    };
    view.querySelector('#system-tests-refresh').onclick = () => window.loadSystemTests();
    view.querySelectorAll('[data-system-tests-action]').forEach(button => {
      button.onclick = () => requestAction(button.dataset.systemTestsAction, button);
    });
  };

  const enhanceProjectCards = () => {
    document.querySelectorAll('#projects-list [data-project-task]').forEach(taskButton => {
      const actions = taskButton.parentElement;
      if (!actions || actions.querySelector('[data-project-system-tests]')) return;
      const button = document.createElement('button');
      button.className = 'link';
      button.type = 'button';
      button.dataset.projectSystemTests = taskButton.dataset.projectTask;
      button.textContent = 'Testes';
      button.onclick = () => {
        selectedProjectId = button.dataset.projectSystemTests;
        localStorage.setItem(STORAGE_KEY, selectedProjectId);
        const navButton = document.querySelector('.sidebar nav [data-view="system-tests"]');
        navButton?.click();
      };
      actions.insertBefore(button, taskButton);
    });
  };

  createUi();
  enhanceProjectCards();

  const projectList = document.querySelector('#projects-list');
  if (projectList) new MutationObserver(enhanceProjectCards).observe(projectList, {childList:true, subtree:true});
})();
