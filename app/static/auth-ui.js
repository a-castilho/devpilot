(() => {
  'use strict';

  const TOKEN_KEY = 'devpilot-token';
  const EXPLICIT_LOGIN_KEY = 'devpilot-explicit-login';
  const modal = document.querySelector('#auth-modal');
  if (!modal) return;

  let bootstrapRequired = false;
  let localBootstrapAvailable = false;
  let taskNavigationInFlight = false;
  let resolveAuthReady;

  window.__devpilotAuthReady = new Promise(resolve => {
    resolveAuthReady = resolve;
  });

  const completeAuth = value => {
    if (typeof resolveAuthReady !== 'function') return;
    const resolver = resolveAuthReady;
    resolveAuthReady = null;
    resolver(Boolean(value));
  };

  const installLogout = () => {
    const header = document.querySelector('.header-actions');
    if (!header || document.querySelector('#logout')) return;
    const logout = document.createElement('button');
    logout.id = 'logout';
    logout.className = 'ghost';
    logout.textContent = 'Sair';
    logout.onclick = () => {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(EXPLICIT_LOGIN_KEY);
      location.reload();
    };
    header.prepend(logout);
  };

  const showModal = () => {
    if (!modal.open) modal.showModal();
  };

  const renderLoginForm = () => {
    modal.innerHTML = `
      <form class="modal" id="auth-form">
        <span class="eyebrow">ACESSO</span><h2>Entrar no DevPilot</h2>
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

    form?.addEventListener('submit', async event => {
      event.preventDefault();
      if (!errorBox || !submit) return;
      errorBox.textContent = '';
      submit.disabled = true;

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
            errorBox.textContent = 'Informe o token de bootstrap ou faça o primeiro acesso diretamente no Linux.';
            submit.disabled = false;
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
        if (!response.ok) {
          throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha na autenticação');
        }
        localStorage.setItem(TOKEN_KEY, data.access_token);
        sessionStorage.setItem(EXPLICIT_LOGIN_KEY, '1');
        location.reload();
      } catch (error) {
        errorBox.textContent = error.message || 'Falha na autenticação';
        submit.disabled = false;
      }
    });

    if (bootstrapRow) bootstrapRow.style.display = bootstrapRequired && !localBootstrapAvailable ? 'grid' : 'none';
    const help = document.querySelector('#auth-help');
    if (help) {
      help.textContent = bootstrapRequired
        ? (localBootstrapAvailable
          ? 'Primeiro acesso neste Linux: informe e-mail e senha. O DevPilot criará o Super Admin sem exigir token manual.'
          : 'Primeiro acesso remoto: conclua no próprio Linux ou informe o token de bootstrap.')
        : 'Use seu e-mail e senha.';
    }
    if (submit) submit.textContent = bootstrapRequired ? 'Criar Super Admin e entrar' : 'Entrar';
    showModal();
  };

  const validateToken = async token => {
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
  };

  const renderResumeSession = token => {
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
        if (errorBox) errorBox.textContent = 'A sessão não é mais válida. Entre novamente.';
        localStorage.removeItem(TOKEN_KEY);
        window.setTimeout(renderLoginForm, 150);
        return;
      }
      installLogout();
      modal.close();
      completeAuth(true);
    });

    other?.addEventListener('click', () => {
      localStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(EXPLICIT_LOGIN_KEY);
      renderLoginForm();
    });
  };

  const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms));

  async function waitForTaskRuntime() {
    for (let attempt = 0; attempt < 40; attempt += 1) {
      if (typeof loadAllTasks === 'function' && typeof renderTasks === 'function' && typeof showView === 'function') return true;
      await sleep(50);
    }
    return false;
  }

  async function ensureTaskLimiter() {
    if (!(await waitForTaskRuntime())) return false;
    if (document.querySelector('script[data-devpilot-task-limiter="1"]')) return true;

    const existing = [...document.scripts].find(script => {
      if (!script.src) return false;
      try { return new URL(script.src, location.href).pathname === '/assets/tasks-lazy-load.js'; }
      catch (_) { return false; }
    });
    if (existing) return true;

    return new Promise(resolve => {
      const script = document.createElement('script');
      script.src = `/assets/tasks-lazy-load.js?v=safe-task-navigation-${Date.now()}`;
      script.async = false;
      script.dataset.devpilotTaskLimiter = '1';
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.body.appendChild(script);
    });
  }

  document.addEventListener('click', event => {
    const nav = event.target.closest?.('.nav[data-view="tasks"]');
    if (!nav || taskNavigationInFlight) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    taskNavigationInFlight = true;

    void (async () => {
      try {
        const limited = await ensureTaskLimiter();
        if (!limited) {
          console.error('[DevPilot] Não foi possível instalar o limitador da lista de tarefas.');
          return;
        }
        if (typeof window.__devpilotLoadFeature === 'function') await window.__devpilotLoadFeature('tasks');
        if (typeof showView === 'function') showView('tasks');
      } finally {
        taskNavigationInFlight = false;
      }
    })();
  }, true);

  async function readStatus() {
    try {
      const response = await fetch('/api/auth/status', {cache: 'no-store'});
      const data = await response.json();
      bootstrapRequired = Boolean(data.bootstrap_required);
      localBootstrapAvailable = Boolean(data.local_bootstrap_available);
    } catch (_) {}
  }

  const boot = async () => {
    await readStatus();
    const token = String(localStorage.getItem(TOKEN_KEY) || '').trim();
    if (!token) {
      renderLoginForm();
      completeAuth(false);
      return;
    }

    const explicitLogin = sessionStorage.getItem(EXPLICIT_LOGIN_KEY) === '1';
    if (explicitLogin) {
      sessionStorage.removeItem(EXPLICIT_LOGIN_KEY);
      const valid = await validateToken(token);
      if (valid) {
        installLogout();
        if (modal.open) modal.close();
        completeAuth(true);
        return;
      }
      localStorage.removeItem(TOKEN_KEY);
      renderLoginForm();
      completeAuth(false);
      return;
    }

    renderResumeSession(token);
  };

  void boot();
})();