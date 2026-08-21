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
    .slice(0, maxLength);

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

  form.addEventListener('submit', event => {
    const normalizedSlug = normalize(slug?.value || name?.value, 100);
    const normalizedLogin = normalize(githubLogin?.value, 39);
    if (slug) slug.value = normalizedSlug;
    if (githubLogin) githubLogin.value = normalizedLogin;
    if (normalizedSlug.length < 2 || normalizedLogin.length < 2) {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (typeof toast === 'function') toast('Informe nome, slug e login GitHub válidos.');
      return;
    }
    if (submit) {
      const original = submit.textContent;
      submit.disabled = true;
      submit.textContent = 'Salvando…';
      window.setTimeout(() => {
        if (form.closest('dialog')?.open) {
          submit.disabled = false;
          submit.textContent = original;
        }
      }, 8000);
    }
  }, true);

  form.addEventListener('reset', () => {
    slugEdited = false;
    if (submit) {
      submit.disabled = false;
      submit.textContent = 'Conectar organização';
    }
  });
})();
