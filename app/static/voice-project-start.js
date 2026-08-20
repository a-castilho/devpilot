(() => {
  const send=document.querySelector('#voice-send');
  const transcript=document.querySelector('#voice-transcript');
  const voiceModal=document.querySelector('#voice-modal');
  const projectModal=document.querySelector('#project-modal');
  const form=document.querySelector('#project-form');
  const toggle=document.querySelector('#project-create-repository');

  if(!send||!transcript||!projectModal||!form||!toggle)return;

  const patterns=[
    /^(?:iniciar|inicie|criar|crie|come[cç]ar|comece)\s+(?:um\s+)?(?:novo\s+)?projeto(?:\s+(?:chamado|nomeado)\s+)?(?<name>.*)$/i,
    /^novo\s+projeto(?:\s+(?<name>.*))?$/i,
  ];

  function parseStartProject(value){
    const cleaned=String(value||'').trim().replace(/\s+/g,' ');
    if(!cleaned)return null;
    for(const pattern of patterns){
      const match=cleaned.match(pattern);
      if(!match)continue;
      return {
        transcript:cleaned,
        name:String(match.groups?.name||'').trim().replace(/^[\s:.-]+|[\s:.-]+$/g,''),
      };
    }
    return null;
  }

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

  send.addEventListener('click',event=>{
    const parsed=parseStartProject(transcript.value);
    if(!parsed)return;

    event.preventDefault();
    event.stopImmediatePropagation();

    const organization=castilhoOrganization();
    if(!organization){
      if(voiceModal?.open)voiceModal.close();
      showView('organizations');
      toast('Conecte a organização a-castilho antes de iniciar um projeto sem URL Git');
      return;
    }

    form.reset();
    const nameInput=form.elements.namedItem('name');
    const slugInput=form.elements.namedItem('slug');
    const descriptionInput=form.elements.namedItem('description');
    const organizationSelect=form.elements.namedItem('organization_id');

    if(nameInput)nameInput.value=parsed.name;
    if(slugInput){
      const slug=slugify(parsed.name);
      slugInput.value=slug.length===1?`${slug}-repo`:slug;
    }
    if(descriptionInput)descriptionInput.value='';
    if(organizationSelect)organizationSelect.value=organization.id;

    toggle.checked=true;
    toggle.dispatchEvent(new Event('change',{bubbles:true}));

    if(voiceModal?.open)voiceModal.close();
    projectModal.showModal();
    toast(parsed.name
      ? 'Projeto preparado. Revise os dados e autorize a criação no GitHub.'
      : 'Informe o nome do projeto e autorize a criação no GitHub.');

    window.setTimeout(()=>{
      if(parsed.name)descriptionInput?.focus();
      else nameInput?.focus();
    },80);
  },true);
})();
