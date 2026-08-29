(() => {
  'use strict';

  const STYLE_ID = 'devpilot-project-identity-style';
  const DIALOG_ID = 'devpilot-project-logo-dialog';
  const MODE_KEY = 'devpilot-project-card-skin-v1';
  const CACHE_KEY = 'devpilot-project-identity-cache-v2';
  const MAX_FILE_BYTES = 3 * 1024 * 1024;
  const MAX_LOGO_LENGTH = 160000;
  const MAX_VISIBLE_IDENTITIES = 50;
  const MANAGEMENT_ROLES = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);

  let editor = null;
  let uploadedLogo = '';
  let hydrationSequence = 0;

  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  }[char]));

  function safeObject(value) {
    try {
      const parsed = typeof value === 'string' ? JSON.parse(value || '{}') : value;
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
    } catch (_) {
      return {};
    }
  }

  function currentRole() {
    try {
      return String(state?.currentUser?.role || '').toUpperCase();
    } catch (_) {
      return '';
    }
  }

  function canManage() {
    return MANAGEMENT_ROLES.has(currentRole());
  }

  function notify(message) {
    try {
      if (typeof toast === 'function') return toast(message);
    } catch (_) {
      // Keep navigation available if the global toaster is unavailable.
    }
    console.info(`[DevPilot] ${message}`);
  }

  async function apiRequest(path, options = {}) {
    const token = String(localStorage.getItem('devpilot-token') || '').trim();
    const headers = {Authorization: `Bearer ${token}`, ...(options.headers || {})};
    if (options.body) headers['Content-Type'] = 'application/json';
    const response = await fetch(`/api${path}`, {...options, headers, cache: 'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data?.detail === 'string' ? data.detail : 'Falha na operação';
      throw new Error(detail);
    }
    return data;
  }

  function identityCache() {
    return safeObject(localStorage.getItem(CACHE_KEY));
  }

  function normalizedIdentity(identity) {
    const accent = /^#[0-9a-f]{6}$/i.test(String(identity?.accent || '')) ? String(identity.accent) : '#2dd4a8';
    return {
      logo: String(identity?.logo || ''),
      accent,
      updated_at: String(identity?.updated_at || ''),
    };
  }

  function cachedIdentity(projectId) {
    return normalizedIdentity(identityCache()[projectId]);
  }

  function cacheIdentity(projectId, identity) {
    if (!projectId) return;
    const cache = identityCache();
    cache[projectId] = normalizedIdentity(identity);
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(cache));
    } catch (_) {
      // Server state remains authoritative when storage is restricted.
    }
  }

  function projectId(card) {
    return String(
      card?.dataset?.projectId
      || card?.querySelector('.analyze[data-id]')?.dataset?.id
      || card?.querySelector('[data-project-task]')?.dataset?.projectTask
      || ''
    );
  }

  function projectName(card) {
    return String(card?.querySelector('.project-identity-copy h3')?.textContent || card?.querySelector('h3')?.textContent || 'Projeto').trim();
  }

  function initials(name) {
    return (String(name || 'Projeto').trim().split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0]).join('') || 'P').toUpperCase();
  }

  function hashProject(value) {
    let hash = 2166136261;
    for (const char of String(value || 'project')) {
      hash ^= char.charCodeAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function shipMarkup(id, accent) {
    const hash = hashProject(id);
    const energy = 72 + (hash % 27);
    const shield = 60 + ((hash >>> 5) % 39);
    const ready = 68 + ((hash >>> 10) % 31);
    return `
      <div class="project-ship-hangar" aria-label="Nave do projeto">
        <span class="project-ship-label">NAVE DO PROJETO</span>
        <div class="project-ship-stage" style="--project-ship-accent:${escapeHtml(accent)}">
          <svg class="project-ship" viewBox="0 0 220 92" role="img" aria-label="Nave tecnológica do projeto">
            <defs><linearGradient id="ship-${escapeHtml(id)}" x1="0" x2="1"><stop stop-color="${escapeHtml(accent)}"/><stop offset="1" stop-color="#3d7cff"/></linearGradient></defs>
            <path d="M34 54 78 34 105 12 134 34 188 54 147 63 126 81 95 81 74 63Z" fill="#071522" stroke="url(#ship-${escapeHtml(id)})" stroke-width="3"/>
            <path d="M88 47 105 25 124 47 116 62H96Z" fill="url(#ship-${escapeHtml(id)})" opacity=".7"/>
            <path d="M55 57 82 50 73 66Z" fill="${escapeHtml(accent)}" opacity=".65"/><path d="m157 50 26 7-19 9Z" fill="#3d7cff" opacity=".65"/>
            <circle cx="105" cy="51" r="6" fill="#e9ffff"/><circle cx="105" cy="51" r="12" fill="none" stroke="${escapeHtml(accent)}" opacity=".45"/>
          </svg>
          <div class="project-ship-stats">
            <span><b>${energy}%</b> energia</span><span><b>${shield}%</b> escudo</span><span><b>${ready}%</b> pronto</span>
          </div>
        </div>
      </div>`;
  }

  function logoMarkup(name, identity, editable) {
    const logo = String(identity?.logo || '');
    const visual = logo
      ? `<img src="${escapeHtml(logo)}" alt="Logo de ${escapeHtml(name)}">`
      : `<span class="project-logo-initials">${escapeHtml(initials(name))}</span>`;
    if (!editable) return `<span class="project-logo-static" aria-label="Identidade visual do projeto">${visual}</span>`;
    return `<button type="button" class="project-logo-control" aria-label="Editar logo de ${escapeHtml(name)}" title="Editar logo">${visual}<i>✎</i></button>`;
  }

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #projects-view .section-head{align-items:center;gap:12px;flex-wrap:wrap}
      #projects-view .section-head>div:first-child{min-width:0;flex:1 1 300px}
      .project-card-skin-switch{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px;padding:4px;border:1px solid #263b49;border-radius:12px;background:#07121a}
      .project-card-skin-switch button{min-height:34px;padding:7px 11px;border:0;border-radius:9px;background:transparent;color:#8ea6b5;font:inherit;font-size:11px;font-weight:800;white-space:nowrap;cursor:pointer}
      .project-card-skin-switch button[aria-pressed="true"]{background:#17303d;color:#effbff;box-shadow:inset 0 0 0 1px #3c5d6d}
      html[data-project-card-skin="game"] .project-card-skin-switch button[data-project-card-skin="game"]{background:linear-gradient(135deg,#12382f,#102441);color:#75ffd4;box-shadow:inset 0 0 0 1px #31d9a2,0 0 16px #31d9a21c}

      #projects-view #projects-list.cards{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr))!important;align-items:stretch!important;gap:14px!important;min-width:0}
      #projects-view #projects-list>.project-card{min-width:0!important;min-height:0!important;height:auto!important;max-height:none!important;overflow:visible!important;padding:15px!important}
      #projects-list .project-card>p{display:-webkit-box;min-height:2.8em;max-height:2.8em;margin:7px 0;overflow:hidden;color:#91a8b5;font-size:12px;line-height:1.4;-webkit-box-orient:vertical;-webkit-line-clamp:2}
      #projects-list .project-card>code{display:block;width:100%;max-width:100%!important;overflow:hidden!important;text-overflow:ellipsis;white-space:nowrap!important}
      #projects-list .project-card .list-row{display:flex;align-items:center;gap:8px;min-width:0;margin-top:8px}
      #projects-list .project-card .list-row>small{min-width:0;flex:1 1 auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      #projects-list .project-card .list-row>div{display:flex;gap:6px;min-width:0;flex:0 1 auto}

      #projects-list .project-identity-head{display:grid;grid-template-columns:58px minmax(0,1fr);align-items:center;gap:11px;min-width:0;margin-bottom:8px}
      #projects-list .project-identity-copy{min-width:0}
      #projects-list .project-identity-copy .eyebrow{margin:0 0 4px!important;max-width:100%}
      #projects-list .project-identity-copy h3{margin:0!important;overflow:hidden;color:#eff8fb;font-size:18px;line-height:1.2;text-overflow:ellipsis;white-space:nowrap}
      #projects-list .project-logo-control,#projects-list .project-logo-static{position:relative;display:grid;width:58px;height:58px;place-items:center;overflow:hidden;border:1px solid color-mix(in srgb,var(--project-accent,#2dd4a8) 58%,#334957);border-radius:15px;background:linear-gradient(145deg,#112535,#07121a);box-shadow:inset 0 1px 0 #ffffff10,0 8px 20px #0005;color:#eafff8}
      #projects-list button.project-logo-control{padding:0;cursor:pointer}
      #projects-list .project-logo-control:hover{border-color:var(--project-accent,#2dd4a8);transform:translateY(-1px)}
      #projects-list .project-logo-control img,#projects-list .project-logo-static img{width:100%;height:100%;object-fit:contain;background:#061018}
      #projects-list .project-logo-initials{font-size:17px;font-weight:900;letter-spacing:.04em}
      #projects-list .project-logo-control i{position:absolute;right:3px;bottom:3px;display:grid;width:18px;height:18px;place-items:center;border:1px solid #ffffff28;border-radius:7px;background:#07131eee;color:var(--project-accent,#2dd4a8);font-size:10px;font-style:normal}

      #projects-list .project-card-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:11px}
      #projects-list .project-card-actions button,#projects-list .project-card .list-row button{display:inline-flex!important;min-width:0!important;min-height:36px!important;align-items:center!important;justify-content:center!important;margin:0!important;padding:7px 9px!important;overflow:hidden;border-radius:9px!important;font-size:11px!important;font-weight:800!important;line-height:1.15!important;text-overflow:ellipsis;white-space:nowrap!important;word-break:normal!important}
      #projects-list .project-card-actions .analyze{border-color:#286751!important;background:#0b2b21!important;color:#83f2c4!important}
      #projects-list .project-card-actions [data-project-task]{border-color:#255b7a!important;background:#0b2030!important;color:#9bd8ff!important}
      #projects-list .project-card-actions .delete-project{border-color:#732c34!important;background:#291116!important;color:#ff8993!important}
      #projects-list .project-skin-action::before{content:attr(data-project-action-icon);font-size:12px;margin-right:5px}

      .project-ship-hangar{display:none}
      html[data-project-card-skin="professional"] #projects-list .project-card{border-color:#263b47!important;background:linear-gradient(155deg,#0e1922,#091219 72%)!important;box-shadow:0 12px 30px #0004,inset 0 1px 0 #ffffff08!important}
      html[data-project-card-skin="professional"] #projects-list .project-card:hover{transform:translateY(-2px);border-color:color-mix(in srgb,var(--project-accent,#2dd4a8) 45%,#334957)!important}

      html[data-project-card-skin="game"] #projects-list .project-logo-control,html[data-project-card-skin="game"] #projects-list .project-logo-static{display:none!important}
      html[data-project-card-skin="game"] #projects-list .project-identity-head{grid-template-columns:minmax(0,1fr);margin-bottom:3px}
      html[data-project-card-skin="game"] #projects-list .project-identity-copy h3{color:#dcfff2;font-size:16px;text-transform:uppercase;letter-spacing:.04em}
      html[data-project-card-skin="game"] #projects-list .project-card{position:relative;border-color:#185848!important;background:radial-gradient(circle at 50% 12%,#12364a 0,#0a1724 42%,#071018 100%)!important;box-shadow:0 12px 34px #0008,inset 0 1px 0 #57ffd51d!important}
      html[data-project-card-skin="game"] #projects-list .project-card::after{content:"";position:absolute;inset:0;pointer-events:none;border-radius:inherit;background-image:radial-gradient(#ffffff25 1px,transparent 1px);background-size:24px 24px;mask-image:linear-gradient(to bottom,#0007,transparent 48%)}
      html[data-project-card-skin="game"] #projects-list .project-ship-hangar{position:relative;z-index:1;display:block;margin:5px 0 9px;padding:8px;border:1px solid color-mix(in srgb,var(--project-accent,#2dd4a8) 38%,#153245);border-radius:12px;background:#06101ab8}
      html[data-project-card-skin="game"] #projects-list .project-ship-label{display:block;margin-bottom:2px;color:#69cbb3;font-size:8px;font-weight:900;letter-spacing:.15em}
      html[data-project-card-skin="game"] #projects-list .project-ship-stage{display:grid;grid-template-columns:minmax(0,1fr) 70px;align-items:center;gap:7px}
      html[data-project-card-skin="game"] #projects-list .project-ship{display:block;width:100%;max-height:84px;filter:drop-shadow(0 0 12px color-mix(in srgb,var(--project-ship-accent) 40%,transparent))}
      html[data-project-card-skin="game"] #projects-list .project-ship-stats{display:grid;gap:4px;color:#80a5b6;font-size:7px;text-transform:uppercase}
      html[data-project-card-skin="game"] #projects-list .project-ship-stats span{display:grid;padding:4px 5px;border:1px solid #1c3b4b;border-radius:6px;background:#061019}
      html[data-project-card-skin="game"] #projects-list .project-ship-stats b{color:#dfffee;font-size:9px}
      html[data-project-card-skin="game"] #projects-list .project-card-actions{position:relative;z-index:1;grid-template-columns:repeat(auto-fit,minmax(38px,1fr));gap:5px;margin-top:7px}
      html[data-project-card-skin="game"] #projects-list .project-card-actions button.project-skin-action{min-height:34px!important;padding:5px!important;font-size:0!important}
      html[data-project-card-skin="game"] #projects-list .project-card-actions button.project-skin-action::before{margin:0!important;font-size:15px!important}
      html[data-project-card-skin="game"] #projects-list .project-card>p{min-height:1.4em;max-height:1.4em;-webkit-line-clamp:1}

      #${DIALOG_ID}{width:min(520px,calc(100vw - 28px));max-height:calc(100dvh - 28px);padding:0;overflow:auto;border:1px solid #304958;border-radius:18px;background:#0a151e;color:#eaf3f7;box-shadow:0 30px 90px #000c}
      #${DIALOG_ID}::backdrop{background:#000b;backdrop-filter:blur(3px)}
      #${DIALOG_ID} .project-logo-modal{padding:20px}
      #${DIALOG_ID} .project-logo-head{display:flex;align-items:start;justify-content:space-between;gap:12px;margin-bottom:16px}
      #${DIALOG_ID} .project-logo-head h2{margin:3px 0 0;font-size:21px}
      #${DIALOG_ID} .project-logo-close{width:34px;height:34px;border:1px solid #304958;border-radius:10px;background:#10202b;color:#d5e3e9;cursor:pointer}
      #${DIALOG_ID} .project-logo-grid{display:grid;grid-template-columns:118px minmax(0,1fr);gap:16px;align-items:start}
      #${DIALOG_ID} .project-logo-preview{display:grid;width:118px;height:118px;place-items:center;overflow:hidden;border:1px solid #365465;border-radius:22px;background:#07121a;color:#eafff8;font-size:30px;font-weight:900}
      #${DIALOG_ID} .project-logo-preview img{width:100%;height:100%;object-fit:contain}
      #${DIALOG_ID} .project-logo-fields{display:grid;gap:11px;min-width:0}
      #${DIALOG_ID} label{display:grid;gap:6px;color:#9eb3bf;font-size:11px;font-weight:800}
      #${DIALOG_ID} input[type="file"],#${DIALOG_ID} input[type="url"]{width:100%;min-width:0;box-sizing:border-box;border:1px solid #2b4555;border-radius:10px;background:#07121a;color:#edf7fb;padding:10px}
      #${DIALOG_ID} .project-logo-color{display:grid;grid-template-columns:1fr 54px;align-items:center;gap:10px}
      #${DIALOG_ID} input[type="color"]{width:54px;height:38px;padding:3px;border:1px solid #2b4555;border-radius:9px;background:#07121a}
      #${DIALOG_ID} .project-logo-hint{margin:12px 0 0;color:#778f9c;font-size:10px;line-height:1.5}
      #${DIALOG_ID} .project-logo-actions{display:grid;grid-template-columns:auto 1fr 1fr;gap:8px;margin-top:18px}
      #${DIALOG_ID} .project-logo-actions button{min-height:38px;padding:8px 12px;border-radius:10px;font-weight:800;cursor:pointer}
      #${DIALOG_ID} .remove{border:1px solid #66313a;background:#271116;color:#ff9099}
      #${DIALOG_ID} .cancel{border:1px solid #304958;background:#10202b;color:#d5e3e9}
      #${DIALOG_ID} .save{border:1px solid #298f6e;background:#0e654d;color:#effff9}
      #${DIALOG_ID} button:disabled{opacity:.55;cursor:wait}

      @media (min-width:1500px){#projects-view #projects-list.cards{grid-template-columns:repeat(4,minmax(0,1fr))!important}}
      @media (max-width:1180px){#projects-view #projects-list.cards{grid-template-columns:repeat(2,minmax(0,1fr))!important}}
      @media (max-width:760px){
        #projects-view .section-head{align-items:stretch}
        #projects-view .section-head>div:first-child{flex-basis:100%}
        .project-card-skin-switch{order:2;width:100%;box-sizing:border-box}
        #projects-view .section-head>[data-project-builder-open]{order:3;width:100%}
        #projects-view #projects-list.cards{grid-template-columns:minmax(0,1fr)!important;gap:11px!important}
        #projects-view #projects-list>.project-card{padding:13px!important}
        #projects-list .project-card-actions{grid-template-columns:repeat(2,minmax(0,1fr))}
        html[data-project-card-skin="game"] #projects-list .project-ship-stage{grid-template-columns:minmax(0,1fr) 76px}
        #${DIALOG_ID} .project-logo-grid{grid-template-columns:1fr}
        #${DIALOG_ID} .project-logo-preview{width:94px;height:94px;border-radius:18px}
        #${DIALOG_ID} .project-logo-actions{grid-template-columns:1fr 1fr}
        #${DIALOG_ID} .remove{grid-column:1/-1;order:3}
      }
      @media (max-width:420px){
        #projects-list .project-identity-head{grid-template-columns:50px minmax(0,1fr);gap:9px}
        #projects-list .project-logo-control,#projects-list .project-logo-static{width:50px;height:50px;border-radius:13px}
        #projects-list .project-card-actions button,#projects-list .project-card .list-row button{min-height:40px!important;font-size:10px!important}
      }
      @media (prefers-reduced-motion:reduce){#projects-list .project-logo-control,#projects-list .project-card{transition:none!important}}
    `;
    document.head.appendChild(style);
  }

  function setMode(mode, announce = false) {
    const next = mode === 'game' ? 'game' : 'professional';
    document.documentElement.dataset.projectCardSkin = next;
    localStorage.setItem(MODE_KEY, next);
    document.querySelectorAll('.project-card-skin-switch [data-project-card-skin]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.projectCardSkin === next));
    });
    if (announce) notify(next === 'game' ? 'Estilo Jogo ativado.' : 'Estilo Profissional ativado.');
  }

  function ensureModeSwitch() {
    const head = document.querySelector('#projects-view .section-head');
    if (!head || head.querySelector('.project-card-skin-switch')) return;
    const switcher = document.createElement('div');
    switcher.className = 'project-card-skin-switch';
    switcher.setAttribute('role', 'group');
    switcher.setAttribute('aria-label', 'Estilo dos cartões de projeto');
    switcher.innerHTML = '<button type="button" data-project-card-skin="professional">▦ Profissional</button><button type="button" data-project-card-skin="game">✦ Jogo</button>';
    const create = head.querySelector('[data-project-builder-open]');
    if (create) head.insertBefore(switcher, create);
    else head.appendChild(switcher);
    switcher.querySelectorAll('button').forEach(button => button.addEventListener('click', () => setMode(button.dataset.projectCardSkin, true)));
    setMode(localStorage.getItem(MODE_KEY) || 'professional');
  }

  function actionIcon(button) {
    if (button.matches('.analyze')) return '◈';
    if (button.matches('[data-project-task]')) return '✦';
    if (button.matches('.delete-project')) return '×';
    const label = String(button.textContent || '').toLowerCase();
    if (label.includes('teste')) return '✓';
    return '›';
  }

  function decorateAction(button) {
    const label = String(button.textContent || '').trim();
    button.classList.add('project-skin-action');
    button.dataset.projectActionIcon = actionIcon(button);
    if (label && !button.title) button.title = label;
    if (label && !button.getAttribute('aria-label')) button.setAttribute('aria-label', label);
  }

  function bindLogoButton(button, card) {
    if (!button?.matches('.project-logo-control')) return;
    button.addEventListener('click', () => void openEditor(card));
  }

  function renderIdentity(card, identity) {
    const id = projectId(card);
    const name = projectName(card);
    const normalized = normalizedIdentity(identity);
    if (id) card.dataset.projectId = id;
    card.style.setProperty('--project-accent', normalized.accent);
    const existing = card.querySelector('.project-logo-control,.project-logo-static');
    if (!existing) return;
    const holder = document.createElement('div');
    holder.innerHTML = logoMarkup(name, normalized, canManage());
    const replacement = holder.firstElementChild;
    existing.replaceWith(replacement);
    bindLogoButton(replacement, card);
  }

  function ensureShip(card) {
    if (card.querySelector(':scope>.project-ship-hangar')) return;
    const id = projectId(card) || projectName(card);
    const identity = cachedIdentity(id);
    const holder = document.createElement('div');
    holder.innerHTML = shipMarkup(id, identity.accent);
    const ship = holder.firstElementChild;
    const description = card.querySelector(':scope>p');
    if (description) description.insertAdjacentElement('afterend', ship);
    else card.querySelector('.project-identity-head')?.insertAdjacentElement('afterend', ship);
  }

  function enhanceCard(card) {
    const id = projectId(card);
    const title = card.querySelector('h3');
    if (!title) return;
    const name = String(title.textContent || 'Projeto').trim();
    if (id) card.dataset.projectId = id;

    if (!card.querySelector('.project-identity-head')) {
      const eyebrow = card.querySelector(':scope>.eyebrow');
      const head = document.createElement('div');
      head.className = 'project-identity-head';
      const copy = document.createElement('div');
      copy.className = 'project-identity-copy';
      if (eyebrow) copy.appendChild(eyebrow);
      copy.appendChild(title);
      const logoHolder = document.createElement('div');
      logoHolder.innerHTML = logoMarkup(name, cachedIdentity(id), canManage());
      const logo = logoHolder.firstElementChild;
      head.append(logo, copy);
      card.insertBefore(head, card.firstChild);
      card.style.setProperty('--project-accent', cachedIdentity(id).accent);
      bindLogoButton(logo, card);
    }

    ensureShip(card);

    let actions = card.querySelector(':scope>.project-card-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'project-card-actions';
      card.appendChild(actions);
    }
    const actionSource = card.querySelector('.list-row>div:last-child');
    if (actionSource) Array.from(actionSource.querySelectorAll('button')).forEach(button => actions.appendChild(button));
    actions.querySelectorAll('button').forEach(decorateAction);
  }

  function enhanceProjects() {
    ensureModeSwitch();
    document.querySelectorAll('#projects-list>.project-card').forEach(enhanceCard);
    void hydrateIdentities();
  }

  function wrapProjectRenderer() {
    const original = window.renderProjects;
    if (typeof original !== 'function' || original.__devpilotIdentityWrapped) return;
    const wrapped = function (...args) {
      const result = original.apply(this, args);
      enhanceProjects();
      return result;
    };
    wrapped.__devpilotIdentityWrapped = true;
    window.renderProjects = wrapped;
  }

  async function hydrateIdentities() {
    const cards = Array.from(document.querySelectorAll('#projects-list>.project-card')).slice(0, MAX_VISIBLE_IDENTITIES);
    const ids = cards.map(projectId).filter(Boolean);
    if (!ids.length) return;
    const sequence = ++hydrationSequence;
    try {
      const identities = await apiRequest(`/ui/project-identities?ids=${encodeURIComponent(ids.join(','))}`);
      if (sequence !== hydrationSequence || !Array.isArray(identities)) return;
      const byId = new Map(identities.map(identity => [String(identity.project_id), identity]));
      cards.forEach(card => {
        const id = projectId(card);
        const identity = byId.get(id);
        if (!identity) return;
        cacheIdentity(id, identity);
        renderIdentity(card, identity);
        const ship = card.querySelector(':scope>.project-ship-hangar');
        if (ship) {
          ship.remove();
          ensureShip(card);
        }
      });
    } catch (_) {
      // Cached identity keeps the project list functional if optional hydration fails.
    }
  }

  function preview(dialog, logo, name) {
    const target = dialog.querySelector('.project-logo-preview');
    target.innerHTML = logo ? `<img src="${escapeHtml(logo)}" alt="Prévia do logo">` : `<span>${escapeHtml(initials(name))}</span>`;
  }

  function setDialogBusy(dialog, busy) {
    dialog.dataset.saving = busy ? '1' : '0';
    dialog.querySelectorAll('button,input').forEach(control => { control.disabled = busy; });
  }

  function ensureDialog() {
    let dialog = document.getElementById(DIALOG_ID);
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = DIALOG_ID;
    dialog.innerHTML = `
      <div class="project-logo-modal">
        <div class="project-logo-head"><div><span class="eyebrow">IDENTIDADE DO PROJETO</span><h2>Logo do projeto</h2></div><button type="button" class="project-logo-close" aria-label="Fechar">×</button></div>
        <div class="project-logo-grid">
          <div class="project-logo-preview"></div>
          <div class="project-logo-fields">
            <label>Enviar imagem<input id="project-logo-file" type="file" accept="image/png,image/jpeg,image/webp"></label>
            <label>Ou usar URL HTTPS<input id="project-logo-url" type="url" inputmode="url" placeholder="https://.../logo.png"></label>
            <label class="project-logo-color"><span>Cor de destaque</span><input id="project-logo-accent" type="color" value="#2dd4a8"></label>
          </div>
        </div>
        <p class="project-logo-hint">PNG, JPG ou WebP até 3 MB. O upload é reduzido antes de salvar. No estilo Profissional aparece como logo; no estilo Jogo o projeto é representado por uma nave.</p>
        <div class="project-logo-actions"><button type="button" class="remove">Remover logo</button><button type="button" class="cancel">Cancelar</button><button type="button" class="save">Salvar identidade</button></div>
      </div>`;
    document.body.appendChild(dialog);
    dialog.querySelector('.project-logo-close').addEventListener('click', () => { if (dialog.dataset.saving !== '1') dialog.close(); });
    dialog.querySelector('.cancel').addEventListener('click', () => { if (dialog.dataset.saving !== '1') dialog.close(); });
    dialog.addEventListener('cancel', event => { if (dialog.dataset.saving === '1') event.preventDefault(); });
    dialog.addEventListener('close', () => {
      if (dialog.dataset.saving === '1') return;
      editor = null;
      uploadedLogo = '';
      dialog.querySelector('#project-logo-file').value = '';
    });
    dialog.querySelector('#project-logo-file').addEventListener('change', async event => {
      const file = event.target.files?.[0];
      if (!file || !editor) return;
      try {
        uploadedLogo = await compressLogo(file);
        dialog.querySelector('#project-logo-url').value = '';
        preview(dialog, uploadedLogo, editor.name);
      } catch (error) {
        uploadedLogo = '';
        event.target.value = '';
        notify(error.message || 'Imagem inválida.');
      }
    });
    dialog.querySelector('#project-logo-url').addEventListener('input', event => {
      if (!editor) return;
      uploadedLogo = '';
      preview(dialog, String(event.target.value || '').trim(), editor.name);
    });
    dialog.querySelector('.save').addEventListener('click', () => void saveIdentity(false));
    dialog.querySelector('.remove').addEventListener('click', () => void saveIdentity(true));
    return dialog;
  }

  async function compressLogo(file) {
    if (!/^image\/(png|jpeg|webp)$/.test(file.type)) throw new Error('Use uma imagem PNG, JPG ou WebP.');
    if (file.size > MAX_FILE_BYTES) throw new Error('A imagem deve ter no máximo 3 MB.');
    const source = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error('Não foi possível ler a imagem.'));
      reader.readAsDataURL(file);
    });
    const image = await new Promise((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new Error('Não foi possível abrir a imagem.'));
      element.src = source;
    });
    const side = 192;
    const canvas = document.createElement('canvas');
    canvas.width = side;
    canvas.height = side;
    const context = canvas.getContext('2d', {alpha: true});
    if (!context) throw new Error('O navegador não conseguiu processar a imagem.');
    const scale = Math.min(side / image.width, side / image.height);
    const width = Math.max(1, Math.round(image.width * scale));
    const height = Math.max(1, Math.round(image.height * scale));
    context.drawImage(image, Math.round((side - width) / 2), Math.round((side - height) / 2), width, height);
    let output = canvas.toDataURL('image/webp', .82);
    if (!output.startsWith('data:image/webp')) output = canvas.toDataURL('image/jpeg', .82);
    if (output.length > MAX_LOGO_LENGTH) throw new Error('A imagem ficou grande demais mesmo após otimização.');
    return output;
  }

  async function openEditor(card) {
    if (!canManage()) return;
    const id = projectId(card);
    if (!id) return;
    const dialog = ensureDialog();
    const name = projectName(card);
    const identity = cachedIdentity(id);
    editor = {card, id, name};
    uploadedLogo = '';
    dialog.querySelector('.project-logo-head h2').textContent = `Logo · ${name}`;
    dialog.querySelector('#project-logo-url').value = identity.logo.startsWith('https://') ? identity.logo : '';
    dialog.querySelector('#project-logo-accent').value = identity.accent;
    preview(dialog, identity.logo, name);
    dialog.showModal();
  }

  async function saveIdentity(removeLogo) {
    if (!editor) return;
    const operation = {id: editor.id, card: editor.card, name: editor.name};
    const dialog = ensureDialog();
    const url = String(dialog.querySelector('#project-logo-url').value || '').trim();
    const existing = cachedIdentity(operation.id);
    const logo = removeLogo ? '' : (uploadedLogo || url || existing.logo || '');
    if (logo && !logo.startsWith('data:image/') && !logo.startsWith('https://')) {
      notify('Use upload de imagem ou uma URL HTTPS.');
      return;
    }
    if (logo.length > MAX_LOGO_LENGTH) {
      notify('Logo acima do limite permitido.');
      return;
    }
    const accent = String(dialog.querySelector('#project-logo-accent').value || '#2dd4a8');
    setDialogBusy(dialog, true);
    try {
      const identity = await apiRequest(`/ui/projects/${encodeURIComponent(operation.id)}/visual-identity`, {
        method: 'PATCH',
        body: JSON.stringify({logo, accent}),
      });
      cacheIdentity(operation.id, identity);
      if (operation.card?.isConnected) {
        renderIdentity(operation.card, identity);
        const ship = operation.card.querySelector(':scope>.project-ship-hangar');
        ship?.remove();
        ensureShip(operation.card);
      }
      if (editor?.id === operation.id) {
        setDialogBusy(dialog, false);
        dialog.close();
      }
      notify(removeLogo ? 'Logo removido do projeto.' : 'Identidade visual salva.');
    } catch (error) {
      if (editor?.id === operation.id) setDialogBusy(dialog, false);
      notify(error.message || 'Não foi possível salvar a identidade visual.');
    }
  }

  function start() {
    ensureStyles();
    ensureDialog();
    ensureModeSwitch();
    setMode(localStorage.getItem(MODE_KEY) || 'professional');
    wrapProjectRenderer();
    enhanceProjects();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();