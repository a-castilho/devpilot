(() => {
  const sidebar = document.querySelector('.sidebar');
  const nav = sidebar?.querySelector(':scope > nav');
  if (!sidebar || !nav || nav.dataset.simplifiedNavigation === 'true') return;

  nav.dataset.simplifiedNavigation = 'true';

  const normalize = value => String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase('pt-BR')
    .trim();

  const ADMIN_VIEWS = new Set([
    'organizations',
    'token-usage',
    'cloud-admin',
    'investia-admin',
  ]);

  const SUPER_ADMIN_ORDER = new Map([
    ['organizations', 10],
    ['token-usage', 20],
    ['cloud-admin', 30],
    ['investia-admin', 40],
    ['linux', 50],
  ]);

  const groupConfigs = [
    {
      id: 'projects',
      label: 'Projetos',
      icon: '▦',
      matches: item => item.dataset.view === 'projects' || item.hasAttribute('data-example-project'),
    },
    {
      id: 'governance',
      label: 'Governança',
      icon: '≣',
      matches: item => ['reports', 'audit'].includes(item.dataset.view),
    },
  ];

  const groupState = new Map(groupConfigs.map(config => [config.id, false]));
  groupState.set('super-admin', true);

  let currentRole = '';
  let roleResolved = false;
  let syncing = false;
  let syncQueued = false;

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

  function isSuperAdmin() {
    return roleResolved && currentRole === 'SUPER_ADMIN';
  }

  function isAdminOnlyItem(item) {
    if (!(item instanceof HTMLElement) || !item.classList.contains('nav')) return false;
    if (item.dataset.superAdmin === 'true') return true;
    if (item.dataset.linuxView === '1') return true;
    return ADMIN_VIEWS.has(String(item.dataset.view || ''));
  }

  function adminOrderKey(item) {
    if (item.dataset.linuxView === '1') return 'linux';
    return String(item.dataset.view || '');
  }

  function navItems() {
    return [...nav.querySelectorAll(':scope > .nav')];
  }

  function ensureGroupHeader(config, {superAdmin = false} = {}) {
    const selector = `.nav-group-toggle[data-nav-group-toggle="${config.id}"]`;
    let toggle = nav.querySelector(`:scope > ${selector}`);
    if (toggle) return toggle;

    toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = `nav-group-toggle${superAdmin ? ' super-admin-nav-header' : ''}`;
    toggle.dataset.navGroupToggle = config.id;
    toggle.setAttribute('aria-expanded', String(Boolean(groupState.get(config.id))));
    toggle.innerHTML = `<span class="nav-group-icon" aria-hidden="true">${config.icon}</span><span class="nav-group-label">${config.label}</span><span class="nav-group-caret" aria-hidden="true">⌄</span>`;
    toggle.addEventListener('click', () => {
      groupState.set(config.id, !groupState.get(config.id));
      syncNavigation();
    });
    return toggle;
  }

  function classifyNormalGroups(items) {
    for (const item of items) {
      if (isAdminOnlyItem(item)) continue;
      const group = groupConfigs.find(config => config.matches(item));
      if (group) item.dataset.navGroup = group.id;
      else delete item.dataset.navGroup;
      item.classList.remove('nav-super-admin-item', 'nav-super-admin-forbidden');
    }
  }

  function classifyAdminItems(items) {
    for (const item of items.filter(isAdminOnlyItem)) {
      item.dataset.superAdmin = 'true';
      item.dataset.navGroup = 'super-admin';
      item.classList.add('nav-super-admin-item');
      item.classList.toggle('nav-super-admin-forbidden', !isSuperAdmin());
    }
  }

  function placeNormalHeader(config, items) {
    const members = items.filter(item => item.dataset.navGroup === config.id && !item.classList.contains('nav-super-admin-forbidden'));
    let toggle = nav.querySelector(`:scope > .nav-group-toggle[data-nav-group-toggle="${config.id}"]`);
    if (!members.length) {
      toggle?.remove();
      return;
    }

    toggle = toggle || ensureGroupHeader(config);
    const first = members[0];
    if (first.previousElementSibling !== toggle) nav.insertBefore(toggle, first);
  }

  function placeSuperAdminBlock(items) {
    const config = {id: 'super-admin', label: 'Super Admin', icon: '◆'};
    let toggle = nav.querySelector(':scope > .nav-group-toggle[data-nav-group-toggle="super-admin"]');
    const members = items
      .filter(isAdminOnlyItem)
      .sort((a, b) => {
        const aOrder = SUPER_ADMIN_ORDER.get(adminOrderKey(a)) ?? 999;
        const bOrder = SUPER_ADMIN_ORDER.get(adminOrderKey(b)) ?? 999;
        return aOrder - bOrder;
      });

    if (!isSuperAdmin() || !members.length) {
      toggle?.remove();
      return;
    }

    toggle = toggle || ensureGroupHeader(config, {superAdmin: true});
    const expectedTail = [toggle, ...members];
    const currentTail = [...nav.children].slice(-expectedTail.length);
    const tailMatches = expectedTail.every((node, index) => currentTail[index] === node);
    if (!tailMatches) {
      const fragment = document.createDocumentFragment();
      expectedTail.forEach(node => fragment.appendChild(node));
      nav.appendChild(fragment);
    }
  }

  function applyGroupVisibility(items) {
    const query = normalize(searchInput.value);
    const searching = Boolean(query);
    let visibleMatches = 0;

    for (const item of items) {
      const forbidden = item.classList.contains('nav-super-admin-forbidden') || item.hidden;
      const groupId = item.dataset.navGroup || '';
      const matchesSearch = !searching || normalize(item.textContent).includes(query);
      const searchMatch = !forbidden && searching && matchesSearch;
      const collapsed = !forbidden && (
        searching
          ? !matchesSearch
          : Boolean(groupId && groupState.has(groupId) && !groupState.get(groupId))
      );

      item.classList.toggle('nav-search-match', searchMatch);
      item.classList.toggle('nav-group-collapsed-item', collapsed);
      if (searchMatch) visibleMatches += 1;
    }

    nav.querySelectorAll(':scope > .nav-group-toggle').forEach(toggle => {
      const groupId = toggle.dataset.navGroupToggle;
      const members = items.filter(item => item.dataset.navGroup === groupId && !item.classList.contains('nav-super-admin-forbidden') && !item.hidden);
      const groupHasSearchMatch = members.some(item => normalize(item.textContent).includes(query));
      toggle.classList.toggle('nav-search-hidden', searching && !groupHasSearchMatch);
      toggle.classList.toggle('active', members.some(item => item.classList.contains('active')));
      toggle.classList.toggle('open', Boolean(groupState.get(groupId)) || (searching && groupHasSearchMatch));
      toggle.setAttribute('aria-expanded', String(Boolean(groupState.get(groupId)) || (searching && groupHasSearchMatch)));
      const caret = toggle.querySelector('.nav-group-caret');
      if (caret) caret.textContent = (groupState.get(groupId) || (searching && groupHasSearchMatch)) ? '⌃' : '⌄';
    });

    emptyState.hidden = !searching || visibleMatches > 0;
  }

  function openActiveGroup(items) {
    if (searchInput.value.trim()) return;
    const active = items.find(item => item.classList.contains('active'));
    const groupId = active?.dataset.navGroup;
    if (groupId && groupState.has(groupId)) groupState.set(groupId, true);
  }

  function syncNavigation() {
    if (syncing) return;
    syncing = true;
    try {
      const items = navItems();
      classifyNormalGroups(items);
      classifyAdminItems(items);
      placeSuperAdminBlock(items);

      const refreshedItems = navItems();
      groupConfigs.forEach(config => placeNormalHeader(config, refreshedItems));
      openActiveGroup(refreshedItems);
      applyGroupVisibility(refreshedItems);
    } finally {
      syncing = false;
    }
  }

  function scheduleSync() {
    if (syncQueued) return;
    syncQueued = true;
    queueMicrotask(() => {
      syncQueued = false;
      syncNavigation();
    });
  }

  searchInput.addEventListener('input', syncNavigation);
  searchInput.addEventListener('keydown', event => {
    if (event.key === 'Enter') {
      const firstMatch = navItems().find(item => item.classList.contains('nav-search-match') && !item.classList.contains('nav-super-admin-forbidden'));
      if (firstMatch) {
        event.preventDefault();
        firstMatch.click();
        searchInput.value = '';
        syncNavigation();
      }
    }

    if (event.key === 'Escape') {
      searchInput.value = '';
      syncNavigation();
      searchInput.blur();
    }
  });

  nav.addEventListener('click', event => {
    const item = event.target.closest('.nav');
    if (!item || !nav.contains(item)) return;
    searchInput.value = '';
    emptyState.hidden = true;
    queueMicrotask(syncNavigation);
  });

  const observer = new MutationObserver(mutations => {
    if (syncing) return;
    if (mutations.some(mutation => mutation.type === 'childList' || mutation.type === 'attributes')) scheduleSync();
  });
  observer.observe(nav, {childList: true, subtree: false, attributes: true, attributeFilter: ['class', 'hidden']});

  async function resolveRole() {
    const immediateRole = typeof state !== 'undefined' ? String(state.currentUser?.role || '').toUpperCase() : '';
    if (immediateRole) {
      currentRole = immediateRole;
      roleResolved = true;
      syncNavigation();
      return;
    }

    const token = localStorage.getItem('devpilot-token') || '';
    if (!token) {
      roleResolved = true;
      syncNavigation();
      return;
    }

    try {
      const response = await fetch('/api/auth/me', {
        headers: {Authorization: `Bearer ${token}`},
        cache: 'no-store',
      });
      if (response.ok) {
        const user = await response.json();
        currentRole = String(user?.role || '').toUpperCase();
      }
    } catch (_) {
      currentRole = '';
    } finally {
      roleResolved = true;
      syncNavigation();
    }
  }

  syncNavigation();
  resolveRole();
})();
