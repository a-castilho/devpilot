(() => {
  const REPOSITORY_FORMAT_ERROR = 'Informe o repositório no formato organização/repositório.';

  const slugify=value=>String(value||'')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g,'')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g,'-')
    .replace(/^-+|-+$/g,'')
    .slice(0,100);

  function cleanRepositoryInput(value){
    let raw=String(value||'')
      .replace(/[\u200b\u200c\u200d\ufeff]/g,'')
      .replace(/\u00a0/g,' ')
      .trim();
    const wrappers={"`":"`","\"":"\"","'":"'","<":">"};
    let changed=true;
    while(changed&&raw.length>=2){
      changed=false;
      const closing=wrappers[raw[0]];
      if(closing&&raw[raw.length-1]===closing){
        raw=raw.slice(1,-1).trim();
        changed=true;
      }
    }
    return raw.replace(/\s*\/\s*/g,'/').trim();
  }

  function validRepositoryPart(value){
    return /^[A-Za-z0-9_.-]+$/.test(value||'')&&value!=='.'&&value!=='..';
  }

  function repositoryParts(path){
    const parts=String(path||'').replace(/^\/+|\/+$/g,'').split('/').filter(Boolean);
    if(parts.length!==2)return null;
    const owner=parts[0];
    const repo=parts[1].replace(/\.git$/i,'');
    if(!validRepositoryPart(owner)||!validRepositoryPart(repo))return null;
    return {owner,repo};
  }

  function normalizeRepositoryInput(value){
    let raw=cleanRepositoryInput(value);
    if(!raw)return {ok:false,error:REPOSITORY_FORMAT_ERROR};

    const ssh=raw.match(/^git@([^:]+):(.+)$/i);
    if(ssh){
      const host=String(ssh[1]||'').toLowerCase();
      const parts=repositoryParts(ssh[2]);
      if(!host||!parts)return {ok:false,error:REPOSITORY_FORMAT_ERROR};
      return {
        ok:true,
        value:host==='github.com'?`${parts.owner}/${parts.repo}`:`https://${host}/${parts.owner}/${parts.repo}`,
      };
    }

    if(/^www\.github\.com\//i.test(raw))raw=`https://${raw.slice(4)}`;
    else if(/^github\.com\//i.test(raw))raw=`https://${raw}`;

    if(/^https?:\/\//i.test(raw)){
      let parsed;
      try{parsed=new URL(raw)}catch(_){return {ok:false,error:REPOSITORY_FORMAT_ERROR}}
      if(parsed.protocol!=='https:'||parsed.username||parsed.password||parsed.search||parsed.hash){
        return {ok:false,error:REPOSITORY_FORMAT_ERROR};
      }
      let host=String(parsed.hostname||'').toLowerCase();
      if(host==='www.github.com')host='github.com';
      const parts=repositoryParts(parsed.pathname);
      if(!host||!parts)return {ok:false,error:REPOSITORY_FORMAT_ERROR};
      return {
        ok:true,
        value:host==='github.com'?`${parts.owner}/${parts.repo}`:`https://${host}/${parts.owner}/${parts.repo}`,
      };
    }

    const parts=repositoryParts(raw);
    if(!parts)return {ok:false,error:REPOSITORY_FORMAT_ERROR};
    return {ok:true,value:`${parts.owner}/${parts.repo}`};
  }

  function castilhoOrganization(){
    return typeof state!=='undefined'
      ? state.organizations.find(org=>String(org.external_login||'').toLowerCase()==='a-castilho')||null
      : null;
  }

  function initLegacyProjectForm(){
    const form=document.querySelector('#project-form');
    if(!form)return;

    const toggle=document.querySelector('#project-create-repository');
    const repositoryInput=document.querySelector('#project-repository-url');
    const repositoryField=document.querySelector('#project-repository-field');
    const organizationSelect=document.querySelector('#project-organization');
    const submit=document.querySelector('#project-submit');
    const nameInput=form.elements.namedItem('name');
    const slugInput=form.elements.namedItem('slug');
    let slugEdited=false;

    function syncProvisionMode(){
      const create=Boolean(toggle?.checked);
      const organization=castilhoOrganization();
      if(repositoryInput){
        repositoryInput.disabled=create;
        repositoryInput.required=!create;
        repositoryInput.placeholder=create
          ? 'Será criado automaticamente em a-castilho/'
          : 'a-castilho/projeto ou https://github.com/a-castilho/projeto';
      }
      if(repositoryField)repositoryField.style.opacity=create?'.55':'1';
      if(organizationSelect){
        if(create&&organization)organizationSelect.value=organization.id;
        organizationSelect.disabled=create;
      }
      if(submit)submit.textContent=create?'Autorizar e criar no GitHub':'Criar projeto';
    }

    toggle?.addEventListener('change',()=>{
      if(toggle.checked&&!castilhoOrganization()){
        toggle.checked=false;
        toast('Conecte primeiro a organização a-castilho em Organizações');
      }
      syncProvisionMode();
    });

    repositoryInput?.addEventListener('blur',()=>{
      if(toggle?.checked||!repositoryInput.value.trim())return;
      const normalized=normalizeRepositoryInput(repositoryInput.value);
      if(normalized.ok)repositoryInput.value=normalized.value;
    });

    slugInput?.addEventListener('input',()=>{slugEdited=true});
    nameInput?.addEventListener('input',()=>{
      if(slugEdited)return;
      const slug=slugify(nameInput.value);
      if(slugInput)slugInput.value=slug.length===1?`${slug}-repo`:slug;
    });

    form.addEventListener('reset',()=>{
      slugEdited=false;
      setTimeout(syncProvisionMode,0);
    });

    form.onsubmit=async event=>{
      event.preventDefault();
      const f=new FormData(form);
      const create=Boolean(toggle?.checked);
      const common={
        name:String(f.get('name')||'').trim(),
        slug:String(f.get('slug')||'').trim(),
        description:String(f.get('description')||''),
        agents_md:String(f.get('agents_md')||''),
        codex_config:{model:f.get('model'),reasoning_effort:'medium',timeout_seconds:1800},
      };

      try{
        if(create){
          const organization=castilhoOrganization();
          if(!organization)throw new Error('Organização a-castilho não está conectada');
          await api('/projects/provision',{method:'POST',body:JSON.stringify(common)});
          toast(`Repositório privado a-castilho/${common.slug} criado e conectado`);
        }else{
          const normalized=normalizeRepositoryInput(f.get('repository_url'));
          if(!normalized.ok)throw new Error(normalized.error);
          if(repositoryInput)repositoryInput.value=normalized.value;
          await api('/projects',{method:'POST',body:JSON.stringify({
            ...common,
            repository_url:normalized.value,
            organization_id:f.get('organization_id')||null,
            default_branch:f.get('default_branch')||'main',
          })});
          toast('Projeto conectado');
        }
        form.closest('dialog').close();
        form.reset();
        await load();
      }catch(error){
        toast(error.message||'Falha ao criar projeto');
      }
    };

    syncProvisionMode();
  }

  function injectBuilderStyles(){
    if(document.querySelector('#project-builder-repository-fix-style'))return;
    const style=document.createElement('style');
    style.id='project-builder-repository-fix-style';
    style.textContent=`
      .builder-repository-grid.repository-grid-three{grid-template-columns:repeat(3,minmax(0,1fr))}
      .builder-repository-error{display:none;margin:10px 0 0;padding:9px 11px;border-radius:10px;border:1px solid rgba(255,188,66,.34);background:rgba(255,188,66,.08);color:#ffd277;font-size:13px;line-height:1.35;text-align:left;word-break:break-word}
      .builder-repository-error.show{display:block}
      #projects-list .repository-pending-code{color:#ffd277;border-color:rgba(255,188,66,.28)}
      #projects-list .analyze[disabled]{opacity:.45;cursor:not-allowed}
      @media(max-width:760px){.builder-repository-grid.repository-grid-three{grid-template-columns:1fr}.project-builder-aside{padding-bottom:88px}}
    `;
    document.head.appendChild(style);
  }

  function builderBlueprint(form){
    const result={};
    form.querySelectorAll('[data-builder-group]').forEach(section=>{
      const key=section.dataset.builderGroup;
      if(!key)return;
      result[key]=[...section.querySelectorAll('.choice-card.selected[data-option]')]
        .map(card=>card.dataset.option)
        .filter(Boolean);
    });
    result.custom_technologies=String(form.elements.namedItem('custom_technologies')?.value||'')
      .split(',').map(item=>item.trim()).filter(Boolean).slice(0,30);
    result.delivery={
      conventional_commits:Boolean(form.elements.namedItem('conventional_commits')?.checked),
      protected_main:Boolean(form.elements.namedItem('protected_main')?.checked),
      pull_request_review:Boolean(form.elements.namedItem('pull_request_review')?.checked),
      migrations_reversible:Boolean(form.elements.namedItem('migrations_reversible')?.checked),
    };
    return result;
  }

  function decoratePendingProjects(){
    const host=document.querySelector('#projects-list');
    if(!host||typeof state==='undefined'||!Array.isArray(state.projects))return;
    const cards=[...host.querySelectorAll('.project-card')];
    cards.forEach((card,index)=>{
      const project=state.projects[index];
      if(!project||String(project.repository_url||'').trim())return;
      const code=card.querySelector('code');
      if(code){
        code.textContent='Repositório pendente';
        code.classList.add('repository-pending-code');
      }
      const analyze=card.querySelector('.analyze');
      if(analyze){
        analyze.disabled=true;
        analyze.title='Conecte um repositório antes de analisar o código';
      }
    });
  }

  function initBuilderRepositoryFlow(){
    const form=document.querySelector('#project-builder-form');
    if(!form)return;
    injectBuilderStyles();

    const repositoryGrid=form.querySelector('.builder-repository-grid');
    if(repositoryGrid&&!repositoryGrid.querySelector('[data-repository-choice="defer"]')){
      const label=document.createElement('label');
      label.className='repository-choice';
      label.dataset.repositoryChoice='defer';
      label.innerHTML=`
        <input type="radio" name="repository_mode" value="defer">
        <strong>Criar repositório depois</strong>
        <small>Cria o projeto local agora e deixa o Git pendente para conexão posterior.</small>
      `;
      repositoryGrid.appendChild(label);
      repositoryGrid.classList.add('repository-grid-three');
    }

    const submit=form.querySelector('#project-builder-submit');
    let feedback=form.querySelector('#project-builder-repository-error');
    if(!feedback&&submit){
      feedback=document.createElement('div');
      feedback.id='project-builder-repository-error';
      feedback.className='builder-repository-error';
      feedback.setAttribute('role','alert');
      feedback.setAttribute('aria-live','polite');
      submit.insertAdjacentElement('afterend',feedback);
    }

    const repositoryInput=form.elements.namedItem('repository_url');
    const organization=form.elements.namedItem('organization_id');
    const existing=form.querySelector('#project-builder-existing-repository');
    const notice=form.querySelector('#project-builder-repository-notice');
    const nameInput=form.elements.namedItem('name');
    const slugInput=form.elements.namedItem('slug');

    const clearFeedback=()=>{
      if(!feedback)return;
      feedback.textContent='';
      feedback.classList.remove('show');
    };
    const showFeedback=message=>{
      if(!feedback)return;
      feedback.textContent=String(message||REPOSITORY_FORMAT_ERROR);
      feedback.classList.add('show');
    };

    function syncBuilderRepositoryUi(){
      const mode=form.elements.namedItem('repository_mode')?.value||'connect';
      const requiresExisting=mode==='connect';
      if(existing)existing.hidden=!requiresExisting;
      if(repositoryInput){
        repositoryInput.required=requiresExisting;
        repositoryInput.disabled=!requiresExisting;
      }
      if(organization)organization.disabled=mode==='create';
      if(notice){
        notice.textContent=mode==='create'
          ? (typeof isSuperAdmin==='function'&&isSuperAdmin()
              ? 'O DevPilot criará um repositório privado na organização a-castilho.'
              : 'A criação automática de repositório exige perfil Super Admin.')
          : mode==='defer'
            ? 'O projeto será criado agora sem Git. O repositório poderá ser conectado ou criado depois.'
            : 'Informe um repositório existente. URLs e formatos GitHub serão normalizados automaticamente.';
      }
      form.querySelectorAll('[data-repository-choice]').forEach(card=>{
        card.classList.toggle('selected',card.dataset.repositoryChoice===mode);
      });
      if(mode!=='connect')clearFeedback();
    }

    form.addEventListener('change',event=>{
      if(event.target?.name==='repository_mode')setTimeout(syncBuilderRepositoryUi,0);
    });
    form.addEventListener('reset',()=>setTimeout(syncBuilderRepositoryUi,0));

    repositoryInput?.addEventListener('input',clearFeedback);
    repositoryInput?.addEventListener('blur',()=>{
      if(!repositoryInput.value.trim())return;
      const normalized=normalizeRepositoryInput(repositoryInput.value);
      if(normalized.ok){
        repositoryInput.value=normalized.value;
        clearFeedback();
      }else{
        showFeedback(normalized.error);
      }
    });

    // Fallback after a deferred creation: if the private builder state still marks the old
    // slug as edited, keep automatic slug generation working whenever the field is empty.
    nameInput?.addEventListener('input',()=>{
      if(!slugInput||String(slugInput.value||'').trim())return;
      const slug=slugify(nameInput.value);
      slugInput.value=slug.length===1?`${slug}-repo`:slug;
    },true);

    async function createDeferredProject(){
      const name=String(form.elements.namedItem('name')?.value||'').trim();
      const slug=String(form.elements.namedItem('slug')?.value||'').trim();
      const description=String(form.elements.namedItem('description')?.value||'').trim();
      const model=String(form.elements.namedItem('model')?.value||'gpt-5.4').trim();
      const agentsMd=String(form.querySelector('#project-builder-agents-preview')?.textContent||'');
      const blueprint=builderBlueprint(form);
      const button=form.querySelector('#project-builder-submit');
      if(button){button.disabled=true;button.textContent='Criando projeto…'}
      clearFeedback();
      try{
        await api('/projects/deferred',{method:'POST',body:JSON.stringify({
          name,
          slug,
          description,
          agents_md:agentsMd,
          codex_config:{
            model,
            reasoning_effort:'medium',
            timeout_seconds:1800,
            project_blueprint:blueprint,
          },
          organization_id:typeof isSuperAdmin==='function'&&isSuperAdmin()?(organization?.value||null):null,
          default_branch:String(form.elements.namedItem('default_branch')?.value||'main').trim()||'main',
        })});
        toast(`Projeto ${name} criado. Repositório pendente.`);
        form.reset();
        form.querySelector('[data-builder-preset="saas-balanced"]')?.click();
        await load();
        showView('projects');
        decoratePendingProjects();
      }catch(error){
        showFeedback(error.message||'Falha ao criar projeto');
      }finally{
        if(button){button.disabled=false;button.textContent='Criar projeto'}
      }
    }

    form.addEventListener('submit',event=>{
      const mode=form.elements.namedItem('repository_mode')?.value||'connect';
      if(mode==='connect'){
        const normalized=normalizeRepositoryInput(repositoryInput?.value||'');
        if(!normalized.ok){
          event.preventDefault();
          event.stopImmediatePropagation();
          showFeedback(normalized.error);
          repositoryInput?.focus();
          return;
        }
        if(repositoryInput)repositoryInput.value=normalized.value;
        clearFeedback();
        return;
      }
      if(mode==='defer'){
        event.preventDefault();
        event.stopImmediatePropagation();
        void createDeferredProject();
      }
    },true);

    const projectsHost=document.querySelector('#projects-list');
    if(projectsHost){
      new MutationObserver(decoratePendingProjects).observe(projectsHost,{childList:true,subtree:true});
    }
    setTimeout(()=>{
      syncBuilderRepositoryUi();
      decoratePendingProjects();
    },0);
  }

  initLegacyProjectForm();
  initBuilderRepositoryFlow();
})();
