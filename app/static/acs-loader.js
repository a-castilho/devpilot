(() => {
  if (document.getElementById('acs-homolog-loader')) return;

  /*
   * Compatibilidade instalada ANTES de auth-ui/app.js/workspace-skins.js.
   *
   * 1) document.scripts é HTMLCollection em Chromium e não implementa forEach.
   *    Alguns módulos antigos tratavam a coleção como Array e abortavam o boot.
   * 2) auth-ui substitui o conteúdo do modal legado e remove #token/#save-token,
   *    enquanto app.js ainda tenta registrar onclick nesses ids. Criamos âncoras
   *    inertes fora do modal para que o runtime legado não quebre durante a
   *    migração para o fluxo autenticado atual.
   */
  if (window.HTMLCollection && !HTMLCollection.prototype.forEach) {
    Object.defineProperty(HTMLCollection.prototype, 'forEach', {
      configurable: true,
      writable: true,
      value: Array.prototype.forEach,
    });
  }

  const ensureLegacyAuthAnchors = () => {
    if (!document.getElementById('token')) {
      const token = document.createElement('input');
      token.id = 'token';
      token.type = 'hidden';
      token.hidden = true;
      token.tabIndex = -1;
      token.value = localStorage.getItem('devpilot-token') || '';
      token.dataset.devpilotLegacyAuthAnchor = '1';
      document.body.appendChild(token);
    }
    if (!document.getElementById('save-token')) {
      const save = document.createElement('button');
      save.id = 'save-token';
      save.type = 'button';
      save.hidden = true;
      save.tabIndex = -1;
      save.dataset.devpilotLegacyAuthAnchor = '1';
      document.body.appendChild(save);
    }
  };

  // auth-ui é defer e troca o conteúdo de #auth-modal antes do núcleo autenticado.
  // DOMContentLoaded ocorre antes de app.js ser carregado pelo scheduler assíncrono.
  document.addEventListener('DOMContentLoaded', ensureLegacyAuthAnchors, {once: true});

  /*
   * Proteção de runtime instalada antes de app.js/simplified-nav.js.
   * O menu possuía observers de atributos que reagiam a alterações de class/hidden
   * feitas pela própria sincronização do menu. Em Chromium/Brave isso pode manter
   * uma fila contínua de microtasks e produzir "Page Unresponsive".
   *
   * Bloqueamos somente observers de ATRIBUTOS cujo alvo seja o <nav> principal.
   * Observers de conteúdo usados por outros componentes continuam intactos.
   */
  if (!window.__devpilotNativeMutationObserver && window.MutationObserver) {
    const NativeMutationObserver = window.MutationObserver;
    window.__devpilotNativeMutationObserver = NativeMutationObserver;

    class DevPilotSafeMutationObserver extends NativeMutationObserver {
      observe(target, options = {}) {
        const isSidebarNav = target instanceof Element
          && target.matches('.sidebar > nav, .sidebar nav');
        const watchesAttributes = Boolean(options && options.attributes);

        if (isSidebarNav && watchesAttributes) {
          window.__devpilotBlockedSidebarObservers = Number(window.__devpilotBlockedSidebarObservers || 0) + 1;
          return;
        }
        return super.observe(target, options);
      }
    }

    window.MutationObserver = DevPilotSafeMutationObserver;
  }

  const stylesheetId = 'acs-homolog-loader-css';
  if (!document.getElementById(stylesheetId)) {
    const link = document.createElement('link');
    link.id = stylesheetId;
    link.rel = 'stylesheet';
    link.href = '/assets/acs-loader.css?v=20260825-safe4';
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
