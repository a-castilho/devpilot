(() => {
  'use strict';

  const originalForm = document.querySelector('#project-builder-form');
  if (!originalForm || originalForm.dataset.simpleBuilderReady === '1') return;

  // O cadastro antigo recebe listeners de provisionamento antes deste arquivo.
  // Substituir o nó inteiro elimina listeners legados que desabilitavam campos
  // e interceptavam o submit do novo formulário simples.
  const form = originalForm.cloneNode(false);
  form.id = 'project-builder-form';
  form.className = 'project-builder project-builder-simple';
  form.dataset.simpleBuilderReady = '1';
  form.setAttribute('autocomplete', 'off');
  originalForm.replaceWith(form);

  document.querySelector('#project-builder-sticky-action')?.remove();

  const slugify = value => String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 100);

  const TYPES = {
    web: 'Site / sistema web',
    app: 'Aplicativo',
    api: 'API / backend',
    automation: 'Automação',
    other: 'Outro',
  };

  function notify(message, type = 'info') {
    if (typeof window.toast === 'function') return window.toast(message, type);
    console[type === 'error' ? 'error' : 'info'](`[DevPilot] ${message}`);
  }

  function goProjects() {
    if (typeof window.showView === 'function') {
      window.showView('projects');
      return;
    }
    document.querySelector('[data-view="projects"], .nav[data-view="projects"]')?.click?.();
  }

  async function request(path, options = {}) {
    if (typeof window.api === 'function') return window.api(path, options);
    const token = String(localStorage.getItem('devpilot-token') || '');
    const response = await fetch(`/api${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data?.detail === 'string' ? data.detail : 'Não foi possível criar o projeto.';
      throw new Error(detail);
    }
    return data;
  }

  form.innerHTML = `
    <div class="simple-project-shell">
      <header class="simple-project-head">
        <button class="ghost simple-project-back" type="button" data-project-builder-close>← Projetos</button>
        <div>
          <span class="eyebrow">NOVO PROJETO</span>
          <h2>Cadastrar projeto</h2>
          <p>Informe somente o essencial. O DevPilot configura o restante automaticamente.</p>
        </div>
      </header>

      <section class="simple-project-card">
        <label class="simple-project-field">
          <span>Nome do projeto</span>
          <input name="name" type="text" autocomplete="off" maxlength="150" placeholder="Ex.: Site pessoal" required>
        </label>

        <label class="simple-project-field">
          <span>Tipo</span>
          <select name="project_type" required>
            <option value="web">Site / sistema web</option>
            <option value="app">Aplicativo</option>
            <option value="api">API / backend</option>
            <option value="automation">Automação</option>
            <option value="other">Outro</option>
          </select>
        </label>

        <label class="simple-project-field simple-project-wide">
          <span>O que esse projeto deve fazer?</span>
          <textarea name="description" rows="4" maxlength="5000" placeholder="Descreva o objetivo em poucas linhas."></textarea>
        </label>

        <label class="simple-project-field simple-project-wide">
          <span>Repositório GitHub</span>
          <input name="repository_url" type="text" autocomplete="off" maxlength="500" placeholder="organizacao/repositorio" required>
          <small>Ex.: a-castilho/site-pessoal</small>
        </label>

        <div class="simple-project-message" id="simple-project-message" role="status" aria-live="polite"></div>

        <div class="simple-project-actions">
          <button class="ghost" type="button" data-project-builder-close>Cancelar</button>
          <button class="primary" id="project-builder-submit" type="submit">Criar projeto</button>
        </div>
      </section>
    </div>`;

  form.querySelectorAll('input, textarea, select, button').forEach(control => {
    control.disabled = false;
    control.removeAttribute('aria-disabled');
    control.style.pointerEvents = 'auto';
    control.style.opacity = '1';
  });

  if (!document.getElementById('devpilot-simple-project-builder-style')) {
    const style = document.createElement('style');
    style.id = 'devpilot-simple-project-builder-style';
    style.textContent = `
      #new-project-view{pointer-events:auto!important}
      #new-project-view .project-builder-simple{display:block!important;max-width:760px;margin:0 auto;padding:18px 16px 110px;box-sizing:border-box;pointer-events:auto!important;opacity:1!important}
      #new-project-view .simple-project-shell,#new-project-view .simple-project-card,#new-project-view .simple-project-field{pointer-events:auto!important}
      .simple-project-shell{display:grid;gap:18px;width:100%}
      .simple-project-head{display:grid;gap:12px}.simple-project-head>div{display:grid;gap:5px}
      .simple-project-head h2{margin:0;font-size:30px;line-height:1.08}.simple-project-head p{margin:0;color:var(--muted,#94a6b8);font-size:14px;line-height:1.5}.simple-project-back{justify-self:start}
      .simple-project-card{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;padding:20px;border:1px solid rgba(91,220,207,.2);border-radius:18px;background:rgba(3,18,28,.82);box-shadow:0 18px 44px rgba(0,0,0,.18)}
      .simple-project-field{display:grid;gap:7px;min-width:0;color:#c7d5df;font-size:13px;font-weight:800}
      .simple-project-field input,.simple-project-field select,.simple-project-field textarea{width:100%;box-sizing:border-box;border:1px solid rgba(255,255,255,.12);border-radius:11px;background:#07141f;color:#e8f1f5;padding:12px 13px;font:inherit;outline:none;pointer-events:auto!important;opacity:1!important;cursor:text!important;touch-action:manipulation}
      .simple-project-field select{cursor:pointer!important}.simple-project-field textarea{resize:vertical;min-height:112px;line-height:1.45}
      .simple-project-field input:focus,.simple-project-field select:focus,.simple-project-field textarea:focus{border-color:rgba(77,226,207,.62);box-shadow:0 0 0 3px rgba(77,226,207,.08)}
      .simple-project-field small{color:var(--muted,#8196a8);font-size:11px;font-weight:600}.simple-project-wide{grid-column:1/-1}
      .simple-project-message{display:none;grid-column:1/-1;padding:10px 12px;border-radius:10px;font-size:13px;line-height:1.4}.simple-project-message.show{display:block}.simple-project-message.error{background:rgba(255,90,90,.08);border:1px solid rgba(255,90,90,.24);color:#ffb4b4}
      .simple-project-actions{grid-column:1/-1;display:flex;justify-content:flex-end;gap:10px;padding-top:4px}.simple-project-actions .primary{min-width:150px}
      @media(max-width:720px){#new-project-view .project-builder-simple{padding:12px 12px 105px}.simple-project-head h2{font-size:25px}.simple-project-card{grid-template-columns:1fr;padding:15px;gap:14px;border-radius:15px}.simple-project-wide,.simple-project-message,.simple-project-actions{grid-column:1}.simple-project-actions{position:relative;z-index:5;margin-top:4px;padding-top:8px}.simple-project-actions button{flex:1;min-height:46px}}
    `;
    document.head.appendChild(style);
  }

  function setMessage(message = '', error = false) {
    const host = form.querySelector('#simple-project-message');
    if (!host) return;
    host.textContent = message;
    host.className = `simple-project-message${message ? ' show' : ''}${error ? ' error' : ''}`;
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;

    const name = String(form.elements.namedItem('name')?.value || '').trim();
    const slug = slugify(name);
    const description = String(form.elements.namedItem('description')?.value || '').trim();
    const repositoryUrl = String(form.elements.namedItem('repository_url')?.value || '').trim();
    const projectType = String(form.elements.namedItem('project_type')?.value || 'web');
    const submit = form.querySelector('#project-builder-submit');

    if (slug.length < 2) {
      setMessage('Use um nome de projeto com pelo menos dois caracteres.', true);
      return;
    }

    const typeLabel = TYPES[projectType] || TYPES.other;
    const agentsMd = `# AGENTS.md — ${name}\n\n## Projeto\nTipo: ${typeLabel}\n\n## Objetivo\n${description || 'Evoluir o projeto conforme as solicitações registradas no DevPilot.'}\n\n## Regras essenciais\n- Preserve compatibilidade e segurança.\n- Não exponha credenciais ou segredos.\n- Execute testes relevantes antes de concluir alterações.\n- Registre claramente o que foi alterado.`;

    setMessage('');
    submit.disabled = true;
    submit.textContent = 'Criando…';

    try {
      await request('/projects', {
        method: 'POST',
        body: JSON.stringify({
          name,
          slug,
          description,
          repository_url: repositoryUrl,
          organization_id: null,
          default_branch: 'main',
          agents_md: agentsMd,
          codex_config: {simple_setup: true, project_type: projectType, model: 'gpt-5.4'},
        }),
      });
      if (typeof window.loadProjects === 'function') await Promise.resolve(window.loadProjects()).catch(() => null);
      notify(`Projeto ${name} criado.`);
      form.reset();
      goProjects();
    } catch (error) {
      const message = String(error?.message || 'Não foi possível criar o projeto.');
      setMessage(message, true);
      notify(message, 'error');
    } finally {
      submit.disabled = false;
      submit.textContent = 'Criar projeto';
    }
  });

  form.addEventListener('click', event => {
    if (!event.target.closest?.('[data-project-builder-close]')) return;
    event.preventDefault();
    goProjects();
  });

  document.querySelectorAll('[data-project-builder-open]').forEach(button => {
    if (button.dataset.simpleBuilderOpenBound === '1') return;
    button.dataset.simpleBuilderOpenBound = '1';
    button.addEventListener('click', () => {
      if (typeof window.showView === 'function') window.showView('new-project');
      window.setTimeout(() => form.elements.namedItem('name')?.focus?.(), 60);
    });
  });

  console.info('[DevPilot] Cadastro simples de projeto isolado do runtime legado');
})();