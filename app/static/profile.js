(() => {
  'use strict';

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const token = () => String(localStorage.getItem('devpilot-token') || '').trim();
  const authHeaders = () => ({Authorization:`Bearer ${token()}`, 'Content-Type':'application/json'});
  const roleLabels = {SUPER_ADMIN:'Super administrador',OWNER:'Proprietário',ADMIN:'Administrador',ANALYST:'Analista',VIEWER:'Visualizador'};
  const roleLabel = role => roleLabels[String(role || '').toUpperCase()] || String(role || 'Perfil');
  const initials = value => String(value || 'DP').trim().split(/\s+/).filter(Boolean).map(part => part[0]).join('').slice(0,2).toUpperCase() || 'DP';

  let profileRequest = null;
  let saving = false;
  let mounted = false;

  const style = document.createElement('style');
  style.dataset.devpilotProfileStyle = '1';
  style.textContent = `
    .profile-shell{display:grid;grid-template-columns:minmax(220px,320px) minmax(0,1fr);gap:20px}.profile-card,.profile-form{background:var(--panel,#0f1b2d);border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:22px}.profile-avatar{width:88px;height:88px;border-radius:50%;display:grid;place-items:center;font-size:28px;font-weight:700;background:rgba(255,255,255,.08);overflow:hidden}.profile-avatar img{width:100%;height:100%;object-fit:cover}.profile-meta{display:grid;gap:8px;margin-top:18px}.profile-badge{display:inline-flex;width:max-content;padding:5px 9px;border-radius:999px;background:rgba(255,255,255,.08);font-size:12px;text-transform:uppercase}.profile-form textarea{resize:vertical}.header-user{order:-2;display:flex;align-items:center;gap:9px;min-width:0;padding:6px 10px;border:1px solid var(--line);border-radius:10px;background:rgba(13,25,40,.72);color:var(--text);cursor:pointer;text-align:left}.header-user:hover{background:var(--surface2);border-color:#31506f}.header-user-avatar{flex:0 0 32px;width:32px;height:32px;border-radius:50%;display:grid;place-items:center;overflow:hidden;background:linear-gradient(135deg,var(--cyan),var(--blue));color:#06101b;font-size:11px;font-weight:850}.header-user-avatar img{width:100%;height:100%;object-fit:cover}.header-user-copy{display:grid;min-width:0;line-height:1.15}.header-user-copy strong{max-width:155px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}.header-user-copy small{margin-top:3px;color:var(--muted);font-size:10px}.header-actions #logout{order:-1}@media(max-width:760px){.profile-shell{grid-template-columns:1fr}.header-user{padding:6px}.header-user-copy{display:none}}
  `;
  if (!document.querySelector('style[data-devpilot-profile-style]')) document.head.appendChild(style);

  const nav = document.createElement('button');
  nav.className = 'nav';
  nav.type = 'button';
  nav.dataset.view = 'profile';
  nav.dataset.profileView = '1';
  nav.textContent = 'Perfil';

  const section = document.createElement('section');
  section.className = 'view';
  section.id = 'profile-view';
  section.innerHTML = `
    <div class="section-head"><p>Dados da conta e preferências pessoais.</p></div>
    <div class="profile-shell">
      <article class="profile-card"><div class="profile-avatar" id="profile-avatar">DP</div><div class="profile-meta"><h3 id="profile-name">Usuário</h3><span class="profile-badge" id="profile-role">—</span><small id="profile-email">—</small><small id="profile-active">—</small></div></article>
      <form class="profile-form" id="profile-form">
        <div class="form-grid"><label>Nome completo<input name="full_name" maxlength="160"></label><label>Cargo<input name="job_title" maxlength="120"></label></div>
        <div class="form-grid"><label>Telefone<input name="phone" maxlength="40"></label><label>Avatar URL<input name="avatar_url" maxlength="500"></label></div>
        <label>Bio<textarea name="bio" rows="4" maxlength="1000"></textarea></label>
        <div class="form-grid"><label>Idioma<input name="locale" maxlength="20" value="pt-BR"></label><label>Fuso horário<input name="timezone" maxlength="80" value="America/Sao_Paulo"></label></div>
        <p class="hint">E-mail, perfil de acesso e status da conta são controlados pelo backend e não podem ser alterados aqui.</p>
        <button class="primary" type="submit">Salvar perfil</button>
      </form>
    </div>`;

  function mount() {
    const sidebarNav = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!sidebarNav || !main) return false;
    if (!nav.isConnected && !document.querySelector('[data-profile-view="1"]')) sidebarNav.appendChild(nav);
    if (!section.isConnected && !document.querySelector('#profile-view')) main.appendChild(section);
    mounted = true;
    return true;
  }

  function cachedUser() {
    return typeof state !== 'undefined' && state?.currentUser ? state.currentUser : null;
  }

  function cacheUser(user) {
    if (typeof state !== 'undefined' && state) state.currentUser = user;
    return user;
  }

  async function requestUser({force=false}={}) {
    if (!force) {
      const cached = cachedUser();
      if (cached) return cached;
    }
    if (profileRequest) return profileRequest;
    profileRequest = fetch('/api/auth/me', {headers:authHeaders(), cache:'no-store'})
      .then(async response => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha ao carregar perfil');
        return cacheUser(data);
      })
      .finally(() => { profileRequest = null; });
    return profileRequest;
  }

  function ensureHeaderUser() {
    if (!token()) return null;
    const header = document.querySelector('.header-actions');
    if (!header) return null;
    let chip = document.querySelector('#header-user');
    if (chip) return chip;
    chip = document.createElement('button');
    chip.id = 'header-user';
    chip.type = 'button';
    chip.className = 'header-user';
    chip.title = 'Abrir perfil';
    chip.innerHTML = '<span class="header-user-avatar" id="header-user-avatar">DP</span><span class="header-user-copy"><strong id="header-user-name">Usuário</strong><small id="header-user-role">Perfil</small></span>';
    chip.addEventListener('click', showProfile);
    header.prepend(chip);
    return chip;
  }

  function render(user) {
    if (!mount() || !user) return;
    const displayName = user.full_name || user.email || 'Administrador';
    const form = section.querySelector('#profile-form');
    ['full_name','phone','job_title','bio','avatar_url','locale','timezone'].forEach(key => {
      const field = form?.elements.namedItem(key);
      if (field && document.activeElement !== field) field.value = user[key] || '';
    });
    section.querySelector('#profile-name').textContent = displayName;
    section.querySelector('#profile-role').textContent = roleLabel(user.role);
    section.querySelector('#profile-email').textContent = user.email || 'Acesso bootstrap';
    section.querySelector('#profile-active').textContent = user.active === false ? 'Conta inativa' : 'Conta ativa';
    const avatar = section.querySelector('#profile-avatar');
    avatar.innerHTML = user.avatar_url ? `<img src="${esc(user.avatar_url)}" alt="Avatar">` : esc(initials(displayName));
    const submit = form?.querySelector('button[type="submit"]');
    if (submit) submit.disabled = Boolean(user.bootstrap) || saving;

    const chip = ensureHeaderUser();
    if (chip) {
      chip.hidden = false;
      chip.querySelector('#header-user-name').textContent = displayName;
      chip.querySelector('#header-user-role').textContent = roleLabel(user.role);
      const chipAvatar = chip.querySelector('#header-user-avatar');
      chipAvatar.innerHTML = user.avatar_url ? `<img src="${esc(user.avatar_url)}" alt="Avatar de ${esc(displayName)}">` : esc(initials(displayName));
    }
  }

  async function loadProfile({force=false, silent=false}={}) {
    try {
      const user = await requestUser({force});
      render(user);
      return user;
    } catch (error) {
      if (!silent) window.toast ? window.toast(error.message) : console.error(error);
      return null;
    }
  }

  function showProfile() {
    if (!mount()) return;
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === 'profile-view'));
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item.dataset.view === 'profile'));
    const title = document.querySelector('#page-title');
    if (title) title.textContent = 'Perfil';
    const user = cachedUser();
    if (user) render(user);
    else void loadProfile();
  }

  async function saveProfile(form) {
    if (!form || saving) return;
    saving = true;
    const submit = form.querySelector('button[type="submit"]');
    if (submit) { submit.disabled = true; submit.textContent = 'Salvando…'; }
    const data = new FormData(form);
    const payload = Object.fromEntries(['full_name','phone','job_title','bio','avatar_url','locale','timezone'].map(key => [key, String(data.get(key) || '').trim() || null]));
    try {
      const response = await fetch('/api/auth/me', {method:'PATCH', headers:authHeaders(), body:JSON.stringify(payload), cache:'no-store'});
      const user = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof user.detail === 'string' ? user.detail : 'Falha ao salvar perfil');
      cacheUser(user);
      render(user);
      window.toast?.('Perfil atualizado');
    } catch (error) {
      window.toast ? window.toast(error.message) : console.error(error);
    } finally {
      saving = false;
      if (submit) { submit.disabled = false; submit.textContent = 'Salvar perfil'; }
    }
  }

  nav.addEventListener('click', showProfile);
  document.addEventListener('submit', event => {
    const form = event.target instanceof HTMLFormElement ? event.target : null;
    if (!form || form.id !== 'profile-form') return;
    event.preventDefault();
    void saveProfile(form);
  }, true);
  document.querySelector('#refresh')?.addEventListener('click', () => {
    if (section.classList.contains('active')) void loadProfile({force:true});
  });

  window.devpilotRefreshProfile = options => loadProfile({force:Boolean(options?.force)});
  mount();
  ensureHeaderUser();
  const initialUser = cachedUser();
  if (initialUser) render(initialUser);
})();
