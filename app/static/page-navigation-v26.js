(() => {
  'use strict';

  if (window.__devpilotPageNavigationV26) return;
  window.__devpilotPageNavigationV26 = true;

  const root = document.documentElement;
  const MAIN_NAV_SELECTOR = '.sidebar nav .nav';
  const VIEW_TITLES = {
    overview: 'Visão geral', projects: 'Projetos', tasks: 'Execuções', providers: 'Modelos de IA',
    reports: 'Relatórios', audit: 'Auditoria', organizations: 'Organizações', users: 'Usuários', profile: 'Perfil',
  };
  const FEATURE_BY_VIEW = {
    projects: 'projects', tasks: 'tasks', providers: 'providers', reports: 'reports', audit: 'audit', organizations: 'organizations',
  };

  let switching = false;
  let pendingView = '';
  let navigationEpoch = 0;
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;

  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').replace(/\s+/g, ' ').trim();

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

  function finish(viewName, options, epoch) {
    if (epoch !== navigationEpoch || pendingView !== viewName) return;
    markOnlyView(viewName);
    restoreViewVisibility(viewName);
    updateTitle(viewName);
    if (options.history !== false) updateHistory(viewName, Boolean(options.replaceHistory));
    root.dataset.devpilotView = viewName;
    root.classList.remove('dp-page-switching');
    document.dispatchEvent(new CustomEvent('devpilot:view-changed', {detail:{view:viewName, source:options.source || 'menu'}}));
    document.dispatchEvent(new CustomEvent('devpilot:page-ready', {detail:{view:viewName, source:options.source || 'menu'}}));
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
    root.classList.add('dp-page-switching');

    const ready = await ensureFeature(viewName);
    if (epoch !== navigationEpoch) return false;
    if (!ready) window.toast?.(`Alguns recursos de ${VIEW_TITLES[viewName] || viewName} não puderam ser carregados.`);

    runNativeView(viewName);
    window.requestAnimationFrame(() => finish(viewName, options, epoch));
    return true;
  }

  window.devpilotNavigate = navigate;

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
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initializeCurrentView, {once:true});
  else initializeCurrentView();
})();
