(() => {
  const token = () => localStorage.getItem('devpilot-token') || '';
  if (!token()) return;
  const ROLE_LABELS={SUPER_ADMIN:'Super Admin',OWNER:'Proprietário',ADMIN:'Administrador',ANALYST:'Analista',VIEWER:'Leitura'};
  const MANAGERS=new Set(['SUPER_ADMIN','OWNER','ADMIN']);
  const optionsFor=role=>role==='SUPER_ADMIN'?Object.keys(ROLE_LABELS):role==='OWNER'?['ADMIN','ANALYST','VIEWER']:['ANALYST','VIEWER'];
  const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

  const style=document.createElement('style');
  style.textContent='.users-toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.users-toolbar input{flex:1 1 240px}.users-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0}.users-summary .metric{margin:0}.user-name{display:block}.user-email{color:var(--muted);font-size:12px}.user-status{font-weight:800}.user-status.active{color:var(--cyan)}.user-status.inactive{color:var(--red)}.user-actions{display:flex;gap:6px;align-items:center}.user-actions select{min-width:145px}.users-table{min-width:760px}.users-note{color:var(--muted);font-size:12px}@media(max-width:760px){.users-summary{grid-template-columns:1fr}}';
  document.head.appendChild(style);

  async function request(path,options={}){
    const headers={'Authorization':`Bearer ${token()}`,...(options.headers||{})};
    if(options.body)headers['Content-Type']='application/json';
    const response=await fetch(path,{...options,headers});const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Falha na operação');return data;
  }

  async function start(){
    let current;try{current=await request('/api/auth/me')}catch(_){return}if(!MANAGERS.has(current.role))return;
    const nav=document.createElement('button');nav.className='nav';nav.textContent='Usuários';document.querySelector('.sidebar nav')?.appendChild(nav);
    const section=document.createElement('section');section.className='view';section.id='users-view';section.innerHTML=`
      <div class="section-head"><div><p>Perfis de acesso no padrão RegulaAI.</p></div><button class="primary" id="new-user">+ Novo usuário</button></div>
      <div class="users-summary" id="users-summary"></div>
      <div class="users-toolbar"><input id="users-search" placeholder="Buscar por nome, e-mail ou perfil"><button class="ghost" id="users-refresh">Atualizar</button></div>
      <div class="panel table-wrap" style="margin-top:16px"><table class="users-table"><thead><tr><th>Usuário</th><th>Perfil</th><th>Status</th><th>Ações</th></tr></thead><tbody id="users-table"></tbody></table></div>
      <p class="users-note">Super Admin administra todos. Proprietário administra Admin/Analista/Leitura. Administrador administra Analista/Leitura.</p>`;document.querySelector('main')?.appendChild(section);
    const dialog=document.createElement('dialog');dialog.id='user-create-modal';dialog.innerHTML=`<form class="modal" id="user-create-form"><button class="close" type="button">×</button><span class="eyebrow">NOVO USUÁRIO</span><h2>Criar acesso</h2><label>Nome<input name="full_name" maxlength="160"></label><label>E-mail<input name="email" type="email" required></label><label>Senha temporária<input name="password" type="password" minlength="12" required></label><label>Perfil<select name="role" id="new-user-role"></select></label><button class="primary" type="submit">Criar usuário</button></form>`;document.body.appendChild(dialog);dialog.querySelector('.close').onclick=()=>dialog.close();
    const roleSelect=document.querySelector('#new-user-role');roleSelect.innerHTML=optionsFor(current.role).map(role=>`<option value="${role}">${ROLE_LABELS[role]}</option>`).join('');
    let users=[];const table=document.querySelector('#users-table'),search=document.querySelector('#users-search');
    function manageable(user){if(user.id===current.id)return false;if(current.role==='SUPER_ADMIN')return true;if(current.role==='OWNER')return ['ADMIN','ANALYST','VIEWER'].includes(user.role);return ['ANALYST','VIEWER'].includes(user.role)}
    function render(){
      const q=search.value.trim().toLowerCase(),filtered=users.filter(user=>`${user.full_name||''} ${user.email} ${user.role}`.toLowerCase().includes(q)),active=users.filter(user=>user.active).length;
      document.querySelector('#users-summary').innerHTML=[['Usuários',users.length],['Ativos',active],['Perfis',new Set(users.map(u=>u.role)).size]].map(([n,v])=>`<div class="metric"><span>${n}</span><strong>${v}</strong></div>`).join('');
      table.innerHTML=filtered.map(user=>{const can=manageable(user),roles=[...new Set([user.role,...optionsFor(current.role)])];return `<tr><td><strong class="user-name">${esc(user.full_name||'Sem nome')}</strong><span class="user-email">${esc(user.email)}</span></td><td><select data-user-role="${user.id}" ${can?'':'disabled'}>${roles.map(role=>`<option value="${role}" ${role===user.role?'selected':''}>${ROLE_LABELS[role]||esc(role)}</option>`).join('')}</select></td><td><span class="user-status ${user.active?'active':'inactive'}">${user.active?'Ativo':'Inativo'}</span></td><td><button class="ghost" data-user-toggle="${user.id}" ${can?'':'disabled'}>${user.active?'Desativar':'Ativar'}</button></td></tr>`}).join('')||'<tr><td colspan="4" class="empty">Nenhum usuário encontrado.</td></tr>';
      table.querySelectorAll('[data-user-role]').forEach(s=>s.onchange=()=>updateUser(s.dataset.userRole,{role:s.value}));table.querySelectorAll('[data-user-toggle]').forEach(b=>b.onclick=()=>{const u=users.find(x=>x.id===b.dataset.userToggle);if(u)updateUser(u.id,{active:!u.active})});
    }
    async function load(){try{users=await request('/api/users');render()}catch(e){window.toast?.(e.message)}}
    async function updateUser(id,patch){try{const updated=await request(`/api/users/${id}`,{method:'PATCH',body:JSON.stringify(patch)});users=users.map(u=>u.id===id?updated:u);render();window.toast?.('Usuário atualizado')}catch(e){window.toast?.(e.message);await load()}}
    nav.onclick=()=>{document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v===section));document.querySelectorAll('.nav').forEach(n=>n.classList.toggle('active',n===nav));const t=document.querySelector('#page-title');if(t)t.textContent='Usuários';load()};search.oninput=render;document.querySelector('#users-refresh').onclick=load;document.querySelector('#new-user').onclick=()=>dialog.showModal();
    document.querySelector('#user-create-form').onsubmit=async event=>{event.preventDefault();const f=new FormData(event.currentTarget);try{await request('/api/users',{method:'POST',body:JSON.stringify({full_name:String(f.get('full_name')||'').trim()||null,email:String(f.get('email')||'').trim(),password:String(f.get('password')||''),role:String(f.get('role')||'VIEWER')})});dialog.close();event.currentTarget.reset();roleSelect.innerHTML=optionsFor(current.role).map(role=>`<option value="${role}">${ROLE_LABELS[role]}</option>`).join('');window.toast?.('Usuário criado');await load()}catch(e){window.toast?.(e.message)}};
  }
  start();
})();
