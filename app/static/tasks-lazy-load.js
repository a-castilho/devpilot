(()=>{
  if(typeof loadAllTasks!=='function'||typeof renderTasks!=='function'||typeof state==='undefined')return;

  const originalLoadAllTasks=loadAllTasks;
  const originalRenderTasks=renderTasks;
  let allowAll=false;

  async function lazyLoadAllTasks(){
    if(!allowAll)return;
    return originalLoadAllTasks();
  }

  function appendLoadAllButton(){
    const table=document.querySelector('#tasks-table');
    if(!table||state.tasksLoadedAll||!state.tasks.length||table.querySelector('.load-all-tasks'))return;

    const row=document.createElement('tr');
    row.className='tasks-more';
    const cell=document.createElement('td');
    cell.colSpan=5;
    const button=document.createElement('button');
    button.type='button';
    button.className='link load-all-tasks';
    button.textContent='Ver todas as tarefas';
    button.addEventListener('click',async()=>{
      allowAll=true;
      button.disabled=true;
      button.textContent='Carregando…';
      await originalLoadAllTasks();
      if(!state.tasksLoadedAll){
        allowAll=false;
        button.disabled=false;
        button.textContent='Ver todas as tarefas';
      }
    });
    cell.appendChild(button);
    row.appendChild(cell);
    table.appendChild(row);
  }

  loadAllTasks=lazyLoadAllTasks;
  renderTasks=function(){
    originalRenderTasks();
    appendLoadAllButton();
  };

  appendLoadAllButton();
})();
