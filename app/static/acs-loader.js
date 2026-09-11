(() => {
  'use strict';

  const GAME_FALLBACK_PATHS = new Set(['/game', '/game/', '/game/index.html']);
  if (GAME_FALLBACK_PATHS.has(window.location.pathname)) {
    const target = `/assets/game/index.html${window.location.search || ''}${window.location.hash || ''}`;
    window.location.replace(target);
    return;
  }

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
    link.href = '/assets/acs-loader.css?v=20260911-vercel-ready1';
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
  let coreReady = false;
  let platformReady = !/\.vercel\.app$/i.test(window.location.hostname);
  const statusText = loader.querySelector('.acs-loader__status span');

  const removeNow = () => {
    if (removed) return;
    removed = true;
    loader.remove();
  };

  const dismiss = () => {
    if (removed || leaving || !coreReady || !platformReady) return;
    leaving = true;
    loader.classList.add('acs-loader--leaving');
    window.setTimeout(removeNow, 220);
  };

  document.addEventListener('devpilot:authenticated-core-ready', () => {
    coreReady = true;
    dismiss();
  }, {once: true});

  async function waitForVercelReadiness() {
    if (platformReady) return;
    const started = Date.now();
    const timeoutMs = 90000;
    const pollMs = 2000;
    if (statusText) statusText.textContent = 'Aguardando publicação na Vercel';

    while (!removed && Date.now() - started < timeoutMs) {
      try {
        const response = await fetch(`/health?_=${Date.now()}`, {
          method: 'GET',
          cache: 'no-store',
          headers: {'Accept': 'application/json,text/plain,*/*'},
        });
        if (response.ok) {
          platformReady = true;
          if (statusText) statusText.textContent = 'Aplicação pronta';
          dismiss();
          return;
        }
      } catch (_) {
        // Vercel/Render can still be warming up. Retry until the bounded timeout.
      }
      await new Promise(resolve => window.setTimeout(resolve, pollMs));
    }

    // Never trap the user indefinitely if a project does not expose /health.
    platformReady = true;
    if (statusText) statusText.textContent = 'Abrindo aplicação';
    dismiss();
  }

  void waitForVercelReadiness();

  // Local/Render loads keep the fast path; Vercel loads stay visible while the
  // deployment/backend readiness check is still warming up.
  window.setTimeout(() => {
    coreReady = true;
    dismiss();
  }, platformReady ? 650 : 1200);
  window.setTimeout(() => {
    if (!/\.vercel\.app$/i.test(window.location.hostname)) removeNow();
  }, 1200);
})();
