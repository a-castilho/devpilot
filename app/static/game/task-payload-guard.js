(() => {
  'use strict';

  const GAME_TASK_LIMIT = 24;
  const GAME_PROJECT_LIMIT = 50;
  const GAME_PROJECT_KEY = 'devpilot-build-game-project';
  const INSTALL_FLAG = '__devpilotGameTaskPayloadGuardInstalled';
  const NON_RECOVERABLE_STATUSES = new Set(['failed', 'cancelled', 'canceled', 'archived']);

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
  const normalizeTitle = value => String(value || '').trim().toLowerCase().replace(/\s+/g, ' ');

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

  // The compact endpoint preserves title + PARTIDA/FASE. Title separates a base
  // phase from verifier gates and corrective subphases without parsing heavy payloads.
  const creationKind = (prompt, title) => normalizeTitle(title) || semanticMarkers(prompt);

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
    const kind = creationKind(prompt, payload?.title);

    if (!projectId || !mission || !phase || !kind) return null;

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
      && creationKind(taskPrompt, task?.title) === identity.kind;
  };

  const canRecoverCreation = task => (
    Boolean(task) && !NON_RECOVERABLE_STATUSES.has(normalizeStatus(task.status))
  );

  async function recoverGameCreation(options) {
    const identity = gameCreationIdentity(options);
    if (!identity) return null;

    await new Promise(resolve => window.setTimeout(resolve, 300));
    const tasks = await originalApi(
      `/ui/game-tasks?project_id=${encodeURIComponent(identity.projectId)}&limit=${GAME_TASK_LIMIT}`,
      {method: 'GET', timeoutMs: 3500, retry: false}
    );

    if (!Array.isArray(tasks)) return null;
    return tasks.find(task => matchesIdentity(task, identity) && canRecoverCreation(task)) || null;
  }

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

    // Mobile fast path: POST immediately. The old v62 guard performed a history GET
    // before every phase creation, turning one tap into a serial GET -> POST chain.
    // The button lock + this in-flight map already prevent duplicate taps. Only when
    // the POST itself fails do we perform one compact recovery lookup.
    const creation = (async () => {
      try {
        trace('game-create:direct:start', {
          projectId: identity.projectId,
          mission: identity.mission,
          phase: identity.phase,
          kind: identity.kind,
        });
        const result = await originalApi(path, options);
        trace('game-create:end', {id: result?.id || undefined});
        return result;
      } catch (error) {
        try {
          trace('game-create:recover:start');
          const recovered = await recoverGameCreation(options);
          if (recovered) {
            trace('game-create:recover:end', {id: recovered.id});
            window.toast?.('Fase registrada. A conexão oscilou, mas a execução foi confirmada.');
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
  window.__devpilotGameNoPreflightV63 = true;
})();
