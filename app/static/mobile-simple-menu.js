(() => {
  if (window.innerWidth > 900) return;
  const sidebar = document.querySelector('.sidebar');
  const sourceNav = sidebar?.querySelector(':scope > nav');
  if (!sidebar || !sourceNav || document.querySelector('.mobile-simple-nav')) return;

  const ICONS = {
    overview: '⌂',
    projects: '▦',
    tasks: '✓',
    providers: '✦',
    organizations: '◎',
    reports: '≣',
    audit: '⌁',
    linux: '>_',
  };

  const root = document.createElement('div');
  root.className = 'mobile-simple-nav';
  root.innerHTML = `
    <button type="button" class="mobile-simple-item" data-simple-target="overview" aria-label="Início"><span>⌂</span><small>Início</small></button>
    <button type="button" class="mobile-simple-item" data-simple-target="projects" aria-label="Projetos"><span>▦</span><small>Projetos</small></button>
    <button type="button" class="mobile-simple-item" data-simple-target="tasks" aria-label="Desenvolvimento"><span>✓</span><small>Tarefas</small></button>
    <button type="button" class="mobile-simple-item" data-simple-menu-open aria-label="Abrir menu"><span>☰</span><small>Menu</small></button>
  `;

  const backdrop = document.createElement('div');
  backdrop.className = 'mobile-simple-backdrop';
  backdrop.hidden = true;

  const sheet = document.createElement('section');
  sheet.className = 'mobile-simple-sheet';
  sheet.hidden = true;
  sheet.setAttribute('role', 'dialog');
  sheet.setAttribute('aria-modal', 'true');
  sheet.setAttribute('aria-label', 'Menu do DevPilot');
  sheet.innerHTML = `
    <div class="mobile-simple-sheet-head">
      <div><span class="eyebrow">NAVEGAÇÃO</span><h2>Menu</h2></div>
      <button type="button" class="mobile-simple-close" aria-label="Fechar menu">×</button>
    </div>
    <div class="mobile-simple-list"></div>
  `;

  document.body.append(backdrop, sheet);
  sidebar.appendChild(root);

  const list = sheet.querySelector('.mobile-simple-list');
  const openButton = root.querySelector('[data-simple-menu-open]');
  const closeButton = sheet.querySelector('.mobile-simple-close');

  function visibleSourceItems() {
    return [...sourceNav.querySelectorAll(':scope > .nav')].filter(item => {
      if (item.hidden) return false;
      if (item.classList.contains('nav-super-admin-forbidden')) return false;
      return true;
    });
  }

  function itemIcon(item) {
    if (item.dataset.exampleProject) return '◫';
    if (item.dataset.linuxView === '1') return ICONS.linux;
    return ICONS[item.dataset.view] || '•';
  }

  function itemLabel(item) {
    return String(item.textContent || item.getAttribute('aria-label') || 'Abrir').replace(/\s+/g, ' ').trim();
  }

  function closeMenu() {
    sheet.hidden = true;
    backdrop.hidden = true;
    document.body.classList.remove('mobile-simple-open');
    openButton.setAttribute('aria-expanded', 'false');
  }

  function openMenu() {
    renderMenu();
    sheet.hidden = false;
    backdrop.hidden = false;
    document.body.classList.add('mobile-simple-open');
    openButton.setAttribute('aria-expanded', 'true');
  }

  function navigate(item) {
    closeMenu();
    item?.click();
    requestAnimationFrame(syncActive);
  }

  function renderMenu() {
    const items = visibleSourceItems();
    list.replaceChildren();
    items.forEach(item => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `mobile-simple-row${item.classList.contains('active') ? ' active' : ''}`;
      button.innerHTML = `<span class="mobile-simple-icon" aria-hidden="true">${itemIcon(item)}</span><span>${itemLabel(item)}</span><span class="mobile-simple-arrow" aria-hidden="true">›</span>`;
      button.addEventListener('click', () => navigate(item));
      list.appendChild(button);
    });
  }

  function syncActive() {
    root.querySelectorAll('[data-simple-target]').forEach(button => {
      const target = button.dataset.simpleTarget;
      const source = sourceNav.querySelector(`.nav[data-view="${CSS.escape(target)}"]`);
      button.classList.toggle('active', Boolean(source?.classList.contains('active')));
    });
    if (!sheet.hidden) renderMenu();
  }

  root.querySelectorAll('[data-simple-target]').forEach(button => {
    button.addEventListener('click', () => {
      const source = sourceNav.querySelector(`.nav[data-view="${CSS.escape(button.dataset.simpleTarget)}"]`);
      navigate(source);
    });
  });

  openButton.setAttribute('aria-expanded', 'false');
  openButton.addEventListener('click', openMenu);
  closeButton.addEventListener('click', closeMenu);
  backdrop.addEventListener('click', closeMenu);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !sheet.hidden) closeMenu();
  });

  const observer = new MutationObserver(syncActive);
  observer.observe(sourceNav, {subtree: true, childList: true, attributes: true, attributeFilter: ['class', 'hidden']});
  syncActive();
})();