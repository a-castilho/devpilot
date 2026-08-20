(()=>{
  const PENDING_KEY='devpilot-telemetry-pending-v1';
  let activeSession=null,recording=false,queue=[],pollTimer=null,flushTimer=null,attached=false,flushing=false;
  const token=()=>localStorage.getItem('devpilot-token')||'';
  const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));

  const request=async(path,options={})=>{
    const current=token();
    if(!current)return null;
    for(let attempt=0;attempt<3;attempt+=1){
      try{
        const response=await fetch(`/api/telemetry${path}`,{
          ...options,
          cache:'no-store',
          headers:{'Authorization':`Bearer ${current}`,'Content-Type':'application/json',...(options.headers||{})}
        });
        if(response.ok)return response.json().catch(()=>({ok:true}));
        if(![502,503,504].includes(response.status))return null;
      }catch(_error){
        // Docker/rebuild e navegação podem causar falhas transitórias locais.
      }
      if(attempt<2)await sleep(120*(attempt+1));
    }
    return null;
  };

  const persist=()=>{
    try{
      if(activeSession?.id&&queue.length){
        localStorage.setItem(PENDING_KEY,JSON.stringify({session_id:activeSession.id,events:queue.slice(-500)}));
      }else if(!queue.length){
        localStorage.removeItem(PENDING_KEY);
      }
    }catch(_error){}
  };

  const restore=next=>{
    if(!next?.id||queue.length)return;
    try{
      const saved=JSON.parse(localStorage.getItem(PENDING_KEY)||'null');
      if(saved?.session_id===next.id&&Array.isArray(saved.events))queue=saved.events.slice(-500);
      else if(saved?.session_id&&saved.session_id!==next.id)localStorage.removeItem(PENDING_KEY);
    }catch(_error){localStorage.removeItem(PENDING_KEY)}
  };

  const mountEntryPoint=()=>{
    const nav=document.querySelector('.sidebar nav');
    if(!nav||document.querySelector('[data-telemetry-entry]'))return;
    const button=document.createElement('button');
    button.className='nav';button.type='button';button.dataset.telemetryEntry='1';button.dataset.telemetryControl='1';button.textContent='Gravador de processos';
    button.addEventListener('click',()=>{window.location.href='/telemetry'});
    nav.appendChild(button);
  };

  const keyPayload=event=>{
    const key=String(event.key||'');let group='other';
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
    return{group,ctrl:event.ctrlKey,alt:event.altKey,shift:event.shiftKey,meta:event.metaKey,repeat:event.repeat,shortcut};
  };

  const enqueue=(event_type,payload)=>{
    if(!recording||!activeSession)return;
    queue.push({event_type,occurred_at:new Date().toISOString(),payload});
    if(queue.length>500)queue=queue.slice(-500);
    persist();
    if(queue.length>=20)void flush();
  };

  const onClick=event=>{
    if(!recording||event.target.closest('[data-telemetry-control]'))return;
    const width=Math.max(innerWidth,1),height=Math.max(innerHeight,1),target=event.target;
    enqueue('click',{
      grid_x:Math.min(19,Math.floor(event.clientX/width*20)),
      grid_y:Math.min(19,Math.floor(event.clientY/height*20)),
      tag:String(target.tagName||'').toLowerCase(),
      role:target.getAttribute?.('role')||'',
      button:['left','middle','right'][event.button]||'other'
    });
  };
  const onKey=event=>{if(recording&&!event.target.closest('[data-telemetry-control]'))enqueue('key',keyPayload(event))};
  const attach=()=>{if(attached)return;attached=true;document.addEventListener('click',onClick,true);document.addEventListener('keydown',onKey,true)};
  const detach=()=>{if(!attached)return;attached=false;document.removeEventListener('click',onClick,true);document.removeEventListener('keydown',onKey,true)};

  const flush=async()=>{
    if(flushing||!activeSession?.id||!queue.length)return false;
    flushing=true;
    const sessionId=activeSession.id;
    const batch=queue.splice(0,250);
    persist();
    try{
      const result=await request(`/sessions/${sessionId}/events`,{method:'POST',body:JSON.stringify({events:batch})});
      if(!result){queue.unshift(...batch);persist();return false}
      persist();
      return true;
    }finally{flushing=false}
  };

  const sync=async()=>{
    const data=await request('/sessions/active');
    const next=data?.active||null;
    if(next){
      const changed=activeSession?.id!==next.id;
      activeSession=next;recording=true;
      if(changed)restore(next);
      attach();
      if(queue.length)void flush();
      return;
    }
    if(recording||activeSession){
      // Tenta a fila final antes de esquecer a sessão. Se falhar, ela fica
      // persistida em localStorage para diagnóstico em vez de sumir silenciosamente.
      await flush();
      recording=false;detach();activeSession=null;
      if(!queue.length)persist();
    }
  };

  const preserve=()=>{persist();};
  mountEntryPoint();
  pollTimer=setInterval(sync,1800);
  flushTimer=setInterval(()=>void flush(),900);
  void sync();
  window.addEventListener('pagehide',preserve,{capture:true});
  window.addEventListener('beforeunload',()=>{persist();clearInterval(pollTimer);clearInterval(flushTimer);detach()});
})();
