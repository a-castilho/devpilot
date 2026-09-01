(() => {
  'use strict';

  const STYLE_ID = 'devpilot-mobile-project-card-compact-style';
  const RENDER_WRAP_FLAG = '__devpilotProjectsMemoryGuard';
  const LOAD_WRAP_FLAG = '__devpilotProjectsFastLoader';
  const MAX_PROJECTS = 50;
  const LOAD_TIMEOUT_MS = 7000;
  const GAME_PROJECT_KEY = 'devpilot-build-game-project';
  const GAME_MISSION_KEY = 'devpilot-build-game-mission';
  const MISSION_VERSION = 'mission-control-v51';

  const mobileViewport = () => window.matchMedia?.('(max-width: 900px)')?.matches === true;
  const lowPower = () => mobileViewport() || document.documentElement.classList.contains('devpilot-low-power');
  const batchSize = () => lowPower() ? 6 : 15;
  const normalize = value => String(value || '').toLocaleLowerCase('pt-BR').replace(/\s+/g, ' ').trim();

  if (mobileViewport()) document.documentElement.classList.add('devpilot-low-power');

  let renderLimit = batchSize();
  let projectsSource = null;
  let fetchedLimit = 0;
  let remoteExhausted = false;
  let requestedRenderLimit = 0;
  let observer = null;

  function hashText(value) {
    let hash = 2166136261;
    for (const char of String(value || 'projeto')) {
      hash ^= char.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function escapeHtml(value) {
    if (typeof window.esc === 'function') return window.esc(value);
    return String(value ?? '').replace(/[&<>'\"]/g, char => ({
      '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '\"':'&quot;',
    }[char]));
  }

  function projectSkin(project = {}) {
    const source = normalize(`${project.name || ''} ${project.description || ''} ${project.repository_url || ''}`);
    if (/(seguran|auth|login|compliance|regula|firewall|permiss|acesso)/.test(source)) return 'DEFENSE';
    if (/(\bia\b|ai|rag|modelo|agent|agente|llm|pesquisa|laborat)/.test(source)) return 'LAB';
    if (/(coleta|estoque|logíst|logist|erp|gestão|gestao|opera|recicl|entrega|pedido)/.test(source)) return 'CARGO';
    if (/(site|portal|front|mobile|landing|conteúdo|conteudo|música|musica)/.test(source)) return 'SCOUT';
    return 'COMMAND';
  }

  function projectTasks(projectId) {
    const tasks = typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks : [];
    return tasks.filter(task => String(task?.project_id ?? '') === String(projectId ?? ''));
  }

  function missionState(project = {}) {
    const tasks = projectTasks(project.id);
    const statusOf = task => normalize(task?.status).replaceAll(' ', '_');
    if (tasks.some(task => ['failed', 'error', 'blocked'].includes(statusOf(task)))) return ['DAMAGED', 'Falha exige atenção'];
    if (tasks.some(task => statusOf(task) === 'awaiting_approval')) return ['DOCKED', 'Aguardando aprovação'];
    if (tasks.some(task => ['running', 'in_progress', 'queued', 'approved', 'processing'].includes(statusOf(task)))) return ['IN_MISSION', 'Missão em andamento'];
    if (!String(project.repository_url || '').trim()) return ['BUILDING', 'Repositório pendente'];
    if (normalize(project.status) === 'active') return ['READY', 'Pronta para missão'];
    return ['STANDBY', 'Em espera'];
  }

  function projectTelemetry(project = {}, index = 0) {
    const hash = hashText(`${project.id}|${project.name}|${project.repository_url}|${index}`);
    const repositoryReady = Boolean(String(project.repository_url || '').trim());
    const branchReady = Boolean(String(project.default_branch || '').trim());
    const [stateName] = missionState(project);
    const damaged = stateName === 'DAMAGED';
    const energy = Math.max(28, Math.min(99, (repositoryReady ? 86 : 48) + (hash % 12) - (damaged ? 18 : 0)));
    const shield = Math.max(24, Math.min(99, (branchReady ? 82 : 52) + ((hash >>> 4) % 14) - (damaged ? 20 : 0)));
    const integrity = Math.max(20, Math.min(100, repositoryReady && branchReady ? 94 - (damaged ? 28 : 0) : 58));
    return {energy, shield, integrity};
  }

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #projects-view.project-mission-control {
        --mc-cyan:#42e4ef;
        --mc-blue:#4f8cff;
        --mc-green:#53e0b7;
        --mc-amber:#f4c35e;
        --mc-red:#ff6b82;
      }

      #projects-view.project-mission-control .section-head {
        align-items:stretch;
        gap:14px;
        margin-bottom:14px;
        padding:18px;
        border:1px solid rgba(71,137,183,.25);
        border-radius:20px;
        background:linear-gradient(145deg,rgba(7,25,43,.94),rgba(5,15,31,.97));
      }
      #projects-view.project-mission-control .section-head > div:first-child {min-width:0}
      #projects-view.project-mission-control .mission-control-kicker {
        display:block;
        margin-bottom:5px;
        color:var(--mc-cyan);
        font-size:.69rem;
        font-weight:900;
        letter-spacing:.13em;
      }
      #projects-view.project-mission-control .mission-control-title {
        margin:0;
        color:#f3f8ff;
        font-size:clamp(1.25rem,5vw,1.8rem);
      }
      #projects-view.project-mission-control .mission-control-copy {
        max-width:720px;
        margin:7px 0 0;
        color:#91a8bc;
        line-height:1.45;
      }
      #projects-view.project-mission-control [data-project-builder-open] {
        align-self:center;
        min-height:48px;
      }

      #projects-view .project-visual-overview {display:none!important}

      .mission-control-hud {
        display:grid;
        grid-template-columns:repeat(4,minmax(0,1fr));
        gap:9px;
        margin:0 0 14px;
      }
      .mission-control-stat {
        min-width:0;
        padding:13px;
        border:1px solid rgba(63,110,151,.25);
        border-radius:15px;
        background:linear-gradient(150deg,rgba(7,24,39,.92),rgba(6,18,31,.96));
      }
      .mission-control-stat small {
        display:block;
        overflow:hidden;
        color:#7f99ad;
        font-size:.61rem;
        font-weight:900;
        letter-spacing:.1em;
        text-overflow:ellipsis;
        white-space:nowrap;
      }
      .mission-control-stat strong {
        display:block;
        margin-top:5px;
        color:#f5f9ff;
        font-size:1.42rem;
      }
      .mission-control-stat span {
        display:block;
        margin-top:2px;
        color:#72cfc5;
        font-size:.7rem;
      }

      #projects-view #projects-list > .project-card {
        content-visibility:auto;
        contain-intrinsic-size:320px;
      }

      #projects-view .mission-ship-card {
        --mission-ship-accent:#49b9ff;
        position:relative;
        overflow:hidden;
        border-color:color-mix(in srgb,var(--mission-ship-accent) 30%,#203447)!important;
        background:
          radial-gradient(circle at 85% 10%,color-mix(in srgb,var(--mission-ship-accent) 10%,transparent),transparent 32%),
          linear-gradient(155deg,#081929,#071521 72%,#07131d)!important;
      }
      #projects-view .mission-ship-card[data-mission-skin="DEFENSE"] {--mission-ship-accent:#8b74ff}
      #projects-view .mission-ship-card[data-mission-skin="LAB"] {--mission-ship-accent:#d06cff}
      #projects-view .mission-ship-card[data-mission-skin="CARGO"] {--mission-ship-accent:#54dfad}
      #projects-view .mission-ship-card[data-mission-skin="SCOUT"] {--mission-ship-accent:#4ab7ff}
      #projects-view .mission-ship-card[data-mission-skin="COMMAND"] {--mission-ship-accent:#f2b84e}

      .mission-ship-meta {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:8px;
        margin:8px 0 10px;
      }
      .mission-ship-class,
      .mission-ship-state {
        display:inline-flex;
        align-items:center;
        min-width:0;
        min-height:26px;
        padding:0 8px;
        border:1px solid color-mix(in srgb,var(--mission-ship-accent) 42%,transparent);
        border-radius:999px;
        background:color-mix(in srgb,var(--mission-ship-accent) 8%,#071521);
        color:color-mix(in srgb,var(--mission-ship-accent) 82%,white);
        font-size:.61rem;
        font-weight:900;
        letter-spacing:.08em;
        white-space:nowrap;
      }
      .mission-ship-state {overflow:hidden;text-overflow:ellipsis}
      .mission-ship-card[data-mission-state="DAMAGED"] .mission-ship-state {border-color:#ff6b8266;color:#ff8397;background:#32121a}
      .mission-ship-card[data-mission-state="DOCKED"] .mission-ship-state {border-color:#f4c35e66;color:#ffd36f;background:#2c2109}
      .mission-ship-card[data-mission-state="IN_MISSION"] .mission-ship-state {border-color:#4f8cff66;color:#78a9ff;background:#0b1c3a}

      .mission-ship-lite {
        position:relative;
        min-height:94px;
        margin:2px 0 11px;
        overflow:hidden;
        border:1px solid color-mix(in srgb,var(--mission-ship-accent) 28%,#1b3043);
        border-radius:14px;
        background:
          radial-gradient(ellipse at 50% 84%,color-mix(in srgb,var(--mission-ship-accent) 17%,transparent),transparent 44%),
          linear-gradient(180deg,#06111e,#081724);
      }
      .mission-ship-lite::before {
        content:'';
        position:absolute;
        top:14px;
        left:50%;
        width:132px;
        height:58px;
        transform:translateX(-50%);
        clip-path:polygon(50% 0,62% 24%,94% 64%,68% 61%,61% 100%,39% 100%,32% 61%,6% 64%,38% 24%);
        background:
          linear-gradient(90deg,transparent 0 46%,color-mix(in srgb,var(--mission-ship-accent) 65%,white) 47% 53%,transparent 54%),
          linear-gradient(145deg,#b7c6d5,#324458 55%,#172333);
        box-shadow:0 14px 22px rgba(0,0,0,.36);
      }
      .mission-ship-lite::after {
        content:'';
        position:absolute;
        left:50%;
        bottom:13px;
        width:18px;
        height:5px;
        transform:translateX(-50%);
        border-radius:999px;
        background:var(--mission-ship-accent);
        box-shadow:-31px 0 8px color-mix(in srgb,var(--mission-ship-accent) 70%,transparent),31px 0 8px color-mix(in srgb,var(--mission-ship-accent) 70%,transparent),0 0 12px var(--mission-ship-accent);
      }
      .mission-ship-lite span {
        position:absolute;
        z-index:2;
        top:8px;
        left:9px;
        color:color-mix(in srgb,var(--mission-ship-accent) 78%,white);
        font-size:.58rem;
        font-weight:900;
        letter-spacing:.1em;
      }

      .mission-telemetry {
        display:grid;
        grid-template-columns:repeat(3,minmax(0,1fr));
        gap:7px;
        margin:0 0 12px;
      }
      .mission-telemetry-item {min-width:0}
      .mission-telemetry-item div {
        height:5px;
        overflow:hidden;
        border-radius:999px;
        background:#172939;
      }
      .mission-telemetry-item i {
        display:block;
        height:100%;
        border-radius:inherit;
        background:var(--mission-ship-accent);
      }
      .mission-telemetry-item small {
        display:flex;
        justify-content:space-between;
        gap:4px;
        margin-top:4px;
        color:#7f96aa;
        font-size:.55rem;
        font-weight:850;
      }
      .mission-telemetry-item b {color:#cfe3f1}

      #projects-view .mission-ship-card .list-row > div:last-child {
        display:grid!important;
        grid-template-columns:repeat(2,minmax(0,1fr));
        gap:8px!important;
        width:100%!important;
      }
      #projects-view .mission-ship-card .list-row button {
        width:100%;
        min-width:0!important;
        min-height:42px;
        margin:0!important;
        border:1px solid rgba(88,130,166,.28);
        border-radius:11px;
        background:#0a1c2b;
        color:#d9e9f4;
        font-size:.76rem!important;
      }
      #projects-view .mission-ship-card [data-mission-play] {
        border-color:color-mix(in srgb,var(--mission-ship-accent) 52%,#29415a)!important;
        color:color-mix(in srgb,var(--mission-ship-accent) 80%,white)!important;
      }

      .projects-memory-footer {
        grid-column:1/-1;
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
        padding:10px 12px;
        border:1px solid rgba(127,127,127,.18);
        border-radius:10px;
        background:rgba(7,17,31,.72);
      }
      .projects-memory-footer small {opacity:.74}
      .projects-memory-footer button {flex:0 0 auto}

      html.devpilot-low-power #projects-view .project-visual-overview,
      html.devpilot-low-power #projects-view .project-ship-svg,
      html.devpilot-low-power #projects-view .project-ship-hangar {
        display:none!important;
        animation:none!important;
        filter:none!important;
      }

      html.devpilot-low-power #projects-view #projects-list .project-card {
        contain:layout paint;
        content-visibility:auto;
        contain-intrinsic-size:250px;
        min-height:0;
        box-shadow:none!important;
        transition:none!important;
      }

      @media (max-width:900px) {
        #projects-view .project-visual-overview,
        #projects-view .project-ship-svg,
        #projects-view .project-ship-hangar {
          display:none!important;
          animation:none!important;
          filter:none!important;
        }
        #projects-view.project-mission-control .section-head {padding:15px;border-radius:17px}
        #projects-view.project-mission-control .section-head [data-project-builder-open] {width:100%}
        .mission-control-hud {grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
        .mission-control-stat {padding:11px}

        #projects-view .project-card > p,
        #projects-view .project-card > code,
        #projects-view .project-card .list-row > small {display:none!important}

        #projects-view .project-card {
          min-height:0;
          padding:16px!important;
          box-shadow:none!important;
          transition:none!important;
        }
        #projects-view .project-card h3 {
          margin:7px 0 4px;
          overflow:hidden;
          text-overflow:ellipsis;
          white-space:nowrap;
        }
        #projects-view .project-card .list-row {
          display:flex;
          justify-content:flex-end;
          padding:0;
          border-top:0;
        }
        .projects-memory-footer {align-items:stretch;flex-direction:column}
        .projects-memory-footer button {width:100%}
      }

      @media (max-width:420px) {
        .mission-ship-meta {align-items:flex-start;flex-direction:column}
        .mission-ship-state {max-width:100%}
        .mission-ship-lite {min-height:88px}
        .mission-ship-lite::before {width:118px;height:53px}
      }
    `;
    document.head.appendChild(style);
  }

  function ensureMissionControlShell() {
    const view = document.getElementById('projects-view');
    if (!view) return;
    view.classList.add('project-mission-control');
    document.documentElement.dataset.devpilotProjectsVisual = MISSION_VERSION;

    if (view.classList.contains('active')) {
      const pageTitle = document.getElementById('page-title');
      if (pageTitle) pageTitle.textContent = 'Mission Control';
      document.title = 'DevPilot — Mission Control';
    }

    const head = view.querySelector(':scope > .section-head');
    if (head && head.dataset.missionControl !== '1') {
      const copy = head.querySelector(':scope > div:first-child');
      if (copy) {
        copy.innerHTML = `
          <span class="mission-control-kicker">MISSION CONTROL</span>
          <h2 class="mission-control-title">Frota de projetos</h2>
          <p class="mission-control-copy">Cada projeto é uma nave. Analise, inicie missões, jogue e acompanhe a prontidão da frota sem carregar efeitos pesados no mobile.</p>
        `;
      }
      const create = head.querySelector('[data-project-builder-open]');
      if (create) create.textContent = '+ Construir nova nave';
      head.dataset.missionControl = '1';
    }
  }

  function renderMissionHud(projects = []) {
    const view = document.getElementById('projects-view');
    const root = document.getElementById('projects-list');
    if (!view || !root) return;

    let hud = view.querySelector('.mission-control-hud');
    if (!hud) {
      hud = document.createElement('section');
      hud.className = 'mission-control-hud';
      hud.setAttribute('aria-label', 'Estado da frota');
      root.insertAdjacentElement('beforebegin', hud);
    }

    const ids = new Set(projects.map(project => String(project.id)));
    const tasks = typeof state !== 'undefined' && Array.isArray(state.tasks)
      ? state.tasks.filter(task => ids.has(String(task?.project_id ?? '')))
      : [];
    const normalizedStatus = task => normalize(task?.status).replaceAll(' ', '_');
    const inMission = new Set(tasks
      .filter(task => ['running', 'in_progress', 'queued', 'approved', 'processing'].includes(normalizedStatus(task)))
      .map(task => String(task.project_id))).size;
    const awaiting = new Set(tasks
      .filter(task => normalizedStatus(task) === 'awaiting_approval')
      .map(task => String(task.project_id))).size;
    const operational = projects.filter(project => String(project.repository_url || '').trim()).length;
    const integrity = projects.length ? Math.round(operational * 100 / projects.length) : 0;

    const stats = [
      ['FROTA', projects.length, 'naves registradas'],
      ['EM MISSÃO', inMission, 'execução ativa'],
      ['AGUARDANDO', awaiting, 'aprovação'],
      ['INTEGRIDADE', `${integrity}%`, `${operational}/${projects.length || 0} operacionais`],
    ];
    hud.innerHTML = stats.map(([label, value, detail]) => `
      <div class="mission-control-stat"><small>${label}</small><strong>${value}</strong><span>${detail}</span></div>
    `).join('');
  }

  function missionTelemetryHtml(values) {
    const item = (label, value) => `
      <div class="mission-telemetry-item">
        <div><i style="width:${value}%"></i></div>
        <small><span>${label}</span><b>${value}%</b></small>
      </div>`;
    return `<div class="mission-telemetry" aria-label="Telemetria da nave">${item('ENERGIA', values.energy)}${item('ESCUDO', values.shield)}${item('INTEGR.', values.integrity)}</div>`;
  }

  function decorateMissionCard(card, project = {}, index = 0) {
    if (!(card instanceof Element)) return;
    const skin = projectSkin(project);
    const [stateName, stateLabel] = missionState(project);
    const telemetry = projectTelemetry(project, index);

    card.classList.add('mission-ship-card');
    card.dataset.missionSkin = skin;
    card.dataset.missionState = stateName;

    let meta = card.querySelector('.mission-ship-meta');
    if (!meta) {
      meta = document.createElement('div');
      meta.className = 'mission-ship-meta';
      const title = card.querySelector('h3');
      if (title) title.insertAdjacentElement('afterend', meta);
      else card.prepend(meta);
    }
    meta.innerHTML = `<span class="mission-ship-class">${skin} CLASS</span><span class="mission-ship-state">${stateLabel}</span>`;

    if (lowPower()) {
      let skinNode = card.querySelector('.mission-ship-lite');
      if (!skinNode) {
        skinNode = document.createElement('div');
        skinNode.className = 'mission-ship-lite';
        meta.insertAdjacentElement('afterend', skinNode);
      }
      skinNode.innerHTML = `<span>SKIN · ${skin}</span>`;
    }

    let telemetryNode = card.querySelector('.mission-telemetry');
    if (!telemetryNode) {
      const host = document.createElement('div');
      host.innerHTML = missionTelemetryHtml(telemetry);
      telemetryNode = host.firstElementChild;
      const lite = card.querySelector('.mission-ship-lite');
      (lite || meta).insertAdjacentElement('afterend', telemetryNode);
    } else {
      const host = document.createElement('div');
      host.innerHTML = missionTelemetryHtml(telemetry);
      telemetryNode.replaceWith(host.firstElementChild);
    }

    const actions = card.querySelector('[data-project-task]')?.parentElement || card.querySelector('.list-row > div:last-child');
    if (actions && project.id != null && !actions.querySelector('[data-mission-play]')) {
      const play = document.createElement('button');
      play.type = 'button';
      play.className = 'link';
      play.dataset.missionPlay = String(project.id);
      play.textContent = 'Jogar';
      actions.appendChild(play);
    }
  }

  function decorateMissionControl(projects, target) {
    ensureMissionControlShell();
    if (!target) target = document.getElementById('projects-list');
    if (!target) return;
    const cards = Array.from(target.children).filter(node => node.classList?.contains('project-card'));
    cards.forEach((card, index) => decorateMissionCard(card, projects[index] || {}, index));
    renderMissionHud(projects);
  }

  function markLowPowerCards(projects, target) {
    if (!lowPower()) return;
    const cards = Array.from(target.children).filter(node => node.classList?.contains('project-card'));
    cards.forEach((card, index) => {
      const project = projects[index] || {};
      const operational = Boolean(String(project.repository_url || '').trim());
      // project-ships.js respeita este marcador e não cria SVG/hangar no modo leve.
      card.dataset.shipEnhanced = '1';
      card.dataset.shipPending = operational ? '0' : '1';
      card.dataset.shipEnergy = operational ? '92' : '55';
      card.dataset.shipShield = operational ? '90' : '50';
      card.dataset.shipReadiness = operational ? '90' : '45';
    });
  }

  function canFetchMore(total) {
    return !remoteExhausted && fetchedLimit < MAX_PROJECTS && total >= fetchedLimit;
  }

  function renderFooter(target, total, visible) {
    target.querySelector('.projects-memory-footer')?.remove();
    const localRemaining = Math.max(0, total - visible);
    const remoteRemaining = canFetchMore(total);
    if (!localRemaining && !remoteRemaining && !lowPower()) return;

    const footer = document.createElement('div');
    footer.className = 'projects-memory-footer';
    const mode = lowPower() ? 'Modo leve · ' : '';
    const more = localRemaining || remoteRemaining;
    const visibleLabel = remoteRemaining ? `${visible} de pelo menos ${total}` : `${visible} de ${total}`;
    footer.innerHTML = `
      <small>${mode}exibindo ${visibleLabel} nave(s)</small>
      ${more ? `<button type="button" class="ghost" data-projects-load-more>Mostrar mais</button>` : ''}
    `;
    target.appendChild(footer);
  }

  function installRenderGuard() {
    const original = window.renderProjects;
    if (typeof original !== 'function' || original[RENDER_WRAP_FLAG]) return;

    const guarded = function (...args) {
      const fullProjects = typeof state !== 'undefined' && Array.isArray(state.projects)
        ? state.projects
        : [];

      if (fullProjects !== projectsSource) {
        projectsSource = fullProjects;
        renderLimit = requestedRenderLimit
          ? Math.min(fullProjects.length || requestedRenderLimit, requestedRenderLimit)
          : batchSize();
        requestedRenderLimit = 0;
      }

      const visibleProjects = fullProjects.slice(0, Math.max(1, renderLimit));
      let result;
      if (typeof state !== 'undefined') state.projects = visibleProjects;
      try {
        result = original.apply(this, args);
      } finally {
        if (typeof state !== 'undefined') state.projects = fullProjects;
      }

      const target = document.getElementById('projects-list');
      if (target) {
        markLowPowerCards(visibleProjects, target);
        decorateMissionControl(visibleProjects, target);
        renderFooter(target, fullProjects.length, visibleProjects.length);
      }
      return result;
    };

    guarded[RENDER_WRAP_FLAG] = true;
    guarded.__devpilotProjectsOriginal = original;
    window.renderProjects = guarded;
    try { renderProjects = guarded; } catch (_) {}
  }

  async function requestProjectPage(requestedLimit, desiredVisible) {
    if (typeof api !== 'function' || typeof state === 'undefined') return [];
    if (state.projectsLoading) return state.projectsLoading;

    const target = document.getElementById('projects-list');
    if (target && !Array.isArray(state.projects)?.length) {
      target.innerHTML = '<div class="empty">Inicializando Mission Control…</div>';
    }

    const safeLimit = Math.max(1, Math.min(MAX_PROJECTS, Number(requestedLimit) || batchSize()));
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), LOAD_TIMEOUT_MS);

    state.projectsLoading = (async () => {
      try {
        const projects = await api(`/ui/projects?limit=${safeLimit}`, {
          signal: controller.signal,
          cache: 'no-store',
        });
        const rows = Array.isArray(projects) ? projects : [];
        fetchedLimit = safeLimit;
        remoteExhausted = rows.length < safeLimit || safeLimit >= MAX_PROJECTS;
        requestedRenderLimit = Math.max(batchSize(), Number(desiredVisible) || batchSize());
        state.projects = rows;
        window.renderProjects?.();
        if (typeof fillProjects === 'function') fillProjects();
        return rows;
      } catch (error) {
        const timedOut = error?.name === 'AbortError';
        const message = timedOut
          ? 'Mission Control demorou mais de 7 segundos. A tela foi liberada; toque em Atualizar para tentar novamente.'
          : (error?.message || 'Não foi possível carregar a frota.');
        if (target) target.innerHTML = `<div class="empty" role="alert">${escapeHtml(message)}</div>`;
        window.toast?.(message);
        return [];
      } finally {
        window.clearTimeout(timeoutId);
        state.projectsLoading = null;
      }
    })();

    return state.projectsLoading;
  }

  function installFastLoader() {
    const original = window.loadProjects;
    if (typeof original !== 'function' || original[LOAD_WRAP_FLAG]) return;

    const fast = function () {
      if (!lowPower()) return original.apply(this, arguments);
      const existing = typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : [];
      const initial = Math.max(batchSize(), Math.min(existing.length || batchSize(), MAX_PROJECTS));
      return requestProjectPage(initial, batchSize());
    };

    fast[LOAD_WRAP_FLAG] = true;
    fast.__devpilotProjectsOriginalLoader = original;
    window.loadProjects = fast;
    try { loadProjects = fast; } catch (_) {}
  }

  async function loadMore() {
    const projects = typeof state !== 'undefined' && Array.isArray(state.projects)
      ? state.projects
      : [];
    const desiredVisible = Math.min(MAX_PROJECTS, renderLimit + batchSize());

    if (desiredVisible <= projects.length) {
      renderLimit = desiredVisible;
      window.renderProjects?.();
      return;
    }

    if (remoteExhausted || fetchedLimit >= MAX_PROJECTS) {
      renderLimit = Math.min(projects.length, desiredVisible);
      window.renderProjects?.();
      return;
    }

    const nextFetchLimit = Math.min(MAX_PROJECTS, Math.max(desiredVisible, fetchedLimit + batchSize()));
    await requestProjectPage(nextFetchLimit, desiredVisible);
  }

  function installObserver() {
    const target = document.getElementById('projects-list');
    if (!target || observer) return;
    observer = new MutationObserver(() => {
      const projects = typeof state !== 'undefined' && Array.isArray(state.projects)
        ? state.projects.slice(0, Math.max(1, renderLimit))
        : [];
      window.requestAnimationFrame(() => decorateMissionControl(projects, target));
    });
    observer.observe(target, {childList:true});
  }

  injectStyles();
  ensureMissionControlShell();
  installRenderGuard();
  installFastLoader();
  installObserver();

  document.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;

    if (target.closest('[data-projects-load-more]')) {
      event.preventDefault();
      void loadMore();
      return;
    }

    const play = target.closest('[data-mission-play]');
    if (play) {
      event.preventDefault();
      const projectId = String(play.dataset.missionPlay || '');
      if (!projectId) return;
      localStorage.setItem(GAME_PROJECT_KEY, projectId);
      localStorage.removeItem(GAME_MISSION_KEY);
      window.location.assign('/game/index.html?v=51');
    }
  });

  const syncMissionTitle = event => {
    const view = String(event?.detail?.view || document.documentElement.dataset.devpilotView || '');
    if (view !== 'projects' && !document.getElementById('projects-view')?.classList.contains('active')) return;
    window.requestAnimationFrame(() => ensureMissionControlShell());
  };
  document.addEventListener('devpilot:view-changed', syncMissionTitle);
  document.addEventListener('devpilot:page-ready', syncMissionTitle);
  document.addEventListener('devpilot:feature-ready', () => {
    ensureMissionControlShell();
    installObserver();
  });
})();
