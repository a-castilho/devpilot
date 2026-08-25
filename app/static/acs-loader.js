(() => {
  if (document.getElementById('acs-homolog-loader')) return;

  const stylesheetId = 'acs-homolog-loader-css';
  if (!document.getElementById(stylesheetId)) {
    const link = document.createElement('link');
    link.id = stylesheetId;
    link.rel = 'stylesheet';
    link.href = '/assets/acs-loader.css?v=20260825-safe2';
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
    </main>
  `;

  document.body.prepend(loader);

  let leaving = false;
  let removed = false;

  const removeNow = () => {
    if (removed) return;
    removed = true;
    loader.remove();
  };

  const dismiss = () => {
    if (leaving || removed) return;
    leaving = true;
    loader.classList.add('acs-loader--leaving');
    window.setTimeout(removeNow, 280);
  };

  // O loader é somente visual. Ele jamais deve bloquear login, navegação ou
  // aguardar a inicialização dos módulos pesados para desaparecer.
  document.addEventListener('devpilot:authenticated-core-ready', dismiss, {once: true});
  window.setTimeout(dismiss, 700);
  window.setTimeout(removeNow, 1400);
})();
