(() => {
  const REPOSITORY_FORMAT_ERROR = 'Informe o repositório no formato organização/repositório.';

  const slugify = value => String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 100);

  const superAdmin = () => typeof isSuperAdmin === 'function' && isSuperAdmin();

  function cleanRepositoryInput(value) {
    let raw = String(value || '')
      .replace(/[\u200b\u200c\u200d\ufeff]/g, '')
      .replace(/\u00a0/g, ' ')
      .trim();
    const wrappers = {"`": "`", "\"": "\"", "'": "'", "<": ">"};
    let changed = true;
    while (changed && raw.length >= 2) {
      changed = false;
      const closing = wrappers[raw[0]];
      if (closing && raw[raw.length - 1] === closing) {
        raw = raw.slice(1, -1).trim();
        changed = true;
      }
    }
    return raw.replace(/\s*\/\s*/g, '/').trim();
  }

  function validRepositoryPart(value) {
    return /^[A-Za-z0-9_.-]+$/.test(value || '') && value !== '.' && value !== '..';
  }

  function repositoryParts(path) {
    const parts = String(path || '').replace(/^\/+|\/+$/g, '').split('/').filter(Boolean);
    if (parts.length !== 2) return null;
    const owner = parts[0];
    const repo = parts[1].replace(/\.git$/i, '');
    if (!validRepositoryPart(owner) || !validRepositoryPart(repo)) return null;
    return {owner, repo};
  }

  function normalizeRepositoryInput(value) {
    let raw = cleanRepositoryInput(value);
    if (!raw) return {ok: false, error: REPOSITORY_FORMAT_ERROR};

    const ssh = raw.match(/^git@([^:]+):(.+)$/i);
    if (ssh) {
      const host = String(ssh[1] || '').toLowerCase();
      const parts = repositoryParts(ssh[2]);
      if (!host || !parts) return {ok: false, error: REPOSITORY_FORMAT_ERROR};
      return {
        ok: true,
        value: host === 'github.com' ? `${parts.owner}/${parts.repo}` : `https://${host}/${parts.owner}/${parts.repo}`,
      };
    }

    if (/^www\.github\.com\//i.test(raw)) raw = `https://${raw.slice(4)}`;
    else if (/^github\.com\//i.test(raw)) raw = `https://${raw}`;

    if (/^https?:\/\//i.test(raw)) {
      let parsed;
      try {
        parsed = new URL(raw);
      } catch (_) {
        return {ok: false, error: REPOSITORY_FORMAT_ERROR};
      }
      if (parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.search || parsed.hash) {
        return {ok: false, error: REPOSITORY_FORMAT_ERROR};
      }
      let host = String(parsed.hostname || '').toLowerCase();
      if (host === 'www.github.com') host = 'github.com';
      const parts = repositoryParts(parsed.pathname);
      if (!host || !parts) return {ok: false, error: REPOSITORY_FORMAT_ERROR};
      return {
        ok: true,
        value: host === 'github.com' ? `${parts.owner}/${parts.repo}` : `https://${host}/${parts.owner}/${parts.repo}`,
      };
    }

    const parts = repositoryParts(raw);
    if (!parts) return {ok: false, error: REPOSITORY_FORMAT_ERROR};
    return {ok: true, value: `${parts.owner}/${parts.repo}`};
  }

  function castilhoOrganization() {
    return typeof state !== 'undefined'
      ? state.organizations.find(org => String(org.external_login || '').toLowerCase() === 'a-castilho') || null
      : null;
  }

  function builderBlueprint(form) {
    const result = {};
    form.querySelectorAll('[data-builder-group]').forEach(section => {
      const key = section.dataset.builderGroup;
      if (!key) return;
      result[key] = [...section.querySelectorAll('.choice-card.selected[data-option]')]
        .map(card => card.dataset.option)
        .filter(Boolean);
    });
    result.custom_technologies = String(form.elements.namedItem('custom_technologies')?.value || '')
      .split(',').map(item => item.trim()).filter(Boolean).slice(0, 30);
    result.delivery = {
      conventional_commits: Boolean(form.elements.namedItem('conventional_commits')?.checked),
      protected_main: Boolean(form.elements.namedItem('protected_main')?.checked),
      pull_request_review: Boolean(form.elements.namedItem('pull_request_review')?.checked),
      migrations_reversible: Boolean(form.elements.namedItem('migrations_reversible')?.checked),
    };
    return result;
  }

  function decoratePendingProjects() {
    const host = document.querySelector('#projects-list');
    if (!host || typeof state === 'undefined' || !Array.isArray(state.projects)) return;
    const cards = [...host.querySelectorAll('.project-card')];
    cards.forEach((card, index) => {
      const project = state.projects[index];
      if (!project || String(project.repository_url || '').trim()) return;
      const code = card.querySelector('code');
      if (code) {
        code.textContent = 'Repositório pendente';
        code.classList.add('repository-pending-code');
      }
      const analyze = card.querySelector('.analyze');
      if (analyze) {
        analyze.disabled = true;
        analyze.title = 'Conecte um repositório antes de analisar o código';
      }
    });
  }

  function injectStyles() {
    if (document.querySelector('#project-git-role-style')) return;
    const style = document.createElement('style');
    style.id = 'project-git-role-style';
    style.textContent = `
      .builder-repository-error{display:none;margin:10px 0 0;padding:9px 11px;border-radius:10px;border:1px solid rgba(255,188,66,.34);background:rgba(255,188,66,.08);color:#ffd277;font-size:13px;line-height:1.35;text-align:left;word-break:break-word}
      .builder-repository-error.show{display:block}
      #projects-list .repository-pending-code{color:#ffd277;border-color:rgba(255,188,66,.28)}
      #projects-list .analyze[disabled]{opacity:.45;cursor:not-allowed}
      [data-git-admin-only][hidden]{display:none!important}
      @media(max-width:760px){.project-builder-aside{padding-bottom:88px}}
    `;
    document.head.appendChild(style);
  }

  function initLegacyProjectForm() {
    const form = document.querySelector('#project-form');
    if (!form) return;

    const toggle = document.querySelector('#project-create-repository');
    const toggleLabel = toggle?.closest('label');
    const repositoryInput = document.querySelector('#project-repository-url');
    const repositoryField = document.querySelector('#project-repository-field');
    const organizationSelect = document.querySelector('#project-organization');
    const organizationField = organizationSelect?.closest('label');
    const defaultBranch = form.elements.namedItem('default_branch');
    const defaultBranchField = defaultBranch?.closest('label');
    const submit = document.querySelector('#project-submit');
    const nameInput = form.elements.namedItem('name');
    const slugInput = form.elements.namedItem('slug');
    const heading = form.querySelector('h2');
    const hint = document.querySelector('#project-provision-hint');
    let slugEdited = false;

    function syncProvisionMode() {
      const admin = superAdmin();
      if (!admin && toggle) toggle.checked = true;
      const create = !admin || Boolean(toggle?.checked);
      const organization = castilhoOrganization();

      [toggleLabel, repositoryField, organizationField, defaultBranchField].forEach(element => {
        if (element) element.hidden = !admin;
      });
      if (heading) heading.textContent = admin ? 'Conectar ou criar repositório' : 'Criar projeto';
      if (hint) {
        hint.hidden = admin;
        if (!admin) hint.textContent = 'O Git será configurado automaticamente pelo DevPilot.';
      }
      if (repositoryInput) {
        repositoryInput.disabled = create;
        repositoryInput.required = admin && !create;
        repositoryInput.placeholder = create
          ? 'Será criado automaticamente pelo DevPilot'
          : 'a-castilho/projeto ou https://github.com/a-castilho/projeto';
      }
      if (organizationSelect) {
        if (admin && create && organization) organizationSelect.value = organization.id;
        organizationSelect.disabled = create;
      }
      if (submit) submit.textContent = admin && !create ? 'Criar projeto' : 'Criar projeto';
    }

    toggle?.addEventListener('change', syncProvisionMode);
    document.querySelectorAll('[data-open="project-modal"]').forEach(button => {
      button.addEventListener('click', () => setTimeout(syncProvisionMode, 0));
    });

    repositoryInput?.addEventListener('blur', () => {
      if (!superAdmin() || toggle?.checked || !repositoryInput.value.trim()) return;
      const normalized = normalizeRepositoryInput(repositoryInput.value);
      if (normalized.ok) repositoryInput.value = normalized.value;
    });

    slugInput?.addEventListener('input', () => { slugEdited = true; });
    nameInput?.addEventListener('input', () => {
      if (slugEdited) return;
      const slug = slugify(nameInput.value);
      if (slugInput) slugInput.value = slug.length === 1 ? `${slug}-repo` : slug;
    });

    form.addEventListener('reset', () => {
      slugEdited = false;
      setTimeout(syncProvisionMode, 0);
    });

    form.onsubmit = async event => {
      event.preventDefault();
      const f = new FormData(form);
      const admin = superAdmin();
      const create = !admin || Boolean(toggle?.checked);
      const common = {
        name: String(f.get('name') || '').trim(),
        slug: String(f.get('slug') || '').trim(),
        description: String(f.get('description') || ''),
        agents_md: String(f.get('agents_md') || ''),
        codex_config: {model: f.get('model'), reasoning_effort: 'medium', timeout_seconds: 1800},
      };

      try {
        if (create) {
          await api('/projects/provision', {method: 'POST', body: JSON.stringify(common)});
          toast(admin
            ? `Repositório privado a-castilho/${common.slug} criado e conectado`
            : `Projeto ${common.name} criado automaticamente`);
        } else {
          const normalized = normalizeRepositoryInput(f.get('repository_url'));
          if (!normalized.ok) throw new Error(normalized.error);
          if (repositoryInput) repositoryInput.value = normalized.value;
          await api('/projects', {method: 'POST', body: JSON.stringify({
            ...common,
            repository_url: normalized.value,
            organization_id: f.get('organization_id') || null,
            default_branch: f.get('default_branch') || 'main',
          })});
          toast('Projeto conectado');
        }
        form.closest('dialog').close();
        form.reset();
        await load();
      } catch (error) {
        toast(error.message || 'Falha ao criar projeto');
      }
    };

    syncProvisionMode();
  }

  function initBuilderRepositoryFlow() {
    const form = document.querySelector('#project-builder-form');
    if (!form) return;
    injectStyles();

    const repositoryGrid = form.querySelector('.builder-repository-grid');
    const repositoryInput = form.elements.namedItem('repository_url');
    const organization = form.elements.namedItem('organization_id');
    const organizationField = organization?.closest('label');
    const defaultBranch = form.elements.namedItem('default_branch');
    const defaultBranchField = defaultBranch?.closest('label');
    const existing = form.querySelector('#project-builder-existing-repository');
    const notice = form.querySelector('#project-builder-repository-notice');
    const repositoryCard = repositoryGrid?.closest('.builder-card');
    const cardHeading = repositoryCard?.querySelector('h3');
    const cardDescription = repositoryCard?.querySelector('p');
    const nameInput = form.elements.namedItem('name');
    const slugInput = form.elements.namedItem('slug');
    const submit = form.querySelector('#project-builder-submit');

    [repositoryGrid, notice, organizationField, defaultBranchField, existing].forEach(element => {
      if (element) element.dataset.gitAdminOnly = '1';
    });

    let feedback = form.querySelector('#project-builder-repository-error');
    if (!feedback && submit) {
      feedback = document.createElement('div');
      feedback.id = 'project-builder-repository-error';
      feedback.className = 'builder-repository-error';
      feedback.setAttribute('role', 'alert');
      feedback.setAttribute('aria-live', 'polite');
      submit.insertAdjacentElement('afterend', feedback);
    }

    const clearFeedback = () => {
      if (!feedback) return;
      feedback.textContent = '';
      feedback.classList.remove('show');
    };
    const showFeedback = message => {
      if (!feedback) return;
      feedback.textContent = String(message || REPOSITORY_FORMAT_ERROR);
      feedback.classList.add('show');
    };

    function forceAutomaticMode() {
      const createRadio = form.querySelector('input[name="repository_mode"][value="create"]');
      const connectRadio = form.querySelector('input[name="repository_mode"][value="connect"]');
      if (createRadio) {
        createRadio.disabled = false;
        createRadio.checked = true;
      }
      if (connectRadio) connectRadio.checked = false;
    }

    function syncBuilderRepositoryUi() {
      const admin = superAdmin();
      if (!admin) forceAutomaticMode();
      const mode = admin ? (form.elements.namedItem('repository_mode')?.value || 'connect') : 'create';
      const requiresExisting = admin && mode === 'connect';

      [repositoryGrid, notice, organizationField, defaultBranchField].forEach(element => {
        if (element) element.hidden = !admin;
      });
      if (existing) existing.hidden = !requiresExisting;
      if (repositoryInput) {
        repositoryInput.required = requiresExisting;
        repositoryInput.disabled = !requiresExisting;
      }
      if (organization) organization.disabled = !admin || mode === 'create';
      if (cardHeading) cardHeading.textContent = admin ? 'Repositório e execução' : 'Execução';
      if (cardDescription) {
        cardDescription.textContent = admin
          ? 'Como Super Admin, escolha criar o Git automaticamente ou conectar um repositório existente.'
          : 'O DevPilot cria e configura o Git automaticamente. Nenhuma informação de repositório é necessária.';
      }
      if (notice && admin) {
        notice.textContent = mode === 'create'
          ? 'O DevPilot criará um repositório privado automaticamente na organização a-castilho.'
          : 'Informe um repositório Git já existente para conectar o projeto.';
      }
      form.querySelectorAll('[data-repository-choice]').forEach(card => {
        card.hidden = !admin;
        card.classList.toggle('selected', admin && card.dataset.repositoryChoice === mode);
      });
      if (!requiresExisting) clearFeedback();
    }

    document.querySelectorAll('[data-project-builder-open]').forEach(button => {
      button.addEventListener('click', () => setTimeout(syncBuilderRepositoryUi, 0));
    });
    form.addEventListener('change', event => {
      if (event.target?.name === 'repository_mode') setTimeout(syncBuilderRepositoryUi, 0);
    });
    form.addEventListener('reset', () => setTimeout(syncBuilderRepositoryUi, 0));

    repositoryInput?.addEventListener('input', clearFeedback);
    repositoryInput?.addEventListener('blur', () => {
      if (!superAdmin() || !repositoryInput.value.trim()) return;
      const mode = form.elements.namedItem('repository_mode')?.value || 'connect';
      if (mode !== 'connect') return;
      const normalized = normalizeRepositoryInput(repositoryInput.value);
      if (normalized.ok) {
        repositoryInput.value = normalized.value;
        clearFeedback();
      } else {
        showFeedback(normalized.error);
      }
    });

    nameInput?.addEventListener('input', () => {
      if (!slugInput || String(slugInput.value || '').trim()) return;
      const slug = slugify(nameInput.value);
      slugInput.value = slug.length === 1 ? `${slug}-repo` : slug;
    }, true);

    async function createAutomaticProject() {
      const name = String(form.elements.namedItem('name')?.value || '').trim();
      const slug = String(form.elements.namedItem('slug')?.value || '').trim();
      const description = String(form.elements.namedItem('description')?.value || '').trim();
      const model = String(form.elements.namedItem('model')?.value || 'gpt-5.4').trim();
      const agentsMd = String(form.querySelector('#project-builder-agents-preview')?.textContent || '');
      const blueprint = builderBlueprint(form);
      if (submit) {
        submit.disabled = true;
        submit.textContent = 'Criando projeto…';
      }
      clearFeedback();
      try {
        await api('/projects/provision', {method: 'POST', body: JSON.stringify({
          name,
          slug,
          description,
          agents_md: agentsMd,
          codex_config: {
            model,
            reasoning_effort: 'medium',
            timeout_seconds: 1800,
            project_blueprint: blueprint,
          },
        })});
        toast(`Projeto ${name} criado automaticamente`);
        form.reset();
        form.querySelector('[data-builder-preset="saas-balanced"]')?.click();
        await load();
        showView('projects');
      } catch (error) {
        showFeedback(error.message || 'Falha ao criar projeto');
      } finally {
        if (submit) {
          submit.disabled = false;
          submit.textContent = 'Criar projeto';
        }
      }
    }

    form.addEventListener('submit', event => {
      if (!superAdmin()) {
        event.preventDefault();
        event.stopImmediatePropagation();
        void createAutomaticProject();
        return;
      }

      const mode = form.elements.namedItem('repository_mode')?.value || 'connect';
      if (mode !== 'connect') return;
      const normalized = normalizeRepositoryInput(repositoryInput?.value || '');
      if (!normalized.ok) {
        event.preventDefault();
        event.stopImmediatePropagation();
        showFeedback(normalized.error);
        repositoryInput?.focus();
        return;
      }
      if (repositoryInput) repositoryInput.value = normalized.value;
      clearFeedback();
    }, true);

    const projectsHost = document.querySelector('#projects-list');
    if (projectsHost) {
      new MutationObserver(decoratePendingProjects).observe(projectsHost, {childList: true, subtree: true});
    }
    setTimeout(() => {
      syncBuilderRepositoryUi();
      decoratePendingProjects();
    }, 0);
  }

  initLegacyProjectForm();
  initBuilderRepositoryFlow();
})();