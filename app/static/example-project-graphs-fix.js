(() => {
  const VIEW_ID = 'project-example-view';
  const BUTTON_LABEL = 'VER GRÁFICOS';
  const REFRESH_PARAM = 'devpilot_graphs_refresh';

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
      '#graphs',
      '#graficos',
      '#chart',
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
      if (!node) continue;
      return node.closest('article,section,.panel,.card') || node;
    }

    return null;
  }

  function showGraphInsideFrame(frame) {
    const doc = frameDocument(frame);
    const target = graphTarget(doc);
    if (!target) return false;

    const win = doc.defaultView;
    const top = target.getBoundingClientRect().top + (win?.scrollY || 0) - 12;

    try {
      win?.scrollTo({top: Math.max(0, top), behavior: 'smooth'});
    } catch (_) {
      target.scrollIntoView({behavior: 'smooth', block: 'start'});
    }

    target.classList.add('devpilot-graphs-focus');
    window.setTimeout(() => target.classList.remove('devpilot-graphs-focus'), 1400);
    return true;
  }

  function requestGraphNavigation(frame) {
    try {
      frame?.contentWindow?.postMessage({
        type: 'devpilot:show-graphs',
        source: 'devpilot',
      }, '*');
    } catch (_) {
      // A navegação por postMessage é apenas um fallback para apps cross-origin.
    }
  }

  function refreshFrame(frame) {
    return new Promise(resolve => {
      if (!frame) {
        resolve(false);
        return;
      }

      const raw = frame.getAttribute('src');
      if (!raw) {
        resolve(false);
        return;
      }

      let settled = false;
      const finish = ok => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeout);
        resolve(ok);
      };

      const onLoad = () => finish(true);
      frame.addEventListener('load', onLoad, {once: true});

      const timeout = window.setTimeout(() => finish(false), 4500);

      try {
        const url = new URL(raw, window.location.href);
        url.searchParams.set(REFRESH_PARAM, String(Date.now()));
        frame.dataset.ready = '0';
        frame.src = url.toString();
      } catch (_) {
        frame.src = raw;
      }
    });
  }

  function setCaptionStatus(currentView, text) {
    const status = currentView?.querySelector('.example-project-caption span');
    if (status) status.textContent = text;
  }

  async function openGraphs(button) {
    const currentView = view();
    const stage = currentView?.querySelector('#repeatai-stage');
    const frame = currentView?.querySelector('#repeatai-frame');
    if (!currentView || !stage || !frame) return;

    if (button.dataset.graphsBusy === '1') return;
    button.dataset.graphsBusy = '1';

    const oldLabel = button.textContent;
    button.disabled = true;
    button.textContent = 'ATUALIZANDO...';
    setCaptionStatus(currentView, 'atualizando gráficos...');

    stage.scrollIntoView({behavior: 'smooth', block: 'start'});

    // Navegar ao gráfico não deve recriar o iframe: a recarga interrompia a
    // captura e multiplicava o custo de renderização no navegador.
    const moved = showGraphInsideFrame(frame);
    if (!moved) requestGraphNavigation(frame);

    window.setTimeout(() => {
      const now = new Date().toLocaleTimeString('pt-BR');
      setCaptionStatus(
        currentView,
        moved ? `gráficos atualizados · ${now}` : 'atualização em tempo real'
      );
      button.disabled = false;
      button.textContent = oldLabel || BUTTON_LABEL;
      button.dataset.graphsBusy = '0';
    }, 80);
  }

  function bindButton(currentView) {
    if (!currentView) return;

    const buttons = currentView.querySelectorAll('#repeatai-wizard-actions button');
    buttons.forEach(button => {
      if (button.textContent.trim() !== BUTTON_LABEL) return;
      if (button.dataset.graphsFix === '1') return;

      button.dataset.graphsFix = '1';
      button.addEventListener('click', () => openGraphs(button));
    });
  }

  function injectFocusStyle() {
    if (document.getElementById('devpilot-graphs-fix-style')) return;

    const style = document.createElement('style');
    style.id = 'devpilot-graphs-fix-style';
    style.textContent = `
      .devpilot-graphs-focus{
        outline:2px solid rgba(59,228,208,.8) !important;
        outline-offset:3px;
        box-shadow:0 0 0 5px rgba(59,228,208,.1) !important
      }
    `;
    document.head.appendChild(style);
  }

  function scan() {
    bindButton(view());
  }

  injectFocusStyle();
  scan();

  let scanFrame = 0;
  const scheduleScan = () => {
    if (scanFrame) return;
    scanFrame = window.requestAnimationFrame(() => {
      scanFrame = 0;
      scan();
    });
  };

  const observer = new MutationObserver(scheduleScan);
  observer.observe(document.querySelector('main') || document.body, {
    childList: true,
    subtree: true,
  });
})();
