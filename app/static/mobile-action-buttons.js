(() => {
  'use strict';

  if (window.__devpilotMobileActionsReady) return;
  window.__devpilotMobileActionsReady = true;

  const ACTION_SELECTOR = [
    '.view .section-head > .primary',
    '.view .hero-actions > .primary',
    '.view .hero-actions > .voice',
    '.view [data-project-builder-open]',
    '.view .builder-submit',
    '.view .task-submit',
    '.view .reports-actions > button',
  ].join(',');

  const isMobile = () => (
    document.body.classList.contains('mobile-route') ||
    window.matchMedia('(max-width: 900px)').matches
  );

  function cleanLabel(button) {
    return String(
      button?.dataset?.responseLabel ||
      button?.getAttribute?.('aria-label') ||
      button?.textContent ||
      'ação'
    )
      .replace(/^\s*[+●✦✓]+\s*/u, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function decorate(root = document) {
    if (!isMobile()) return;
    root.querySelectorAll?.(ACTION_SELECTOR).forEach(button => {
      if (!(button instanceof HTMLButtonElement)) return;
      button.classList.add('dp-mobile-action');
      if (!button.dataset.responseLabel) button.dataset.responseLabel = cleanLabel(button);
    });
  }

  function announceImmediateAction(button) {
    if (!isMobile() || !button?.classList?.contains('dp-mobile-action')) return;
    if (button.type === 'submit' || button.closest('form')?.contains(button) && button.hasAttribute('form')) return;
    if (button.getAttribute('aria-busy') === 'true') return;

    const label = cleanLabel(button);
    if (!label) return;
    const message = `Abrindo ${label}…`;
    if (window.DevPilotResponses?.info) {
      window.DevPilotResponses.info(message, {duration: 1800});
    } else if (typeof window.toast === 'function') {
      window.toast(message);
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest?.('.dp-mobile-action');
    if (!(button instanceof HTMLButtonElement)) return;
    announceImmediateAction(button);
  }, true);

  const observer = new MutationObserver(mutations => {
    if (!isMobile()) return;
    for (const mutation of mutations) {
      mutation.addedNodes.forEach(node => {
        if (!(node instanceof Element)) return;
        if (node.matches?.(ACTION_SELECTOR)) decorate(node.parentElement || document);
        else decorate(node);
      });
    }
  });

  const start = () => {
    decorate();
    observer.observe(document.body, {childList: true, subtree: true});
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, {once: true});
  } else {
    start();
  }

  window.matchMedia('(max-width: 900px)').addEventListener?.('change', event => {
    if (event.matches) decorate();
  });
})();
