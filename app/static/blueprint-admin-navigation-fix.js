(() => {
  'use strict';

  document.addEventListener('click', event => {
    const button = event.target instanceof Element
      ? event.target.closest('[data-view="blueprints-admin"]')
      : null;
    if (!button) return;
    const view = document.getElementById('blueprints-admin-view');
    if (!view) return;
    queueMicrotask(() => {
      document.querySelectorAll('.view').forEach(item => {
        const active = item === view;
        item.classList.toggle('active', active);
        item.hidden = !active;
        item.setAttribute('aria-hidden', active ? 'false' : 'true');
      });
      document.documentElement.dataset.devpilotView = 'blueprints-admin';
    });
  }, true);
})();
