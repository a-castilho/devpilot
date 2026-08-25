(() => {
  'use strict';

  const token = () => String(localStorage.getItem('devpilot-token') || '').trim();
  const TERMINAL = new Set(['MISSION_COMPLETE', 'SHOT_FAILED', 'SHIELD_BLOCKED']);

  async function request(path, options = {}) {
    const headers = {...(options.headers || {})};
    const authToken = token();
    if (authToken) headers.Authorization = `Bearer ${authToken}`;
    if (options.body != null && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {...options, headers, cache: 'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`;
      const error = new Error(detail);
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function phaseFromRun(run) {
    const mode = String(run?.logs?.mode || '').toLowerCase();
    const status = String(run?.status || '').toLowerCase();
    if (mode.includes('analysis')) return 'scan';
    if (mode === 'execute') return 'fire';
    if (mode === 'budget-blocked') return 'shield';
    if (status === 'success') return 'hit';
    if (status === 'failed') return 'miss';
    return 'waiting';
  }

  function gameState(taskStatus, phase) {
    const status = String(taskStatus || '').toLowerCase();
    if (status === 'completed') return 'MISSION_COMPLETE';
    if (status === 'blocked' || status === 'awaiting_approval') return 'SHIELD_BLOCKED';
    if (status === 'failed' || status === 'cancelled') return 'SHOT_FAILED';
    if (status === 'queued') return 'MISSION_READY';
    if (status === 'running' || status === 'review') {
      if (phase === 'scan') return 'SCANNING';
      if (phase === 'fire') return 'FIRING';
      if (phase === 'shield') return 'SHIELD_BLOCKED';
      if (phase === 'hit') return 'TARGET_HIT';
      if (phase === 'miss') return 'SHOT_FAILED';
      return 'IN_OPERATION';
    }
    return 'MISSION_READY';
  }

  const label = state => ({
    MISSION_READY: 'Missão preparada',
    IN_OPERATION: 'Nave em operação',
    SCANNING: 'Radar analisando',
    FIRING: 'Arma disparada',
    TARGET_HIT: 'Alvo atingido',
    SHOT_FAILED: 'Disparo falhou',
    SHIELD_BLOCKED: 'Escudo / autorização necessária',
    MISSION_COMPLETE: 'Missão concluída',
  })[state] || state;

  async function missionState(taskId) {
    if (!taskId) throw new Error('Task da missão não informada');
    const rows = await request('/api/task-runs/latest?limit=500');
    const summary = Array.isArray(rows)
      ? rows.find(row => String(row?.task_id || '') === String(taskId))
      : null;
    if (!summary) throw new Error('Missão não encontrada no workflow atual');

    const run = summary.run_id
      ? await request(`/api/task-runs/${encodeURIComponent(summary.run_id)}`)
      : null;
    const technicalPhase = phaseFromRun(run);
    const state = gameState(summary.task_status, technicalPhase);
    return {
      task_id: summary.task_id,
      run_id: summary.run_id || run?.id || null,
      technical_status: String(summary.task_status || ''),
      technical_phase: technicalPhase,
      game_state: state,
      game_label: label(state),
      failure_reason: summary.failure_reason || '',
      failure_category: summary.failure_category || '',
      requires_authorization: Boolean(summary.requires_authorization) || state === 'SHIELD_BLOCKED',
      run,
    };
  }

  async function retry(taskId) {
    const before = await missionState(taskId);
    if (before.requires_authorization || before.game_state === 'SHIELD_BLOCKED') {
      throw new Error('Missão protegida pelo escudo: conclua o fluxo normal de autorização.');
    }
    if (before.technical_status !== 'failed') {
      throw new Error('Retry só é permitido para missão realmente falha.');
    }
    await request(`/api/tasks/${encodeURIComponent(taskId)}/retry`, {method: 'POST'});
    return missionState(taskId);
  }

  function emit(name, detail) {
    document.dispatchEvent(new CustomEvent(name, {detail}));
  }

  function watch(taskId, {interval = 2500, onChange} = {}) {
    let active = true;
    let lastSignature = '';
    const stop = () => { active = false; };
    const tick = async () => {
      while (active) {
        try {
          const current = await missionState(taskId);
          const signature = JSON.stringify([
            current.game_state,
            current.technical_status,
            current.run_id,
            current.run?.status,
          ]);
          if (signature !== lastSignature) {
            lastSignature = signature;
            onChange?.(current);
            emit('devpilot:game-state', current);
          }
          if (TERMINAL.has(current.game_state)) break;
        } catch (error) {
          emit('devpilot:game-error', {task_id: taskId, message: error.message, status: error.status || null});
          break;
        }
        await new Promise(resolve => setTimeout(resolve, interval));
      }
    };
    void tick();
    return stop;
  }

  window.DevPilotGameWorkflow = Object.freeze({
    missionState,
    retry,
    watch,
    gameState,
    phaseFromRun,
    label,
  });
  emit('devpilot:game-workflow-ready', {version: 2});
})();
