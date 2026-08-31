(() => {
  'use strict';

  if (window.__devpilotPageNavigationV38) return;
  window.__devpilotPageNavigationV38 = true;
  window.__devpilotPageNavigationV26 = true;

  const root = document.documentElement;
  const NAV_SELECTOR = '[data-view]';
  const SIDEBAR_NAV_SELECTOR = '.sidebar nav .nav[data-view]';
  const VIEW_TITLES = {
    overview: 'Visão geral',
    projects: 'Projetos',
    'new-project': 'Novo projeto',
    tasks: 'Execuções',
    providers: 'Modelos de IA',
    reports: 'Relatórios',
    audit: 'Auditoria',
    organizations: 'Organizações',
    users: 'Usuários',
    profile: 'Perfil',
    'cloud-admin': 'Clouds',
    'deploy-admin': 'Deploy',
    'super-admin': 'Super Admin',
    'local-test': 'Teste local',
    'mission-control': 'Mission Control',
    'rag-admin': 'RAG Admin',
    'investia-admin': 'InvestIA',
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
    if (item.dataset.view) return String(item.dataset.view).trim();
    if (item.dataset.profileView === '1') return 'profile';

    const label = normalize(item.textContent);
    const aliases = {
      'visao geral': 'overview',
      'inicio': 'overview',
      'projetos': 'projects',
      'novo projeto': 'new-project',
      'execucoes': 'tasks',
      'tarefas': 'tasks',
      'desenvolvimento': 'tasks',
      'modelos de ia': 'providers',
      'relatorios': 'reports',
      'auditoria': 'audit',
      'organizacoes': 'organizations',
      'usuarios': 'users',
      'perfil': 'profile',
      'clouds': 'cloud-admin',
      'deploy': 'deploy-admin',
      'mission control': 'mission-control',
      'rag admin': 'rag-admin',
    };
    return aliases[label] || '';
  }

  function targetFor(viewName) {
    return document.getElementById(`${viewName}-view`);
  }

  function labelFor(viewName) {
    if (VIEW_TITLES[viewName]) return VIEW_TITLES[viewName];

    const nav = Array.from(document.querySelectorAll(NAV_SELECTOR))
      .find(item => resolveView(item) === viewName);
    const navLabel = String(nav?.textContent || '').replace(/\s+/g, ' ').trim();
    if (navLabel) return navLabel.replace(/\s*[·•]\s*carregando…?$/iu, '').trim();

    const view = targetFor(viewName);
    const heading = view?.querySelector('h1, h2, h3, .panel-title h3');
    const headingLabel = String(heading?.textContent || '').replace(/\s+/g, ' ').trim();
    if (headingLabel) return headingLabel;

    return viewName
      .split('-')
      .filter(Boolean)
      .map(part => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }

  function closeMobileMenu() {
    document.querySelector('.mobile-simple-close')?.click?.();
    document.body.classList.remove('mobile-simple-open');
  }

  function markOnlyView(viewName) {
    const expectedId = `${viewName}-view`;
    document.querySelectorAll('.view').forEach(view => {
      const active = view.id === expectedId;
      view.classList.toggle('active', active);
      view.hidden = !active;
      view.setAttribute('aria-hidden', active ? 'false' : 'true');
    });

    document.querySelectorAll(NAV_SELECTOR).forEach(nav => {
      const active = resolveView(nav) === viewName;
      nav.classList.toggle('active', active);
      if (active) nav.setAttribute('aria-current', 'page');
      else nav.removeAttribute('aria-current');
    });
  }

  function restoreViewVisibility(viewName) {
    const view = targetFor(viewName);
    if (!view) return false;
    view.hidden = false;
    view.setAttribute('aria-hidden', 'false');
    return true;
  }

  function updateTitle(viewName) {
    const label = labelFor(viewName);
    const title = document.querySelector('#page-title');
    if (title) title.textContent = label;
    document.title = `DevPilot — ${label}`;
  }

  function updateHistory(viewName, replace = false) {
    const method = replace ? 'replaceState' : 'pushState';
    const target = viewName && viewName !== 'overview'
      ? `${location.pathname}${location.search}#/${encodeURIComponent(viewName)}`
      : `${location.pathname}${location.search}`;

    const current = `${location.pathname}${location.search}${location.hash}`;
    if (current === target) return;
    history[method]({devpilotView: viewName || 'overview'}, '', target);
  }

  function runNativeView(viewName) {
    const nativeShowView = window.showView;
    if (typeof nativeShowView === 'function') {
      nativeShowView(viewName);
    }
    markOnlyView(viewName);
  }

  function emitNavigationFailure(viewName, source, reason) {
    console.warn('[DevPilot] Falha de navegação', {view: viewName, source, reason});
    document.dispatchEvent(new CustomEvent('devpilot:navigation-failed', {
      detail: {view: viewName, source: source || 'navigation', reason},
    }));
  }

  function finish(viewName, options = {}, epoch = navigationEpoch) {
    if (epoch !== navigationEpoch || pendingView !== viewName) return;

    const view = targetFor(viewName);
    if (!view) {
      root.classList.remove('dp-page-switching');
      switching = false;
      pendingView = '';
      emitNavigationFailure(viewName, options.source, 'view-not-found');
      return;
    }

    markOnlyView(viewName);
    restoreViewVisibility(viewName);
    updateTitle(viewName);

    if (!reducedMotion) view.classList.add('dp-page-entering');

    window.scrollTo({top: 0, left: 0, behavior: 'auto'});
    document.querySelector('main')?.scrollTo?.({top: 0, left: 0, behavior: 'auto'});

    if (options.history !== false) updateHistory(viewName, Boolean(options.replaceHistory));

    root.dataset.devpilotView = viewName;
    root.classList.remove('dp-page-switching');
    root.classList.add('dp-page-ready');

    window.requestAnimationFrame(() => {
      if (epoch !== navigationEpoch) return;
      view.classList.remove('dp-page-entering');
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
    viewName = String(viewName || '').trim();
    if (!viewName) return false;
    if (switching && pendingView === viewName) return true;

    const target = targetFor(viewName);
    if (!target) {
      emitNavigationFailure(viewName, options.source, 'view-not-found');
      return false;
    }

    navigationEpoch += 1;
    const epoch = navigationEpoch;
    switching = true;
    pendingView = viewName;
    closeMobileMenu();

    root.classList.remove('dp-page-ready');
    root.classList.add('dp-page-switching');

    document.querySelectorAll('.dp-page-leaving').forEach(node => node.classList.remove('dp-page-leaving'));
    const current = document.querySelector('.view.active');
    if (!reducedMotion && current !== target) current?.classList.add('dp-page-leaving');

    window.setTimeout(() => {
      if (epoch !== navigationEpoch || pendingView !== viewName) return;
      current?.classList.remove('dp-page-leaving');
      runNativeView(viewName);
      window.requestAnimationFrame(() => finish(viewName, options, epoch));
    }, options.immediate || reducedMotion ? 0 : 72);

    return true;
  }

  window.devpilotNavigate = navigate;

  function internalViewControl(target) {
    const item = target?.closest?.(NAV_SELECTOR);
    if (!(item instanceof Element)) return null;
    if (item.dataset.devpilotFeaturePlaceholder) return null;
    if (item.matches('option')) return null;
    return item;
  }

  document.addEventListener('click', event => {
    const item = internalViewControl(event.target);
    if (!item) return;

    const viewName = resolveView(item);
    if (!viewName) return;

    const target = targetFor(viewName);
    if (!target) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    navigate(viewName, {
      source: item.closest('.sidebar') ? 'sidebar' : (item.closest('.mobile-bottom-nav, .mobile-simple-menu') ? 'mobile' : 'internal-link'),
    });
  }, true);

  function viewFromLocation() {
    const routeMatch = location.hash.match(/^#\/([^/?#]+)/);
    if (routeMatch) return decodeURIComponent(routeMatch[1]);

    const legacy = location.hash.match(/^#([A-Za-z0-9_-]+)$/);
    if (legacy) {
      const value = legacy[1];
      if (value === 'overview' || targetFor(value)) return value;
    }
    return 'overview';
  }

  function navigateFromLocation(source) {
    const viewName = viewFromLocation();
    if (!targetFor(viewName)) {
      navigate('overview', {source, history: false, immediate: true});
      return;
    }
    navigate(viewName, {source, history: false, immediate: true});
  }

  window.addEventListener('popstate', () => navigateFromLocation('history'));
  window.addEventListener('hashchange', () => navigateFromLocation('hash'));

  function initializeCurrentView() {
    const requested = viewFromLocation();
    const active = document.querySelector('.view.active');
    const fallback = active?.id?.replace(/-view$/, '') || 'overview';
    const viewName = targetFor(requested) ? requested : fallback;

    markOnlyView(viewName);
    restoreViewVisibility(viewName);
    updateTitle(viewName);
    root.dataset.devpilotView = viewName;

    if (requested !== viewName || (viewName === 'overview' && location.hash)) {
      updateHistory(viewName, true);
    }
  }

  document.addEventListener('devpilot:feature-ready', () => {
    const requested = viewFromLocation();
    if (requested !== 'overview' && targetFor(requested) && root.dataset.devpilotView !== requested) {
      navigate(requested, {source: 'feature-ready', history: false, immediate: true});
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCurrentView, {once: true});
  } else {
    initializeCurrentView();
  }

  console.info('[DevPilot] Page Navigation V38 — rotas internas unificadas');
})();
