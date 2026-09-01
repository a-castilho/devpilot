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

  // O preauth loader cuida somente do boot visual e da sessão. Navegação,
  // dados e runtime de Projetos pertencem ao page-navigation/feature-loader.
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

  document.addEventListener('devpilot:authenticated-core-ready', dismiss, {once:true});
  window.setTimeout(dismiss, 650);
  window.setTimeout(removeNow, 1200);
})();
