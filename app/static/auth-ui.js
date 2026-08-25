(() => {
  const TOKEN_KEY = 'devpilot-token';
  const modal = document.querySelector('#auth-modal');
  if (!modal) return;

  // Compatibilidade para o renderer legado de tarefas em app.js: ele usa o helper
  // de elemento unico para '.approve' e em seguida chama forEach. Para esse seletor
  // especifico, devolvemos a colecao correspondente; todos os demais seletores
  // preservam o comportamento nativo de querySelector.
  const nativeQuerySelector = document.querySelector.bind(document);
  document.querySelector = selector => (
    selector === '.approve'
      ? document.querySelectorAll(selector)
      : nativeQuerySelector(selector)
  );

  let bootstrapRequired = false;
  let localBootstrapAvailable = false;
  let taskNavigationInFlight = false;

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

  const errorBox = document.querySelector('#auth-error');
  const submit = document.querySelector('#auth-submit');
  const bootstrapRow = document.querySelector('#auth-bootstrap-row');

  const openLogin = (message = '') => {
    if (message) errorBox.textContent = message;
    if (!modal.open) modal.showModal();
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
      location.reload();
    };
    header.prepend(logout);
  };

  async function validateStoredSession() {
    const token = String(localStorage.getItem(TOKEN_KEY) || '').trim();
    if (!token) {
      openLogin();
      return false;
    }

    try {
      const response = await fetch('/api/auth/me', {
        headers: {Authorization: `Bearer ${token}`},
        cache: 'no-store',
      });
      if (response.ok) {
        installLogout();
        return true;
      }

      if (response.status === 401 || response.status === 403 || response.status === 404) {
        localStorage.removeItem(TOKEN_KEY);
        openLogin('Sua sessão expirou. Entre novamente.');
        return false;
      }

      openLogin('Não foi possível validar sua sessão agora.');
      return false;
    } catch (_) {
      openLogin('Não foi possível validar sua sessão agora.');
      return false;
    }
  }

  // O bootstrap autenticado aguarda esta Promise. Assim, um token antigo nunca
  // dispara app.js, chat, voz ou outros módulos pesados enquanto o login está aberto.
  window.__devpilotAuthReady = validateStoredSession();

  const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms));

  async function waitForTaskRuntime() {
    for (let attempt = 0; attempt < 40; attempt += 1) {
      if (typeof loadAllTasks === 'function' && typeof renderTasks === 'function' && typeof showView === 'function') {
        return true;
      }
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

  // app.js abre Desenvolvimento chamando loadAllTasks() imediatamente. O limitador
  // precisa existir ANTES desse onclick; por isso este gate roda em capture phase.
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
        if (typeof window.__devpilotLoadFeature === 'function') {
          await window.__devpilotLoadFeature('tasks');
        }
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
      const needsManualToken = bootstrapRequired && !localBootstrapAvailable;
      bootstrapRow.style.display = needsManualToken ? 'grid' : 'none';
      document.querySelector('#auth-help').textContent = bootstrapRequired
        ? (localBootstrapAvailable
          ? 'Primeiro acesso neste Linux: informe e-mail e senha. O DevPilot criará o Super Admin sem exigir token manual.'
          : 'Primeiro acesso remoto: por segurança, conclua no próprio Linux ou informe o token de bootstrap.')
        : 'Use seu e-mail e senha.';
      submit.textContent = bootstrapRequired ? 'Criar Super Admin e entrar' : 'Entrar';
    } catch (_) {
      errorBox.textContent = 'Não foi possível consultar o estado da autenticação.';
    }
  }

  document.querySelector('#auth-form').addEventListener('submit', async event => {
    event.preventDefault();
    errorBox.textContent = '';
    submit.disabled = true;

    const payload = {
      email: document.querySelector('#auth-email').value.trim(),
      password: document.querySelector('#auth-password').value,
    };
    const headers = {'Content-Type': 'application/json'};
    let endpoint = '/api/auth/login';

    if (bootstrapRequired) {
      endpoint = '/api/auth/bootstrap';
      if (!localBootstrapAvailable) {
        const bootstrapToken = document.querySelector('#auth-bootstrap').value.trim();
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
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha na autenticação');
      }
      localStorage.setItem(TOKEN_KEY, data.access_token);
      location.reload();
    } catch (error) {
      errorBox.textContent = error.message;
      submit.disabled = false;
    }
  });

  readStatus();
})();
