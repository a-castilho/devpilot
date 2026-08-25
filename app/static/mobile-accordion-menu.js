(() => {
  const sidebar = document.querySelector('.sidebar');
  const nav = sidebar?.querySelector(':scope > nav');
  if (!sidebar || !nav || document.querySelector('.mobile-accordion-sheet')) return;

  const STORAGE_KEY = 'devpilot-mobile-favorites-v1';
  const MAX_FAVORITES = 4;
  const DEFAULT_FAVORITES = ['view:overview', 'view:tasks', 'view:projects', 'view:providers'];

  const normalize = value => String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('pt-BR')
    .trim();

  const groupMeta = {
    principal: {label: 'Principal', icon: '⌂', order: 10},
    projects: {label: 'Projetos', icon: '▦', order: 20},
    intelligence: {label: 'Inteligência', icon: '✦', order: 30},
    governance: {label: 'Governança', icon: '≣', order: 40},
    'super-admin': {label: 'Super Admin', icon: '◆', order: 50},
    other: {label: 'Outros', icon: '•', order: 90},
  };

  const iconByView = {
    overview: '⌂',
    organizations: '◎',
    projects: '▦',
    tasks: '✓',
    providers: '✦',
    reports: '≣',
    audit: '⌁',
    'token-usage': '◫',
    'cloud-admin': '☁',
    'investia-admin': '◇',
    linux: '>_',
  };

  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'mobile-accordion-trigger';
  trigger.setAttribute('aria-label', 'Abrir menu');
  trigger.setAttribute('aria-expanded', 'false');
  trigger.setAttribute('aria-controls', 'mobile-accordion-sheet');
  trigger.textContent = '☰';

  const quickbar = document.createElement('div');
  quickbar.className = 'mobile-quickbar';
  quickbar.setAttribute('aria-label', 'Acesso rápido');

  sidebar.append(trigger, quickbar);

  const backdrop = document.createElement('div');
  backdrop.className = 'mobile-accordion-backdrop';
  backdrop.setAttribute('aria-hidden', 'true');

  const sheet = document.createElement('section');
  sheet.id = 'mobile-accordion-sheet';
  sheet.className = 'mobile-accordion-sheet';
  sheet.setAttribute('role', 'dialog');
  sheet.setAttribute('aria-modal', 'true');
  sheet.setAttribute('aria-label', 'Menu do DevPilot');
  sheet.innerHTML = `
    <div class="mobile-accordion-handle" aria-hidden="true"></div>
    <div class="mobile-accordion-head">
      <div>
        <span class="eyebrow">NAVEGAÇÃO PERSONALIZÁVEL</span>
        <h2>Escolha o que quer ver</h2>
      </div>
      <button class="mobile-accordion-close" type="button" aria-label="Fechar menu">×</button>
    </div>
    <label class="mobile-accordion-search">
      <input type="search" aria-label="Buscar no menu" placeholder="Buscar funcionalidade..." autocomplete="off">
    </label>
    <div class="mobile-accordion-groups"></div>
  `;

  document.body.append(backdrop, sheet);

  const closeButton = sheet.querySelector('.mobile-accordion-close');
  const searchInput = sheet.querySelector('.mobile-accordion-search input');
  const groupsRoot = sheet.querySelector('.mobile-accordion-groups');

  let favorites = loadFavorites();
  let rebuildQueued = false;

  function notify(message) {
    if (window.DevPilotResponses?.info) window.DevPilotResponses.info(message);
    else if (typeof window.toast === 'function') window.toast(message);
  }

  function itemKey(item) {
    if (item.dataset.view) return `view:${item.dataset.view}`;
    if (item.dataset.exampleProject) return `example:${item.dataset.exampleProject}`;
    if (item.dataset.linuxView === '1') return 'view:linux';
    return `item:${normalize(item.textContent).replace(/\s+/g, '-')}`;
  }

  function itemLabel(item) {
    return String(item.textContent || item.getAttribute('aria-label') || 'Abrir').replace(/\s+/g, ' ').trim();
  }

  function itemIcon(item) {
    if (item.dataset.exampleProject) return '◫';
    if (item.dataset.linuxView === '1') return '>_';
    return iconByView[item.dataset.view] || '•';
  }

  function itemGroup(item) {
    const assigned = item.dataset.navGroup;
    if (assigned && groupMeta[assigned]) return assigned;

    const view = String(item.dataset.view || '');
    if (view === 'overview' || view === 'tasks') return 'principal';
    if (view === 'projects' || item.dataset.exampleProject) return 'projects';
    if (view === 'providers') return 'intelligence';
    if (view === 'reports' || view === 'audit') return 'governance';
    if (item.dataset.superAdmin === 'true' || item.dataset.linuxView === '1') return 'super-admin';
    return 'other';
  }

  function eligibleItems() {
    return [...nav.querySelectorAll(':scope > .nav')].filter(item => {
      if (item.hidden) return false;
      if (item.classList.contains('nav-super-admin-forbidden')) return false;
      return true;
    });
  }

  function loadFavorites() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (Array.isArray(parsed)) return parsed.filter(Boolean).slice(0, MAX_FAVORITES);
    } catch (_) {
      // Fall back to the safe defaults below.
    }
    return [...DEFAULT_FAVORITES];
  }

  function saveFavorites() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites.slice(0, MAX_FAVORITES)));
  }

  function activeItem() {
    return eligibleItems().find(item => item.classList.contains('active')) || null;
  }

  function openMenu() {
    sheet.classList.add('open');
    backdrop.classList.add('open');
    document.body.classList.add('mobile-accordion-open');
    trigger.setAttribute('aria-expanded', 'true');
    trigger.textContent = '×';
    rebuild();
    requestAnimationFrame(() => searchInput.focus({preventScroll: true}));
  }

  function closeMenu({restoreFocus = true} = {}) {
    sheet.classList.remove('open');
    backdrop.classList.remove('open');
    document.body.classList.remove('mobile-accordion-open');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.textContent = '☰';
    searchInput.value = '';
    applySearch('');
    if (restoreFocus) trigger.focus({preventScroll: true});
  }

  function navigateTo(item) {
    if (!item) return;
    closeMenu({restoreFocus: false});
    item.click();
    requestAnimationFrame(rebuild);
  }

  function toggleFavorite(key) {
    if (favorites.includes(key)) {
      favorites = favorites.filter(value => value !== key);
    } else {
      if (favorites.length >= MAX_FAVORITES) {
        notify(`Escolha no máximo ${MAX_FAVORITES} atalhos importantes.`);
        return;
      }
      favorites.push(key);
    }
    saveFavorites();
    rebuild();
  }

  function renderQuickbar(items) {
    const byKey = new Map(items.map(item => [itemKey(item), item]));
    favorites = favorites.filter(key => byKey.has(key));

    if (!favorites.length) {
      const defaultsAvailable = DEFAULT_FAVORITES.filter(key => byKey.has(key));
      favorites = defaultsAvailable.slice(0, MAX_FAVORITES);
      saveFavorites();
    }

    quickbar.replaceChildren();
    favorites.forEach(key => {
      const item = byKey.get(key);
      if (!item) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `mobile-quick-item${item.classList.contains('active') ? ' active' : ''}`;
      button.setAttribute('aria-label', itemLabel(item));
      button.setAttribute('title', itemLabel(item));
      button.innerHTML = `<span class="mobile-menu-icon" aria-hidden="true">${itemIcon(item)}</span>`;
      button.addEventListener('click', () => navigateTo(item));
      quickbar.appendChild(button);
    });
  }

  function renderGroups(items) {
    const active = activeItem();
    const activeGroup = active ? itemGroup(active) : 'principal';
    const grouped = new Map();

    items.forEach(item => {
      const groupId = itemGroup(item);
      if (!grouped.has(groupId)) grouped.set(groupId, []);
      grouped.get(groupId).push(item);
    });

    const groups = [...grouped.entries()].sort((a, b) => {
      const aOrder = groupMeta[a[0]]?.order ?? 999;
      const bOrder = groupMeta[b[0]]?.order ?? 999;
      return aOrder - bOrder;
    });

    groupsRoot.replaceChildren();

    groups.forEach(([groupId, members]) => {
      const meta = groupMeta[groupId] || groupMeta.other;
      const details = document.createElement('details');
      details.className = 'mobile-accordion-group';
      details.dataset.mobileMenuGroup = groupId;
      details.open = groupId === activeGroup;

      const summary = document.createElement('summary');
      summary.innerHTML = `<span class="mobile-accordion-group-icon" aria-hidden="true">${meta.icon}</span><span>${meta.label}</span>`;
      details.appendChild(summary);

      const rows = document.createElement('div');
      rows.className = 'mobile-accordion-group-items';

      members.forEach(item => {
        const key = itemKey(item);
        const label = itemLabel(item);
        const row = document.createElement('div');
        row.className = 'mobile-accordion-row';
        row.dataset.mobileMenuSearch = normalize(label);

        const go = document.createElement('button');
        go.type = 'button';
        go.className = `mobile-accordion-nav-item${item.classList.contains('active') ? ' active' : ''}`;
        go.innerHTML = `<span class="mobile-menu-icon" aria-hidden="true">${itemIcon(item)}</span><span>${label}</span>`;
        go.addEventListener('click', () => navigateTo(item));

        const pin = document.createElement('button');
        pin.type = 'button';
        pin.className = `mobile-accordion-pin${favorites.includes(key) ? ' pinned' : ''}`;
        pin.setAttribute('aria-label', favorites.includes(key) ? `Remover ${label} do acesso rápido` : `Fixar ${label} no acesso rápido`);
        pin.setAttribute('title', favorites.includes(key) ? 'Remover do acesso rápido' : 'Fixar no acesso rápido');
        pin.textContent = favorites.includes(key) ? '★' : '☆';
        pin.addEventListener('click', event => {
          event.stopPropagation();
          toggleFavorite(key);
        });

        row.append(go, pin);
        rows.appendChild(row);
      });

      details.appendChild(rows);
      details.addEventListener('toggle', () => {
        if (!details.open || searchInput.value.trim()) return;
        groupsRoot.querySelectorAll('.mobile-accordion-group[open]').forEach(other => {
          if (other !== details) other.open = false;
        });
      });
      groupsRoot.appendChild(details);
    });
  }

  function applySearch(value) {
    const query = normalize(value);
    let matches = 0;

    groupsRoot.querySelectorAll('.mobile-accordion-group').forEach(group => {
      let groupMatches = 0;
      group.querySelectorAll('.mobile-accordion-row').forEach(row => {
        const visible = !query || String(row.dataset.mobileMenuSearch || '').includes(query);
        row.hidden = !visible;
        if (visible) groupMatches += 1;
      });
      group.hidden = groupMatches === 0;
      if (query && groupMatches) group.open = true;
      matches += groupMatches;
    });

    let empty = groupsRoot.querySelector('.mobile-accordion-empty');
    if (query && matches === 0) {
      if (!empty) {
        empty = document.createElement('div');
        empty.className = 'mobile-accordion-empty';
        empty.textContent = 'Nenhuma funcionalidade encontrada.';
        groupsRoot.appendChild(empty);
      }
    } else {
      empty?.remove();
    }
  }

  function rebuild() {
    const items = eligibleItems();
    renderQuickbar(items);
    renderGroups(items);
    applySearch(searchInput.value);
  }

  function scheduleRebuild() {
    if (rebuildQueued) return;
    rebuildQueued = true;
    queueMicrotask(() => {
      rebuildQueued = false;
      rebuild();
    });
  }

  trigger.addEventListener('click', () => {
    if (sheet.classList.contains('open')) closeMenu();
    else openMenu();
  });
  closeButton.addEventListener('click', () => closeMenu());
  backdrop.addEventListener('click', () => closeMenu());
  searchInput.addEventListener('input', event => applySearch(event.target.value));
  searchInput.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeMenu();
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && sheet.classList.contains('open')) closeMenu();
  });

  let touchStartY = null;
  sheet.addEventListener('touchstart', event => {
    touchStartY = event.touches?.[0]?.clientY ?? null;
  }, {passive: true});
  sheet.addEventListener('touchend', event => {
    if (touchStartY == null) return;
    const endY = event.changedTouches?.[0]?.clientY ?? touchStartY;
    if (endY - touchStartY > 90 && groupsRoot.scrollTop <= 0) closeMenu();
    touchStartY = null;
  }, {passive: true});

  const observer = new MutationObserver(mutations => {
    if (mutations.some(mutation => mutation.type === 'childList' || mutation.type === 'attributes')) scheduleRebuild();
  });
  observer.observe(nav, {
    childList: true,
    subtree: false,
    attributes: true,
    attributeFilter: ['class', 'hidden', 'data-nav-group', 'data-super-admin'],
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > 900 && sheet.classList.contains('open')) closeMenu({restoreFocus: false});
  });

  rebuild();
})();

(() => {
  if (document.querySelector('script[data-project-ships-loader="1"]')) return;
  const script = document.createElement('script');
  script.src = '/assets/project-ships.js?v=20260824-2';
  script.async = false;
  script.dataset.projectShipsLoader = '1';
  document.head.appendChild(script);
})();

(() => {
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

  function clearLoading() {
    stack.querySelectorAll('.dp-response-balloon[data-type="loading"]').forEach(remove);
  }

  function notify(message, options = {}) {
    const text = String(message || '').trim();
    if (!text) return null;
    const type = options.type || classify(text);
    if (type !== 'loading') clearLoading();

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
      notify('A operação está demorando mais que o esperado. Você pode continuar aguardando ou tentar novamente.', {type: 'warning'});
    }, Number(options.timeout || 15000));
    return id;
  }

  window.DevPilotResponses = {
    notify,
    clearLoading,
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
    if (message) loading(message);
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
