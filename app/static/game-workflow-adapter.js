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
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    return response.json();
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

  async function missionState(taskId) {
    return request(`/api/game/missions/${encodeURIComponent(taskId)}`);
  }

  async function fire(taskId) {
    const payload = await request(`/api/game/missions/${encodeURIComponent(taskId)}/fire`, {method: 'POST'});
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
          const state = await missionState(taskId);
          const signature = JSON.stringify([state.game_state, state.technical_status, state.run?.id, state.run?.status]);
          if (signature !== last) {
            last = signature;
            onChange?.(state);
            document.dispatchEvent(new CustomEvent('devpilot:game-state', {detail: state}));
          }
          if (['MISSION_COMPLETE', 'SHOT_FAILED', 'SHIELD_BLOCKED'].includes(state.game_state)) break;
        } catch (error) {
          document.dispatchEvent(new CustomEvent('devpilot:game-error', {detail: {taskId, message: error.message}}));
          break;
        }
        await new Promise(resolve => setTimeout(resolve, interval));
      }
    };
    void tick();
    return () => { active = false; };
  }

  window.DevPilotGameWorkflow = {missionState, fire, watch, gameLabel};
})();
