(() => {
  const form = document.querySelector('#project-builder-form');
  if (!form) return;

  const descriptionInput = form.elements.namedItem('description');
  if (!(descriptionInput instanceof HTMLTextAreaElement)) return;

  const profileCopy = form.querySelector('.builder-presets')?.closest('.builder-card')?.querySelector('p');
  const PROFILE_LABELS = {
    'saas-balanced': 'SaaS equilibrado',
    'api-fast': 'API rápida',
    'lean-mvp': 'MVP enxuto',
    enterprise: 'Enterprise',
  };

  const PROFILE_SIGNALS = {
    enterprise: [
      ['enterprise', 6], ['corporativo', 5], ['microserv', 6], ['kubernetes', 6], ['grpc', 5],
      ['alta escala', 4], ['high scale', 4], ['b2b', 3], ['event driven', 3], ['event-driven', 3],
    ],
    'api-fast': [
      ['api', 5], ['backend', 4], ['endpoint', 4], ['webhook', 4], ['integracao', 3],
      ['servico http', 4], ['rest', 4], ['openapi', 3], ['servico de dados', 3],
    ],
    'lean-mvp': [
      ['site pessoal', 8], ['portfolio', 8], ['landing page', 8], ['site institucional', 7],
      ['blog', 6], ['vitrine', 6], ['pagina pessoal', 7], ['site simples', 7], ['mvp', 5],
      ['prototipo', 5], ['curriculo online', 7],
    ],
    'saas-balanced': [
      ['saas', 6], ['plataforma', 4], ['sistema', 3], ['painel', 3], ['dashboard', 3],
      ['assinatura', 3], ['multiusuario', 5], ['multi-tenant', 5], ['multitenant', 5],
      ['crm', 4], ['erp', 4], ['marketplace', 4], ['ecommerce', 4], ['e-commerce', 4], ['app web', 4],
    ],
  };

  let applyingAutomaticProfile = false;
  let userCustomizedBlueprint = false;
  let descriptionTimer = null;

  const normalize = value => String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();

  const containsAny = (text, terms) => terms.some(term => text.includes(term));

  function bestProfile(text) {
    const scores = Object.fromEntries(Object.keys(PROFILE_SIGNALS).map(key => [key, 0]));
    Object.entries(PROFILE_SIGNALS).forEach(([profile, signals]) => {
      signals.forEach(([signal, weight]) => {
        if (text.includes(signal)) scores[profile] += weight;
      });
    });
    const ranked = Object.entries(scores).sort((a, b) => b[1] - a[1]);
    return ranked[0]?.[1] > 0 ? ranked[0][0] : 'saas-balanced';
  }

  function suggestionFor(rawDescription) {
    const text = normalize(rawDescription);
    const suggestion = {profile: bestProfile(text), groups: {}, delivery: {}};

    if (containsAny(text, ['site pessoal', 'portfolio', 'landing page', 'site institucional', 'pagina pessoal', 'curriculo online', 'blog', 'vitrine'])) {
      suggestion.profile = 'lean-mvp';
      suggestion.groups = {
        project_type: ['pwa'],
        languages: ['javascript'],
        backend: ['none'],
        frontend: ['vanilla'],
        architecture: ['mvc'],
        patterns: [],
        databases: [],
        interfaces: [],
        security: [],
        tests: ['unit'],
        quality: ['lint', 'format'],
        infrastructure: ['github-actions', 'vercel'],
        documentation: ['readme', 'agents'],
      };
      suggestion.delivery = {migrations_reversible: false};
      return suggestion;
    }

    if (containsAny(text, ['linha de comando', 'command line', 'cli', 'terminal app', 'ferramenta de terminal'])) {
      suggestion.profile = 'lean-mvp';
      suggestion.groups = {
        project_type: ['cli'], languages: ['python'], backend: ['none'], frontend: ['none'],
        architecture: ['clean'], patterns: ['service-layer', 'adapter'], databases: ['sqlite'], interfaces: [],
        security: [], tests: ['unit', 'integration'], quality: ['lint', 'format', 'type-check'],
        infrastructure: ['github-actions'], documentation: ['readme', 'agents'],
      };
      suggestion.delivery = {migrations_reversible: false};
      return suggestion;
    }

    if (containsAny(text, ['automacao', 'robo', 'bot ', 'worker', 'fila', 'crawler', 'scraper', 'raspagem', 'rotina automatica', 'n8n'])) {
      suggestion.profile = 'api-fast';
      suggestion.groups = {
        project_type: ['automation'], languages: ['python'], backend: ['none'], frontend: ['none'],
        architecture: ['hexagonal'], patterns: ['service-layer', 'adapter', 'dependency-injection'],
        databases: ['sqlite', 'redis'], interfaces: ['webhooks'], security: ['secret-vault'],
        tests: ['unit', 'integration'], quality: ['lint', 'format', 'type-check'],
        infrastructure: ['docker', 'compose', 'github-actions', 'render'], documentation: ['readme', 'agents', 'runbook'],
      };
      return suggestion;
    }

    if (containsAny(text, ['inteligencia artificial', 'machine learning', 'data science', 'pipeline de dados', 'data pipeline', 'etl', 'modelo de ia', 'rag', 'llm', 'chatbot'])) {
      suggestion.profile = 'api-fast';
      suggestion.groups = {
        project_type: ['data-ai'], languages: ['python'], backend: ['fastapi'], frontend: ['none'],
        architecture: ['hexagonal'], patterns: ['repository', 'service-layer', 'adapter', 'dependency-injection'],
        databases: ['postgresql', 'redis'], interfaces: ['rest', 'openapi'], security: ['jwt', 'rate-limit', 'secret-vault'],
        tests: ['unit', 'integration', 'contract'], quality: ['lint', 'format', 'type-check'],
        infrastructure: ['docker', 'compose', 'github-actions', 'render'], documentation: ['readme', 'agents', 'api-docs', 'runbook'],
      };
      return suggestion;
    }

    if (containsAny(text, ['app mobile', 'aplicativo mobile', 'pwa', 'mobile web', 'instalavel no celular'])) {
      suggestion.profile = 'lean-mvp';
      suggestion.groups = {
        project_type: ['pwa'], languages: ['typescript'], backend: ['nestjs'], frontend: ['react'],
        architecture: ['modular-monolith'], patterns: ['service-layer', 'repository', 'dependency-injection'],
        databases: ['postgresql'], interfaces: ['rest', 'openapi'], security: ['jwt', 'rbac', 'rate-limit'],
        tests: ['unit', 'integration', 'e2e'], quality: ['lint', 'format', 'type-check'],
        infrastructure: ['docker', 'github-actions', 'vercel'], documentation: ['readme', 'agents'],
      };
      return suggestion;
    }

    if (containsAny(text, ['ecommerce', 'e-commerce', 'loja virtual', 'marketplace', 'carrinho', 'checkout'])) {
      suggestion.profile = 'saas-balanced';
      suggestion.groups = {
        frontend: ['nextjs'], interfaces: ['rest', 'openapi', 'webhooks'],
        security: ['oauth2', 'rbac', 'audit-log', 'rate-limit', 'secret-vault'],
        infrastructure: ['docker', 'compose', 'github-actions', 'vercel', 'render'],
      };
      return suggestion;
    }

    if (containsAny(text, ['painel administrativo', 'backoffice', 'dashboard administrativo', 'admin interno'])) {
      suggestion.profile = 'saas-balanced';
      suggestion.groups = {
        project_type: ['admin'], languages: ['typescript'], backend: ['nestjs'], frontend: ['react'],
        architecture: ['modular-monolith'], security: ['oauth2', 'rbac', 'audit-log', 'rate-limit', 'secret-vault'],
      };
      return suggestion;
    }

    return suggestion;
  }

  function groupElement(groupKey) {
    return [...form.querySelectorAll('[data-builder-group]')]
      .find(section => section.dataset.builderGroup === groupKey) || null;
  }

  function setGroup(groupKey, optionIds) {
    const section = groupElement(groupKey);
    if (!section) return;
    const wanted = new Set(optionIds || []);
    const cards = [...section.querySelectorAll('.choice-card[data-option]')];

    cards.forEach(card => {
      const shouldBeSelected = wanted.has(card.dataset.option);
      if (card.classList.contains('selected') !== shouldBeSelected) card.click();
    });
  }

  function setDelivery(delivery) {
    Object.entries(delivery || {}).forEach(([name, enabled]) => {
      const input = form.elements.namedItem(name);
      if (!(input instanceof HTMLInputElement) || input.type !== 'checkbox') return;
      if (input.checked === Boolean(enabled)) return;
      input.checked = Boolean(enabled);
      input.dispatchEvent(new Event('input', {bubbles: true}));
    });
  }

  function applySuggestion(rawDescription) {
    const text = normalize(rawDescription);
    if (!text) return;

    const suggestion = suggestionFor(text);
    const presetButton = form.querySelector(`[data-builder-preset="${suggestion.profile}"]`);
    if (!presetButton) return;

    applyingAutomaticProfile = true;
    try {
      presetButton.click();
      Object.entries(suggestion.groups).forEach(([groupKey, optionIds]) => setGroup(groupKey, optionIds));
      setDelivery(suggestion.delivery);
      if (profileCopy) {
        profileCopy.textContent = `Perfil sugerido automaticamente: ${PROFILE_LABELS[suggestion.profile]}. Ajuste abaixo somente o que precisar.`;
      }
      form.dataset.descriptionProfile = suggestion.profile;
    } finally {
      applyingAutomaticProfile = false;
    }
  }

  function scheduleDescriptionProfile() {
    window.clearTimeout(descriptionTimer);
    if (userCustomizedBlueprint) return;
    const text = descriptionInput.value.trim();
    if (text.length < 3) return;
    descriptionTimer = window.setTimeout(() => applySuggestion(text), 320);
  }

  form.addEventListener('click', event => {
    if (applyingAutomaticProfile) return;
    if (event.target.closest?.('[data-builder-preset], .choice-card')) {
      userCustomizedBlueprint = true;
      if (profileCopy) profileCopy.textContent = 'Perfil ajustado por você. As escolhas manuais serão preservadas.';
    }
  });

  form.querySelectorAll('.builder-delivery input[type="checkbox"]').forEach(input => {
    input.addEventListener('change', () => {
      if (!applyingAutomaticProfile) userCustomizedBlueprint = true;
    });
  });

  descriptionInput.addEventListener('input', scheduleDescriptionProfile);
  descriptionInput.addEventListener('blur', () => {
    if (userCustomizedBlueprint || descriptionInput.value.trim().length < 3) return;
    window.clearTimeout(descriptionTimer);
    applySuggestion(descriptionInput.value);
  });

  form.addEventListener('reset', () => {
    window.clearTimeout(descriptionTimer);
    userCustomizedBlueprint = false;
    form.dataset.descriptionProfile = '';
    if (profileCopy) profileCopy.textContent = 'Descreva o projeto acima. O DevPilot selecionará o perfil e preencherá as opções automaticamente.';
  });

  if (profileCopy) {
    profileCopy.textContent = 'Descreva o projeto acima. O DevPilot selecionará o perfil e preencherá as opções automaticamente.';
  }
  if (descriptionInput.value.trim().length >= 3) scheduleDescriptionProfile();
})();
