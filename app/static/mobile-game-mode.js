/* DevPilot mobile: keep Modo jogo visible in the bottom quickbar. */
(() => {
  'use strict';

  const GAME_SELECTOR = '.sidebar nav .nav[data-view="build-game"]';
  const QUICKBAR_SELECTOR = '.mobile-quickbar';
  const ITEM_CLASS = 'mobile-game-mode-item';
  let syncing = false;
  let scheduled = false;

  const isMobileRoute = () => document.body?.classList.contains('mobile-route');

  function scheduleSync() {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(() => {
      scheduled = false;
      sync();
    });
  }

  function sync() {
    if (syncing || !isMobileRoute()) return;
    syncing = true;
    try {
      const gameNav = document.querySelector(GAME_SELECTOR);
      const quickbar = document.querySelector(QUICKBAR_SELECTOR);
      if (!gameNav || !quickbar) return;

      let button = quickbar.querySelector(`.${ITEM_CLASS}`);
      if (!button) {
        button = document.createElement('button');
        button.type = 'button';
        button.className = `mobile-quick-item ${ITEM_CLASS}`;
        button.setAttribute('aria-label', 'Modo jogo');
        button.setAttribute('title', 'Modo jogo');
        button.innerHTML = '<span class="mobile-menu-icon" aria-hidden="true">🎮</span>';
        button.addEventListener('click', () => {
          const source = document.querySelector(GAME_SELECTOR);
          if (!source) return;
          source.click();
          requestAnimationFrame(scheduleSync);
        });
        quickbar.appendChild(button);
      }

      button.classList.toggle('active', gameNav.classList.contains('active'));
      button.setAttribute('aria-current', gameNav.classList.contains('active') ? 'page' : 'false');
    } finally {
      syncing = false;
    }
  }

  function boot() {
    if (!isMobileRoute()) return;

    sync();

    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;

    const observer = new MutationObserver(scheduleSync);
    observer.observe(sidebar, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class', 'hidden'],
    });

    document.addEventListener('devpilot:mobile-game-sync', scheduleSync);
    window.addEventListener('pageshow', scheduleSync);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, {once: true});
  } else {
    boot();
  }
})();
