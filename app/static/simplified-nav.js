(() => {
  const sidebar = document.querySelector('.sidebar');
  const nav = sidebar?.querySelector(':scope > nav');
  if (!sidebar || !nav || nav.dataset.simplifiedNavigation === 'true') return;

  nav.dataset.simplifiedNavigation = 'true';

  const originalItems = [...nav.querySelectorAll(':scope > .nav')];
  if (!originalItems.length) return;

  const normalize = value => String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('pt-BR')
    .trim();

  const groups = [
    {
      id: 'home',
      label: 'Início',
      icon: '⌂',
      direct: true,
      matches: item => item.dataset.view === 'overview',
    },
    {
      id: 'projects',
      label: 'Projetos',
      icon: '▦',
      matches: item => ['organizations', 'projects'].includes(item.dataset.view) || item.hasAttribute('data-example-project'),
    },
    {
      id: 'development',
      label: 'Desenvolvimento',
      icon: '✓',
      direct: true,
      matches: item => item.dataset.view === 'tasks',
    },
    {
      id: 'intelligence',
      label: 'Inteligência',
      icon: '✦',
      direct: true,
      matches: item => item.dataset.view === 'providers',
    },
    {
      id: 'governance',
      label: 'Governança',
      icon: '≣',
      matches: item => ['reports', 'audit'].includes(item.dataset.view),
    },
  ];

  const search = document.createElement('label');
  search.className = 'sidebar-search';
  search.innerHTML = '<span class="sidebar-search-icon" aria-hidden="true">⌕</span><input type="search" aria-label="Buscar funcionalidade no DevPilot" placeholder="Buscar no DevPilot...">';
  sidebar.insertBefore(search, nav);

  const searchInput = search.querySelector('input');
  const emptyState = document.createElement('div');
  emptyState.className = 'sidebar-search-empty';
  emptyState.hidden = true;
  emptyState.textContent = 'Nenhuma funcionalidade encontrada.';
  nav.insertAdjacentElement('afterend', emptyState);

  const groupElements = [];

  groups.forEach(config => {
    const items = originalItems.filter(config.matches);
    if (!items.length) return;

    const group = document.createElement('div');
    group.className = 'nav-group';
    group.dataset.group = config.id;
    group.dataset.direct = config.direct ? 'true' : 'false';

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'nav-group-toggle';
    toggle.setAttribute('aria-expanded', 'false');
    toggle.innerHTML = `<span class="nav-group-icon" aria-hidden="true">${config.icon}</span><span class="nav-group-label">${config.label}</span><span class="nav-group-caret" aria-hidden="true">⌄</span>`;

    const itemContainer = document.createElement('div');
    itemContainer.className = 'nav-group-items';
    itemContainer.hidden = !config.direct;

    items.forEach(item => itemContainer.appendChild(item));
    group.append(toggle, itemContainer);
    nav.appendChild(group);

    const entry = { config, group, toggle, itemContainer, items };
    groupElements.push(entry);

    toggle.addEventListener('click', () => {
      if (config.direct) {
        const item = items.find(candidate => !candidate.hidden) || items[0];
        item?.click();
        return;
      }

      const willOpen = !group.classList.contains('open');
      setOpenGroup(willOpen ? entry : null);
    });
  });

  function setOpenGroup(target) {
    if (window.matchMedia('(max-width: 900px)').matches) return;

    groupElements.forEach(entry => {
      const open = target === entry && !entry.config.direct;
      entry.group.classList.toggle('open', open);
      entry.toggle.setAttribute('aria-expanded', String(open));
      entry.itemContainer.hidden = entry.config.direct || !open;
      const caret = entry.toggle.querySelector('.nav-group-caret');
      if (caret && !entry.config.direct) caret.textContent = open ? '⌃' : '⌄';
    });
  }

  function syncActiveGroup({ open = true } = {}) {
    const activeItem = originalItems.find(item => item.classList.contains('active'));
    const activeEntry = activeItem
      ? groupElements.find(entry => entry.items.includes(activeItem))
      : null;

    groupElements.forEach(entry => entry.group.classList.toggle('active', entry === activeEntry));

    if (open && activeEntry && !activeEntry.config.direct && !searchInput.value.trim()) {
      setOpenGroup(activeEntry);
    } else if (open && activeEntry?.config.direct && !searchInput.value.trim()) {
      setOpenGroup(null);
    }
  }

  function syncResponsiveMode() {
    const mobile = window.matchMedia('(max-width: 900px)').matches;

    if (mobile) {
      groupElements.forEach(entry => {
        entry.itemContainer.hidden = false;
      });
      return;
    }

    syncActiveGroup();
  }

  function matchingItems(query) {
    const normalizedQuery = normalize(query);
    if (!normalizedQuery) return [];

    return originalItems.filter(item => {
      if (item.hidden) return false;
      return normalize(item.textContent).includes(normalizedQuery);
    });
  }

  function syncSearch() {
    const query = searchInput.value;
    const matches = matchingItems(query);

    originalItems.forEach(item => item.classList.toggle('nav-search-match', matches.includes(item)));
    emptyState.hidden = !query.trim() || matches.length > 0;

    if (!query.trim()) {
      syncActiveGroup();
      return matches;
    }

    const firstMatch = matches[0];
    const firstGroup = firstMatch
      ? groupElements.find(entry => entry.items.includes(firstMatch))
      : null;

    if (firstGroup && !firstGroup.config.direct) setOpenGroup(firstGroup);
    if (firstGroup?.config.direct) setOpenGroup(null);

    return matches;
  }

  searchInput.addEventListener('input', syncSearch);
  searchInput.addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      const firstMatch = syncSearch()[0];
      if (firstMatch) {
        event.preventDefault();
        firstMatch.click();
        searchInput.value = '';
        syncSearch();
      }
    }

    if (event.key === 'Escape') {
      searchInput.value = '';
      syncSearch();
      searchInput.blur();
    }
  });

  originalItems.forEach(item => {
    item.addEventListener('click', () => {
      searchInput.value = '';
      emptyState.hidden = true;
      originalItems.forEach(candidate => candidate.classList.remove('nav-search-match'));
      queueMicrotask(() => syncActiveGroup());
    });
  });

  const activeObserver = new MutationObserver(() => syncActiveGroup({ open: !searchInput.value.trim() }));
  originalItems.forEach(item => activeObserver.observe(item, { attributes: true, attributeFilter: ['class', 'hidden'] }));

  const media = window.matchMedia('(max-width: 900px)');
  media.addEventListener?.('change', syncResponsiveMode);

  syncResponsiveMode();
})();
