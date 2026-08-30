(() => {
  const form = document.querySelector('#task-form');
  const mode = document.querySelector('#task-mode');
  const context = document.querySelector('#task-context');
  const hint = document.querySelector('#task-mode-hint');
  const assistTitle = document.querySelector('#task-assist-title');
  const assistText = document.querySelector('#task-assist-text');
  const submit = document.querySelector('#task-submit');

  if (!form || !mode || !context) return;

  const approvalInput = form.querySelector('input[name="requires_approval"]');
  const approvalLabel = approvalInput?.closest('label');

  function applyApprovalByExceptionDefault() {
    if (approvalInput) approvalInput.checked = false;
    if (approvalLabel) {
      approvalLabel.lastChild.textContent = ' Exigir aprovação manual mesmo para ação segura';
      approvalLabel.title = 'Push, merge, deploy, produção, dependências, ações destrutivas e credenciais continuam exigindo aprovação automaticamente.';
    }
  }

  const modes = {
    'analysis-read-only': {
      title: 'Análise assistida pelo AgentOS',
      text: 'O repositório será consultado em uma área isolada. Nenhuma alteração será persistida; a resposta destacará evidências, riscos, impacto e recomendações.',
      hint: 'A IA analisará este contexto junto com o repositório, sem persistir alterações.',
      submit: 'Registrar análise',
      instruction: 'Faça uma análise/diagnóstico do contexto informado. Investigue o repositório, cite evidências concretas e produza achados priorizados com risco, impacto, recomendação e esforço estimado. Não implemente mudanças e não persista alterações em arquivos.'
    },
    develop: {
      title: 'Desenvolvimento assistido pelo AgentOS',
      text: 'Antes de alterar código, o DevPilot verifica se a funcionalidade já existe para evitar telas, endpoints, serviços ou fluxos duplicados.',
      hint: 'A primeira etapa é uma verificação obrigatória de duplicidade. Só depois a IA implementa o que realmente estiver faltando.',
      submit: 'Registrar desenvolvimento',
      instruction: 'Comece obrigatoriamente verificando no repositório se o comportamento solicitado já existe, inclusive em telas, rotas, componentes, serviços, modelos, testes e documentação relacionados. Não crie uma segunda implementação do que já existe. Se estiver completo, apenas valide e apresente evidências sem alterar código. Se estiver parcial, reutilize a implementação existente e desenvolva somente as lacunas comprovadas. Depois execute as verificações relevantes e resuma o preflight, as alterações e os riscos remanescentes.'
    },
    fix: {
      title: 'Correção assistida pelo AgentOS',
      text: 'O DevPilot investiga a causa raiz, aplica uma correção mínima e valida a regressão antes de devolver o resultado para revisão.',
      hint: 'Descreva o erro observado, comportamento esperado e evidências disponíveis.',
      submit: 'Registrar correção',
      instruction: 'Diagnostique a causa raiz do problema descrito e implemente uma correção mínima e segura. Preserve compatibilidade, execute testes de regressão relevantes e resuma evidências e riscos.'
    },
    review: {
      title: 'Revisão assistida pelo AgentOS',
      text: 'O DevPilot revisa o contexto e o repositório para apontar regressões, inconsistências e oportunidades antes de qualquer alteração.',
      hint: 'A revisão não solicita implementação automática; qualquer mudança posterior deve ser criada como nova tarefa.',
      submit: 'Registrar revisão',
      instruction: 'Revise o contexto e o repositório. Identifique regressões, inconsistências, riscos de segurança, lacunas de testes e oportunidades. Não implemente mudanças nesta tarefa.'
    }
  };

  function refreshMode() {
    const config = modes[mode.value] || modes['analysis-read-only'];
    if (hint) hint.textContent = config.hint;
    if (assistTitle) assistTitle.textContent = config.title;
    if (assistText) assistText.textContent = config.text;
    if (submit) submit.textContent = config.submit;
  }

  mode.addEventListener('change', refreshMode);
  applyApprovalByExceptionDefault();
  refreshMode();

  form.addEventListener('submit', () => {
    const raw = context.value.trim();
    const selectedMode = mode.value;
    const config = modes[selectedMode] || modes['analysis-read-only'];
    context.value = `[DEVPILOT_MODE=${selectedMode}]\n${config.instruction}\n\nContexto do usuário:\n${raw}`;
    window.setTimeout(() => {
      context.value = raw;
    }, 0);
  }, true);

  form.addEventListener('reset', () => {
    window.setTimeout(() => {
      applyApprovalByExceptionDefault();
      refreshMode();
    }, 0);
  });

  // A classificação visual segue o mesmo contrato do worker: uma ação nunca
  // volta a aparecer como análise só porque contém o diagnóstico de origem.
  const taskTableBody = document.querySelector('#tasks-table');

  function taskKind(task) {
    const prompt = String(task?.prompt || '');
    const source = String(task?.source || '').toLowerCase();
    const lowerPrompt = prompt.toLowerCase();
    const legacyText = `${task?.title || ''}\n${prompt}`.toLowerCase();
    const actionSignals = [
      'correção baseada na análise',
      'correcao baseada na analise',
      'ação recomendada',
      'acao recomendada',
      'execute as correções',
      'execute as correcoes',
      'não faça uma nova análise',
      'nao faca uma nova analise'
    ];

    if (
      source === 'analysis' ||
      source === 'analysis-action' ||
      lowerPrompt.includes('[analysis-action]') ||
      lowerPrompt.includes('[analysis-run:') ||
      lowerPrompt.includes('[devpilot_stage=execute]') ||
      lowerPrompt.includes('[devpilot_stage=correct]') ||
      actionSignals.some(signal => legacyText.includes(signal))
    ) return 'action';

    if (
      source === 'execution-verification' ||
      lowerPrompt.includes('[post-execution-verification]') ||
      lowerPrompt.includes('[devpilot_stage=verify]')
    ) return 'analysis';

    const marker = prompt.match(/\[DEVPILOT_MODE=([^\]]+)\]/i)?.[1]?.toLowerCase();

    if (marker === 'analysis-read-only' || marker === 'review') return 'analysis';
    if (marker === 'develop' || marker === 'fix') return 'execution';

    const readOnlySignals = [
      'somente leitura',
      'não modifique arquivos',
      'nao modifique arquivos',
      'não implemente',
      'nao implemente',
      'análise técnica',
      'analise tecnica',
      'auditoria somente leitura'
    ];

    return readOnlySignals.some(signal => legacyText.includes(signal))
      ? 'analysis'
      : 'execution';
  }

  function ensureTaskKindStyles() {
    if (document.querySelector('#devpilot-task-kind-style')) return;
    const style = document.createElement('style');
    style.id = 'devpilot-task-kind-style';
    style.textContent = `
      .task-kind-badge{display:inline-flex;align-items:center;gap:6px;white-space:nowrap;font-size:11px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}
      .task-kind-badge::before{content:'';width:7px;height:7px;border-radius:50%;background:currentColor;box-shadow:0 0 10px currentColor}
      .task-kind-badge.analysis{color:#63e6be}
      .task-kind-badge.action{color:#74c0fc}
      .task-kind-badge.execution{color:#74c0fc}
    `;
    document.head.appendChild(style);
  }

  function ensureTaskKindHeader() {
    const table = taskTableBody?.closest('table');
    const headerRow = table?.querySelector('thead tr');
    if (!headerRow || headerRow.querySelector('[data-task-kind-header]')) return;

    const originHeader = [...headerRow.children].find(
      cell => cell.textContent.trim().toLowerCase() === 'origem'
    );
    if (!originHeader) return;

    const header = document.createElement('th');
    header.dataset.taskKindHeader = 'true';
    header.textContent = 'Tipo';
    originHeader.insertAdjacentElement('afterend', header);
  }

  function enhanceTaskKindColumn() {
    if (!taskTableBody) return;

    ensureTaskKindStyles();
    ensureTaskKindHeader();

    const tasks = typeof state !== 'undefined' && Array.isArray(state.tasks)
      ? state.tasks
      : [];
    const rows = [...taskTableBody.querySelectorAll('tr.task-main-row')];

    rows.forEach((row, index) => {
      const task = tasks[index];
      if (!task || row.children.length < 2) return;

      const kind = taskKind(task);
      const label = kind === 'analysis' ? 'Análise' : 'Execução';
      let cell = row.querySelector('.task-kind-cell');

      if (!cell) {
        cell = document.createElement('td');
        cell.className = 'task-kind-cell';
        row.children[1].insertAdjacentElement('afterend', cell);
      }

      cell.innerHTML = `<span class="task-kind-badge ${kind}">${label}</span>`;
      row.dataset.taskId = task.id || '';
    });

    const emptyCell = taskTableBody.querySelector('td.empty');
    if (emptyCell) emptyCell.colSpan = Math.max(Number(emptyCell.colSpan || 5), 6);
  }

  if (taskTableBody) {
    let scheduled = false;

    const scheduleEnhancement = () => {
      if (scheduled) return;

      scheduled = true;

      window.requestAnimationFrame(() => {
        scheduled = false;

        if (
          document.querySelector(
            '#tasks-view.active'
          )
        ) {
          enhanceTaskKindColumn();
        }
      });
    };

    document.addEventListener(
      'devpilot:tasks-rendered',
      scheduleEnhancement
    );

    if (
      document.querySelector(
        '#tasks-view.active'
      )
    ) {
      scheduleEnhancement();
    }
  }
})();
