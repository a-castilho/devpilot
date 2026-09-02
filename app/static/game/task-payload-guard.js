(() => {
  'use strict';

  const GAME_TASK_LIMIT = 24;
  const GAME_PROJECT_LIMIT = 50;
  const GAME_PROJECT_KEY = 'devpilot-build-game-project';
  const INSTALL_FLAG = '__devpilotGameTaskPayloadGuardInstalled';
  const PRECHECK_TIMEOUT_MS = 1400;
  const CREATE_TIMEOUT_MS = 6500;
  const RECOVERY_TIMEOUT_MS = 2200;
  const TRACE_LIMIT = 80;

  if (window[INSTALL_FLAG]) return;

  const originalApi = window.api;

  const now = () => typeof performance !== 'undefined' && typeof performance.now === 'function'
    ? Math.round(performance.now())
    : Date.now();

  const trace = (stage, detail = {}) => {
    const entry = {stage, at: now(), ...detail};
    if (!Array.isArray(window.__devpilotGameBootTrace)) window.__devpilotGameBootTrace = [];
    window.__devpilotGameBootTrace.push(entry);
    if (window.__devpilotGameBootTrace.length > TRACE_LIMIT) {
      window.__devpilotGameBootTrace.splice(0, window.__devpilotGameBootTrace.length - TRACE_LIMIT);
    }
    return entry;
  };

  const promptValue = (prompt, label) => {
    const escaped = String(label || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return String(prompt || '').match(new RegExp(`^${escaped}:\\s*(.+)$`, 'mi'))?.[1]?.trim() || '';
  };

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

    if (!projectId || !mission || !phase) return null;

    return {
      projectId,
      mission,
      phase,
      key: `${projectId}::${mission}::${phase}`,
    };
  };

  async function findGameCreation(options, delayOrConfig = 0) {
    const identity = gameCreationIdentity(options);
    if (!identity) return null;

    const config = typeof delayOrConfig === 'number'
      ? {
          delayMs: delayOrConfig,
          timeoutMs: delayOrConfig > 0 ? RECOVERY_TIMEOUT_MS : PRECHECK_TIMEOUT_MS,
        }
      : {
          delayMs: Number(delayOrConfig?.delayMs || 0),
          timeoutMs: Number(delayOrConfig?.timeoutMs || PRECHECK_TIMEOUT_MS),
        };

    if (config.delayMs > 0) {
      await new Promise(resolve => window.setTimeout(resolve, config.delayMs));
    }

    const tasks = await originalApi(
      `/ui/game-tasks?project_id=${encodeURIComponent(identity.projectId)}&limit=${GAME_TASK_LIMIT}`,
      {method: 'GET', timeoutMs: config.timeoutMs, retry: false},
    );

    if (!Array.isArray(tasks)) return null;

    return tasks.find(task => {
      const taskPrompt = String(task?.prompt || '');
      return promptValue(taskPrompt, 'PARTIDA') === identity.mission
        && promptValue(taskPrompt, 'FASE') === identity.phase;
    }) || null;
  }

  async function precheckGameCreation(options) {
    try {
      const existing = await findGameCreation(options);
      return existing;
    } catch (precheckError) {
      trace('game-create:dedupe:precheck-timeout', {
        message: String(precheckError?.message || precheckError || 'erro'),
      });
      return null;
    }
  }

  async function recoverGameCreation(options) {
    return findGameCreation(options, 350);
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
      });
      return inFlight;
    }

    const creation = (async () => {
      try {
        trace('game-create:dedupe:check', {
          projectId: identity.projectId,
          mission: identity.mission,
          phase: identity.phase,
        });

        // This stale-tab check is bounded. A slow Wi-Fi response never blocks the
        // real POST indefinitely: timeout/error here simply lets creation continue.
        const existing = await precheckGameCreation(options);
        if (existing) {
          trace('game-create:dedupe:existing', {
            id: existing.id,
            projectId: identity.projectId,
            mission: identity.mission,
            phase: identity.phase,
          });
          window.toast?.('Esta etapa já está registrada. A tarefa existente será reutilizada.');
          return existing;
        }

        const result = await originalApi(path, {
          ...options,
          timeoutMs: Number(options?.timeoutMs || CREATE_TIMEOUT_MS),
        });
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
  window.__devpilotGameTraceLimit = TRACE_LIMIT;
  window.__devpilotGamePrecheckTimeoutMs = PRECHECK_TIMEOUT_MS;
})();
