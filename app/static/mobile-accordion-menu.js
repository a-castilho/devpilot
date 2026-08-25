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