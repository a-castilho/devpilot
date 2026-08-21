(() => {
  const form = document.querySelector('#organization-form');
  if (!form || form.dataset.normalizationBound === '1') return;
  form.dataset.normalizationBound = '1';

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
  const submit = form.querySelector('button[type="submit"]');
  let slugEdited = false;

  if (name) name.id ||= 'organization-name';
  if (slug) slug.id ||= 'organization-slug';
  if (githubLogin) githubLogin.id ||= 'organization-github-login';

  if (!form.querySelector('#organization-identifier-hint') && githubLogin) {
    const hint = document.createElement('p');
    hint.className = 'hint';
    hint.id = 'organization-identifier-hint';
    hint.textContent = 'Acentos e espaços são convertidos automaticamente. Ex.: A Organização → a-organizacao.';
    githubLogin.closest('label')?.insertAdjacentElement('afterend', hint);
    slug?.setAttribute('aria-describedby', hint.id);
    githubLogin.setAttribute('aria-describedby', hint.id);
  }

  name?.addEventListener('input', () => {
    if (!slugEdited || !slug?.value) slug.value = normalize(name.value, 100);
  });
  slug?.addEventListener('input', () => {
    slugEdited = true;
    slug.value = normalize(slug.value, 100);
  });
  githubLogin?.addEventListener('blur', () => {
    githubLogin.value = normalize(githubLogin.value, 39);
  });

  form.onsubmit = async event => {
    event.preventDefault();
    if (typeof isSuperAdmin === 'function' && !isSuperAdmin()) {
      if (typeof toast === 'function') toast('Acesso exclusivo do Super Admin');
      return;
    }

    const formData = new FormData(form);
    const normalizedSlug = normalize(formData.get('slug') || formData.get('name'), 100);
    const normalizedLogin = normalize(formData.get('github_login'), 39);
    const organizationName = String(formData.get('name') || '').trim();

    if (slug) slug.value = normalizedSlug;
    if (githubLogin) githubLogin.value = normalizedLogin;

    if (organizationName.length < 2 || normalizedSlug.length < 2 || normalizedLogin.length < 1) {
      if (typeof toast === 'function') toast('Informe nome, slug e login GitHub válidos.');
      return;
    }

    const payload = {
      name: organizationName,
      slug: normalizedSlug,
      github_login: normalizedLogin,
    };
    const accessToken = String(formData.get('access_token') || '').trim();
    if (accessToken) payload.access_token = accessToken;

    const original = submit?.textContent || 'Conectar organização';
    if (submit) {
      submit.disabled = true;
      submit.textContent = 'Salvando…';
    }

    let organization;
    try {
      organization = await api('/organizations', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      form.closest('dialog')?.close();
      form.reset();
      slugEdited = false;
      if (typeof toast === 'function') toast('Organização conectada. Sincronizando repositórios…');
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
    if (submit) {
      submit.disabled = false;
      submit.textContent = 'Conectar organização';
    }
  });
})();
