(() => {
  'use strict';

  if (window.__devpilotMobileAccordionMenuStable) return;
  window.__devpilotMobileAccordionMenuStable = true;

  let mounted = false;
  let syncFrame = 0;
  let backFrame = 0;

  const MOBILE_MAX = 900;
  const BACK_CLASS = 'mobile-page-back';
  const BACK_STYLE_ID = 'devpilot-mobile-page-back-style';

  function ensureMobileRouteOverrides() {
    if (document.querySelector('style[data-mobile-simple-route-overrides="1"]')) return;
    const style = document.createElement('style');
    style.dataset.mobileSimpleRouteOverrides = '1';
    style.textContent = `
      @media (max-width: 900px) {
        body.mobile-route .sidebar {
          display:flex!important;
          grid-template-columns:none!important;
          align-items:stretch!important;
          height:calc(68px + env(safe-area-inset-bottom))!important;
          padding:6px max(6px,env(safe-area-inset-right)) calc(6px + env(safe-area-inset-bottom)) max(6px,env(safe-area-inset-left))!important;
        }
        body.mobile-route .sidebar > nav,
        body.mobile-route .sidebar > .mobile-nav-arrow,
        body.mobile-route .sidebar > :not(.mobile-simple-nav) {display:none!important}
        body.mobile-route .sidebar > .mobile-simple-nav {
          display:grid!important;
          grid-template-columns:repeat(5,minmax(0,1fr))!important;
          gap:4px!important;
          width:100%!important;
          height:52px!important;
          margin:0!important;
        }
        body.mobile-route .mobile-simple-item {
          width:100%!important;
          min-width:0!important;
          max-width:none!important;
          height:52px!important;
          min-height:52px!important;
          padding:3px 2px!important;
          border-radius:11px!important;
          font-size:inherit!important;
        }
        body.mobile-route .mobile-simple-item > span {display:block!important;font-size:19px!important;line-height:1!important}
        body.mobile-route .mobile-simple-item > small {display:block!important;font-size:9px!important;line-height:1.1!important}
        body.mobile-route .mobile-simple-item[data-simple-menu-open] {flex:initial!important;width:100%!important;min-width:0!important;max-width:none!important}
      }
    `;
    document.head.appendChild(style);
  }

  function ensureBackStyle() {
    if (document.getElementById(BACK_STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = BACK_STYLE_ID;
    style.textContent = `
      @media (max-width: ${MOBILE_MAX}px) {
        main > .view.active > .${BACK_CLASS} {
          position: sticky;
          top: max(8px, env(safe-area-inset-top));
          z-index: 80;
          display:flex;
          align-items:center;
          justify-content:flex-start;
          gap:12px;
          width:100%;
          min-height:56px;
          margin:0 0 16px;
          padding:0 18px;
          border:1px solid rgba(55,227,215,.72);
          border-radius:16px;
          background:linear-gradient(90deg, rgba(0,95,102,.98), rgba(7,45,66,.98));
          box-shadow:0 12px 30px rgba(0,0,0,.36), inset 0 1px 0 rgba(255,255,255,.08), 0 0 0 1px rgba(40,210,220,.08);
          color:#f3fbff;
          font:inherit;
          font-size:16px;
          font-weight:850;
          letter-spacing:.01em;
          backdrop-filter:blur(14px);
          -webkit-backdrop-filter:blur(14px);
          cursor:pointer;
          touch-action:manipulation;
        }
        main > .view.active > .${BACK_CLASS}::before {
          content:'←';
          display:grid;
          place-items:center;
          width:30px;
          height:30px;
          color:#49f2e3;
          font-size:28px;
          font-weight:500;
          line-height:1;
        }
        main > .view.active > .${BACK_CLASS}:active { transform:translateY(1px); }
        body.mobile-route #tasks-v9-back,
        body.mobile-route .project-builder-back { display:none!important; }
      }
      @media (min-width: ${MOBILE_MAX + 1}px) {
        .${BACK_CLASS} { display:none!important; }
      }
    `;
    document.head.appendChild(style);
  }

  function sourceElements() {
    const sidebar = document.querySelector('.sidebar');
    return {
      sidebar,
      sourceNav: sidebar?.querySelector(':scope > nav') || null,
      root: sidebar?.querySelector(':scope > .mobile-simple-nav') || null,
      sheet: document.querySelector('.mobile-simple-sheet'),
      backdrop: document.querySelector('.mobile-simple-backdrop'),
    };
  }

  const activeView = () => document.querySelector('main > .view.active');
  const sourceNav = () => document.querySelector('.sidebar > nav');

  function backDestination(view) {
    if (view?.id === 'new-project-view') return 'projects';
    return 'overview';
  }

  function backLabel(view) {
    if (view?.id === 'new-project-view') return 'Voltar para Projetos';
    return 'Voltar';
  }

  function navigateBack(target) {
    const button = sourceNav()?.querySelector(`.nav[data-view="${CSS.escape(target)}"]`);
    if (button) {
      button.click();
      return;
    }
    window.location.hash = target === 'overview' ? '#overview' : `#${target}`;
  }

  function mountBack({scrollToTop = false} = {}) {
    ensureBackStyle();
    if (window.innerWidth > MOBILE_MAX) return;

    const view = activeView();
    document.querySelectorAll(`.${BACK_CLASS}`).forEach(button => {
      if (!view || !button.closest('main > .view.active')) button.remove();
    });

    if (!view || view.id === 'overview-view') return;

    let button = view.querySelector(`:scope > .${BACK_CLASS}`);
    if (!button) {
      button = document.createElement('button');
      button.type = 'button';
      button.className = BACK_CLASS;
      view.prepend(button);
    }

    button.textContent = backLabel(view);
    button.setAttribute('aria-label', backLabel(view));
    button.onclick = () => navigateBack(backDestination(view));

    if (scrollToTop) {
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
          window.scrollTo({top: 0, left: 0, behavior: 'auto'});
          document.scrollingElement?.scrollTo?.({top: 0, left: 0, behavior: 'auto'});
          view.scrollTo?.({top: 0, left: 0, behavior: 'auto'});
        });
      });
    }
  }

  function scheduleBack({scrollToTop = false} = {}) {
    if (backFrame) window.cancelAnimationFrame(backFrame);
    backFrame = window.requestAnimationFrame(() => {
      backFrame = 0;
      mountBack({scrollToTop});
    });
  }

  function mountMobileMenu() {
    ensureMobileRouteOverrides();
    ensureBackStyle();
    if (window.innerWidth > 900) return false;

    const {sidebar, sourceNav, root: existingRoot} = sourceElements();
    if (!sidebar || !sourceNav) return false;
    if (existingRoot) {
      mounted = true;
      scheduleSync();
      scheduleBack();
      return true;
    }

    const icons = {
      overview:'⌂', projects:'▦', tasks:'✓', providers:'✦', organizations:'◎',
      reports:'≣', audit:'⌁', linux:'>_', 'token-usage':'◫', 'cloud-admin':'☁', 'investia-admin':'◇',
    };

    const root = document.createElement('div');
    root.className = 'mobile-simple-nav';
    root.setAttribute('aria-label', 'Navegação principal');
    root.innerHTML = `
      <button type="button" class="mobile-simple-item" data-simple-target="overview"><span aria-hidden="true">⌂</span><small>Início</small></button>
      <button type="button" class="mobile-simple-item" data-simple-target="projects"><span aria-hidden="true">▦</span><small>Projetos</small></button>
      <button type="button" class="mobile-simple-item" data-simple-target="tasks"><span aria-hidden="true">✓</span><small>Execuções</small></button>
      <button type="button" class="mobile-simple-item" data-simple-game><span aria-hidden="true">🎮</span><small>Jogo</small></button>
      <button type="button" class="mobile-simple-item" data-simple-menu-open aria-label="Abrir menu" aria-expanded="false"><span aria-hidden="true">☰</span><small>Menu</small></button>
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
    mounted = true;

    const list = sheet.querySelector('.mobile-simple-list');
    const openButton = root.querySelector('[data-simple-menu-open]');
    const closeButton = sheet.querySelector('.mobile-simple-close');

    const items = () => [...sourceNav.querySelectorAll(':scope > .nav')]
      .filter(item => !item.hidden && !item.classList.contains('nav-super-admin-forbidden'));

    const label = item => String(item.textContent || item.getAttribute('aria-label') || 'Abrir')
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/^Tarefas$/i, 'Execuções')
      .replace(/^Desenvolvimento$/i, 'Execuções');

    const icon = item => {
      if (item.dataset.exampleProject) return '◫';
      if (item.dataset.linuxView === '1') return icons.linux;
      if (item.dataset.devpilotFeaturePlaceholder === 'game' || item.dataset.devpilotGameStable === '1') return '🎮';
      return icons[item.dataset.view] || '•';
    };

    function close({restoreFocus = false} = {}) {
      sheet.hidden = true;
      backdrop.hidden = true;
      document.body.classList.remove('mobile-simple-open');
      openButton.setAttribute('aria-expanded', 'false');
      if (restoreFocus) openButton.focus?.();
    }

    function navigate(item) {
      if (!item) return;
      close();
      item.click();
      scheduleSync();
      scheduleBack({scrollToTop: true});
    }

    function renderMenu() {
      const fragment = document.createDocumentFragment();
      items().forEach(item => {
        const button = document.createElement('button');
        const active = item.classList.contains('active');
        button.type = 'button';
        button.className = `mobile-simple-row${active ? ' active' : ''}`;
        if (active) button.setAttribute('aria-current', 'page');
        button.innerHTML = `<span class="mobile-simple-icon" aria-hidden="true">${icon(item)}</span><span>${label(item)}</span><span class="mobile-simple-arrow" aria-hidden="true">›</span>`;
        button.addEventListener('click', () => navigate(item));
        fragment.appendChild(button);
      });
      list.replaceChildren(fragment);
    }

    function open() {
      renderMenu();
      sheet.hidden = false;
      backdrop.hidden = false;
      document.body.classList.add('mobile-simple-open');
      openButton.setAttribute('aria-expanded', 'true');
      window.requestAnimationFrame(() => closeButton?.focus?.());
    }

    root.querySelectorAll('[data-simple-target]').forEach(button => {
      button.addEventListener('click', () => {
        navigate(sourceNav.querySelector(`.nav[data-view="${CSS.escape(button.dataset.simpleTarget)}"]`));
      });
    });

    root.querySelector('[data-simple-game]')?.addEventListener('click', () => {
      window.location.assign('/game/index.html');
    });

    openButton.addEventListener('click', open);
    closeButton?.addEventListener('click', () => close({restoreFocus:true}));
    backdrop.addEventListener('click', () => close({restoreFocus:true}));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !sheet.hidden) close({restoreFocus:true});
    });

    scheduleSync();
    scheduleBack({scrollToTop: true});
    return true;
  }

  function sync() {
    syncFrame = 0;
    if (!mounted && !mountMobileMenu()) return;

    const {sourceNav, root, sheet} = sourceElements();
    if (!sourceNav || !root) return;

    root.querySelectorAll('[data-simple-target]').forEach(button => {
      const source = sourceNav.querySelector(`.nav[data-view="${CSS.escape(button.dataset.simpleTarget)}"]`);
      const active = Boolean(source?.classList.contains('active'));
      button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });

    if (sheet && !sheet.hidden) {
      const list = sheet.querySelector('.mobile-simple-list');
      if (list) {
        const rows = [...list.querySelectorAll('.mobile-simple-row')];
        const navItems = [...sourceNav.querySelectorAll(':scope > .nav')]
          .filter(item => !item.hidden && !item.classList.contains('nav-super-admin-forbidden'));
        if (rows.length !== navItems.length) {
          sheet.hidden = true;
          document.querySelector('.mobile-simple-backdrop')?.setAttribute('hidden', '');
          document.body.classList.remove('mobile-simple-open');
          root.querySelector('[data-simple-menu-open]')?.setAttribute('aria-expanded', 'false');
        }
      }
    }

    scheduleBack();
  }

  function scheduleSync() {
    if (syncFrame) return;
    syncFrame = window.requestAnimationFrame(sync);
  }

  function boot() {
    if (window.innerWidth <= 900) mountMobileMenu();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, {once:true});
  } else {
    boot();
  }

  window.addEventListener('resize', () => {
    if (window.innerWidth <= 900) mountMobileMenu();
    scheduleSync();
    scheduleBack();
  }, {passive:true});

  document.addEventListener('devpilot:view-changed', () => {
    scheduleSync();
    scheduleBack({scrollToTop: true});
  });
  document.addEventListener('devpilot:page-ready', scheduleSync);
  document.addEventListener('devpilot:feature-ready', scheduleSync);
  document.addEventListener('devpilot:login-complete', () => {
    scheduleSync();
    scheduleBack({scrollToTop: true});
  });

  console.info('[DevPilot] Menu mobile estável com retorno fixo no topo e abertura no início da página');
})();
