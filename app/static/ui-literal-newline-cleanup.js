(() => {
  const LITERAL_NEWLINE_ONLY = /^(?:\\r|\\n)+$/;

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

  removeLiteralNewlineArtifacts();

  const observer = new MutationObserver(() => removeLiteralNewlineArtifacts());
  observer.observe(document.body, {childList: true, subtree: true});

  window.setTimeout(() => observer.disconnect(), 2000);
})();
