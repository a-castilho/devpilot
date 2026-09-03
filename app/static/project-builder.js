(() => {
  'use strict';

  if (window.__devpilotProjectBuilderV94) return;

  const form = document.querySelector('#project-builder-form');
  const host = document.querySelector('#project-builder-groups');
  if (!form || !host) return;

  const bootStartedAt = performance.now();

  const groups = [
    {
      key: 'project_type',
      title: 'Tipo de projeto',
      description: 'Escolha o formato principal da solução.',
      multiple: false,
      options: [
        ['saas', 'SaaS Web', 'Produto multiusuário e painel web'],
        ['hotsite', 'Hotsite', 'Site enxuto para campanha, evento ou lançamento'],
        ['landing-page', 'Landing page', 'Página focada em conversão e captação de leads'],
        ['personal-site', 'Site pessoal', 'Presença pessoal, currículo, biografia e contatos'],
        ['portfolio', 'Portfólio', 'Projetos, cases, serviços e apresentação profissional'],
        ['institutional-site', 'Site institucional', 'Empresa, serviços, equipe, contatos e conteúdo'],
        ['blog-portal', 'Blog / Portal', 'Conteúdo editorial, categorias e publicação recorrente'],
        ['ecommerce', 'E-commerce', 'Catálogo, carrinho, checkout e pedidos'],
        ['docs-site', 'Site de documentação', 'Documentação técnica, guias e base de conhecimento'],
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
        ['html', 'HTML5', 'Estrutura semântica para web'],
        ['css', 'CSS3', 'Estilos, responsividade e animações'],
        ['python', 'Python', 'Backend, IA e automação'],
        ['typescript', 'TypeScript', 'Frontend e backend tipado'],
        ['javascript', 'JavaScript', 'Web e Node.js'],
        ['php', 'PHP', 'Web e APIs'],
        ['java', 'Java', 'Serviços corporativos'],
        ['go', 'Go', 'Serviços leves e concorrentes'],
        ['rust', 'Rust', 'Performance e segurança de memória'],
        ['ruby', 'Ruby', 'Web produtiva e automação'],
        ['dart', 'Dart', 'Flutter e aplicações multiplataforma'],
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
        ['flask', 'Flask', 'Python leve e flexível'],
        ['nestjs', 'NestJS', 'Node.js modular com TypeScript'],
        ['express', 'Express', 'Node.js minimalista'],
        ['laravel', 'Laravel', 'PHP moderno e produtivo'],
        ['symfony', 'Symfony', 'PHP modular e corporativo'],
        ['spring', 'Spring Boot', 'Java para serviços robustos'],
        ['dotnet', 'ASP.NET Core', '.NET moderno para APIs e aplicações'],
        ['rails', 'Ruby on Rails', 'Web full-stack produtiva'],
        ['gin', 'Gin', 'APIs rápidas em Go'],
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
        ['angular', 'Angular', 'Framework completo para aplicações web'],
        ['svelte', 'Svelte', 'Bundle enxuto e reativo'],
        ['sveltekit', 'SvelteKit', 'Svelte com SSR, rotas e server actions'],
        ['astro', 'Astro', 'Sites rápidos orientados a conteúdo'],
        ['remix', 'Remix', 'React com foco em web standards'],
        ['htmx', 'HTMX', 'HTML orientado pelo servidor'],
        ['vanilla', 'HTML / JS', 'Sem framework'],
        ['none', 'Sem frontend', 'API, worker ou CLI'],
      ],
    },
    {
      key: 'web_ui',
      title: 'UI, CSS e design system',
      description: 'Tecnologias para layout, componentes, responsividade e identidade visual.',
      multiple: true,
      options: [
        ['tailwind', 'Tailwind CSS', 'Utility-first e design system rápido'],
        ['bootstrap', 'Bootstrap', 'Componentes e grid consolidados'],
        ['sass', 'Sass / SCSS', 'CSS com recursos de pré-processador'],
        ['css-modules', 'CSS Modules', 'Escopo local de estilos'],
        ['shadcn', 'shadcn/ui', 'Componentes acessíveis e customizáveis'],
        ['mui', 'Material UI', 'Componentes React baseados em Material Design'],
        ['chakra', 'Chakra UI', 'Componentes React acessíveis'],
        ['framer-motion', 'Framer Motion', 'Animações e microinterações React'],
      ],
    },
    {
      key: 'cms_content',
      title: 'CMS e conteúdo',
      description: 'Gerenciamento editorial para sites, blogs, portais e landing pages.',
      multiple: true,
      options: [
        ['wordpress', 'WordPress', 'CMS tradicional e ecossistema amplo'],
        ['woocommerce', 'WooCommerce', 'Comércio eletrônico no WordPress'],
        ['strapi', 'Strapi', 'Headless CMS open source'],
        ['directus', 'Directus', 'Headless CMS sobre banco SQL'],
        ['sanity', 'Sanity', 'Conteúdo estruturado e edição colaborativa'],
        ['contentful', 'Contentful', 'Headless CMS gerenciado'],
        ['mdx', 'MDX', 'Markdown com componentes'],
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
        ['jamstack', 'Jamstack', 'Site desacoplado, estático e distribuído por CDN'],
        ['serverless', 'Serverless', 'Funções e serviços gerenciados sob demanda'],
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
        ['supabase', 'Supabase', 'PostgreSQL, auth, storage e realtime gerenciados'],
        ['firebase', 'Firebase', 'Backend gerenciado para aplicações web/mobile'],
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
        ['email', 'E-mail transacional', 'Confirmações, alertas e automações'],
        ['whatsapp', 'WhatsApp', 'Mensagens, atendimento e notificações'],
      ],
    },
    {
      key: 'marketing_analytics',
      title: 'Marketing, SEO e analytics',
      description: 'Medição, aquisição, SEO e otimização de conversão.',
      multiple: true,
      options: [
        ['seo', 'SEO técnico', 'Metadados, sitemap, schema e performance'],
        ['ga4', 'Google Analytics 4', 'Métricas de audiência e conversão'],
        ['gtm', 'Google Tag Manager', 'Gestão de tags e eventos'],
        ['search-console', 'Search Console', 'Indexação e desempenho orgânico'],
        ['meta-pixel', 'Meta Pixel', 'Conversões e campanhas Meta'],
        ['plausible', 'Plausible', 'Analytics simples e focado em privacidade'],
        ['hotjar', 'Hotjar', 'Mapas de calor e comportamento'],
      ],
    },
    {
      key: 'commerce_payments',
      title: 'Pagamentos e comércio',
      description: 'Checkout, cobrança, PIX e plataformas de venda.',
      multiple: true,
      options: [
        ['stripe', 'Stripe', 'Pagamentos e assinaturas'],
        ['mercado-pago', 'Mercado Pago', 'PIX, cartão e checkout'],
        ['pix', 'PIX', 'Cobrança e pagamento instantâneo'],
        ['paypal', 'PayPal', 'Pagamentos internacionais'],
        ['shopify', 'Shopify', 'Plataforma de e-commerce gerenciada'],
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
        ['csp', 'CSP', 'Política de conteúdo contra XSS e injeções'],
        ['captcha', 'CAPTCHA / Turnstile', 'Proteção de formulários contra abuso'],
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
        ['visual', 'Visual regression', 'Proteção contra regressões de layout'],
        ['accessibility', 'Acessibilidade', 'Validação automática de WCAG'],
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
        ['lighthouse', 'Lighthouse', 'Performance, SEO e boas práticas web'],
        ['wcag', 'WCAG', 'Acessibilidade como requisito de qualidade'],
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
        ['netlify', 'Netlify', 'Sites estáticos, funções e deploy contínuo'],
        ['cloudflare-pages', 'Cloudflare Pages', 'Sites estáticos e edge global'],
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
        ['content-guide', 'Guia de conteúdo', 'Tom, páginas, SEO e publicação'],
        ['runbook', 'Runbook', 'Operação e incidentes'],
      ],
    },
  ];

  const presets = {
    'saas-balanced': {
      project_type: ['saas'], languages: ['python', 'typescript'], backend: ['fastapi'], frontend: ['react'],
      web_ui: ['tailwind'], cms_content: [], architecture: ['clean'],
      patterns: ['repository', 'service-layer', 'adapter', 'dependency-injection'],
      databases: ['postgresql', 'redis'], interfaces: ['rest', 'openapi', 'webhooks'],
      marketing_analytics: [], commerce_payments: [],
      security: ['oauth2', 'rbac', 'multi-tenant', 'audit-log', 'rate-limit', 'secret-vault'],
      tests: ['unit', 'integration', 'e2e', 'coverage'], quality: ['lint', 'format', 'type-check', 'pre-commit', 'sast'],
      infrastructure: ['docker', 'compose', 'github-actions', 'render'], documentation: ['readme', 'agents', 'adr', 'architecture', 'api-docs'],
    },
    'api-fast': {
      project_type: ['api'], languages: ['python'], backend: ['fastapi'], frontend: ['none'], web_ui: [], cms_content: [], architecture: ['hexagonal'],
      patterns: ['repository', 'service-layer', 'adapter', 'dependency-injection'], databases: ['postgresql', 'redis'],
      interfaces: ['rest', 'openapi', 'webhooks'], marketing_analytics: [], commerce_payments: [],
      security: ['jwt', 'rbac', 'audit-log', 'rate-limit', 'secret-vault'],
      tests: ['unit', 'integration', 'contract', 'coverage'], quality: ['lint', 'format', 'type-check', 'pre-commit'],
      infrastructure: ['docker', 'compose', 'github-actions', 'render'], documentation: ['readme', 'agents', 'api-docs', 'runbook'],
    },
    'lean-mvp': {
      project_type: ['saas'], languages: ['typescript'], backend: ['nestjs'], frontend: ['react'], web_ui: ['tailwind'], cms_content: [], architecture: ['modular-monolith'],
      patterns: ['service-layer', 'repository', 'dependency-injection'], databases: ['postgresql'], interfaces: ['rest', 'openapi'],
      marketing_analytics: [], commerce_payments: [], security: ['jwt', 'rbac', 'rate-limit'], tests: ['unit', 'integration'], quality: ['lint', 'format', 'type-check'],
      infrastructure: ['docker', 'github-actions'], documentation: ['readme', 'agents'],
    },
    enterprise: {
      project_type: ['microservices'], languages: ['java', 'typescript'], backend: ['spring'], frontend: ['react'], web_ui: ['tailwind'], cms_content: [], architecture: ['ddd'],
      patterns: ['repository', 'service-layer', 'factory', 'strategy', 'adapter', 'observer', 'cqrs', 'unit-of-work', 'dependency-injection'],
      databases: ['postgresql', 'redis', 's3'], interfaces: ['rest', 'grpc', 'webhooks', 'openapi'], marketing_analytics: [], commerce_payments: [],
      security: ['oauth2', 'rbac', 'multi-tenant', 'audit-log', 'rate-limit', 'secret-vault'],
      tests: ['unit', 'integration', 'e2e', 'contract', 'coverage'], quality: ['lint', 'format', 'type-check', 'pre-commit', 'sast', 'dependency-scan'],
      infrastructure: ['docker', 'compose', 'github-actions', 'kubernetes', 'terraform'], documentation: ['readme', 'agents', 'adr', 'architecture', 'api-docs', 'runbook'],
    },
  };

  const selected = Object.create(null);
  const groupByKey = new Map(groups.map(group => [group.key, group]));
  const optionLabels = new Map(groups.map(group => [
    group.key,
    new Map(group.options.map(([id, label]) => [id, label])),
  ]));

  let slugEdited = false;
  let summaryFrame = 0;
  let dragStrip = null;
  let dragStartX = 0;
  let dragStartScroll = 0;
  let dragMoved = false;

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

  const asArray = value => Array.isArray(value) ? value : [];
  const optionLabel = (groupKey, optionId) => optionLabels.get(groupKey)?.get(optionId) || optionId;

  function recordDiagnostic(name, startedAt, detail = {}) {
    const durationMs = Math.round((performance.now() - startedAt) * 10) / 10;
    const entry = {scope:'new-project', name, durationMs, at:Date.now(), ...detail};
    window.__devpilotFrontendDiagnostics = Array.isArray(window.__devpilotFrontendDiagnostics)
      ? window.__devpilotFrontendDiagnostics
      : [];
    window.__devpilotFrontendDiagnostics.push(entry);
    if (window.__devpilotFrontendDiagnostics.length > 80) window.__devpilotFrontendDiagnostics.shift();
    if (durationMs >= 50) console.warn('[DevPilot] operação lenta no Novo projeto', entry);
    return durationMs;
  }

  function seedDefaults() {
    groups.forEach(group => { selected[group.key] = new Set(); });
    Object.entries(presets['saas-balanced']).forEach(([key, values]) => {
      selected[key] = new Set(values);
    });
  }

  function renderGroups() {
    const startedAt = performance.now();
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
    recordDiagnostic('render-groups', startedAt, {groups:groups.length, options:groups.reduce((sum, group) => sum + group.options.length, 0)});
  }

  function syncSelectionUI() {
    const startedAt = performance.now();
    host.querySelectorAll('.choice-card[data-group][data-option]').forEach(button => {
      const active = selected[button.dataset.group]?.has(button.dataset.option) || false;
      if (button.classList.contains('selected') !== active) button.classList.toggle('selected', active);
      const pressed = String(active);
      if (button.getAttribute('aria-pressed') !== pressed) button.setAttribute('aria-pressed', pressed);
    });
    recordDiagnostic('sync-selection', startedAt);
    scheduleSummary();
  }

  function selectOption(groupKey, optionId) {
    const group = groupByKey.get(groupKey);
    if (!group) return;
    const set = selected[groupKey] || (selected[groupKey] = new Set());
    if (group.multiple) {
      if (set.has(optionId)) set.delete(optionId); else set.add(optionId);
    } else {
      set.clear();
      set.add(optionId);
    }
    syncSelectionUI();
  }

  function applyPreset(name) {
    const preset = presets[name];
    if (!preset) return;
    groups.forEach(group => { selected[group.key] = new Set(); });
    Object.entries(preset).forEach(([key, values]) => { selected[key] = new Set(values); });
    form.querySelectorAll('[data-builder-preset]').forEach(button => {
      button.classList.toggle('active', button.dataset.builderPreset === name);
    });
    syncSelectionUI();
  }

  function blueprint() {
    const result = {};
    groups.forEach(group => { result[group.key] = [...(selected[group.key] || [])]; });
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
    const deliveryLabels = {
      conventional_commits: 'Conventional Commits',
      protected_main: 'branch principal protegida',
      pull_request_review: 'revisão por Pull Request',
      migrations_reversible: 'migrações reversíveis',
    };
    const delivery = Object.entries(data.delivery || {})
      .filter(([, enabled]) => enabled)
      .map(([key]) => deliveryLabels[key])
      .filter(Boolean);

    return `# AGENTS.md — ${projectName}\n\n## Objetivo\n${description || 'Implementar e evoluir o projeto conforme a especificação técnica selecionada no DevPilot.'}\n\n## Stack selecionada\n- Tipo: ${listFor('project_type', data)}\n- Linguagens: ${listFor('languages', data)}\n- Backend: ${listFor('backend', data)}\n- Frontend: ${listFor('frontend', data)}\n- UI/CSS: ${listFor('web_ui', data)}\n- CMS/conteúdo: ${listFor('cms_content', data)}\n- Arquitetura: ${listFor('architecture', data)}\n- Padrões: ${listFor('patterns', data)}\n- Dados/cache: ${listFor('databases', data)}\n- APIs/integrações: ${listFor('interfaces', data)}\n- Marketing/analytics: ${listFor('marketing_analytics', data)}\n- Pagamentos/comércio: ${listFor('commerce_payments', data)}\n- Segurança: ${listFor('security', data)}\n- Testes: ${listFor('tests', data)}\n- Qualidade: ${listFor('quality', data)}\n- Infra/deploy: ${listFor('infrastructure', data)}\n- Documentação: ${listFor('documentation', data)}${data.custom_technologies.length ? `\n- Tecnologias adicionais: ${data.custom_technologies.join(', ')}` : ''}\n\n## Regras de engenharia\n- Preserve isolamento de módulos, tenants e credenciais conforme a arquitetura escolhida.\n- Não exponha segredos, tokens ou variáveis sensíveis no código, logs ou respostas.\n- Implemente validação de entrada, tratamento explícito de falhas e observabilidade nas operações críticas.\n- Mantenha dependências externas atrás de adapters/interfaces quando aplicável.\n- Toda alteração relevante deve incluir testes compatíveis com a estratégia selecionada.\n- Mudanças destrutivas, deploy, merge, push e dependências exigem aprovação antes da execução.\n- Registre decisões arquiteturais importantes e mantenha a documentação sincronizada com o código.\n${delivery.length ? `- Fluxo de entrega: ${delivery.join(', ')}.\n` : ''}${customRules ? `\n## Regras adicionais do cliente\n${customRules}\n` : ''}`;
  }

  function updateSummary() {
    summaryFrame = 0;
    const startedAt = performance.now();
    const data = blueprint();
    const count = groups.reduce((sum, group) => sum + asArray(data[group.key]).length, 0) + data.custom_technologies.length;
    const countEl = form.querySelector('#project-builder-selection-count');
    if (countEl) countEl.textContent = `${count} escolhas`;

    const summary = form.querySelector('#project-builder-summary');
    if (summary) {
      const rows = [
        ['Projeto', listFor('project_type', data)], ['Linguagens', listFor('languages', data)],
        ['Backend', listFor('backend', data)], ['Frontend', listFor('frontend', data)],
        ['UI/CSS', listFor('web_ui', data)], ['CMS', listFor('cms_content', data)],
        ['Arquitetura', listFor('architecture', data)], ['Dados', listFor('databases', data)],
        ['Infra', listFor('infrastructure', data)],
      ];
      summary.innerHTML = rows.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join('');
    }

    const preview = form.querySelector('#project-builder-agents-preview');
    const details = preview?.closest('details');
    if (preview && details?.open) preview.textContent = buildAgentsMd(data);
    recordDiagnostic('update-summary', startedAt, {preview:Boolean(preview && details?.open)});
  }

  function scheduleSummary() {
    if (summaryFrame) return;
    summaryFrame = window.requestAnimationFrame(updateSummary);
  }

  function syncRepositoryMode() {
    const mode = form.elements.namedItem('repository_mode')?.value || 'connect';
    const create = mode === 'create';
    const existing = form.querySelector('#project-builder-existing-repository');
    if (existing) existing.hidden = create;
    const url = form.elements.namedItem('repository_url');
    if (url) url.required = !create;
    const organization = form.querySelector('#project-builder-organization');
    if (organization) organization.disabled = create;
    const notice = form.querySelector('#project-builder-repository-notice');
    if (notice) {
      notice.textContent = create
        ? (typeof isSuperAdmin === 'function' && isSuperAdmin()
          ? 'O DevPilot tentará criar um repositório privado na organização a-castilho. Se o GitHub estiver indisponível, o projeto será salvo com Git pendente.'
          : 'O DevPilot salvará o projeto e configurará o Git automaticamente quando disponível.')
        : 'Informe um repositório Git já existente para conectar o projeto.';
    }
    form.querySelectorAll('[data-repository-choice]').forEach(card => {
      card.classList.toggle('selected', card.dataset.repositoryChoice === mode);
    });
  }

  function navigateProjects() {
    if (typeof window.devpilotNavigate === 'function') {
      void window.devpilotNavigate('projects', {source:'project-builder-back', immediate:true});
      return;
    }
    if (typeof window.showView === 'function') window.showView('projects');
  }

  function startDrag(strip, event) {
    if (event.pointerType !== 'mouse' || event.button !== 0) return;
    dragStrip = strip;
    dragStartX = event.clientX;
    dragStartScroll = strip.scrollLeft;
    dragMoved = false;
    strip.classList.add('is-dragging');
  }

  function moveDrag(event) {
    if (!dragStrip) return;
    const delta = event.clientX - dragStartX;
    if (Math.abs(delta) > 6) dragMoved = true;
    if (dragMoved) dragStrip.scrollLeft = dragStartScroll - delta;
  }

  function stopDrag() {
    if (!dragStrip) return;
    const strip = dragStrip;
    dragStrip = null;
    strip.classList.remove('is-dragging');
    strip.dataset.dragged = dragMoved ? '1' : '0';
    if (dragMoved) window.setTimeout(() => { strip.dataset.dragged = '0'; }, 120);
  }

  host.addEventListener('click', event => {
    const button = event.target.closest?.('.choice-card[data-group][data-option]');
    if (!button || !host.contains(button)) return;
    const strip = button.closest('.choice-strip');
    if (strip?.dataset.dragged === '1') {
      strip.dataset.dragged = '0';
      return;
    }
    selectOption(button.dataset.group, button.dataset.option);
  });

  host.addEventListener('pointerdown', event => {
    const strip = event.target.closest?.('.choice-strip');
    if (strip && host.contains(strip)) startDrag(strip, event);
  });
  host.addEventListener('pointermove', moveDrag);
  host.addEventListener('pointerup', stopDrag);
  host.addEventListener('pointercancel', stopDrag);
  host.addEventListener('pointerleave', stopDrag);

  form.addEventListener('click', event => {
    const preset = event.target.closest?.('[data-builder-preset]');
    if (preset && form.contains(preset)) applyPreset(preset.dataset.builderPreset);
  });

  document.querySelectorAll('[data-project-builder-close]').forEach(button => {
    button.addEventListener('click', navigateProjects);
  });

  form.addEventListener('change', event => {
    if (event.target?.name === 'repository_mode') syncRepositoryMode();
  });

  form.addEventListener('input', event => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement)) return;
    scheduleSummary();
  });

  const previewDetails = form.querySelector('#project-builder-agents-preview')?.closest('details');
  previewDetails?.addEventListener('toggle', () => {
    if (previewDetails.open) scheduleSummary();
  });

  const nameInput = form.elements.namedItem('name');
  const slugInput = form.elements.namedItem('slug');
  slugInput?.addEventListener('input', () => { slugEdited = true; });
  nameInput?.addEventListener('input', () => {
    if (slugEdited) return;
    const value = slugify(nameInput.value);
    if (slugInput) slugInput.value = value.length === 1 ? `${value}-repo` : value;
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
    const submit = form.querySelector('#project-builder-submit');
    if (submit) { submit.disabled = true; submit.textContent = 'Criando projeto…'; }
    try {
      if (mode === 'create') {
        const project = await api('/projects/provision', {method:'POST', body:JSON.stringify(common)});
        let config = project?.codex_config;
        if (typeof config === 'string') {
          try { config = JSON.parse(config); } catch (_) { config = {}; }
        }
        const repositoryPending = !String(project?.repository_url || '').trim()
          && Boolean(config && typeof config === 'object' && config.repository_pending);
        toast(repositoryPending
          ? `Projeto ${name} criado. GitHub pendente — conecte o repositório depois em Projetos.`
          : `Projeto ${name} criado com repositório privado`);
      } else {
        const repositoryUrl = String(form.elements.namedItem('repository_url')?.value || '').trim();
        if (!repositoryUrl) throw new Error('Informe o repositório Git existente');
        await api('/projects', {method:'POST', body:JSON.stringify({
          ...common,
          repository_url:repositoryUrl,
          organization_id:typeof isSuperAdmin === 'function' && isSuperAdmin()
            ? (form.elements.namedItem('organization_id')?.value || null)
            : null,
          default_branch:String(form.elements.namedItem('default_branch')?.value || 'main').trim() || 'main',
        })});
        toast(`Projeto ${name} conectado com a especificação técnica`);
      }
      form.reset();
      slugEdited = false;
      applyPreset('saas-balanced');
      navigateProjects();
    } catch (error) {
      toast(error?.message || 'Falha ao criar projeto');
    } finally {
      if (submit) { submit.disabled = false; submit.textContent = 'Criar projeto'; }
    }
  });

  form.addEventListener('reset', () => {
    slugEdited = false;
    window.requestAnimationFrame(() => {
      applyPreset('saas-balanced');
      syncRepositoryMode();
    });
  });

  seedDefaults();
  renderGroups();
  syncSelectionUI();
  syncRepositoryMode();

  const bootDurationMs = recordDiagnostic('builder-init', bootStartedAt, {
    options:groups.reduce((sum, group) => sum + group.options.length, 0),
  });
  window.__devpilotProjectBuilderV94 = Object.freeze({version:'v94', bootDurationMs});
  document.dispatchEvent(new CustomEvent('devpilot:project-builder-ready', {
    detail:{version:'v94', bootDurationMs},
  }));
})();
