(()=>{
  const q=s=>document.querySelector(s);
  const qa=s=>[...document.querySelectorAll(s)];
  const roles=new Set(['SUPER_ADMIN','OWNER','ADMIN']);
  const names={openai:'OpenAI',anthropic:'Anthropic',google:'Google Gemini',custom:'Custom'};
  const icons={openai:'O',anthropic:'A',google:'G',custom:'C'};
  let role='VIEWER';
  let catalog={};
  let connections=[];
  let editor={connection:null,available:[],recommended:[],selected:new Set()};

  const esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const manage=()=>roles.has(role);

  async function api(path,opt={}){
    const headers={Authorization:`Bearer ${localStorage.getItem('devpilot-token')||''}`,...(opt.headers||{})};
    if(opt.body)headers['Content-Type']='application/json';
    const r=await fetch(`/api${path}`,{...opt,headers});
    const d=r.status===204?null:await r.json().catch(()=>({}));
    if(!r.ok)throw Error(typeof d?.detail==='string'?d.detail:'Falha na operação');
    return d;
  }

  function note(m){
    if(typeof toast==='function')toast(m);
    else console.info(m);
  }

  function ensureEditDialog(){
    let dialog=q('#provider-model-editor');
    if(dialog)return dialog;
    dialog=document.createElement('dialog');
    dialog.id='provider-model-editor';
    dialog.innerHTML=`<form class="modal provider-model-editor" id="provider-model-editor-form">
      <button class="close" type="button" aria-label="Fechar">×</button>
      <span class="eyebrow">MODELOS DA CONEXÃO</span>
      <h2 id="pc-edit-title">Atualizar modelos</h2>
      <p class="provider-edit-intro">Você não precisa manter todo o catálogo do provedor. Para o DevPilot, normalmente <strong>1 a 6 modelos</strong> bem escolhidos são suficientes.</p>
      <div id="pc-edit-auto">
        <label>Buscar modelo<input id="pc-edit-search" type="search" placeholder="Ex.: gpt-5, claude, gemini"></label>
        <label>Modelos usados pelo DevPilot<select id="pc-edit-models" multiple size="12"></select></label>
        <div class="provider-edit-toolbar">
          <button class="ghost" id="pc-edit-recommended" type="button">Usar recomendados</button>
          <small id="pc-edit-count"></small>
        </div>
      </div>
      <label id="pc-edit-manual" hidden>Modelos, separados por vírgula<input id="pc-edit-manual-input" placeholder="modelo-a,modelo-b"></label>
      <p class="hint" id="pc-edit-status">Consultando catálogo atual…</p>
      <button class="primary" type="submit">Salvar modelos</button>
    </form>`;
    document.body.append(dialog);
    dialog.querySelector('.close').onclick=()=>dialog.close();
    dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()});
    q('#pc-edit-search').addEventListener('input',renderEditorOptions);
    q('#pc-edit-models').addEventListener('change',syncEditorSelection);
    q('#pc-edit-recommended').addEventListener('click',useRecommendedModels);
    q('#provider-model-editor-form').onsubmit=saveEditedModels;
    return dialog;
  }

  function install(){
    if(!q('link[href="/assets/provider-models.css"]')){
      const l=document.createElement('link');
      l.rel='stylesheet';
      l.href='/assets/provider-models.css';
      document.head.append(l);
    }

    const v=q('#providers-view');
    if(v)v.innerHTML=`<div class="provider-shell">
      <section class="provider-hero">
        <div><span class="eyebrow">GATEWAY MULTIMODELO · AGENTOS</span><h2>Orquestre modelos sem ficar preso a <em>um fornecedor.</em></h2><p>Conecte provedores, valide credenciais nos catálogos oficiais e mantenha somente os modelos que o DevPilot realmente usa.</p></div>
        <div class="provider-hero-actions"><button class="ghost" id="pc-refresh">↻ Atualizar catálogos</button><button class="primary" id="pc-connect">+ Conectar IA</button></div>
      </section>
      <div class="provider-readonly" id="pc-readonly">Modo de consulta: apenas perfis administrativos alteram provedores.</div>
      <div class="provider-metrics" id="pc-metrics"></div>
      <div class="provider-grid">
        <section class="provider-panel"><div class="provider-panel-head"><div><span class="eyebrow">CONEXÕES</span><h3>Provedores configurados</h3><p>Segredos nunca retornam ao navegador. A lista de modelos pode ser atualizada sem trocar a API key.</p></div></div><div class="provider-list" id="providers-list"></div></section>
        <section class="provider-panel"><div class="provider-panel-head"><div><span class="eyebrow">CATÁLOGO</span><h3>Modelos disponíveis</h3><p>Ao vivo com credencial válida; referência segura nos demais casos.</p></div></div><div class="catalog-list" id="pc-catalog"></div></section>
      </div>
      <div class="provider-security"><b>✓</b><div><strong>Vault protegido</strong><p>API keys ficam criptografadas no servidor; auditoria registra somente provedor, conexão e quantidade de modelos.</p></div></div>
    </div>`;

    const m=q('#provider-modal');
    if(m)m.innerHTML=`<form class="modal" id="provider-form">
      <button class="close" type="button">×</button><span class="eyebrow">PROVEDOR DE IA</span><h2>Conectar modelo</h2>
      <div class="provider-modal-note"><b>✦</b><span>A credencial é validada na API oficial antes de ser salva.</span></div>
      <div class="form-grid"><label>Provedor<select name="provider" id="pc-provider"><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option><option value="google">Google Gemini</option><option value="custom">Custom</option></select></label><label>Nome da conexão<input name="label" value="Principal" required></label></div>
      <label>API key<input name="api_key" id="pc-key" type="password" autocomplete="off" required></label>
      <div id="pc-auto"><label>Modelos que serão usados<select id="pc-models" multiple size="8"></select></label><p class="hint">Não é necessário salvar o catálogo inteiro. O DevPilot pré-seleciona até 6 modelos recomendados.</p></div>
      <label id="pc-manual" hidden>Modelos, separados por vírgula<input name="models_manual" placeholder="modelo-a,modelo-b"></label>
      <div class="model-catalog-row"><small id="pc-status" class="model-catalog-status">Catálogo de referência carregado.</small><div class="provider-inline-actions"><button class="link" id="pc-recommended" type="button">Usar recomendados</button><button class="link" id="pc-discover" type="button">Consultar API oficial</button></div></div>
      <p class="hint">A chave é criptografada no servidor e nunca retorna pela API.</p><button class="primary" type="submit">Validar e salvar conexão</button>
    </form>`;

    q('#pc-connect')?.addEventListener('click',openModal);
    q('#pc-refresh')?.addEventListener('click',()=>load(true));
    q('#provider-modal .close')?.addEventListener('click',()=>m.close());
    q('#pc-provider')?.addEventListener('change',()=>modalModels(true));
    q('#pc-key')?.addEventListener('change',discover);
    q('#pc-discover')?.addEventListener('click',discover);
    q('#pc-recommended')?.addEventListener('click',selectConnectRecommendations);
    if(q('#provider-form'))q('#provider-form').onsubmit=save;
    ensureEditDialog();
  }

  function metrics(){
    const vals=[
      ['Conexões ativas',connections.filter(x=>x.enabled).length],
      ['Provedores',new Set(connections.map(x=>x.provider)).size],
      ['Modelos selecionados',new Set(connections.flatMap(x=>x.models||[])).size],
      ['Catálogos ao vivo',Object.values(catalog).filter(x=>x?.source==='live').length],
    ];
    if(q('#pc-metrics'))q('#pc-metrics').innerHTML=vals.map(([a,b])=>`<div class="provider-metric"><span>${a}</span><strong>${b}</strong></div>`).join('');
  }

  function chips(ms=[]){
    return (ms.length?ms.slice(0,6):['catálogo automático']).map(x=>`<span class="provider-chip">${esc(x)}</span>`).join('')+(ms.length>6?`<span class="provider-chip">+${ms.length-6}</span>`:'');
  }

  function renderConnections(){
    const t=q('#providers-list');
    if(!t)return;
    if(!connections.length){
      t.innerHTML='<div class="provider-empty">Nenhuma conexão cadastrada. O catálogo de referência continua disponível.</div>';
      return;
    }
    t.innerHTML=connections.map(x=>{
      const count=(x.models||[]).length;
      const advice=count>6?`<p class="provider-model-advice">${count} modelos selecionados. Você pode reduzir para 1–6 sem perder o catálogo disponível.</p>`:'';
      return `<article class="provider-card">
        <div class="provider-card-top"><div class="provider-brand"><span class="provider-icon">${icons[x.provider]||'IA'}</span><div><h4>${esc(x.label)}</h4><small>${esc(names[x.provider]||x.provider)} · ${count} modelo(s) selecionado(s)</small></div></div><span class="provider-status ${x.enabled?'':'paused'}">${x.enabled?'● ATIVO':'Ⅱ PAUSADO'}</span></div>
        <div class="provider-model-chips">${chips(x.models)}</div>${advice}
        ${manage()?`<div class="provider-card-actions"><button class="link pc-edit" data-id="${x.id}">Editar modelos</button><button class="link pc-toggle" data-id="${x.id}" data-on="${x.enabled?'1':'0'}">${x.enabled?'Pausar':'Ativar'}</button><button class="link provider-danger pc-delete" data-id="${x.id}">Remover</button></div>`:''}
      </article>`;
    }).join('');
    qa('.pc-edit').forEach(b=>b.onclick=()=>openEditor(b.dataset.id));
    qa('.pc-toggle').forEach(b=>b.onclick=()=>toggle(b));
    qa('.pc-delete').forEach(b=>b.onclick=()=>remove(b));
  }

  function renderCatalog(){
    const t=q('#pc-catalog');
    if(!t)return;
    t.innerHTML=['openai','anthropic','google','custom'].map(p=>{
      const e=catalog[p]||{source:'reference',models:[]};
      const ms=e.models||[];
      const txt=ms.slice(0,5).map(x=>x.label===x.id?x.id:`${x.label} (${x.id})`).join(' · ');
      return `<article class="catalog-card"><div class="catalog-row"><strong>${names[p]}</strong><span class="catalog-source ${esc(e.source)}">${esc(e.source)}</span></div><p class="catalog-models">${esc(ms.length?txt+(ms.length>5?` · +${ms.length-5}`:''):e.warning||'Catálogo manual')}</p></article>`;
    }).join('');
  }

  async function load(refresh=false){
    try{
      const me=await api('/auth/me');
      role=String(me.role||'VIEWER').toUpperCase();
      let refreshed={};
      if(refresh&&manage()){
        const result=await api('/providers/model-catalog/refresh',{method:'POST'});
        refreshed=result?.providers||{};
        note('Catálogos atualizados sem alterar os modelos selecionados');
      }
      const [c,k]=await Promise.all([api('/providers'),api('/providers/model-catalog')]);
      connections=c||[];
      catalog={...(k?.providers||{}),...refreshed};
      if(q('#pc-connect'))q('#pc-connect').hidden=!manage();
      if(q('#pc-refresh'))q('#pc-refresh').hidden=!manage();
      q('#pc-readonly')?.classList.toggle('visible',!manage());
      metrics();
      renderConnections();
      renderCatalog();
    }catch(e){note(e.message)}
  }

  function recommendedIds(entry){
    return (entry?.recommended_models||[]).map(x=>typeof x==='string'?x:x.id).filter(Boolean);
  }

  function modalModels(preferRecommended=false){
    const p=q('#pc-provider')?.value||'openai';
    const a=q('#pc-auto');
    const m=q('#pc-manual');
    const s=q('#pc-status');
    const sel=q('#pc-models');
    if(!a||!m||!s||!sel)return;
    s.classList.remove('error');
    if(p==='custom'){
      a.hidden=true;
      m.hidden=false;
      s.textContent='Catálogo manual para provedor customizado.';
      return;
    }
    a.hidden=false;
    m.hidden=true;
    const e=catalog[p];
    const ms=e?.models||[];
    const recommended=new Set(recommendedIds(e));
    sel.innerHTML=ms.map(x=>`<option value="${esc(x.id)}" ${preferRecommended&&recommended.has(x.id)?'selected':''}>${esc(x.label===x.id?x.id:`${x.label} — ${x.id}`)}</option>`).join('');
    if(preferRecommended&&!sel.selectedOptions.length){
      [...sel.options].slice(0,Math.min(6,sel.options.length)).forEach(option=>{option.selected=true});
    }
    s.textContent=e?.source==='live'?`Catálogo ao vivo: ${ms.length} disponível(is).`:e?.source==='stored'?`Catálogo salvo: ${ms.length} item(ns). Consulte a API oficial para ver opções atuais.`:`Catálogo de referência: ${ms.length} item(ns). Informe a API key para validar sua conta.`;
  }

  function selectConnectRecommendations(){
    const p=q('#pc-provider')?.value||'openai';
    if(p==='custom')return;
    const sel=q('#pc-models');
    const recommended=new Set(recommendedIds(catalog[p]));
    [...sel.options].forEach(option=>{option.selected=recommended.has(option.value)});
    if(!sel.selectedOptions.length)[...sel.options].slice(0,Math.min(6,sel.options.length)).forEach(option=>{option.selected=true});
    note(`${sel.selectedOptions.length} modelo(s) recomendado(s) selecionado(s)`);
  }

  function openModal(){
    if(!manage())return;
    q('#provider-form')?.reset();
    q('#provider-modal')?.showModal();
    modalModels(true);
  }

  async function discover(){
    const p=q('#pc-provider')?.value||'openai';
    const key=q('#pc-key')?.value.trim()||'';
    const b=q('#pc-discover');
    const s=q('#pc-status');
    if(p==='custom'){modalModels();return}
    if(key.length<8){s.textContent='Informe a API key para consultar os modelos atuais.';return}
    b.disabled=true;
    s.classList.remove('error');
    s.textContent='Consultando a API oficial do provedor…';
    try{
      catalog[p]=await api('/providers/discover-models',{method:'POST',body:JSON.stringify({provider:p,api_key:key})});
      modalModels(true);
    }catch(e){
      s.classList.add('error');
      s.textContent=e.message;
    }finally{b.disabled=false}
  }

  async function save(ev){
    ev.preventDefault();
    const f=ev.currentTarget;
    const d=new FormData(f);
    const p=String(d.get('provider'));
    const models=p==='custom'
      ?String(d.get('models_manual')||'').split(',').map(x=>x.trim()).filter(Boolean)
      :[...q('#pc-models').selectedOptions].map(x=>x.value);
    const btn=f.querySelector('button[type=submit]');
    const old=btn.textContent;
    btn.disabled=true;
    btn.textContent='Validando…';
    try{
      await api('/providers/connect',{method:'POST',body:JSON.stringify({provider:p,label:d.get('label'),api_key:d.get('api_key'),models})});
      q('#provider-modal').close();
      f.reset();
      note('Conexão validada e salva com um conjunto enxuto de modelos');
      await load();
    }catch(e){note(e.message)}
    finally{btn.disabled=false;btn.textContent=old}
  }

  function editorModels(){
    const map=new Map(editor.available.map(model=>[model.id,model]));
    for(const id of editor.selected){
      if(!map.has(id))map.set(id,{id,label:id});
    }
    return [...map.values()];
  }

  function renderEditorOptions(){
    if(!editor.connection)return;
    const sel=q('#pc-edit-models');
    const term=(q('#pc-edit-search')?.value||'').trim().toLowerCase();
    const models=editorModels().filter(model=>!term||`${model.id} ${model.label}`.toLowerCase().includes(term));
    sel.innerHTML=models.map(model=>`<option value="${esc(model.id)}" ${editor.selected.has(model.id)?'selected':''}>${esc(model.label===model.id?model.id:`${model.label} — ${model.id}`)}</option>`).join('');
    updateEditorCount();
  }

  function syncEditorSelection(){
    const sel=q('#pc-edit-models');
    [...sel.options].forEach(option=>{
      if(option.selected)editor.selected.add(option.value);
      else editor.selected.delete(option.value);
    });
    updateEditorCount();
  }

  function updateEditorCount(){
    const count=q('#pc-edit-count');
    if(count)count.textContent=`${editor.selected.size} selecionado(s) · ${editor.available.length} disponível(is)`;
  }

  function useRecommendedModels(){
    const ids=editor.recommended.map(model=>model.id).filter(Boolean);
    if(!ids.length){note('O catálogo não retornou recomendações para esta conexão');return}
    editor.selected=new Set(ids);
    renderEditorOptions();
    note(`${ids.length} modelo(s) recomendado(s) selecionado(s)`);
  }

  async function openEditor(connectionId){
    if(!manage())return;
    const connection=connections.find(item=>item.id===connectionId);
    if(!connection)return;
    const dialog=ensureEditDialog();
    const status=q('#pc-edit-status');
    const auto=q('#pc-edit-auto');
    const manual=q('#pc-edit-manual');
    q('#pc-edit-title').textContent=`Modelos de ${connection.label}`;
    q('#pc-edit-search').value='';
    status.classList.remove('error');
    status.textContent='Consultando catálogo atual sem expor a API key…';
    editor={connection,available:[],recommended:[],selected:new Set(connection.models||[])};
    if(connection.provider==='custom'){
      auto.hidden=true;
      manual.hidden=false;
      q('#pc-edit-manual-input').value=(connection.models||[]).join(', ');
    }else{
      auto.hidden=false;
      manual.hidden=true;
      q('#pc-edit-models').innerHTML='';
    }
    if(!dialog.open)dialog.showModal();
    if(connection.provider==='custom'){
      status.textContent='Edite manualmente os IDs usados por esta conexão.';
      return;
    }
    try{
      const data=await api(`/providers/${connection.id}/models`);
      editor.available=data?.models||[];
      editor.recommended=data?.recommended_models||[];
      editor.selected=new Set(data?.selected_models||connection.models||[]);
      renderEditorOptions();
      status.textContent=data?.warning?`${data.warning} Você ainda pode reduzir a seleção atual.`:`Catálogo ${data?.source==='live'?'ao vivo':'salvo'} carregado. Escolha somente os modelos necessários.`;
      status.classList.toggle('error',Boolean(data?.warning));
    }catch(e){
      status.classList.add('error');
      status.textContent=e.message;
    }
  }

  async function saveEditedModels(ev){
    ev.preventDefault();
    if(!editor.connection)return;
    const connection=editor.connection;
    let models=[];
    if(connection.provider==='custom'){
      models=(q('#pc-edit-manual-input')?.value||'').split(',').map(x=>x.trim()).filter(Boolean);
    }else{
      syncEditorSelection();
      models=[...editor.selected];
    }
    if(!models.length){note('Selecione ao menos um modelo');return}
    const btn=ev.currentTarget.querySelector('button[type=submit]');
    const old=btn.textContent;
    btn.disabled=true;
    btn.textContent='Salvando…';
    try{
      const result=await api(`/providers/${connection.id}/models`,{method:'PATCH',body:JSON.stringify({models})});
      q('#provider-model-editor').close();
      note(`${result.model_count||models.length} modelo(s) salvo(s) para ${connection.label}`);
      await load();
    }catch(e){note(e.message)}
    finally{btn.disabled=false;btn.textContent=old}
  }

  async function toggle(b){
    const enabled=b.dataset.on!=='1';
    b.disabled=true;
    try{
      await api(`/providers/${b.dataset.id}/enabled`,{method:'PATCH',body:JSON.stringify({enabled})});
      note(enabled?'Conexão ativada':'Conexão pausada');
      await load();
    }catch(e){note(e.message)}
    finally{b.disabled=false}
  }

  async function remove(b){
    if(!confirm('Remover esta conexão de IA? A credencial criptografada será excluída.'))return;
    b.disabled=true;
    try{
      await api(`/providers/${b.dataset.id}`,{method:'DELETE'});
      note('Conexão removida');
      await load();
    }catch(e){note(e.message)}
    finally{b.disabled=false}
  }

  install();
  try{loadProviders=load}catch{}
  if(q('#providers-view')?.classList.contains('active'))load();
})();
