(() => {
  function ensureResponseManager() {
    if (window.DevPilotResponses || document.querySelector('script[data-response-manager="1"]')) return;
    const responses = document.createElement('script');
    responses.src = '/assets/response-manager.js?v=20260825-1';
    responses.defer = true;
    responses.dataset.responseManager = '1';
    document.head.appendChild(responses);
  }

  function ensureGameEntry() {
    if (window.__devpilotGameEntryReady || document.querySelector('script[data-game-entry="1"]')) return;
    const script = document.createElement('script');
    script.src = '/assets/game-entry.js?v=20260825-1';
    script.defer = true;
    script.dataset.gameEntry = '1';
    document.head.appendChild(script);
  }

  function ensureMobileRouteOverrides() {
    if (document.querySelector('style[data-mobile-simple-route-overrides="1"]')) return;
    const style = document.createElement('style');
    style.dataset.mobileSimpleRouteOverrides = '1';
    style.textContent = `
      @media (max-width: 900px) {
        body.mobile-route .sidebar {
          display: flex !important;
          grid-template-columns: none !important;
          align-items: stretch !important;
          height: calc(68px + env(safe-area-inset-bottom)) !important;
          padding: 6px max(6px, env(safe-area-inset-right)) calc(6px + env(safe-area-inset-bottom)) max(6px, env(safe-area-inset-left)) !important;
        }
        body.mobile-route .sidebar > nav,
        body.mobile-route .sidebar > .mobile-nav-arrow,
        body.mobile-route .sidebar > :not(.mobile-simple-nav) {
          display: none !important;
        }
        body.mobile-route .sidebar > .mobile-simple-nav {
          display: grid !important;
          grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
          gap: 4px !important;
          width: 100% !important;
          height: 52px !important;
          margin: 0 !important;
        }
        body.mobile-route .mobile-simple-item {
          width: 100% !important;
          min-width: 0 !important;
          max-width: none !important;
          height: 52px !important;
          min-height: 52px !important;
          padding: 3px 2px !important;
          border-radius: 11px !important;
          font-size: inherit !important;
        }
        body.mobile-route .mobile-simple-item > span {
          display: block !important;
          font-size: 19px !important;
          line-height: 1 !important;
        }
        body.mobile-route .mobile-simple-item > small {
          display: block !important;
          font-size: 9px !important;
          line-height: 1.1 !important;
        }
        body.mobile-route .mobile-simple-item[data-simple-menu-open] {
          flex: initial !important;
          width: 100% !important;
          min-width: 0 !important;
          max-width: none !important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  let waitObserver = null;

  function mountMobileMenu() {
    ensureResponseManager();
    ensureGameEntry();
    ensureMobileRouteOverrides();
    if (window.innerWidth > 900) return false;
    if (document.querySelector('.mobile-simple-nav')) return true;

    const sidebar = document.querySelector('.sidebar');
    const sourceNav = sidebar?.querySelector(':scope > nav');
    if (!sidebar || !sourceNav) return false;

    const icons = {
      overview: '⌂', projects: '▦', tasks: '✓', providers: '✦', organizations: '◎',
      reports: '≣', audit: '⌁', linux: '>_', 'token-usage': '◫', 'cloud-admin': '☁', 'investia-admin': '◇',
    };

    const root = document.createElement('div');
    root.className = 'mobile-simple-nav';
    root.innerHTML = `
      <button type="button" class="mobile-simple-item" data-simple-target="overview"><span>⌂</span><small>Início</small></button>
      <button type="button" class="mobile-simple-item" data-simple-target="projects"><span>▦</span><small>Projetos</small></button>
      <button type="button" class="mobile-simple-item" data-simple-target="tasks"><span>✓</span><small>Tarefas</small></button>
      <button type="button" class="mobile-simple-item" data-simple-menu-open aria-label="Abrir menu"><span>☰</span><small>Menu</small></button>
    `;

    const backdrop = document.createElement('div');
    backdrop.className = 'mobile-simple-backdrop';
    backdrop.hidden = true;

    const sheet = document.createElement('section');
    sheet.className = 'mobile-simple-sheet';
    sheet.hidden = true;
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-modal', 'true');
    sheet.setAttribute('aria-label', 'Menu do DevPilot');
    sheet.innerHTML = `
      <div class="mobile-simple-sheet-head">
        <div><span class="eyebrow">NAVEGAÇÃO</span><h2>Menu</h2></div>
        <button type="button" class="mobile-simple-close" aria-label="Fechar menu">×</button>
      </div>
      <div class="mobile-simple-list"></div>
    `;

    document.body.append(backdrop, sheet);
    sidebar.appendChild(root);

    const list = sheet.querySelector('.mobile-simple-list');
    const openButton = root.querySelector('[data-simple-menu-open]');

    function items() {
      return [...sourceNav.querySelectorAll(':scope > .nav')].filter(item => !item.hidden && !item.classList.contains('nav-super-admin-forbidden'));
    }

    function label(item) {
      return String(item.textContent || item.getAttribute('aria-label') || 'Abrir').replace(/\s+/g, ' ').trim();
    }

    function icon(item) {
      if (item.dataset.exampleProject) return '◫';
      if (item.dataset.linuxView === '1') return icons.linux;
      return icons[item.dataset.view] || '•';
    }

    function close() {
      sheet.hidden = true;
      backdrop.hidden = true;
      document.body.classList.remove('mobile-simple-open');
      openButton.setAttribute('aria-expanded', 'false');
    }

    function navigate(item) {
      if (!item) return;
      close();
      item.click();
      requestAnimationFrame(sync);
    }

    function renderMenu() {
      list.replaceChildren();
      items().forEach(item => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `mobile-simple-row${item.classList.contains('active') ? ' active' : ''}`;
        button.innerHTML = `<span class="mobile-simple-icon">${icon(item)}</span><span>${label(item)}</span><span class="mobile-simple-arrow">›</span>`;
        button.addEventListener('click', () => navigate(item));
        list.appendChild(button);
      });
    }

    function open() {
      renderMenu();
      sheet.hidden = false;
      backdrop.hidden = false;
      document.body.classList.add('mobile-simple-open');
      openButton.setAttribute('aria-expanded', 'true');
    }

    function sync() {
      root.querySelectorAll('[data-simple-target]').forEach(button => {
        const source = sourceNav.querySelector(`.nav[data-view="${CSS.escape(button.dataset.simpleTarget)}"]`);
        button.classList.toggle('active', Boolean(source?.classList.contains('active')));
      });
      if (!sheet.hidden) renderMenu();
    }

    root.querySelectorAll('[data-simple-target]').forEach(button => {
      button.addEventListener('click', () => navigate(sourceNav.querySelector(`.nav[data-view="${CSS.escape(button.dataset.simpleTarget)}"]`)));
    });
    openButton.setAttribute('aria-expanded', 'false');
    openButton.addEventListener('click', open);
    sheet.querySelector('.mobile-simple-close').addEventListener('click', close);
    backdrop.addEventListener('click', close);
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && !sheet.hidden) close(); });
    new MutationObserver(sync).observe(sourceNav, {subtree:true, childList:true, attributes:true, attributeFilter:['class','hidden']});
    sync();

    waitObserver?.disconnect();
    waitObserver = null;
    return true;
  }

  function bootstrapMobileMenu() {
    if (mountMobileMenu()) return;
    if (waitObserver) return;
    waitObserver = new MutationObserver(() => {
      if (mountMobileMenu()) {
        waitObserver?.disconnect();
        waitObserver = null;
      }
    });
    waitObserver.observe(document.documentElement, {childList: true, subtree: true});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapMobileMenu, {once: true});
  } else {
    bootstrapMobileMenu();
  }

  window.addEventListener('resize', () => {
    if (window.innerWidth <= 900 && !document.querySelector('.mobile-simple-nav')) bootstrapMobileMenu();
  });
})();

/* Mobile Chat DevPilot: mantém o <select> como fonte de estado, mas evita o picker
 * nativo de tela inteira do Android. Os projetos são carregados somente ao abrir
 * o controle, preservando o boot leve da visão geral. */
(() => {
  const STYLE_ID = 'devpilot-mobile-chat-project-picker-style';
  let projectLoading = null;

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      @media (max-width: 900px) {
        #voice-modal .voice-project-control > #voice-project {
          position: absolute !important;
          width: 1px !important;
          height: 1px !important;
          opacity: 0 !important;
          pointer-events: none !important;
          overflow: hidden !important;
        }
        #voice-modal .mobile-chat-project-picker { position: relative; width: 100%; }
        #voice-modal .mobile-chat-project-trigger {
          width: 100%; min-height: 48px; display: flex; align-items: center;
          justify-content: space-between; gap: 12px; padding: 11px 14px;
          border: 1px solid rgba(148,163,184,.22); border-radius: 13px;
          background: rgba(15,23,42,.72); color: #e6eef2; text-align: left;
          font: inherit; touch-action: manipulation;
        }
        #voice-modal .mobile-chat-project-trigger::after { content: '⌄'; color: #91a0aa; }
        #voice-modal .mobile-chat-project-trigger[aria-expanded="true"]::after { content: '⌃'; }
        #voice-modal .mobile-chat-project-list {
          position: absolute; z-index: 40; top: calc(100% + 6px); left: 0; right: 0;
          max-height: min(42vh, 320px); overflow: auto; overscroll-behavior: contain;
          padding: 6px; border: 1px solid rgba(148,163,184,.24); border-radius: 14px;
          background: #0b141c; box-shadow: 0 18px 42px rgba(0,0,0,.46);
        }
        #voice-modal .mobile-chat-project-list[hidden] { display: none !important; }
        #voice-modal .mobile-chat-project-option {
          width: 100%; min-height: 46px; display: flex; align-items: center;
          padding: 10px 12px; border: 0; border-radius: 10px; background: transparent;
          color: #dce8ed; text-align: left; font: inherit;
        }
        #voice-modal .mobile-chat-project-option[aria-selected="true"] {
          background: rgba(45,212,191,.13); color: #effffd;
        }
        #voice-modal .mobile-chat-project-option:active { background: rgba(148,163,184,.13); }
        #voice-modal .mobile-chat-project-empty { padding: 12px; color: #91a0aa; font-size: .86rem; }
      }
    `;
    document.head.appendChild(style);
  }

  function optionText(option) {
    return String(option?.textContent || '').trim() || 'Geral — sem projeto';
  }

  async function ensureProjects(select) {
    const realProjects = [...select.options].filter(option => String(option.value || '').trim());
    if (realProjects.length) return;
    if (projectLoading) return projectLoading;
    projectLoading = (async () => {
      try {
        if (typeof loadProjects === 'function') await loadProjects();
      } finally {
        projectLoading = null;
      }
    })();
    return projectLoading;
  }

  function mountPicker() {
    if (window.innerWidth > 900) return false;
    const select = document.querySelector('#voice-modal #voice-project');
    const control = select?.closest('.voice-project-control');
    if (!select || !control) return false;
    if (control.querySelector('.mobile-chat-project-picker')) return true;

    ensureStyle();
    select.setAttribute('aria-hidden', 'true');
    select.tabIndex = -1;

    const picker = document.createElement('div');
    picker.className = 'mobile-chat-project-picker';
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'mobile-chat-project-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-label', 'Selecionar projeto do Chat DevPilot');

    const list = document.createElement('div');
    list.className = 'mobile-chat-project-list';
    list.setAttribute('role', 'listbox');
    list.setAttribute('aria-label', 'Projetos disponíveis');
    list.hidden = true;
    picker.append(trigger, list);
    control.appendChild(picker);

    function selectedOption() {
      return [...select.options].find(option => option.selected) || select.options[0] || null;
    }

    function syncTrigger() {
      trigger.textContent = optionText(selectedOption());
    }

    function close() {
      list.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
    }

    function renderList() {
      const options = [...select.options];
      list.replaceChildren();
      if (!options.length) {
        const empty = document.createElement('div');
        empty.className = 'mobile-chat-project-empty';
        empty.textContent = 'Nenhum projeto disponível.';
        list.appendChild(empty);
        return;
      }
      options.forEach(option => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'mobile-chat-project-option';
        button.setAttribute('role', 'option');
        button.setAttribute('aria-selected', String(option.selected));
        button.dataset.value = option.value;
        button.textContent = optionText(option);
        button.addEventListener('click', () => {
          select.value = option.value;
          select.dispatchEvent(new Event('change', {bubbles: true}));
          syncTrigger();
          close();
          trigger.focus({preventScroll: true});
        });
        list.appendChild(button);
      });
    }

    trigger.addEventListener('click', async event => {
      event.preventDefault();
      event.stopPropagation();
      const opening = list.hidden;
      if (!opening) return close();
      trigger.disabled = true;
      trigger.textContent = 'Carregando projetos…';
      await ensureProjects(select);
      trigger.disabled = false;
      syncTrigger();
      renderList();
      list.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
    });
    picker.addEventListener('click', event => event.stopPropagation());
    document.addEventListener('click', close);
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !list.hidden) {
        close();
        trigger.focus({preventScroll: true});
      }
    });
    select.addEventListener('change', () => {
      syncTrigger();
      if (!list.hidden) renderList();
    });
    new MutationObserver(() => {
      syncTrigger();
      if (!list.hidden) renderList();
    }).observe(select, {childList: true, subtree: true, attributes: true, attributeFilter: ['selected']});
    syncTrigger();
    return true;
  }

  function bootstrapPicker() {
    if (mountPicker()) return;
    const observer = new MutationObserver(() => {
      if (mountPicker()) observer.disconnect();
    });
    observer.observe(document.documentElement, {childList: true, subtree: true});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapPicker, {once: true});
  } else {
    bootstrapPicker();
  }
})();