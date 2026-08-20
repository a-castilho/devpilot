(() => {
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const token = () => localStorage.getItem('devpilot-token') || '';
  const headers = () => ({'Authorization': `Bearer ${token()}`, 'Content-Type': 'application/json'});

  const style = document.createElement('style');
  style.textContent = `
    .profile-shell{display:grid;grid-template-columns:minmax(220px,320px) minmax(0,1fr);gap:20px}.profile-card,.profile-form{background:var(--panel,#0f1b2d);border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:22px}.profile-avatar{width:88px;height:88px;border-radius:50%;display:grid;place-items:center;font-size:28px;font-weight:700;background:rgba(255,255,255,.08);overflow:hidden}.profile-avatar img{width:100%;height:100%;object-fit:cover}.profile-meta{display:grid;gap:8px;margin-top:18px}.profile-badge{display:inline-flex;width:max-content;padding:5px 9px;border-radius:999px;background:rgba(255,255,255,.08);font-size:12px;text-transform:uppercase}.profile-form textarea{resize:vertical}@media(max-width:760px){.profile-shell{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  const nav = document.createElement('button');
  nav.className = 'nav'; nav.dataset.profileView = '1'; nav.textContent = 'Perfil';
  document.querySelector('.sidebar nav')?.appendChild(nav);

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
  document.querySelector('main')?.appendChild(section);

  async function request(path, options={}) {
    const response = await fetch(path, {...options, headers: {...headers(), ...(options.headers||{})}});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha ao carregar perfil');
    return data;
  }

  function showProfile() {
    document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'profile-view'));
    document.querySelectorAll('.nav').forEach(v => v.classList.toggle('active', v === nav));
    const title = document.querySelector('#page-title'); if (title) title.textContent = 'Perfil';
    loadProfile();
  }

  async function loadProfile() {
    try {
      const user = await request('/api/auth/me');
      const form = document.querySelector('#profile-form');
      ['full_name','phone','job_title','bio','avatar_url','locale','timezone'].forEach(k => { if (form.elements[k]) form.elements[k].value = user[k] || ''; });
      document.querySelector('#profile-name').textContent = user.full_name || user.email || 'Administrador';
      document.querySelector('#profile-role').textContent = user.role || '—';
      document.querySelector('#profile-email').textContent = user.email || 'Acesso bootstrap';
      document.querySelector('#profile-active').textContent = user.active ? 'Conta ativa' : 'Conta inativa';
      const avatar = document.querySelector('#profile-avatar');
      if (user.avatar_url) avatar.innerHTML = `<img src="${esc(user.avatar_url)}" alt="Avatar">`;
      else avatar.textContent = (user.full_name || user.email || 'DP').split(/\s+/).map(x=>x[0]).join('').slice(0,2).toUpperCase();
      form.querySelector('button[type="submit"]').disabled = Boolean(user.bootstrap);
    } catch (error) { window.toast ? window.toast(error.message) : console.error(error); }
  }

  nav.addEventListener('click', showProfile);
  document.querySelector('#profile-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    const payload = Object.fromEntries(['full_name','phone','job_title','bio','avatar_url','locale','timezone'].map(k => [k, String(f.get(k)||'').trim() || null]));
    try {
      await request('/api/auth/me', {method:'PATCH', body:JSON.stringify(payload)});
      if (window.toast) window.toast('Perfil atualizado');
      await loadProfile();
    } catch (error) { if (window.toast) window.toast(error.message); }
  });
})();
