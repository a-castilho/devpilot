(() => {
  'use strict';

  const TOKEN_KEY = 'devpilot-token';
  const MOBILE_PROJECT_LIMIT = 6;
  const MOBILE_PROJECT_TIMEOUT_MS = 7000;

  function tokenExpired(token) {
    try {
      const parts = String(token || '').split('.');
      if (parts.length !== 3) return true;
      const payload = JSON.parse(
        decodeURIComponent(
          atob(parts[1].replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(parts[1].length / 4) * 4, '='))
            .split('')
            .map(char => `%${char.charCodeAt(0).toString(16).padStart(2, '0')}`)
            .join('')
        )
      );
      const exp = Number(payload?.exp || 0);
      if (!Number.isFinite(exp) || exp <= 0) return true;
      return exp <= Math.floor(Date.now() / 1000) + 5;
    } catch (_) {
      return true;
    }
  }

  const storedToken = String(localStorage.getItem(TOKEN_KEY) || '').trim();
  if (storedToken && tokenExpired(storedToken)) {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.setItem('devpilot-auth-message', 'Sua sessão expirou. Entre novamente.');
    document.documentElement.dataset.devpilotExpiredSessionCleared = '1';
  }

  const isMobileViewport = () => window.matchMedia?.('(max-width: 900px)')?.matches === true;
  const escapeHtml = value => String(value ?? '').replace(/[&<>'\"]/g, char => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '\"':'&quot;',
  }[char]));

  function installMobileProjectStyle() {
    if (!isMobileViewport() || document.getElementById('devpilot-mobile-project-safe-style')) return;
    document.documentElement.classList.add('devpilot-low-power');
    const style = document.createElement('style');
    style.id = 'devpilot-mobile-project-safe-style';
    style.textContent = `
      html.devpilot-mobile-project-safe #projects-view .project-visual-overview,
      html.devpilot-mobile-project-safe #projects-view .project-ship-svg,
      html.devpilot-mobile-project-safe #projects-view .project-ship-hangar,
      html.devpilot-mobile-project-safe #projects-view .projects-command-center,
      html.devpilot-mobile-project-safe #projects-view [data-project-fleet],
      html.devpilot-mobile-project-safe #projects-view canvas,
      html.devpilot-mobile-project-safe #projects-view svg { display:none !important; }
      html.devpilot-mobile-project-safe #projects-list { display:grid !important; grid-template-columns:1fr !important; gap:12px !important; }
      html.devpilot-mobile-project-safe #projects-list .project-card { min-height:0 !important; padding:16px !important; contain:layout paint !important; content-visibility:auto !important; box-shadow:none !important; animation:none !important; filter:none !important; }
      html.devpilot-mobile-project-safe #projects-list .project-card p,
      html.devpilot-mobile-project-safe #projects-list .project-card code,
      html.devpilot-mobile-project-safe #projects-list .project-card .list-row > small { display:none !important; }
      html.devpilot-mobile-project-safe #projects-list .list-row { border:0 !important; padding:0 !important; }
      html.devpilot-mobile-project-safe #projects-list .list-row > div { width:100% !important; display:grid !important; grid-template-columns:1fr 1fr !important; gap:8px !important; }
      html.devpilot-mobile-project-safe #projects-list button { min-height:44px !important; }
    `;
    document.head.appendChild(style);
  }

  async function fetchMobileProjects() {
    const token = String(localStorage.getItem(TOKEN_KEY) || '').trim();
    if (!token) throw new Error('Autenticação necessária');
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), MOBILE_PROJECT_TIMEOUT_MS);
    try {
      const response = await fetch(`/api/ui/projects?limit=${MOBILE_PROJECT_LIMIT}`, {
        headers: {Authorization:`Bearer ${token}`},
        cache:'no-store',
        signal:controller.signal,
      });
      const data = await response.json().catch(() => ([]));
      if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : `Falha ao carregar projetos (HTTP ${response.status})`);
      return Array.isArray(data) ? data : [];
    } catch (error) {
      if (error?.name === 'AbortError') throw new Error('Projetos demoraram mais de 7 segundos. Tente novamente.');
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function renderMobileProjects(projects) {
    const target = document.getElementById('projects-list');
    if (!target) return;
    target.innerHTML = projects.map(project => `
      <article class="project-card" data-mobile-safe-project="${escapeHtml(project.id)}">
        <span class="eyebrow">${escapeHtml(String(project.status || 'ativo').toUpperCase())}</span>
        <h3>${escapeHtml(project.name || 'Projeto')}</h3>
        <div class="list-row"><div>
          <button class="link" type="button" data-mobile-project-analyze="${escapeHtml(project.id)}">Analisar</button>
          <button class="link" type="button" data-mobile-project-task="${escapeHtml(project.id)}">Nova execução</button>
        </div></div>
      </article>
    `).join('') || '<div class="empty">Nenhum projeto cadastrado.</div>';
  }

  async function mobileLoadProjects() {
    const target = document.getElementById('projects-list');
    if (target) target.innerHTML = '<div class="empty">Carregando até 6 projetos…</div>';
    try {
      const projects = await fetchMobileProjects();
      if (typeof window.state === 'object') window.state.projects = projects;
      try { if (typeof state === 'object') state.projects = projects; } catch (_) {}
      renderMobileProjects(projects);
      try { if (typeof fillProjects === 'function') fillProjects(); } catch (_) {}
      return projects;
    } catch (error) {
      if (target) target.innerHTML = `<div class="empty" role="alert">${escapeHtml(error?.message || 'Falha ao carregar projetos')}<br><button class="ghost" type="button" data-mobile-project-retry>Tentar novamente</button></div>`;
      return [];
    }
  }

  function showProjectsSafe() {
    if (!isMobileViewport()) return false;
    document.documentElement.classList.add('devpilot-mobile-project-safe', 'devpilot-low-power');
    try {
      if (typeof setActiveView === 'function') setActiveView('projects');
      else if (typeof showView === 'function') showView('projects');
    } catch (_) {
      document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === 'projects-view'));
    }
    const title = document.getElementById('page-title');
    if (title) title.textContent = 'Projetos';
    void mobileLoadProjects();
    document.dispatchEvent(new CustomEvent('devpilot:view-changed', {detail:{view:'projects', source:'mobile-safe'}}));
    return true;
  }

  function projectTrigger(target) {
    return target instanceof Element
      ? target.closest('[data-view="projects"], [data-mobile-view="projects"], a[href*="#/projects"], a[href$="#projects"]')
      : null;
  }

  function installMobileProjectCircuitBreaker() {
    if (!isMobileViewport() || window.__devpilotMobileProjectsCircuitBreaker) return;
    window.__devpilotMobileProjectsCircuitBreaker = true;
    installMobileProjectStyle();

    document.addEventListener('click', event => {
      const trigger = projectTrigger(event.target);
      if (!trigger) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      showProjectsSafe();
      try { history.replaceState(null, '', `${location.pathname}${location.search}#/projects`); } catch (_) {}
    }, true);

    document.addEventListener('click', event => {
      const retry = event.target instanceof Element ? event.target.closest('[data-mobile-project-retry]') : null;
      if (retry) {
        event.preventDefault();
        void mobileLoadProjects();
        return;
      }
      const analyze = event.target instanceof Element ? event.target.closest('[data-mobile-project-analyze]') : null;
      if (analyze) {
        event.preventDefault();
        const id = analyze.dataset.mobileProjectAnalyze;
        analyze.disabled = true;
        Promise.resolve(typeof api === 'function' ? api(`/projects/${encodeURIComponent(id)}/analyze`, {method:'POST'}) : null)
          .then(() => window.toast?.('Análise técnica enfileirada'))
          .catch(error => window.toast?.(error?.message || 'Falha ao analisar'))
          .finally(() => { analyze.disabled = false; });
        return;
      }
      const task = event.target instanceof Element ? event.target.closest('[data-mobile-project-task]') : null;
      if (task) {
        event.preventDefault();
        const projectId = task.dataset.mobileProjectTask || '';
        if (typeof window.devpilotOpenTaskModal === 'function') return window.devpilotOpenTaskModal({projectId, source:'project'});
        Promise.resolve(window.__devpilotLoadFeature?.('taskModal')).then(() => window.devpilotOpenTaskModal?.({projectId, source:'project'}));
      }
    }, true);

    document.addEventListener('devpilot:authenticated-core-ready', () => {
      try {
        window.loadProjects = mobileLoadProjects;
        loadProjects = mobileLoadProjects;
      } catch (_) {}
      if (/^#\/?projects\b/.test(location.hash || '')) showProjectsSafe();
    }, {once:true});
  }

  installMobileProjectCircuitBreaker();

  if (document.getElementById('acs-homolog-loader')) return;

  const stylesheetId = 'acs-homolog-loader-css';
  if (!document.getElementById(stylesheetId)) {
    const link = document.createElement('link');
    link.id = stylesheetId;
    link.rel = 'stylesheet';
    link.href = '/assets/acs-loader.css?v=20260825-deterministic1';
    document.head.appendChild(link);
  }

  const loader = document.createElement('div');
  loader.id = 'acs-homolog-loader';
  loader.className = 'acs-loader';
  loader.setAttribute('role', 'status');
  loader.setAttribute('aria-live', 'polite');
  loader.setAttribute('aria-label', 'Carregando ACS');
  loader.style.pointerEvents = 'none';
  loader.innerHTML = `
    <main class="acs-loader__content">
      <div class="acs-loader__logo-stage" aria-hidden="true">
        <div class="acs-loader__logo-halo"></div>
        <img class="acs-loader__logo" src="/assets/logo-acastilho.svg" alt="">
      </div>
      <div class="acs-loader__brand-block">
        <div class="acs-loader__brand">ACS</div>
        <div class="acs-loader__tagline">Software · Produto · IA</div>
      </div>
      <div class="acs-loader__progress-wrap" aria-hidden="true">
        <div class="acs-loader__progress-track">
          <span class="acs-loader__progress-fill"></span>
        </div>
      </div>
      <div class="acs-loader__status" aria-hidden="true"><span>Inicializando experiência</span></div>
    </main>`;

  document.body.prepend(loader);

  let removed = false;
  let leaving = false;
  const removeNow = () => { if (!removed) { removed = true; loader.remove(); } };
  const dismiss = () => {
    if (removed || leaving) return;
    leaving = true;
    loader.classList.add('acs-loader--leaving');
    window.setTimeout(removeNow, 220);
  };

  document.addEventListener('devpilot:authenticated-core-ready', dismiss, {once:true});
  window.setTimeout(dismiss, 650);
  window.setTimeout(removeNow, 1200);
})();
