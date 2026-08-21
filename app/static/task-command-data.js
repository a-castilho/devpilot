(()=>{
  const CARD_ID='task-command-data-card';
  const STYLE_ID='task-command-data-styles';

  function ensureStyles(){
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');
    style.id=STYLE_ID;
    style.textContent=`
      .task-command-data-card{margin:0 0 16px;padding:16px;border:1px solid #29445f;border-radius:14px;background:#081522}
      .task-command-data-card[hidden]{display:none}
      .task-command-data-header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
      .task-command-data-header .eyebrow{margin:0;color:#79aee8}
      .task-command-data-copy{padding:7px 11px;border:1px solid #345b82;border-radius:9px;background:#10283f;color:#dcecff;font:inherit;font-size:11px;font-weight:800;cursor:pointer}
      .task-command-data-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(120px,.35fr);gap:10px}
      .task-command-data-field{min-width:0;padding:10px 12px;border-radius:10px;background:#050d17}
      .task-command-data-field.wide{grid-column:1/-1}
      .task-command-data-label{display:block;margin-bottom:5px;color:#7f93aa;font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
      .task-command-data-value{display:block;color:#e8f2ff;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;line-height:1.45;white-space:pre-wrap;overflow-wrap:anywhere}
      .task-command-data-value.ok{color:#61e7ac}.task-command-data-value.failed{color:#ff9eb0}
      @media(max-width:720px){.task-command-data-card{padding:14px}.task-command-data-grid{grid-template-columns:1fr}.task-command-data-field.wide{grid-column:auto}}
    `;
    document.head.appendChild(style);
  }

  function extractJsonObject(text){
    const marker=String(text||'').indexOf('LOG BRUTO');
    if(marker<0)return null;
    const start=String(text).indexOf('{',marker);
    if(start<0)return null;
    let depth=0,inString=false,escaped=false;
    for(let index=start;index<text.length;index+=1){
      const char=text[index];
      if(inString){
        if(escaped){escaped=false;continue}
        if(char==='\\'){escaped=true;continue}
        if(char==='"')inString=false;
        continue;
      }
      if(char==='"'){inString=true;continue}
      if(char==='{')depth+=1;
      else if(char==='}'){
        depth-=1;
        if(depth===0){
          try{return JSON.parse(text.slice(start,index+1))}catch(_error){return null}
        }
      }
    }
    return null;
  }

  function firstValue(sources,keys){
    for(const source of sources){
      if(!source||typeof source!=='object')continue;
      for(const key of keys){
        const value=source[key];
        if(value!==undefined&&value!==null&&String(value).trim()!=='')return value;
      }
    }
    return '';
  }

  function commandData(logs,metaText=''){
    const nested=logs?.command&&typeof logs.command==='object'?logs.command:{};
    const sources=[nested,logs];
    return{
      command:firstValue(sources,['command','command_text','executed_command','cmd']),
      cwd:firstValue(sources,['cwd','working_directory','workdir']),
      shell:firstValue(sources,['shell']),
      exitCode:firstValue(sources,['exit_code','return_code','returncode']),
      capturedAt:firstValue(sources,['captured_at','executed_at','finished_at'])||String(metaText||'').replace(/^.*?início\s*/i,'').trim(),
    };
  }

  function ensureCard(dialog){
    let card=dialog.querySelector(`#${CARD_ID}`);
    if(card)return card;
    const details=dialog.querySelector('.task-technical-details');
    if(!details)return null;
    card=document.createElement('section');
    card.id=CARD_ID;
    card.className='task-command-data-card';
    card.hidden=true;
    card.innerHTML=`<div class="task-command-data-header"><span class="eyebrow">COMANDO EXECUTADO</span><button class="task-command-data-copy" type="button">Copiar comando</button></div><div class="task-command-data-grid"></div>`;
    details.parentNode.insertBefore(card,details);
    return card;
  }

  function render(dialog){
    const output=dialog.querySelector('#task-log-output');
    const card=ensureCard(dialog);
    if(!output||!card)return;
    const logs=extractJsonObject(output.textContent||'');
    const data=commandData(logs||{},dialog.querySelector('#task-log-meta')?.textContent||'');
    const entries=[
      ['Comando',data.command,true],['Diretório',data.cwd,true],['Shell',data.shell,false],
      ['Código de saída',data.exitCode,false],['Registrado em',data.capturedAt,true],
    ].filter(([,value])=>value!==''&&value!==null&&value!==undefined);
    const grid=card.querySelector('.task-command-data-grid');
    grid.replaceChildren();
    card.hidden=!entries.length;
    card.dataset.command=data.command?String(data.command):'';
    for(const [label,value,wide] of entries){
      const field=document.createElement('div');field.className=`task-command-data-field${wide?' wide':''}`;
      const fieldLabel=document.createElement('span');fieldLabel.className='task-command-data-label';fieldLabel.textContent=label;
      const fieldValue=document.createElement('code');fieldValue.className='task-command-data-value';fieldValue.textContent=String(value);
      if(label==='Código de saída')fieldValue.classList.add(String(value)==='0'?'ok':'failed');
      field.append(fieldLabel,fieldValue);grid.appendChild(field);
    }
    const copy=card.querySelector('.task-command-data-copy');
    copy.disabled=!card.dataset.command;
    copy.onclick=async()=>{
      if(!card.dataset.command)return;
      try{await navigator.clipboard.writeText(card.dataset.command);copy.textContent='Copiado';setTimeout(()=>copy.textContent='Copiar comando',1400)}
      catch(_error){copy.textContent='Falha ao copiar';setTimeout(()=>copy.textContent='Copiar comando',1800)}
    };
  }

  function watchDialog(dialog){
    if(dialog.dataset.commandDataBound==='1')return;
    dialog.dataset.commandDataBound='1';ensureCard(dialog);render(dialog);
    const output=dialog.querySelector('#task-log-output');
    const meta=dialog.querySelector('#task-log-meta');
    const observer=new MutationObserver(()=>render(dialog));
    if(output)observer.observe(output,{childList:true,subtree:true,characterData:true});
    if(meta)observer.observe(meta,{childList:true,subtree:true,characterData:true});
  }

  function scan(){document.querySelectorAll('#task-log-modal').forEach(watchDialog)}
  ensureStyles();scan();
  new MutationObserver(scan).observe(document.documentElement,{childList:true,subtree:true});
})();
