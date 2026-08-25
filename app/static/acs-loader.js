(() => {
  if (document.getElementById('acs-homolog-loader')) return;

  const stylesheetId = 'acs-homolog-loader-css';
  if (!document.getElementById(stylesheetId)) {
    const link = document.createElement('link');
    link.id = stylesheetId;
    link.rel = 'stylesheet';
    link.href = '/assets/acs-loader.css?v=20260824-2';
    document.head.appendChild(link);
  }

  const previousOverflow = document.body.style.overflow;
  document.body.style.overflow = 'hidden';

  const loader = document.createElement('div');
  loader.id = 'acs-homolog-loader';
  loader.className = 'acs-loader';
  loader.setAttribute('role', 'status');
  loader.setAttribute('aria-live', 'polite');
  loader.setAttribute('aria-label', 'Carregando ACS');
  loader.innerHTML = `
    <div class="acs-loader__grid" aria-hidden="true"></div>
    <div class="acs-loader__aurora acs-loader__aurora--one" aria-hidden="true"></div>
    <div class="acs-loader__aurora acs-loader__aurora--two" aria-hidden="true"></div>
    <div class="acs-loader__scan" aria-hidden="true"></div>
    <div class="acs-loader__particles" aria-hidden="true">${Array.from({ length: 12 }, () => '<span></span>').join('')}</div>
    <div class="acs-loader__corner acs-loader__corner--tl" aria-hidden="true"></div>
    <div class="acs-loader__corner acs-loader__corner--tr" aria-hidden="true"></div>
    <div class="acs-loader__corner acs-loader__corner--bl" aria-hidden="true"></div>
    <div class="acs-loader__corner acs-loader__corner--br" aria-hidden="true"></div>
    <main class="acs-loader__content">
      <div class="acs-loader__logo-stage" aria-hidden="true">
        <div class="acs-loader__orbit acs-loader__orbit--outer"></div>
        <div class="acs-loader__orbit acs-loader__orbit--middle"></div>
        <div class="acs-loader__orbit acs-loader__orbit--inner"></div>
        <div class="acs-loader__logo-halo"></div>
        <img class="acs-loader__logo" src="/assets/logo-acastilho.svg" alt="">
        <span class="acs-loader__satellite acs-loader__satellite--one"></span>
        <span class="acs-loader__satellite acs-loader__satellite--two"></span>
        <span class="acs-loader__satellite acs-loader__satellite--three"></span>
      </div>
      <div class="acs-loader__brand-block">
        <div class="acs-loader__brand">ACS</div>
        <div class="acs-loader__tagline">Software · Produto · IA</div>
      </div>
      <div class="acs-loader__progress-wrap" aria-hidden="true">
        <div class="acs-loader__progress-track">
          <span class="acs-loader__progress-fill"></span>
          <span class="acs-loader__progress-spark"></span>
        </div>
      </div>
      <div class="acs-loader__status" aria-hidden="true">
        <span>Inicializando experiência</span>
        <span>Conectando serviços</span>
        <span>Preparando ACS</span>
      </div>
    </main>
    <div class="acs-loader__footer" aria-hidden="true">
      <span class="acs-loader__footer-dot"></span>
      <span>Construindo tecnologia para problemas reais</span>
    </div>
  `;

  document.body.prepend(loader);

  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    loader.classList.add('acs-loader--leaving');
    window.setTimeout(() => {
      loader.remove();
      document.body.style.overflow = previousOverflow;
    }, 450);
  };

  // O splash é visual, nunca um gate da aplicação. Mesmo que API, CSS,
  // imagem ou outro serviço demore/falhe, a interface deve ser liberada.
  window.setTimeout(finish, 1400);
  window.setTimeout(() => {
    if (document.getElementById('acs-homolog-loader')) {
      loader.remove();
      document.body.style.overflow = previousOverflow;
    }
  }, 3000);

  window.addEventListener('pageshow', (event) => {
    if (event.persisted) finish();
  }, { once: true });
})();
