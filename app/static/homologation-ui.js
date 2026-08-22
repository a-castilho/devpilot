(() => {
  const OPERATORS = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);

  function currentRole() {
    return String(
      (typeof state !== 'undefined' && state.currentUser?.role) || ''
    ).toUpperCase();
  }

  function canOperate() {
    return OPERATORS.has(currentRole());
  }

  function projectBlueprint(form) {
    const result = {};
    form.querySelectorAll('[data-builder-group]').forEach(section => {
      const key = section.dataset.builderGroup;
      if (!key) return;
      result[key] = [...section.querySelectorAll('.choice-card.selected[data-option]')]
        .map(card => card.dataset.option)
        .filter(Boolean);
    });
    result.custom_technologies = String(
      form.elements.namedItem('custom_technologies')?.value || ''
    ).split(',').map(item => item.trim()).filter(Boolean).slice(0, 30);
    result.delivery = {
      conventional_commits: Boolean(form.elements.namedItem('conventional_commits')?.checked),
      protected_main: Boolean(form.elements.namedItem('protected_main')?.checked),
      pull_request_review: Boolean(form.elements.namedItem('pull_request_review')?.checked),
      migrations_reversible: Boolean(form.elements.namedItem('migrations_reversible')?.checked),
    };
    return result;
  }

  function enableManagedCreate() {
    if (!canOperate()) return;
    const form = document.querySelector('#project-builder-form');
    if (!form) return;
    const create = form.querySelector('input[name="repository_mode"][value="create"]');
    if (create) create.disabled = false;

    const mode = form.elements.namedItem('repository_mode')?.value || 'connect';
    const notice = form.querySelector('#project-builder-repository-notice');
    if (notice && mode === 'create') {
      notice.textContent =
        'O DevPilot criará GitHub + starter + Neon + Render + Vercel e preparará a homologação.';
    }
  }

  async function submitManagedProject(event) {
    const form = event.currentTarget;
    if (!canOperate()) return;
    const mode = form.elements.namedItem('repository_mode')?.value || 'connect';
    if (mode !== 'create') return;

    event.preventDefault();
    event.stopImmediatePropagation();

    const name = String(form.elements.namedItem('name')?.value || '').trim();
    const slug = String(form.elements.namedItem('slug')?.value || '').trim();
    const description = String(form.elements.namedItem('description')?.value || '').trim();
    const model = String(form.elements.namedItem('model')?.value || 'gpt-5.4').trim();
    const agentsMd = String(
      form.querySelector('#project-builder-agents-preview')?.textContent || ''
    );
    const button = form.querySelector('#project-builder-submit');

    if (!name || !slug) {
      toast('Informe nome e slug do projeto');
      return;
    }

    const payload = {
      name,
      slug,
      description,
      agents_md: agentsMd,
      provision_cloud: true,
      codex_config: {
        model,
        reasoning_effort: 'medium',
        timeout_seconds: 1800,
        project_blueprint: projectBlueprint(form),
      },
    };

    const original = button?.textContent || 'Criar projeto';
    if (button) {
      button.disabled = true;
      button.textContent = 'Criando e publicando homologação…';
    }

    try {
      const result = await api('/projects/homologation', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      const cloud = result?.homologation || {};
      if (cloud.status === 'provisioned') {
        toast(`Projeto ${name} criado. Homologação iniciada.`);
      } else if (cloud.missing_credentials?.length) {
        toast(`Projeto criado. Cloud pendente: ${cloud.missing_credentials.join(', ')}`);
      } else {
        toast(`Projeto ${name} criado. Homologação: ${cloud.status || 'pendente'}.`);
      }

      form.reset();
      form.querySelector('[data-builder-preset="saas-balanced"]')?.click();
      await load();
      showView('projects');
      window.setTimeout(decorateHomologationButtons, 0);
    } catch (error) {
      toast(error.message || 'Falha ao criar projeto para homologação');
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = original;
      }
    }
  }

  async function testHomologation(project, button) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Validando…';

    try {
      let status = await api(`/projects/${project.id}/homologation`);
      let cloud = status?.homologation || {};

      if (cloud.status !== 'provisioned') {
        status = await api(`/projects/${project.id}/homologation/provision`, {
          method: 'POST',
        });
        cloud = status?.homologation || {};
      }

      const verification = await api(`/projects/${project.id}/homologation/verify`, {
        method: 'POST',
      });
      if (verification.status === 'ready') {
        toast('Homologação pronta: Vercel → Render → banco validado');
        if (verification.url) {
          window.open(verification.url, '_blank', 'noopener,noreferrer');
        }
      } else {
        const failing = (verification.checks || [])
          .filter(check => !check.ok)
          .map(check => check.name);
        toast(
          failing.length
            ? `Homologação ainda subindo: ${failing.join(', ')}`
            : 'Homologação ainda está sendo preparada'
        );
      }
    } catch (error) {
      toast(error.message || 'Falha ao testar homologação');
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function decorateHomologationButtons() {
    if (!canOperate() || typeof state === 'undefined' || !Array.isArray(state.projects)) return;
    const host = document.querySelector('#projects-list');
    if (!host) return;

    [...host.querySelectorAll('.project-card')].forEach((card, index) => {
      const project = state.projects[index];
      if (!project || !String(project.repository_url || '').trim()) return;
      if (card.querySelector('.homologation-test-button')) return;
      const actions = card.querySelector('.list-row > div:last-child');
      if (!actions) return;

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'link homologation-test-button';
      button.textContent = 'Testar homologação';
      button.title = 'Provisionar se necessário e validar Vercel → Render → banco';
      button.addEventListener('click', () => testHomologation(project, button));
      actions.appendChild(button);
    });
  }

  function install() {
    const form = document.querySelector('#project-builder-form');
    if (form && !form.dataset.homologationSubmit) {
      form.dataset.homologationSubmit = '1';
      form.addEventListener('submit', submitManagedProject, true);
      form.addEventListener('change', event => {
        if (event.target?.name === 'repository_mode') {
          window.setTimeout(enableManagedCreate, 0);
        }
      });
    }

    const dialog = form?.closest('dialog');
    if (dialog && !dialog.dataset.homologationObserved) {
      dialog.dataset.homologationObserved = '1';
      new MutationObserver(enableManagedCreate).observe(dialog, {
        attributes: true,
        attributeFilter: ['open'],
      });
    }

    const host = document.querySelector('#projects-list');
    if (host && !host.dataset.homologationObserved) {
      host.dataset.homologationObserved = '1';
      new MutationObserver(decorateHomologationButtons).observe(host, {childList: true});
    }

    enableManagedCreate();
    decorateHomologationButtons();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, {once: true});
  } else {
    install();
  }
  window.setInterval(install, 1200);
})();
