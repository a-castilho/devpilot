(() => {
  const form = document.querySelector('#organization-form');
  if (!form || form.dataset.normalizationBound === '1') return;
  form.dataset.normalizationBound = '1';

  const MANAGED_ORGANIZATION = 'a-castilho';
  const normalize = (value, maxLength = 100) => String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, maxLength)
    .replace(/^-+|-+$/g, '');

  const name = form.querySelector('input[name="name"]');
  const slug = form.querySelector('input[name="slug"]');
  const githubLogin = form.querySelector('input[name="github_login"]');
  const accessToken = form.querySelector('input[name="access_token"]');
  const submit = form.querySelector('button[type="submit"]');
  const modal = form.closest('dialog');
  const modalTitle = form.querySelector('h2');
  let slugEdited = false;

  if (name) name.id ||= 'organization-name';
  if (slug) slug.id ||= 'organization-slug';
  if (githubLogin) githubLogin.id ||= 'organization-github-login';
  if (accessToken) accessToken.id ||= 'organization-access-token';

  if (!form.querySelector('#organization-identifier-hint') && githubLogin) {
    const hint = document.createElement('p');
    hint.className = 'hint';
    hint.id = 'organization-identifier-hint';
    hint.textContent = 'Acentos e espaços são convertidos automaticamente. Ex.: A Organização → a-organizacao.';
    githubLogin.closest('label')?.insertAdjacentElement('afterend', hint);
    slug?.setAttribute('aria-describedby', hint.id);
    githubLogin.setAttribute('aria-describedby', hint.id);
  }

  if (accessToken && !form.querySelector('#github-token-guidance')) {
    const guide = document.createElement('div');
    guide.id = 'github-token-guidance';
    guide.className = 'task-assist-card';
    guide.setAttribute('aria-live', 'polite');
    guide.innerHTML = `
      <span class="task-assist-icon" aria-hidden="true">G</span>
      <div>
        <strong>Token GitHub para a organização a-castilho</strong>
        <p>Crie um <b>Fine-grained personal access token</b> com <b>Resource owner = a-castilho</b>. O DevPilot não deve usar um token cujo Resource owner seja apenas sua conta pessoal.</p>
        <p><b>Permissões recomendadas:</b> Administration: Read and write; Contents: Read and write; Pull requests: Read and write; Issues: Read and write; Workflows: Read and write; Metadata: Read.</p>
        <label class="check" style="margin-top:10px">
          <input type="checkbox" id="github-resource-owner-confirmation">
          Confirmo que o Resource owner do token é a-castilho
        </label>
        <small>Não cole o token em conversas. Informe-o somente neste campo do DevPilot; ele é armazenado criptografado e não retorna pela API.</small>
      </div>`;
    accessToken.closest('label')?.insertAdjacentElement('beforebegin', guide);
  }

  const ownerConfirmation = form.querySelector('#github-resource-owner-confirmation');

  const syncManagedOrganizationRules = () => {
    if (!githubLogin || !accessToken) return;
    const managed = normalize(githubLogin.value, 39) === MANAGED_ORGANIZATION;
    accessToken.required = managed;
    accessToken.placeholder = managed
      ? 'Obrigatório: Fine-grained PAT da organização a-castilho'
      : 'Opcional para leitura pública; obrigatório para recursos privados';
    if (ownerConfirmation) {
      ownerConfirmation.required = managed;
      ownerConfirmation.closest('label')?.classList.toggle('required', managed);
    }
  };

  const credentialFailure = org => {
    if (String(org?.sync_status || '').toLowerCase() !== 'failed') return false;
    return /token|credential|credencial|expired|expirado|bad credentials|401|403|fine-grained/i
      .test(String(org?.last_sync_error || ''));
  };

  const resetOrganizationEditor = () => {
    form.dataset.editOrganizationId = '';
    if (modalTitle) modalTitle.textContent = 'Conectar organização GitHub';
    if (submit) submit.textContent = 'Conectar organização';
    if (slug) slug.disabled = false;
    if (githubLogin) githubLogin.disabled = false;
  };

  const openCredentialEditor = org => {
    if (!org || !isSuperAdmin()) return;
    form.reset();
    form.dataset.editOrganizationId = String(org.id || '');
    if (name) name.value = String(org.name || '');
    if (slug) {
      slug.value = String(org.slug || '');
      slug.disabled = true;
    }
    if (githubLogin) {
      githubLogin.value = String(org.external_login || '');
      githubLogin.disabled = true;
    }
    if (accessToken) {
      accessToken.value = '';
      accessToken.required = true;
      accessToken.placeholder = 'Cole o novo Fine-grained PAT';
    }
    if (ownerConfirmation) {
      ownerConfirmation.checked = false;
      ownerConfirmation.required = true;
    }
    if (modalTitle) modalTitle.textContent = 'Atualizar credencial GitHub';
    if (submit) submit.textContent = 'Salvar e validar';
    modal?.showModal?.();
    accessToken?.focus();
  };

  name?.addEventListener('input', () => {
    if (!slugEdited || !slug?.value) slug.value = normalize(name.value, 100);
  });
  slug?.addEventListener('input', () => {
    slugEdited = true;
    slug.value = normalize(slug.value, 100);
  });
  githubLogin?.addEventListener('input', syncManagedOrganizationRules);
  githubLogin?.addEventListener('blur', () => {
    githubLogin.value = normalize(githubLogin.value, 39);
    syncManagedOrganizationRules();
  });

  syncManagedOrganizationRules();

  form.onsubmit = async event => {
    event.preventDefault();
    if (typeof isSuperAdmin === 'function' && !isSuperAdmin()) {
      if (typeof toast === 'function') toast('Acesso exclusivo do Super Admin');
      return;
    }

    const formData = new FormData(form);
    const editingId = String(form.dataset.editOrganizationId || '').trim();
    const normalizedSlug = normalize(formData.get('slug') || slug?.value || formData.get('name'), 100);
    const normalizedLogin = normalize(formData.get('github_login') || githubLogin?.value, 39);
    const organizationName = String(formData.get('name') || '').trim();
    const token = String(formData.get('access_token') || '').trim();

    if (!editingId && slug) slug.value = normalizedSlug;
    if (!editingId && githubLogin) githubLogin.value = normalizedLogin;

    if (organizationName.length < 2 || normalizedSlug.length < 2 || normalizedLogin.length < 1) {
      if (typeof toast === 'function') toast('Informe nome, slug e login GitHub válidos.');
      return;
    }

    if (normalizedLogin === MANAGED_ORGANIZATION && !token) {
      if (typeof toast === 'function') toast('Informe o Fine-grained PAT da organização a-castilho.');
      accessToken?.focus();
      return;
    }

    if (normalizedLogin === MANAGED_ORGANIZATION && !ownerConfirmation?.checked) {
      if (typeof toast === 'function') toast('Confirme que o Resource owner do token é a-castilho.');
      ownerConfirmation?.focus();
      return;
    }

    const original = submit?.textContent || (editingId ? 'Salvar e validar' : 'Conectar organização');
    if (submit) {
      submit.disabled = true;
      submit.textContent = editingId ? 'Salvando…' : 'Conectando…';
    }

    let organization;
    try {
      if (editingId) {
        organization = await api(`/organizations/${editingId}`, {
          method: 'PATCH',
          body: JSON.stringify({name: organizationName, access_token: token}),
        });
        modal?.close();
        form.reset();
        resetOrganizationEditor();
        if (typeof toast === 'function') toast('Credencial atualizada. Validando acesso ao GitHub…');
      } else {
        const payload = {
          name: organizationName,
          slug: normalizedSlug,
          github_login: normalizedLogin,
        };
        if (token) payload.access_token = token;
        organization = await api('/organizations', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        modal?.close();
        form.reset();
        slugEdited = false;
        if (typeof toast === 'function') toast('Organização conectada. Verificando acesso aos repositórios…');
      }
    } catch (error) {
      if (typeof toast === 'function') toast(error.message);
      return;
    } finally {
      if (submit) {
        submit.disabled = false;
        submit.textContent = original;
      }
    }

    void (async () => {
      await load();
      await syncOrganization(organization.id);
    })();
  };

  form.addEventListener('reset', () => {
    slugEdited = false;
    if (ownerConfirmation) ownerConfirmation.checked = false;
    resetOrganizationEditor();
    if (submit) submit.disabled = false;
    setTimeout(syncManagedOrganizationRules, 0);
  });

  const originalRenderOrganizations = window.renderOrganizations;
  if (typeof originalRenderOrganizations === 'function') {
    window.renderOrganizations = function renderOrganizationsWithCredentialState() {
      originalRenderOrganizations();
      const target = document.querySelector('#organizations-list');
      if (!target || !Array.isArray(state?.organizations)) return;

      state.organizations.forEach(org => {
        const button = target.querySelector(`.sync-org[data-id="${CSS.escape(String(org.id))}"]`);
        const card = button?.closest('.project-card');
        if (!button || !card) return;

        const failed = String(org.sync_status || '').toLowerCase() === 'failed';
        if (!failed) return;

        const authFailure = credentialFailure(org);
        const eyebrow = card.querySelector('.eyebrow');
        const credentialLabel = card.querySelector('code');
        if (eyebrow) eyebrow.textContent = authFailure
          ? 'GITHUB · CREDENCIAL NECESSÁRIA'
          : 'GITHUB · FALHA';
        if (credentialLabel && authFailure) {
          credentialLabel.textContent = org.has_credentials
            ? 'credencial configurada · validação falhou'
            : 'sem credencial válida';
        }
        button.textContent = authFailure ? 'Atualizar credencial' : 'Tentar novamente';
        button.onclick = authFailure
          ? () => openCredentialEditor(org)
          : () => void syncOrganization(org.id, button);
      });
    };
  }

  const originalSyncOrganization = window.syncOrganization;
  if (typeof originalSyncOrganization === 'function') {
    window.syncOrganization = async function syncOrganizationWithFreshState(id, button) {
      try {
        return await originalSyncOrganization(id, button);
      } finally {
        state.organizations = [];
        await loadOrganizations();
      }
    };
  }
})();
