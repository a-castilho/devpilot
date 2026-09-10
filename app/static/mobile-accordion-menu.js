(() => {
  'use strict';

  if (window.__devpilotMobileAccordionMenuStable) return;
  window.__devpilotMobileAccordionMenuStable = true;

  const MOBILE_MAX = 900;
  const STYLE_ID = 'devpilot-mobile-shell-style-v2';
  const BACK_CLASS = 'mobile-page-back';
  const STACK_CLASS = 'mobile-action-stack';
  let mounted = false;
  let frame = 0;

  const activeView = () => document.querySelector('main > .view.active');
  const sourceNav = () => document.querySelector('.sidebar > nav');

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      @media (max-width:${MOBILE_MAX}px) {
        .sidebar {
          display:flex!important;
          align-items:stretch!important;
          height:calc(68px + env(safe-area-inset-bottom))!important;
          padding:6px max(6px,env(safe-area-inset-right)) calc(6px + env(safe-area-inset-bottom)) max(6px,env(safe-area-inset-left))!important;
        }
        .sidebar > nav,
        .sidebar > .mobile-nav-arrow,
        .sidebar > :not(.mobile-simple-nav) { display:none!important; }
        .sidebar > .mobile-simple-nav {
          display:grid!important;
          grid-template-columns:repeat(5,minmax(0,1fr))!important;
          gap:4px!important;
          width:100%!important;
          height:52px!important;
          margin:0!important;
        }
        .mobile-simple-item {
          width:100%!important;
          min-width:0!important;
          height:52px!important;
          min-height:52px!important;
          padding:3px 2px!important;
          border-radius:11px!important;
        }
        .mobile-simple-item > span { display:block!important; font-size:19px!important; line-height:1!important; }
        .mobile-simple-item > small { display:block!important; font-size:9px!important; line-height:1.1!important; }

        main > header .header-actions .dp-mobile-source-hidden,
        main > .view.active .dp-mobile-source-hidden { display:none!important; }

        main > .view.active > .${BACK_CLASS} {
          position:sticky;
          top:max(8px,env(safe-area-inset-top));
          z-index:82;
          display:flex;
          align-items:center;
          justify-content:flex-start;
          gap:12px;
          width:100%;
          min-height:54px;
          margin:0 0 12px;
          padding:0 18px;
          border:1px solid rgba(55,227,215,.65);
          border-radius:16px;
          background:linear-gradient(90deg,rgba(0,95,102,.97),rgba(7,45,66,.97));
          box-shadow:0 12px 30px rgba(0,0,0,.34),inset 0 1px 0 rgba(255,255,255,.08);
          color:#f3fbff;
          font:inherit;
          font-size:16px;
          font-weight:850;
          cursor:pointer;
          touch-action:manipulation;
        }
        main > .view.active > .${BACK_CLASS}::before {
          content:'←';
          color:#49f2e3;
          font-size:27px;
          font-weight:500;
          line-height:1;
        }

        main > .view.active > .${STACK_CLASS} {
          display:grid;
          gap:9px;
          width:100%;
          margin:0 0 16px;
        }
        .mobile-primary-cta {
          width:100%;
          min-height:58px;
          border:1px solid rgba(70,255,195,.38);
          border-radius:16px;
          background:linear-gradient(90deg,#08a86f,#0d987e);
          box-shadow:0 14px 30px rgba(0,145,104,.20),inset 0 1px 0 rgba(255,255,255,.10);
          color:#fff;
          font:inherit;
          font-size:17px;
          font-weight:900;
          cursor:pointer;
          touch-action:manipulation;
        }
        .mobile-primary-cta:disabled { opacity:.55; cursor:not-allowed; }
        .mobile-control-accordion {
          overflow:hidden;
          border:1px solid rgba(55,201,214,.28);
          border-radius:14px;
          background:linear-gradient(180deg,rgba(9,31,49,.94),rgba(5,22,38,.96));
          box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
        }
        .mobile-control-accordion[open] { border-color:rgba(55,227,215,.46); }
        .mobile-control-accordion > summary {
          position:relative;
          display:flex;
          align-items:center;
          min-height:52px;
          padding:0 48px 0 16px;
          color:#eefaff;
          font-size:15px;
          font-weight:750;
          list-style:none;
          cursor:pointer;
          user-select:none;
        }
        .mobile-control-accordion > summary::-webkit-details-marker { display:none; }
        .mobile-control-accordion > summary::after {
          content:'⌄';
          position:absolute;
          right:17px;
          top:50%;
          transform:translateY(-52%);
          color:#7cebe4;
          font-size:20px;
          transition:transform .16s ease;
        }
        .mobile-control-accordion[open] > summary::after { transform:translateY(-48%) rotate(180deg); }
        .mobile-control-body {
          display:grid;
          gap:9px;
          padding:0 12px 12px;
        }
        .mobile-control-body > button {
          width:100%;
          min-height:46px;
          padding:10px 14px;
          border:1px solid rgba(128,174,209,.20);
          border-radius:12px;
          background:#10243a;
          color:#eef6ff;
          font:inherit;
          font-weight:750;
          text-align:center;
          cursor:pointer;
        }
        .mobile-control-body .tasks-v9-filters,
        .mobile-control-body .tasks-v9-filters > * { width:100%!important; max-width:none!important; }
        .mobile-control-body .tasks-v9-filters { margin:0!important; }
        .mobile-control-body .section-head { margin:0!important; }
        #tasks-v9-back,
        .project-builder-back { display:none!important; }
      }
      @media (min-width:${MOBILE_MAX + 1}px) {
        .${BACK_CLASS}, .${STACK_CLASS} { display:none!important; }
      }
    `;
    document.head.appendChild(style);
  }

  function proxy(source, className = '') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.textContent = String(source?.textContent || source?.getAttribute('aria-label') || 'Abrir').replace(/\s+/g, ' ').trim();
    button.disabled = Boolean(source?.disabled);
    button.addEventListener('click', () => source?.click());
    return button;
  }

  function accordion(label, nodes = []) {
    if (!nodes.length) return null;
    const details = document.createElement('details');
    details.className = 'mobile-control-accordion';
    const summary = document.createElement('summary');
    summary.textContent = label;
    const body = document.createElement('div');
    body.className = 'mobile-control-body';
    nodes.forEach(node => body.appendChild(node));
    details.append(summary, body);
    return details;
  }

  function preferredPrimary(view) {
    if (!view) return null;
    if (view.id === 'projects-view') return view.querySelector('[data-project-builder-open]');
    if (view.id === 'tasks-view') return view.querySelector('.tasks-v9-toolbar .primary[data-open="task-modal"]');
    if (view.id === 'overview-view') return view.querySelector('.overview-actions .primary[data-open="task-modal"]');
    if (view.id === 'new-project-view') return view.querySelector('#project-builder-submit, .project-builder-sticky-submit');
    // Formulários administrativos precisam manter a ação de persistência junto aos campos.
    // Não mova o Salvar de Clouds para o CTA compacto do topo no mobile.
    if (view.id === 'cloud-admin-view') return null;
    return view.querySelector('.primary');
  }

  function collectActionSources(view, primary) {
    const sources = [];
    const add = node => {
      if (!node || node === primary || sources.includes(node)) return;
      sources.push(node);
    };
    document.querySelectorAll('main > header .header-actions button').forEach(add);
    if (view?.id === 'overview-view') view.querySelectorAll('.overview-actions button').forEach(add);
    if (view?.id === 'tasks-view') view.querySelectorAll('.tasks-v9-toolbar button').forEach(add);
    if (view?.id === 'new-project-view') view.querySelectorAll('.project-builder-back').forEach(add);
    return sources;
  }

  function mountCompactControls() {
    ensureStyle();
    if (window.innerWidth > MOBILE_MAX) return;
    const view = activeView();
    if (!view) return;

    document.querySelectorAll(`.${STACK_CLASS}`).forEach(stack => {
      if (!stack.closest('main > .view.active')) stack.remove();
    });
    document.querySelectorAll('.dp-mobile-source-hidden').forEach(node => node.classList.remove('dp-mobile-source-hidden'));

    let stack = view.querySelector(`:scope > .${STACK_CLASS}`);
    if (stack) stack.remove();
    stack = document.createElement('section');
    stack.className = STACK_CLASS;
    stack.setAttribute('aria-label', 'Ações da tela');

    const primary = preferredPrimary(view);
    if (primary) {
      primary.classList.add('dp-mobile-source-hidden');
      const cta = proxy(primary, 'mobile-primary-cta');
      stack.appendChild(cta);
    }

    const actionSources = collectActionSources(view, primary);
    const actionButtons = actionSources.map(source => {
      source.classList.add('dp-mobile-source-hidden');
      return proxy(source);
    });
    const actions = accordion('Ações do sistema', actionButtons);
    if (actions) stack.appendChild(actions);

    if (view.id === 'tasks-view') {
      const filters = view.querySelector('.tasks-v9-filters');
      if (filters) {
        const filtersClone = filters.cloneNode(true);
        filtersClone.querySelectorAll('[id]').forEach(node => node.removeAttribute('id'));
        filtersClone.querySelectorAll('input,select,button').forEach(control => {
          const originalId = control.getAttribute('id');
          if (originalId) control.removeAttribute('id');
        });
        filtersClone.addEventListener('input', event => {
          const target = event.target;
          const label = target?.closest('label')?.querySelector('span')?.textContent?.trim();
          const originals = [...filters.querySelectorAll('input,select')];
          const original = originals.find(item => item.closest('label')?.querySelector('span')?.textContent?.trim() === label);
          if (original) {
            original.value = target.value;
            original.dispatchEvent(new Event('input', {bubbles:true}));
            original.dispatchEvent(new Event('change', {bubbles:true}));
          }
        });
        filters.classList.add('dp-mobile-source-hidden');
        const filterAccordion = accordion('Filtros e busca', [filtersClone]);
        if (filterAccordion) stack.appendChild(filterAccordion);
      }
      const indicators = view.querySelector('#tasks-v9-indicators');
      if (indicators) {
        const indicatorAccordion = accordion('Indicadores', [proxy(indicators)]);
        if (indicatorAccordion) stack.appendChild(indicatorAccordion);
      }
    }

    if (view.id === 'projects-view') {
      const intro = view.querySelector('.section-head > div');
      if (intro) {
        intro.classList.add('dp-mobile-source-hidden');
        const copy = intro.cloneNode(true);
        copy.classList.remove('dp-mobile-source-hidden');
        const fleet = accordion('Frota de projetos', [copy]);
        if (fleet) stack.appendChild(fleet);
      }
    }

    const back = view.querySelector(`:scope > .${BACK_CLASS}`);
    if (back?.nextSibling) view.insertBefore(stack, back.nextSibling);
    else if (back) view.appendChild(stack);
    else view.prepend(stack);
  }

  function backDestination(view) {
    return view?.id === 'new-project-view' ? 'projects' : 'overview';
  }

  function mountBack({scrollToTop = false} = {}) {
    ensureStyle();
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
    button.textContent = view.id === 'new-project-view' ? 'Voltar para Projetos' : 'Voltar';
    button.onclick = () => {
      const target = backDestination(view);
      const nav = sourceNav()?.querySelector(`.nav[data-view="${CSS.escape(target)}"]`);
      if (nav) nav.click();
      else window.location.hash = target === 'overview' ? '#overview' : `#${target}`;
    };

    if (scrollToTop) {
      window.requestAnimationFrame(() => window.requestAnimationFrame(() => {
        window.scrollTo({top:0,left:0,behavior:'auto'});
        document.scrollingElement?.scrollTo?.({top:0,left:0,behavior:'auto'});
      }));
    }
  }

  function mountMobileMenu() {
    ensureStyle();
    if (window.innerWidth > MOBILE_MAX) return false;
    const sidebar = document.querySelector('.sidebar');
    const nav = sourceNav();
    if (!sidebar || !nav) return false;

    let root = sidebar.querySelector(':scope > .mobile-simple-nav');
    if (!root) {
      root = document.createElement('div');
      root.className = 'mobile-simple-nav';
      root.setAttribute('aria-label', 'Navegação principal');
      root.innerHTML = `
        <button type="button" class="mobile-simple-item" data-simple-target="overview"><span>⌂</span><small>Início</small></button>
        <button type="button" class="mobile-simple-item" data-simple-target="projects"><span>▦</span><small>Projetos</small></button>
        <button type="button" class="mobile-simple-item" data-simple-target="tasks"><span>✓</span><small>Execuções</small></button>
        <button type="button" class="mobile-simple-item" data-simple-game><span>🎮</span><small>Jogo</small></button>
        <button type="button" class="mobile-simple-item" data-simple-menu-open><span>☰</span><small>Menu</small></button>`;
      sidebar.appendChild(root);

      root.querySelectorAll('[data-simple-target]').forEach(button => {
        button.addEventListener('click', () => nav.querySelector(`.nav[data-view="${CSS.escape(button.dataset.simpleTarget)}"]`)?.click());
      });
      root.querySelector('[data-simple-game]')?.addEventListener('click', () => window.location.assign('/game/index.html'));
      root.querySelector('[data-simple-menu-open]')?.addEventListener('click', () => {
        const source = [...nav.querySelectorAll(':scope > .nav')].filter(item => !item.hidden && !item.classList.contains('nav-super-admin-forbidden'));
        const existing = document.querySelector('.mobile-simple-sheet');
        existing?.remove();
        const sheet = document.createElement('section');
        sheet.className = 'mobile-simple-sheet';
        sheet.innerHTML = `<div class="mobile-simple-sheet-head"><div><span class="eyebrow">NAVEGAÇÃO</span><h2>Menu</h2></div><button type="button" class="mobile-simple-close">×</button></div><div class="mobile-simple-list"></div>`;
        const list = sheet.querySelector('.mobile-simple-list');
        source.forEach(item => {
          const row = document.createElement('button');
          row.type = 'button';
          row.className = `mobile-simple-row${item.classList.contains('active') ? ' active' : ''}`;
          row.textContent = String(item.textContent || '').replace(/\s+/g,' ').trim();
          row.onclick = () => { item.click(); sheet.remove(); };
          list.appendChild(row);
        });
        sheet.querySelector('.mobile-simple-close').onclick = () => sheet.remove();
        document.body.appendChild(sheet);
      });
    }
    mounted = true;
    return true;
  }

  function sync({scrollToTop = false} = {}) {
    if (window.innerWidth > MOBILE_MAX) return;
    mountMobileMenu();
    mountBack({scrollToTop});
    mountCompactControls();

    const nav = sourceNav();
    const root = document.querySelector('.mobile-simple-nav');
    root?.querySelectorAll('[data-simple-target]').forEach(button => {
      const source = nav?.querySelector(`.nav[data-view="${CSS.escape(button.dataset.simpleTarget)}"]`);
      button.classList.toggle('active', Boolean(source?.classList.contains('active')));
    });
  }

  function schedule(options = {}) {
    if (frame) window.cancelAnimationFrame(frame);
    frame = window.requestAnimationFrame(() => {
      frame = 0;
      sync(options);
    });
  }

  function boot() {
    if (window.innerWidth <= MOBILE_MAX) schedule({scrollToTop:true});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();

  window.addEventListener('resize', () => schedule(), {passive:true});
  document.addEventListener('devpilot:view-changed', () => schedule({scrollToTop:true}));
  document.addEventListener('devpilot:page-ready', () => schedule());
  document.addEventListener('devpilot:feature-ready', () => schedule());
  document.addEventListener('devpilot:login-complete', () => schedule({scrollToTop:true}));

  console.info('[DevPilot] Mobile compacto: um CTA verde, ações preservadas em sanfonas e navegação fixa');
})();