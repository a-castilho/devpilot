(() => {
  if (!document.querySelector('script[data-mobile-action-buttons="1"]')) {
    const actions = document.createElement('script');
    actions.src = '/assets/mobile-action-buttons.js?v=20260825-1';
    actions.defer = true;
    actions.dataset.mobileActionButtons = '1';
    document.head.appendChild(actions);
  }

  if (window.DevPilotResponses) return;

  const stack = document.createElement('section');
  stack.className = 'dp-response-stack';
  stack.setAttribute('aria-live', 'polite');
  stack.setAttribute('aria-label', 'Avisos do DevPilot');
  document.body.appendChild(stack);
  document.body.classList.add('dp-response-manager-ready');

  const titles = {
    success: 'Concluído',
    error: 'Não foi possível concluir',
    warning: 'Atenção',
    info: 'DevPilot',
    loading: 'Processando',
  };
  const icons = {success: '✓', error: '!', warning: '△', info: 'i', loading: '•'};
  const formMessages = {
    'organization-form': 'Conectando organização e preparando a sincronização…',
    'project-form': 'Salvando o projeto e preparando o repositório…',
    'project-builder-form': 'Criando o projeto com a configuração selecionada…',
    'task-form': 'Registrando a solicitação para o DevPilot…',
    'provider-form': 'Protegendo e salvando a conexão…',
  };

  let sequence = 0;
  let lastLegacy = {signature: '', at: 0};

  function classify(message) {
    const text = String(message || '').toLocaleLowerCase('pt-BR');
    if (/erro|falha|não foi possível|negad|inválid|indisponível|autenticação necessária/.test(text)) return 'error';
    if (/atenção|exclusivo|máximo|pendente|aguarde|necessári/.test(text)) return 'warning';
    if (/conclu|salv|conectad|registrad|aprovad|criad|enfileirad|sync/.test(text)) return 'success';
    return 'info';
  }

  function remove(balloon) {
    if (!balloon || !balloon.isConnected) return;
    balloon.classList.add('dp-response-out');
    window.setTimeout(() => balloon.remove(), 190);
  }

  function clearPendingActions() {
    document.querySelectorAll('[data-response-pending="1"]').forEach(button => {
      button.classList.remove('dp-action-pending');
      button.removeAttribute('aria-busy');
      delete button.dataset.responsePending;
    });
  }

  function markPendingAction(button) {
    if (!(button instanceof HTMLButtonElement)) return;
    button.classList.add('dp-action-pending');
    button.setAttribute('aria-busy', 'true');
    button.dataset.responsePending = '1';
  }

  function clearLoading() {
    stack.querySelectorAll('.dp-response-balloon[data-type="loading"]').forEach(remove);
  }

  function notify(message, options = {}) {
    const text = String(message || '').trim();
    if (!text) return null;
    const type = options.type || classify(text);
    if (type !== 'loading') {
      clearLoading();
      clearPendingActions();
    }

    const id = `dp-response-${++sequence}`;
    const balloon = document.createElement('article');
    balloon.id = id;
    balloon.className = 'dp-response-balloon';
    balloon.dataset.type = type;
    balloon.setAttribute('role', type === 'error' || type === 'warning' ? 'alert' : 'status');
    balloon.innerHTML = `
      <span class="dp-response-icon" aria-hidden="true">${icons[type] || icons.info}</span>
      <div class="dp-response-copy"><strong></strong><p></p></div>
      <button class="dp-response-close" type="button" aria-label="Fechar aviso">×</button>
    `;
    balloon.querySelector('strong').textContent = options.title || titles[type] || titles.info;
    balloon.querySelector('p').textContent = text;
    balloon.querySelector('.dp-response-close').addEventListener('click', () => remove(balloon));
    stack.prepend(balloon);

    while (stack.children.length > 4) remove(stack.lastElementChild);

    document.dispatchEvent(new CustomEvent('devpilot:response', {
      detail: {id, type, message: text},
    }));

    if (!options.persistent) {
      const duration = Number(options.duration || (type === 'error' ? 6500 : type === 'warning' ? 5200 : 4000));
      window.setTimeout(() => remove(balloon), duration);
    }
    return id;
  }

  function loading(message, options = {}) {
    clearLoading();
    const id = notify(message, {...options, type: 'loading', persistent: true});
    window.setTimeout(() => {
      const balloon = document.getElementById(id);
      if (!balloon?.isConnected) return;
      remove(balloon);
      clearPendingActions();
      notify('A operação está demorando mais que o esperado. Você pode continuar aguardando ou tentar novamente.', {type: 'warning'});
    }, Number(options.timeout || 10000));
    return id;
  }

  window.DevPilotResponses = {
    notify,
    clearLoading,
    clearPendingActions,
    loading,
    success: (message, options = {}) => notify(message, {...options, type: 'success'}),
    error: (message, options = {}) => notify(message, {...options, type: 'error'}),
    warning: (message, options = {}) => notify(message, {...options, type: 'warning'}),
    info: (message, options = {}) => notify(message, {...options, type: 'info'}),
  };

  document.addEventListener('submit', event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    const message = formMessages[form.id];
    if (!message) return;
    markPendingAction(event.submitter);
    loading(message, {timeout: 10000});
  }, true);

  const legacyToast = document.querySelector('#toast');
  if (legacyToast) {
    const forwardLegacyToast = () => {
      if (!legacyToast.classList.contains('show')) return;
      const message = String(legacyToast.textContent || '').trim();
      if (!message) return;
      const signature = `${classify(message)}:${message}`;
      const now = Date.now();
      if (lastLegacy.signature === signature && now - lastLegacy.at < 700) return;
      lastLegacy = {signature, at: now};
      notify(message);
    };
    new MutationObserver(forwardLegacyToast).observe(legacyToast, {
      childList: true,
      characterData: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class'],
    });
  }
})();
