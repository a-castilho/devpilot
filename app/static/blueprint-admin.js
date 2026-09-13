(() => {
  'use strict';

  const ROLE = 'SUPER_ADMIN';
  const bp = {items:[], metrics:{}, selected:null, recommendations:[]};
  const token = () => String(localStorage.getItem('devpilot-token') || '').trim();
  const esc = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const isSuperAdmin = () => String((typeof state !== 'undefined' && state.currentUser?.role) || '').toUpperCase() === ROLE;
  const csv = value => String(value || '').split(',').map(item => item.trim()).filter(Boolean);

  async function request(path, options={}) {
    const headers = {...(options.headers || {}), Authorization:`Bearer ${token()}`};
    if (options.body) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {...options, headers, cache:'no-store'});
    const data = response.status === 204 ? null : await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : `HTTP ${response.status}`);
    return data;
  }

  function styles() {
    if (document.getElementById('blueprint-admin-styles')) return;
    const style = document.createElement('style');
    style.id = 'blueprint-admin-styles';
    style.textContent = `
      .bp-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:14px 0}.bp-card,.bp-box,.bp-item{border:1px solid var(--border,#26354a);border-radius:14px;background:rgba(255,255,255,.015)}.bp-card,.bp-box{padding:14px}.bp-card strong{display:block;font-size:23px;margin-top:4px}.bp-card small,.bp-item small{opacity:.68}.bp-layout{display:grid;grid-template-columns:minmax(260px,.8fr) minmax(0,1.6fr);gap:16px}.bp-list{display:grid;gap:8px}.bp-item{padding:12px;text-align:left;color:inherit;cursor:pointer;width:100%}.bp-item.active{border-color:#36d399;box-shadow:inset 3px 0 #36d399}.bp-item small{display:block;margin-top:4px}.bp-tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.bp-tag{font-size:11px;border:1px solid var(--border,#26354a);border-radius:999px;padding:3px 7px}.bp-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.bp-kv{border:1px solid var(--border,#26354a);border-radius:10px;padding:9px}.bp-kv small{display:block;opacity:.6}.bp-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.bp-form label{display:grid;gap:4px;font-size:12px}.bp-form .full{grid-column:1/-1}.bp-form textarea{min-height:78px;resize:vertical}.bp-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.bp-json{white-space:pre-wrap;overflow-wrap:anywhere;max-height:250px;overflow:auto;background:rgba(0,0,0,.18);padding:10px;border-radius:10px;font-size:12px}.bp-note{padding:9px 11px;border:1px solid var(--border,#26354a);border-radius:10px;margin:9px 0}.bp-note.error{border-color:#be123c}.bp-note.ok{border-color:#16a34a}.bp-match-result{border:1px solid var(--border,#26354a);border-radius:10px;padding:9px;margin-top:8px}.bp-empty{padding:14px;border:1px dashed var(--border,#26354a);border-radius:12px;opacity:.72}
      @media(max-width:900px){.bp-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.bp-layout,.bp-grid,.bp-form{grid-template-columns:1fr}.bp-form .full{grid-column:auto}}
    `;
    document.head.appendChild(style);
  }

  function mount() {
    if (!isSuperAdmin() || document.getElementById('blueprints-admin-view')) return;
    const nav = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!nav || !main) return;
    styles();

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'nav';
    button.dataset.view = 'blueprints-admin';
    button.dataset.superAdmin = 'true';
    button.textContent = 'Blueprints';
    nav.insertBefore(button, nav.querySelector('[data-view="rag-admin"]') || nav.querySelector('[data-view="cloud-admin"]') || null);

    const view = document.createElement('section');
    view.className = 'view';
    view.id = 'blueprints-admin-view';
    view.innerHTML = `
      <div class="section-head"><div><span class="eyebrow">SUPER ADMIN · REUTILIZAÇÃO</span><h2>Blueprints de projeto</h2><p>Catálogo, versões, métricas, matcher e cadastro de estruturas reutilizáveis.</p></div><div class="bp-actions"><button class="ghost" id="bp-refresh">Atualizar</button><button class="primary" id="bp-new">Novo Blueprint</button></div></div>
      <div id="bp-note"></div><div class="bp-summary" id="bp-summary"></div>
      <div class="bp-layout"><article class="panel"><div class="panel-title"><div><span class="eyebrow">REGISTRY</span><h3>Catálogo</h3></div></div><div class="bp-list" id="bp-list"></div></article><article class="panel"><div id="bp-detail"></div></article></div>
      <div class="bp-box" style="margin-top:16px"><div class="panel-title"><div><span class="eyebrow">MATCHER</span><h3>Testar seleção automática</h3></div></div><div class="bp-form"><label class="full">Descrição<textarea id="bp-match-description" placeholder="SaaS FastAPI React PostgreSQL com login e dashboard"></textarea></label><label>Stack<input id="bp-match-stack" placeholder="backend=fastapi,frontend=react,database=postgresql"></label><label>Capabilities<input id="bp-match-capabilities" placeholder="auth,dashboard,docker"></label><label>Tags<input id="bp-match-tags" placeholder="saas,fullstack"></label><label>Score mínimo<input id="bp-match-score" type="number" min="0" max="1" step="0.05" value="0.35"></label></div><div class="bp-actions"><button class="primary" id="bp-run-match">Executar matcher</button></div><div id="bp-match-results"></div></div>
      <div class="bp-box" id="bp-create" style="margin-top:16px" hidden><div class="panel-title"><div><span class="eyebrow">SUPER ADMIN</span><h3>Cadastrar versão</h3></div></div><div class="bp-form"><label>Slug<input id="bp-slug"></label><label>Nome<input id="bp-name"></label><label>Versão<input id="bp-version" value="1.0.0"></label><label>Status<select id="bp-status"><option>experimental</option><option>candidate</option><option>stable</option><option>deprecated</option></select></label><label>Tipo<input id="bp-kind" value="fullstack"></label><label>Capabilities<input id="bp-capabilities"></label><label class="full">Descrição<textarea id="bp-description"></textarea></label><label class="full">Stack JSON<textarea id="bp-stack">{"backend":"fastapi","frontend":"react","database":"postgresql"}</textarea></label><label class="full">Parâmetros<input id="bp-parameters" placeholder="project_name,database_name"></label><label class="full">Tags<input id="bp-tags"></label><label class="full">Arquivos JSON<textarea id="bp-files" placeholder='[{"path":"README.md","content":"# {{ project_name }}"}]'></textarea></label></div><div class="bp-actions"><button class="primary" id="bp-save">Salvar Blueprint</button><button class="ghost" id="bp-cancel">Cancelar</button></div></div>`;
    main.appendChild(view);

    button.onclick = () => { document.querySelectorAll('.view').forEach(item => item.classList.toggle('active', item === view)); document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button)); void load(); };
    view.querySelector('#bp-refresh').onclick = load;
    view.querySelector('#bp-new').onclick = () => { view.querySelector('#bp-create').hidden = false; view.querySelector('#bp-create').scrollIntoView({behavior:'smooth'}); };
    view.querySelector('#bp-cancel').onclick = () => { view.querySelector('#bp-create').hidden = true; };
    view.querySelector('#bp-run-match').onclick = match;
    view.querySelector('#bp-save').onclick = save;
  }

  function note(message='', kind='') { const el=document.getElementById('bp-note'); if (el) el.innerHTML=message?`<div class="bp-note ${kind}">${esc(message)}</div>`:''; }

  function render() {
    const summary = document.getElementById('bp-summary');
    const list = document.getElementById('bp-list');
    if (!summary || !list) return;
    const total = bp.items.length;
    const stable = bp.items.filter(item => item.status === 'stable').length;
    const usages = Number(bp.metrics.total_usage || bp.metrics.projects_created || 0);
    const successful = Number(bp.metrics.successful_projects || bp.metrics.success || 0);
    summary.innerHTML = `<div class="bp-card"><span class="eyebrow">CATÁLOGO</span><strong>${total}</strong><small>blueprints</small></div><div class="bp-card"><span class="eyebrow">ESTÁVEIS</span><strong>${stable}</strong><small>preferidos</small></div><div class="bp-card"><span class="eyebrow">USOS</span><strong>${usages}</strong><small>seleções</small></div><div class="bp-card"><span class="eyebrow">SUCESSO</span><strong>${usages ? Math.round(successful/usages*100) : 0}%</strong><small>histórico</small></div>`;
    list.innerHTML = bp.items.map(item => `<button class="bp-item ${bp.selected?.slug===item.slug?'active':''}" data-bp="${esc(item.slug)}"><strong>${esc(item.name)}</strong><small>${esc(item.slug)} · v${esc(item.version)} · ${esc(item.status)}</small><div class="bp-tags">${Object.values(item.stack||{}).slice(0,4).map(value=>`<span class="bp-tag">${esc(value)}</span>`).join('')}</div></button>`).join('') || '<div class="bp-empty">Nenhum Blueprint cadastrado.</div>';
    list.querySelectorAll('[data-bp]').forEach(button => button.onclick = () => select(button.dataset.bp));
    detail();
  }

  function detail() {
    const target=document.getElementById('bp-detail'); if (!target) return;
    const item=bp.selected; if (!item) { target.innerHTML='<div class="bp-empty">Selecione um Blueprint.</div>'; return; }
    target.innerHTML=`<div class="panel-title"><div><span class="eyebrow">BLUEPRINT</span><h3>${esc(item.name)}</h3></div><span class="status">${esc(item.status)}</span></div><div class="bp-grid"><div class="bp-kv"><small>Slug</small><strong>${esc(item.slug)}</strong></div><div class="bp-kv"><small>Versão</small><strong>${esc(item.version)}</strong></div><div class="bp-kv"><small>Tipo</small><strong>${esc(item.kind||'generic')}</strong></div><div class="bp-kv"><small>Arquivos</small><strong>${(item.files||[]).length}</strong></div></div><p>${esc(item.description||'Sem descrição.')}</p><div class="bp-tags">${(item.capabilities||[]).map(v=>`<span class="bp-tag">${esc(v)}</span>`).join('')}</div><h4>Stack</h4><pre class="bp-json">${esc(JSON.stringify(item.stack||{},null,2))}</pre><details><summary>Manifest completo</summary><pre class="bp-json">${esc(JSON.stringify(item,null,2))}</pre></details>`;
  }

  async function load() {
    note('Carregando Blueprints...');
    try { const [items,metrics]=await Promise.all([request('/api/blueprints?latest_only=true'),request('/api/blueprints/metrics')]); bp.items=Array.isArray(items)?items:[]; bp.metrics=metrics||{}; bp.selected=bp.items.find(item=>item.slug===bp.selected?.slug)||bp.items[0]||null; note(); render(); }
    catch(error){ note(`Falha ao carregar: ${error.message}`,'error'); }
  }

  async function select(slug) { try { bp.selected=await request(`/api/blueprints/${encodeURIComponent(slug)}`); render(); } catch(error){ note(error.message,'error'); } }

  function stackFromText(value) { const out={}; csv(value).forEach(item=>{ const parts=item.split('='); if(parts.length>1) out[parts.shift().trim()]=parts.join('=').trim(); }); return out; }

  async function match() {
    try {
      const payload={description:document.getElementById('bp-match-description').value,stack:stackFromText(document.getElementById('bp-match-stack').value),capabilities:csv(document.getElementById('bp-match-capabilities').value),tags:csv(document.getElementById('bp-match-tags').value),minimum_score:Number(document.getElementById('bp-match-score').value||.35),limit:5};
      bp.recommendations=await request('/api/blueprints/recommend',{method:'POST',body:JSON.stringify(payload)})||[];
      const target=document.getElementById('bp-match-results'); target.innerHTML=bp.recommendations.map((item,index)=>`<div class="bp-match-result"><strong>#${index+1} ${esc(item.blueprint?.name||item.blueprint_slug||item.slug||'')}</strong> · ${Math.round(Number(item.score||0)*100)}%<br><small>${esc((item.reasons||[]).join(' · '))}</small></div>`).join('')||'<div class="bp-empty">Nenhum Blueprint atingiu o score mínimo.</div>';
      note('Matcher executado.','ok');
    } catch(error){ note(`Falha no matcher: ${error.message}`,'error'); }
  }

  async function save() {
    try {
      const json=(id,fallback)=>{ const raw=document.getElementById(id).value.trim(); return raw?JSON.parse(raw):fallback; };
      const payload={slug:document.getElementById('bp-slug').value.trim(),name:document.getElementById('bp-name').value.trim(),version:document.getElementById('bp-version').value.trim(),status:document.getElementById('bp-status').value,kind:document.getElementById('bp-kind').value.trim()||'generic',description:document.getElementById('bp-description').value.trim(),stack:json('bp-stack',{}),capabilities:csv(document.getElementById('bp-capabilities').value),parameters:csv(document.getElementById('bp-parameters').value),tags:csv(document.getElementById('bp-tags').value),files:json('bp-files',[]),metadata:{},overwrite:false};
      if(!payload.slug||!payload.name||!payload.version) throw new Error('Slug, nome e versão são obrigatórios.');
      const created=await request('/api/blueprints',{method:'POST',body:JSON.stringify(payload)}); bp.selected=created; document.getElementById('bp-create').hidden=true; await load(); note(`Blueprint ${created.slug} v${created.version} salvo.`,'ok');
    } catch(error){ note(`Não foi possível salvar: ${error.message}`,'error'); }
  }

  const boot=()=>{ mount(); if(!document.getElementById('blueprints-admin-view')) setTimeout(mount,600); };
  document.addEventListener('devpilot:feature-ready', event => { if(event.detail?.feature==='admin') boot(); });
  document.addEventListener('devpilot:authenticated-ui-ready', boot, {once:true});
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,450),{once:true}); else setTimeout(boot,450);
})();