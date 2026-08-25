(()=>{
  const GRID=20;
  const MIN_INTERVAL_MS=120;
  const ACTIVE_SYNC_MS=2500;
  const IDLE_SYNC_MS=5000;
  const HIDDEN_SYNC_MS=15000;
  let sessionId='';
  let queue=[];
  let lastCell='';
  let lastAt=0;
  let syncing=false;
  let flushing=false;
  let attached=false;
  let syncTimer=null;
  let flushTimer=null;
  let destroyed=false;

  const token=()=>localStorage.getItem('devpilot-token')||'';
  const authHeaders=()=>({'Authorization':`Bearer ${token()}`,'Content-Type':'application/json'});

  function attachPointer(){
    if(attached||!sessionId)return;
    attached=true;
    document.addEventListener('pointermove',onPointerMove,{capture:true,passive:true});
  }

  function detachPointer(){
    if(!attached)return;
    attached=false;
    document.removeEventListener('pointermove',onPointerMove,true);
  }

  function stopFlushTimer(){
    if(!flushTimer)return;
    clearInterval(flushTimer);
    flushTimer=null;
  }

  function startFlushTimer(){
    if(flushTimer||!sessionId)return;
    flushTimer=setInterval(()=>void flush(),900);
  }

  function applySession(next){
    const normalized=String(next||'');
    if(normalized===sessionId){
      if(sessionId){attachPointer();startFlushTimer()}
      else{detachPointer();stopFlushTimer()}
      return;
    }
    sessionId=normalized;
    queue=[];
    lastCell='';
    lastAt=0;
    if(sessionId){attachPointer();startFlushTimer()}
    else{detachPointer();stopFlushTimer()}
  }

  function nextSyncDelay(){
    if(document.hidden)return HIDDEN_SYNC_MS;
    return sessionId?ACTIVE_SYNC_MS:IDLE_SYNC_MS;
  }

  function scheduleSync(delay=nextSyncDelay()){
    if(destroyed)return;
    clearTimeout(syncTimer);
    syncTimer=setTimeout(()=>void syncSession(),Math.max(300,delay));
  }

  async function syncSession(){
    if(destroyed)return;
    if(syncing){scheduleSync();return}
    if(!token()){
      applySession('');
      scheduleSync();
      return;
    }
    syncing=true;
    try{
      const response=await fetch('/api/telemetry/sessions/active',{cache:'no-store',headers:authHeaders()});
      if(response.ok){
        const data=await response.json();
        applySession(data?.active?.id||'');
      }else if(response.status===401||response.status===403){
        applySession('');
      }
    }catch(_error){}finally{
      syncing=false;
      scheduleSync();
    }
  }

  async function flush(){
    if(flushing||!sessionId||!queue.length||!token())return;
    flushing=true;
    const batch=queue.splice(0,250);
    try{
      const response=await fetch(`/api/telemetry/sessions/${encodeURIComponent(sessionId)}/pointer`,{
        method:'POST',headers:authHeaders(),body:JSON.stringify({events:batch})
      });
      if(!response.ok&&response.status!==409)queue.unshift(...batch);
      if(response.status===409)applySession('');
    }catch(_error){queue.unshift(...batch)}finally{
      if(queue.length>500)queue=queue.slice(-500);
      flushing=false;
    }
  }

  function onPointerMove(event){
    if(!sessionId||event.target?.closest?.('[data-telemetry-control]'))return;
    const now=performance.now();
    if(now-lastAt<MIN_INTERVAL_MS)return;
    const width=Math.max(window.innerWidth,1);
    const height=Math.max(window.innerHeight,1);
    const grid_x=Math.max(0,Math.min(GRID-1,Math.floor(event.clientX/width*GRID)));
    const grid_y=Math.max(0,Math.min(GRID-1,Math.floor(event.clientY/height*GRID)));
    const cell=`${grid_x}:${grid_y}`;
    if(cell===lastCell)return;
    lastCell=cell;lastAt=now;
    queue.push({grid_x,grid_y,occurred_at:new Date().toISOString()});
    if(queue.length>=40)void flush();
  }

  document.addEventListener('visibilitychange',()=>{
    if(destroyed)return;
    scheduleSync(document.hidden?HIDDEN_SYNC_MS:300);
  });
  window.addEventListener('pagehide',()=>void flush(),{capture:true});
  window.addEventListener('beforeunload',()=>{
    destroyed=true;
    clearTimeout(syncTimer);
    stopFlushTimer();
    detachPointer();
  });
  scheduleSync(0);
})();
