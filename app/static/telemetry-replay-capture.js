(()=>{
  const GRID=20;
  const MIN_INTERVAL_MS=120;
  let sessionId='';
  let queue=[];
  let lastCell='';
  let lastAt=0;
  let syncing=false;
  let flushing=false;

  const token=()=>localStorage.getItem('devpilot-token')||'';
  const authHeaders=()=>({'Authorization':`Bearer ${token()}`,'Content-Type':'application/json'});

  async function syncSession(){
    if(syncing||!token())return;
    syncing=true;
    try{
      const response=await fetch('/api/telemetry/sessions/active',{cache:'no-store',headers:authHeaders()});
      if(!response.ok)return;
      const data=await response.json();
      const next=data?.active?.id||'';
      if(next!==sessionId){sessionId=next;queue=[];lastCell='';}
    }catch(_error){}finally{syncing=false}
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
      if(response.status===409){sessionId='';queue=[];lastCell='';}
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

  document.addEventListener('pointermove',onPointerMove,{capture:true,passive:true});
  setInterval(()=>void syncSession(),1800);
  setInterval(()=>void flush(),900);
  window.addEventListener('pagehide',()=>void flush(),{capture:true});
  void syncSession();
})();
