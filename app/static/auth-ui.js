(() => {
  const modal = document.querySelector('#auth-modal');
  if (!modal) return;
  let bootstrapRequired = false;

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

  async function readStatus() {
    try {
      const response = await fetch('/api/auth/status');
      const data = await response.json();
      bootstrapRequired = Boolean(data.bootstrap_required);
      document.querySelector('#auth-bootstrap-row').style.display = bootstrapRequired ? 'grid' : 'none';
      document.querySelector('#auth-help').textContent = bootstrapRequired
        ? 'Primeiro acesso: crie o administrador principal usando o token de bootstrap. Depois disso, o token não autentica sessões normais.'
        : 'Use seu e-mail e senha.';
      submit.textContent = bootstrapRequired ? 'Criar administrador e entrar' : 'Entrar';
    } catch (_) {
      errorBox.textContent = 'Não foi possível consultar o estado da autenticação.';
    }
  }

  document.querySelector('#auth-form').addEventListener('submit', async event => {
    event.preventDefault(); errorBox.textContent = ''; submit.disabled = true;
    const payload = {email:document.querySelector('#auth-email').value.trim(), password:document.querySelector('#auth-password').value};
    const headers = {'Content-Type':'application/json'};
    let endpoint = '/api/auth/login';
    if (bootstrapRequired) {
      endpoint = '/api/auth/bootstrap';
      headers.Authorization = `Bearer ${document.querySelector('#auth-bootstrap').value.trim()}`;
    }
    try {
      const response = await fetch(endpoint, {method:'POST', headers, body:JSON.stringify(payload)});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha na autenticação');
      localStorage.setItem('devpilot-token', data.access_token); location.reload();
    } catch (error) { errorBox.textContent = error.message; submit.disabled = false; }
  });

  if (localStorage.getItem('devpilot-token')) {
    const header = document.querySelector('.header-actions');
    if (header && !document.querySelector('#logout')) {
      const logout = document.createElement('button'); logout.id='logout'; logout.className='ghost'; logout.textContent='Sair';
      logout.onclick=()=>{localStorage.removeItem('devpilot-token');location.reload()}; header.prepend(logout);
    }
  }
  readStatus();
})();
