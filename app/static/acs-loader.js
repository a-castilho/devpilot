(() => {
  'use strict';

  const TOKEN_KEY = 'devpilot-token';

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
      <div class="acs-loader__status" aria-hidden="true">
        <span>Inicializando experiência</span>
      </div>
    </main>`;

  document.body.prepend(loader);

  let removed = false;
  let leaving = false;

  const removeNow = () => {
    if (removed) return;
    removed = true;
    loader.remove();
  };

  const dismiss = () => {
    if (removed || leaving) return;
    leaving = true;
    loader.classList.add('acs-loader--leaving');
    window.setTimeout(removeNow, 220);
  };

  document.addEventListener('devpilot:authenticated-core-ready', dismiss, {once: true});
  window.setTimeout(dismiss, 650);
  window.setTimeout(removeNow, 1200);
})();

/*
 * Recuperação determinística do frontend V37.
 * O HTML autenticado remove scripts pesados do boot e o feature-loader os
 * carrega sob demanda. Em rotas mobile, a tela de Projetos podia ficar ativa
 * sem disparar o gatilho da sidebar; nesse cenário as naves e o layout compacto
 * existiam no repositório, mas nunca eram carregados.
 */
(() => {
  'use strict';

  if (window.__devpilotFrontendRecoveryV37) return;
  window.__devpilotFrontendRecoveryV37 = true;

  const REVISION = 'frontend-v37-recovery-20260831';
  const PROJECT_STYLES = ['layout-projects-v6.css', 'layout-authority-v37.css'];
  const PROJECT_SCRIPTS = ['mobile-project-card-compact.js', 'project-ships.js'];
  let recoveryPromise = null;

  const assetName = value => {
    try { return new URL(value, location.href).pathname.split('/').pop() || ''; }
    catch (_) { return ''; }
  };

  function ensureStyle(name) {
    const existing = Array.from(document.querySelectorAll('link[rel="stylesheet"]'))
      .some(link => assetName(link.href) === name);
    if (existing) return;

    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = `/assets/${encodeURIComponent(name)}?v=${REVISION}`;
    link.dataset.devpilotFrontendRecovery = '1';
    document.head.appendChild(link);
  }

  function loadScript(name) {
    const existing = Array.from(document.scripts).find(script => assetName(script.src) === name);
    if (existing) return Promise.resolve(true);

    return new Promise(resolve => {
      const script = document.createElement('script');
      script.src = `/assets/${encodeURIComponent(name)}?v=${REVISION}`;
      script.async = false;
      script.dataset.devpilotFrontendRecovery = '1';
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.body.appendChild(script);
    });
  }

  function projectsViewIsActive() {
    const view = document.querySelector('#projects-view');
    if (!view) return false;
    return view.classList.contains('active') || view.hidden === false || location.hash.includes('projects');
  }

  async function recoverProjectsExperience() {
    if (recoveryPromise) return recoveryPromise;

    recoveryPromise = (async () => {
      PROJECT_STYLES.forEach(ensureStyle);

      if (typeof window.__devpilotLoadFeature === 'function') {
        try {
          await window.__devpilotLoadFeature('projects');
        } catch (_) {}
      }

      for (const name of PROJECT_SCRIPTS) {
        await loadScript(name);
      }

      document.documentElement.dataset.devpilotFrontendRecovery = 'v37-projects';
      document.dispatchEvent(new CustomEvent('devpilot:frontend-recovered', {
        detail: {scope: 'projects', version: 'v37'},
      }));
      return true;
    })().finally(() => {
      recoveryPromise = null;
    });

    return recoveryPromise;
  }

  function recoverIfNeeded() {
    if (projectsViewIsActive()) void recoverProjectsExperience();
  }

  document.addEventListener('devpilot:authenticated-core-ready', () => {
    window.setTimeout(() => void recoverProjectsExperience(), 0);
  });
  document.addEventListener('devpilot:dashboard-revealed', recoverIfNeeded);
  document.addEventListener('devpilot:view-changed', recoverIfNeeded);
  document.addEventListener('devpilot:page-ready', recoverIfNeeded);
  window.addEventListener('hashchange', recoverIfNeeded);

  document.addEventListener('click', event => {
    const projectsTarget = event.target.closest?.('[data-view="projects"], [data-simple-target="projects"]');
    if (projectsTarget) void recoverProjectsExperience();
  }, true);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', recoverIfNeeded, {once: true});
  } else {
    recoverIfNeeded();
  }
})();
