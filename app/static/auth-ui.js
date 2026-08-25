(() => {
  'use strict';

  const TOKEN_KEY = 'devpilot-token';
  const modal = document.querySelector('#auth-modal');
  if (!modal) return;

  const root = document.documentElement;
  const SAFE_STYLE_ID = 'devpilot-auth-compositor-safe';
  let bootstrapRequired = false;
  let localBootstrapAvailable = false;
  let resolveAuthReady;
  let runtimeHandoffStarted = false;

  function installCompositorSafeMode() {
    if (!document.getElementById(SAFE_STYLE_ID)) {
      const style = document.createElement('style');
      style.id = SAFE_STYLE_ID;
      style.textContent = `
        dialog::backdrop {
          background: #020811 !important;
          backdrop-filter: none !important;
          -webkit-backdrop-filter: none !important;
        }
        html.devpilot-auth-pending body {
          background: #07111f !important;
          background-image: none !important;
        }
        html.devpilot-auth-pending .shell,
        html.devpilot-auth-pending .voice-dock,
        html.devpilot-auth-pending .toast {
          visibility: hidden !important;
        }
        html.devpilot-auth-pending dialog {
          visibility: visible !important;
          box-shadow: 0 18px 48px rgba(0,0,0,.55) !important;
          transform: none !important;
          animation: none !important;
          transition: none !important;
        }
        html.devpilot-auth-pending *,
        html.devpilot-auth-pending *::before,
        html.devpilot-auth-pending *::after {
          animation-play-state: paused !important;
        }
        @media (max-width: 900px) {
          html.devpilot-auth-pending .sidebar {
            backdrop-filter: none !important;
            -webkit-backdrop-filter: none !important;
          }
        }
      `;
      document.head.appendChild(style);
    }
    root.classList.add('devpilot-auth-pending');
  }

  installCompositorSafeMode();

  window.__devpilotAuthReady = new Promise(resolve => {
    resolveAuthReady = resolve;
  });

  const completeAuth = value => {
    if (typeof resolveAuthReady !== 'function') return;
    const resolve = resolveAuthReady;
    resolveAuthReady = null;
    resolve(Boolean(value));
  };

  const showModal = () => {
    if (!modal.open) modal.showModal();
  };

  const closeModal = () => {
    if (modal.open) modal.close();
  };

  const revealDashboard = () => {
    root.classList.remove('devpilot-auth-pending');
    closeModal();
    window.requestAnimationFrame(() => {
      document.dispatchEvent(new CustomEvent('devpilot:dashboard-revealed'));
    });
  };

  const installLogout = () => {
    const header = document.querySelector('.header-actions');
    if (!header || document.querySelector('#logout')) return;
    const button = document.createElement('button');
    button.id = 'logout';
    button.className = 'ghost';
    button.type = 'button';
    button.textContent = 'Sair';
    button.addEventListener('click', () => {
      localStorage.removeItem(TOKEN_KEY);
      location.reload();
    });
    header.prepend(button);
  };

  function handoffAuthenticatedRuntime(statusElement = null) {
    if (runtimeHandoffStarted) return;
    runtimeHandoffStarted = true;
    installLogout();

    if (statusElement) statusElement.textContent = 'Abrindo ambiente seguro…';

    const finish = () => {
      if (!runtimeHandoffStarted) return;
      runtimeHandoffStarted = false;
      revealDashboard();
    };

    document.addEventListener('devpilot:authenticated-core-ready', finish, {once: true});

    // Caso o evento tenha ocorrido entre a validação e a instalação do listener.
    queueMicrotask(() => {
      if (window.__devpilotBoot?.phase === 'ready') finish();
    });

    completeAuth(true);

    // Falha de asset não pode deixar um modal aparentemente congelado para sempre.
    window.setTimeout(() => {
      if (!root.classList.contains('devpilot-auth-pending')) return;
      if (window.__devpilotBoot?.phase === 'failed') {
        runtimeHandoffStarted = false;
        if (statusElement) statusElement.textContent = 'Falha ao carregar a interface. Atualize a página.';
      }
    }, 8000);
  }

  async function readStatus() {
    try {
      const response = await fetch('/api/auth/status', {cache: 'no-store'});
      const data = await response.json();
      bootstrapRequired = Boolean(data.bootstrap_required);
      localBootstrapAvailable = Boolean(data.local_bootstrap_available);
    } catch (_) {
      bootstrapRequired = false;
      localBootstrapAvailable = false;
    }
  }

  async function validateToken(token) {
    if (!token) return false;
    try {
      const response = await fetch('/api/auth/me', {
        headers: {Authorization: `Bearer ${token}`},
        cache: 'no-store',
      });
      if (response.ok) return true;
      if ([401, 403, 404].includes(response.status)) localStorage.removeItem(TOKEN_KEY);
    } catch (_) {}
    return false;
  }

  function renderLoginForm(message = '') {
    installCompositorSafeMode();
    runtimeHandoffStarted = false;
    modal.innerHTML = `
      <form class="modal" id="auth-form">
        <span class="eyebrow">ACESSO</span>
        <h2>Entrar no DevPilot</h2>
        <p id="auth-help">Use seu e-mail e senha.</p>
        <label>E-mail<input id="auth-email" type="email" autocomplete="username" required></label>
        <label>Senha<input id="auth-password" type="password" autocomplete="current-password" minlength="8" required></label>
        <label id="auth-bootstrap-row" style="display:none">Token de bootstrap<input id="auth-bootstrap" type="password" autocomplete="off"></label>
        <div id="auth-error" class="hint" role="alert"></div>
        <button class="primary" id="auth-submit" type="submit">Entrar</button>
      </form>`;

    const form = document.querySelector('#auth-form');
    const errorBox = document.querySelector('#auth-error');
    const submit = document.querySelector('#auth-submit');
    const bootstrapRow = document.querySelector('#auth-bootstrap-row');
    const help = document.querySelector('#auth-help');

    if (errorBox && message) errorBox.textContent = message;
    if (bootstrapRow) bootstrapRow.style.display = bootstrapRequired && !localBootstrapAvailable ? 'grid' : 'none';
    if (help) {
      help.textContent = bootstrapRequired
        ? (localBootstrapAvailable
          ? 'Primeiro acesso neste Linux: informe e-mail e senha.'
          : 'Primeiro acesso remoto: informe também o token de bootstrap.')
        : 'Use seu e-mail e senha.';
    }
    if (submit) submit.textContent = bootstrapRequired ? 'Criar Super Admin e entrar' : 'Entrar';

    form?.addEventListener('submit', async event => {
      event.preventDefault();
      if (!errorBox || !submit) return;
      errorBox.textContent = '';
      submit.disabled = true;
      submit.textContent = 'Validando…';

      const payload = {
        email: document.querySelector('#auth-email')?.value.trim() || '',
        password: document.querySelector('#auth-password')?.value || '',
      };
      const headers = {'Content-Type': 'application/json'};
      let endpoint = '/api/auth/login';

      if (bootstrapRequired) {
        endpoint = '/api/auth/bootstrap';
        if (!localBootstrapAvailable) {
          const bootstrapToken = document.querySelector('#auth-bootstrap')?.value.trim() || '';
          if (!bootstrapToken) {
            errorBox.textContent = 'Informe o token de bootstrap.';
            submit.disabled = false;
            submit.textContent = 'Entrar';
            return;
          }
          headers.Authorization = `Bearer ${bootstrapToken}`;
        }
      }

      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers,
          body: JSON.stringify(payload),
          cache: 'no-store',
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.access_token) {
          throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha na autenticação');
        }

        localStorage.setItem(TOKEN_KEY, data.access_token);
        document.dispatchEvent(new CustomEvent('devpilot:login-complete'));
        handoffAuthenticatedRuntime(errorBox);
      } catch (error) {
        errorBox.textContent = error.message || 'Falha na autenticação';
        submit.disabled = false;
        submit.textContent = bootstrapRequired ? 'Criar Super Admin e entrar' : 'Entrar';
      }
    });

    showModal();
  }

  function renderResumeSession(token) {
    installCompositorSafeMode();
    runtimeHandoffStarted = false;
    modal.innerHTML = `
      <div class="modal" id="auth-resume">
        <span class="eyebrow">SESSÃO SALVA</span>
        <h2>Continuar no DevPilot?</h2>
        <p>Existe uma sessão anterior neste navegador. O dashboard só será iniciado depois da sua confirmação.</p>
        <div id="auth-resume-error" class="hint" role="alert"></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap">
          <button class="primary" id="auth-resume-submit" type="button">Continuar sessão</button>
          <button class="ghost" id="auth-other-account" type="button">Entrar com outra conta</button>
        </div>
      </div>`;
    showModal();

    const resume = document.querySelector('#auth-resume-submit');
    const other = document.querySelector('#auth-other-account');
    const errorBox = document.querySelector('#auth-resume-error');

    resume?.addEventListener('click', async () => {
      resume.disabled = true;
      resume.textContent = 'Validando…';
      const valid = await validateToken(token);
      if (!valid) {
        localStorage.removeItem(TOKEN_KEY);
        renderLoginForm('A sessão não é mais válida. Entre novamente.');
        return;
      }
      handoffAuthenticatedRuntime(errorBox);
    });

    other?.addEventListener('click', () => {
      localStorage.removeItem(TOKEN_KEY);
      renderLoginForm();
    });
  }

  const boot = async () => {
    await readStatus();
    const token = String(localStorage.getItem(TOKEN_KEY) || '').trim();
    if (!token) {
      renderLoginForm();
      return;
    }
    renderResumeSession(token);
  };

  void boot();
})();