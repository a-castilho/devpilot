(() => {
  'use strict';

  const GAME_TASK_LIMIT = 24;
  const GAME_PROJECT_LIMIT = 50;
  const GAME_PROJECT_KEY = 'devpilot-build-game-project';
  const INSTALL_FLAG = '__devpilotGameTaskPayloadGuardInstalled';
  const RETRYABLE_STATUSES = new Set(['failed', 'cancelled', 'canceled', 'archived']);

  if (window[INSTALL_FLAG]) return;

  const originalApi = window.api;

  const now = () => typeof performance !== 'undefined' && typeof performance.now === 'function'
    ? Math.round(performance.now())
    : Date.now();

  const trace = (stage, detail = {}) => {
    const entry = {stage, at: now(), ...detail};
    if (!Array.isArray(window.__devpilotGameBootTrace)) window.__devpilotGameBootTrace = [];
    window.__devpilotGameBootTrace.push(entry);
    console.debug('[DevPilot Game Trace]', entry);
    return entry;
  };

  const normalizeStatus = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');

  const promptValue = (prompt, label) => {
    const escaped = String(label || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return String(prompt || '').match(new RegExp(`^${escaped}:\\s*(.+)$`, 'mi'))?.[1]?.trim() || '';
  };

  const semanticMarkers = prompt => (
    String(prompt || '').match(/\[DEVPILOT_[^\]]+\]/g) || []
  )
    .filter(marker => !marker.startsWith('[DEVPILOT_MODE='))
    .sort()
    .join('|');

  const creationKind = prompt => [
    semanticMarkers(prompt),
    promptValue(prompt, 'SUBFASE'),
    promptValue(prompt, 'TAREFA_ORIGEM'),
    promptValue(prompt, 'ORIGEM_EXECUCAO'),
  ].join('::');

  const requestPayload = options => {
    if (!options?.body || typeof options.body !== 'string') return {};
    try { return JSON.parse(options.body); }
    catch (_) { return {}; }
  };

  const gameCreationIdentity = options => {
    const payload = requestPayload(options);
    const projectId = String(payload?.project_id || '').trim();
    const prompt = String(payload?.prompt || '');
    const mission = promptValue(prompt, 'PARTIDA');
    const phase = promptValue(prompt, 'FASE');
    const kind = creationKind(prompt);

    if (!projectId || !mission || !phase) return null;

    return {
      projectId,
      mission,
      phase,
      kind,
      key: `${projectId}::${mission}::${phase}::${kind}`,
    };
  };

  const matchesIdentity = (task, identity) => {
    const taskPrompt = String(task?.prompt || '');
    return promptValue(taskPrompt, 'PARTIDA') === identity.mission
      && promptValue(taskPrompt, 'FASE') === identity.phase
      && creationKind(taskPrompt) === identity.kind;
  };

  async function findGameCreations(options, delayMs = 0) {
    const identity = gameCreationIdentity(options);
    if (!identity) return [];

    if (delayMs > 0) {
      await new Promise(resolve => window.setTimeout(resolve, delayMs));
    }

    const tasks = await originalApi(
      `/ui/game-tasks?project_id=${encodeURIComponent(identity.projectId)}&limit=${GAME_TASK_LIMIT}`,
      {method: 'GET'}
    );

    if (!Array.isArray(tasks)) return [];
    return tasks.filter(task => matchesIdentity(task, identity));
  }

  async function findGameCreation(options, delayMs = 0, excludedIds = new Set()) {
    const tasks = await findGameCreations(options, delayMs);
    return tasks.find(task => !excludedIds.has(String(task?.id || ''))) || null;
  }

  async function recoverGameCreation(options, excludedIds = new Set()) {
    return findGameCreation(options, 350, excludedIds);
  }

  const canReusePersistedCreation = task => {
    if (!task) return false;
    return !RETRYABLE_STATUSES.has(normalizeStatus(task.status));
  };

  window.__devpilotGameTrace = trace;
  trace('guard:ready');

  if (typeof originalApi !== 'function') {
    trace('guard:error', {message: 'api indisponível'});
    return;
  }

  window[INSTALL_FLAG] = true;
  const gameCreationLocks = new Map();

  async function createGameTaskOnce(path, options) {
    const identity = gameCreationIdentity(options);
    if (!identity) return originalApi(path, options);

    const inFlight = gameCreationLocks.get(identity.key);
    if (inFlight) {
      trace('game-create:dedupe:join', {
        projectId: identity.projectId,
        mission: identity.mission,
        phase: identity.phase,
        kind: identity.kind,
      });
      return inFlight;
    }

    const creation = (async () => {
      let previousIds = new Set();
      try {
        trace('game-create:dedupe:check', {
          projectId: identity.projectId,
          mission: identity.mission,
          phase: identity.phase,
          kind: identity.kind,
        });

        const previous = await findGameCreations(options);
        previousIds = new Set(previous.map(task => String(task?.id || '')).filter(Boolean));
        const latest = previous[0] || null;

        if (canReusePersistedCreation(latest)) {
          trace('game-create:dedupe:existing', {
            id: latest.id,
            status: normalizeStatus(latest.status),
            projectId: identity.projectId,
            mission: identity.mission,
            phase: identity.phase,
            kind: identity.kind,
          });
          window.toast?.('Esta etapa já está registrada. A tarefa existente será reutilizada.');
          return latest;
        }

        if (latest) {
          trace('game-create:retry:new-attempt', {
            previousId: latest.id,
            previousStatus: normalizeStatus(latest.status),
            projectId: identity.projectId,
            mission: identity.mission,
            phase: identity.phase,
            kind: identity.kind,
          });
        }

        const result = await originalApi(path, options);
        trace('game-create:end', {id: result?.id || undefined});
        return result;
      } catch (error) {
        try {
          trace('game-create:recover:start');
          const recovered = await recoverGameCreation(options, previousIds);
          if (recovered) {
            trace('game-create:recover:end', {id: recovered.id});
            window.toast?.('Fase registrada. A conexão oscilou, mas a nova execução foi confirmada.');
            return recovered;
          }
          trace('game-create:recover:miss');
        } catch (recoveryError) {
          trace('game-create:recover:error', {
            message: String(recoveryError?.message || recoveryError || 'erro'),
          });
        }
        throw error;
      }
    })();

    gameCreationLocks.set(identity.key, creation);
    try {
      return await creation;
    } finally {
      if (gameCreationLocks.get(identity.key) === creation) {
        gameCreationLocks.delete(identity.key);
      }
    }
  }

  window.api = async (path, options = {}) => {
    const requestPath = String(path || '');
    const method = String(options?.method || 'GET').toUpperCase();
    let routedPath = path;
    let stage = 'api';

    if (requestPath === '/projects' || requestPath.startsWith('/projects?')) {
      const savedProjectId = String(localStorage.getItem(GAME_PROJECT_KEY) || '').trim();
      const includeProject = savedProjectId
        ? `&include_project_id=${encodeURIComponent(savedProjectId)}`
        : '';
      routedPath = `/ui/projects?limit=${GAME_PROJECT_LIMIT}${includeProject}`;
      stage = 'projects';
    } else {
      const isGameTaskList = requestPath.startsWith('/tasks?') && requestPath.includes('project_id=');
      if (isGameTaskList) {
        const params = new URLSearchParams(requestPath.split('?')[1] || '');
        const projectId = params.get('project_id');
        if (projectId) {
          routedPath = `/ui/game-tasks?project_id=${encodeURIComponent(projectId)}&limit=${GAME_TASK_LIMIT}`;
          stage = 'game-tasks';
        }
      } else if (requestPath === '/tasks' && method === 'POST') {
        stage = 'game-create';
      }
    }

    trace(`${stage}:start`, {path: String(routedPath || ''), method});

    if (stage === 'game-create') {
      try {
        return await createGameTaskOnce(routedPath, options);
      } catch (error) {
        trace('game-create:error', {message: String(error?.message || error || 'erro')});
        throw error;
      }
    }

    try {
      const result = await originalApi(routedPath, options);
      trace(`${stage}:end`, {
        count: Array.isArray(result) ? result.length : undefined,
        id: result?.id || undefined,
      });
      return result;
    } catch (error) {
      if (stage === 'projects' || stage === 'game-tasks') {
        window.__devpilotGameLoadError = error instanceof Error
          ? error
          : new Error(String(error || 'Falha ao carregar o Modo Jogo'));
      }

      trace(`${stage}:error`, {message: String(error?.message || error || 'erro')});
      throw error;
    }
  };

  window.__devpilotGameTaskLimit = GAME_TASK_LIMIT;
  window.__devpilotGameProjectLimit = GAME_PROJECT_LIMIT;
  window.__devpilotGameUsesLightweightHistory = true;
  window.__devpilotGameUsesLightweightProjects = true;
  window.__devpilotGameCreateRecovery = true;
  window.__devpilotGameCreateDedup = true;
  window.__devpilotGameRetryCreatesNewTask = true;
  window.__devpilotGameCreationIdentityV62 = true;
})();
