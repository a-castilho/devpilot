const state = {
  token: localStorage.getItem('devpilot-token') || '',
  overview: {},
  projects: [],
  tasks: [],
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>'"]/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
})[character]);
const slugify = value => String(value || '')
  .normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
  .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 100);

function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.classList.add('show');
  setTimeout(() => element.classList.remove('show'), 3000);
}

function apiError(detail) {
  if (Array.isArray(detail)) {
    return detail.map(item => {
      const field = (item.loc || []).filter(part => part !== 'body').join('.');
      return `${field ? `${field}: ` : ''}${item.msg || 'valor inválido'}`;
    }).join(' · ');
  }
  if (detail && typeof detail === 'object') return detail.message || JSON.stringify(detail);
  return detail || 'Falha na operação';
}

async function api(path, options = {}) {
  const headers = {'Authorization': `Bearer ${state.token}`, ...options.headers};
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(`/api${path}`, {...options, headers});
  if (response.status === 401) {
    $('#auth-modal').showModal();
    throw new Error('Autenticação necessária');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(apiError(data.detail));
  return data;
}

function showView(name) {
  $$('.view').forEach(view => view.classList.toggle('active', view.id === `${name}-view`));
  $$('.nav').forEach(item => item.classList.toggle('active', item.dataset.view === name));
  $('#page-title').textContent = {
    overview: 'Visão geral', studio: 'Estúdio IA', projects: 'Projetos',
    tasks: 'Desenvolvimento', providers: 'Modelos e credenciais', audit: 'Auditoria',
  }[name];
  if (name === 'providers') loadProviders();
  if (name === 'audit') loadAudit();
}

function status(value) {
  return `<span class="status ${esc(value)}">${esc(String(value).replaceAll('_', ' '))}</span>`;
}

function formatNumber(value) {
  const notation = value >= 100000 ? 'compact' : 'standard';
  return new Intl.NumberFormat('pt-BR', {notation}).format(value || 0);
}

function formatDuration(seconds) {
  if (!Number.isFinite(Number(seconds))) return '—';
  const minutes = Math.max(1, Math.round(Number(seconds) / 60));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  return remaining ? `${hours}h ${remaining}min` : `${hours}h`;
}

function formatEta(task) {
  if (!task.expected_completion_at) return '—';
  return `<strong>~${formatDuration(task.estimated_seconds)}</strong><br><small>${new Date(task.expected_completion_at).toLocaleString('pt-BR')}</small>`;
}

async function load() {
  try {
    const [overview, projects, tasks] = await Promise.all([
      api('/overview'), api('/projects'), api('/tasks'),
    ]);
    state.overview = overview;
    state.projects = projects;
    state.tasks = tasks;
    renderOverview();
    renderProjects();
    renderTasks();
    fillProjects();
  } catch (error) {
    if (state.token) toast(error.message);
  }
}

function renderOverview() {
  const overview = state.overview;
  const usage = overview.usage || {};
  const metrics = [
    ['Projetos', overview.projects], ['Tarefas', overview.tasks],
    ['Em andamento', overview.active], ['Concluídas', overview.completed],
    ['Tokens usados', formatNumber(usage.total_tokens)],
    ['Tempo médio', formatDuration(overview.average_duration_seconds)],
    ['Fim da fila', formatDuration(overview.queue_eta_seconds)],
  ];
  $('#metrics').innerHTML = metrics
    .map(([name, value]) => `<div class="metric"><span>${name}</span><strong>${value}</strong></div>`)
    .join('');
  $('#recent-tasks').innerHTML = state.tasks.slice(0, 5).map(task => `
    <div class="list-row"><div><strong>${esc(task.title)}</strong>
    <p>${new Date(task.created_at).toLocaleString('pt-BR')} · ${esc(task.source)}</p></div>
    ${status(task.status)}</div>`).join('') || '<div class="empty">Nenhuma tarefa ainda.</div>';
  const card = $('#execution-card');
  card.classList.toggle('warning', overview.execution_enabled && !overview.execution_ready);
  card.classList.toggle('disabled', !overview.execution_enabled);
  $('#execution-status').textContent = overview.execution_ready
    ? 'Ativo — desenvolvimento automático'
    : overview.execution_enabled
      ? 'Aguardando conexão OpenAI'
      : 'Pausado — habilite a execução';
}

function renderProjects() {
  $('#projects-list').innerHTML = state.projects.map(project => `
    <article class="project-card"><span class="eyebrow">${esc(project.status).toUpperCase()}</span>
    <h3>${esc(project.name)}</h3><p>${esc(project.description || 'Sem descrição')}</p>
    <code>${esc(project.repository_url)}</code><div class="list-row">
    <small>Branch ${esc(project.default_branch)}</small><div>
    <button class="link analyze" data-id="${project.id}">Analisar</button>
    <button class="link" data-project-task="${project.id}">Nova tarefa</button></div></div></article>`).join('')
    || '<div class="empty">Conecte seu primeiro repositório.</div>';
  $$('[data-project-task]').forEach(button => {
    button.onclick = () => {
      fillProjects(button.dataset.projectTask);
      $('#task-modal').showModal();
    };
  });
  $$('.analyze').forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/projects/${button.dataset.id}/analyze`, {method: 'POST'});
        toast('Análise enfileirada; o relatório aparecerá em Desenvolvimento');
        load();
      } catch (error) { toast(error.message); }
    };
  });
}

function renderTasks() {
  const finalStates = new Set(['completed', 'failed']);
  $('#tasks-table').innerHTML = state.tasks.map(task => {
    const actions = [];
    if (task.status === 'awaiting_approval') {
      actions.push(`<button class="primary approve" data-id="${task.id}">Aprovar</button>`);
    }
    if (task.run_count > 0) {
      actions.push(`<button class="ghost report" data-id="${task.id}">Relatório</button>`);
    }
    return `<tr><td><strong>${esc(task.title)}</strong><br>
      <small>${new Date(task.created_at).toLocaleString('pt-BR')}</small></td>
      <td>${esc(task.source)}</td><td>${status(task.status)}</td>
      <td><input class="priority-input" data-id="${task.id}" type="number" min="0" max="100"
        value="${task.priority}" ${finalStates.has(task.status) ? 'disabled' : ''} aria-label="Prioridade de ${esc(task.title)}"></td>
      <td>${formatEta(task)}</td><td><div class="table-actions">${actions.join('') || '—'}</div></td></tr>`;
  }).join('') || '<tr><td colspan="6" class="empty">Nenhuma tarefa registrada.</td></tr>';
  $$('.priority-input').forEach(input => {
    input.onchange = async () => {
      try {
        await api(`/tasks/${input.dataset.id}`, {
          method: 'PATCH', body: JSON.stringify({priority: Number(input.value)}),
        });
        toast('Prioridade atualizada e fila recalculada');
        load();
      } catch (error) { toast(error.message); load(); }
    };
  });
  $$('.approve').forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/tasks/${button.dataset.id}/approve`, {method: 'POST'});
        toast('Tarefa aprovada e enfileirada');
        load();
      } catch (error) { toast(error.message); }
    };
  });
  $$('.report').forEach(button => { button.onclick = () => openReport(button.dataset.id); });
}

async function openReport(taskId) {
  try {
    const report = await api(`/tasks/${taskId}/report`);
    $('#report-title').textContent = report.task.title;
    $('#report-content').innerHTML = report.runs.map(run => `
      <article class="run-report"><div class="panel-title"><div>${status(run.status)}</div>
      <time>${new Date(run.started_at).toLocaleString('pt-BR')}</time></div>
      <div class="run-metrics"><span>Tempo <b>${formatDuration(run.duration_seconds)}</b></span>
      <span>Tokens <b>${formatNumber(run.usage.total_tokens)}</b></span>
      <span>Branch <b>${esc(run.branch || '—')}</b></span></div>
      <h4>Resposta da IA</h4><pre>${esc(run.output || run.summary || 'Sem resposta textual.')}</pre>
    </article>`).join('') || '<div class="empty">A execução ainda não produziu relatório.</div>';
    $('#report-modal').showModal();
  } catch (error) { toast(error.message); }
}

function fillProjects(selected = '') {
  const options = state.projects.map(project =>
    `<option value="${project.id}" ${project.id === selected ? 'selected' : ''}>${esc(project.name)}</option>`
  ).join('');
  $('#task-project').innerHTML = options;
  $('#voice-project').innerHTML = options;
}

async function loadProviders() {
  try {
    const data = await api('/providers');
    $('#providers-list').innerHTML = data.map(provider => `
      <article class="project-card"><span class="eyebrow">${provider.enabled ? 'ATIVO' : 'PAUSADO'}</span>
      <h3>${esc(provider.label)}</h3><p>${esc(provider.provider)} · ${provider.models.map(esc).join(', ') || 'credencial operacional'}</p>
      <code>••••••••••••••••</code></article>`).join('') || '<div class="empty">Nenhum provedor conectado.</div>';
  } catch (error) { toast(error.message); }
}

async function loadAudit() {
  try {
    const data = await api('/audit');
    $('#audit-list').innerHTML = data.map(event => `
      <div class="audit"><i></i><div><strong>${esc(event.action)}</strong><br>
      <small>${esc(event.actor)} · ${esc(event.outcome)} · hash ${event.event_hash.slice(0, 10)}</small></div>
      <time>${new Date(event.created_at).toLocaleString('pt-BR')}</time></div>`).join('')
      || '<div class="empty">A trilha de auditoria começará na primeira ação.</div>';
  } catch (error) { toast(error.message); }
}

$$('[data-view]').forEach(button => { button.onclick = () => showView(button.dataset.view); });
$$('[data-open]').forEach(button => { button.onclick = () => $(`#${button.dataset.open}`).showModal(); });
$$('dialog .close').forEach(button => { button.onclick = () => button.closest('dialog').close(); });
$('#refresh').onclick = load;
$('#save-token').onclick = () => {
  state.token = $('#token').value;
  localStorage.setItem('devpilot-token', state.token);
  setTimeout(load);
};

const projectForm = $('#project-form');
const projectName = projectForm.elements.name;
const projectSlug = projectForm.elements.slug;
let slugEdited = false;
projectSlug.oninput = () => { slugEdited = true; projectSlug.value = slugify(projectSlug.value); };
projectName.oninput = () => { if (!slugEdited) projectSlug.value = slugify(projectName.value); };

projectForm.onsubmit = async event => {
  event.preventDefault();
  const form = new FormData(event.target);
  const submit = $('button[type="submit"]', event.target);
  const autoStart = form.get('auto_start') === 'on';
  const payload = {
    name: String(form.get('name')).trim(), slug: slugify(form.get('slug')),
    repository_url: String(form.get('repository_url')).trim(),
    description: String(form.get('description')).trim(), agents_md: String(form.get('agents_md')),
    default_branch: String(form.get('default_branch')).trim(), auto_start: autoStart,
    generate_agents_md: form.get('generate_agents_md') === 'on',
    codex_config: {model: String(form.get('model')).trim(), reasoning_effort: 'medium', timeout_seconds: 1800},
  };
  submit.disabled = true;
  try {
    await api('/projects', {method: 'POST', body: JSON.stringify(payload)});
    event.target.closest('dialog').close(); event.target.reset(); slugEdited = false;
    toast(autoStart ? 'Projeto criado e desenvolvimento enfileirado' : 'Projeto conectado');
    load();
  } catch (error) { toast(error.message); } finally { submit.disabled = false; }
};

$('#studio-form').onsubmit = async event => {
  event.preventDefault();
  const form = new FormData(event.target);
  const name = String(form.get('name')).trim();
  const description = [
    `Objetivo: ${String(form.get('objective')).trim()}`,
    `Tecnologia preferida: ${String(form.get('stack')).trim() || 'definir após análise'}`,
    `Restrições e critérios: ${String(form.get('constraints')).trim() || 'aplicar padrões do projeto'}`,
  ].join('\n\n');
  const submit = $('button[type="submit"]', event.target);
  submit.disabled = true;
  try {
    await api('/projects', {method: 'POST', body: JSON.stringify({
      name, slug: slugify(name), repository_url: String(form.get('repository_url')).trim(),
      description, agents_md: '', default_branch: 'main', auto_start: true,
      generate_agents_md: true,
      codex_config: {model: String(form.get('model')).trim(), reasoning_effort: 'medium', timeout_seconds: 1800},
    })});
    event.target.reset();
    toast(state.overview.execution_ready
      ? 'Projeto criado; a IA iniciou o desenvolvimento'
      : 'Projeto criado e enfileirado; conecte a OpenAI e habilite a execução');
    await load(); showView('tasks');
  } catch (error) { toast(error.message); } finally { submit.disabled = false; }
};

$('#task-form').onsubmit = async event => {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = {
    project_id: form.get('project_id'), title: form.get('title'), prompt: form.get('prompt'),
    priority: Number(form.get('priority')), requires_approval: form.get('requires_approval') === 'on',
    source: 'dashboard',
  };
  try {
    await api('/tasks', {method: 'POST', body: JSON.stringify(payload)});
    event.target.closest('dialog').close(); event.target.reset();
    toast('Tarefa registrada'); load();
  } catch (error) { toast(error.message); }
};

$('#provider-form').onsubmit = async event => {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = {
    provider: form.get('provider'), label: form.get('label'), api_key: form.get('api_key'),
    models: String(form.get('models')).split(',').map(value => value.trim()).filter(Boolean),
  };
  try {
    await api('/providers', {method: 'POST', body: JSON.stringify(payload)});
    event.target.closest('dialog').close(); event.target.reset();
    toast('Conexão protegida e salva'); loadProviders(); load();
  } catch (error) { toast(error.message); }
};

async function openVoice() {
  $('#voice-modal').showModal();
  try {
    const capability = await api('/voice/capabilities');
    $('#voice-capability').textContent = capability.message;
    $('#voice-capability').classList.toggle('ready', capability.browser_speech);
  } catch (error) { $('#voice-capability').textContent = error.message; }
}

$('#voice-hero').onclick = openVoice;
$('#voice-dock').onclick = openVoice;
let recognition;
$('#voice-start').onclick = () => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return toast('Reconhecimento de voz indisponível neste navegador');
  recognition = new SpeechRecognition();
  recognition.lang = 'pt-BR'; recognition.interimResults = true; recognition.continuous = false;
  $('#voice-status').textContent = 'Ouvindo…';
  recognition.onresult = event => {
    $('#voice-transcript').value = [...event.results].map(result => result[0].transcript).join(' ');
  };
  recognition.onend = () => { $('#voice-status').textContent = 'Transcrição pronta. Revise antes de enviar.'; };
  recognition.onerror = () => toast('Não foi possível capturar o áudio');
  recognition.start();
};

$('#voice-send').onclick = async () => {
  const transcript = $('#voice-transcript').value.trim();
  const project_id = $('#voice-project').value;
  if (!transcript) return toast('Fale ou digite um comando');
  try {
    const data = await api('/voice/commands', {
      method: 'POST', body: JSON.stringify({transcript, project_id}),
    });
    $('#voice-modal').close(); toast(data.message);
    speechSynthesis.speak(new SpeechSynthesisUtterance('Comando registrado. Revise e aprove antes da execução.'));
    load();
  } catch (error) { toast(error.message); }
};

if (!state.token) $('#auth-modal').showModal(); else load();
