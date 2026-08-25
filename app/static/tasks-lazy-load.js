(()=>{
  if(typeof loadAllTasks!=='function'||typeof renderTasks!=='function'||typeof state==='undefined')return;

  const originalRenderTasks=renderTasks;
  const PAGE_SIZE=20;
  const MAX_LIMIT=500;
  let currentLimit=Math.max(5,Number(state.tasks?.length||0));
  let explicitLoading=false;
  let hasMore=true;
  let hydrationInstalled=false;

  const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,char=>({
    '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
  }[char]));

  // Nunca coloque prompts extensos no DOM durante a renderização da tabela.
  // O conteúdo completo é materializado somente quando o usuário abre o detalhe.
  taskInstructions=function(task){
    const prompt=String(task?.prompt||'').trim();
    if(!prompt)return '';
    return `<details class="task-instructions" data-task-instructions="${escapeHtml(task.id)}"><summary>Ver instruções da análise</summary><div class="task-instructions-content" data-task-instructions-body><span class="eyebrow">INSTRUÇÕES CAPTURADAS</span><p>Abra para carregar as instruções.</p></div></details>`;
  };

  function hydrateInstruction(details){
    if(!details?.open||details.dataset.hydrated==='1')return;
    const task=Array.isArray(state.tasks)
      ? state.tasks.find(item=>String(item.id)===String(details.dataset.taskInstructions||''))
      : null;
    const body=details.querySelector('[data-task-instructions-body]');
    if(!body||!task)return;
    const prompt=String(task.prompt||'').trim();
    body.innerHTML=`<span class="eyebrow">INSTRUÇÕES CAPTURADAS</span><p>${escapeHtml(prompt)}</p>`;
    details.dataset.hydrated='1';
  }

  function installInstructionHydration(){
    if(hydrationInstalled)return;
    const table=document.querySelector('#tasks-table');
    if(!table)return;
    hydrationInstalled=true;
    table.addEventListener('toggle',event=>{
      const details=event.target?.closest?.('details[data-task-instructions]');
      if(details)hydrateInstruction(details);
    },true);
  }

  async function lazyLoadAllTasks(){
    // Chamadas automáticas do app.js são intencionalmente ignoradas.
    // Apenas o botão de paginação pode aumentar o histórico em memória/DOM.
    if(!explicitLoading)return;
    const nextLimit=Math.min(MAX_LIMIT,currentLimit+PAGE_SIZE);
    if(nextLimit<=currentLimit){
      hasMore=false;
      return;
    }

    const tasks=await api(`/tasks?limit=${nextLimit}`);
    state.tasks=Array.isArray(tasks)?tasks:[];
    currentLimit=state.tasks.length;
    hasMore=state.tasks.length>=nextLimit&&nextLimit<MAX_LIMIT;
    state.tasksLoadedAll=!hasMore;
    renderTasks();
  }

  function appendLoadMoreButton(){
    const table=document.querySelector('#tasks-table');
    if(!table||!state.tasks.length||!hasMore||table.querySelector('.load-more-tasks'))return;

    const row=document.createElement('tr');
    row.className='tasks-more';
    const cell=document.createElement('td');
    cell.colSpan=5;
    const button=document.createElement('button');
    button.type='button';
    button.className='link load-more-tasks';
    button.textContent=`Carregar mais ${PAGE_SIZE} tarefas`;
    button.addEventListener('click',async()=>{
      explicitLoading=true;
      button.disabled=true;
      button.textContent='Carregando…';
      try{
        await lazyLoadAllTasks();
      }catch(error){
        if(typeof toast==='function')toast(error.message||'Falha ao carregar tarefas');
      }finally{
        explicitLoading=false;
        if(button.isConnected){
          button.disabled=false;
          button.textContent=`Carregar mais ${PAGE_SIZE} tarefas`;
        }
      }
    });
    cell.appendChild(button);
    row.appendChild(cell);
    table.appendChild(row);
  }

  loadAllTasks=lazyLoadAllTasks;
  renderTasks=function(){
    originalRenderTasks();
    installInstructionHydration();
    appendLoadMoreButton();
  };

  installInstructionHydration();
  appendLoadMoreButton();
})();
