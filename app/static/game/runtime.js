/* Minimal shared runtime for the standalone game document. */
'use strict';

const GAME_PROJECT_KEY = 'devpilot-build-game-project';
const GAME_PIPELINE_MARKER = '[DEVPILOT_BUILD_GAME_PIPELINE_V2]';
const REPOSITORY_GATE_MARKER = '[DEVPILOT_REPOSITORY_GATE_V99]';
const REPOSITORY_READY_WAIT_MS = 120000;
const REPOSITORY_READY_POLL_MS = 1200;

const state = {
  token: localStorage.getItem('devpilot-token') || '',
  projects: [],
};

const repositoryReleaseInFlight = new Map();

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>'\"]/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '\"': '&quot;',
}[char]));
const sleep = milliseconds => new Promise(resolve => window.setTimeout(resolve, milliseconds));

function toast(message) {
  const element = $('#toast');
  if (!element) return;
  element.textContent = message;
  element.classList.add('show');
  window.setTimeout(() => element.classList.remove('show'), 4200);
}

function errorDetail(data, status = 0) {
  if (typeof data?.detail === 'string') return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map(item => item.msg || 'Entrada inválida').join(' · ');
  if (status >= 500) return `O DevPilot encontrou um erro interno (HTTP ${status}).`;
  if (status >= 400) return `A operação foi recusada (HTTP ${status}).`;
  return 'Falha na operação';
}

function networkErrorMessage(error) {
  if (error?.name === 'AbortError') {
    return 'O DevPilot demorou demais para responder. Verifique a conexão e tente novamente.';
  }
  if (navigator.onLine === false) {
    return 'O dispositivo está sem conexão com o DevPilot.';
  }
  return 'Não foi possível conectar ao DevPilot. Verifique se o servidor continua disponível e tente novamente.';
}

function standaloneRoute(path, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();
  if (method !== 'GET') return {path, kind: 'default'};

  const raw = String(path || '');
  if (raw === '/projects') {
    const selected = String(localStorage.getItem(GAME_PROJECT_KEY) || '').trim();
    const include = selected ? `&include_project_id=${encodeURIComponent(selected)}` : '';
    return {
      path: `/ui/projects?limit=50${include}`,
      kind: 'projects',
    };
  }

  if (raw.startsWith('/tasks?')) {
    const params = new URLSearchParams(raw.split('?', 2)[1] || '');
    const projectId = String(params.get('project_id') || localStorage.getItem(GAME_PROJECT_KEY) || '').trim();
    if (projectId) {
      return {
        path: `/ui/game-tasks?project_id=${encodeURIComponent(projectId)}&limit=24`,
        kind: 'game-tasks',
      };
    }
  }

  return {path: raw, kind: 'default'};
}

function normalizeStatus(value) {
  return String(value || '').trim().toLowerCase().replaceAll(' ', '_');
}

function repositoryReady(project) {
  return Boolean(String(project?.repository_url || '').trim());
}

function cachedProject(projectId) {
  const id = String(projectId || '').trim();
  return state.projects.find(project => String(project?.id) === id) || null;
}

function repositoryGatedTask(row) {
  const prompt = String(row?.prompt || '');
  return prompt.includes(REPOSITORY_GATE_MARKER)
    && normalizeStatus(row?.status) === 'awaiting_approval';
}

async function requestJson(path, options = {}, attempt = 0) {
  const method = String(options.method || 'GET').toUpperCase();
  const controller = options.signal ? null : new AbortController();
  const timeoutId = controller
    ? window.setTimeout(() => controller.abort(), Number(options.timeoutMs || 10000))
    : 0;

  const headers = {
    Authorization: `Bearer ${state.token}`,
    ...(options.headers || {}),
  };

  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }

  let response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      method,
      headers,
      cache: options.cache || 'no-store',
      signal: options.signal || controller?.signal,
    });
  } catch (error) {
    if (timeoutId) window.clearTimeout(timeoutId);

    if (method === 'GET' && options.retry !== false && attempt === 0 && navigator.onLine !== false) {
      await sleep(250);
      return requestJson(path, options, attempt + 1);
    }

    throw new Error(networkErrorMessage(error));
  }

  if (timeoutId) window.clearTimeout(timeoutId);

  const data = await response.json().catch(() => ({}));

  if (response.status === 401) {
    localStorage.removeItem('devpilot-token');
    state.token = '';
    document.getElementById('auth-modal')?.showModal?.();
    throw new Error('Sua sessão expirou. Volte ao painel e entre novamente.');
  }

  if (!response.ok) {
    if (method === 'GET' && options.retry !== false && response.status >= 500 && attempt === 0) {
      await sleep(250);
      return requestJson(path, options, attempt + 1);
    }
    throw new Error(errorDetail(data, response.status));
  }

  return data;
}

function taskPayload(path, options = {}) {
  if (String(path || '') !== '/tasks') return null;
  if (String(options.method || 'GET').toUpperCase() !== 'POST') return null;
  if (!options.body || options.body instanceof FormData) return null;
  try {
    return typeof options.body === 'string' ? JSON.parse(options.body) : {...options.body};
  } catch (_) {
    return null;
  }
}

function repositoryGateRequest(path, options = {}) {
  const payload = taskPayload(path, options);
  const projectId = String(payload?.project_id || '').trim();
  if (!payload || !projectId || repositoryReady(cachedProject(projectId))) {
    return {projectId, staged: false, options};
  }

  const prompt = String(payload.prompt || '').trim();
  const stagedPrompt = prompt.includes(REPOSITORY_GATE_MARKER)
    ? prompt
    : `${prompt}${prompt ? '\n' : ''}${REPOSITORY_GATE_MARKER}`;

  return {
    projectId,
    staged: true,
    options: {
      ...options,
      body: JSON.stringify({
        ...payload,
        prompt: stagedPrompt,
        requires_approval: true,
      }),
    },
  };
}

async function refreshProject(projectId) {
  const id = String(projectId || '').trim();
  const rows = await requestJson(
    `/ui/projects?limit=50&include_project_id=${encodeURIComponent(id)}`,
    {timeoutMs: 5000, retry: false},
  );
  const projects = Array.isArray(rows) ? rows : [];
  state.projects = projects;
  return projects.find(item => String(item?.id) === id) || null;
}

async function releaseRepositoryGatedTask(task, projectId) {
  const taskId = String(task?.id || '').trim();
  const id = String(projectId || task?.project_id || '').trim();
  if (!taskId || !id) return null;
  if (!repositoryGatedTask(task)) return task;
  if (repositoryReleaseInFlight.has(taskId)) return repositoryReleaseInFlight.get(taskId);

  const promise = (async () => {
    try {
      await requestJson(`/projects/${encodeURIComponent(id)}/repository/retry`, {
        method: 'POST',
        timeoutMs: 10000,
        retry: false,
      }).catch(() => null);

      const deadline = Date.now() + REPOSITORY_READY_WAIT_MS;
      while (Date.now() < deadline) {
        const provision = await requestJson(
          `/projects/${encodeURIComponent(id)}/repository/provisioning`,
          {timeoutMs: 5000, retry: false},
        ).catch(() => null);

        if (String(provision?.repository_url || '').trim()) {
          await refreshProject(id).catch(() => null);
          try {
            await requestJson(`/tasks/${encodeURIComponent(taskId)}/approve`, {
              method: 'POST',
              timeoutMs: 10000,
              retry: false,
            });
          } catch (error) {
            if (!String(error?.message || '').includes('not awaiting approval')) throw error;
          }

          toast('Execução criada. Repositório pronto; Planejamento liberado para o worker.');
          document.dispatchEvent(new CustomEvent('devpilot:game:repository-ready', {
            detail: {projectId: id, taskId},
          }));
          if (typeof window.loadBuildGame === 'function') {
            await window.loadBuildGame().catch(() => null);
          }
          return true;
        }

        if (String(provision?.state || '') === 'failed' && String(provision?.error || '').trim()) {
          throw new Error(`A execução foi criada, mas o repositório não ficou pronto: ${String(provision.error).trim()}`);
        }
        await sleep(REPOSITORY_READY_POLL_MS);
      }

      throw new Error('A execução foi criada e está aguardando o repositório. O provisionamento ainda não terminou.');
    } catch (error) {
      toast(error?.message || 'A execução foi criada, mas o repositório ainda não está pronto.');
      console.error('[DevPilot Repository Gate]', error);
      return false;
    } finally {
      repositoryReleaseInFlight.delete(taskId);
    }
  })();

  repositoryReleaseInFlight.set(taskId, promise);
  return promise;
}

function normalizeGameTasks(rows) {
  if (!Array.isArray(rows)) return [];
  return rows.map(row => {
    const prompt = String(row?.prompt || '');
    if (repositoryGatedTask(row)) {
      void releaseRepositoryGatedTask(row, row?.project_id);
    }
    return {
      ...row,
      status: repositoryGatedTask(row) ? 'queued' : row?.status,
      prompt: prompt.includes(GAME_PIPELINE_MARKER)
        ? prompt
        : `${prompt}${prompt ? '\n' : ''}${GAME_PIPELINE_MARKER}`,
    };
  });
}

async function api(path, options = {}) {
  state.token = String(localStorage.getItem('devpilot-token') || state.token || '');
  if (!state.token) {
    document.getElementById('auth-modal')?.showModal?.();
    throw new Error('Autenticação necessária');
  }

  const gate = repositoryGateRequest(path, options);
  const route = standaloneRoute(path, gate.options);
  const requestOptions = route.kind === 'default'
    ? gate.options
    : {...gate.options, timeoutMs: Number(gate.options.timeoutMs || 5000), retry: false};
  const data = await requestJson(route.path, requestOptions);

  if (gate.staged && data?.id) {
    void releaseRepositoryGatedTask(data, gate.projectId);
  }

  if (route.kind === 'game-tasks') return normalizeGameTasks(data);
  return data;
}

function status(value) {
  const normalized = String(value || '').replaceAll('_', ' ');
  return `<span class="status ${esc(value)}">${esc(normalized)}</span>`;
}

// build-game.js expects this symbol because it also supports the dashboard.
// In standalone mode the document already owns the game view, so navigation is a no-op.
function showView() {}

window.api = api;
window.toast = toast;
window.status = status;
window.showView = showView;
window.__devpilotGameState = state;
window.__devpilotGameApiReady = true;
window.__devpilotGameCompactRuntime = true;
window.__devpilotGameStartupRequestTimeoutMs = 5000;
