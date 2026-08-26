const $=(selector)=>document.querySelector(selector);
const state={token:localStorage.getItem('devpilot-token')||'',session:null,analysisSession:null,recording:false,queue:[],timer:null,flushTimer:null,pollTimer:null,finishing:false};

function toast(message){const el=$('#toast');el.textContent=message;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),3000)}
function headers(){return {'Authorization':`Bearer ${state.token}`,'Content-Type':'application/json'}}
async function api(path,options={}){const response=await fetch(`/api/telemetry${path}`,{...options,headers:{...headers(),...(options.headers||{})}});const data=await response.json().catch(()=>({}));if(response.status===401){$('#auth-card').classList.remove('hidden');throw new Error('Token DevPilot necessário')}if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Falha na operação');return data}
function formatTime(seconds){const safe=Math.max(0,Number(seconds)||0);return `${String(Math.floor(safe/60)).padStart(2,'0')}:${String(safe%60).padStart(2,'0')}`}
function authState(){if(state.token)$('#auth-card').classList.add('hidden');else $('#auth-card').classList.remove('hidden')}

function keyPayload(event){
  const key=String(event.key||'');
  let group='other';
  if(event.ctrlKey||event.altKey||event.metaKey)group='shortcut';
  else if(key.length===1)group='text';
  else if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End','PageUp','PageDown','Tab','Enter'].includes(key))group='navigation';
  else if(['Backspace','Delete','Insert','Escape'].includes(key))group='editing';
  else if(['Shift','Control','Alt','Meta','CapsLock'].includes(key))group='modifier';
  else if(/^F\d{1,2}$/.test(key))group='function';
  let shortcut='';
  if(group==='shortcut'){
    const parts=[];
    if(event.ctrlKey)parts.push('ctrl');if(event.altKey)parts.push('alt');if(event.shiftKey)parts.push('shift');if(event.metaKey)parts.push('meta');
    if(key.length<=12&&!['Control','Alt','Shift','Meta'].includes(key))parts.push(key.toLowerCase());
    shortcut=parts.join('+').replace(/[^a-z0-9+_.:-]/g,'').slice(0,32);
  }
  return {group,ctrl:event.ctrlKey,alt:event.altKey,shift:event.shiftKey,meta:event.metaKey,repeat:event.repeat,shortcut};
}

function onClick(event){
  if(!state.recording||event.target.closest('[data-telemetry-control]'))return;
  const width=Math.max(window.innerWidth,1),height=Math.max(window.innerHeight,1),target=event.target;
  enqueue('click',{grid_x:Math.min(19,Math.floor(event.clientX/width*20)),grid_y:Math.min(19,Math.floor(event.clientY/height*20)),tag:String(target.tagName||'').toLowerCase(),role:target.getAttribute?.('role')||'',button:['left','middle','right'][event.button]||'other'});
}
function onKey(event){if(!state.recording||event.target.closest('[data-telemetry-control]'))return;enqueue('key',keyPayload(event))}
function enqueue(event_type,payload){state.queue.push({event_type,occurred_at:new Date().toISOString(),payload});$('#queue-count').textContent=state.queue.length;if(state.queue.length>=40)flushQueue()}
function attachCapture(){document.addEventListener('click',onClick,true);document.addEventListener('keydown',onKey,true)}
function detachCapture(){document.removeEventListener('click',onClick,true);document.removeEventListener('keydown',onKey,true)}

async function flushQueue(){
  if(!state.session||!state.queue.length)return;
  const batch=state.queue.splice(0,250);$('#queue-count').textContent=state.queue.length;
  try{await api(`/sessions/${state.session.id}/events`,{method:'POST',body:JSON.stringify({events:batch})})}
  catch(error){if(state.recording){state.queue.unshift(...batch);$('#queue-count').textContent=state.queue.length}if(!String(error.message).includes('not recording'))toast(error.message)}
}

function setRecordingUI(){
  const active=state.recording;
  $('#pulse').classList.toggle('active',active);
  $('#status-label').textContent=active?'Gravando atividade':'Pronto para gravar';
  $('#stop').disabled=!active;$('#analyze').disabled=!(state.analysisSession||state.session);
  document.querySelectorAll('.duration').forEach(button=>button.disabled=active);
  if(state.session){$('#browser-count').textContent=state.session.event_counts?.browser||0;$('#terminal-count').textContent=state.session.event_counts?.terminal||0;$('#countdown').textContent=formatTime(state.session.remaining_seconds||0)}else{$('#browser-count').textContent='0';$('#terminal-count').textContent='0';$('#countdown').textContent='00:00'}
}

async function refreshSession(){
  if(!state.session)return;
  try{const item=await api(`/sessions/${state.session.id}`);state.session=item;if(state.analysisSession?.id===item.id)state.analysisSession=item;$('#browser-count').textContent=item.event_counts?.browser||0;$('#terminal-count').textContent=item.event_counts?.terminal||0;if(item.status!=='recording'&&state.recording)await finishSession(false)}catch(error){toast(error.message)}
}

function startTimers(){
  clearInterval(state.timer);clearInterval(state.flushTimer);clearInterval(state.pollTimer);
  state.timer=setInterval(()=>{if(!state.session||!state.recording)return;const end=new Date(state.session.ends_at).getTime();const remaining=Math.max(0,Math.ceil((end-Date.now())/1000));$('#countdown').textContent=formatTime(remaining);if(remaining<=0)finishSession(true)},250);
  state.flushTimer=setInterval(flushQueue,1800);
  state.pollTimer=setInterval(refreshSession,3000);
}
function clearTimers(){clearInterval(state.timer);clearInterval(state.flushTimer);clearInterval(state.pollTimer);state.timer=state.flushTimer=state.pollTimer=null}

async function startSession(seconds){
  if(!state.token)return authState();
  try{
    const item=await api('/sessions',{method:'POST',body:JSON.stringify({duration_seconds:Number(seconds)})});
    state.session=item;state.analysisSession=item;state.recording=true;state.queue=[];attachCapture();startTimers();setRecordingUI();renderAnalysis(item.analysis||{},item);toast(`Gravação iniciada por ${Math.round(seconds/60)} minuto(s)`);
  }catch(error){toast(error.message);await loadActive()}
}

async function finishSession(stopOnServer=true){
  if(state.finishing||!state.session)return;
  state.finishing=true;state.recording=false;detachCapture();clearTimers();
  try{
    await flushQueue();
    if(stopOnServer)state.session=await api(`/sessions/${state.session.id}/stop`,{method:'POST',body:'{}'});
    state.analysisSession=state.session;
    await analyzeSession(state.session,{announce:true});
    await loadHistory();
  }catch(error){toast(error.message)}finally{state.finishing=false;setRecordingUI()}
}

async function analyzeSession(item,{announce=false}={}){
  if(!item?.id)return null;
  const analysis=await api(`/sessions/${item.id}/analyze`,{method:'POST',body:'{}'});
  const updated={...item,analysis};
  state.analysisSession=updated;
  if(state.session?.id===item.id)state.session=updated;
  renderAnalysis(analysis,updated);
  setRecordingUI();
  if(announce)toast('Análise concluída');
  return updated;
}

async function analyzeCurrent(){
  const target=state.analysisSession||state.session;
  if(!target)return;
  try{await analyzeSession(target,{announce:true});await loadHistory()}catch(error){toast(error.message)}
}

function setAnalysisContext(item){
  const title=$('.analysis-panel .section-title > div');
  if(!title)return;
  let context=$('#analysis-session-context');
  if(!context){context=document.createElement('p');context.id='analysis-session-context';context.className='analysis-session-context';title.appendChild(context)}
  if(!item){context.textContent='';return}
  const when=item.started_at?new Date(item.started_at).toLocaleString('pt-BR'):'Sessão';
  context.textContent=`Sessão ${when} · ${item.duration_seconds||0}s · ${item.status||'—'}`;
}

function renderAnalysis(analysis,item=state.analysisSession||state.session){
  setAnalysisContext(item);
  const summary=analysis?.summary;if(!summary){$('#score').textContent='—';$('#summary').innerHTML='<div class="empty">Esta sessão ainda não possui análise. Use “Analisar novamente” para gerar.</div>';$('#candidates').innerHTML='';return}
  $('#score').textContent=analysis.automation_score;
  const items=[['Eventos',summary.events],['Terminal',summary.terminal_commands],['Cliques',summary.browser_clicks],['Teclas',summary.key_events],['Padrões',summary.repeated_patterns]];
  $('#summary').innerHTML=items.map(([label,value])=>`<div class="summary-card"><span>${label}</span><strong>${value}</strong></div>`).join('');
  const candidates=analysis.candidates||[];
  $('#candidates').innerHTML=candidates.map(item=>`<article class="candidate"><div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.proposal)}</p>${item.evidence?.length?`<code>${escapeHtml(item.evidence.join(' → '))}</code>`:''}</div><div class="confidence">${Math.round((item.confidence||0)*100)}% · ${item.occurrences||0}x</div></article>`).join('')||'<div class="empty">Nenhuma repetição forte ainda. Grave o mesmo fluxo mais de uma vez para aumentar a evidência.</div>';
}
function escapeHtml(value){return String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))}

async function loadActive(){
  if(!state.token)return authState();
  try{
    const data=await api('/sessions/active');
    if(data.active){state.session=data.active;state.recording=true;if(!state.analysisSession)state.analysisSession=data.active;attachCapture();startTimers();setRecordingUI();if(state.analysisSession?.id===data.active.id)renderAnalysis(data.active.analysis||{},data.active)}
    else{state.session=null;state.recording=false;detachCapture();clearTimers();setRecordingUI()}
  }catch(error){toast(error.message)}
}

function markSelectedHistory(sessionId){
  document.querySelectorAll('.history-row').forEach(row=>row.classList.toggle('selected',row.dataset.sessionRow===sessionId));
  document.querySelectorAll('[data-session]').forEach(button=>{
    const selected=button.dataset.session===sessionId;
    button.textContent=selected?'Exibindo':'Ver análise';
    button.setAttribute('aria-pressed',String(selected));
  });
}

async function openHistoryAnalysis(sessionId,button){
  const original=button.textContent;
  button.disabled=true;button.textContent='Abrindo…';
  try{
    let item=await api(`/sessions/${sessionId}`);
    state.analysisSession=item;
    if(!item.analysis?.summary)item=await analyzeSession(item);
    else renderAnalysis(item.analysis,item);
    state.analysisSession=item;
    markSelectedHistory(item.id);
    setRecordingUI();
    const panel=$('.analysis-panel');
    panel.classList.add('analysis-highlight');
    panel.scrollIntoView({behavior:'smooth',block:'start'});
    setTimeout(()=>panel.classList.remove('analysis-highlight'),900);
    toast('Análise da sessão carregada');
  }catch(error){button.textContent=original;toast(error.message)}finally{button.disabled=false}
}

async function loadHistory(){
  if(!state.token)return;
  try{
    const items=await api('/sessions?limit=12');
    $('#history').innerHTML=items.map(item=>`<div class="history-row${state.analysisSession?.id===item.id?' selected':''}" data-session-row="${item.id}"><div><strong>${new Date(item.started_at).toLocaleString('pt-BR')}</strong><br><small>${item.duration_seconds}s · ${item.status}</small></div><span>${item.event_counts.browser} web</span><span>${item.event_counts.terminal} terminal</span><button data-session="${item.id}" data-telemetry-control aria-pressed="${state.analysisSession?.id===item.id?'true':'false'}">${state.analysisSession?.id===item.id?'Exibindo':'Ver análise'}</button></div>`).join('')||'<div class="empty">Nenhuma sessão registrada.</div>';
    document.querySelectorAll('[data-session]').forEach(button=>button.onclick=()=>openHistoryAnalysis(button.dataset.session,button));
  }catch(error){toast(error.message)}
}

const hookText="export DEVPILOT_URL=http://127.0.0.1:8080\nexport DEVPILOT_TERMINAL_CAPTURE=1\nexport DEVPILOT_TELEMETRY_TOKEN='seu-token-de-acesso'\nsource \"$HOME/Documents/devpilot/tools/devpilot_terminal_capture.sh\"";
document.querySelectorAll('.duration').forEach(button=>button.onclick=()=>startSession(button.dataset.seconds));
$('#stop').onclick=()=>finishSession(true);$('#analyze').onclick=analyzeCurrent;$('#refresh-history').onclick=loadHistory;
$('#copy-hook').onclick=async()=>{try{await navigator.clipboard.writeText(hookText);toast('Configuração copiada')}catch{toast('Não foi possível copiar')}};
$('#save-token').onclick=()=>{const token=$('#token-input').value.trim();if(!token)return;state.token=token;localStorage.setItem('devpilot-token',token);authState();loadActive();loadHistory()};
window.addEventListener('beforeunload',()=>{detachCapture();clearTimers()});
authState();loadActive();loadHistory();
