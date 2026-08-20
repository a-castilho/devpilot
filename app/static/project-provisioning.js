(() => {
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

  const slugify=value=>String(value||'')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g,'')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g,'-')
    .replace(/^-+|-+$/g,'')
    .slice(0,100);

  function castilhoOrganization(){
    return state.organizations.find(org=>String(org.external_login||'').toLowerCase()==='a-castilho')||null;
  }

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
        const repositoryUrl=String(f.get('repository_url')||'').trim();
        if(!repositoryUrl)throw new Error('Informe a URL Git ou marque a criação automática');
        await api('/projects',{method:'POST',body:JSON.stringify({
          ...common,
          repository_url:repositoryUrl,
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
})();
