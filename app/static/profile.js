(() => {
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const token = () => localStorage.getItem('devpilot-token') || '';
  const headers = () => ({'Authorization': `Bearer ${token()}`, 'Content-Type': 'application/json'});
  const roleLabels = {
    SUPER_ADMIN: 'Super administrador',
    OWNER: 'Proprietário',
    ADMIN: 'Administrador',
    ANALYST: 'Analista',
    VIEWER: 'Visualizador',
  };
  const roleLabel = role => roleLabels[String(role || '').toUpperCase()] || String(role || 'Perfil');
  const initials = value => String(value || 'DP').trim().split(/\s+/).filter(Boolean).map(part => part[0]).join('').slice(0, 2).toUpperCase() || 'DP';

  const style = document.createElement('style');
  style.textContent = `
    .profile-shell{display:grid;grid-template-columns:minmax(220px,320px) minmax(0,1fr);gap:20px}.profile-card,.profile-form{background:var(--panel,#0f1b2d);border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:22px}.profile-avatar{width:88px;height:88px;border-radius:50%;display:grid;place-items:center;font-size:28px;font-weight:700;background:rgba(255,255,255,.08);overflow:hidden}.profile-avatar img{width:100%;height:100%;object-fit:cover}.profile-meta{display:grid;gap:8px;margin-top:18px}.profile-badge{display:inline-flex;width:max-content;padding:5px 9px;border-radius:999px;background:rgba(255,255,255,.08);font-size:12px;text-transform:uppercase}.profile-form textarea{resize:vertical}
    .header-user{order:-2;display:flex;align-items:center;gap:9px;min-width:0;padding:6px 10px;border:1px solid var(--line);border-radius:10px;background:rgba(13,25,40,.72);color:var(--text);cursor:pointer;text-align:left}.header-user:hover{background:var(--surface2);border-color:#31506f}.header-user-avatar{flex:0 0 32px;width:32px;height:32px;border-radius:50%;display:grid;place-items:center;overflow:hidden;background:linear-gradient(135deg,var(--cyan),var(--blue));color:#06101b;font-size:11px;font-weight:850}.header-user-avatar img{width:100%;height:100%;object-fit:cover}.header-user-copy{display:grid;min-width:0;line-height:1.15}.header-user-copy strong{max-width:155px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}.header-user-copy small{margin-top:3px;color:var(--muted);font-size:10px}.header-actions #logout{order:-1}
    @media(max-width:760px){.profile-shell{grid-template-columns:1fr}.header-user{padding:6px}.header-user-copy{display:none}}
  `;
  document.head.appendChild(style);

  const sidebarNav = document.querySelector('.sidebar nav');
  const main = document.querySelector('main');
  if (!sidebarNav || !main) return;

  const nav = document.createElement('button');
  nav.className = 'nav';
  nav.type = 'button';
  nav.dataset.view = 'profile';
  nav.dataset.profileView = '1';
  nav.textContent = 'Perfil';
  sidebarNav.appendChild(nav);

  const section = document.createElement('section');
  section.className = 'view'; section.id = 'profile-view';
  section.innerHTML = `
    <div class="section-head"><p>Dados da conta e preferências pessoais.</p></div>
    <div class="profile-shell">
      <article class="profile-card">
        <div class="profile-avatar" id="profile-avatar">DP</div>
        <div class="profile-meta"><h3 id="profile-name">Usuário</h3><span class="profile-badge" id="profile-role">—</span><small id="profile-email">—</small><small id="profile-active">—</small></div>
      </article>
      <form class="profile-form" id="profile-form">
        <div class="form-grid"><label>Nome completo<input name="full_name" maxlength="160"></label><label>Cargo<input name="job_title" maxlength="120"></label></div>
        <div class="form-grid"><label>Telefone<input name="phone" maxlength="40"></label><label>Avatar URL<input name="avatar_url" maxlength="500"></label></div>
        <label>Bio<textarea name="bio" rows="4" maxlength="1000"></textarea></label>
        <div class="form-grid"><label>Idioma<input name="locale" maxlength="20" value="pt-BR"></label><label>Fuso horário<input name="timezone" maxlength="80" value="America/Sao_Paulo"></label></div>
        <p class="hint">E-mail, perfil de acesso e status da conta são controlados pelo backend e não podem ser alterados aqui.</p>
        <button class="primary" type="submit">Salvar perfil</button>
      </form>
    </div>`;
  main.appendChild(section);

  let headerUser = null;

  function ensureProfileMounted() {
    const currentMain = document.querySelector('main');
    const currentNav = document.querySelector('.sidebar nav');
    if (!section.isConnected && currentMain) currentMain.appendChild(section);
    if (!nav.isConnected && currentNav) currentNav.appendChild(nav);
    return section.isConnected;
  }

  function profileForm() {
    ensureProfileMounted();
    return section.querySelector('#profile-form');
  }

  function ensureHeaderUser() {
    if (!token()) return null;
    const header = document.querySelector('.header-actions');
    if (!header) return null;
    headerUser = document.querySelector('#header-user');
    if (headerUser) return headerUser;
    headerUser = document.createElement('button');
    headerUser.id = 'header-user';
    headerUser.type = 'button';
    headerUser.className = 'header-user';
    headerUser.title = 'Abrir perfil';
    headerUser.innerHTML = '<span class="header-user-avatar" id="header-user-avatar">DP</span><span class="header-user-copy"><strong id="header-user-name">Usuário</strong><small id="header-user-role">Perfil</small></span>';
    headerUser.addEventListener('click', showProfile);
    header.prepend(headerUser);
    return headerUser;
  }

  function renderHeaderUser(user) {
    const chip = ensureHeaderUser();
    if (!chip) return;
    chip.hidden = false;
    const displayName = user.full_name || user.email || 'Administrador';
    const headerName = chip.querySelector('#header-user-name');
    const headerRole = chip.querySelector('#header-user-role');
    const avatar = chip.querySelector('#header-user-avatar');
    if (headerName) headerName.textContent = displayName;
    if (headerRole) headerRole.textContent = roleLabel(user.role);
    if (avatar) {
      if (user.avatar_url) avatar.innerHTML = `<img src="${esc(user.avatar_url)}" alt="Avatar de ${esc(displayName)}">`;
      else avatar.textContent = initials(displayName);
    }
    chip.setAttribute('aria-label', `${displayName}, perfil ${roleLabel(user.role)}. Abrir perfil.`);
  }

  async function request(path, options={}) {
    const response = await fetch(path, {...options, headers: {...headers(), ...(options.headers||{})}});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha ao carregar perfil');
    return data;
  }

  function showProfile() {
    if (!ensureProfileMounted()) {
      window.toast?.('Não foi possível abrir o Perfil. Atualize a página.');
      return;
    }
    document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v === section));
    document.querySelectorAll('.nav').forEach(v => v.classList.toggle('active', v === nav));
    const title = document.querySelector('#page-title'); if (title) title.textContent = 'Perfil';
    loadProfile();
  }

  async function loadProfile({silent=false}={}) {
    try {
      const user = await request('/api/auth/me');
      renderHeaderUser(user);
      const form = profileForm();
      if (!form) throw new Error('Tela de perfil indisponível. Atualize o DevPilot.');
      ['full_name','phone','job_title','bio','avatar_url','locale','timezone'].forEach(k => {
        const field = form.elements.namedItem(k);
        if (field) field.value = user[k] || '';
      });
      const name = section.querySelector('#profile-name');
      const role = section.querySelector('#profile-role');
      const email = section.querySelector('#profile-email');
      const active = section.querySelector('#profile-active');
      const avatar = section.querySelector('#profile-avatar');
      if (name) name.textContent = user.full_name || user.email || 'Administrador';
      if (role) role.textContent = roleLabel(user.role);
      if (email) email.textContent = user.email || 'Acesso bootstrap';
      if (active) active.textContent = user.active ? 'Conta ativa' : 'Conta inativa';
      if (avatar) {
        if (user.avatar_url) avatar.innerHTML = `<img src="${esc(user.avatar_url)}" alt="Avatar">`;
        else avatar.textContent = initials(user.full_name || user.email || 'DP');
      }
      const submit = form.querySelector('button[type="submit"]');
      if (submit) submit.disabled = Boolean(user.bootstrap);
    } catch (error) {
      if (silent && headerUser) headerUser.hidden = true;
      if (!silent) window.toast ? window.toast(error.message) : console.error(error);
    }
  }

  nav.addEventListener('click', showProfile);
  profileForm()?.addEventListener('submit', async event => {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    const payload = Object.fromEntries(['full_name','phone','job_title','bio','avatar_url','locale','timezone'].map(k => [k, String(f.get(k)||'').trim() || null]));
    try {
      await request('/api/auth/me', {method:'PATCH', body:JSON.stringify(payload)});
      if (window.toast) window.toast('Perfil atualizado');
      await loadProfile();
    } catch (error) { if (window.toast) window.toast(error.message); }
  });

  if (token()) {
    ensureHeaderUser();
    loadProfile({silent:true});
  }
})();
