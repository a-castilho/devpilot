const state = {
  token: localStorage.getItem('devpilot-token') || '',
  currentUser: null,
  organizations: [],
  projects: [],
  tasks: [],
  tasksLoadedAll: false,
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
  const response = await fetch(`/api${path}`, {...options, headers});
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

function showView(name) {
  if (name === 'organizations' && !isSuperAdmin()) {
    toast('Acesso exclusivo do Super Admin');
    return;
  }
  $$('.view').forEach(view => view.classList.toggle('active', view.id === `${name}-view`));
  $$('.nav').forEach(nav => nav.classList.toggle('active', nav.dataset.view === name));
  const title = $('#page-title');
  if (title) {
    title.textContent = {
      overview: 'Visão geral', organizations: 'Organizações', projects: 'Projetos',
      tasks: 'Desenvolvimento', providers: 'Modelos de IA', reports: 'Relatórios', audit: 'Auditoria',
    }[name] || title.textContent;
  }
  if (name === 'organizations') renderOrganizations();
  if (name === 'tasks') {
    renderTasks();
    void loadAllTasks();
  }
  if (name === 'providers') void loadProviders();
  if (name === 'audit') void loadAudit();
}

function status(value) {
  return `<span class="status ${esc(value)}">${esc(String(value).replaceAll('_', ' '))}</span>`;
}

async function load() {
  if (!state.token) return;
  try {
    state.currentUser = await api('/auth/me');
    applyRoleVisibility();
    const [overview, projects, tasks] = await Promise.all([
      api('/overview'),
      api('/projects'),
      api('/tasks?limit=5'),
    ]);
    state.organizations = isSuperAdmin() ? await api('/organizations') : [];
    state.projects = Array.isArray(projects) ? projects : [];
    state.tasks = Array.isArray(tasks) ? tasks : [];
    state.tasksLoadedAll = false;
    renderOverview(overview || {});
    renderOrganizations();
    renderProjects();
    renderTasks();
    if ($('#tasks-view')?.classList.contains('active')) void loadAllTasks();
    fillProjects();
    fillOrganizations();
  } catch (error) {
    if (state.token) toast(error.message || 'Falha ao carregar o DevPilot');
  }
}

function taskInstructions(task) {
  const prompt = String(task?.prompt || '').trim();
  if (!prompt) return '';
  return `<details class="task-instructions"><summary>Ver instruções da análise</summary><div class="task-instructions-content"><span class="eyebrow">INSTRUÇÕES CAPTURADAS</span><p>${esc(prompt)}</p></div></details>`;
}

function renderOverview(overview) {
  const metrics = $('#metrics');
  if (metrics) {
    metrics.innerHTML = [
      ['Projetos', overview.projects], ['Tarefas', overview.tasks],
      ['Em andamento', overview.active], ['Concluídas', overview.completed],
    ].map(([name, value]) => `<div class="metric"><span>${name}</span><strong>${value ?? 0}</strong></div>`).join('');
  }
  const recent = $('#recent-tasks');
  if (recent) {
    recent.innerHTML = state.tasks.slice(0, 5).map(task => `
      <div class="recent-task"><div class="list-row"><div><strong>${esc(task.title)}</strong><p>${new Date(task.created_at).toLocaleString('pt-BR')} · ${esc(task.source)}</p></div>${status(task.status)}</div>${taskInstructions(task)}</div>
    `).join('') || '<div class="empty">Nenhuma tarefa ainda.</div>';
  }
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
  $$('.sync-org').forEach(button => {
    button.onclick = () => syncOrganization(button.dataset.id, button);
  });
}

function renderProjects() {
  const target = $('#projects-list');
  if (!target) return;
  target.innerHTML = state.projects.map(project => `
    <article class="project-card"><span class="eyebrow">${esc(project.status).toUpperCase()}</span><h3>${esc(project.name)}</h3><p>${esc(project.description || 'Sem descrição')}${project.organization_id && isSuperAdmin() ? ` · ${esc(organizationName(project.organization_id))}` : ''}</p><code>${esc(project.repository_url)}</code><div class="list-row"><small>Branch ${esc(project.default_branch)}</small><div><button class="link analyze" data-id="${project.id}">Analisar</button><button class="link" data-project-task="${project.id}">Nova tarefa</button></div></div></article>
  `).join('') || '<div class="empty">Conecte seu primeiro repositório.</div>';
  $$('[data-project-task]').forEach(button => {
    button.onclick = () => {
      fillProjects(button.dataset.projectTask);
      $('#task-modal')?.showModal?.();
    };
  });
  $$('.analyze').forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/projects/${button.dataset.id}/analyze`, {method: 'POST'});
        toast('Análise técnica enfileirada');
        await load();
      } catch (error) {
        toast(error.message);
      }
    };
  });
}

async function loadAllTasks() {
  if (state.tasksLoadedAll) return;
  if (state.tasksLoading) return state.tasksLoading;
  state.tasksLoading = api('/tasks?limit=20')
    .then(tasks => {
      state.tasks = Array.isArray(tasks) ? tasks : [];
      state.tasksLoadedAll = state.tasks.length < 20;
      renderTasks();
    })
    .catch(error => toast(error.message))
    .finally(() => { state.tasksLoading = null; });
  return state.tasksLoading;
}

function renderTasks() {
  const table = $('#tasks-table');
  if (!table) return;
  table.innerHTML = state.tasks.map(task => `
    <tr class="task-main-row"><td><strong>${esc(task.title)}</strong><br><small>${new Date(task.created_at).toLocaleString('pt-BR')}</small></td><td>${esc(task.source)}</td><td>${status(task.status)}</td><td>${task.priority}</td><td>${task.status === 'awaiting_approval' ? `<button class="primary approve" data-id="${task.id}">Aprovar</button>` : '—'}</td></tr><tr class="task-instructions-row"><td colspan="5">${taskInstructions(task) || '<span class="task-instructions-empty">Sem instruções registradas.</span>'}</td></tr>
  `).join('') || '<tr><td colspan="5" class="empty">Nenhuma tarefa registrada.</td></tr>';
  $$('.approve').forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/tasks/${button.dataset.id}/approve`, {method: 'POST'});
        toast('Tarefa aprovada e enfileirada');
        await load();
      } catch (error) {
        toast(error.message);
      }
    };
  });
  if (typeof window.renderTaskAnalytics === 'function') window.renderTaskAnalytics();
}

function fillProjects(selected = '') {
  const options = state.projects.map(project => `<option value="${project.id}" ${String(project.id) === String(selected) ? 'selected' : ''}>${esc(project.name)}</option>`).join('');
  const taskProject = $('#task-project');
  const voiceProject = $('#voice-project');
  if (taskProject) taskProject.innerHTML = options;
  if (voiceProject) voiceProject.innerHTML = options;
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
    await load();
  } catch (error) {
    toast(error.message);
    await load();
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
    const data = await api('/audit');
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
    button.onclick = () => {
      if (button.dataset.open === 'organization-modal' && !isSuperAdmin()) return toast('Acesso exclusivo do Super Admin');
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
      await load();
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
      await load();
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
      await load();
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

  const openVoice = () => $('#voice-modal')?.showModal?.();
  const voiceHero = $('#voice-hero');
  const voiceDock = $('#voice-dock');
  if (voiceHero) voiceHero.onclick = openVoice;
  if (voiceDock) voiceDock.onclick = openVoice;

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
      await load();
    } catch (error) {
      toast(error.message);
    }
  };
}

bindCoreControls();
if (state.token) void load();
else $('#auth-modal')?.showModal?.();

/* Navegação mobile sem MutationObserver autorreferente. */
(() => {
  const sidebar = document.querySelector('.sidebar');
  const nav = sidebar?.querySelector('nav');
  if (!sidebar || !nav || sidebar.querySelector('.mobile-nav-arrow')) return;

  const makeArrow = (direction, label, symbol) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `mobile-nav-arrow mobile-nav-arrow-${direction}`;
    button.setAttribute('aria-label', label);
    button.setAttribute('title', label);
    button.textContent = symbol;
    return button;
  };

  const previous = makeArrow('prev', 'Navegar para a esquerda', '‹');
  const next = makeArrow('next', 'Navegar para a direita', '›');
  sidebar.insertBefore(previous, nav);
  sidebar.insertBefore(next, nav.nextSibling);

  const visibleItems = () => [...nav.querySelectorAll('.nav')].filter(item => {
    if (item.hidden) return false;
    const style = window.getComputedStyle(item);
    return style.display !== 'none' && style.visibility !== 'hidden';
  });

  const centerItem = item => {
    if (!item) return;
    const left = item.offsetLeft - Math.max(0, (nav.clientWidth - item.offsetWidth) / 2);
    nav.scrollTo({left: Math.max(0, left), behavior: 'auto'});
  };

  const sync = () => {
    const items = visibleItems();
    if (!items.length) {
      previous.disabled = true;
      next.disabled = true;
      return;
    }
    let index = items.findIndex(item => item.classList.contains('active'));
    if (index < 0) index = 0;
    previous.disabled = index <= 0;
    next.disabled = index >= items.length - 1;
    centerItem(items[index]);
  };

  const move = direction => {
    const items = visibleItems();
    if (!items.length) return;
    let index = items.findIndex(item => item.classList.contains('active'));
    if (index < 0) index = 0;
    const targetIndex = Math.max(0, Math.min(items.length - 1, index + direction));
    const target = items[targetIndex];
    if (!target || targetIndex === index) return;
    target.click();
    window.requestAnimationFrame(sync);
  };

  previous.addEventListener('click', () => move(-1));
  next.addEventListener('click', () => move(1));
  nav.addEventListener('click', () => window.requestAnimationFrame(sync));
  window.addEventListener('resize', sync, {passive: true});
  document.addEventListener('devpilot:feature-ready', () => window.requestAnimationFrame(sync));
  sync();
})();

/* Indicadores de estado: observa somente nós adicionados; não observa atributos. */
(() => {
  const STYLE_ID = 'devpilot-state-loaders';
  const activeStates = new Set(['running','processing','in_progress','in progress','analyzing','analysing','executing','syncing','loading','queued','pending','starting','deploying']);
  const waitingStates = new Set(['blocked','awaiting_approval','awaiting approval','paused','waiting']);
  const successStates = new Set(['completed','complete','success','succeeded','done','review','approved','active','ativo']);
  const errorStates = new Set(['failed','failure','error','cancelled','canceled','rejected']);
  const normalize = value => String(value || '').trim().toLowerCase().replace(/[-]+/g, '_').replace(/\s+/g, ' ');

  function installStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .status{align-items:center;gap:7px;min-height:24px;line-height:1;letter-spacing:.02em;transition:border-color .2s ease,background .2s ease,color .2s ease,box-shadow .2s ease}
      .state-loader{position:relative;display:inline-grid;place-items:center;flex:0 0 12px;width:12px;height:12px;border-radius:50%;color:currentColor}
      .state-loader::before,.state-loader::after{content:'';position:absolute;inset:0;border-radius:inherit}
      .status.state-active{color:#65ead4;background:#1aa7901f;box-shadow:inset 0 0 0 1px #36d7c02b}
      .status.state-active .state-loader::before{border:2px solid currentColor;opacity:.2}
      .status.state-active .state-loader::after{border:2px solid transparent;border-top-color:currentColor;border-right-color:currentColor;animation:devpilot-state-spin .8s linear infinite;box-shadow:0 0 9px currentColor}
      .status.state-waiting{color:#ffc86f;background:#ffbb551b;box-shadow:inset 0 0 0 1px #ffbb5524}
      .status.state-waiting .state-loader::before{inset:2px;background:currentColor;box-shadow:0 0 8px currentColor;animation:devpilot-state-pulse 1.35s ease-in-out infinite}
      .status.state-success{color:#65ead4;background:#21a6961f}
      .status.state-success .state-loader::before{content:'✓';inset:auto;position:static;font-size:11px;font-weight:950;line-height:1}
      .status.state-error{color:#ff8796;background:#ff657719}
      .status.state-error .state-loader::before{content:'×';inset:auto;position:static;font-size:14px;font-weight:950;line-height:1}
      .status.state-neutral .state-loader::before{inset:3px;background:currentColor;opacity:.72}
      @keyframes devpilot-state-spin{to{transform:rotate(360deg)}}
      @keyframes devpilot-state-pulse{0%,100%{transform:scale(.7);opacity:.45}50%{transform:scale(1);opacity:1}}
      @media (prefers-reduced-motion:reduce){.status .state-loader::before,.status .state-loader::after{animation:none!important}}
    `;
    document.head.appendChild(style);
  }

  function classify(raw) {
    const value = normalize(raw);
    if (activeStates.has(value) || activeStates.has(value.replaceAll(' ', '_'))) return 'active';
    if (waitingStates.has(value) || waitingStates.has(value.replaceAll(' ', '_'))) return 'waiting';
    if (successStates.has(value) || successStates.has(value.replaceAll(' ', '_'))) return 'success';
    if (errorStates.has(value) || errorStates.has(value.replaceAll(' ', '_'))) return 'error';
    return 'neutral';
  }

  function decorate(element) {
    if (!(element instanceof HTMLElement) || !element.classList.contains('status')) return;
    const existing = element.querySelector(':scope > .state-loader');
    const raw = element.dataset.stateValue || element.textContent.trim();
    const kind = classify(raw);
    element.dataset.stateValue = raw;
    element.classList.remove('state-active','state-waiting','state-success','state-error','state-neutral');
    element.classList.add(`state-${kind}`);
    element.setAttribute('aria-label', `Estado: ${raw.replaceAll('_', ' ')}`);
    if (!existing) {
      const loader = document.createElement('span');
      loader.className = 'state-loader';
      loader.setAttribute('aria-hidden', 'true');
      element.prepend(loader);
    }
  }

  function scan(root = document) {
    if (root instanceof HTMLElement && root.matches('.status')) decorate(root);
    root.querySelectorAll?.('.status').forEach(decorate);
  }

  installStyles();
  scan();
  const observer = new MutationObserver(records => {
    records.forEach(record => record.addedNodes.forEach(node => {
      if (node.nodeType === Node.ELEMENT_NODE) scan(node);
    }));
  });
  observer.observe(document.body, {childList: true, subtree: true});
})();