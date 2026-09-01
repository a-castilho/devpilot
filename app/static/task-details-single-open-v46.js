(() => {
  'use strict';

  if (window.__devpilotTaskDetailsSingleOpenV46) return;
  window.__devpilotTaskDetailsSingleOpenV46 = true;

  const VIEW_SELECTOR = '#tasks-view';
  const ROW_SELECTOR = '[data-task-details-row], .task-inline-details[data-task-instructions]';
  const BUTTON_SELECTOR = '.tasks-v9-details[data-id], .task-instructions-load[data-id]';

  let activeId = '';
  let reconciling = false;
  let reconcileTimer = 0;
  let observer = null;

  function view() {
    return document.querySelector(VIEW_SELECTOR);
  }

  function rowId(row) {
    return String(row?.dataset?.taskDetailsRow || row?.dataset?.taskInstructions || '');
  }

  function rows() {
    const target = view();
    return target ? [...target.querySelectorAll(ROW_SELECTOR)] : [];
  }

  function buttonsFor(id) {
    const target = view();
    if (!target || !id) return [];
    return [...target.querySelectorAll(BUTTON_SELECTOR)]
      .filter(button => String(button.dataset.id || '') === String(id));
  }

  function rowIsOpen(row) {
    if (!row || row.hidden) return false;
    if (row.getAttribute('aria-hidden') === 'true') return false;
    return row.style.getPropertyValue('display') !== 'none';
  }

  function syncButton(button, open) {
    if (!button) return;
    button.setAttribute('aria-expanded', open ? 'true' : 'false');
    button.classList.toggle('dp-v13-open', open);
    button.classList.toggle('dp-details-open', open);

    if (button.classList.contains('tasks-v9-details')) {
      const expected = open ? 'Ocultar' : 'Detalhes';
      if (button.textContent !== expected) button.textContent = expected;
    }
  }

  function setRowState(row, open) {
    if (!row) return;

    const next = open ? '1' : '0';
    if (row.dataset.dpDetailsActive !== next) row.dataset.dpDetailsActive = next;
    if (row.dataset.dpV13Open !== next) row.dataset.dpV13Open = next;

    if (row.hidden === open) row.hidden = !open;

    const ariaHidden = open ? 'false' : 'true';
    if (row.getAttribute('aria-hidden') !== ariaHidden) row.setAttribute('aria-hidden', ariaHidden);

    if (open) {
      if (row.style.getPropertyValue('display')) row.style.removeProperty('display');
    } else if (row.style.getPropertyValue('display') !== 'none' || row.style.getPropertyPriority('display') !== 'important') {
      row.style.setProperty('display', 'none', 'important');
    }

    const id = rowId(row);
    buttonsFor(id).forEach(button => syncButton(button, open));
  }

  function reconcile(preferredId = '') {
    if (reconciling) return;
    const target = view();
    if (!target) return;

    reconciling = true;
    try {
      target.dataset.dpDetailsSingleOpen = '1';
      const allRows = rows();
      let keeper = null;

      if (preferredId) {
        const preferred = allRows.find(row => rowId(row) === String(preferredId));
        if (preferred && rowIsOpen(preferred)) keeper = preferred;
      }

      if (!keeper) keeper = allRows.find(rowIsOpen) || null;

      allRows.forEach(row => setRowState(row, row === keeper));
      activeId = keeper ? rowId(keeper) : '';
    } finally {
      reconciling = false;
    }
  }

  function scheduleReconcile(preferredId = activeId, delay = 0) {
    window.clearTimeout(reconcileTimer);
    reconcileTimer = window.setTimeout(() => reconcile(preferredId), delay);
  }

  function installObserver() {
    const target = document.querySelector('#tasks-table');
    if (!target || observer) return;

    observer = new MutationObserver(mutations => {
      if (reconciling) return;
      if (!mutations.some(mutation => mutation.type === 'childList' || mutation.type === 'attributes')) return;
      scheduleReconcile(activeId, 0);
    });

    observer.observe(target, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['hidden', 'style', 'data-dp-v13-open'],
    });
  }

  function install() {
    const target = view();
    if (!target) return;
    target.dataset.dpDetailsSingleOpen = '1';
    installObserver();
    reconcile('');
  }

  window.addEventListener('click', event => {
    const button = event.target.closest?.(BUTTON_SELECTOR);
    if (!button || !button.closest(VIEW_SELECTOR)) return;

    const id = String(button.dataset.id || '');
    if (!id) return;

    activeId = id;

    // Deixa o controlador existente executar e, logo depois, normaliza o estado.
    // Isso preserva o carregamento dos detalhes e elimina a abertura simultânea.
    [0, 24, 90].forEach(delay => window.setTimeout(() => reconcile(id), delay));
  }, true);

  document.addEventListener('devpilot:tasks-rendered', () => {
    activeId = '';
    window.setTimeout(() => {
      installObserver();
      reconcile('');
    }, 0);
  });

  document.addEventListener('devpilot:view-changed', event => {
    if (event?.detail?.view !== 'tasks') return;
    window.setTimeout(install, 0);
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, {once: true});
  } else {
    install();
  }
})();
