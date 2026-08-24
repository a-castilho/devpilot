/* DevPilot Build Game weapons: real task outcomes rendered as spaceship weapon telemetry. */
(() => {
  'use strict';

  const STYLE_ID = 'build-game-weapons-style';
  const PANEL_ATTR = 'data-build-game-weapons';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const PHASE_COUNT = 6;
  const ACTIVE_SHOT_STATUSES = new Set(['awaiting_approval', 'queued', 'running', 'review']);
  const MISS_STATUSES = new Set(['failed', 'cancelled']);

  let lastShell = null;
  let lastContextKey = '';
  let requestSequence = 0;

  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const escapeRegExp = value => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  const promptValue = (task, label) => {
    const match = String(task?.prompt || '').match(new RegExp(`^${escapeRegExp(label)}:\\s*(.+)$`, 'mi'));
    return match?.[1]?.trim() || '';
  };

  const phaseFromTask = task => Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  const missionFromTask = task => promptValue(task, 'PARTIDA');
  const isGameTask = task => String(task?.prompt || '').includes(MARKER);

  function installStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .build-game-weapons-panel{position:relative;overflow:hidden;padding:16px;border:1px solid rgba(96,232,215,.24);border-radius:18px;background:radial-gradient(circle at 88% 18%,rgba(81,211,255,.13),transparent 34%),linear-gradient(145deg,rgba(5,18,29,.96),rgba(3,9,17,.98));box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}
      .build-game-weapons-panel:after{content:'TARGET';position:absolute;right:16px;top:4px;font-size:clamp(2.6rem,8vw,6rem);font-weight:900;letter-spacing:.08em;color:rgba(255,255,255,.018);pointer-events:none}
      .build-game-weapons-head{position:relative;z-index:1;display:flex;align-items:flex-end;justify-content:space-between;gap:14px;margin-bottom:13px}
      .build-game-weapons-head h3{margin:3px 0 0;font-size:1.2rem}
      .build-game-weapons-head p{margin:5px 0 0;max-width:680px;color:var(--muted,#91a6b8);font-size:.74rem}
      .build-game-weapons-mode{display:flex;align-items:center;gap:7px;white-space:nowrap;font-size:.67rem;font-weight:800;letter-spacing:.08em;color:#7ce7d3;text-transform:uppercase}
      .build-game-weapons-mode i{width:8px;height:8px;border-radius:50%;background:#68efbd;box-shadow:0 0 12px rgba(104,239,189,.55)}
      .build-game-weapons-grid{position:relative;z-index:1;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}
      .build-game-weapon-stat{min-height:102px;padding:12px;border:1px solid rgba(110,222,212,.14);border-radius:13px;background:linear-gradient(150deg,rgba(14,36,48,.72),rgba(3,10,17,.9))}
      .build-game-weapon-stat span{display:block;font-size:.62rem;font-weight:800;letter-spacing:.09em;color:#77aaa9;text-transform:uppercase}
      .build-game-weapon-stat strong{display:block;margin-top:7px;font-size:1.75rem;line-height:1;color:#e5fff9}
      .build-game-weapon-stat small{display:block;margin-top:7px;color:#78909d;font-size:.66rem;line-height:1.35}
      .build-game-weapon-stat.weapon-fired{border-color:rgba(90,202,255,.24)}
      .build-game-weapon-stat.weapon-hit{border-color:rgba(96,239,190,.32)}
      .build-game-weapon-stat.weapon-hit strong{color:#8cf6cf}
      .build-game-weapon-stat.weapon-miss{border-color:rgba(255,112,137,.3)}
      .build-game-weapon-stat.weapon-miss strong{color:#ff899d}
      .build-game-weapons-targeting{position:relative;z-index:1;display:grid;grid-template-columns:minmax(150px,.32fr) minmax(0,1fr);gap:12px;align-items:center;margin-top:11px;padding-top:11px;border-top:1px solid rgba(255,255,255,.055)}
      .build-game-target{display:flex;align-items:center;gap:11px}
      .build-game-target-ring{display:grid;place-items:center;width:68px;height:68px;flex:0 0 auto;border:1px solid rgba(102,238,216,.42);border-radius:50%;background:radial-gradient(circle,rgba(104,239,210,.12) 0 18%,transparent 19% 42%,rgba(104,239,210,.08) 43% 45%,transparent 46%);box-shadow:inset 0 0 18px rgba(73,228,205,.08)}
      .build-game-target-ring strong{font-size:1rem;color:#dffff8}
      .build-game-target-copy span{display:block;font-size:.6rem;font-weight:800;letter-spacing:.09em;color:#6eb7b2;text-transform:uppercase}
      .build-game-target-copy strong{display:block;margin-top:4px;font-size:.86rem;color:#d9fff8}
      .build-game-accuracy-track{height:8px;overflow:hidden;border-radius:999px;background:rgba(255,255,255,.065)}
      .build-game-accuracy-track i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#58d8ff,#68f0bb);transition:width .25s ease}
      .build-game-weapons-foot{display:flex;gap:8px 15px;flex-wrap:wrap;margin-top:8px;color:#8399a5;font-size:.66rem}
      .build-game-weapons-foot b{color:#d7eee9}
      .build-game-weapons-error{position:relative;z-index:1;padding:10px 12px;border:1px solid rgba(255,159,98,.22);border-radius:10px;color:#d8b29b;font-size:.72rem;background:rgba(62,28,14,.14)}
      @media(max-width:800px){.build-game-weapons-grid{grid-template-columns:1fr 1fr}.build-game-weapons-targeting{grid-template-columns:1fr}.build-game-weapons-head{align-items:flex-start;flex-direction:column}.build-game-weapons-mode{white-space:normal}}
      @media(max-width:440px){.build-game-weapons-panel{padding:12px}.build-game-weapon-stat{min-height:92px}.build-game-weapon-stat strong{font-size:1.5rem}}
    `;
    document.head.appendChild(style);
  }

  function context(view) {
    const projectId = String(view.querySelector('#build-game-project')?.value || localStorage.getItem(PROJECT_KEY) || '').trim();
    const missionId = String(localStorage.getItem(MISSION_KEY) || '').trim();
    return {projectId, missionId, key: `${projectId}:${missionId}`};
  }

  function telemetry(tasks) {
    const shotsFired = tasks.length;
    const hits = tasks.filter(task => normalize(task?.status) === 'completed').length;
    const misses = tasks.filter(task => MISS_STATUSES.has(normalize(task?.status))).length;
    const inFlight = tasks.filter(task => ACTIVE_SHOT_STATUSES.has(normalize(task?.status))).length;
    const blocked = tasks.filter(task => normalize(task?.status) === 'blocked').length;
    const attemptedPhases = new Set(tasks.map(phaseFromTask).filter(phase => phase >= 1 && phase <= PHASE_COUNT));
    const notFired = Math.max(0, PHASE_COUNT - attemptedPhases.size);
    const resolved = hits + misses;
    const accuracy = resolved ? Math.round((hits / resolved) * 100) : 0;
    return {shotsFired, notFired, hits, misses, inFlight, blocked, resolved, accuracy};
  }

  function panelMarkup(data) {
    return `
      <div class="build-game-weapons-head">
        <div><span class="eyebrow">SISTEMA DE ARMAS · TELEMETRIA REAL</span><h3>Armas da nave</h3><p>Cada tarefa executada na partida vira um disparo. O alvo só conta como atingido quando a execução termina realmente concluída.</p></div>
        <div class="build-game-weapons-mode"><i></i> armamento sincronizado</div>
      </div>
      <div class="build-game-weapons-grid" aria-label="Resultados dos disparos">
        <div class="build-game-weapon-stat weapon-fired"><span>Disparados</span><strong>${data.shotsFired}</strong><small>tarefas lançadas nesta partida</small></div>
        <div class="build-game-weapon-stat weapon-idle"><span>Não disparados</span><strong>${data.notFired}</strong><small>fases ainda sem tentativa</small></div>
        <div class="build-game-weapon-stat weapon-hit"><span>Acertou o alvo</span><strong>${data.hits}</strong><small>execuções concluídas</small></div>
        <div class="build-game-weapon-stat weapon-miss"><span>Errou o alvo</span><strong>${data.misses}</strong><small>falhas ou cancelamentos</small></div>
      </div>
      <div class="build-game-weapons-targeting">
        <div class="build-game-target">
          <div class="build-game-target-ring" aria-label="Precisão ${data.accuracy}%"><strong>${data.accuracy}%</strong></div>
          <div class="build-game-target-copy"><span>Precisão de tiro</span><strong>${data.resolved ? `${data.hits}/${data.resolved} alvos resolvidos` : 'Aguardando primeiro resultado'}</strong></div>
        </div>
        <div>
          <div class="build-game-accuracy-track" aria-hidden="true"><i style="width:${data.accuracy}%"></i></div>
          <div class="build-game-weapons-foot"><span>🚀 Em voo: <b>${data.inFlight}</b></span><span>⛔ Travados: <b>${data.blocked}</b></span><span>🎯 Resolvidos: <b>${data.resolved}</b></span></div>
        </div>
      </div>`;
  }

  function ensurePanel(view) {
    const shell = view.querySelector('.build-game-shell');
    if (!shell) return null;
    let panel = shell.querySelector(`[${PANEL_ATTR}]`);
    if (panel) return panel;

    panel = document.createElement('section');
    panel.className = 'build-game-weapons-panel';
    panel.setAttribute(PANEL_ATTR, '');
    panel.setAttribute('aria-label', 'Armas da nave e telemetria dos disparos');

    const progress = shell.querySelector('.build-game-progress');
    const score = shell.querySelector('.build-game-score');
    if (progress) progress.insertAdjacentElement('afterend', panel);
    else if (score) score.insertAdjacentElement('afterend', panel);
    else shell.appendChild(panel);
    return panel;
  }

  function renderTelemetry(view, data) {
    const panel = ensurePanel(view);
    if (!panel) return;
    panel.innerHTML = panelMarkup(data);
  }

  function renderError(view) {
    const panel = ensurePanel(view);
    if (!panel) return;
    panel.innerHTML = '<div class="build-game-weapons-error">Telemetria das armas indisponível agora. Atualize a partida para tentar novamente.</div>';
  }

  async function loadTelemetry(view, projectId, missionId, sequence) {
    if (!projectId || !missionId || typeof api !== 'function') {
      renderTelemetry(view, telemetry([]));
      return;
    }

    try {
      const tasks = await api(`/tasks?project_id=${encodeURIComponent(projectId)}&limit=500`);
      if (sequence !== requestSequence || !view.isConnected) return;
      const missionTasks = (Array.isArray(tasks) ? tasks : []).filter(task => isGameTask(task) && missionFromTask(task) === missionId);
      renderTelemetry(view, telemetry(missionTasks));
    } catch (error) {
      if (sequence !== requestSequence || !view.isConnected) return;
      renderError(view);
    }
  }

  function sync(force = false) {
    const view = document.querySelector('#build-game-view');
    const shell = view?.querySelector('.build-game-shell');
    if (!view || !shell) return;

    const current = context(view);
    if (!force && shell === lastShell && current.key === lastContextKey) return;
    lastShell = shell;
    lastContextKey = current.key;
    const sequence = ++requestSequence;
    renderTelemetry(view, telemetry([]));
    loadTelemetry(view, current.projectId, current.missionId, sequence);
  }

  function boot() {
    installStyle();
    sync(true);

    const main = document.querySelector('main') || document.body;
    if (main && main.dataset.buildGameWeaponsObserved !== '1') {
      main.dataset.buildGameWeaponsObserved = '1';
      let queued = false;
      new MutationObserver(() => {
        if (queued) return;
        queued = true;
        requestAnimationFrame(() => {
          queued = false;
          sync(false);
        });
      }).observe(main, {childList: true, subtree: true});
    }

    window.addEventListener('storage', event => {
      if (event.key === PROJECT_KEY || event.key === MISSION_KEY) sync(true);
    });
    document.addEventListener('devpilot:build-game-new-session', () => sync(true));
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
