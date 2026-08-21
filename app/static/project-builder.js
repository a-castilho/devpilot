(() => {
  const form = document.querySelector('#project-builder-form');
  if (!form) return;

  const groups = [
    {
      key: 'project_type',
      title: 'Tipo de projeto',
      description: 'Escolha o formato principal da solução.',
      multiple: false,
      options: [
        ['saas', 'SaaS Web', 'Produto multiusuário e painel web'],
        ['api', 'API / Backend', 'Serviço HTTP para integrações'],
        ['admin', 'Painel administrativo', 'Backoffice e operações'],
        ['pwa', 'PWA / Mobile Web', 'Experiência instalável e responsiva'],
        ['automation', 'Automação / Worker', 'Filas, robôs e rotinas'],
        ['microservices', 'Microserviços', 'Serviços independentes'],
        ['cli', 'CLI', 'Ferramenta de terminal'],
        ['data-ai', 'Dados / IA', 'Pipelines, modelos e processamento'],
      ],
    },
    {
      key: 'languages',
      title: 'Linguagens',
      description: 'Pode combinar mais de uma linguagem.',
      multiple: true,
      options: [
        ['python', 'Python', 'Backend, IA e automação'],
        ['typescript', 'TypeScript', 'Frontend e backend tipado'],
        ['javascript', 'JavaScript', 'Web e Node.js'],
        ['php', 'PHP', 'Web e APIs'],
        ['java', 'Java', 'Serviços corporativos'],
        ['go', 'Go', 'Serviços leves e concorrentes'],
        ['kotlin', 'Kotlin', 'Backend e Android'],
        ['csharp', 'C#', '.NET e serviços'],
      ],
    },
    {
      key: 'backend',
      title: 'Backend / Framework',
      description: 'Base principal para regras de negócio e APIs.',
      multiple: false,
      options: [
        ['fastapi', 'FastAPI', 'Python assíncrono e OpenAPI'],
        ['django', 'Django', 'Python completo e produtivo'],
        ['nestjs', 'NestJS', 'Node.js modular com TypeScript'],
        ['express', 'Express', 'Node.js minimalista'],
        ['laravel', 'Laravel', 'PHP moderno e produtivo'],
        ['symfony', 'Symfony', 'PHP modular e corporativo'],
        ['spring', 'Spring Boot', 'Java para serviços robustos'],
        ['none', 'Sem backend', 'Projeto exclusivamente cliente/estático'],
      ],
    },
    {
      key: 'frontend',
      title: 'Frontend',
      description: 'Interface principal do projeto.',
      multiple: false,
      options: [
        ['react', 'React', 'SPA e ecossistema amplo'],
        ['nextjs', 'Next.js', 'React com SSR e rotas'],
        ['vue', 'Vue', 'Interface progressiva'],
        ['nuxt', 'Nuxt', 'Vue com SSR e rotas'],
        ['svelte', 'Svelte', 'Bundle enxuto e reativo'],
        ['htmx', 'HTMX', 'HTML orientado pelo servidor'],
        ['vanilla', 'HTML / JS', 'Sem framework'],
        ['none', 'Sem frontend', 'API, worker ou CLI'],
      ],
    },
    {
      key: 'architecture',
      title: 'Arquitetura',
      description: 'Estrutura que guiará módulos, dependências e crescimento.',
      multiple: false,
      options: [
        ['clean', 'Clean Architecture', 'Dependências apontando para o domínio'],
        ['hexagonal', 'Hexagonal', 'Ports & adapters'],
        ['ddd', 'DDD', 'Domínio e linguagem ubíqua'],
        ['modular-monolith', 'Monólito modular', 'Módulos isolados no mesmo deploy'],
        ['mvc', 'MVC', 'Separação clássica de responsabilidades'],
        ['microservices', 'Microserviços', 'Serviços independentes por domínio'],
      ],
    },
    {
      key: 'patterns',
      title: 'Padrões de projeto',
      description: 'Selecione os padrões que devem orientar a implementação.',
      multiple: true,
      options: [
        ['repository', 'Repository', 'Persistência atrás de interfaces'],
        ['service-layer', 'Service Layer', 'Casos de uso e orquestração'],
        ['factory', 'Factory', 'Criação desacoplada de objetos'],
        ['strategy', 'Strategy', 'Algoritmos substituíveis'],
        ['adapter', 'Adapter', 'Integrações isoladas'],
        ['observer', 'Observer', 'Eventos e reações desacopladas'],
        ['cqrs', 'CQRS', 'Leitura e escrita separadas'],
        ['unit-of-work', 'Unit of Work', 'Transações consistentes'],
        ['dependency-injection', 'DI', 'Dependências explícitas e testáveis'],
      ],
    },
    {
      key: 'databases',
      title: 'Dados e cache',
      description: 'Bancos, cache e armazenamento principal.',
      multiple: true,
      options: [
        ['postgresql', 'PostgreSQL', 'Relacional principal'],
        ['mysql', 'MySQL', 'Relacional amplamente suportado'],
        ['sqlite', 'SQLite', 'Local e projetos enxutos'],
        ['mongodb', 'MongoDB', 'Documentos e flexibilidade'],
        ['redis', 'Redis', 'Cache, sessão e filas'],
        ['dynamodb', 'DynamoDB', 'NoSQL gerenciado na AWS'],
        ['s3', 'S3 compatível', 'Arquivos e objetos'],
      ],
    },
    {
      key: 'interfaces',
      title: 'APIs e integrações',
      description: 'Como o sistema conversa com clientes e outros serviços.',
      multiple: true,
      options: [
        ['rest', 'REST', 'HTTP e recursos'],
        ['graphql', 'GraphQL', 'Consulta flexível'],
        ['websocket', 'WebSocket', 'Tempo real'],
        ['grpc', 'gRPC', 'RPC eficiente entre serviços'],
        ['webhooks', 'Webhooks', 'Eventos para terceiros'],
        ['openapi', 'OpenAPI', 'Contrato e documentação automática'],
      ],
    },
    {
      key: 'security',
      title: 'Segurança e acesso',
      description: 'Controles essenciais já definidos na especificação.',
      multiple: true,
      options: [
        ['oauth2', 'OAuth2 / OIDC', 'Login federado e tokens'],
        ['jwt', 'JWT', 'Sessão stateless'],
        ['rbac', 'RBAC', 'Permissões por função'],
        ['multi-tenant', 'Multi-tenant', 'Isolamento entre clientes'],
        ['audit-log', 'Auditoria', 'Trilha de ações críticas'],
        ['rate-limit', 'Rate limit', 'Proteção contra abuso'],
        ['secret-vault', 'Vault de segredos', 'Credenciais fora do código'],
      ],
    },
    {
      key: 'tests',
      title: 'Testes',
      description: 'Qualidade mínima exigida antes de liberar mudanças.',
      multiple: true,
      options: [
        ['unit', 'Unitários', 'Regras isoladas'],
        ['integration', 'Integração', 'Banco e serviços reais/controlados'],
        ['e2e', 'E2E', 'Fluxos completos do usuário'],
        ['contract', 'Contrato', 'Compatibilidade entre APIs'],
        ['coverage', 'Cobertura', 'Meta de cobertura acompanhada'],
      ],
    },
    {
      key: 'quality',
      title: 'Qualidade de código',
      description: 'Automação para manter o padrão do repositório.',
      multiple: true,
      options: [
        ['lint', 'Lint', 'Regras estáticas'],
        ['format', 'Formatter', 'Formatação automática'],
        ['type-check', 'Type check', 'Verificação de tipos'],
        ['pre-commit', 'Pre-commit', 'Validação antes do commit'],
        ['sast', 'SAST', 'Análise estática de segurança'],
        ['dependency-scan', 'Dependências', 'Auditoria de vulnerabilidades'],
      ],
    },
    {
      key: 'infrastructure',
      title: 'Infraestrutura e deploy',
      description: 'Ambiente de execução, entrega e infraestrutura como código.',
      multiple: true,
      options: [
        ['docker', 'Docker', 'Ambiente reproduzível'],
        ['compose', 'Docker Compose', 'Stack local integrada'],
        ['github-actions', 'GitHub Actions', 'CI/CD'],
        ['vercel', 'Vercel', 'Frontend e edge'],
        ['render', 'Render', 'Web services e workers'],
        ['aws', 'AWS', 'Cloud AWS'],
        ['gcp', 'GCP', 'Google Cloud'],
        ['azure', 'Azure', 'Microsoft Cloud'],
        ['kubernetes', 'Kubernetes', 'Orquestração de containers'],
        ['terraform', 'Terraform', 'Infraestrutura como código'],
      ],
    },
    {
      key: 'documentation',
      title: 'Documentação',
      description: 'Arquivos e contratos que devem nascer com o projeto.',
      multiple: true,
      options: [
        ['readme', 'README', 'Instalação e operação'],
        ['agents', 'AGENTS.md', 'Regras para agentes'],
        ['adr', 'ADR', 'Decisões arquiteturais'],
        ['architecture', 'Arquitetura', 'Mapa de módulos e dependências'],
        ['api-docs', 'API docs', 'Contratos e exemplos'],
        ['runbook', 'Runbook', 'Operação e incidentes'],
      ],
    },
  ];

  const presets = {
    'saas-balanced': {
      project_type: ['saas'], languages: ['python', 'typescript'], backend: ['fastapi'], frontend: ['react'],
      architecture: ['clean'], patterns: ['repository', 'service-layer', 'adapter', 'dependency-injection'],
      databases: ['postgresql', 'redis'], interfaces: ['rest', 'openapi', 'webhooks'],
      security: ['oauth2', 'rbac', 'multi-tenant', 'audit-log', 'rate-limit', 'secret-vault'],
      tests: ['unit', 'integration', 'e2e', 'coverage'], quality: ['lint', 'format', 'type-check', 'pre-commit', 'sast'],
      infrastructure: ['docker', 'compose', 'github-actions', 'render'], documentation: ['readme', 'agents', 'adr', 'architecture', 'api-docs'],
    },
    'api-fast': {
      project_type: ['api'], languages: ['python'], backend: ['fastapi'], frontend: ['none'], architecture: ['hexagonal'],
      patterns: ['repository', 'service-layer', 'adapter', 'dependency-injection'], databases: ['postgresql', 'redis'],
      interfaces: ['rest', 'openapi', 'webhooks'], security: ['jwt', 'rbac', 'audit-log', 'rate-limit', 'secret-vault'],
      tests: ['unit', 'integration', 'contract', 'coverage'], quality: ['lint', 'format', 'type-check', 'pre-commit'],
      infrastructure: ['docker', 'compose', 'github-actions', 'render'], documentation: ['readme', 'agents', 'api-docs', 'runbook'],
    },
    'lean-mvp': {
      project_type: ['saas'], languages: ['typescript'], backend: ['nestjs'], frontend: ['react'], architecture: ['modular-monolith'],
      patterns: ['service-layer', 'repository', 'dependency-injection'], databases: ['postgresql'], interfaces: ['rest', 'openapi'],
      security: ['jwt', 'rbac', 'rate-limit'], tests: ['unit', 'integration'], quality: ['lint', 'format', 'type-check'],
      infrastructure: ['docker', 'github-actions'], documentation: ['readme', 'agents'],
    },
    enterprise: {
      project_type: ['microservices'], languages: ['java', 'typescript'], backend: ['spring'], frontend: ['react'], architecture: ['ddd'],
      patterns: ['repository', 'service-layer', 'factory', 'strategy', 'adapter', 'observer', 'cqrs', 'unit-of-work', 'dependency-injection'],
      databases: ['postgresql', 'redis', 's3'], interfaces: ['rest', 'grpc', 'webhooks', 'openapi'],
      security: ['oauth2', 'rbac', 'multi-tenant', 'audit-log', 'rate-limit', 'secret-vault'],
      tests: ['unit', 'integration', 'e2e', 'contract', 'coverage'], quality: ['lint', 'format', 'type-check', 'pre-commit', 'sast', 'dependency-scan'],
      infrastructure: ['docker', 'compose', 'github-actions', 'kubernetes', 'terraform'], documentation: ['readme', 'agents', 'adr', 'architecture', 'api-docs', 'runbook'],
    },
  };

  const selected = Object.create(null);
  let slugEdited = false;

  const slugify = value => String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 100);

  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  })[char]);

  const optionLabel = (groupKey, optionId) => {
    const group = groups.find(item => item.key === groupKey);
    const option = group?.options.find(item => item[0] === optionId);
    return option?.[1] || optionId;
  };

  const asArray = value => Array.isArray(value) ? value : [];

  function seedDefaults() {
    Object.entries(presets['saas-balanced']).forEach(([key, values]) => {
      selected[key] = new Set(values);
    });
  }

  function renderGroups() {
    const host = document.querySelector('#project-builder-groups');
    if (!host) return;
    host.innerHTML = groups.map(group => `
      <section class="builder-group" data-builder-group="${escapeHtml(group.key)}">
        <div class="builder-group-head">
          <div><h3>${escapeHtml(group.title)}</h3><p>${escapeHtml(group.description)}</p></div>
          <span>${group.multiple ? 'múltipla escolha' : 'escolha única'}</span>
        </div>
        <div class="choice-strip" data-choice-strip="${escapeHtml(group.key)}" tabindex="0" aria-label="${escapeHtml(group.title)}">
          ${group.options.map(([id, label, meta]) => `
            <button type="button" class="choice-card" data-group="${escapeHtml(group.key)}" data-option="${escapeHtml(id)}" aria-pressed="false">
              <strong>${escapeHtml(label)}</strong><small>${escapeHtml(meta)}</small><i aria-hidden="true">✓</i>
            </button>`).join('')}
        </div>
      </section>`).join('');

    host.querySelectorAll('.choice-card').forEach(button => {
      button.addEventListener('click', () => {
        const strip = button.closest('.choice-strip');
        if (strip?.dataset.dragged === '1') {
          strip.dataset.dragged = '0';
          return;
        }
        selectOption(button.dataset.group, button.dataset.option);
      });
    });

    host.querySelectorAll('.choice-strip').forEach(enableMouseDrag);
    syncSelectionUI();
  }

  function enableMouseDrag(strip) {
    let down = false;
    let startX = 0;
    let startScroll = 0;
    let moved = false;

    strip.addEventListener('pointerdown', event => {
      if (event.pointerType !== 'mouse' || event.button !== 0) return;
      down = true;
      moved = false;
      startX = event.clientX;
      startScroll = strip.scrollLeft;
      strip.classList.add('is-dragging');
    });
    strip.addEventListener('pointermove', event => {
      if (!down) return;
      const delta = event.clientX - startX;
      if (Math.abs(delta) > 6) moved = true;
      if (moved) strip.scrollLeft = startScroll - delta;
    });
    const stop = () => {
      if (!down) return;
      down = false;
      strip.classList.remove('is-dragging');
      strip.dataset.dragged = moved ? '1' : '0';
      if (moved) window.setTimeout(() => { strip.dataset.dragged = '0'; }, 120);
    };
    strip.addEventListener('pointerup', stop);
    strip.addEventListener('pointercancel', stop);
    strip.addEventListener('pointerleave', stop);
  }

  function selectOption(groupKey, optionId) {
    const group = groups.find(item => item.key === groupKey);
    if (!group) return;
    if (!selected[groupKey]) selected[groupKey] = new Set();
    const set = selected[groupKey];
    if (group.multiple) {
      if (set.has(optionId)) set.delete(optionId); else set.add(optionId);
    } else {
      set.clear();
      set.add(optionId);
    }
    syncSelectionUI();
  }

  function syncSelectionUI() {
    form.querySelectorAll('.choice-card').forEach(button => {
      const active = selected[button.dataset.group]?.has(button.dataset.option) || false;
      button.classList.toggle('selected', active);
      button.setAttribute('aria-pressed', String(active));
    });
    updateSummary();
  }

  function applyPreset(name) {
    const preset = presets[name];
    if (!preset) return;
    groups.forEach(group => { selected[group.key] = new Set(); });
    Object.entries(preset).forEach(([key, values]) => { selected[key] = new Set(values); });
    document.querySelectorAll('[data-builder-preset]').forEach(button => {
      button.classList.toggle('active', button.dataset.builderPreset === name);
    });
    syncSelectionUI();
  }

  function blueprint() {
    const result = {};
    groups.forEach(group => {
      result[group.key] = [...(selected[group.key] || [])];
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

  function listFor(key, data) {
    return asArray(data[key]).map(id => optionLabel(key, id)).join(', ') || 'Não definido';
  }

  function buildAgentsMd(data) {
    const projectName = String(form.elements.namedItem('name')?.value || '').trim() || 'Novo projeto';
    const description = String(form.elements.namedItem('description')?.value || '').trim();
    const customRules = String(form.elements.namedItem('extra_rules')?.value || '').trim();
    const delivery = Object.entries(data.delivery).filter(([, enabled]) => enabled).map(([key]) => ({
      conventional_commits: 'Conventional Commits', protected_main: 'branch principal protegida', pull_request_review: 'revisão por Pull Request', migrations_reversible: 'migrações reversíveis',
    })[key]);

    return `# AGENTS.md — ${projectName}\n\n## Objetivo\n${description || 'Implementar e evoluir o projeto conforme a especificação técnica selecionada no DevPilot.'}\n\n## Stack selecionada\n- Tipo: ${listFor('project_type', data)}\n- Linguagens: ${listFor('languages', data)}\n- Backend: ${listFor('backend', data)}\n- Frontend: ${listFor('frontend', data)}\n- Arquitetura: ${listFor('architecture', data)}\n- Padrões: ${listFor('patterns', data)}\n- Dados/cache: ${listFor('databases', data)}\n- APIs/integrações: ${listFor('interfaces', data)}\n- Segurança: ${listFor('security', data)}\n- Testes: ${listFor('tests', data)}\n- Qualidade: ${listFor('quality', data)}\n- Infra/deploy: ${listFor('infrastructure', data)}\n- Documentação: ${listFor('documentation', data)}${data.custom_technologies.length ? `\n- Tecnologias adicionais: ${data.custom_technologies.join(', ')}` : ''}\n\n## Regras de engenharia\n- Preserve isolamento de módulos, tenants e credenciais conforme a arquitetura escolhida.\n- Não exponha segredos, tokens ou variáveis sensíveis no código, logs ou respostas.\n- Implemente validação de entrada, tratamento explícito de falhas e observabilidade nas operações críticas.\n- Mantenha dependências externas atrás de adapters/interfaces quando aplicável.\n- Toda alteração relevante deve incluir testes compatíveis com a estratégia selecionada.\n- Mudanças destrutivas, deploy, merge, push e dependências exigem aprovação antes da execução.\n- Registre decisões arquiteturais importantes e mantenha a documentação sincronizada com o código.\n${delivery.length ? `- Fluxo de entrega: ${delivery.join(', ')}.\n` : ''}${customRules ? `\n## Regras adicionais do cliente\n${customRules}\n` : ''}`;
  }

  function updateSummary() {
    const data = blueprint();
    const count = groups.reduce((sum, group) => sum + asArray(data[group.key]).length, 0) + data.custom_technologies.length;
    const countEl = document.querySelector('#project-builder-selection-count');
    if (countEl) countEl.textContent = `${count} escolhas`;
    const summary = document.querySelector('#project-builder-summary');
    if (summary) {
      const rows = [
        ['Projeto', listFor('project_type', data)], ['Linguagens', listFor('languages', data)],
        ['Backend', listFor('backend', data)], ['Frontend', listFor('frontend', data)],
        ['Arquitetura', listFor('architecture', data)], ['Dados', listFor('databases', data)],
        ['Infra', listFor('infrastructure', data)],
      ];
      summary.innerHTML = rows.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join('');
    }
    const preview = document.querySelector('#project-builder-agents-preview');
    if (preview) preview.textContent = buildAgentsMd(data);
  }

  function castilhoOrganization() {
    return state.organizations.find(org => String(org.external_login || '').toLowerCase() === 'a-castilho') || null;
  }

  function fillBuilderOrganizations() {
    const select = document.querySelector('#project-builder-organization');
    if (!select) return;
    select.innerHTML = '<option value="">Sem organização</option>' + (isSuperAdmin()
      ? state.organizations.map(org => `<option value="${escapeHtml(org.id)}">${escapeHtml(org.name)}</option>`).join('')
      : '');
    const castilho = castilhoOrganization();
    if (castilho) select.value = castilho.id;
  }

  function syncRepositoryMode() {
    const mode = form.elements.namedItem('repository_mode')?.value || 'connect';
    const create = mode === 'create';
    const existing = document.querySelector('#project-builder-existing-repository');
    if (existing) existing.hidden = create;
    const url = form.elements.namedItem('repository_url');
    if (url) url.required = !create;
    const organization = document.querySelector('#project-builder-organization');
    if (organization) organization.disabled = create;
    const notice = document.querySelector('#project-builder-repository-notice');
    if (notice) {
      notice.textContent = create
        ? (isSuperAdmin() ? 'O DevPilot criará um repositório privado na organização a-castilho.' : 'A criação automática de repositório exige perfil Super Admin.')
        : 'Informe um repositório Git já existente para conectar o projeto.';
    }
    document.querySelectorAll('[data-repository-choice]').forEach(card => {
      card.classList.toggle('selected', card.dataset.repositoryChoice === mode);
    });
  }

  function openBuilder() {
    fillBuilderOrganizations();
    if (!isSuperAdmin()) {
      const createRadio = form.querySelector('input[name="repository_mode"][value="create"]');
      if (createRadio) createRadio.disabled = true;
      const connectRadio = form.querySelector('input[name="repository_mode"][value="connect"]');
      if (connectRadio) connectRadio.checked = true;
    }
    syncRepositoryMode();
    showView('new-project');
    const title = document.querySelector('#page-title');
    if (title) title.textContent = 'Novo projeto';
    window.scrollTo({top: 0, behavior: 'smooth'});
  }

  document.querySelectorAll('[data-project-builder-open]').forEach(button => button.addEventListener('click', openBuilder));
  document.querySelectorAll('[data-project-builder-close]').forEach(button => button.addEventListener('click', () => showView('projects')));
  document.querySelectorAll('[data-builder-preset]').forEach(button => button.addEventListener('click', () => applyPreset(button.dataset.builderPreset)));
  form.querySelectorAll('input[name="repository_mode"]').forEach(input => input.addEventListener('change', syncRepositoryMode));
  form.querySelectorAll('input, textarea, select').forEach(input => input.addEventListener('input', updateSummary));

  const nameInput = form.elements.namedItem('name');
  const slugInput = form.elements.namedItem('slug');
  slugInput?.addEventListener('input', () => { slugEdited = true; });
  nameInput?.addEventListener('input', () => {
    if (slugEdited) return;
    const value = slugify(nameInput.value);
    if (slugInput) slugInput.value = value.length === 1 ? `${value}-repo` : value;
    updateSummary();
  });

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const data = blueprint();
    const name = String(form.elements.namedItem('name')?.value || '').trim();
    const slug = String(form.elements.namedItem('slug')?.value || '').trim();
    const description = String(form.elements.namedItem('description')?.value || '').trim();
    const model = String(form.elements.namedItem('model')?.value || 'gpt-5.4').trim();
    const agentsMd = buildAgentsMd(data);
    const mode = form.elements.namedItem('repository_mode')?.value || 'connect';
    const common = {
      name,
      slug,
      description,
      agents_md: agentsMd,
      codex_config: {
        model,
        reasoning_effort: 'medium',
        timeout_seconds: 1800,
        project_blueprint: data,
      },
    };
    const submit = document.querySelector('#project-builder-submit');
    if (submit) { submit.disabled = true; submit.textContent = 'Criando projeto…'; }
    try {
      if (mode === 'create') {
        if (!isSuperAdmin()) throw new Error('A criação automática exige perfil Super Admin');
        if (!castilhoOrganization()) throw new Error('Conecte primeiro a organização a-castilho em Organizações');
        await api('/projects/provision', {method: 'POST', body: JSON.stringify(common)});
        toast(`Projeto ${name} criado com repositório privado`);
      } else {
        const repositoryUrl = String(form.elements.namedItem('repository_url')?.value || '').trim();
        if (!repositoryUrl) throw new Error('Informe o repositório Git existente');
        await api('/projects', {method: 'POST', body: JSON.stringify({
          ...common,
          repository_url: repositoryUrl,
          organization_id: isSuperAdmin() ? (form.elements.namedItem('organization_id')?.value || null) : null,
          default_branch: String(form.elements.namedItem('default_branch')?.value || 'main').trim() || 'main',
        })});
        toast(`Projeto ${name} conectado com a especificação técnica`);
      }
      form.reset();
      slugEdited = false;
      applyPreset('saas-balanced');
      await load();
      showView('projects');
    } catch (error) {
      toast(error.message || 'Falha ao criar projeto');
    } finally {
      if (submit) { submit.disabled = false; submit.textContent = 'Criar projeto'; }
    }
  });

  seedDefaults();
  renderGroups();
  syncRepositoryMode();
})();