(() => {
  const ROOT_SELECTOR = '#projects-list';
  const STYLE_ID = 'devpilot-project-ships-style';

  const themes = [
    {name: 'azul', accent: '#31a8ff', accent2: '#7bdcff'},
    {name: 'vermelha', accent: '#ff5252', accent2: '#ff9a82'},
    {name: 'verde', accent: '#35e58a', accent2: '#90ffc0'},
    {name: 'violeta', accent: '#9b6cff', accent2: '#d4a4ff'},
    {name: 'ciano', accent: '#29dfe4', accent2: '#8fffff'},
    {name: 'dourada', accent: '#ffba43', accent2: '#ffe38b'},
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

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #projects-list {
        align-items: start;
      }

      #projects-list .project-card.project-ship-card {
        --ship-accent: #31a8ff;
        --ship-accent-2: #7bdcff;
        position: relative;
        overflow: hidden;
        border-color: color-mix(in srgb, var(--ship-accent) 30%, #244132);
        background:
          radial-gradient(circle at 50% 38%, color-mix(in srgb, var(--ship-accent) 10%, transparent), transparent 34%),
          linear-gradient(160deg, #091824 0%, #071d18 72%, #08131c 100%);
        box-shadow: 0 18px 48px #0008, inset 0 1px 0 #ffffff0a;
        transition: border-color .2s ease, transform .2s ease, box-shadow .2s ease;
      }

      #projects-list .project-card.project-ship-card:hover {
        transform: translateY(-2px);
        border-color: color-mix(in srgb, var(--ship-accent) 56%, #244132);
        box-shadow: 0 22px 58px #0009, 0 0 28px color-mix(in srgb, var(--ship-accent) 12%, transparent);
      }

      #projects-list .project-ship-hangar {
        position: relative;
        min-height: 228px;
        margin: 14px 0 12px;
        overflow: hidden;
        border: 1px solid color-mix(in srgb, var(--ship-accent) 32%, #203249);
        border-radius: 13px;
        background:
          radial-gradient(ellipse at 50% 82%, color-mix(in srgb, var(--ship-accent) 20%, transparent) 0, transparent 44%),
          radial-gradient(circle at 50% 10%, #ffffff0b 0, transparent 46%),
          linear-gradient(180deg, #06101a 0%, #081522 54%, #07120f 100%);
        isolation: isolate;
      }

      #projects-list .project-ship-hangar::before,
      #projects-list .project-ship-hangar::after {
        content: '';
        position: absolute;
        inset: 0;
        pointer-events: none;
      }

      #projects-list .project-ship-hangar::before {
        opacity: .34;
        background-image:
          radial-gradient(circle at 12% 16%, #fff 0 1px, transparent 1.3px),
          radial-gradient(circle at 76% 23%, #fff 0 1px, transparent 1.3px),
          radial-gradient(circle at 36% 42%, #fff 0 1px, transparent 1.3px),
          radial-gradient(circle at 91% 48%, #fff 0 1px, transparent 1.3px),
          radial-gradient(circle at 23% 64%, #fff 0 1px, transparent 1.3px);
      }

      #projects-list .project-ship-hangar::after {
        inset: auto 8% 16px;
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--ship-accent), transparent);
        box-shadow: 0 -17px 40px color-mix(in srgb, var(--ship-accent) 32%, transparent);
        opacity: .72;
      }

      #projects-list .project-ship-label {
        position: absolute;
        z-index: 3;
        top: 10px;
        left: 11px;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 8px;
        border: 1px solid color-mix(in srgb, var(--ship-accent) 45%, transparent);
        border-radius: 999px;
        background: #06111bd6;
        color: var(--ship-accent-2);
        font-size: 9px;
        font-weight: 850;
        letter-spacing: .12em;
      }

      #projects-list .project-ship-label::before {
        content: '';
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--ship-accent);
        box-shadow: 0 0 12px var(--ship-accent);
      }

      #projects-list .project-ship-svg {
        position: relative;
        z-index: 2;
        display: block;
        width: 100%;
        height: 166px;
        margin-top: 25px;
        filter: drop-shadow(0 18px 14px #0009);
        animation: devpilot-ship-hover 4.8s ease-in-out infinite;
      }

      @keyframes devpilot-ship-hover {
        0%, 100% { transform: translateY(1px); }
        50% { transform: translateY(-5px); }
      }

      #projects-list .project-ship-hud {
        position: absolute;
        z-index: 4;
        left: 10px;
        right: 10px;
        bottom: 9px;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
      }

      #projects-list .project-ship-meter {
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: 6px;
        min-width: 0;
        padding: 6px 7px;
        border: 1px solid #ffffff10;
        border-radius: 8px;
        background: #041018d9;
      }

      #projects-list .project-ship-meter span {
        color: #9fb3c9;
        font-size: 8px;
        font-weight: 800;
        letter-spacing: .06em;
      }

      #projects-list .project-ship-meter strong {
        color: #dceafb;
        font-size: 9px;
      }

      #projects-list .project-ship-meter-track {
        height: 5px;
        overflow: hidden;
        border-radius: 999px;
        background: #193143;
      }

      #projects-list .project-ship-meter-fill {
        display: block;
        width: var(--ship-meter, 80%);
        height: 100%;
        border-radius: inherit;
        background: linear-gradient(90deg, var(--ship-accent), var(--ship-accent-2));
        box-shadow: 0 0 10px color-mix(in srgb, var(--ship-accent) 56%, transparent);
      }

      #projects-list .project-ship-meter.shield .project-ship-meter-fill {
        background: linear-gradient(90deg, #3f8fff, #66ddff);
        box-shadow: 0 0 10px #3dafff75;
      }

      #projects-list .project-ship-card > .eyebrow:first-child {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 9px;
        border: 1px solid #2ad89755;
        border-radius: 999px;
        background: #08312070;
      }

      #projects-list .project-ship-card > .eyebrow:first-child::before {
        content: '';
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #38e99a;
        box-shadow: 0 0 10px #38e99a;
      }

      #projects-list .project-ship-card code {
        border-color: color-mix(in srgb, var(--ship-accent) 18%, #203249);
        background: #06111d;
      }

      #projects-list .project-ship-card button.project-ship-analyze,
      #projects-list .project-ship-card button.project-ship-tests,
      #projects-list .project-ship-card button.project-ship-play,
      #projects-list .project-ship-card button.project-ship-task {
        min-height: 38px;
        margin: 2px;
        border: 1px solid #ffffff16;
        border-radius: 9px;
        background: #071620;
        font-weight: 800;
        transition: transform .15s ease, border-color .15s ease, box-shadow .15s ease;
      }

      #projects-list .project-ship-card button.project-ship-analyze {
        color: #42e8b0;
        border-color: #32d99b55;
        background: #0a2b22;
      }

      #projects-list .project-ship-card button.project-ship-tests {
        color: #69bfff;
        border-color: #3297e455;
        background: #092135;
      }

      #projects-list .project-ship-card button.project-ship-play {
        color: #c18cff;
        border-color: #9a63ff66;
        background: #20143d;
        box-shadow: inset 0 0 20px #8d4fff12;
      }

      #projects-list .project-ship-card button.project-ship-task {
        color: #59eea7;
        border-color: #38d78355;
        background: #0c2b20;
      }

      #projects-list .project-ship-card button.project-ship-analyze:hover,
      #projects-list .project-ship-card button.project-ship-tests:hover,
      #projects-list .project-ship-card button.project-ship-play:hover,
      #projects-list .project-ship-card button.project-ship-task:hover {
        transform: translateY(-1px);
        border-color: currentColor;
        box-shadow: 0 7px 18px #0007;
      }

      @media (prefers-reduced-motion: reduce) {
        #projects-list .project-ship-svg { animation: none; }
        #projects-list .project-card.project-ship-card { transition: none; }
      }

      @media (max-width: 900px) {
        #projects-list .project-ship-hangar { min-height: 206px; }
        #projects-list .project-ship-svg { height: 148px; }
      }

      @media (max-width: 520px) {
        #projects-list .project-ship-card { padding: 15px; }
        #projects-list .project-ship-hangar { min-height: 188px; margin: 10px 0; }
        #projects-list .project-ship-svg { height: 132px; margin-top: 28px; }
        #projects-list .project-ship-hud { grid-template-columns: 1fr; gap: 5px; }
        #projects-list .project-ship-meter { padding: 4px 6px; }
      }
    `;
    document.head.appendChild(style);
  }

  function shipSvg(id, accent, accent2, variant) {
    const fin = variant % 3;
    const sideWing = fin === 0 ? 68 : fin === 1 ? 88 : 54;
    const nose = fin === 2 ? 31 : 43;
    return `
      <svg class="project-ship-svg" viewBox="0 0 520 270" role="img" aria-label="Nave do projeto">
        <defs>
          <linearGradient id="${id}-hull" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#edf5ff"/>
            <stop offset="0.34" stop-color="#9baaba"/>
            <stop offset="0.68" stop-color="#3a4654"/>
            <stop offset="1" stop-color="#141c26"/>
          </linearGradient>
          <linearGradient id="${id}-dark" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#485664"/>
            <stop offset="1" stop-color="#101821"/>
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

        <ellipse cx="260" cy="229" rx="166" ry="24" fill="#02080d" opacity=".8"/>
        <ellipse cx="260" cy="227" rx="145" ry="16" fill="none" stroke="${accent}" stroke-width="2" opacity=".55"/>
        <ellipse cx="260" cy="227" rx="105" ry="9" fill="${accent}" opacity=".08" filter="url(#${id}-glow)"/>

        <g transform="translate(0 1)">
          <path d="M220 115 L${sideWing} 190 L190 188 L237 155 Z" fill="url(#${id}-dark)" stroke="#93a2b0" stroke-opacity=".35"/>
          <path d="M300 115 L${520 - sideWing} 190 L330 188 L283 155 Z" fill="url(#${id}-dark)" stroke="#93a2b0" stroke-opacity=".35"/>
          <path d="M224 135 L103 188 L194 172 L236 150 Z" fill="url(#${id}-accent)" opacity=".78"/>
          <path d="M296 135 L417 188 L326 172 L284 150 Z" fill="url(#${id}-accent)" opacity=".78"/>

          <path d="M260 ${nose} C292 69 321 116 326 174 L299 211 L221 211 L194 174 C199 116 228 69 260 ${nose} Z" fill="url(#${id}-hull)" stroke="#c8d5e0" stroke-opacity=".38" stroke-width="2"/>
          <path d="M260 67 C278 82 291 104 295 126 L282 147 L238 147 L225 126 C229 104 242 82 260 67 Z" fill="#07111a" stroke="${accent}" stroke-width="3"/>
          <path d="M260 76 C271 87 278 99 281 111 L270 120 L250 120 L239 111 C242 99 249 87 260 76 Z" fill="url(#${id}-accent)" opacity=".86" filter="url(#${id}-glow)"/>

          <path d="M217 171 L245 161 L245 198 L220 201 Z" fill="#111923" stroke="#82909d" stroke-opacity=".28"/>
          <path d="M303 171 L275 161 L275 198 L300 201 Z" fill="#111923" stroke="#82909d" stroke-opacity=".28"/>
          <path d="M253 151 L267 151 L274 205 L246 205 Z" fill="#202b36"/>
          <path d="M252 159 L268 159 L268 191 L252 191 Z" fill="url(#${id}-accent)" opacity=".76"/>

          <rect x="212" y="198" width="32" height="10" rx="4" fill="${accent}" opacity=".9" filter="url(#${id}-glow)"/>
          <rect x="276" y="198" width="32" height="10" rx="4" fill="${accent}" opacity=".9" filter="url(#${id}-glow)"/>
          <rect x="250" y="204" width="20" height="8" rx="4" fill="${accent2}" opacity=".95" filter="url(#${id}-glow)"/>

          <path d="M220 126 L200 158" stroke="${accent}" stroke-width="4" stroke-linecap="round" opacity=".85"/>
          <path d="M300 126 L320 158" stroke="${accent}" stroke-width="4" stroke-linecap="round" opacity=".85"/>
          <path d="M224 187 L187 193" stroke="${accent2}" stroke-width="3" stroke-linecap="round" opacity=".78"/>
          <path d="M296 187 L333 193" stroke="${accent2}" stroke-width="3" stroke-linecap="round" opacity=".78"/>
        </g>
      </svg>
    `;
  }

  function styleActions(card) {
    card.querySelectorAll('button').forEach(button => {
      const label = String(button.textContent || '').toLocaleLowerCase('pt-BR').trim();
      button.classList.toggle('project-ship-analyze', label.includes('analisar'));
      button.classList.toggle('project-ship-tests', label.includes('teste'));
      button.classList.toggle('project-ship-play', label.includes('jogar'));
      button.classList.toggle('project-ship-task', label.includes('nova tarefa'));
    });
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
    const id = `devpilot-${safeId(title)}-${index}-${hash.toString(36).slice(0, 6)}`;

    card.style.setProperty('--ship-accent', theme.accent);
    card.style.setProperty('--ship-accent-2', theme.accent2);
    card.classList.add('project-ship-card');

    const hangar = document.createElement('div');
    hangar.className = 'project-ship-hangar';
    hangar.setAttribute('aria-label', `Nave do projeto ${title}`);
    hangar.innerHTML = `
      <span class="project-ship-label">NAVE DO PROJETO</span>
      ${shipSvg(id, theme.accent, theme.accent2, hash)}
      <div class="project-ship-hud" aria-label="Status da nave">
        <div class="project-ship-meter energy">
          <span>ENERGIA</span>
          <i class="project-ship-meter-track"><b class="project-ship-meter-fill" style="--ship-meter:${energy}%"></b></i>
          <strong>${energy}%</strong>
        </div>
        <div class="project-ship-meter shield">
          <span>ESCUDO</span>
          <i class="project-ship-meter-track"><b class="project-ship-meter-fill" style="--ship-meter:${shield}%"></b></i>
          <strong>${shield}%</strong>
        </div>
      </div>
    `;

    const description = card.querySelector('h3 + p') || card.querySelector('p');
    if (description) description.insertAdjacentElement('afterend', hangar);
    else card.querySelector('h3')?.insertAdjacentElement('afterend', hangar);

    card.dataset.shipEnhanced = '1';
  }

  let scheduled = false;
  function enhanceAll() {
    scheduled = false;
    document.querySelectorAll(`${ROOT_SELECTOR} > .project-card`).forEach((card, index) => enhance(card, index));
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
