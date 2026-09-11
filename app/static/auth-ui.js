(() => {
  'use strict';

  const TOKEN_KEY = 'devpilot-token';
  const AUTH_MESSAGE_KEY = 'devpilot-auth-message';
  const modal = document.querySelector('#auth-modal');
  if (!modal) return;

  const root = document.documentElement;
  const SAFE_STYLE_ID = 'devpilot-auth-compositor-safe';
  const FETCH_TIMEOUT_MS = 3000;
  let bootstrapRequired = false;
  let localBootstrapAvailable = false;
  let resolveAuthReady;
  let runtimeHandoffStarted = false;

  function consumeAuthMessage(fallback = '') {
    const message = String(sessionStorage.getItem(AUTH_MESSAGE_KEY) || '').trim();
    sessionStorage.removeItem(AUTH_MESSAGE_KEY);
    return message || fallback;
  }

  function tokenExpired(token) {
    try {
      const parts = String(token || '').split('.');
      if (parts.length !== 3) return true;
      const payload = JSON.parse(decodeURIComponent(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(parts[1].length / 4) * 4, '=')).split('').map(char => `%${char.charCodeAt(0).toString(16).padStart(2, '0')}`).join('')));
      const exp = Number(payload?.exp || 0);
      return !Number.isFinite(exp) || exp <= Math.floor(Date.now() / 1000) + 5;
    } catch (_) { return true; }
  }

  function installCompositorSafeMode() {
    if (!document.getElementById(SAFE_STYLE_ID)) {
      const style = document.createElement('style');
      style.id = SAFE_STYLE_ID;
      style.textContent = `dialog::backdrop{background:#020811!important;backdrop-filter:none!important;-webkit-backdrop-filter:none!important}html.devpilot-auth-pending body{background:#07111f!important;background-image:none!important}html.devpilot-auth-pending .shell,html.devpilot-auth-pending .voice-dock,html.devpilot-auth-pending .toast{visibility:hidden!important}html.devpilot-auth-pending dialog{visibility:visible!important;box-shadow:0 18px 48px rgba(0,0,0,.55)!important;transform:none!important;animation:none!important;transition:none!important}html.devpilot-auth-pending *,html.devpilot-auth-pending *::before,html.devpilot-auth-pending *::after{animation-play-state:paused!important}#auth-modal:has(.public-home){width:min(1180px,calc(100vw - 24px));max-width:none;padding:0;border:0;background:transparent;overflow:auto}.public-home{box-sizing:border-box;min-height:min(760px,calc(100vh - 32px));padding:clamp(24px,5vw,68px);border:1px solid rgba(148,163,184,.18);border-radius:28px;color:#e5edf7;background:radial-gradient(circle at 50% -10%,rgba(56,189,248,.16),transparent 34%),linear-gradient(145deg,#07111f,#0a1423 55%,#07101d);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.public-nav{display:flex;align-items:center;justify-content:space-between;gap:18px}.public-brand{display:flex;align-items:center;gap:12px;font-weight:800;letter-spacing:-.02em}.public-brand-mark{display:grid;place-items:center;width:38px;height:38px;border-radius:12px;background:#38bdf8;color:#04111c;box-shadow:0 8px 28px rgba(56,189,248,.2)}.public-login{border:1px solid rgba(148,163,184,.26);background:rgba(15,23,42,.7);color:#f8fafc;border-radius:999px;padding:10px 18px;font-weight:700;cursor:pointer}.public-hero{max-width:820px;margin:clamp(54px,10vh,110px) auto 0;text-align:center}.public-kicker{display:inline-flex;gap:8px;align-items:center;color:#7dd3fc;font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.public-kicker::before{content:"";width:7px;height:7px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 5px rgba(34,197,94,.09)}.public-hero h1{margin:18px 0 14px;color:#f8fafc;font-size:clamp(38px,7vw,74px);line-height:.98;letter-spacing:-.055em}.public-hero p{max-width:700px;margin:0 auto;color:#94a3b8;font-size:clamp(16px,2vw,20px);line-height:1.65}.public-search{display:flex;gap:10px;max-width:760px;margin:34px auto 0;padding:8px;border:1px solid rgba(148,163,184,.22);border-radius:20px;background:rgba(2,8,17,.72);box-shadow:0 24px 80px rgba(0,0,0,.28)}.public-search input{flex:1;min-width:0;border:0;outline:0;padding:14px 16px;color:#f8fafc;background:transparent;font-size:16px}.public-search button{border:0;border-radius:14px;padding:0 22px;background:#38bdf8;color:#04111c;font-weight:850;cursor:pointer}.public-status{min-height:24px;margin:14px auto 0;color:#94a3b8;font-size:13px}.public-results{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;max-width:980px;margin:30px auto 0;text-align:left}.public-result{padding:20px;border:1px solid rgba(148,163,184,.16);border-radius:18px;background:rgba(15,23,42,.58)}.public-result small{color:#7dd3fc;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.public-result h3{margin:9px 0 7px;color:#f8fafc;font-size:18px}.public-result p{margin:0;color:#94a3b8;font-size:14px;line-height:1.55}.public-excerpt{margin-top:12px!important;padding-top:12px;border-top:1px solid rgba(148,163,184,.12);color:#cbd5e1!important}.public-empty{grid-column:1/-1;text-align:center;color:#64748b;padding:18px}.public-foot{margin-top:38px;text-align:center;color:#64748b;font-size:12px}@media(max-width:800px){#auth-modal:has(.public-home){width:100vw;height:100vh;max-height:none;margin:0}.public-home{min-height:100vh;border-radius:0;padding:22px 16px 34px}.public-hero{margin-top:64px}.public-search{flex-direction:column}.public-search button{min-height:48px}.public-results{grid-template-columns:1fr}}`;
      document.head.appendChild(style);
    }
    root.classList.add('devpilot-auth-pending');
  }

  installCompositorSafeMode();
  window.__devpilotAuthReady = new Promise(resolve => { resolveAuthReady = resolve; });
  const completeAuth = value => { if (typeof resolveAuthReady !== 'function') return; const resolve = resolveAuthReady; resolveAuthReady = null; resolve(Boolean(value)); };
  const showModal = () => { if (!modal.open) modal.showModal(); };
  const closeModal = () => { if (modal.open) modal.close(); };
  const revealDashboard = () => { root.classList.remove('devpilot-auth-pending'); closeModal(); window.requestAnimationFrame(() => document.dispatchEvent(new CustomEvent('devpilot:dashboard-revealed'))); };

  const installLogout = () => {
    const header = document.querySelector('.header-actions');
    if (!header || document.querySelector('#logout')) return;
    const button = document.createElement('button');
    button.id='logout'; button.className='ghost'; button.type='button'; button.textContent='Sair';
    button.addEventListener('click',()=>{localStorage.removeItem(TOKEN_KEY);location.reload();});
    header.prepend(button);
  };

  function handoffAuthenticatedRuntime(statusElement=null){
    if(runtimeHandoffStarted)return; runtimeHandoffStarted=true; installLogout(); if(statusElement)statusElement.textContent='Abrindo ambiente seguro…';
    const finish=()=>{if(!runtimeHandoffStarted)return;runtimeHandoffStarted=false;revealDashboard();};
    document.addEventListener('devpilot:authenticated-core-ready',finish,{once:true});
    queueMicrotask(()=>{if(window.__devpilotBoot?.phase==='ready')finish();}); completeAuth(true);
    window.setTimeout(()=>{if(!root.classList.contains('devpilot-auth-pending'))return;if(window.__devpilotBoot?.phase==='failed'){runtimeHandoffStarted=false;if(statusElement)statusElement.textContent='Falha ao carregar a interface. Atualize a página.';}},8000);
  }

  async function fetchWithTimeout(url,options={},timeout=FETCH_TIMEOUT_MS){const controller=new AbortController();const timer=window.setTimeout(()=>controller.abort(),timeout);try{return await fetch(url,{...options,signal:controller.signal});}finally{window.clearTimeout(timer);}}
  async function readStatus(){try{const response=await fetchWithTimeout('/api/auth/status',{cache:'no-store'});const data=await response.json();bootstrapRequired=Boolean(data.bootstrap_required);localBootstrapAvailable=Boolean(data.local_bootstrap_available);}catch(_){bootstrapRequired=false;localBootstrapAvailable=false;}}
  async function validateToken(token){if(!token||tokenExpired(token)){localStorage.removeItem(TOKEN_KEY);return false;}try{const response=await fetchWithTimeout('/api/auth/me',{headers:{Authorization:`Bearer ${token}`},cache:'no-store'});if(response.ok)return true;if([401,403,404].includes(response.status))localStorage.removeItem(TOKEN_KEY);}catch(_){}return false;}
  function renderResults(container,data){const results=Array.isArray(data?.results)?data.results:[];if(!results.length){container.innerHTML='<div class="public-empty">Nenhum projeto público encontrado para esta busca.</div>';return;}container.innerHTML=results.map(item=>{const excerpt=item.excerpts?.[0]?.text||'';const badge=item.match==='rag'?'RAG · conhecimento do projeto':'Projeto público';return `<article class="public-result"><small>${badge}</small><h3>${escapeHtml(item.name||'')}</h3><p>${escapeHtml(item.description||'Projeto desenvolvido com DevPilot.')}</p>${excerpt?`<p class="public-excerpt">${escapeHtml(excerpt)}</p>`:''}</article>`;}).join('');}
  function escapeHtml(value){return String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));}

  function renderPublicHome(message=''){
    installCompositorSafeMode();runtimeHandoffStarted=false;modal.removeAttribute('data-devpilot-auth-loading');
    modal.innerHTML=`<section class="public-home"><nav class="public-nav"><div class="public-brand"><span class="public-brand-mark">D</span><span>DevPilot</span></div><button class="public-login" id="public-login" type="button">Entrar</button></nav><div class="public-hero"><span class="public-kicker">Conhecimento vivo dos projetos</span><h1>Descubra o que já foi construído.</h1><p>Pesquise projetos públicos desenvolvidos com o DevPilot. O buscador consulta descrições e, quando disponível, o RAG de cada projeto para encontrar informação técnica relevante.</p><form class="public-search" id="public-search"><input id="public-query" type="search" maxlength="180" autocomplete="off" placeholder="Ex.: sistema de reciclagem, música ao vivo, compliance…" aria-label="Buscar projetos"><button type="submit">Buscar</button></form><div class="public-status" id="public-status">${escapeHtml(message||'Pesquise por ideia, tecnologia, negócio ou funcionalidade.')}</div></div><div class="public-results" id="public-results"></div><div class="public-foot">DevPilot · desenvolvimento automatizado, auditável e orientado por conhecimento.</div></section>`;
    showModal();
    const form=document.querySelector('#public-search'),input=document.querySelector('#public-query'),status=document.querySelector('#public-status'),results=document.querySelector('#public-results');
    document.querySelector('#public-login')?.addEventListener('click',()=>renderLoginForm());
    const search=async(query='')=>{if(!results||!status)return;status.textContent=query?'Consultando projetos e conhecimento RAG…':'Projetos públicos recentes';try{const response=await fetchWithTimeout(`/api/investia/catalog/search?q=${encodeURIComponent(query)}&limit=6`,{cache:'no-store'},8000);const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error('Busca indisponível');renderResults(results,data);status.textContent=query?`${data.results?.length||0} resultado(s) · ${data.rag_available?'RAG ativo':'busca por catálogo'}`:'Projetos públicos recentes';}catch(_){results.innerHTML='<div class="public-empty">A busca está temporariamente indisponível. Você ainda pode entrar no DevPilot.</div>';status.textContent='Não foi possível consultar o catálogo agora.';}};
    form?.addEventListener('submit',event=>{event.preventDefault();void search(String(input?.value||'').trim());});void search('');
  }

  function renderLoginForm(message=''){
    installCompositorSafeMode();runtimeHandoffStarted=false;modal.removeAttribute('data-devpilot-auth-loading');
    modal.innerHTML=`<form class="modal" id="auth-form"><span class="eyebrow">ACESSO</span><h2>Entrar no DevPilot</h2><p id="auth-help">Use seu e-mail e senha.</p><label>E-mail<input id="auth-email" type="email" autocomplete="username" required></label><label>Senha<input id="auth-password" type="password" autocomplete="current-password" minlength="8" required></label><label id="auth-bootstrap-row" style="display:none">Token de bootstrap<input id="auth-bootstrap" type="password" autocomplete="off"></label><div id="auth-error" class="hint" role="alert"></div><div style="display:flex;gap:10px;flex-wrap:wrap"><button class="primary" id="auth-submit" type="submit">Entrar</button><button class="ghost" id="auth-back" type="button">Voltar</button></div></form>`;
    const form=document.querySelector('#auth-form'),errorBox=document.querySelector('#auth-error'),submit=document.querySelector('#auth-submit'),bootstrapRow=document.querySelector('#auth-bootstrap-row'),help=document.querySelector('#auth-help');
    if(errorBox&&message)errorBox.textContent=message;if(bootstrapRow)bootstrapRow.style.display=bootstrapRequired&&!localBootstrapAvailable?'grid':'none';if(help)help.textContent=bootstrapRequired?(localBootstrapAvailable?'Primeiro acesso neste Linux: informe e-mail e senha.':'Primeiro acesso remoto: informe também o token de bootstrap.'):'Use seu e-mail e senha.';if(submit)submit.textContent=bootstrapRequired?'Criar Super Admin e entrar':'Entrar';
    document.querySelector('#auth-back')?.addEventListener('click',()=>renderPublicHome());
    form?.addEventListener('submit',async event=>{event.preventDefault();if(!errorBox||!submit)return;errorBox.textContent='';submit.disabled=true;submit.textContent='Validando…';const payload={email:document.querySelector('#auth-email')?.value.trim()||'',password:document.querySelector('#auth-password')?.value||''};const headers={'Content-Type':'application/json'};let endpoint='/api/auth/login';if(bootstrapRequired){endpoint='/api/auth/bootstrap';if(!localBootstrapAvailable){const bootstrapToken=document.querySelector('#auth-bootstrap')?.value.trim()||'';if(!bootstrapToken){errorBox.textContent='Informe o token de bootstrap.';submit.disabled=false;submit.textContent='Entrar';return;}headers.Authorization=`Bearer ${bootstrapToken}`;}}try{const response=await fetchWithTimeout(endpoint,{method:'POST',headers,body:JSON.stringify(payload),cache:'no-store'},8000);const data=await response.json().catch(()=>({}));if(!response.ok||!data.access_token)throw new Error(typeof data.detail==='string'?data.detail:'Falha na autenticação');localStorage.setItem(TOKEN_KEY,data.access_token);sessionStorage.removeItem(AUTH_MESSAGE_KEY);document.dispatchEvent(new CustomEvent('devpilot:login-complete'));handoffAuthenticatedRuntime(errorBox);}catch(error){errorBox.textContent=error?.name==='AbortError'?'O servidor demorou para responder. Tente novamente.':(error.message||'Falha na autenticação');submit.disabled=false;submit.textContent=bootstrapRequired?'Criar Super Admin e entrar':'Entrar';}});
    showModal();
  }

  function renderResumeSession(token){if(!token||tokenExpired(token)){localStorage.removeItem(TOKEN_KEY);renderPublicHome(consumeAuthMessage('Sua sessão expirou. Entre novamente.'));return;}installCompositorSafeMode();runtimeHandoffStarted=false;modal.removeAttribute('data-devpilot-auth-loading');modal.innerHTML=`<div class="modal" id="auth-resume"><span class="eyebrow">SESSÃO SALVA</span><h2>Continuar no DevPilot?</h2><p>Existe uma sessão anterior neste navegador. O dashboard só será iniciado depois da sua confirmação.</p><div id="auth-resume-error" class="hint" role="alert"></div><div style="display:flex;gap:10px;flex-wrap:wrap"><button class="primary" id="auth-resume-submit" type="button">Continuar sessão</button><button class="ghost" id="auth-other-account" type="button">Entrar com outra conta</button><button class="ghost" id="auth-public-home" type="button">Página inicial</button></div></div>`;showModal();const resume=document.querySelector('#auth-resume-submit'),errorBox=document.querySelector('#auth-resume-error');resume?.addEventListener('click',async()=>{resume.disabled=true;resume.textContent='Validando…';const valid=await validateToken(token);if(!valid){localStorage.removeItem(TOKEN_KEY);renderLoginForm('A sessão não é mais válida. Entre novamente.');return;}handoffAuthenticatedRuntime(errorBox);});document.querySelector('#auth-other-account')?.addEventListener('click',()=>{localStorage.removeItem(TOKEN_KEY);renderLoginForm();});document.querySelector('#auth-public-home')?.addEventListener('click',()=>renderPublicHome());}

  const isInitialLoadingPlaceholder=()=>modal.dataset.devpilotAuthLoading==='true'||modal.textContent?.includes('Carregando DevPilot')===true;

  const boot=async()=>{
    const fallback=window.setTimeout(()=>{if((!modal.open||isInitialLoadingPlaceholder())&&root.classList.contains('devpilot-auth-pending')){if(modal.open&&isInitialLoadingPlaceholder())closeModal();const token=String(localStorage.getItem(TOKEN_KEY)||'').trim();if(token&&!tokenExpired(token))renderResumeSession(token);else{if(token)localStorage.removeItem(TOKEN_KEY);renderPublicHome(consumeAuthMessage(''));}}},FETCH_TIMEOUT_MS+500);
    await readStatus();window.clearTimeout(fallback);
    if(modal.open&&!isInitialLoadingPlaceholder())return;
    if(modal.open&&isInitialLoadingPlaceholder())closeModal();
    const token=String(localStorage.getItem(TOKEN_KEY)||'').trim();
    if(!token||tokenExpired(token)){if(token)localStorage.removeItem(TOKEN_KEY);renderPublicHome(consumeAuthMessage(token?'Sua sessão expirou. Entre novamente.':''));return;}
    renderResumeSession(token);
  };

  void boot();
})();