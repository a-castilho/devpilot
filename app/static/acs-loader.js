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
    link.href = '/assets/acs-loader.css?v=20260913-render-gate2';
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
      <div class="acs-loader__status">
        <span>Inicializando experiência</span>
      </div>
    </main>`;

  document.body.prepend(loader);

  let removed = false;
  let leaving = false;
  let coreReady = false;
  const requiresBackendGate = /\.vercel\.app$/i.test(window.location.hostname);
  let backendReady = !requiresBackendGate;
  const statusText = loader.querySelector('.acs-loader__status span');

  const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms));

  const removeNow = () => {
    if (removed) return;
    removed = true;
    loader.remove();
  };

  const dismiss = () => {
    if (removed || leaving || !coreReady || !backendReady) return;
    leaving = true;
    if (statusText) statusText.textContent = 'Backend disponível. Abrindo login…';
    loader.classList.add('acs-loader--leaving');
    window.setTimeout(removeNow, 220);
  };

  document.addEventListener('devpilot:authenticated-core-ready', () => {
    coreReady = true;
    dismiss();
  }, {once: true});

  async function fetchReady(url, {expectAuthStatus = false} = {}) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(`${url}${url.includes('?') ? '&' : '?'}_=${Date.now()}`, {
        method: 'GET',
        cache: 'no-store',
        headers: {'Accept': 'application/json,text/plain,*/*'},
        signal: controller.signal,
      });
      if (!response.ok) return false;
      if (!expectAuthStatus) return true;
      const data = await response.json().catch(() => null);
      return Boolean(data && typeof data === 'object' && Object.prototype.hasOwnProperty.call(data, 'bootstrap_required'));
    } catch (_) {
      return false;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  async function checkApplicationReadiness() {
    const healthReady = await fetchReady('/health');
    if (!healthReady) return false;
    return fetchReady('/api/auth/status', {expectAuthStatus: true});
  }

  async function waitForRenderBackend() {
    if (backendReady) return;

    let attempt = 0;
    let consecutiveReady = 0;
    const startedAt = Date.now();
    if (statusText) statusText.textContent = 'Aguardando backend subir na Render…';

    while (!removed && !backendReady) {
      attempt += 1;
      const ready = await checkApplicationReadiness();
      consecutiveReady = ready ? consecutiveReady + 1 : 0;

      if (consecutiveReady >= 2) {
        backendReady = true;
        document.documentElement.dataset.devpilotBackendReady = '1';
        dismiss();
        return;
      }

      const elapsedSeconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
      if (statusText) {
        if (ready) {
          statusText.textContent = 'Confirmando autenticação e banco…';
        } else {
          statusText.textContent = elapsedSeconds < 30
            ? 'Aguardando backend subir na Render…'
            : `Backend ainda iniciando na Render… ${elapsedSeconds}s`;
        }
      }

      await sleep(ready ? 700 : (attempt < 4 ? 1500 : 2500));
    }
  }

  if (requiresBackendGate) {
    document.documentElement.dataset.devpilotBackendReady = '0';
    void waitForRenderBackend();
  }

  window.setTimeout(() => {
    coreReady = true;
    dismiss();
  }, requiresBackendGate ? 500 : 650);

  if (!requiresBackendGate) {
    window.setTimeout(removeNow, 1200);
  }
})();
