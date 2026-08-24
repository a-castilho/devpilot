(() => {
  const LITERAL_NEWLINE_ONLY = /^(?:\\r|\\n)+$/;
  const ANALYSIS_DIALOG_ID = 'task-log-modal';
  const ANALYSIS_LINK_SELECTOR = '.task-log-link';
  const CORRECTION_CARD_SELECTOR = '.analysis-correction-card';
  const REVEAL_TIMEOUT_MS = 10000;

  function removeLiteralNewlineArtifacts(root = document.body) {
    if (!root) return;

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const removable = [];
    let node = walker.nextNode();

    while (node) {
      const value = String(node.nodeValue || '').trim();
      if (value && LITERAL_NEWLINE_ONLY.test(value)) removable.push(node);
      node = walker.nextNode();
    }

    removable.forEach((textNode) => textNode.remove());
  }

  function correctionCardIsVisible(card) {
    return Boolean(card && !card.hidden && card.getClientRects().length);
  }

  function revealCorrectionCard(dialog) {
    if (!dialog?.open) return false;

    const panel = dialog.querySelector('.task-log-modal-panel');
    const card = panel?.querySelector(CORRECTION_CARD_SELECTOR);
    if (!panel || !correctionCardIsVisible(card)) return false;

    window.requestAnimationFrame(() => {
      const target = Math.max(
        0,
        card.offsetTop + card.offsetHeight - panel.clientHeight + 12,
      );
      panel.scrollTo({top: target, behavior: 'auto'});
    });
    return true;
  }

  function revealCorrectionCardWhenReady() {
    const dialog = document.getElementById(ANALYSIS_DIALOG_ID);
    if (!dialog) return;
    if (revealCorrectionCard(dialog)) return;

    const observer = new MutationObserver(() => {
      if (!dialog.open) {
        observer.disconnect();
        return;
      }
      if (revealCorrectionCard(dialog)) observer.disconnect();
    });

    observer.observe(dialog, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['hidden', 'open'],
    });

    window.setTimeout(() => observer.disconnect(), REVEAL_TIMEOUT_MS);
  }

  removeLiteralNewlineArtifacts();

  const cleanupObserver = new MutationObserver(() => removeLiteralNewlineArtifacts());
  cleanupObserver.observe(document.body, {childList: true, subtree: true});
  window.setTimeout(() => cleanupObserver.disconnect(), 2000);

  document.addEventListener('click', (event) => {
    if (!event.target.closest?.(ANALYSIS_LINK_SELECTOR)) return;
    window.setTimeout(revealCorrectionCardWhenReady, 90);
  }, true);
})();
