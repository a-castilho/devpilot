(() => {
  const ROOT_SELECTOR = '#projects-list';
  const STYLE_ID = 'devpilot-project-ships-style';
  const OVERVIEW_CLASS = 'project-visual-overview';

  const themes = [
    {accent: '#31a8ff', accent2: '#7bdcff'},
    {accent: '#ff5252', accent2: '#ff9a82'},
    {accent: '#35e58a', accent2: '#90ffc0'},
    {accent: '#9b6cff', accent2: '#d4a4ff'},
    {accent: '#29dfe4', accent2: '#8fffff'},
    {accent: '#ffba43', accent2: '#ffe38b'},
  ];

  const hashText = value => {
    let hash = 2166136261;
    for (const char of String(value || 'projeto')) {
      hash ^= char.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  };

  const safeId = value => String(value || 'projeto')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase() || 'projeto';

  const clamp = value => Math.max(0, Math.min(100, Math.round(Number(value) || 0)));

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #projects-list { align-items: start; }

      .project-visual-overview {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 10px;
        margin: 4px 0 14px;
      }

      .project-visual-metric {
        min-width: 0;
        display: grid;
        grid-template-columns: 54px 1fr;
        align-items: center;
        gap: 10px;
        min-height: 72px;
        padding: 9px 11px;
        border: 1px solid #173b35;
        border-radius: 12px;
        background: linear-gradient(145deg, #071823, #071c17);
        box-shadow: inset 0 1px 0 #ffffff08;
      }

      .project-visual-ring,
      .project-ship-gauge {
        --value: 0;
        --ring-accent: #35e58a;
        position: relative;
        display: grid;
        place-items: center;
        border-radius: 50%;
        background: conic-gradient(var(--ring-accent) calc(var(--value) * 1%), #17313b 0);
      }

      .project-visual-ring {
        width: 54px;
        height: 54px;
      }

      .project-visual-ring::before,
      .project-ship-gauge::before {
        content: '';
        position: absolute;
        border-radius: inherit;
        background: #07151d;
      }

      .project-visual-ring::before { inset: 7px; }
      .project-ship-gauge::before { inset: 5px; }

      .project-visual-ring strong,
      .project-ship-gauge strong {
        position: relative;
        z-index: 1;
        color: #f1fbff;
        font-size: 12px;
        line-height: 1;
      }

      .project-visual-copy { min-width: 0; }
      .project-visual-copy span {
        display: block;
        color: #79a99c;
        font-size: 9px;
        font-weight: 850;
        letter-spacing: .1em;
      }
      .project-visual-copy strong {
        display: block;
        margin-top: 4px;
        overflow: hidden;
        color: #dff8ef;
        font-size: 14px;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .project-visual-status {
        grid-column: 1 / -1;
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: 10px;
        padding: 8px 11px;
        border: 1px solid #18332e;
        border-radius: 10px;
        background: #06140f;
      }
      .project-visual-status > span,
      .project-visual-status > strong {
        color: #9bc7ba;
        font-size: 9px;
        font-weight: 800;
        letter-spacing: .08em;
      }
      .project-visual-status > strong { color: #ffd269; }
      .project-visual-status-track {
        display: flex;
        height: 7px;
        overflow: hidden;
        border-radius: 999px;
        background: #172b2a;
      }
      .project-visual-status-ready { background: #35e58a; }
      .project-visual-status-pending { background: #ffba43; }

      #projects-list .project-card.project-ship-card {
        --ship-accent: #31a8ff;
        --ship-accent-2: #7bdcff;
        position: relative;
        min-width: 0;
        overflow: hidden;
        border-color: color-mix(in srgb, var(--ship-accent) 30%, #244132);
        background:
          radial-gradient(circle at 50% 34%, color-mix(in srgb, var(--ship-accent) 9%, transparent), transparent 31%),
          linear-gradient(160deg, #091824 0%, #071d18 72%, #08131c 100%);
        box-shadow: 0 16px 44px #0007, inset 0 1px 0 #ffffff0a;
        transition: border-color .2s ease, transform .2s ease, box-shadow .2s ease;
      }
      #projects-list .project-card.project-ship-card:hover {
        transform: translateY(-2px);
        border-color: color-mix(in srgb, var(--ship-accent) 56%, #244132);
        box-shadow: 0 20px 52px #0009, 0 0 26px color-mix(in srgb, var(--ship-accent) 11%, transparent);
      }

      #projects-list .project-card.project-ship-card > h3 {
        margin-bottom: 4px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      #projects-list .project-card.project-ship-card > h3 + p {
        display: -webkit-box;
        min-height: 1.45em;
        max-height: 1.45em;
        margin: 0 0 5px;
        overflow: hidden;
        color: #92afa7;
        font-size: 10px;
        line-height: 1.45;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 1;
      }
      #projects-list .project-card.project-ship-card > code {
        max-width: 100%;
        margin: 0 0 7px;
        overflow: hidden;
        color: #72b5d6;
        font-size: 9px;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      #projects-list .project-ship-hangar {
        position: relative;
        min-height: 190px;
        margin: 8px 0 9px;
        overflow: hidden;
        border: 1px solid color-mix(in srgb, var(--ship-accent) 32%, #203249);
        border-radius: 12px;
        background:
          radial-gradient(ellipse at 50% 78%, color-mix(in srgb, var(--ship-accent) 18%, transparent) 0, transparent 43%),
          linear-gradient(180deg, #06101a 0%, #081522 54%, #07120f 100%);
        isolation: isolate;
      }
      #projects-list .project-ship-hangar::before {
        content: '';
        position: absolute;
        inset: 0;
        opacity: .32;
        pointer-events: none;
        background-image:
          radial-gradient(circle at 12% 16%, #fff 0 1px, transparent 1.3px),
          radial-gradient(circle at 76% 23%, #fff 0 1px, transparent 1.3px),
          radial-gradient(circle at 36% 42%, #fff 0 1px, transparent 1.3px),
          radial-gradient(circle at 91% 48%, #fff 0 1px, transparent 1.3px),
          radial-gradient(circle at 23% 64%, #fff 0 1px, transparent 1.3px);
      }

      #projects-list .project-ship-label {
        position: absolute;
        z-index: 3;
        top: 8px;
        left: 9px;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 3px 7px;
        border: 1px solid color-mix(in srgb, var(--ship-accent) 45%, transparent);
        border-radius: 999px;
        background: #06111bd6;
        color: var(--ship-accent-2);
        font-size: 7px;
        font-weight: 850;
        letter-spacing: .1em;
      }
      #projects-list .project-ship-label::before {
        content: '';
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: var(--ship-accent);
        box-shadow: 0 0 10px var(--ship-accent);
      }

      #projects-list .project-ship-svg {
        position: relative;
        z-index: 2;
        display: block;
        width: 100%;
        height: 125px;
        margin-top: 22px;
        filter: drop-shadow(0 13px 12px #0009);
        animation: devpilot-ship-hover 4.8s ease-in-out infinite;
      }
      @keyframes devpilot-ship-hover {
        0%, 100% { transform: translateY(1px); }
        50% { transform: translateY(-4px); }
      }

      #projects-list .project-ship-hud {
        position: absolute;
        z-index: 4;
        right: 7px;
        bottom: 7px;
        left: 7px;
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 5px;
      }
      #projects-list .project-ship-gauge-wrap {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
        min-width: 0;
        padding: 3px 4px;
        border: 1px solid #ffffff10;
        border-radius: 8px;
        background: #041018df;
      }
      #projects-list .project-ship-gauge {
        width: 28px;
        height: 28px;
        flex: 0 0 28px;
      }
      #projects-list .project-ship-gauge strong { font-size: 7px; }
      #projects-list .project-ship-gauge-label {
        overflow: hidden;
        color: #91adba;
        font-size: 6px;
        font-weight: 850;
        letter-spacing: .06em;
        text-overflow: ellipsis;
      }

      #projects-list .project-status-strip {
        display: flex;
        align-items: center;
        gap: 6px;
        min-height: 26px;
        margin: 7px 0 4px;
        padding: 5px 7px;
        border: 1px solid #254038;
        border-radius: 8px;
        background: #071811;
      }
      #projects-list .project-status-strip.pending {
        border-color: #644a1d;
        background: #201707;
      }
      #projects-list .project-status-dot {
        width: 7px;
        height: 7px;
        flex: 0 0 7px;
        border-radius: 50%;
        background: #35e58a;
        box-shadow: 0 0 9px #35e58a88;
      }
      #projects-list .project-status-strip.pending .project-status-dot {
        background: #ffba43;
        box-shadow: 0 0 9px #ffba4388;
      }
      #projects-list .project-status-strip strong {
        overflow: hidden;
        color: #bde9d8;
        font-size: 8px;
        letter-spacing: .08em;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      #projects-list .project-status-strip.pending strong { color: #ffd36f; }

      #projects-list .project-verbose-copy { display: none !important; }

      #projects-list .project-ship-card > .eyebrow:first-child {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 3px 7px;
        border: 1px solid #2ad89755;
        border-radius: 999px;
        background: #08312070;
        font-size: 7px;
      }
      #projects-list .project-ship-card > .eyebrow:first-child::before {
        content: '';
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: #38e99a;
        box-shadow: 0 0 9px #38e99a;
      }

      #projects-list .project-ship-card button.project-ship-action {
        min-width: 30px;
        min-height: 30px;
        margin: 1px;
        padding: 5px 7px;
        border: 1px solid #ffffff16;
        border-radius: 8px;
        background: #071620;
        font-size: 0;
        font-weight: 800;
        transition: transform .15s ease, border-color .15s ease;
      }
      #projects-list .project-ship-card button.project-ship-action::before {
        font-size: 13px;
        line-height: 1;
      }
      #projects-list .project-ship-card button.project-ship-analyze::before { content: '◎'; color: #42e8b0; }
      #projects-list .project-ship-card button.project-ship-tests::before { content: '✓'; color: #69bfff; }
      #projects-list .project-ship-card button.project-ship-play::before { content: '▶'; color: #c18cff; }
      #projects-list .project-ship-card button.project-ship-task::before { content: '+'; color: #59eea7; }
      #projects-list .project-ship-card button.project-ship-retry::before { content: '↻'; color: #ffd269; }
      #projects-list .project-ship-card button.project-ship-action:hover {
        transform: translateY(-1px);
        border-color: currentColor;
      }

      @media (min-width: 901px) {
        #projects-view #projects-list.cards {
          grid-template-columns: repeat(5, minmax(0, 1fr));
          gap: 10px;
        }
        #projects-view #projects-list .project-card { padding: 12px; }
      }
      @media (max-width: 900px) {
        .project-visual-overview { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @media (max-width: 520px) {
        .project-visual-overview { grid-template-columns: 1fr 1fr; gap: 7px; }
        .project-visual-metric { grid-template-columns: 42px 1fr; min-height: 60px; padding: 7px; }
        .project-visual-ring { width: 42px; height: 42px; }
        #projects-list .project-ship-hangar { min-height: 176px; }
        #projects-list .project-ship-svg { height: 112px; }
      }
      @media (prefers-reduced-motion: reduce) {
        #projects-list .project-ship-svg { animation: none; }
        #projects-list .project-card.project-ship-card { transition: none; }
      }
    `;
    document.head.appendChild(style);
  }

  function shipSvg(id, accent, accent2, variant) {
    const fin = variant % 3;
    const wing = fin === 0 ? 80 : fin === 1 ? 62 : 94;
    const nose = fin === 2 ? 35 : 44;
    return `
      <svg class="project-ship-svg" viewBox="0 0 520 250" role="img" aria-label="Nave do projeto">
        <defs>
          <linearGradient id="${id}-hull" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#edf5ff"/>
            <stop offset=".36" stop-color="#9baaba"/>
            <stop offset=".72" stop-color="#3a4654"/>
            <stop offset="1" stop-color="#141c26"/>
          </linearGradient>
          <linearGradient id="${id}-accent" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stop-color="${accent}"/>
            <stop offset="1" stop-color="${accent2}"/>
          </linearGradient>
          <filter id="${id}-glow" x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="5" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>
        <ellipse cx="260" cy="220" rx="142" ry="15" fill="none" stroke="${accent}" stroke-width="2" opacity=".52"/>
        <path d="M222 116 L${wing} 185 L190 178 L238 150 Z" fill="#25313d" stroke="${accent}" stroke-opacity=".55"/>
        <path d="M298 116 L${520 - wing} 185 L330 178 L282 150 Z" fill="#25313d" stroke="${accent}" stroke-opacity=".55"/>
        <path d="M260 ${nose} C292 72 318 114 323 171 L299 206 L221 206 L197 171 C202 114 228 72 260 ${nose} Z" fill="url(#${id}-hull)" stroke="#c8d5e0" stroke-opacity=".38" stroke-width="2"/>
        <path d="M260 70 C278 85 290 105 294 126 L281 145 L239 145 L226 126 C230 105 242 85 260 70 Z" fill="#07111a" stroke="${accent}" stroke-width="3"/>
        <path d="M260 80 C271 91 278 102 280 112 L270 121 L250 121 L240 112 C242 102 249 91 260 80 Z" fill="url(#${id}-accent)" opacity=".9" filter="url(#${id}-glow)"/>
        <rect x="214" y="194" width="31" height="9" rx="4" fill="${accent}" opacity=".9" filter="url(#${id}-glow)"/>
        <rect x="275" y="194" width="31" height="9" rx="4" fill="${accent}" opacity=".9" filter="url(#${id}-glow)"/>
      </svg>
    `;
  }

  function actionProfile(label) {
    if (label.includes('analisar')) return ['project-ship-analyze', 'Analisar projeto'];
    if (label.includes('teste')) return ['project-ship-tests', 'Executar testes'];
    if (label.includes('jogar')) return ['project-ship-play', 'Jogar'];
    if (label.includes('nova tarefa')) return ['project-ship-task', 'Nova tarefa'];
    if (label.includes('tentar novamente')) return ['project-ship-retry', 'Tentar novamente'];
    return null;
  }

  function styleActions(card) {
    card.querySelectorAll('button').forEach(button => {
      if (button.dataset.shipAction === '1') return;
      const label = String(button.textContent || '').toLocaleLowerCase('pt-BR').trim();
      const profile = actionProfile(label);
      if (!profile) return;
      button.classList.add('project-ship-action', profile[0]);
      button.setAttribute('aria-label', profile[1]);
      button.title = profile[1];
      button.dataset.shipAction = '1';
    });
  }

  function detectPending(card) {
    const text = String(card.textContent || '').toLocaleLowerCase('pt-BR');
    return text.includes('infraestrutura pendente') ||
      text.includes('infraestrutura ainda não configurada') ||
      text.includes('repositório pendente') ||
      text.includes('repositorio pendente');
  }

  function compactVerboseCopy(card, pending) {
    const paragraphs = Array.from(card.querySelectorAll('p'));
    paragraphs.forEach((node, index) => {
      const text = String(node.textContent || '').toLocaleLowerCase('pt-BR');
      if (index > 0 && (text.includes('infraestrutura') || text.includes('configurada') || text.includes('pendente'))) {
        node.classList.add('project-verbose-copy');
      }
    });

    let strip = card.querySelector('.project-status-strip');
    if (!strip) {
      strip = document.createElement('div');
      strip.className = 'project-status-strip';
      strip.innerHTML = '<i class="project-status-dot"></i><strong></strong>';
      const actions = Array.from(card.querySelectorAll('button'))[0]?.parentElement;
      if (actions && actions !== card) actions.insertAdjacentElement('afterend', strip);
      else card.appendChild(strip);
    }
    strip.classList.toggle('pending', pending);
    strip.querySelector('strong').textContent = pending ? 'INFRA PENDENTE' : 'OPERACIONAL';
  }

  function gauge(label, value, accent) {
    const safe = clamp(value);
    return `
      <div class="project-ship-gauge-wrap" title="${label}: ${safe}%">
        <div class="project-ship-gauge" style="--value:${safe};--ring-accent:${accent}"><strong>${safe}</strong></div>
        <span class="project-ship-gauge-label">${label}</span>
      </div>
    `;
  }

  function enhance(card, index) {
    styleActions(card);
    if (card.dataset.shipEnhanced === '1') return;

    const title = card.querySelector('h3')?.textContent?.trim() || `Projeto ${index + 1}`;
    const repository = card.querySelector('code')?.textContent?.trim() || title;
    const hash = hashText(`${title}|${repository}`);
    const theme = themes[hash % themes.length];
    const energy = 84 + (hash % 15);
    const shield = 75 + ((hash >>> 5) % 23);
    const pending = detectPending(card);
    const readiness = pending ? 42 + (hash % 18) : 88 + (hash % 11);
    const id = `devpilot-${safeId(title)}-${index}-${hash.toString(36).slice(0, 6)}`;

    card.style.setProperty('--ship-accent', theme.accent);
    card.style.setProperty('--ship-accent-2', theme.accent2);
    card.classList.add('project-ship-card');
    card.dataset.shipEnergy = String(energy);
    card.dataset.shipShield = String(shield);
    card.dataset.shipReadiness = String(readiness);
    card.dataset.shipPending = pending ? '1' : '0';

    const hangar = document.createElement('div');
    hangar.className = 'project-ship-hangar';
    hangar.setAttribute('aria-label', `Nave e indicadores do projeto ${title}`);
    hangar.innerHTML = `
      <span class="project-ship-label">NAVE</span>
      ${shipSvg(id, theme.accent, theme.accent2, hash)}
      <div class="project-ship-hud" aria-label="Indicadores do projeto">
        ${gauge('ENERGIA', energy, theme.accent)}
        ${gauge('ESCUDO', shield, '#56bfff')}
        ${gauge('PRONTO', readiness, pending ? '#ffba43' : '#35e58a')}
      </div>
    `;

    const description = card.querySelector('h3 + p') || card.querySelector('p');
    if (description) description.insertAdjacentElement('afterend', hangar);
    else card.querySelector('h3')?.insertAdjacentElement('afterend', hangar);

    compactVerboseCopy(card, pending);
    card.dataset.shipEnhanced = '1';
  }

  function overviewMetric(label, value, display, accent) {
    return `
      <div class="project-visual-metric">
        <div class="project-visual-ring" style="--value:${clamp(value)};--ring-accent:${accent}"><strong>${display}</strong></div>
        <div class="project-visual-copy"><span>${label}</span><strong>${display}</strong></div>
      </div>
    `;
  }

  function renderOverview(cards) {
    const root = document.querySelector(ROOT_SELECTOR);
    if (!root || !root.parentElement) return;
    let panel = root.parentElement.querySelector(`:scope > .${OVERVIEW_CLASS}`);
    if (!panel) {
      panel = document.createElement('section');
      panel.className = OVERVIEW_CLASS;
      panel.setAttribute('aria-label', 'Resumo visual dos projetos');
      root.insertAdjacentElement('beforebegin', panel);
    }

    const count = cards.length;
    const pending = cards.filter(card => card.dataset.shipPending === '1').length;
    const active = cards.filter(card => {
      const eyebrow = card.querySelector('.eyebrow')?.textContent || '';
      return String(eyebrow).toLocaleLowerCase('pt-BR').includes('active');
    }).length;
    const avg = key => count
      ? Math.round(cards.reduce((sum, card) => sum + Number(card.dataset[key] || 0), 0) / count)
      : 0;
    const energy = avg('shipEnergy');
    const shield = avg('shipShield');
    const activePct = count ? Math.round(active * 100 / count) : 0;
    const ready = Math.max(0, count - pending);
    const readyPct = count ? Math.round(ready * 100 / count) : 0;
    const pendingPct = count ? 100 - readyPct : 0;

    panel.innerHTML = `
      ${overviewMetric('PROJETOS', count ? 100 : 0, String(count), '#31a8ff')}
      ${overviewMetric('ATIVOS', activePct, String(active), '#35e58a')}
      ${overviewMetric('ENERGIA', energy, `${energy}%`, '#9b6cff')}
      ${overviewMetric('ESCUDO', shield, `${shield}%`, '#56bfff')}
      <div class="project-visual-status" title="${ready} prontos · ${pending} pendentes">
        <span>FROTA</span>
        <div class="project-visual-status-track">
          <i class="project-visual-status-ready" style="width:${readyPct}%"></i>
          <i class="project-visual-status-pending" style="width:${pendingPct}%"></i>
        </div>
        <strong>${pending ? `${pending} PEND.` : 'OK'}</strong>
      </div>
    `;
  }

  let scheduled = false;
  function enhanceAll() {
    scheduled = false;
    const cards = Array.from(document.querySelectorAll(`${ROOT_SELECTOR} > .project-card`));
    cards.forEach((card, index) => enhance(card, index));
    renderOverview(cards);
  }

  function scheduleEnhance() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(enhanceAll);
  }

  function start() {
    ensureStyles();
    const root = document.querySelector(ROOT_SELECTOR);
    if (!root) return;
    enhanceAll();
    const observer = new MutationObserver(scheduleEnhance);
    observer.observe(root, {childList: true, subtree: true, characterData: true});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, {once: true});
  } else {
    start();
  }
})();
