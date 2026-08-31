(() => {
  'use strict';
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
        <div class="acs-loader__progress-track"><span class="acs-loader__progress-fill"></span></div>
      </div>
      <div class="acs-loader__status" aria-hidden="true"><span>Inicializando experiência</span></div>
    </main>`;
  document.body.prepend(loader);

  let removed = false;
  let leaving = false;
  let projectsRuntimePromise = null;

  const scriptName = src => {
    try { return new URL(src, location.href).pathname.split('/').pop() || ''; }
    catch (_) { return ''; }
  };

  const loadRuntimeScript = name => new Promise(resolve => {
    const existing = Array.from(document.scripts).find(script => scriptName(script.src) === name);
    if (existing) {
      if (existing.dataset.devpilotProjectsRuntimeState === 'loading') {
        existing.addEventListener('load', () => resolve(true), {once: true});
        existing.addEventListener('error', () => resolve(false), {once: true});
      } else resolve(true);
      return;
    }
    const script = document.createElement('script');
    script.src = `/assets/${encodeURIComponent(name)}?v=1.1.4-projects-runtime`;
    script.async = false;
    script.dataset.devpilotProjectsRuntime = '1';
    script.dataset.devpilotProjectsRuntimeState = 'loading';
    script.onload = () => { script.dataset.devpilotProjectsRuntimeState = 'loaded'; resolve(true); };
    script.onerror = () => { script.dataset.devpilotProjectsRuntimeState = 'failed'; resolve(false); };
    document.body.appendChild(script);
  });

  const ensureProjectsRuntime = () => {
    if (projectsRuntimePromise) return projectsRuntimePromise;
    projectsRuntimePromise = (async () => {
      const ships = await loadRuntimeScript('project-ships.js');
      const compact = await loadRuntimeScript('mobile-project-card-compact.js');
      const ready = ships && compact;
      document.dispatchEvent(new CustomEvent('devpilot:projects-runtime-ready', {detail: {ready}}));
      return ready;
    })();
    return projectsRuntimePromise;
  };

  const projectsVisible = () => {
    const view = document.querySelector('#projects-view');
    return Boolean(view && !view.hidden && getComputedStyle(view).display !== 'none');
  };

  document.addEventListener('click', event => {
    if (event.target.closest?.('.nav[data-view="projects"], [data-view="projects"], [data-mobile-view="projects"]')) {
      void ensureProjectsRuntime();
    }
  }, true);

  document.addEventListener('devpilot:authenticated-core-ready', () => {
    if (projectsVisible()) void ensureProjectsRuntime();
  });

  const removeNow = () => { if (!removed) { removed = true; loader.remove(); } };
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
