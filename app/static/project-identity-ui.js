(() => {
  'use strict';

  const ROOT_SELECTOR = '#projects-list';
  const STYLE_ID = 'devpilot-project-identity-style';
  const MODE_KEY = 'devpilot-project-card-skin-v1';
  const LOGO_CACHE_KEY = 'devpilot-project-logo-cache-v1';
  const DIALOG_ID = 'devpilot-project-logo-dialog';
  const MAX_FILE_BYTES = 3 * 1024 * 1024;
  const MAX_LOGO_LENGTH = 160000;
  const MANAGEMENT_ROLES = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);

  let scheduled = false;
  let fullProjectsPromise = null;
  let activeEditor = null;
  let pendingFileLogo = '';

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  }[char]));

  function safeJson(value, fallback = {}) {
    try {
      const parsed = typeof value === 'string' ? JSON.parse(value || '{}') : value;
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : fallback;
    } catch (_) {
      return fallback;
    }
  }

  function currentRole() {
    try {
      return String(state?.currentUser?.role || '').toUpperCase();
    } catch (_) {
      return '';
    }
  }

  function canManageIdentity() {
    return MANAGEMENT_ROLES.has(currentRole());
  }

  function notify(message) {
    try {
      if (typeof toast === 'function') return toast(message);
    } catch (_) {
      // Fallback below.
    }
    console.info(`[DevPilot] ${message}`);
  }

  async function request(path, options = {}) {
    const token = String(localStorage.getItem('devpilot-token') || '').trim();
    const headers = {Authorization: `Bearer ${token}`, ...(options.headers || {})};
    if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
    const response = await fetch(`/api${path}`, {...options, headers, cache: 'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data?.detail === 'string' ? data.detail : 'Falha na operação';
      throw new Error(detail);
    }
    return data;
  }

  function logoCache() {
    return safeJson(localStorage.getItem(LOGO_CACHE_KEY), {});
  }

  function cachedIdentity(projectId) {
    return safeJson(logoCache()[projectId], {});
  }

  function cacheIdentity(projectId, identity) {
    const cache = logoCache();
    cache[projectId] = {
      logo: String(identity?.logo || ''),
      accent: /^#[0-9a-f]{6}$/i.test(String(identity?.accent || '')) ? identity.accent : '#2dd4a8',
      updated_at: String(identity?.updated_at || ''),
    };
    try {
      localStorage.setItem(LOGO_CACHE_KEY, JSON.stringify(cache));
    } catch (_) {
      // Storage can be unavailable in private/restricted contexts. The server save still succeeds.
    }
  }

  function projectConfig(project) {
    return safeJson(project?.codex_config, {});
  }

  function projectIdentity(project) {
    const config = projectConfig(project);
    const identity = safeJson(config.visual_identity, {});
    return {
      logo: String(identity.logo || ''),
      accent: /^#[0-9a-f]{6}$/i.test(String(identity.accent || '')) ? identity.accent : '#2dd4a8',
      updated_at: String(identity.updated_at || ''),
    };
  }

  async function fullProjects() {
    if (!fullProjectsPromise) {
      fullProjectsPromise = request('/projects').then(items => Array.isArray(items) ? items : []).catch(error => {
        fullProjectsPromise = null;
        throw error;
      });
    }
    return fullProjectsPromise;
  }

  function projectIdForCard(card) {
    return card.dataset.projectId
      || card.querySelector('.analyze[data-id]')?.dataset.id
      || card.querySelector('[data-project-task]')?.dataset.projectTask
      || '';
  }

  function initials(name) {
    const words = String(name || 'Projeto').trim().split(/\s+/).filter(Boolean);
    return (words.slice(0, 2).map(word => word[0]).join('') || 'P').toUpperCase();
  }

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #projects-view .section-head {
        align-items: center;
        gap: 14px;
        flex-wrap: wrap;
      }
      #projects-view .section-head > div:first-child { min-width: 0; flex: 1 1 320px; }
      #projects-view .section-head > [data-project-builder-open] { flex: 0 0 auto; }

      .project-card-skin-switch {
        display: inline-grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 4px;
        padding: 4px;
        border: 1px solid #253646;
        border-radius: 12px;
        background: #07111a;
        box-shadow: inset 0 1px 0 #ffffff08;
      }
      .project-card-skin-switch button {
        min-height: 34px;
        padding: 7px 12px;
        border: 0;
        border-radius: 9px;
        background: transparent;
        color: #8fa7b8;
        font: inherit;
        font-size: 11px;
        font-weight: 800;
        cursor: pointer;
        white-space: nowrap;
      }
      .project-card-skin-switch button[aria-pressed="true"] {
        background: #153040;
        color: #e9fbff;
        box-shadow: inset 0 0 0 1px #3b6075;
      }
      html[data-project-card-skin="game"] .project-card-skin-switch button[data-project-card-skin="game"][aria-pressed="true"] {
        background: linear-gradient(135deg, #123630, #102243);
        color: #70ffd0;
        box-shadow: inset 0 0 0 1px #35dba5, 0 0 18px #35dba51c;
      }

      #projects-view #projects-list.cards {
        display: grid !important;
        grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
        align-items: stretch !important;
        gap: 14px !important;
        min-width: 0;
      }
      #projects-view #projects-list > .project-card {
        min-width: 0 !important;
        min-height: 0 !important;
        max-height: none !important;
        height: auto !important;
        overflow: visible !important;
        padding: 15px !important;
      }
      #projects-list .project-card code {
        display: block;
        width: 100%;
        max-width: 100% !important;
        overflow: hidden !important;
        text-overflow: ellipsis;
        white-space: nowrap !important;
      }
      #projects-list .project-card .list-row {
        align-items: center;
        gap: 8px;
        min-width: 0;
        margin-top: 8px;
      }
      #projects-list .project-card .list-row > small {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      #projects-list .project-identity-head {
        display: grid;
        grid-template-columns: 58px minmax(0, 1fr);
        align-items: center;
        gap: 11px;
        min-width: 0;
        margin-bottom: 9px;
      }
      #projects-list .project-identity-copy { min-width: 0; }
      #projects-list .project-identity-copy .eyebrow {
        margin: 0 0 4px !important;
        max-width: 100%;
      }
      #projects-list .project-identity-copy h3 {
        margin: 0 !important;
        min-width: 0;
        overflow: hidden;
        color: #edf7fb;
        font-size: 18px;
        line-height: 1.2;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      #projects-list .project-logo-control,
      #projects-list .project-logo-static {
        position: relative;
        display: grid;
        width: 58px;
        height: 58px;
        place-items: center;
        overflow: hidden;
        border: 1px solid color-mix(in srgb, var(--project-accent, #2dd4a8) 58%, #334554);
        border-radius: 15px;
        background: linear-gradient(145deg, #102333, #07121b);
        box-shadow: inset 0 1px 0 #ffffff10, 0 8px 22px #0005;
        color: #e6fbf5;
      }
      #projects-list button.project-logo-control {
        padding: 0;
        cursor: pointer;
      }
      #projects-list .project-logo-control:hover {
        border-color: var(--project-accent, #2dd4a8);
        transform: translateY(-1px);
      }
      #projects-list .project-logo-control img,
      #projects-list .project-logo-static img {
        width: 100%;
        height: 100%;
        object-fit: contain;
        background: #061018;
      }
      #projects-list .project-logo-initials {
        font-size: 17px;
        font-weight: 900;
        letter-spacing: .04em;
      }
      #projects-list .project-logo-edit-badge {
        position: absolute;
        right: 3px;
        bottom: 3px;
        display: grid;
        width: 18px;
        height: 18px;
        place-items: center;
        border: 1px solid #ffffff24;
        border-radius: 7px;
        background: #07131eea;
        color: var(--project-accent, #2dd4a8);
        font-size: 10px;
        line-height: 1;
      }

      #projects-list .project-card-actions {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 7px;
        margin-top: 12px;
      }
      #projects-list .project-card-actions button {
        display: inline-flex !important;
        min-width: 0 !important;
        min-height: 36px !important;
        width: 100%;
        align-items: center;
        justify-content: center;
        gap: 6px;
        margin: 0 !important;
        padding: 7px 9px !important;
        overflow: hidden;
        border-radius: 9px !important;
        font-size: 11px !important;
        font-weight: 800 !important;
        line-height: 1.15 !important;
        text-overflow: ellipsis;
        white-space: nowrap !important;
        word-break: normal !important;
      }
      #projects-list .project-card-actions button::before {
        flex: 0 0 auto;
        font-size: 12px !important;
      }
      html[data-project-card-skin="professional"] #projects-list .project-card-actions .analyze {
        border-color: #286752 !important;
        background: #0b2a21 !important;
        color: #81f2c3 !important;
      }
      html[data-project-card-skin="professional"] #projects-list .project-card-actions [data-project-task] {
        border-color: #235a7c !important;
        background: #0b2030 !important;
        color: #9cd8ff !important;
      }
      html[data-project-card-skin="professional"] #projects-list .project-card-actions .delete-project,
      html[data-project-card-skin="professional"] #projects-list .project-card-actions [class*="delete"] {
        border-color: #6e2830 !important;
        background: #2a1015 !important;
        color: #ff8791 !important;
      }

      html[data-project-card-skin="professional"] #projects-list .project-ship-hangar,
      html[data-project-card-skin="professional"] #projects-view .project-visual-overview {
        display: none !important;
      }
      html[data-project-card-skin="professional"] #projects-list .project-card.project-ship-card {
        border-color: #233844 !important;
        background: linear-gradient(155deg, #0e1821, #09121a 72%) !important;
        box-shadow: 0 12px 30px #0004, inset 0 1px 0 #ffffff08 !important;
      }
      html[data-project-card-skin="professional"] #projects-list .project-card.project-ship-card:hover {
        transform: translateY(-2px);
        border-color: color-mix(in srgb, var(--project-accent, #2dd4a8) 48%, #314451) !important;
        box-shadow: 0 18px 38px #0006, 0 0 22px color-mix(in srgb, var(--project-accent, #2dd4a8) 8%, transparent) !important;
      }
      html[data-project-card-skin="professional"] #projects-list .project-ship-card > h3,
      html[data-project-card-skin="professional"] #projects-list .project-ship-card > .eyebrow:first-child {
        display: none !important;
      }

      html[data-project-card-skin="game"] #projects-view #projects-list.cards {
        grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
        gap: 12px !important;
      }
      html[data-project-card-skin="game"] #projects-list .project-logo-control,
      html[data-project-card-skin="game"] #projects-list .project-logo-static { display: none !important; }
      html[data-project-card-skin="game"] #projects-list .project-identity-head {
        grid-template-columns: minmax(0, 1fr);
        margin-bottom: 4px;
      }
      html[data-project-card-skin="game"] #projects-list .project-identity-copy h3 {
        color: #ddfff3;
        font-size: 16px;
        letter-spacing: .01em;
      }
      html[data-project-card-skin="game"] #projects-list .project-card-actions {
        grid-template-columns: repeat(auto-fit, minmax(38px, 1fr));
        gap: 5px;
        margin-top: 7px;
      }
      html[data-project-card-skin="game"] #projects-list .project-card-actions button.project-ship-action {
        min-height: 34px !important;
        padding: 5px !important;
        font-size: 0 !important;
      }
      html[data-project-card-skin="game"] #projects-list .project-card-actions button.project-ship-action::before {
        margin: 0 !important;
        font-size: 14px !important;
      }
      html[data-project-card-skin="game"] #projects-list .project-card code { font-size: 8px !important; }
      html[data-project-card-skin="game"] #projects-list .project-card .list-row { margin-top: 4px; }

      #${DIALOG_ID} {
        width: min(520px, calc(100vw - 28px));
        max-height: min(720px, calc(100dvh - 28px));
        padding: 0;
        overflow: auto;
        border: 1px solid #304556;
        border-radius: 18px;
        background: #0a141d;
        color: #e7f1f6;
        box-shadow: 0 30px 90px #000b;
      }
      #${DIALOG_ID}::backdrop { background: #000b; backdrop-filter: blur(3px); }
      #${DIALOG_ID} .project-logo-modal { padding: 20px; }
      #${DIALOG_ID} .project-logo-modal-head {
        display: flex;
        align-items: start;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 16px;
      }
      #${DIALOG_ID} .project-logo-modal-head h2 { margin: 3px 0 0; font-size: 21px; }
      #${DIALOG_ID} .project-logo-close {
        width: 34px;
        height: 34px;
        border: 1px solid #304556;
        border-radius: 10px;
        background: #101e29;
        color: #cfe0e9;
        cursor: pointer;
      }
      #${DIALOG_ID} .project-logo-editor-grid {
        display: grid;
        grid-template-columns: 118px minmax(0, 1fr);
        gap: 16px;
        align-items: start;
      }
      #${DIALOG_ID} .project-logo-preview {
        display: grid;
        width: 118px;
        height: 118px;
        place-items: center;
        overflow: hidden;
        border: 1px solid #365265;
        border-radius: 22px;
        background: #07111a;
        color: #e5fff6;
        font-size: 30px;
        font-weight: 900;
      }
      #${DIALOG_ID} .project-logo-preview img { width: 100%; height: 100%; object-fit: contain; }
      #${DIALOG_ID} .project-logo-fields { display: grid; gap: 11px; min-width: 0; }
      #${DIALOG_ID} label { display: grid; gap: 6px; color: #9db2bf; font-size: 11px; font-weight: 800; }
      #${DIALOG_ID} input[type="file"],
      #${DIALOG_ID} input[type="url"] {
        width: 100%;
        min-width: 0;
        box-sizing: border-box;
        border: 1px solid #2b4354;
        border-radius: 10px;
        background: #07121b;
        color: #e7f1f6;
        padding: 10px;
      }
      #${DIALOG_ID} .project-logo-color-row {
        display: grid;
        grid-template-columns: 1fr 52px;
        align-items: center;
        gap: 10px;
      }
      #${DIALOG_ID} input[type="color"] {
        width: 52px;
        height: 38px;
        padding: 3px;
        border: 1px solid #2b4354;
        border-radius: 9px;
        background: #07121b;
      }
      #${DIALOG_ID} .project-logo-hint { margin: 12px 0 0; color: #738b99; font-size: 10px; line-height: 1.5; }
      #${DIALOG_ID} .project-logo-actions {
        display: grid;
        grid-template-columns: auto 1fr 1fr;
        gap: 8px;
        margin-top: 18px;
      }
      #${DIALOG_ID} .project-logo-actions button {
        min-height: 38px;
        padding: 8px 12px;
        border-radius: 10px;
        font-weight: 800;
        cursor: pointer;
      }
      #${DIALOG_ID} .project-logo-remove { border: 1px solid #603039; background: #251116; color: #ff8b94; }
      #${DIALOG_ID} .project-logo-cancel { border: 1px solid #304556; background: #101e29; color: #cfe0e9; }
      #${DIALOG_ID} .project-logo-save { border: 1px solid #258f6c; background: #0e644c; color: #edfff8; }
      #${DIALOG_ID} button:disabled { opacity: .55; cursor: wait; }

      @media (min-width: 1500px) {
        #projects-view #projects-list.cards,
        html[data-project-card-skin="game"] #projects-view #projects-list.cards {
          grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
        }
      }
      @media (max-width: 1180px) {
        #projects-view #projects-list.cards,
        html[data-project-card-skin="game"] #projects-view #projects-list.cards {
          grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        }
      }
      @media (max-width: 760px) {
        #projects-view .section-head { align-items: stretch; }
        #projects-view .section-head > div:first-child { flex-basis: 100%; }
        .project-card-skin-switch { order: 2; flex: 1 1 100%; width: 100%; box-sizing: border-box; }
        #projects-view .section-head > [data-project-builder-open] { order: 3; width: 100%; }
        #projects-view #projects-list.cards,
        html[data-project-card-skin="game"] #projects-view #projects-list.cards {
          grid-template-columns: minmax(0, 1fr) !important;
          gap: 11px !important;
        }
        #projects-view #projects-list > .project-card { padding: 13px !important; }
        #projects-list .project-card-actions { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        #${DIALOG_ID} .project-logo-editor-grid { grid-template-columns: 1fr; }
        #${DIALOG_ID} .project-logo-preview { width: 94px; height: 94px; border-radius: 18px; }
        #${DIALOG_ID} .project-logo-actions { grid-template-columns: 1fr 1fr; }
        #${DIALOG_ID} .project-logo-remove { grid-column: 1 / -1; order: 3; }
      }
      @media (max-width: 420px) {
        #projects-list .project-identity-head { grid-template-columns: 50px minmax(0, 1fr); gap: 9px; }
        #projects-list .project-logo-control,
        #projects-list .project-logo-static { width: 50px; height: 50px; border-radius: 13px; }
        #projects-list .project-identity-copy h3 { font-size: 16px; }
        #projects-list .project-card-actions button { min-height: 40px !important; font-size: 10px !important; }
      }
      @media (prefers-reduced-motion: reduce) {
        #projects-list .project-logo-control,
        #projects-list .project-card.project-ship-card { transition: none !important; }
      }
    `;
    document.head.appendChild(style);
  }

  function setMode(mode, announce = false) {
    const next = mode === 'game' ? 'game' : 'professional';
    document.documentElement.dataset.projectCardSkin = next;
    localStorage.setItem(MODE_KEY, next);
    document.querySelectorAll('[data-project-card-skin]').forEach(button => {
      if (!button.matches('.project-card-skin-switch button')) return;
      button.setAttribute('aria-pressed', String(button.dataset.projectCardSkin === next));
    });
    if (announce) notify(next === 'game' ? 'Visual de jogo ativado.' : 'Visual profissional ativado.');
  }

  function ensureModeSwitch() {
    const head = document.querySelector('#projects-view .section-head');
    if (!head || head.querySelector('.project-card-skin-switch')) return;
    const switcher = document.createElement('div');
    switcher.className = 'project-card-skin-switch';
    switcher.setAttribute('role', 'group');
    switcher.setAttribute('aria-label', 'Estilo dos projetos');
    switcher.innerHTML = `
      <button type="button" data-project-card-skin="professional">▦ Profissional</button>
      <button type="button" data-project-card-skin="game">✦ Jogo</button>
    `;
    const create = head.querySelector('[data-project-builder-open]');
    if (create) head.insertBefore(switcher, create);
    else head.appendChild(switcher);
    switcher.querySelectorAll('button').forEach(button => {
      button.addEventListener('click', () => setMode(button.dataset.projectCardSkin, true));
    });
    setMode(localStorage.getItem(MODE_KEY) || 'professional', false);
  }

  function identityMarkup(projectName, identity, editable) {
    const logo = String(identity?.logo || '');
    const preview = logo
      ? `<img src="${esc(logo)}" alt="Logo de ${esc(projectName)}">`
      : `<span class="project-logo-initials">${esc(initials(projectName))}</span>`;
    if (!editable) return `<div class="project-logo-static" aria-label="Identidade visual do projeto">${preview}</div>`;
    return `
      <button class="project-logo-control" type="button" aria-label="Editar logo de ${esc(projectName)}" title="Editar logo">
        ${preview}<span class="project-logo-edit-badge">✎</span>
      </button>
    `;
  }

  function renderIdentity(card, identity) {
    const projectId = projectIdForCard(card);
    const title = card.querySelector('.project-identity-copy h3')?.textContent?.trim()
      || card.querySelector('h3')?.textContent?.trim()
      || 'Projeto';
    card.style.setProperty('--project-accent', identity?.accent || '#2dd4a8');
    const current = card.querySelector('.project-logo-control, .project-logo-static');
    if (current) {
      const holder = document.createElement('div');
      holder.innerHTML = identityMarkup(title, identity, canManageIdentity());
      const next = holder.firstElementChild;
      current.replaceWith(next);
      if (next?.matches('.project-logo-control')) {
        next.addEventListener('click', event => {
          event.stopPropagation();
          void openLogoEditor(card, projectId, title);
        });
      }
    }
  }

  function ensureActions(card) {
    let actions = card.querySelector(':scope > .project-card-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'project-card-actions';
      card.appendChild(actions);
    }
    const buttons = Array.from(card.querySelectorAll('button')).filter(button => {
      if (button.closest(`#${DIALOG_ID}`)) return false;
      if (button.matches('.project-logo-control')) return false;
      if (button.closest('.project-card-actions') === actions) return false;
      return true;
    });
    buttons.forEach(button => actions.appendChild(button));
    actions.querySelectorAll('button').forEach(button => {
      const text = String(button.textContent || '').trim();
      button.title = button.title || text;
      if (text && !button.getAttribute('aria-label')) button.setAttribute('aria-label', text);
    });
  }

  function enhanceCard(card) {
    const projectId = projectIdForCard(card);
    if (projectId) card.dataset.projectId = projectId;

    if (card.dataset.projectIdentityEnhanced !== '1') {
      const title = card.querySelector('h3');
      if (!title) return;
      const projectName = title.textContent?.trim() || 'Projeto';
      const eyebrow = card.querySelector(':scope > .eyebrow');
      const head = document.createElement('div');
      head.className = 'project-identity-head';
      const copy = document.createElement('div');
      copy.className = 'project-identity-copy';
      if (eyebrow) copy.appendChild(eyebrow);
      copy.appendChild(title);
      const identity = projectId ? cachedIdentity(projectId) : {};
      const logoHolder = document.createElement('div');
      logoHolder.innerHTML = identityMarkup(projectName, identity, canManageIdentity());
      const logoNode = logoHolder.firstElementChild;
      head.append(logoNode, copy);
      card.insertBefore(head, card.firstChild);
      card.style.setProperty('--project-accent', identity.accent || '#2dd4a8');
      if (logoNode?.matches('.project-logo-control')) {
        logoNode.addEventListener('click', event => {
          event.stopPropagation();
          void openLogoEditor(card, projectId, projectName);
        });
      }
      card.dataset.projectIdentityEnhanced = '1';
    }
    ensureActions(card);
  }

  function enhanceAll() {
    scheduled = false;
    ensureModeSwitch();
    document.querySelectorAll(`${ROOT_SELECTOR} > .project-card`).forEach(enhanceCard);
  }

  function scheduleEnhance() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(enhanceAll);
  }

  function previewLogo(dialog, logo, name) {
    const preview = dialog.querySelector('.project-logo-preview');
    if (!preview) return;
    preview.innerHTML = logo
      ? `<img src="${esc(logo)}" alt="Prévia do logo">`
      : `<span>${esc(initials(name))}</span>`;
  }

  function ensureDialog() {
    let dialog = document.getElementById(DIALOG_ID);
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = DIALOG_ID;
    dialog.innerHTML = `
      <div class="project-logo-modal">
        <div class="project-logo-modal-head">
          <div><span class="eyebrow">IDENTIDADE DO PROJETO</span><h2 id="project-logo-title">Logo do projeto</h2></div>
          <button class="project-logo-close" type="button" aria-label="Fechar">×</button>
        </div>
        <div class="project-logo-editor-grid">
          <div class="project-logo-preview" aria-live="polite"></div>
          <div class="project-logo-fields">
            <label>Enviar imagem
              <input id="project-logo-file" type="file" accept="image/png,image/jpeg,image/webp">
            </label>
            <label>Ou usar URL HTTPS
              <input id="project-logo-url" type="url" inputmode="url" placeholder="https://.../logo.png">
            </label>
            <label class="project-logo-color-row"><span>Cor de destaque</span><input id="project-logo-accent" type="color" value="#2dd4a8"></label>
          </div>
        </div>
        <p class="project-logo-hint">A imagem enviada é reduzida no navegador antes de ser salva no projeto. No estilo Profissional ela aparece como logo; no estilo Jogo o projeto vira uma nave.</p>
        <div class="project-logo-actions">
          <button class="project-logo-remove" type="button">Remover logo</button>
          <button class="project-logo-cancel" type="button">Cancelar</button>
          <button class="project-logo-save" type="button">Salvar identidade</button>
        </div>
      </div>
    `;
    document.body.appendChild(dialog);

    dialog.querySelector('.project-logo-close').addEventListener('click', () => dialog.close());
    dialog.querySelector('.project-logo-cancel').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => {
      pendingFileLogo = '';
      activeEditor = null;
      const file = dialog.querySelector('#project-logo-file');
      if (file) file.value = '';
    });
    dialog.querySelector('#project-logo-file').addEventListener('change', async event => {
      const file = event.target.files?.[0];
      if (!file || !activeEditor) return;
      try {
        pendingFileLogo = await compressLogo(file);
        dialog.querySelector('#project-logo-url').value = '';
        previewLogo(dialog, pendingFileLogo, activeEditor.name);
      } catch (error) {
        event.target.value = '';
        pendingFileLogo = '';
        notify(error.message || 'Imagem inválida.');
      }
    });
    dialog.querySelector('#project-logo-url').addEventListener('input', event => {
      if (!activeEditor) return;
      pendingFileLogo = '';
      const value = String(event.target.value || '').trim();
      previewLogo(dialog, value, activeEditor.name);
    });
    dialog.querySelector('.project-logo-save').addEventListener('click', () => void saveEditor(false));
    dialog.querySelector('.project-logo-remove').addEventListener('click', () => void saveEditor(true));
    return dialog;
  }

  async function compressLogo(file) {
    if (!file.type.match(/^image\/(png|jpeg|webp)$/)) throw new Error('Use uma imagem PNG, JPG ou WebP.');
    if (file.size > MAX_FILE_BYTES) throw new Error('A imagem deve ter no máximo 3 MB.');

    const source = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error('Não foi possível ler a imagem.'));
      reader.readAsDataURL(file);
    });
    const image = await new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('Não foi possível abrir a imagem.'));
      img.src = source;
    });

    const side = 192;
    const canvas = document.createElement('canvas');
    canvas.width = side;
    canvas.height = side;
    const context = canvas.getContext('2d', {alpha: true});
    if (!context) throw new Error('Seu navegador não conseguiu processar a imagem.');
    context.clearRect(0, 0, side, side);
    const scale = Math.min(side / image.width, side / image.height);
    const width = Math.max(1, Math.round(image.width * scale));
    const height = Math.max(1, Math.round(image.height * scale));
    context.drawImage(image, Math.round((side - width) / 2), Math.round((side - height) / 2), width, height);

    let result = canvas.toDataURL('image/webp', 0.82);
    if (!result.startsWith('data:image/webp')) result = canvas.toDataURL('image/jpeg', 0.82);
    if (result.length > MAX_LOGO_LENGTH) {
      const small = document.createElement('canvas');
      small.width = 128;
      small.height = 128;
      small.getContext('2d').drawImage(canvas, 0, 0, 128, 128);
      result = small.toDataURL('image/webp', 0.72);
    }
    if (result.length > MAX_LOGO_LENGTH) throw new Error('A imagem ainda ficou grande demais. Escolha outra imagem.');
    return result;
  }

  async function findFullProject(projectId) {
    const projects = await fullProjects();
    return projects.find(project => String(project.id) === String(projectId)) || null;
  }

  async function openLogoEditor(card, projectId, name) {
    if (!projectId || !canManageIdentity()) return;
    const dialog = ensureDialog();
    activeEditor = {card, projectId, name};
    pendingFileLogo = '';
    const cached = cachedIdentity(projectId);
    dialog.querySelector('#project-logo-title').textContent = `Logo · ${name}`;
    dialog.querySelector('#project-logo-url').value = cached.logo.startsWith('https://') ? cached.logo : '';
    dialog.querySelector('#project-logo-accent').value = cached.accent || '#2dd4a8';
    previewLogo(dialog, cached.logo, name);
    dialog.showModal();

    try {
      const project = await findFullProject(projectId);
      if (!project || !activeEditor || activeEditor.projectId !== projectId) return;
      const serverIdentity = projectIdentity(project);
      cacheIdentity(projectId, serverIdentity);
      renderIdentity(card, serverIdentity);
      dialog.querySelector('#project-logo-url').value = serverIdentity.logo.startsWith('https://') ? serverIdentity.logo : '';
      dialog.querySelector('#project-logo-accent').value = serverIdentity.accent || '#2dd4a8';
      previewLogo(dialog, serverIdentity.logo, name);
    } catch (_) {
      // The cached/fallback identity remains usable; save will surface an actionable error.
    }
  }

  async function saveEditor(removeLogo) {
    if (!activeEditor) return;
    const dialog = ensureDialog();
    const save = dialog.querySelector('.project-logo-save');
    const remove = dialog.querySelector('.project-logo-remove');
    save.disabled = true;
    remove.disabled = true;
    try {
      const project = await findFullProject(activeEditor.projectId);
      if (!project) throw new Error('Projeto não encontrado.');
      const config = projectConfig(project);
      const previous = safeJson(config.visual_identity, {});
      const url = String(dialog.querySelector('#project-logo-url').value || '').trim();
      let logo = removeLogo ? '' : (pendingFileLogo || url || previous.logo || '');
      if (logo && !logo.startsWith('data:image/') && !logo.startsWith('https://')) {
        throw new Error('Use upload de imagem ou uma URL HTTPS.');
      }
      if (logo.length > MAX_LOGO_LENGTH) throw new Error('Logo acima do limite permitido.');
      const accent = String(dialog.querySelector('#project-logo-accent').value || '#2dd4a8');
      const identity = {logo, accent, updated_at: new Date().toISOString()};
      const codexConfig = {...config, visual_identity: {...previous, ...identity}};

      await request(`/projects/${encodeURIComponent(activeEditor.projectId)}`, {
        method: 'PATCH',
        body: JSON.stringify({codex_config: codexConfig}),
      });
      cacheIdentity(activeEditor.projectId, identity);
      renderIdentity(activeEditor.card, identity);
      fullProjectsPromise = null;
      dialog.close();
      notify(removeLogo ? 'Logo removido do projeto.' : 'Identidade visual salva.');
    } catch (error) {
      notify(error.message || 'Não foi possível salvar a identidade visual.');
    } finally {
      save.disabled = false;
      remove.disabled = false;
    }
  }

  async function hydrateServerVisuals() {
    const cards = Array.from(document.querySelectorAll(`${ROOT_SELECTOR} > .project-card`));
    if (!cards.length || cards.length > 12) return;
    try {
      const projects = await fullProjects();
      const byId = new Map(projects.map(project => [String(project.id), project]));
      cards.forEach(card => {
        const projectId = projectIdForCard(card);
        const project = byId.get(String(projectId));
        if (!project) return;
        const identity = projectIdentity(project);
        cacheIdentity(projectId, identity);
        renderIdentity(card, identity);
      });
    } catch (_) {
      // Logos are an enhancement; project navigation must remain available if the heavy endpoint fails.
    }
  }

  function start() {
    ensureStyles();
    ensureDialog();
    ensureModeSwitch();
    setMode(localStorage.getItem(MODE_KEY) || 'professional', false);
    const root = document.querySelector(ROOT_SELECTOR);
    if (!root) return;
    enhanceAll();
    const observer = new MutationObserver(scheduleEnhance);
    observer.observe(root, {childList: true, subtree: true});
    window.setTimeout(() => void hydrateServerVisuals(), 850);
    document.addEventListener('devpilot:workspace-skin', scheduleEnhance);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();