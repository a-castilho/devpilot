(() => {
  if (document.getElementById('acs-homolog-loader')) return;

  /*
   * Compatibilidade instalada ANTES de auth-ui/app.js.
   * O pós-login precisa permanecer mínimo: qualquer módulo opcional executado
   * automaticamente pode bloquear a thread principal em máquinas pequenas.
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

  /*
   * Circuit breaker definitivo do boot autenticado.
   *
   * O scheduler legado continua conhecendo dezenas de arquivos. Em vez de deixar
   * cada módulo decidir se deve ou não iniciar, aceitamos automaticamente apenas
   * o núcleo comprovadamente necessário para a aplicação básica. Todo script com
   * data-devpilot-progressive fora desta allowlist é marcado como suprimido e tem
   * seu onload concluído de forma assíncrona para que o scheduler não fique preso.
   *
   * Cargas explícitas feitas por uma funcionalidade NÃO usam este marcador e não
   * são bloqueadas. Portanto esta proteção não impede evolução sob demanda; ela
   * apenas proíbe trabalho pesado durante login/boot.
   */
  const SAFE_AUTH_BOOT_SCRIPTS = new Set([
    'app.js',
    'profile.js',
    'users.js',
  ]);

  const scriptName = node => {
    if (!(node instanceof HTMLScriptElement) || !node.src) return '';
    try {
      return new URL(node.src, location.href).pathname.split('/').pop() || '';
    } catch (_) {
      return '';
    }
  };

  const installAuthenticatedBootCircuitBreaker = () => {
    const body = document.body;
    if (!body || body.dataset.devpilotMinimalBoot === '1') return;
    body.dataset.devpilotMinimalBoot = '1';

    const nativeAppendChild = body.appendChild;
    const appendNormally = node => nativeAppendChild.call(body, node);
    window.__devpilotNativeBodyAppend = appendNormally;
    window.__devpilotSafeAuthBootScripts = [...SAFE_AUTH_BOOT_SCRIPTS];

    body.appendChild = function devpilotMinimalBootAppend(node) {
      const automaticRuntimeScript = node instanceof HTMLScriptElement
        && node.dataset.devpilotProgressive === '1';

      if (!automaticRuntimeScript) return nativeAppendChild.call(this, node);

      const name = scriptName(node);
      if (SAFE_AUTH_BOOT_SCRIPTS.has(name)) return nativeAppendChild.call(this, node);

      const boot = window.__devpilotBoot = window.__devpilotBoot || {};
      boot.suppressed = Array.isArray(boot.suppressed) ? boot.suppressed : [];
      if (name && !boot.suppressed.includes(name)) boot.suppressed.push(name);
      node.dataset.devpilotSuppressed = '1';

      queueMicrotask(() => {
        try {
          if (typeof node.onload === 'function') node.onload(new Event('load'));
        } catch (error) {
          console.error('[DevPilot] Falha ao concluir módulo suprimido', name, error);
        }
      });
      return node;
    };
  };

  installAuthenticatedBootCircuitBreaker();

  // auth-ui é defer e troca o conteúdo de #auth-modal antes do núcleo autenticado.
  document.addEventListener('DOMContentLoaded', ensureLegacyAuthAnchors, {once: true});

  /*
   * Proteção adicional contra observers autorreferentes do menu legado.
   * Mantemos somente observers que não vigiam atributos do nav principal.
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
    link.href = '/assets/acs-loader.css?v=20260825-minimalboot1';
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

  // O loader é somente visual e nunca pode bloquear entrada ou navegação.
  document.addEventListener('devpilot:authenticated-core-ready', dismiss, {once: true});
  window.setTimeout(dismiss, 700);
  window.setTimeout(removeNow, 1400);
})();
