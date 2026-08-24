(() => {
  const VIEW_ID = 'project-example-view';

  function view() {
    return document.getElementById(VIEW_ID);
  }

  function frameDocument(frame) {
    try {
      return frame?.contentDocument || frame?.contentWindow?.document || null;
    } catch (_) {
      return null;
    }
  }

  function graphTarget(doc) {
    if (!doc) return null;
    const selectors = [
      '#chart',
      '#graphs',
      '#graficos',
      '[data-section="graphs"]',
      '[data-section="charts"]',
      '.graphs',
      '.charts',
      '.chart',
      'canvas',
      'svg[role="img"]',
    ];

    for (const selector of selectors) {
      const node = doc.querySelector(selector);
      if (node) return node.closest('article,section,.panel,.card') || node;
    }
    return null;
  }

  function showGraphInsideFrame(frame) {
    const doc = frameDocument(frame);
    const target = graphTarget(doc);
    if (!target) return false;

    try {
      target.scrollIntoView({behavior: 'auto', block: 'start'});
    } catch (_) {
      return false;
    }

    target.classList.add('devpilot-graphs-focus');
    window.setTimeout(() => target.classList.remove('devpilot-graphs-focus'), 700);
    return true;
  }

  function setCaptionStatus(currentView, text) {
    const status = currentView?.querySelector('.example-project-caption span');
    if (status) status.textContent = text;
  }

  function openGraphs(button) {
    const currentView = view();
    const stage = currentView?.querySelector('#repeatai-stage');
    const frame = currentView?.querySelector('#repeatai-frame');
    if (!currentView || !stage || !frame) return;
    if (button.dataset.graphsBusy === '1') return;

    button.dataset.graphsBusy = '1';
    const oldLabel = button.textContent;
    button.disabled = true;
    setCaptionStatus(currentView, 'abrindo gráficos...');

    stage.scrollIntoView({behavior: 'auto', block: 'start'});

    window.setTimeout(() => {
      const moved = showGraphInsideFrame(frame);
      setCaptionStatus(currentView, moved ? 'gráficos prontos' : 'painel pronto');
      button.disabled = false;
      button.textContent = oldLabel || 'VER GRÁFICOS';
      button.dataset.graphsBusy = '0';
    }, 60);
  }

  function injectFocusStyle() {
    if (document.getElementById('devpilot-graphs-fix-style')) return;
    const style = document.createElement('style');
    style.id = 'devpilot-graphs-fix-style';
    style.textContent = `
      .devpilot-graphs-focus{
        outline:2px solid rgba(59,228,208,.7)!important;
        outline-offset:2px
      }
    `;
    document.head.appendChild(style);
  }

  injectFocusStyle();

  document.addEventListener('click', event => {
    const button = event.target.closest?.('#repeatai-wizard-actions button');
    if (!button || button.textContent.trim() !== 'VER GRÁFICOS') return;
    openGraphs(button);
  });
})();