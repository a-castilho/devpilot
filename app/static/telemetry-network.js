(()=>{
  const nativeFetch=window.fetch.bind(window);
  const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));

  function isTelemetryRequest(input){
    const value=typeof input==='string'?input:(input?.url||'');
    try{
      const url=new URL(value,window.location.href);
      return url.origin===window.location.origin&&url.pathname.startsWith('/api/telemetry');
    }catch(_error){return false}
  }

  window.fetch=async(input,init)=>{
    if(!isTelemetryRequest(input))return nativeFetch(input,init);
    let lastError=null;
    for(let attempt=0;attempt<3;attempt+=1){
      try{
        const response=await nativeFetch(input,init);
        if(![502,503,504].includes(response.status)||attempt===2)return response;
      }catch(error){
        lastError=error;
        if(attempt===2)throw error;
      }
      await sleep(attempt===0?140:320);
    }
    if(lastError)throw lastError;
    return nativeFetch(input,init);
  };

  document.addEventListener('DOMContentLoaded',()=>{
    const button=document.querySelector('#copy-hook');
    if(!button)return;
    const hookText=[
      'export DEVPILOT_URL=http://127.0.0.1:8080',
      'source "$HOME/Documents/devpilot/tools/devpilot_terminal_capture.sh"'
    ].join('\n');

    button.onclick=async()=>{
      const original=button.textContent;
      try{
        await navigator.clipboard.writeText(hookText);
        button.textContent='Configuração copiada';
      }catch(_error){
        button.textContent='Falha ao copiar';
      }
      window.setTimeout(()=>{button.textContent=original},1800);
    };
  });
})();
