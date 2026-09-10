(() => {
  const form = document.querySelector('#organization-form');
  if (!form || form.dataset.normalizationBound === '1') return;
  form.dataset.normalizationBound = '1';
  form.noValidate = true;

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
  let slugEdited = false;
  let submitting = false;

  if (name) name.id ||= 'organization-name';
  if (slug) slug.id ||= 'organization-slug';
  if (githubLogin) githubLogin.id ||= 'organization-github-login';
  if (accessToken) {
    accessToken.id ||= 'organization-access-token';
    accessToken.required = false;
    accessToken.placeholder = 'Opcional; use apenas para repositórios privados';
  }

  let feedback = form.querySelector('#organization-submit-feedback');
  if (!feedback && submit) {
    feedback = document.createElement('p');
    feedback.id = 'organization-submit-feedback';
    feedback.setAttribute('role', 'status');
    feedback.setAttribute('aria-live', 'polite');
    feedback.style.cssText = 'margin:10px 0 0;color:#9fb0c2;font-size:13px;line-height:1.4;';
    submit.insertAdjacentElement('beforebegin', feedback);
  }
  const setFeedback = (message = '', error = false) => {
    if (!feedback) return;
    feedback.textContent = message;
    feedback.style.color = error ? '#ffb4b4' : '#9fb0c2';
  };

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

  const handleSubmit = async event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (submitting) return;

    if (typeof isSuperAdmin === 'function' && !isSuperAdmin()) {
      const message = 'Acesso exclusivo do Super Admin';
      setFeedback(message, true);
      if (typeof toast === 'function') toast(message);
      return;
    }

    const formData = new FormData(form);
    const normalizedSlug = normalize(formData.get('slug') || formData.get('name'), 100);
    const normalizedLogin = normalize(formData.get('github_login'), 39);
    const organizationName = String(formData.get('name') || '').trim();
    const token = String(formData.get('access_token') || '').trim();

    if (slug) slug.value = normalizedSlug;
    if (githubLogin) githubLogin.value = normalizedLogin;

    if (organizationName.length < 2 || normalizedSlug.length < 2 || normalizedLogin.length < 1) {
      const message = 'Informe nome, slug e login GitHub válidos.';
      setFeedback(message, true);
      if (typeof toast === 'function') toast(message);
      return;
    }

    const payload = {
      name: organizationName,
      slug: normalizedSlug,
      github_login: normalizedLogin,
    };
    if (token) payload.access_token = token;

    const original = submit?.textContent || 'Conectar e sincronizar';
    submitting = true;
    setFeedback('Conectando organização…');
    if (submit) {
      submit.disabled = true;
      submit.textContent = 'Conectando…';
    }

    let organization;
    try {
      organization = await api('/organizations', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setFeedback('Organização cadastrada. Sincronizando repositórios…');
      if (typeof toast === 'function') toast('Organização conectada. Sincronizando repositórios públicos…');
      if (typeof load === 'function') await load();
      if (organization?.id && typeof syncOrganization === 'function') {
        await syncOrganization(organization.id);
      }
      form.closest('dialog')?.close();
      form.reset();
      slugEdited = false;
    } catch (error) {
      const message = String(error?.message || 'Não foi possível cadastrar a organização.');
      setFeedback(message, true);
      if (typeof toast === 'function') toast(message);
    } finally {
      submitting = false;
      if (submit) {
        submit.disabled = false;
        submit.textContent = original;
      }
    }
  };

  form.onsubmit = null;
  form.addEventListener('submit', handleSubmit, true);

  form.addEventListener('reset', () => {
    slugEdited = false;
    submitting = false;
    setFeedback('');
    if (submit) {
      submit.disabled = false;
      submit.textContent = 'Conectar e sincronizar';
    }
  });
})();
