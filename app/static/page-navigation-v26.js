(() => {
  'use strict';

  if (window.__devpilotPageNavigationV26) return;
  window.__devpilotPageNavigationV26 = true;

  const root = document.documentElement;
  const MAIN_NAV_SELECTOR = '.sidebar nav .nav';
  const VIEW_TITLES = {
    overview: 'Visão geral',
    projects: 'Projetos',
    tasks: 'Execuções',
    providers: 'Modelos de IA',
    reports: 'Relatórios',
    audit: 'Auditoria',
    organizations: 'Organizações',
    users: 'Usuários',
    profile: 'Perfil',
  };

  let switching = false;
  let pendingView = '';
  let navigationEpoch = 0;
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;

  const normalize = value => String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('pt-BR')
    .replace(/\s+/g, ' ')
    .trim();

  function resolveView(item) {
    if (!(item instanceof Element)) return '';
    if (item.dataset.view) return String(item.dataset.view);
    if (item.dataset.profileView === '1') return 'profile';

    const label = normalize(item.textContent);
    const aliases = {
      'visao geral': 'overview',
      'inicio': 'overview',
      'projetos': 'projects',
      'execucoes': 'tasks',
      'tarefas': 'tasks',
      'desenvolvimento': 'tasks',
      'modelos de ia': 'providers',
      'relatorios': 'reports',
      'auditoria': 'audit',
      'organizacoes': 'organizations',
      'usuarios': 'users',
      'perfil': 'profile',
    };
    return aliases[label] || '';
  }

  function closeMobileMenu() {
    document.querySelector('.mobile-simple-close')?.click?.();
    document.body.classList.remove('mobile-simple-open');
  }

  function markOnlyView(viewName) {
    const expectedId = `${viewName}-view`;
    document.querySelectorAll('main > .view, main .view').forEach(view => {
      const active = view.id === expectedId;
      view.classList.toggle('active', active);
      view.hidden = !active;
      view.setAttribute('aria-hidden', active ? 'false' : 'true');
    });

    document.querySelectorAll(MAIN_NAV_SELECTOR).forEach(nav => {
      const active = resolveView(nav) === viewName;
      nav.classList.toggle('active', active);
      if (active) nav.setAttribute('aria-current', 'page');
      else nav.removeAttribute('aria-current');
    });
  }

  function restoreViewVisibility(viewName) {
    const view = document.getElementById(`${viewName}-view`);
    if (view) {
      view.hidden = false;
      view.setAttribute('aria-hidden', 'false');
    }
  }

  function updateTitle(viewName) {
    const title = document.querySelector('#page-title');
    const label = VIEW_TITLES[viewName];
    if (!label) return;
    if (title) title.textContent = label;
    document.title = `DevPilot — ${label}`;
  }

  function updateHistory(viewName, replace = false) {
    if (!viewName || viewName === 'overview') {
      if (location.hash && location.hash.startsWith('#/')) {
        history[replace ? 'replaceState' : 'pushState']({devpilotView: 'overview'}, '', location.pathname + location.search);
      }
      return;
    }

    const nextHash = `#/${encodeURIComponent(viewName)}`;
    if (location.hash === nextHash) return;
    history[replace ? 'replaceState' : 'pushState']({devpilotView: viewName}, '', nextHash);
  }

  function runNativeView(viewName) {
    const nativeShowView = window.showView;
    if (typeof nativeShowView === 'function') {
      nativeShowView(viewName);
      return true;
    }
    markOnlyView(viewName);
    return false;
  }

  function finish(viewName, options = {}, epoch = navigationEpoch) {
    if (epoch !== navigationEpoch || pendingView !== viewName) return;

    markOnlyView(viewName);
    restoreViewVisibility(viewName);
    updateTitle(viewName);

    const view = document.getElementById(`${viewName}-view`);
    if (!reducedMotion) view?.classList.add('dp-page-entering');

    window.scrollTo({top: 0, left: 0, behavior: 'auto'});
    document.querySelector('main')?.scrollTo?.({top: 0, left: 0, behavior: 'auto'});

    if (options.history !== false) updateHistory(viewName, Boolean(options.replaceHistory));

    root.dataset.devpilotView = viewName;
    root.classList.remove('dp-page-switching');
    root.classList.add('dp-page-ready');

    window.requestAnimationFrame(() => {
      if (epoch !== navigationEpoch) return;
      view?.classList.remove('dp-page-entering');
      window.setTimeout(() => {
        if (epoch === navigationEpoch) root.classList.remove('dp-page-ready');
      }, reducedMotion ? 0 : 170);
    });

    document.dispatchEvent(new CustomEvent('devpilot:view-changed', {
      detail: {view: viewName, source: options.source || 'menu'}
    }));
    document.dispatchEvent(new CustomEvent('devpilot:page-ready', {
      detail: {view: viewName, source: options.source || 'menu'}
    }));

    switching = false;
    pendingView = '';
  }

  function navigate(viewName, options = {}) {
    if (!viewName) return false;
    if (switching && pendingView === viewName) return true;

    const target = document.getElementById(`${viewName}-view`);
    if (!target && viewName !== 'users' && viewName !== 'profile') return false;

    navigationEpoch += 1;
    const epoch = navigationEpoch;
    switching = true;
    pendingView = viewName;
    closeMobileMenu();

    root.classList.remove('dp-page-ready');
    root.classList.add('dp-page-switching');

    document.querySelectorAll('.dp-page-leaving').forEach(node => node.classList.remove('dp-page-leaving'));
    const current = document.querySelector('.view.active');
    if (!reducedMotion) current?.classList.add('dp-page-leaving');

    window.setTimeout(() => {
      if (epoch !== navigationEpoch || pendingView !== viewName) return;
      current?.classList.remove('dp-page-leaving');
      runNativeView(viewName);

      window.requestAnimationFrame(() => {
        finish(viewName, options, epoch);
      });
    }, options.immediate || reducedMotion ? 0 : 72);

    return true;
  }

  window.devpilotNavigate = navigate;

  document.addEventListener('click', event => {
    const item = event.target.closest?.(MAIN_NAV_SELECTOR);
    if (!item || item.dataset.devpilotFeaturePlaceholder) return;

    const viewName = resolveView(item);
    if (!viewName) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    navigate(viewName, {source: 'menu'});
  }, true);

  window.addEventListener('popstate', () => {
    const match = location.hash.match(/^#\/([^/?#]+)/);
    const viewName = match ? decodeURIComponent(match[1]) : 'overview';
    navigate(viewName, {source: 'history', history: false, immediate: true});
  });

  function initializeCurrentView() {
    const active = document.querySelector('.view.active');
    const viewName = active?.id?.replace(/-view$/, '') || 'overview';
    markOnlyView(viewName);
    updateTitle(viewName);
    root.dataset.devpilotView = viewName;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCurrentView, {once: true});
  } else {
    initializeCurrentView();
  }

  console.info('[DevPilot] Page Navigation V26 estável');
})();
