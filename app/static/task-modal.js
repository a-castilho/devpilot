(() => {
  'use strict';

  const form = document.querySelector('#task-form');
  const mode = document.querySelector('#task-mode');
  const context = document.querySelector('#task-context');
  const hint = document.querySelector('#task-mode-hint');
  const assistTitle = document.querySelector('#task-assist-title');
  const assistText = document.querySelector('#task-assist-text');
  const submit = document.querySelector('#task-submit');

  if (!form || !mode || !context) return;
  if (window.__devpilotCanonicalExecutionSubmitV34) return;
  window.__devpilotCanonicalExecutionSubmitV34 = true;

  /*
   * app.js é carregado antes deste módulo e historicamente instalava
   * taskForm.onsubmit. Nova execução reutiliza o mesmo contrato /api/tasks,
   * portanto deve existir um único dono do submit. Removemos apenas o handler
   * legado do mesmo formulário; os demais controles do app.js permanecem.
   */
  form.onsubmit = null;
  delete form.dataset.submitting;

  const approvalInput = form.querySelector('input[name="requires_approval"]');
  const approvalLabel = approvalInput?.closest('label');

  const modes = {
    'analysis-read-only': {
      title: 'Análise assistida pelo AgentOS',
      text: 'O repositório será consultado em uma área isolada. Nenhuma alteração será persistida; a resposta destacará evidências, riscos, impacto e recomendações.',
      hint: 'A IA analisará este contexto junto com o repositório, sem persistir alterações.',
      submit: 'Salvar execução',
      instruction: 'Faça uma análise/diagnóstico do contexto informado. Investigue o repositório, cite evidências concretas e produza achados priorizados com risco, impacto, recomendação e esforço estimado. Não implemente mudanças e não persista alterações em arquivos.'
    },
    develop: {
      title: 'Execução assistida pelo AgentOS',
      text: 'Antes de alterar código, o DevPilot verifica se a funcionalidade já existe para evitar telas, endpoints, serviços ou fluxos duplicados.',
      hint: 'A primeira etapa é uma verificação obrigatória de duplicidade. Só depois a IA implementa o que realmente estiver faltando.',
      submit: 'Salvar execução',
      instruction: 'Comece obrigatoriamente verificando no repositório se o comportamento solicitado já existe, inclusive em telas, rotas, componentes, serviços, modelos, testes e documentação relacionados. Não crie uma segunda implementação do que já existe. Se estiver completo, apenas valide e apresente evidências sem alterar código. Se estiver parcial, reutilize a implementação existente e desenvolva somente as lacunas comprovadas. Depois execute as verificações relevantes e resuma o preflight, as alterações e os riscos remanescentes.'
    },
    fix: {
      title: 'Correção assistida pelo AgentOS',
      text: 'O DevPilot investiga a causa raiz, aplica uma correção mínima e valida a regressão antes de devolver o resultado para revisão.',
      hint: 'Descreva o erro observado, comportamento esperado e evidências disponíveis.',
      submit: 'Salvar execução',
      instruction: 'Diagnostique a causa raiz do problema descrito e implemente uma correção mínima e segura. Preserve compatibilidade, execute testes de regressão relevantes e resuma evidências e riscos.'
    },
    review: {
      title: 'Revisão assistida pelo AgentOS',
      text: 'O DevPilot revisa o contexto e o repositório para apontar regressões, inconsistências e oportunidades antes de qualquer alteração.',
      hint: 'A revisão não solicita implementação automática; qualquer mudança posterior deve ser criada como nova execução.',
      submit: 'Salvar execução',
      instruction: 'Revise o contexto e o repositório. Identifique regressões, inconsistências, riscos de segurança, lacunas de testes e oportunidades. Não implemente mudanças nesta execução.'
    }
  };

  function notify(message) {
    if (typeof window.toast === 'function') {
      window.toast(message);
      return;
    }
    const node = document.querySelector('#toast');
    if (!node) return;
    node.textContent = message;
    node.classList.add('show');
    window.setTimeout(() => node.classList.remove('show'), 4200);
  }

  function detailMessage(body, status) {
    if (typeof body?.detail === 'string') return body.detail;
    if (Array.isArray(body?.detail)) {
      return body.detail.map(item => item?.msg || 'Entrada inválida').join(' · ');
    }
    return `Não foi possível salvar a execução${status ? ` (HTTP ${status})` : ''}`;
  }

  function tokenExpired(token) {
    try {
      const parts = String(token || '').split('.');
      if (parts.length !== 3) return true;
      const payload = JSON.parse(
        decodeURIComponent(
          atob(parts[1].replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(parts[1].length / 4) * 4, '='))
            .split('')
            .map(char => `%${char.charCodeAt(0).toString(16).padStart(2, '0')}`)
            .join('')
        )
      );
      const exp = Number(payload?.exp || 0);
      return !Number.isFinite(exp) || exp <= Math.floor(Date.now() / 1000) + 5;
    } catch (_) {
      return true;
    }
  }

  function requireFreshLogin(message = 'Sua sessão expirou. Entre novamente para continuar.') {
    localStorage.removeItem('devpilot-token');
    sessionStorage.setItem('devpilot-auth-message', message);
    window.setTimeout(() => window.location.reload(), 0);
  }

  async function apiJson(path, options = {}) {
    const token = String(localStorage.getItem('devpilot-token') || '').trim();
    if (!token || tokenExpired(token)) {
      requireFreshLogin();
      throw new Error('Sessão expirada. Faça login novamente.');
    }

    const response = await fetch(`/api${path}`, {
      ...options,
      cache: 'no-store',
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options.body ? {'Content-Type': 'application/json'} : {}),
        ...(options.headers || {}),
      },
    });

    const body = await response.json().catch(() => ({}));

    if (response.status === 401) {
      requireFreshLogin('Sua sessão não é mais válida. Entre novamente para continuar.');
      throw new Error('Sessão expirada. Faça login novamente.');
    }

    if (!response.ok) throw new Error(detailMessage(body, response.status));
    return body;
  }

  function automaticTitle(value) {
    const clean = String(value || '')
      .replace(/^[-#*\s]+/, '')
      .replace(/\s+/g, ' ')
      .trim();
    if (!clean) return 'Nova execução';
    return clean.length > 88 ? `${clean.slice(0, 85).trim()}…` : clean;
  }

  function decoratedPrompt(raw, selectedMode) {
    const config = modes[selectedMode] || modes['analysis-read-only'];
    return `[DEVPILOT_MODE=${selectedMode}]\n${config.instruction}\n\nContexto do usuário:\n${raw}`;
  }

  function canonicalSource(value) {
    const source = String(value || '').trim().toLowerCase();
    return source === 'voice' || source === 'api' ? source : 'dashboard';
  }

  function applyApprovalByExceptionDefault() {
    if (approvalInput) approvalInput.checked = false;
    if (approvalLabel?.lastChild) {
      approvalLabel.lastChild.textContent = ' Exigir aprovação manual mesmo para ação segura';
      approvalLabel.title = 'Push, merge, deploy, produção, dependências, ações destrutivas e credenciais continuam exigindo aprovação automaticamente.';
    }
  }

  function refreshMode() {
    const config = modes[mode.value] || modes['analysis-read-only'];
    if (hint) hint.textContent = config.hint;
    if (assistTitle) assistTitle.textContent = config.title;
    if (assistText) assistText.textContent = config.text;
    if (submit) submit.textContent = config.submit;
  }

  function prepareForm() {
    form.noValidate = true;
    form.setAttribute('novalidate', 'novalidate');
    form.querySelectorAll('[required]').forEach(field => field.removeAttribute('required'));
    const title = form.querySelector('[name="title"]');
    if (title) title.placeholder = 'Opcional · o DevPilot gera pelo contexto';
    const eyebrow = form.querySelector('.task-modal-heading .eyebrow');
    if (eyebrow) eyebrow.textContent = 'NOVA EXECUÇÃO';
  }

  async function verifyCreated(id) {
    if (!id) return false;
    try {
      const detail = await apiJson(`/ui/tasks/${encodeURIComponent(id)}`);
      return String(detail?.id || '') === String(id);
    } catch (_) {
      return false;
    }
  }

  async function refreshExecutions() {
    try {
      if (typeof window.devpilotNavigate === 'function') {
        await window.devpilotNavigate('tasks', {history: true});
      } else {
        document.querySelector('.nav[data-view="tasks"]')?.click?.();
      }
    } catch (_) {}

    window.setTimeout(() => {
      try {
        if (typeof window.loadAllTasks === 'function') {
          void window.loadAllTasks(true, 20);
        } else {
          document.querySelector('#tasks-v9-refresh')?.click?.();
        }
      } catch (_) {}
    }, 100);
  }

  async function saveExecution(event) {
    if (event.target !== form) return;

    event.preventDefault();

    if (form.dataset.executionSubmitting === '1') return;

    prepareForm();

    const data = new FormData(form);
    const projectId = String(data.get('project_id') || '').trim();
    const rawPrompt = String(data.get('prompt') || '').trim();
    const rawTitle = String(data.get('title') || '').trim();
    const selectedMode = String(data.get('mode') || 'analysis-read-only');

    if (!projectId) {
      notify('Selecione um projeto para salvar a execução.');
      form.querySelector('[name="project_id"]')?.focus?.();
      return;
    }

    if (!rawPrompt) {
      notify('Descreva o que deve ser executado.');
      context.focus?.();
      return;
    }

    const priorityValue = Number(data.get('priority') || 50);
    const payload = {
      project_id: projectId,
      title: rawTitle || automaticTitle(rawPrompt),
      prompt: decoratedPrompt(rawPrompt, selectedMode),
      priority: Number.isFinite(priorityValue)
        ? Math.max(0, Math.min(100, priorityValue))
        : 50,
      requires_approval: data.get('requires_approval') === 'on',
      source: canonicalSource(form.closest('dialog')?.dataset.taskSource),
    };

    const originalText = submit?.textContent || 'Salvar execução';
    form.dataset.executionSubmitting = '1';

    if (submit) {
      submit.disabled = true;
      submit.setAttribute('aria-busy', 'true');
      submit.textContent = 'Salvando execução…';
    }

    try {
      const created = await apiJson('/tasks', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      const id = String(created?.id || '').trim();
      if (!id) {
        throw new Error('O servidor não retornou o identificador da execução.');
      }

      const persisted = await verifyCreated(id);
      if (!persisted) {
        throw new Error('A execução foi criada, mas a confirmação da gravação falhou. Atualize a lista antes de tentar novamente.');
      }

      const modal = form.closest('dialog');
      modal?.close?.();
      form.reset();
      if (modal) delete modal.dataset.taskSource;

      document.dispatchEvent(new CustomEvent('devpilot:execution-created', {
        detail: {execution: created, persisted: true},
      }));

      notify('Execução salva com sucesso.');
      await refreshExecutions();
    } catch (error) {
      console.error('[DevPilot] Falha ao salvar execução', error);
      notify(error?.message || 'Não foi possível salvar a execução.');
    } finally {
      delete form.dataset.executionSubmitting;
      if (submit) {
        submit.disabled = false;
        submit.removeAttribute('aria-busy');
        submit.textContent = originalText || 'Salvar execução';
      }
    }
  }

  mode.addEventListener('change', refreshMode);
  form.addEventListener('submit', saveExecution);
  form.addEventListener('reset', () => {
    window.setTimeout(() => {
      applyApprovalByExceptionDefault();
      refreshMode();
      prepareForm();
    }, 0);
  });

  prepareForm();
  applyApprovalByExceptionDefault();
  refreshMode();

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

  function enhanceTaskKindColumn() {
    if (!taskTableBody) return;
    ensureTaskKindStyles();

    const tasks = typeof state !== 'undefined' && Array.isArray(state.tasks)
      ? state.tasks
      : [];
    const rows = [...taskTableBody.querySelectorAll('tr.task-main-row')];

    rows.forEach((row, index) => {
      const task = tasks[index];
      if (!task) return;
      const kind = taskKind(task);
      const badge = row.querySelector('.task-kind-badge');
      if (badge) {
        badge.classList.remove('analysis', 'action', 'execution');
        badge.classList.add(kind);
        badge.textContent = kind === 'analysis' ? 'Análise' : 'Execução';
      }
      row.dataset.taskId = task.id || '';
    });
  }

  if (taskTableBody) {
    let scheduled = false;
    const scheduleEnhancement = () => {
      if (scheduled) return;
      scheduled = true;
      window.requestAnimationFrame(() => {
        scheduled = false;
        if (document.querySelector('#tasks-view.active')) enhanceTaskKindColumn();
      });
    };
    document.addEventListener('devpilot:tasks-rendered', scheduleEnhancement);
    if (document.querySelector('#tasks-view.active')) scheduleEnhancement();
  }

  window.__devpilotCanonicalExecutionSubmitV30 = true;
  console.info('[DevPilot] Execução Submit V34 canônico ativo');
})();

/* Runtime Experience V13: legado temporário; carregado somente após intenção explícita no modal. */
(() => {
  if (
    window.__devpilotRuntimeExperienceV13 ||
    document.querySelector('script[data-runtime-experience-v13]')
  ) return;

  const script = document.createElement('script');
  script.src = '/assets/runtime-experience-v13.js?v=20260830-direct-1';
  script.async = true;
  script.dataset.runtimeExperienceV13 = '1';
  document.head.appendChild(script);
})();