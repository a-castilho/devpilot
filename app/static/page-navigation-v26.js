(() => {
  'use strict';

  if (window.__devpilotPageNavigationV26) return;
  window.__devpilotPageNavigationV26 = true;

  const root = document.documentElement;
  const MAIN_NAV_SELECTOR = '.sidebar nav .nav';
  const VIEW_TITLES = {
    overview: 'Visão geral', projects: 'Projetos', 'new-project': 'Novo projeto', tasks: 'Execuções', providers: 'Modelos de IA',
    reports: 'Relatórios', audit: 'Auditoria', organizations: 'Organizações', users: 'Usuários', profile: 'Perfil',
  };
  const FEATURE_BY_VIEW = {
    projects: 'projects', 'new-project': 'projectBuilder', tasks: 'tasks', providers: 'providers', reports: 'reports', audit: 'audit', organizations: 'organizations',
  };

  let switching = false;
  let pendingView = '';
  let navigationEpoch = 0;

  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').replace(/\s+/g, ' ').trim();

  function appendStylesheet(id, href) {
    if (document.getElementById(id)) return;
    const link = document.createElement('link');
    link.id = id;
    link.rel = 'stylesheet';
    link.href = href;
    document.head.appendChild(link);
  }

  function ensureGameUiStyles() {
    appendStylesheet('devpilot-game-operations-v39', '/assets/game-operations-v39.css?v=20260901-1');
    appendStylesheet('devpilot-execution-ship-v45', '/assets/execution-ship-v45.css?v=20260901-1');
  }

  function resolveView(item) {
    if (!(item instanceof Element)) return '';
    if (item.dataset.view) return String(item.dataset.view);
    if (item.dataset.profileView === '1') return 'profile';
    return ({'visao geral':'overview','inicio':'overview','projetos':'projects','execucoes':'tasks','tarefas':'tasks','desenvolvimento':'tasks','modelos de ia':'providers','relatorios':'reports','auditoria':'audit','organizacoes':'organizations','usuarios':'users','perfil':'profile'})[normalize(item.textContent)] || '';
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
      view.classList.remove('dp-page-leaving', 'dp-page-entering');
    });
    document.querySelectorAll(MAIN_NAV_SELECTOR).forEach(nav => {
      const active = resolveView(nav) === viewName;
      nav.classList.toggle('active', active);
      if (active) nav.setAttribute('aria-current', 'page'); else nav.removeAttribute('aria-current');
    });
  }

  function restoreViewVisibility(viewName) {
    const view = document.getElementById(`${viewName}-view`);
    if (!view) return;
    view.hidden = false;
    view.setAttribute('aria-hidden', 'false');
  }

  function updateTitle(viewName) {
    const label = VIEW_TITLES[viewName];
    if (!label) return;
    const title = document.querySelector('#page-title');
    if (title) title.textContent = label;
    document.title = `DevPilot — ${label}`;
  }

  function updateHistory(viewName, replace = false) {
    if (!viewName || viewName === 'overview') {
      if (location.hash.startsWith('#/')) history[replace ? 'replaceState' : 'pushState']({devpilotView:'overview'}, '', location.pathname + location.search);
      return;
    }
    const nextHash = `#/${encodeURIComponent(viewName)}`;
    if (location.hash !== nextHash) history[replace ? 'replaceState' : 'pushState']({devpilotView:viewName}, '', nextHash);
  }

  async function ensureFeature(viewName) {
    const feature = FEATURE_BY_VIEW[viewName];
    if (!feature || typeof window.__devpilotLoadFeature !== 'function') return true;
    try { return await window.__devpilotLoadFeature(feature); }
    catch (error) { console.error(`[DevPilot] Falha ao carregar ${feature}`, error); return false; }
  }

  function runNativeView(viewName) {
    if (typeof window.showView === 'function') {
      window.showView(viewName);
      return;
    }
    markOnlyView(viewName);
  }

  function commitView(viewName, options = {}) {
    runNativeView(viewName);
    markOnlyView(viewName);
    restoreViewVisibility(viewName);
    updateTitle(viewName);
    if (options.history !== false) updateHistory(viewName, Boolean(options.replaceHistory));
    root.dataset.devpilotView = viewName;
    root.classList.remove('dp-page-switching');
    document.dispatchEvent(new CustomEvent('devpilot:view-changed', {detail:{view:viewName, source:options.source || 'menu'}}));
  }

  function finish(viewName, options, epoch, ready) {
    if (epoch !== navigationEpoch || pendingView !== viewName) return;
    root.classList.remove('dp-page-switching');
    if (!ready) window.toast?.(`Alguns recursos de ${VIEW_TITLES[viewName] || viewName} não puderam ser carregados.`);
    document.dispatchEvent(new CustomEvent('devpilot:page-ready', {detail:{view:viewName, source:options.source || 'menu', resourcesReady:Boolean(ready)}}));
    switching = false;
    pendingView = '';
  }

  async function navigate(viewName, options = {}) {
    if (!viewName) return false;
    const target = document.getElementById(`${viewName}-view`);
    if (!target && !['users','profile'].includes(viewName)) return false;
    if (switching && pendingView === viewName) return true;

    navigationEpoch += 1;
    const epoch = navigationEpoch;
    switching = true;
    pendingView = viewName;
    closeMobileMenu();

    // A troca visual é atômica e imediata. O carregamento lazy nunca pode
    // manter a view anterior por baixo nem bloquear os cliques da nova tela.
    root.classList.add('dp-page-switching');
    commitView(viewName, options);

    // Recursos da view são carregados depois que a tela já está utilizável.
    // Timeout/erro de bundle não deixa a SPA presa em estado de switching.
    let ready = true;
    try {
      ready = await ensureFeature(viewName);
      if (epoch !== navigationEpoch) return false;
      return true;
    } finally {
      finish(viewName, options, epoch, ready);
    }
  }

  window.devpilotNavigate = navigate;

  function installVisibilitySafeShowView() {
    if (window.__devpilotVisibilitySafeShowViewV39) return;
    const nativeShowView = window.showView;
    if (typeof nativeShowView !== 'function') return;
    window.__devpilotVisibilitySafeShowViewV39 = true;
    window.showView = function devpilotVisibilitySafeShowView(viewName) {
      const result = nativeShowView.apply(this, arguments);
      if (viewName === 'organizations' && typeof window.isSuperAdmin === 'function' && !window.isSuperAdmin()) return result;
      if (!document.getElementById(`${viewName}-view`)) return result;
      markOnlyView(viewName);
      restoreViewVisibility(viewName);
      updateTitle(viewName);
      root.dataset.devpilotView = viewName;
      root.classList.remove('dp-page-switching');
      return result;
    };
  }

  document.addEventListener('click', event => {
    const item = event.target.closest?.(MAIN_NAV_SELECTOR);
    if (!item || item.dataset.devpilotFeaturePlaceholder) return;
    const viewName = resolveView(item);
    if (!viewName) return;
    event.preventDefault();
    void navigate(viewName, {source:'menu'});
  });

  window.addEventListener('popstate', () => {
    const match = location.hash.match(/^#\/([^/?#]+)/);
    void navigate(match ? decodeURIComponent(match[1]) : 'overview', {source:'history', history:false});
  });

  function initializeCurrentView() {
    const active = document.querySelector('.view.active');
    const viewName = active?.id?.replace(/-view$/, '') || 'overview';
    markOnlyView(viewName);
    updateTitle(viewName);
    root.dataset.devpilotView = viewName;
    root.classList.remove('dp-page-switching');
  }

  ensureGameUiStyles();
  installVisibilitySafeShowView();

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initializeCurrentView, {once:true});
  else initializeCurrentView();
})();