/* DevPilot game v78 — project switching and approval inside the game. */
(() => {
  'use strict';

  if (window.__devpilotGameProjectSwitchApprovalV78Ready) return;
  window.__devpilotGameProjectSwitchApprovalV78Ready = true;

  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const DRAFT_PROJECT_KEY = 'devpilot-game-v74-project';
  const STYLE_ID = 'devpilot-game-project-switch-approval-v78-style';
  let scheduled = false;
  let projectsCache = null;

  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const controller = () => window.__devpilotGameControllerV73;

  const installStyle = () => {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .game78-project-switch{display:grid;gap:8px;padding:13px 14px;border:1px solid #294158;border-radius:15px;background:#071927}
      .game78-project-switch label{color:#8fa6ba;font-size:.72rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase}
      .game78-project-switch select{width:100%;min-height:52px;border:1px solid #31516b;border-radius:12px;background:#061421;color:#f4f9ff;padding:10px 12px;font-weight:800;outline:none}
      .game78-project-switch small{color:#7f94a7}.game78-project-switch strong{color:#55f3e4}
      .game78-approval{display:grid;gap:10px;padding:15px;border:1px solid #f0b64d66;border-radius:15px;background:#34270f99}
      .game78-approval strong{color:#ffd889}.game78-approval p{color:#d9c6a0!important}
      .game78-approve{min-height:58px;border:0;border-radius:15px;background:linear-gradient(135deg,#ffd66b,#ffb344);color:#281600;font-size:1rem;font-weight:950;cursor:pointer}
      .game78-approve:disabled{opacity:.55;cursor:wait}
    `;
    document.head.appendChild(style);
  };

  const loadProjects = async () => {
    if (Array.isArray(projectsCache) && projectsCache.length) return projectsCache;
    const current = window.__devpilotGameState?.projects;
    if (Array.isArray(current) && current.length) {
      projectsCache = current;
      return projectsCache;
    }
    if (typeof window.api !== 'function') return [];
    const rows = await window.api('/projects', {timeoutMs:5000, retry:false});
    projectsCache = Array.isArray(rows) ? rows : [];
    return projectsCache;
  };

  const switchProject = projectId => {
    const target = String(projectId || '').trim();
    if (!target) return;
    localStorage.setItem(PROJECT_KEY, target);
    localStorage.setItem(DRAFT_PROJECT_KEY, target);
    localStorage.removeItem(MISSION_KEY);
    window.location.reload();
  };

  const injectProjectSwitch = async (host, state) => {
    if (!host || host.querySelector('[data-game78-project-switch]')) return;
    const projects = await loadProjects();
    if (projects.length < 2) return;

    const selected = String(state?.projectId || localStorage.getItem(PROJECT_KEY) || '');
    const box = document.createElement('div');
    box.className = 'game78-project-switch';
    box.dataset.game78ProjectSwitch = '1';
    box.innerHTML = `
      <label for="game78-project">Projeto</label>
      <select id="game78-project" data-game78-project>
        ${projects.map(project => `<option value="${esc(project.id)}" ${String(project.id) === selected ? 'selected' : ''}>${esc(project.name)}</option>`).join('')}
      </select>
      <small>A rodada atual continua no servidor. Você pode acompanhar outro projeto sem interrompê-la.</small>`;

    const first = host.firstElementChild;
    if (first?.nextSibling) host.insertBefore(box, first.nextSibling);
    else host.appendChild(box);

    box.querySelector('[data-game78-project]')?.addEventListener('change', event => {
      const next = String(event.target.value || '');
      if (next && next !== selected) switchProject(next);
    });
  };

  const injectApproval = (host, state) => {
    if (!host) return;
    host.querySelector('[data-game78-approval]')?.remove();
    if (normalize(state?.taskStatus) !== 'awaiting_approval' || !state?.taskId) return;

    const box = document.createElement('section');
    box.className = 'game78-approval';
    box.dataset.game78Approval = '1';
    box.innerHTML = `
      <strong>🔐 Esta etapa precisa da sua aprovação</strong>
      <p>Você não precisa sair do jogo. Aprove aqui e a esteira continua automaticamente.</p>
      <button class="game78-approve" type="button" data-game78-approve>✓ Aprovar e continuar</button>`;

    const actions = host.querySelector('.game74-actions');
    if (actions) actions.before(box);
    else host.appendChild(box);

    const button = box.querySelector('[data-game78-approve]');
    button.onclick = async () => {
      button.disabled = true;
      button.textContent = 'Aprovando…';
      try {
        await window.api(`/tasks/${encodeURIComponent(state.taskId)}/approve`, {method:'POST', timeoutMs:7000});
        button.textContent = '✓ Aprovado. Continuando…';
        if (typeof window.loadBuildGame === 'function') await window.loadBuildGame();
      } catch (error) {
        button.disabled = false;
        button.textContent = '✓ Aprovar e continuar';
        window.toast?.(error?.message || 'Não foi possível aprovar esta etapa');
      }
    };
  };

  const mount = async () => {
    const state = controller()?.snapshot?.();
    const host = document.querySelector('#devpilot-game-ui-v73 .game74');
    if (!state || !host) return;
    installStyle();
    await injectProjectSwitch(host, state);
    injectApproval(host, state);
  };

  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    window.setTimeout(() => {
      scheduled = false;
      void mount().catch(error => console.warn('[DevPilot Game v78]', error));
    }, 40);
  };

  document.addEventListener('devpilot:game:state', schedule);
  document.addEventListener('devpilot:game:rendered', schedule);
  document.addEventListener('devpilot:game:enhancements-ready', schedule);
  document.addEventListener('devpilot:game:core-ready', schedule);
  schedule();
})();
