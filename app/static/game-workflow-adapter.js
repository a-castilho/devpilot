(() => {
  'use strict';

  const token = () => String(localStorage.getItem('devpilot-token') || '').trim();

  async function request(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        ...(options.headers || {}),
        Authorization: `Bearer ${token()}`,
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`;
      throw new Error(message);
    }
    return data;
  }

  function gameLabel(state) {
    return {
      MISSION_READY: 'Missão preparada',
      IN_OPERATION: 'Nave em operação',
      SCANNING: 'Radar analisando',
      FIRING: 'Arma disparada',
      TARGET_HIT: 'Alvo atingido',
      SHOT_FAILED: 'Disparo falhou',
      SHIELD_BLOCKED: 'Escudo / autorização necessária',
      MISSION_COMPLETE: 'Missão concluída',
    }[state] || state;
  }

  function phaseFromRun(run) {
    const mode = String(run?.logs?.mode || '').toLowerCase();
    if (mode.includes('analysis')) return 'scan';
    if (mode === 'execute') return 'fire';
    if (mode === 'budget-blocked') return 'shield';
    if (String(run?.status || '').toLowerCase() === 'success') return 'hit';
    if (String(run?.status || '').toLowerCase() === 'failed') return 'miss';
    return 'waiting';
  }

  function gameState(taskStatus, phase) {
    const status = String(taskStatus || '').toLowerCase();
    if (status === 'completed') return 'MISSION_COMPLETE';
    if (status === 'blocked' || status === 'awaiting_approval') return 'SHIELD_BLOCKED';
    if (status === 'failed') return 'SHOT_FAILED';
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

  async function missionState(taskId) {
    const rows = await request('/api/task-runs/latest?limit=500');
    const summary = Array.isArray(rows)
      ? rows.find(item => String(item?.task_id || '') === String(taskId))
      : null;
    if (!summary) throw new Error('Missão não encontrada no workflow atual');

    let run = null;
    if (summary.run_id) {
      run = await request(`/api/task-runs/${encodeURIComponent(summary.run_id)}`);
    }
    const technicalPhase = phaseFromRun(run);
    return {
      task_id: summary.task_id,
      technical_status: summary.task_status,
      game_state: gameState(summary.task_status, technicalPhase),
      technical_phase: technicalPhase,
      failure_reason: summary.failure_reason || '',
      failure_category: summary.failure_category || '',
      requires_authorization: Boolean(summary.requires_authorization),
      run,
    };
  }

  async function fire(taskId) {
    const before = await missionState(taskId);
    if (before.game_state === 'SHIELD_BLOCKED' || before.requires_authorization) {
      throw new Error('Missão protegida pelo escudo: conclua o fluxo normal de autorização.');
    }
    if (before.technical_status === 'failed') {
      await request(`/api/tasks/${encodeURIComponent(taskId)}/retry`, {method: 'POST'});
    } else if (before.technical_status !== 'queued') {
      throw new Error('A missão não pode ser disparada no estado atual.');
    }
    const payload = await missionState(taskId);
    document.dispatchEvent(new CustomEvent('devpilot:game-event', {
      detail: {type: 'weapon_fired', ...payload},
    }));
    return payload;
  }

  async function watch(taskId, {interval = 2500, onChange} = {}) {
    let active = true;
    let last = '';
    const tick = async () => {
      while (active) {
        try {
          const current = await missionState(taskId);
          const signature = JSON.stringify([
            current.game_state,
            current.technical_status,
            current.run?.id,
            current.run?.status,
          ]);
          if (signature !== last) {
            last = signature;
            onChange?.(current);
            document.dispatchEvent(new CustomEvent('devpilot:game-state', {detail: current}));
          }
          if (['MISSION_COMPLETE', 'SHOT_FAILED', 'SHIELD_BLOCKED'].includes(current.game_state)) break;
        } catch (error) {
          document.dispatchEvent(new CustomEvent('devpilot:game-error', {
            detail: {taskId, message: error.message},
          }));
          break;
        }
        await new Promise(resolve => setTimeout(resolve, interval));
      }
    };
    void tick();
    return () => { active = false; };
  }

  window.DevPilotGameWorkflow = {
    missionState,
    fire,
    watch,
    gameLabel,
    phaseFromRun,
    gameState,
  };
})();
