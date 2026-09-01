(() => {
  'use strict';

  const token = () => localStorage.getItem('devpilot-token') || '';
  if (!token()) return;

  const ROLE_LABELS = {
    SUPER_ADMIN: 'Super Admin',
    OWNER: 'Proprietário',
    ADMIN: 'Administrador',
    ANALYST: 'Analista',
    VIEWER: 'Leitura',
  };
  const MANAGERS = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  }[c]));

  const style = document.createElement('style');
  style.textContent = `
    .users-toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.users-toolbar input{flex:1 1 240px}
    .users-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0}.users-summary .metric{margin:0}
    .user-name{display:block}.user-email{color:var(--muted);font-size:12px}.user-status{font-weight:800}.user-status.active{color:var(--cyan)}.user-status.inactive{color:var(--red)}
    .user-actions{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.user-actions select{min-width:145px}.users-table{min-width:760px}.users-note{color:var(--muted);font-size:12px}
    .user-role-save[disabled]{opacity:.42;cursor:not-allowed}.user-role-protected{display:inline-flex;align-items:center;gap:6px;color:var(--muted);font-size:11px;font-weight:800}
    .users-security-note{margin:10px 0 0;padding:10px 12px;border:1px solid rgba(53,229,209,.18);border-radius:10px;background:rgba(53,229,209,.04);color:var(--muted);font-size:12px;line-height:1.45}
    .users-stepup-copy{color:var(--muted);font-size:13px;line-height:1.5;margin:0 0 12px}
    @media(max-width:760px){.users-summary{grid-template-columns:1fr}.user-actions{align-items:stretch}.user-actions select,.user-actions button{min-height:44px}}
  `;
  document.head.appendChild(style);

  async function request(path, options = {}) {
    const headers = {'Authorization': `Bearer ${token()}`, ...(options.headers || {})};
    if (options.body) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {...options, headers});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha na operação');
    return data;
  }

  async function start() {
    let current;
    try { current = await request('/api/auth/me'); } catch (_) { return; }
    if (!MANAGERS.has(current.role)) return;

    let roleCatalog = [];
    try {
      const data = await request('/api/users/roles');
      roleCatalog = Array.isArray(data) ? data : [];
    } catch (_) {
      return;
    }
    const assignableRoles = new Set(roleCatalog.map(item => String(item.value || '')));
    const roleValues = roleCatalog.map(item => String(item.value || '')).filter(Boolean);

    const nav = document.createElement('button');
    nav.className = 'nav';
    nav.dataset.view = 'users';
    nav.textContent = 'Usuários';
    document.querySelector('.sidebar nav')?.appendChild(nav);

    const note = current.role === 'SUPER_ADMIN'
      ? 'Super Admin é uma conta raiz protegida. Proprietário exige reautenticação. Administrador, Analista e Leitura seguem a matriz normal.'
      : current.role === 'OWNER'
        ? 'Proprietário administra Administrador, Analista e Leitura. Super Admin não é atribuível nesta tela.'
        : 'Administrador administra apenas Analista e Leitura. Super Admin e Proprietário não são atribuíveis.';

    const section = document.createElement('section');
    section.className = 'view';
    section.id = 'users-view';
    section.hidden = true;
    section.setAttribute('aria-hidden', 'true');
    section.innerHTML = `
      <div class="section-head"><div><p>Perfis de acesso com separação de privilégios.</p></div><button class="primary" id="new-user">+ Novo usuário</button></div>
      <div class="users-summary" id="users-summary"></div>
      <div class="users-toolbar"><input id="users-search" placeholder="Buscar por nome, e-mail ou perfil"><button class="ghost" id="users-refresh">Atualizar</button></div>
      <p class="users-security-note"><strong>Segurança:</strong> selecionar um perfil não altera a conta. É necessário confirmar em <em>Salvar perfil</em>. Super Admin não pode ser criado, promovido, rebaixado ou desativado por este editor.</p>
      <div class="panel table-wrap" style="margin-top:16px"><table class="users-table"><thead><tr><th>Usuário</th><th>Perfil</th><th>Status</th><th>Ações</th></tr></thead><tbody id="users-table"></tbody></table></div>
      <p class="users-note">${note}</p>`;
    document.querySelector('main')?.appendChild(section);

    const createDialog = document.createElement('dialog');
    createDialog.id = 'user-create-modal';
    createDialog.innerHTML = `<form class="modal" id="user-create-form">
      <button class="close" type="button">×</button><span class="eyebrow">NOVO USUÁRIO</span><h2>Criar acesso</h2>
      <label>Nome<input name="full_name" maxlength="160"></label>
      <label>E-mail<input name="email" type="email" required></label>
      <label>Senha temporária<input name="password" type="password" minlength="12" autocomplete="new-password" required></label>
      <label>Perfil<select name="role" id="new-user-role"></select></label>
      <p class="users-security-note" id="new-user-owner-warning" hidden>Proprietário é um perfil privilegiado. Para criá-lo, confirme novamente a senha do Super Admin.</p>
      <label id="new-user-stepup-wrap" hidden>Senha atual do Super Admin<input name="confirmation_password" type="password" minlength="8" autocomplete="current-password"></label>
      <button class="primary" type="submit">Criar usuário</button>
    </form>`;
    document.body.appendChild(createDialog);
    createDialog.querySelector('.close').onclick = () => createDialog.close();

    const stepUpDialog = document.createElement('dialog');
    stepUpDialog.id = 'user-stepup-modal';
    stepUpDialog.innerHTML = `<form class="modal" id="user-stepup-form">
      <button class="close" type="button">×</button><span class="eyebrow">CONFIRMAÇÃO DE SEGURANÇA</span><h2>Reautenticar</h2>
      <p class="users-stepup-copy" id="user-stepup-message"></p>
      <label>Senha atual do Super Admin<input name="password" type="password" minlength="8" autocomplete="current-password" required></label>
      <div class="form-actions"><button class="ghost" type="button" data-stepup-cancel>Cancelar</button><button class="primary" type="submit">Confirmar</button></div>
    </form>`;
    document.body.appendChild(stepUpDialog);

    const roleSelect = document.querySelector('#new-user-role');
    const ownerWarning = document.querySelector('#new-user-owner-warning');
    const ownerStepUpWrap = document.querySelector('#new-user-stepup-wrap');
    const ownerStepUpInput = ownerStepUpWrap.querySelector('input');

    function fillCreateRoles() {
      roleSelect.innerHTML = roleValues.map(role => `<option value="${esc(role)}">${esc(ROLE_LABELS[role] || role)}</option>`).join('');
      syncCreateStepUp();
    }
    function syncCreateStepUp() {
      const privileged = roleSelect.value === 'OWNER';
      ownerWarning.hidden = !privileged;
      ownerStepUpWrap.hidden = !privileged;
      ownerStepUpInput.required = privileged;
      if (!privileged) ownerStepUpInput.value = '';
    }
    roleSelect.addEventListener('change', syncCreateStepUp);
    fillCreateRoles();

    function askStepUp(message) {
      return new Promise(resolve => {
        const form = stepUpDialog.querySelector('#user-stepup-form');
        const input = form.elements.password;
        const messageNode = stepUpDialog.querySelector('#user-stepup-message');
        let settled = false;
        const finish = value => {
          if (settled) return;
          settled = true;
          input.value = '';
          form.onsubmit = null;
          stepUpDialog.querySelector('[data-stepup-cancel]').onclick = null;
          stepUpDialog.querySelector('.close').onclick = null;
          if (stepUpDialog.open) stepUpDialog.close();
          resolve(value);
        };
        messageNode.textContent = message;
        form.onsubmit = event => { event.preventDefault(); finish(String(input.value || '')); };
        stepUpDialog.querySelector('[data-stepup-cancel]').onclick = () => finish(null);
        stepUpDialog.querySelector('.close').onclick = () => finish(null);
        stepUpDialog.oncancel = event => { event.preventDefault(); finish(null); };
        stepUpDialog.showModal();
        window.setTimeout(() => input.focus(), 30);
      });
    }

    let users = [];
    const table = document.querySelector('#users-table');
    const search = document.querySelector('#users-search');
    const visibleUser = user => current.role === 'SUPER_ADMIN' || user.role !== 'SUPER_ADMIN';
    const manageable = user => user.id !== current.id && user.role !== 'SUPER_ADMIN' && assignableRoles.has(user.role);

    function render() {
      const q = search.value.trim().toLowerCase();
      const filtered = users.filter(user => `${user.full_name || ''} ${user.email} ${user.role}`.toLowerCase().includes(q));
      const active = users.filter(user => user.active).length;
      document.querySelector('#users-summary').innerHTML = [
        ['Usuários', users.length], ['Ativos', active], ['Perfis', new Set(users.map(u => u.role)).size],
      ].map(([name, value]) => `<div class="metric"><span>${name}</span><strong>${value}</strong></div>`).join('');

      table.innerHTML = filtered.map(user => {
        const can = manageable(user);
        const roles = can ? roleValues : [user.role];
        const roleControl = `<select data-user-role="${esc(user.id)}" data-original-role="${esc(user.role)}" ${can ? '' : 'disabled'}>${roles.map(role => `<option value="${esc(role)}" ${role === user.role ? 'selected' : ''}>${esc(ROLE_LABELS[role] || role)}</option>`).join('')}</select>`;
        const roleSave = can
          ? `<button class="ghost user-role-save" type="button" data-user-role-save="${esc(user.id)}" disabled>Salvar perfil</button>`
          : `<span class="user-role-protected">🔒 ${user.role === 'SUPER_ADMIN' ? 'Conta raiz protegida' : 'Perfil protegido'}</span>`;
        return `<tr>
          <td><strong class="user-name">${esc(user.full_name || 'Sem nome')}</strong><span class="user-email">${esc(user.email)}</span></td>
          <td>${roleControl}</td>
          <td><span class="user-status ${user.active ? 'active' : 'inactive'}">${user.active ? 'Ativo' : 'Inativo'}</span></td>
          <td><div class="user-actions">${roleSave}<button class="ghost" data-user-toggle="${esc(user.id)}" ${can ? '' : 'disabled'}>${user.active ? 'Desativar' : 'Ativar'}</button></div></td>
        </tr>`;
      }).join('') || '<tr><td colspan="4" class="empty">Nenhum usuário encontrado.</td></tr>';

      table.querySelectorAll('[data-user-role]').forEach(select => {
        select.onchange = () => {
          const save = table.querySelector(`[data-user-role-save="${CSS.escape(select.dataset.userRole)}"]`);
          if (save) save.disabled = select.value === select.dataset.originalRole;
        };
      });
      table.querySelectorAll('[data-user-role-save]').forEach(button => {
        button.onclick = () => saveRole(button.dataset.userRole);
      });
      table.querySelectorAll('[data-user-toggle]').forEach(button => {
        button.onclick = () => toggleUser(button.dataset.userToggle);
      });
    }

    async function load() {
      try {
        const data = await request('/api/users');
        users = Array.isArray(data) ? data.filter(visibleUser) : [];
        render();
      } catch (error) {
        window.toast?.(error.message);
      }
    }

    async function saveRole(id) {
      const user = users.find(item => item.id === id);
      const select = table.querySelector(`[data-user-role="${CSS.escape(id)}"]`);
      if (!user || !select) return;
      const requested = String(select.value || '');
      if (!assignableRoles.has(requested) || requested === 'SUPER_ADMIN') {
        window.toast?.('Perfil não atribuível nesta sessão');
        await load();
        return;
      }
      if (requested === user.role) return;
      if (!window.confirm(`Alterar ${user.email} de ${ROLE_LABELS[user.role] || user.role} para ${ROLE_LABELS[requested] || requested}?`)) {
        select.value = user.role;
        render();
        return;
      }

      const patch = {role: requested};
      if (requested === 'OWNER' || user.role === 'OWNER') {
        const password = await askStepUp(`A alteração envolve o perfil Proprietário de ${user.email}. Confirme a senha atual do Super Admin para continuar.`);
        if (!password) { await load(); return; }
        patch.confirmation_password = password;
      }
      await updateUser(id, patch);
    }

    async function toggleUser(id) {
      const user = users.find(item => item.id === id);
      if (!user) return;
      const verb = user.active ? 'desativar' : 'ativar';
      if (!window.confirm(`Deseja ${verb} o acesso de ${user.email}?`)) return;
      const patch = {active: !user.active};
      if (user.role === 'OWNER') {
        const password = await askStepUp(`A alteração muda o estado de um Proprietário (${user.email}). Confirme a senha atual do Super Admin.`);
        if (!password) return;
        patch.confirmation_password = password;
      }
      await updateUser(id, patch);
    }

    async function updateUser(id, patch) {
      try {
        const updated = await request(`/api/users/${id}`, {method: 'PATCH', body: JSON.stringify(patch)});
        if (visibleUser(updated)) users = users.map(user => user.id === id ? updated : user);
        else users = users.filter(user => user.id !== id);
        render();
        window.toast?.('Usuário atualizado');
      } catch (error) {
        window.toast?.(error.message);
        await load();
      }
    }

    nav.onclick = () => {
      if (typeof window.devpilotNavigate === 'function') {
        window.devpilotNavigate('users', {source: 'users-menu'});
      } else {
        document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
        document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === nav));
        section.hidden = false;
        section.setAttribute('aria-hidden', 'false');
        const title = document.querySelector('#page-title');
        if (title) title.textContent = 'Usuários';
      }
      load();
    };

    document.addEventListener('devpilot:page-ready', event => {
      if (event.detail?.view === 'users') load();
    });

    search.oninput = render;
    document.querySelector('#users-refresh').onclick = load;
    document.querySelector('#new-user').onclick = () => createDialog.showModal();
    document.querySelector('#user-create-form').onsubmit = async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const data = new FormData(form);
      const role = String(data.get('role') || 'VIEWER');
      const payload = {
        full_name: String(data.get('full_name') || '').trim() || null,
        email: String(data.get('email') || '').trim(),
        password: String(data.get('password') || ''),
        role,
      };
      if (role === 'OWNER') payload.confirmation_password = String(data.get('confirmation_password') || '');
      try {
        await request('/api/users', {method: 'POST', body: JSON.stringify(payload)});
        createDialog.close();
        form.reset();
        fillCreateRoles();
        window.toast?.('Usuário criado');
        await load();
      } catch (error) {
        window.toast?.(error.message);
      }
    };
  }

  start();
})();
