(()=>{
  const q=s=>document.querySelector(s);
  const token=()=>localStorage.getItem('devpilot-token')||'';
  let lastCatalog=null;
  let catalogBusy=false;

  async function api(path,opt={}){
    const headers={Authorization:`Bearer ${token()}`,...(opt.headers||{})};
    if(opt.body)headers['Content-Type']='application/json';
    const response=await fetch(`/api${path}`,{...opt,headers});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw Error(typeof data?.detail==='string'?data.detail:'Falha ao configurar Ollama');
    return data;
  }

  function note(message){
    if(typeof toast==='function')toast(message);
    else console.info(message);
  }

  function providerIsOllama(){
    return q('#pc-provider')?.value==='ollama';
  }

  function installOption(){
    const select=q('#pc-provider');
    if(!select||select.querySelector('option[value="ollama"]'))return;
    const option=document.createElement('option');
    option.value='ollama';
    option.textContent='Ollama Local · Linux de homologação';
    const custom=select.querySelector('option[value="custom"]');
    select.insertBefore(option,custom||null);
  }

  function keyLabel(){
    const key=q('#pc-key');
    return key?.closest('label')||null;
  }

  function applyMode(){
    installOption();
    const isOllama=providerIsOllama();
    const key=q('#pc-key');
    const label=keyLabel();
    const discover=q('#pc-discover');
    const status=q('#pc-status');
    if(key){
      key.required=!isOllama;
      if(isOllama)key.value='';
    }
    if(label)label.hidden=isOllama;
    if(discover)discover.textContent=isOllama?'Detectar no Linux':'Consultar API oficial';
    if(isOllama&&status){
      status.classList.remove('error');
      status.textContent='O DevPilot acessará o Linux de homologação, iniciará a instância Ollama e detectará os modelos instalados.';
      discoverOllama(true);
    }
  }

  function fillModels(data,preferRecommended=true){
    lastCatalog=data;
    const select=q('#pc-models');
    if(!select)return;
    const recommended=new Set((data?.recommended_models||[]).map(item=>item?.id||item));
    const models=data?.models||[];
    select.innerHTML=models.map(item=>{
      const id=String(item?.id||item||'');
      const label=String(item?.label||id);
      const selected=preferRecommended&&recommended.has(id)?' selected':'';
      return `<option value="${id.replaceAll('&','&amp;').replaceAll('"','&quot;')}"${selected}>${label.replaceAll('&','&amp;').replaceAll('<','&lt;')}</option>`;
    }).join('');
    if(preferRecommended&&!select.selectedOptions.length){
      [...select.options].slice(0,Math.min(2,select.options.length)).forEach(option=>{option.selected=true});
    }
    const status=q('#pc-status');
    if(status){
      const prefix=data?.started?'Instância Ollama iniciada. ':'Instância Ollama já estava ativa. ';
      status.textContent=`${prefix}${models.length} modelo(s) detectado(s) no Linux de homologação.${data?.warning?` ${data.warning}`:''}`;
      status.classList.toggle('error',Boolean(data?.warning)&&!models.length);
    }
  }

  async function discoverOllama(silent=false){
    if(!providerIsOllama()||catalogBusy)return;
    catalogBusy=true;
    const button=q('#pc-discover');
    if(button)button.disabled=true;
    const status=q('#pc-status');
    if(status)status.textContent='Conectando ao Linux de homologação e verificando Ollama…';
    try{
      const data=await api('/ollama-provider/discover',{method:'POST',body:'{}'});
      fillModels(data,true);
      if(!silent)note(data?.started?'Ollama iniciado no Linux de homologação':'Ollama já está ativo no Linux de homologação');
      refreshCatalogCard(data);
    }catch(error){
      if(status){status.classList.add('error');status.textContent=error.message}
      if(!silent)note(error.message);
    }finally{
      catalogBusy=false;
      if(button)button.disabled=false;
    }
  }

  async function saveOllama(event){
    if(!providerIsOllama())return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const form=event.currentTarget;
    const label=String(new FormData(form).get('label')||'Ollama Homologação').trim();
    const models=[...q('#pc-models').selectedOptions].map(option=>option.value);
    const button=form.querySelector('button[type="submit"]');
    const original=button?.textContent||'';
    if(button){button.disabled=true;button.textContent='Iniciando Ollama…'}
    try{
      const result=await api('/ollama-provider/connect',{
        method:'POST',
        body:JSON.stringify({label,models}),
      });
      q('#provider-modal')?.close();
      form.reset();
      note(result.runtime_started?'Ollama iniciado e cadastrado como IA':'Ollama cadastrado e pronto para fallback');
      if(typeof loadProviders==='function')await loadProviders();
      await loadCatalogCard();
    }catch(error){
      note(error.message);
    }finally{
      if(button){button.disabled=false;button.textContent=original}
    }
  }

  function polishConnections(){
    document.querySelectorAll('#providers-list .provider-card').forEach(card=>{
      const small=card.querySelector('small');
      if(!small||!small.textContent.trim().toLowerCase().startsWith('ollama ·'))return;
      small.textContent=small.textContent.replace(/^ollama/i,'Ollama Local');
      const icon=card.querySelector('.provider-icon');
      if(icon)icon.textContent='OL';
    });
  }

  function refreshCatalogCard(data){
    const root=q('#pc-catalog');
    if(!root)return;
    let article=root.querySelector('[data-ollama-catalog="1"]');
    if(!article){
      article=document.createElement('article');
      article.className='catalog-card';
      article.dataset.ollamaCatalog='1';
      article.innerHTML='<div class="catalog-row"><strong>Ollama Local</strong><span class="catalog-source"></span></div><p class="catalog-models"></p>';
      root.append(article);
    }
    const models=data?.models||[];
    const preview=models.slice(0,5).map(item=>String(item?.label||item?.id||item)).join(' · ');
    const source=article.querySelector('.catalog-source');
    const sourceName=data?.source==='live'?'live':'reference';
    if(source){source.className=`catalog-source ${sourceName}`;source.textContent=sourceName}
    const text=article.querySelector('.catalog-models');
    if(text)text.textContent=preview||(data?.warning||'Linux de homologação ainda não consultado.');
  }

  async function loadCatalogCard(){
    try{
      const data=await api('/ollama-provider/catalog');
      lastCatalog=data;
      refreshCatalogCard(data);
    }catch{}
  }

  function install(){
    installOption();
    q('#pc-provider')?.addEventListener('change',applyMode,true);
    q('#pc-discover')?.addEventListener('click',event=>{
      if(!providerIsOllama())return;
      event.preventDefault();
      event.stopImmediatePropagation();
      discoverOllama(false);
    },true);
    q('#provider-form')?.addEventListener('submit',saveOllama,true);

    const observer=new MutationObserver(()=>{
      installOption();
      polishConnections();
      if(lastCatalog&&!q('#pc-catalog [data-ollama-catalog="1"]'))refreshCatalogCard(lastCatalog);
    });
    const providers=q('#providers-view');
    if(providers)observer.observe(providers,{childList:true,subtree:true});
    loadCatalogCard();
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
})();
