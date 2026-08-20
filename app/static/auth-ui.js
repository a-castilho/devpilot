(() => {
  const modal = document.querySelector('#auth-modal');
  if (!modal) return;
  let bootstrapRequired = false;

  modal.innerHTML = `
    <form class="modal" id="auth-form" novalidate>
      <span class="eyebrow">ACESSO</span><h2>Entrar no DevPilot</h2>
      <p id="auth-help">Use seu e-mail e senha.</p>
      <label>E-mail<input id="auth-email" type="email" autocomplete="username" required></label>
      <label>Senha<input id="auth-password" type="password" autocomplete="current-password" minlength="8" required></label>
      <label id="auth-bootstrap-row" style="display:none">Token de bootstrap<input id="auth-bootstrap" type="password" autocomplete="off"></label>
      <div id="auth-error" class="auth-feedback" role="alert" aria-live="assertive" aria-atomic="true" hidden></div>
      <button class="primary" id="auth-submit" type="submit">Entrar</button>
      <details><summary class="hint">Acesso técnico por token</summary><label>Token<input id="auth-technical-token" type="password" autocomplete="off"></label><button class="ghost" id="auth-token-submit" type="button">Usar token</button></details>
    </form>`;

  const form = document.querySelector('#auth-form');
  const errorBox = document.querySelector('#auth-error');
  const submit = document.querySelector('#auth-submit');
  const emailInput = document.querySelector('#auth-email');
  const passwordInput = document.querySelector('#auth-password');
  const bootstrapInput = document.querySelector('#auth-bootstrap');
  const technicalTokenInput = document.querySelector('#auth-technical-token');
  const allCredentialFields = [emailInput, passwordInput, bootstrapInput, technicalTokenInput];

  function setInvalid(fields = []) {
    allCredentialFields.forEach(field => {
      if (!field) return;
      const invalid = fields.includes(field);
      field.toggleAttribute('aria-invalid', invalid);
      if (!invalid) field.removeAttribute('aria-describedby');
    });
    fields.forEach(field => field?.setAttribute('aria-describedby', 'auth-error'));
  }

  function clearError() {
    errorBox.hidden = true;
    errorBox.textContent = '';
    errorBox.removeAttribute('data-state');
    setInvalid();
  }

  function showError(message, { fields = [], focus = false } = {}) {
    errorBox.textContent = message || 'Não foi possível concluir a autenticação.';
    errorBox.hidden = false;
    errorBox.dataset.state = 'error';
    setInvalid(fields);
    errorBox.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    if (focus) (fields[0] || emailInput)?.focus({ preventScroll: true });
  }

  function setSubmitting(isSubmitting) {
    submit.disabled = isSubmitting;
    submit.setAttribute('aria-busy', String(isSubmitting));
  }

  async function readStatus() {
    try {
      const response = await fetch('/api/auth/status');
      const data = await response.json();
      bootstrapRequired = Boolean(data.bootstrap_required);
      document.querySelector('#auth-bootstrap-row').style.display = bootstrapRequired ? 'grid' : 'none';
      document.querySelector('#auth-help').textContent = bootstrapRequired
        ? 'Primeiro acesso: crie o administrador principal usando o token de bootstrap.'
        : 'Use seu e-mail e senha.';
      submit.textContent = bootstrapRequired ? 'Criar administrador e entrar' : 'Entrar';
    } catch (_) {
      showError('Não foi possível consultar o estado da autenticação.');
    }
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    clearError();
    setSubmitting(true);

    const payload = { email: emailInput.value.trim(), password: passwordInput.value };
    const headers = { 'Content-Type': 'application/json' };
    let endpoint = '/api/auth/login';
    let failureStatus = 0;
    const credentialFields = bootstrapRequired
      ? [emailInput, passwordInput, bootstrapInput]
      : [emailInput, passwordInput];

    if (bootstrapRequired) {
      endpoint = '/api/auth/bootstrap';
      headers.Authorization = `Bearer ${bootstrapInput.value.trim()}`;
    }

    try {
      const response = await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify(payload) });
      failureStatus = response.status;
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha na autenticação');
      }
      localStorage.setItem('devpilot-token', data.access_token);
      location.reload();
    } catch (error) {
      const message = failureStatus === 401
        ? 'Credenciais inválidas. Confira os dados e tente novamente.'
        : error.message;
      showError(message, { fields: credentialFields, focus: true });
    } finally {
      setSubmitting(false);
    }
  });

  document.querySelector('#auth-token-submit').addEventListener('click', () => {
    const token = technicalTokenInput.value.trim();
    if (!token) {
      showError('Informe o token técnico para continuar.', { fields: [technicalTokenInput], focus: true });
      return;
    }
    clearError();
    localStorage.setItem('devpilot-token', token);
    location.reload();
  });

  function handleAuthError(event) {
    const detail = event.detail || window.__devpilotAuthError || {};
    showError(
      detail.message || 'Sua sessão expirou ou o token técnico é inválido. Entre novamente.',
      { fields: detail.fields || [], focus: true },
    );
  }

  const pendingAuthError = window.__devpilotAuthError;
  if (pendingAuthError) {
    handleAuthError({ detail: pendingAuthError });
    delete window.__devpilotAuthError;
  }
  window.addEventListener('devpilot:auth-error', handleAuthError);

  if (localStorage.getItem('devpilot-token')) {
    const header = document.querySelector('.header-actions');
    if (header && !document.querySelector('#logout')) {
      const logout = document.createElement('button');
      logout.id = 'logout';
      logout.className = 'ghost';
      logout.textContent = 'Sair';
      logout.onclick = () => {
        localStorage.removeItem('devpilot-token');
        location.reload();
      };
      header.prepend(logout);
    }
  }
  readStatus();
})();
