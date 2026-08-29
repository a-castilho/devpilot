const state = {
  token: localStorage.getItem('devpilot-token') || '',
  currentUser: null,
  organizations: [],
  projects: [],
  tasks: [],
  tasksLoadedAll: false,
  dashboardLoading: null,
  projectsLoading: null,
  organizationsLoading: null,
  tasksLoading: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
}[char]));

function toast(message) {
  const element = $('#toast');
  if (!element) return;
  element.textContent = message;
  element.classList.add('show');
  window.setTimeout(() => element.classList.remove('show'), 3200);
}

function errorDetail(data) {
  if (typeof data?.detail === 'string') return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map(item => item.msg || 'Entrada inválida').join(' · ');
  return 'Falha na operação';
}

async function api(path, options = {}) {
  const headers = {Authorization: `Bearer ${state.token}`, ...options.headers};
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(`/api${path}`, {...options, headers, cache: options.cache || 'no-store'});
  if (response.status === 401) {
    localStorage.removeItem('devpilot-token');
    $('#auth-modal')?.showModal?.();
    throw new Error('Autenticação necessária');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorDetail(data));
  return data;
}

function isSuperAdmin() {
  return String(state.currentUser?.role || '').toUpperCase() === 'SUPER_ADMIN';
}

function applyRoleVisibility() {
  const allowed = isSuperAdmin();
  const nav = $('.nav[data-view="organizations"]');
  if (nav) nav.hidden = !allowed;
  const view = $('#organizations-view');
  if (view && !allowed) view.classList.remove('active');
  const field = $('#project-organization')?.closest('label');
  if (field) field.hidden = !allowed;
  const modal = $('#organization-modal');
  if (modal && !allowed && modal.open) modal.close();
}

function status(value) {
  return `<span class="status ${esc(value)}">${esc(String(value || '').replaceAll('_', ' '))}</span>`;
}

function decorateStatuses(root = document) {
  root.querySelectorAll?.('.status').forEach(element => {
    if (element.dataset.devpilotDecorated === '1') return;
    element.dataset.devpilotDecorated = '1';
  });
}

function setActiveView(name) {
  $$('.view').forEach(view => view.classList.toggle('active', view.id === `${name}-view`));
  $$('.nav').forEach(nav => nav.classList.toggle('active', nav.dataset.view === name));
  const title = $('#page-title');
  if (title) {
    title.textContent = {
      overview: 'Visão geral', organizations: 'Organizações', projects: 'Projetos',
      tasks: 'Desenvolvimento', providers: 'Modelos de IA', reports: 'Relatórios', audit: 'Auditoria',
    }[name] || title.textContent;
  }
}

function showView(name) {
  if (name === 'organizations' && !isSuperAdmin()) {
    toast('Acesso exclusivo do Super Admin');
    return;
  }
  setActiveView(name);
  if (name === 'projects') void loadProjects();
  if (name === 'organizations') void loadOrganizations();
  if (name === 'tasks') void loadAllTasks();
  if (name === 'providers') void loadProviders();
  if (name === 'audit') void loadAudit();
}

async function loadDashboard() {
  if (!state.token) return false;
  if (state.dashboardLoading) return state.dashboardLoading;

  state.dashboardLoading = (async () => {
    try {
      // Pós-login deliberadamente pequeno: somente identidade, visão geral
      // e cinco tarefas recentes são carregadas nesta etapa.
      state.currentUser = await api('/auth/me');
      applyRoleVisibility();
      const [overview, recentTasks] = await Promise.all([
        api('/overview'),
        api('/ui/tasks?limit=20'),
      ]);
      state.tasks = Array.isArray(recentTasks) ? recentTasks : [];
      state.tasksLoadedAll = false;
      renderOverview(overview || {});
      if ($('#tasks-view')?.classList.contains('active')) renderTasks();
      return true;
    } catch (error) {
      if (state.token) toast(error.message || 'Falha ao carregar a visão geral');
      return false;
    } finally {
      state.dashboardLoading = null;
    }
  })();

  return state.dashboardLoading;
}

async function loadProjects() {
  if (state.projectsLoading) return state.projectsLoading;
  const target = $('#projects-list');
  if (target && !state.projects.length) target.innerHTML = '<div class="empty">Carregando projetos…</div>';

  state.projectsLoading = (async () => {
    try {
      const projects = await api('/ui/projects?limit=50');
      state.projects = Array.isArray(projects) ? projects : [];
      renderProjects();
      fillProjects();
      return state.projects;
    } catch (error) {
      if (target) target.innerHTML = `<div class="empty">${esc(error.message)}</div>`;
      toast(error.message);
      return [];
    } finally {
      state.projectsLoading = null;
    }
  })();

  return state.projectsLoading;
}

async function loadOrganizations() {
  if (!isSuperAdmin()) return [];
  if (state.organizationsLoading) return state.organizationsLoading;
  const target = $('#organizations-list');
  if (target && !state.organizations.length) target.innerHTML = '<div class="empty">Carregando organizações…</div>';

  state.organizationsLoading = (async () => {
    try {
      const organizations = await api('/organizations');
      state.organizations = Array.isArray(organizations) ? organizations : [];
      renderOrganizations();
      fillOrganizations();
      return state.organizations;
    } catch (error) {
      if (target) target.innerHTML = `<div class="empty">${esc(error.message)}</div>`;
      toast(error.message);
      return [];
    } finally {
      state.organizationsLoading = null;
    }
  })();

  return state.organizationsLoading;
}

async function load() {
  await loadDashboard();
  const active = $('.view.active')?.id?.replace(/-view$/, '') || 'overview';
  if (active === 'projects') await loadProjects();
  else if (active === 'organizations') await loadOrganizations();
  else if (active === 'tasks') await loadAllTasks(true);
  else if (active === 'providers') await loadProviders();
  else if (active === 'audit') await loadAudit();
}

function renderOverview(overview) {
  const tasks = Array.isArray(state.tasks) ? state.tasks : [];
  const normalized = value => String(value || '').toLowerCase();
  const groups = {
    active: tasks.filter(task => ['running', 'in_progress', 'queued', 'approved', 'processing'].includes(normalized(task.status))),
    approvals: tasks.filter(task => normalized(task.status) === 'awaiting_approval'),
    failed: tasks.filter(task => ['failed', 'error', 'blocked'].includes(normalized(task.status))),
    completed: tasks.filter(task => ['completed', 'done', 'review'].includes(normalized(task.status))),
  };
  const total = Math.max(Number(overview.tasks || 0), tasks.length);
  const completed = Number(overview.completed ?? groups.completed.length);
  const completionRate = total ? Math.round((completed / total) * 100) : 0;

  const metrics = $('#metrics');
  if (metrics) {
    const values = [
      ['Projetos', overview.projects ?? 0, 'Repositórios acompanhados', 'projects'],
      ['Em andamento', overview.active ?? groups.active.length, 'Execuções e fila', 'active'],
      ['Aguardando você', groups.approvals.length, 'Aprovações pendentes', 'approval'],
      ['Concluídas', completed, 'Entregas finalizadas', 'completed'],
    ];
    metrics.innerHTML = values.map(([name, value, detail, tone]) => `
      <article class="metric overview-metric ${tone}">
        <span>${esc(name)}</span><strong>${value}</strong><small>${esc(detail)}</small>
      </article>
    `).join('');
  }

  const summary = $('#overview-summary');
  if (summary) {
    summary.textContent = total
      ? `${total} tarefas acompanhadas em ${overview.projects ?? 0} projetos. ${groups.active.length} estão em movimento agora.`
      : 'Seu ambiente está pronto. Crie uma tarefa ou conecte um projeto para começar.';
  }

  const attention = $('#attention-card');
  if (attention) {
    let content;
    if (groups.failed.length) {
      content = ['!', 'FALHA QUE PRECISA DE ATENÇÃO', `${groups.failed.length} tarefa(s) com falha`, 'Abra Desenvolvimento para consultar o motivo e os registros.', 'danger'];
    } else if (groups.approvals.length) {
      content = ['✓', 'AGUARDANDO SUA DECISÃO', `${groups.approvals.length} aprovação(ões) pendente(s)`, 'Revise a análise antes de liberar alterações no código.', 'warning'];
    } else if (groups.active.length) {
      content = ['↻', 'DEV PILOT TRABALHANDO', `${groups.active.length} tarefa(s) em andamento`, 'Você pode acompanhar cada etapa em Desenvolvimento.', 'active'];
    } else {
      content = ['✓', 'OPERAÇÃO EM DIA', 'Nada exige sua atenção agora', 'Novas atividades aparecerão aqui automaticamente.', 'success'];
    }
    attention.className = `attention-card ${content[4]}`;
    attention.innerHTML = `<span class="attention-icon">${content[0]}</span><div><small>${content[1]}</small><strong>${content[2]}</strong><p>${content[3]}</p></div>`;
    attention.onclick = () => {
      if (groups.failed.length || groups.approvals.length || groups.active.length) showView('tasks');
    };
  }

  const rate = $('#completion-rate');
  const bar = $('#completion-bar');
  if (rate) rate.textContent = `${completionRate}%`;
  if (bar) bar.style.width = `${Math.min(100, completionRate)}%`;

  const breakdown = $('#status-breakdown');
  if (breakdown) {
    breakdown.innerHTML = [
      ['Em andamento', groups.active.length, 'active'],
      ['Aguardando aprovação', groups.approvals.length, 'approval'],
      ['Com falha', groups.failed.length, 'failed'],
      ['Concluídas', completed, 'completed'],
    ].map(([label, value, tone]) => `<span class="breakdown-item ${tone}"><i></i><b>${value}</b> ${label}</span>`).join('');
  }

  const recent = $('#recent-tasks');
  if (recent) {
    recent.innerHTML = tasks.slice(0, 6).map(task => `
      <button type="button" class="recent-task overview-task" data-view="tasks">
        <span class="task-state ${esc(normalized(task.status))}"></span>
        <span class="task-copy"><strong>${esc(task.title)}</strong><small>${new Date(task.created_at).toLocaleString('pt-BR')} · ${esc(task.source || 'dashboard')}</small></span>
        ${status(task.status)}
      </button>
    `).join('') || '<div class="empty">Nenhuma atividade ainda. Crie o primeiro desenvolvimento.</div>';
    decorateStatuses(recent);
    $$('[data-view="tasks"]', recent).forEach(button => button.onclick = () => showView('tasks'));
  }

  const overviewRefresh = $('#overview-refresh');
  if (overviewRefresh) overviewRefresh.onclick = () => void loadDashboard();
}
function organizationName(id) {
  return state.organizations.find(item => item.id === id)?.name || '';
}

function renderOrganizations() {
  const target = $('#organizations-list');
  if (!target) return;
  if (!isSuperAdmin()) {
    target.innerHTML = '';
    return;
  }
  target.innerHTML = state.organizations.map(org => `
    <article class="project-card"><span class="eyebrow">GITHUB · ${esc(org.sync_status).toUpperCase()}</span><h3>${esc(org.name)}</h3><p>@${esc(org.external_login)} · ${org.repository_count} repositórios · ${org.project_count} projetos</p><code>${org.has_credentials ? 'credencial de leitura protegida' : 'sem credencial · somente dados públicos'}</code>${org.last_sync_error ? `<p>${esc(org.last_sync_error)}</p>` : ''}<div class="list-row"><small>${org.last_synced_at ? `Sync ${new Date(org.last_synced_at).toLocaleString('pt-BR')}` : 'Ainda não sincronizado'}</small><button class="link sync-org" data-id="${org.id}">Sincronizar</button></div></article>
  `).join('') || '<div class="empty">Cadastre a primeira organização GitHub.</div>';
  $$('.sync-org', target).forEach(button => {
    button.onclick = () => void syncOrganization(button.dataset.id, button);
  });
}

function renderProjects() {
  const target = $('#projects-list');
  if (!target) return;
  target.innerHTML = state.projects.map(project => `
    <article class="project-card"><span class="eyebrow">${esc(project.status).toUpperCase()}</span><h3>${esc(project.name)}</h3><p>${esc(project.description || 'Sem descrição')}${project.organization_id && isSuperAdmin() && organizationName(project.organization_id) ? ` · ${esc(organizationName(project.organization_id))}` : ''}</p><code>${esc(project.repository_url)}</code><div class="list-row"><small>Branch ${esc(project.default_branch)}</small><div><button class="link analyze" data-id="${project.id}">Analisar</button><button class="link" data-project-task="${project.id}">Nova tarefa</button></div></div></article>
  `).join('') || '<div class="empty">Conecte seu primeiro repositório.</div>';

  $$('[data-project-task]', target).forEach(button => {
    button.onclick = async () => {
      fillProjects(button.dataset.projectTask);
      $('#task-modal')?.showModal?.();
    };
  });
  $$('.analyze', target).forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/projects/${button.dataset.id}/analyze`, {method: 'POST'});
        toast('Análise técnica enfileirada');
        await loadDashboard();
      } catch (error) {
        toast(error.message);
      }
    };
  });
}

async function loadAllTasks(force = false) {
  if (state.tasksLoading) return state.tasksLoading;
  if (state.tasksLoadedAll && !force) return state.tasks;

  state.tasksLoading = (async () => {
    try {
      const tasks = await api('/ui/tasks?limit=20');
      state.tasks = Array.isArray(tasks) ? tasks : [];
      state.tasksLoadedAll = state.tasks.length < 20;
      renderTasks();
      return state.tasks;
    } catch (error) {
      toast(error.message);
      return [];
    } finally {
      state.tasksLoading = null;
    }
  })();

  return state.tasksLoading;
}

async function loadTaskInstructions(taskId, container, button) {
  if (!taskId || !container || container.dataset.loaded === '1') return;
  button.disabled = true;
  button.textContent = 'Carregando…';
  try {
    const task = await api(`/ui/tasks/${encodeURIComponent(taskId)}`);
    const pre = document.createElement('pre');
    pre.className = 'task-instructions-content';
    pre.style.whiteSpace = 'pre-wrap';
    pre.style.overflowWrap = 'anywhere';
    pre.textContent = String(task.prompt || 'Sem instruções registradas.');
    container.replaceChildren(pre);
    container.dataset.loaded = '1';
  } catch (error) {
    button.disabled = false;
    button.textContent = 'Tentar novamente';
    toast(error.message);
  }
}

function renderTasks() {
  const table = $('#tasks-table');
  if (!table) return;
  table.innerHTML = state.tasks.map(task => `
    <tr class="task-main-row"><td><strong>${esc(task.title)}</strong><br><small>${new Date(task.created_at).toLocaleString('pt-BR')}</small></td><td>${esc(task.source)}</td><td>${status(task.status)}</td><td>${task.priority}</td><td>${task.status === 'awaiting_approval' ? `<button class="primary approve" data-id="${task.id}">Aprovar</button>` : '—'}</td></tr>
    <tr class="task-instructions-row"><td colspan="5"><div data-task-instructions="${task.id}"><button class="link task-instructions-load" type="button" data-id="${task.id}">Ver instruções da análise</button></div></td></tr>
  `).join('') || '<tr><td colspan="5" class="empty">Nenhuma tarefa registrada.</td></tr>';

  $$('.approve', table).forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/tasks/${button.dataset.id}/approve`, {method: 'POST'});
        toast('Tarefa aprovada e enfileirada');
        await loadAllTasks(true);
        await loadDashboard();
      } catch (error) {
        toast(error.message);
      }
    };
  });
  $$('.task-instructions-load', table).forEach(button => {
    button.onclick = () => {
      const container = table.querySelector(`[data-task-instructions="${CSS.escape(button.dataset.id)}"]`);
      void loadTaskInstructions(button.dataset.id, container, button);
    };
  });
  decorateStatuses(table);
  if (typeof window.renderTaskAnalytics === 'function') window.renderTaskAnalytics();
}

function fillProjects(selected = '') {
  const options = state.projects.map(project => `<option value="${project.id}" ${String(project.id) === String(selected) ? 'selected' : ''}>${esc(project.name)}</option>`).join('');
  const taskProject = $('#task-project');
  const voiceProject = $('#voice-project');
  if (taskProject) taskProject.innerHTML = options || '<option value="">Nenhum projeto carregado</option>';
  if (voiceProject) voiceProject.innerHTML = options || '<option value="">Nenhum projeto carregado</option>';
}

function fillOrganizations(selected = '') {
  const target = $('#project-organization');
  if (!target) return;
  target.innerHTML = '<option value="">Sem organização</option>' + (isSuperAdmin()
    ? state.organizations.map(org => `<option value="${org.id}" ${String(org.id) === String(selected) ? 'selected' : ''}>${esc(org.name)}</option>`).join('')
    : '');
}

async function syncOrganization(id, button) {
  if (!isSuperAdmin()) return toast('Acesso exclusivo do Super Admin');
  const original = button?.textContent;
  if (button) {
    button.disabled = true;
    button.textContent = 'Sincronizando…';
  }
  try {
    const result = await api(`/organizations/${id}/sync`, {method: 'POST', body: JSON.stringify({import_projects: true})});
    toast(`Sync concluído: ${result.repositories} repositórios, ${result.imported_projects} projetos importados`);
    state.organizations = [];
    state.projects = [];
    await loadOrganizations();
    await loadDashboard();
  } catch (error) {
    toast(error.message);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = original;
    }
  }
}

async function loadProviders() {
  const target = $('#providers-list');
  if (!target) return;
  try {
    const data = await api('/providers');
    target.innerHTML = (Array.isArray(data) ? data : []).map(provider => `
      <article class="project-card"><span class="eyebrow">${provider.enabled ? 'ATIVO' : 'PAUSADO'}</span><h3>${esc(provider.label)}</h3><p>${esc(provider.provider)} · ${(provider.models || []).map(esc).join(', ') || 'modelos automáticos'}</p><code>••••••••••••••••</code></article>
    `).join('') || '<div class="empty">Nenhum provedor conectado.</div>';
  } catch (error) {
    toast(error.message);
  }
}

async function loadAudit() {
  const target = $('#audit-list');
  if (!target) return;
  try {
    const data = await api('/audit?limit=50');
    target.innerHTML = (Array.isArray(data) ? data : []).map(item => `
      <div class="audit"><i></i><div><strong>${esc(item.action)}</strong><br><small>${esc(item.actor)} · ${esc(item.outcome)} · hash ${esc(String(item.event_hash || '').slice(0, 10))}</small></div><time>${new Date(item.created_at).toLocaleString('pt-BR')}</time></div>
    `).join('') || '<div class="empty">A trilha de auditoria começará na primeira ação.</div>';
  } catch (error) {
    toast(error.message);
  }
}

function bindCoreControls() {
  $$('[data-view]').forEach(button => {
    button.onclick = () => showView(button.dataset.view);
  });

  $$('[data-open]').forEach(button => {
    button.onclick = async () => {
      if (button.dataset.open === 'organization-modal' && !isSuperAdmin()) return toast('Acesso exclusivo do Super Admin');
      if (button.dataset.open === 'task-modal' && !state.projects.length) await loadProjects();
      if (button.dataset.open === 'organization-modal' && isSuperAdmin() && !state.organizations.length) await loadOrganizations();
      $(`#${button.dataset.open}`)?.showModal?.();
    };
  });

  $$('dialog .close').forEach(button => {
    button.onclick = () => button.closest('dialog')?.close?.();
  });

  const refresh = $('#refresh');
  if (refresh) refresh.onclick = () => void load();

  const organizationForm = $('#organization-form');
  if (organizationForm) organizationForm.onsubmit = async event => {
    event.preventDefault();
    if (!isSuperAdmin()) return toast('Acesso exclusivo do Super Admin');
    const form = new FormData(event.target);
    const payload = {name: form.get('name'), slug: form.get('slug'), github_login: form.get('github_login')};
    const accessToken = String(form.get('access_token') || '').trim();
    if (accessToken) payload.access_token = accessToken;
    try {
      const organization = await api('/organizations', {method: 'POST', body: JSON.stringify(payload)});
      event.target.closest('dialog')?.close?.();
      event.target.reset();
      toast('Organização conectada. Sincronizando repositórios…');
      await syncOrganization(organization.id);
    } catch (error) {
      toast(error.message);
    }
  };

  const projectForm = $('#project-form');
  if (projectForm) projectForm.onsubmit = async event => {
    event.preventDefault();
    const form = new FormData(event.target);
    const payload = {
      name: form.get('name'), slug: form.get('slug'), repository_url: form.get('repository_url'),
      organization_id: isSuperAdmin() ? (form.get('organization_id') || null) : null,
      description: form.get('description'), agents_md: form.get('agents_md'), default_branch: form.get('default_branch'),
      codex_config: {model: form.get('model'), reasoning_effort: 'medium', timeout_seconds: 1800},
    };
    try {
      await api('/projects', {method: 'POST', body: JSON.stringify(payload)});
      event.target.closest('dialog')?.close?.();
      event.target.reset();
      toast('Projeto conectado');
      state.projects = [];
      await loadProjects();
      await loadDashboard();
    } catch (error) {
      toast(error.message);
    }
  };

  const taskForm = $('#task-form');
  if (taskForm) taskForm.onsubmit = async event => {
    event.preventDefault();
    const form = new FormData(event.target);
    const payload = {
      project_id: form.get('project_id'), title: form.get('title'), prompt: form.get('prompt'),
      priority: Number(form.get('priority')), requires_approval: form.get('requires_approval') === 'on', source: 'dashboard',
    };
    try {
      await api('/tasks', {method: 'POST', body: JSON.stringify(payload)});
      event.target.closest('dialog')?.close?.();
      event.target.reset();
      toast('Tarefa registrada');
      await loadDashboard();
      if ($('#tasks-view')?.classList.contains('active')) await loadAllTasks(true);
    } catch (error) {
      toast(error.message);
    }
  };

  const providerForm = $('#provider-form');
  if (providerForm) providerForm.onsubmit = async event => {
    event.preventDefault();
    const form = new FormData(event.target);
    const payload = {
      provider: form.get('provider'), label: form.get('label'), api_key: form.get('api_key'),
      models: String(form.get('models') || '').split(',').map(item => item.trim()).filter(Boolean),
    };
    try {
      await api('/providers', {method: 'POST', body: JSON.stringify(payload)});
      event.target.closest('dialog')?.close?.();
      event.target.reset();
      toast('Conexão protegida e salva');
      await loadProviders();
    } catch (error) {
      toast(error.message);
    }
  };

  const openVoice = async () => {
    if (!state.projects.length) await loadProjects();
    $('#voice-modal')?.showModal?.();
  };
  const voiceHero = $('#voice-hero');
  const voiceDock = $('#voice-dock');
  if (voiceHero) voiceHero.onclick = () => void openVoice();
  if (voiceDock) voiceDock.onclick = () => void openVoice();

  let recognition;
  const voiceStart = $('#voice-start');
  if (voiceStart) voiceStart.onclick = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return toast('Reconhecimento de voz indisponível neste navegador');
    recognition = new SpeechRecognition();
    recognition.lang = 'pt-BR';
    recognition.interimResults = true;
    recognition.continuous = false;
    const voiceStatus = $('#voice-status');
    if (voiceStatus) voiceStatus.textContent = 'Ouvindo…';
    recognition.onresult = event => {
      const transcript = $('#voice-transcript');
      if (transcript) transcript.value = [...event.results].map(result => result[0].transcript).join(' ');
    };
    recognition.onend = () => {
      const statusElement = $('#voice-status');
      if (statusElement) statusElement.textContent = 'Transcrição pronta. Revise antes de enviar.';
    };
    recognition.onerror = () => toast('Não foi possível capturar o áudio');
    recognition.start();
  };

  const voiceSend = $('#voice-send');
  if (voiceSend) voiceSend.onclick = async () => {
    const transcript = $('#voice-transcript')?.value.trim() || '';
    const projectId = $('#voice-project')?.value || '';
    if (!transcript) return toast('Fale ou digite um comando');
    try {
      const data = await api('/voice/commands', {method: 'POST', body: JSON.stringify({transcript, project_id: projectId})});
      $('#voice-modal')?.close?.();
      toast(data.message);
      if ('speechSynthesis' in window && 'SpeechSynthesisUtterance' in window) {
        speechSynthesis.speak(new SpeechSynthesisUtterance('Comando registrado. Revise e aprove antes da execução.'));
      }
      await loadDashboard();
    } catch (error) {
      toast(error.message);
    }
  };
}

bindCoreControls();
if (state.token) void loadDashboard();
else $('#auth-modal')?.showModal?.();

/* Navegação mobile sem observers de atributos. */
(() => {
  const sidebar = document.querySelector('.sidebar');
  const nav = sidebar?.querySelector('nav');
  if (!sidebar || !nav || sidebar.querySelector('.mobile-nav-arrow')) return;

  const makeArrow = (direction, label, symbol) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `mobile-nav-arrow mobile-nav-arrow-${direction}`;
    button.setAttribute('aria-label', label);
    button.textContent = symbol;
    return button;
  };

  const previous = makeArrow('prev', 'Navegar para a esquerda', '‹');
  const next = makeArrow('next', 'Navegar para a direita', '›');
  sidebar.insertBefore(previous, nav);
  sidebar.insertBefore(next, nav.nextSibling);

  const visibleItems = () => [...nav.querySelectorAll('.nav')].filter(item => !item.hidden && getComputedStyle(item).display !== 'none');
  const sync = () => {
    const items = visibleItems();
    let index = items.findIndex(item => item.classList.contains('active'));
    if (index < 0) index = 0;
    previous.disabled = index <= 0;
    next.disabled = !items.length || index >= items.length - 1;
  };
  const move = direction => {
    const items = visibleItems();
    let index = items.findIndex(item => item.classList.contains('active'));
    if (index < 0) index = 0;
    const target = items[Math.max(0, Math.min(items.length - 1, index + direction))];
    if (target && target !== items[index]) target.click();
    requestAnimationFrame(sync);
  };

  previous.addEventListener('click', () => move(-1));
  next.addEventListener('click', () => move(1));
  nav.addEventListener('click', () => requestAnimationFrame(sync));
  window.addEventListener('resize', sync, {passive: true});
  document.addEventListener('devpilot:feature-ready', () => requestAnimationFrame(sync));
  sync();
})();