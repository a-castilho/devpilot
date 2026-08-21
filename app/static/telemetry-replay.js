(()=>{
  const state={events:[],session:null,index:0,playing:false,raf:0,startedAt:0,speed:2,terminalQueue:[],terminalTimer:0,typing:false};
  const token=()=>localStorage.getItem('devpilot-token')||'';
  const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

  function mount(){
    if(document.querySelector('#replay-panel'))return;
    const history=document.querySelector('#history')?.closest('.panel');
    if(!history)return;
    const panel=document.createElement('section');
    panel.id='replay-panel';
    panel.className='panel replay-panel';
    panel.hidden=true;
    panel.dataset.telemetryControl='1';
    panel.innerHTML=`
      <div class="section-title replay-title">
        <div><p class="eyebrow">REPETIÇÃO VISUAL</p><h2>Simulação da sessão gravada</h2><p id="replay-meta" class="replay-meta"></p></div>
        <div class="replay-controls">
          <label>Velocidade <select id="replay-speed"><option value="1">1×</option><option value="2" selected>2×</option><option value="4">4×</option></select></label>
          <button id="replay-restart" type="button">↻ Repetir</button>
          <button id="replay-close" type="button">Fechar</button>
        </div>
      </div>
      <div class="replay-notice">Simulação somente visual: nenhum clique, tecla ou comando é executado de verdade.</div>
      <div class="replay-stage">
        <div class="replay-browser" id="replay-browser">
          <div class="replay-browser-bar"><span></span><span></span><span></span><strong>Eventos web</strong></div>
          <div class="replay-canvas" id="replay-canvas">
            <div class="replay-grid"></div>
            <div class="replay-cursor" id="replay-cursor" aria-hidden="true"></div>
            <div class="replay-web-caption" id="replay-web-caption">Aguardando evento…</div>
          </div>
        </div>
        <div class="replay-terminal">
          <div class="replay-terminal-bar">Terminal sanitizado</div>
          <pre id="replay-terminal-log"><span class="muted">$ aguardando comandos…</span></pre>
        </div>
      </div>
      <div class="replay-progress"><div id="replay-progress-bar"></div></div>
      <div class="replay-status"><span id="replay-status">Pronto</span><strong id="replay-counter">0 / 0 eventos</strong></div>`;
    history.parentNode.insertBefore(panel,history);
    panel.querySelector('#replay-speed').addEventListener('change',event=>{state.speed=Number(event.target.value)||2;if(state.events.length)restart()});
    panel.querySelector('#replay-restart').addEventListener('click',restart);
    panel.querySelector('#replay-close').addEventListener('click',()=>{stop();panel.hidden=true});
  }

  async function api(path){
    const response=await fetch(`/api/telemetry${path}`,{cache:'no-store',headers:{'Authorization':`Bearer ${token()}`}});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Falha ao carregar repetição');
    return data;
  }

  function addReplayButtons(){
    mount();
    document.querySelectorAll('.history-row').forEach(row=>{
      if(row.querySelector('[data-replay-session]'))return;
      const sessionId=row.dataset.sessionRow;
      if(!sessionId)return;
      const button=document.createElement('button');
      button.type='button';
      button.dataset.replaySession=sessionId;
      button.dataset.telemetryControl='1';
      button.textContent='Repetir sessão';
      button.addEventListener('click',()=>openReplay(sessionId,button));
      row.appendChild(button);
    });
  }

  function eventTime(event){return new Date(event.occurred_at).getTime()||0}
  function eventLabel(event){
    if(event.source==='terminal')return 'Terminal';
    if(event.event_type==='move')return 'Movimento do mouse';
    if(event.event_type==='click')return 'Clique';
    if(event.event_type==='key')return 'Tecla / atalho';
    return `${event.source} · ${event.event_type}`;
  }

  function moveCursor(payload,click=false){
    const cursor=document.querySelector('#replay-cursor');
    if(!cursor)return;
    const x=(Math.max(0,Math.min(19,Number(payload?.grid_x)||0))+.5)/20*100;
    const y=(Math.max(0,Math.min(19,Number(payload?.grid_y)||0))+.5)/20*100;
    cursor.style.left=`${x}%`;cursor.style.top=`${y}%`;cursor.classList.add('visible');
    if(click){cursor.classList.remove('clicked');void cursor.offsetWidth;cursor.classList.add('clicked')}
  }

  function renderWebEvent(event){
    const caption=document.querySelector('#replay-web-caption');
    const payload=event.payload||{};
    if(event.event_type==='move'){
      moveCursor(payload,false);
      caption.textContent=`Mouse → região ${payload.grid_x+1}, ${payload.grid_y+1}`;
    }else if(event.event_type==='click'){
      moveCursor(payload,true);
      const target=[payload.tag,payload.role].filter(Boolean).join(' / ')||'controle';
      caption.textContent=`Clique em ${target}`;
    }else if(event.event_type==='key'){
      const detail=payload.shortcut||payload.group||'tecla';
      caption.textContent=`Tecla: ${detail}`;
      caption.classList.remove('key-flash');void caption.offsetWidth;caption.classList.add('key-flash');
    }
  }

  function resetTerminal(){
    clearInterval(state.terminalTimer);state.terminalTimer=0;state.terminalQueue=[];state.typing=false;
    const terminal=document.querySelector('#replay-terminal-log');
    if(terminal)terminal.innerHTML='<span class="muted">$ aguardando comandos…</span>';
  }

  function enqueueTerminal(payload){
    const command=String(payload?.command||'').trim();
    if(!command)return;
    state.terminalQueue.push({command,exitCode:payload?.exit_code,cwd:String(payload?.cwd||'')});
    drainTerminal();
  }

  function drainTerminal(){
    if(state.typing||!state.terminalQueue.length)return;
    state.typing=true;
    const item=state.terminalQueue.shift();
    const terminal=document.querySelector('#replay-terminal-log');
    if(!terminal){state.typing=false;return}
    if(terminal.querySelector('.muted'))terminal.textContent='';
    const line=document.createElement('span');line.className='replay-terminal-line';
    const prefix=item.cwd?`${item.cwd} $ `:'$ ';
    line.textContent=prefix;terminal.appendChild(line);
    terminal.scrollTop=terminal.scrollHeight;
    let index=0;
    clearInterval(state.terminalTimer);
    state.terminalTimer=setInterval(()=>{
      line.textContent=prefix+item.command.slice(0,++index);
      terminal.scrollTop=terminal.scrollHeight;
      if(index>=item.command.length){
        clearInterval(state.terminalTimer);state.terminalTimer=0;
        const suffix=document.createElement('span');
        suffix.className=Number(item.exitCode)===0?'replay-exit ok':'replay-exit';
        suffix.textContent=item.exitCode===null||item.exitCode===undefined?'\n':`\n[exit ${item.exitCode}]\n`;
        terminal.appendChild(suffix);state.typing=false;drainTerminal();
      }
    },Math.max(6,Math.round(28/state.speed)));
  }

  function processEvent(event){
    if(event.source==='terminal'&&event.event_type==='command')enqueueTerminal(event.payload||{});
    else if(event.source==='browser')renderWebEvent(event);
    const status=document.querySelector('#replay-status');
    if(status)status.textContent=eventLabel(event);
  }

  function updateProgress(){
    const total=Math.max(state.events.length,1);
    const percent=Math.min(100,state.index/total*100);
    const bar=document.querySelector('#replay-progress-bar');
    const counter=document.querySelector('#replay-counter');
    if(bar)bar.style.width=`${percent}%`;
    if(counter)counter.textContent=`${state.index} / ${state.events.length} eventos`;
  }

  function stop(){if(state.raf)cancelAnimationFrame(state.raf);state.raf=0;state.playing=false;clearInterval(state.terminalTimer);state.terminalTimer=0;state.typing=false}

  function tick(now){
    if(!state.playing||!state.events.length)return;
    const first=eventTime(state.events[0]);
    const elapsed=(now-state.startedAt)*state.speed;
    while(state.index<state.events.length&&eventTime(state.events[state.index])-first<=elapsed){processEvent(state.events[state.index]);state.index+=1}
    updateProgress();
    if(state.index>=state.events.length){
      state.playing=false;state.raf=0;
      const status=document.querySelector('#replay-status');if(status)status.textContent='Repetição concluída';
      const bar=document.querySelector('#replay-progress-bar');if(bar)bar.style.width='100%';
      return;
    }
    state.raf=requestAnimationFrame(tick);
  }

  function restart(){
    if(!state.events.length)return;
    stop();resetTerminal();state.index=0;
    const cursor=document.querySelector('#replay-cursor');if(cursor){cursor.className='replay-cursor';cursor.removeAttribute('style')}
    const caption=document.querySelector('#replay-web-caption');if(caption)caption.textContent='Iniciando repetição…';
    state.startedAt=performance.now();state.playing=true;updateProgress();state.raf=requestAnimationFrame(tick);
  }

  async function openReplay(sessionId,button){
    if(!token())return;
    const original=button.textContent;button.disabled=true;button.textContent='Carregando…';
    try{
      const data=await api(`/sessions/${encodeURIComponent(sessionId)}/timeline?limit=5000`);
      state.events=Array.isArray(data.events)?data.events.slice().sort((a,b)=>eventTime(a)-eventTime(b)):[];
      state.session=data.session||null;
      mount();
      const panel=document.querySelector('#replay-panel');panel.hidden=false;
      const meta=document.querySelector('#replay-meta');
      const when=state.session?.started_at?new Date(state.session.started_at).toLocaleString('pt-BR'):'Sessão';
      meta.textContent=`${when} · ${state.events.length} eventos · dados sanitizados`;
      panel.scrollIntoView({behavior:'smooth',block:'start'});
      if(state.events.length)restart();
      else{resetTerminal();document.querySelector('#replay-status').textContent='Sessão sem eventos para repetir';updateProgress()}
    }catch(error){
      const toast=document.querySelector('#toast');if(toast){toast.textContent=error.message;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),3000)}
    }finally{button.disabled=false;button.textContent=original}
  }

  const observer=new MutationObserver(addReplayButtons);
  function boot(){mount();addReplayButtons();const history=document.querySelector('#history');if(history)observer.observe(history,{childList:true,subtree:true})}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
