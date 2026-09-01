(() => {
  'use strict';

  const STYLE_ID = 'mission-control-ai-dashboard-style';
  const FLEET_STYLE_ID = 'mission-control-fleet-ships-style';
  let chartFrame = 0;

  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  const getAppState = () => {
    try {
      return typeof state !== 'undefined' ? state : {projects: [], tasks: [], currentUser: null};
    } catch (_) {
      return {projects: [], tasks: [], currentUser: null};
    }
  };

  const ensureStylesheet = () => {
    if (document.querySelector(`link[data-${STYLE_ID}]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/assets/mission-control-ai-dashboard.css?v=20260829-2';
    link.setAttribute(`data-${STYLE_ID}`, '1');
    document.head.appendChild(link);
  };

  const ensureFleetShipStyles = () => {
    if (document.getElementById(FLEET_STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = FLEET_STYLE_ID;
    style.textContent = `
      body.mission-control-mode .mc-fleet {
        grid-template-columns: repeat(2,minmax(0,1fr));
        align-items: stretch;
        max-height: none;
        overflow: visible;
      }
      body.mission-control-mode .mc-ship-card.mc-ship-visual {
        --mc-ship-accent:#64e6ff;
        --mc-ship-accent-2:#72a8ff;
        position:relative;
        display:flex;
        flex-direction:column;
        gap:0;
        min-width:0;
        padding:12px;
        overflow:hidden;
        border:1px solid color-mix(in srgb,var(--mc-ship-accent) 30%,rgba(100,230,255,.12));
        border-radius:16px;
        background:linear-gradient(160deg,rgba(4,13,25,.96),rgba(6,22,34,.95));
        box-shadow:0 16px 34px rgba(0,0,0,.24),inset 0 1px rgba(255,255,255,.025);
      }
      body.mission-control-mode .mc-ship-card.mc-ship-visual:hover {
        transform:translateY(-2px);
        border-color:color-mix(in srgb,var(--mc-ship-accent) 62%,rgba(100,230,255,.25));
      }
      body.mission-control-mode .mc-ship-card.mc-ship-visual .mc-status-light {display:none;}
      body.mission-control-mode .mc-ship-card.mc-ship-visual .mc-ship-icon {display:none;}
      .mc-fleet-ship-hangar {
        position:relative;
        min-height:178px;
        margin-bottom:10px;
        overflow:hidden;
        border:1px solid color-mix(in srgb,var(--mc-ship-accent) 36%,#142840);
        border-radius:13px;
        background:radial-gradient(ellipse at 50% 84%,color-mix(in srgb,var(--mc-ship-accent) 18%,transparent),transparent 45%),linear-gradient(180deg,#030a13 0%,#071521 58%,#06110f 100%);
      }
      .mc-fleet-ship-hangar::before {
        content:'';
        position:absolute;
        inset:0;
        opacity:.3;
        pointer-events:none;
        background-image:radial-gradient(circle at 12% 16%,#fff 0 1px,transparent 1.3px),radial-gradient(circle at 76% 23%,#fff 0 1px,transparent 1.3px),radial-gradient(circle at 36% 42%,#fff 0 1px,transparent 1.3px),radial-gradient(circle at 91% 48%,#fff 0 1px,transparent 1.3px),radial-gradient(circle at 23% 64%,#fff 0 1px,transparent 1.3px);
      }
      .mc-fleet-ship-label {
        position:absolute;
        z-index:4;
        top:9px;
        left:9px;
        display:inline-flex;
        align-items:center;
        gap:5px;
        padding:4px 8px;
        border:1px solid color-mix(in srgb,var(--mc-ship-accent) 50%,transparent);
        border-radius:999px;
        background:rgba(3,12,22,.84);
        color:var(--mc-ship-accent);
        font-size:8px;
        font-weight:850;
        letter-spacing:.12em;
      }
      .mc-fleet-ship-label::before {
        content:'';
        width:6px;
        height:6px;
        border-radius:50%;
        background:var(--mc-ship-accent);
        box-shadow:0 0 10px var(--mc-ship-accent);
      }
      .mc-fleet-ship-svg {
        position:relative;
        z-index:2;
        display:block;
        width:100%;
        height:126px;
        margin-top:27px;
        filter:drop-shadow(0 13px 13px rgba(0,0,0,.62));
        animation:mc-fleet-ship-hover 4.8s ease-in-out infinite;
      }
      @keyframes mc-fleet-ship-hover {0%,100%{transform:translateY(1px)}50%{transform:translateY(-4px)}}
      .mc-fleet-ship-hud {
        position:absolute;
        z-index:4;
        right:7px;
        bottom:7px;
        left:7px;
        display:grid;
        grid-template-columns:repeat(3,minmax(0,1fr));
        gap:5px;
      }
      .mc-fleet-ship-gauge {
        display:grid;
        grid-template-columns:30px minmax(0,1fr);
        align-items:center;
        gap:5px;
        min-width:0;
        padding:4px 5px;
        border:1px solid rgba(255,255,255,.08);
        border-radius:8px;
        background:rgba(2,12,20,.88);
      }
      .mc-fleet-ship-ring {
        --value:0;
        position:relative;
        display:grid;
        place-items:center;
        width:30px;
        height:30px;
        border-radius:50%;
        background:conic-gradient(var(--mc-ship-accent) calc(var(--value) * 1%),#17313b 0);
      }
      .mc-fleet-ship-ring::before {content:'';position:absolute;inset:5px;border-radius:50%;background:#07131d;}
      .mc-fleet-ship-ring strong {position:relative;z-index:1;color:#fff;font-size:8px;}
      .mc-fleet-ship-gauge span {overflow:hidden;color:#8faabd;font-size:6px;font-weight:850;letter-spacing:.07em;text-overflow:ellipsis;}
      .mc-ship-card.mc-ship-visual .mc-ship-copy {padding:2px 2px 0;}
      .mc-ship-card.mc-ship-visual .mc-ship-copy small {font-size:8px;}
      .mc-ship-card.mc-ship-visual .mc-ship-copy strong {margin-top:3px;font-size:14px;}
      .mc-ship-card.mc-ship-visual .mc-ship-copy em {margin-top:3px;}
      .mc-ship-card.mc-ship-visual .mc-ship-copy > span {display:block;margin-top:4px;}
      @media(max-width:900px){
        body.mission-control-mode .mc-fleet {grid-template-columns:1fr;}
        .mc-fleet-ship-hangar {min-height:196px;}
        .mc-fleet-ship-svg {height:140px;}
      }
      @media(max-width:520px){
        .mc-fleet-ship-hangar {min-height:180px;}
        .mc-fleet-ship-svg {height:126px;}
        .mc-fleet-ship-gauge {grid-template-columns:26px minmax(0,1fr);padding:3px 4px;}
        .mc-fleet-ship-ring {width:26px;height:26px;}
      }
      @media(prefers-reduced-motion:reduce){.mc-fleet-ship-svg{animation:none;}}
    `;
    document.head.appendChild(style);
  };

  const numberFrom = value => {
    const parsed = Number(String(value ?? '').replace(/[^0-9.-]/g, ''));
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const readMetricSnapshot = target => {
    const snapshot = {};
    target.querySelectorAll(':scope > div').forEach(card => {
      const label = card.querySelector('span')?.textContent?.trim().toUpperCase();
      const value = numberFrom(card.querySelector('strong')?.textContent);
      if (!label) return;
      if (label === 'PROJETOS') snapshot.projects = value;
      if (label === 'TAREFAS') snapshot.tasks = value;
      if (label === 'EM ANDAMENTO') snapshot.active = value;
      if (label === 'CONCLUÍDAS') snapshot.completed = value;
      if (label.includes('APROVA')) snapshot.pending = value;
    });
    return snapshot;
  };

  const statusBuckets = () => {
    const tasks = getAppState().tasks || [];
    const buckets = {active: 0, completed: 0, pending: 0, failed: 0, other: 0};
    tasks.forEach(task => {
      const value = String(task?.status || '').toLowerCase();
      if (['running', 'in_progress', 'processing', 'queued'].includes(value)) buckets.active += 1;
      else if (['completed', 'done', 'success'].includes(value)) buckets.completed += 1;
      else if (['awaiting_approval', 'pending', 'review'].includes(value)) buckets.pending += 1;
      else if (['failed', 'error', 'blocked', 'cancelled', 'rejected'].includes(value)) buckets.failed += 1;
      else buckets.other += 1;
    });
    return buckets;
  };

  const recentActivityPoints = () => {
    const tasks = getAppState().tasks || [];
    const now = new Date();
    const values = Array.from({length: 7}, () => 0);
    tasks.forEach(task => {
      if (!task?.created_at) return;
      const date = new Date(task.created_at);
      if (Number.isNaN(date.getTime())) return;
      const diffDays = Math.floor((new Date(now.getFullYear(), now.getMonth(), now.getDate()) - new Date(date.getFullYear(), date.getMonth(), date.getDate())) / 86400000);
      if (diffDays >= 0 && diffDays < 7) values[6 - diffDays] += 1;
    });
    const max = Math.max(1, ...values);
    return values.map((value, index) => {
      const x = 8 + (index * 84 / 6);
      const y = 42 - (value / max) * 32;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  };

  const renderCharts = () => {
    const target = document.querySelector('#mc-metrics');
    if (!target || target.querySelector('.mc-chart-grid')) return;

    const snapshot = readMetricSnapshot(target);
    const buckets = statusBuckets();
    const total = snapshot.tasks || (buckets.active + buckets.completed + buckets.pending + buckets.failed + buckets.other);
    const completed = snapshot.completed || buckets.completed;
    const active = snapshot.active || buckets.active;
    const pending = snapshot.pending || buckets.pending;
    const failed = buckets.failed;
    const other = Math.max(0, total - completed - active - pending - failed);
    const completion = total > 0 ? Math.max(0, Math.min(100, Math.round((completed / total) * 100))) : 0;

    const categories = [
      ['Concluídas', completed, 'ok'],
      ['Em andamento', active, 'active'],
      ['Aguardando', pending, 'warning'],
      ['Falhas', failed, 'danger'],
      ['Outras', other, 'neutral'],
    ].filter(([, value]) => value > 0);
    const safeTotal = Math.max(1, categories.reduce((sum, [, value]) => sum + value, 0));

    target.innerHTML = `
      <div class="mc-chart-grid" aria-label="Gráficos operacionais">
        <article class="mc-chart-card mc-chart-progress">
          <div class="mc-chart-heading"><span>PROGRESSO</span><small>fluxo concluído</small></div>
          <div class="mc-donut" style="--mc-progress:${completion * 3.6}deg" role="img" aria-label="${completion}% das tarefas concluídas">
            <div><strong>${completion}%</strong><span>concluído</span></div>
          </div>
        </article>

        <article class="mc-chart-card mc-chart-status">
          <div class="mc-chart-heading"><span>DISTRIBUIÇÃO</span><small>estado das missões</small></div>
          <div class="mc-stacked-chart" role="img" aria-label="Distribuição das tarefas por estado">
            ${categories.map(([label, value, tone]) => `<i class="${tone}" style="flex:${Math.max(1, value)}" title="${escapeHtml(label)}: ${value}"></i>`).join('') || '<i class="neutral" style="flex:1"></i>'}
          </div>
          <div class="mc-chart-legend">
            ${categories.map(([label, value, tone]) => `<span><i class="${tone}"></i>${escapeHtml(label)} <small>${Math.round((value / safeTotal) * 100)}%</small></span>`).join('') || '<span><i class="neutral"></i>Sem tarefas</span>'}
          </div>
        </article>

        <article class="mc-chart-card mc-chart-activity">
          <div class="mc-chart-heading"><span>RITMO</span><small>atividade recente</small></div>
          <svg viewBox="0 0 100 50" role="img" aria-label="Atividade recente em sete dias" preserveAspectRatio="none">
            <path d="M8 42H92" class="mc-chart-axis"></path>
            <polyline points="${recentActivityPoints()}" class="mc-chart-line"></polyline>
          </svg>
          <div class="mc-chart-days"><span>-6d</span><span>hoje</span></div>
        </article>
      </div>
    `;
  };

  const scheduleCharts = () => {
    if (chartFrame) cancelAnimationFrame(chartFrame);
    chartFrame = requestAnimationFrame(() => {
      chartFrame = 0;
      renderCharts();
    });
  };

  const observeMetrics = () => {
    const target = document.querySelector('#mc-metrics');
    if (!target || target.dataset.aiChartsObserved === '1') return;
    target.dataset.aiChartsObserved = '1';
    new MutationObserver(scheduleCharts).observe(target, {childList: true, subtree: true, characterData: true});
    scheduleCharts();
  };

  const hashText = value => {
    let hash = 2166136261;
    for (const char of String(value || 'projeto')) {
      hash ^= char.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  };

  const fleetTheme = seed => [
    ['#31a8ff','#7bdcff'], ['#9b6cff','#d4a4ff'], ['#35e58a','#90ffc0'],
    ['#29dfe4','#8fffff'], ['#ffba43','#ffe38b'], ['#ff6b7a','#ffb0b8']
  ][seed % 6];

  const fleetShipSvg = (seed, accent, accent2) => `
    <svg class="mc-fleet-ship-svg" viewBox="0 0 520 180" aria-hidden="true">
      <defs>
        <linearGradient id="mcShipBody${seed}" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="${accent2}" stop-opacity=".95"/><stop offset="48%" stop-color="${accent}" stop-opacity=".92"/><stop offset="100%" stop-color="#1c365a" stop-opacity=".95"/></linearGradient>
        <linearGradient id="mcShipWing${seed}" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="${accent}"/><stop offset="100%" stop-color="#7a8cff"/></linearGradient>
      </defs>
      <ellipse cx="260" cy="142" rx="140" ry="15" fill="${accent}" opacity=".12"/>
      <path d="M125 102 L212 75 L332 75 L397 102 L356 118 L162 118 Z" fill="url(#mcShipBody${seed})" stroke="${accent2}" stroke-opacity=".7"/>
      <path d="M190 75 L238 46 L314 46 L346 75 Z" fill="#0f2241" stroke="${accent2}" stroke-opacity=".55"/>
      <path d="M150 104 L92 132 L148 126 L179 116 Z" fill="url(#mcShipWing${seed})" opacity=".88"/>
      <path d="M372 104 L430 132 L374 126 L343 116 Z" fill="url(#mcShipWing${seed})" opacity=".88"/>
      <path d="M224 90 L255 64 L305 64 L327 90 Z" fill="#8fe8ff" opacity=".35"/>
      <circle cx="195" cy="98" r="5" fill="#dffaff"/><circle cx="228" cy="93" r="5" fill="#dffaff"/><circle cx="292" cy="93" r="5" fill="#dffaff"/><circle cx="325" cy="98" r="5" fill="#dffaff"/>
      <rect x="146" y="121" width="35" height="10" rx="4" fill="#20395a"/><rect x="338" y="121" width="35" height="10" rx="4" fill="#20395a"/>
      <path d="M173 126 C160 145,151 150,144 160" stroke="${accent2}" stroke-width="5" stroke-linecap="round" opacity=".75"/><path d="M347 126 C360 145,369 150,376 160" stroke="${accent2}" stroke-width="5" stroke-linecap="round" opacity=".75"/>
    </svg>`;

  const enhanceFleetShips = () => {
    if (!document.body.classList.contains('mission-control-mode')) return;
    const fleet = document.querySelector('#mc-fleet');
    if (!fleet) return;
    ensureFleetShipStyles();
    fleet.querySelectorAll('.mc-ship-card').forEach(card => {
      if (card.dataset.mcShipVisual === '1') return;
      const name = card.querySelector('.mc-ship-copy strong')?.textContent?.trim() || 'Projeto';
      const status = card.querySelector('.mc-ship-copy small')?.textContent?.trim() || 'ACTIVE';
      const seed = hashText(name);
      const [accent, accent2] = fleetTheme(seed);
      const energy = 82 + (seed % 17);
      const shield = 80 + ((seed >>> 4) % 19);
      const ready = 84 + ((seed >>> 8) % 15);
      const hangar = document.createElement('div');
      hangar.className = 'mc-fleet-ship-hangar';
      hangar.style.setProperty('--mc-ship-accent', accent);
      hangar.style.setProperty('--mc-ship-accent-2', accent2);
      hangar.innerHTML = `
        <span class="mc-fleet-ship-label">${escapeHtml(status)}</span>
        ${fleetShipSvg(seed, accent, accent2)}
        <div class="mc-fleet-ship-hud">
          <div class="mc-fleet-ship-gauge"><span class="mc-fleet-ship-ring" style="--value:${energy}"><strong>${energy}</strong></span><span>ENERGIA</span></div>
          <div class="mc-fleet-ship-gauge"><span class="mc-fleet-ship-ring" style="--value:${shield}"><strong>${shield}</strong></span><span>ESCUDO</span></div>
          <div class="mc-fleet-ship-gauge"><span class="mc-fleet-ship-ring" style="--value:${ready}"><strong>${ready}</strong></span><span>PRONTO</span></div>
        </div>`;
      card.prepend(hangar);
      card.classList.add('mc-ship-visual');
      card.style.setProperty('--mc-ship-accent', accent);
      card.style.setProperty('--mc-ship-accent-2', accent2);
      card.dataset.mcShipVisual = '1';
    });
  };

  const observeFleet = () => {
    const fleet = document.querySelector('#mc-fleet');
    if (!fleet || fleet.dataset.mcShipObserved === '1') return;
    fleet.dataset.mcShipObserved = '1';
    new MutationObserver(() => requestAnimationFrame(enhanceFleetShips)).observe(fleet, {childList:true});
    enhanceFleetShips();
  };

  const openCanonicalChat = () => {
    if (typeof window.devpilotOpenChat === 'function') {
      void window.devpilotOpenChat();
      return;
    }

    const modal = document.querySelector('#voice-modal');
    if (modal && !modal.open) modal.showModal?.();
    void window.__devpilotLoadFeature?.('voice');
  };

  const createChatLaunchers = () => {
    if (!document.querySelector('#mc-ai-launcher')) {
      const launcher = document.createElement('button');
      launcher.id = 'mc-ai-launcher';
      launcher.className = 'mc-ai-launcher';
      launcher.type = 'button';
      launcher.setAttribute('aria-label', 'Abrir Chat DevPilot');
      launcher.setAttribute('title', 'Chat DevPilot');
      launcher.innerHTML = '<span aria-hidden="true">✦</span><strong>IA</strong>';
      launcher.addEventListener('click', openCanonicalChat);
      document.body.appendChild(launcher);
    }

    const headerActions = document.querySelector('header .header-actions');
    if (headerActions && !document.querySelector('#mc-ai-header-button')) {
      const button = document.createElement('button');
      button.id = 'mc-ai-header-button';
      button.className = 'ghost mc-ai-header-button';
      button.type = 'button';
      button.textContent = '✦ Chat IA';
      button.setAttribute('aria-label', 'Abrir Chat DevPilot');
      button.addEventListener('click', openCanonicalChat);
      headerActions.prepend(button);
    }
  };

  const bindKeyboardShortcut = () => {
    if (document.documentElement.dataset.mcAiChatShortcut === '1') return;
    document.documentElement.dataset.mcAiChatShortcut = '1';
    document.addEventListener('keydown', event => {
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'i') {
        event.preventDefault();
        openCanonicalChat();
      }
    });
  };

  const init = () => {
    ensureStylesheet();
    createChatLaunchers();
    observeMetrics();
    observeFleet();
    bindKeyboardShortcut();

    const panel = document.querySelector('#mission-control-panel');
    if (panel && panel.dataset.aiDashboardObserved !== '1') {
      panel.dataset.aiDashboardObserved = '1';
      new MutationObserver(() => {
        observeMetrics();
        observeFleet();
        scheduleCharts();
        requestAnimationFrame(enhanceFleetShips);
      }).observe(panel, {childList: true, subtree: true});
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
