(() => {
  const VIEW_ID = 'project-example-view';
  const FRAME_ID = 'repeatai-frame';
  const STAGE_ID = 'repeatai-stage';
  const TICK_MS = 1000;

  let observer = null;
  let liveTimer = null;
  let graphsVisible = false;
  let lastScrollY = window.scrollY;
  let pendingScrollDelta = 0;

  function view() {
    return document.getElementById(VIEW_ID);
  }

  function frame() {
    return view()?.querySelector(`#${FRAME_ID}`) || null;
  }

  function frameDocument() {
    try {
      const current = frame();
      return current?.contentDocument || current?.contentWindow?.document || null;
    } catch (_) {
      return null;
    }
  }

  function setOuterStatus(text) {
    const node = view()?.querySelector('.example-project-caption span');
    if (!node) return;
    node.textContent = text;
    node.classList.add('repeatai-mobile-live');
  }

  function ensureRecording(doc) {
    if (!doc) return false;
    const start = doc.getElementById('start');
    const stop = doc.getElementById('stop');
    const duration = doc.getElementById('duration');

    if (stop && !stop.disabled) return true;
    if (!start || start.disabled) return false;

    if (duration && !duration.disabled) duration.value = '300';
    start.click();
    return Boolean(stop && !stop.disabled);
  }

  function forwardScrollSample(doc) {
    if (!doc || !pendingScrollDelta) return;
    const delta = Math.max(-900, Math.min(900, pendingScrollDelta));
    pendingScrollDelta = 0;

    try {
      doc.dispatchEvent(new WheelEvent('wheel', {
        deltaY: delta,
        bubbles: true,
      }));
    } catch (_) {
      // A atualização temporal do gráfico continua mesmo sem WheelEvent.
    }
  }

  function refreshLiveHint(doc) {
    const hint = doc?.getElementById('chartHint');
    if (!hint) return;
    const now = new Date().toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
    hint.textContent = `ao vivo · ${now}`;
  }

  function liveTick() {
    if (!graphsVisible || document.hidden) return;
    const doc = frameDocument();
    if (!doc) return;

    const recording = ensureRecording(doc);
    forwardScrollSample(doc);
    refreshLiveHint(doc);
    setOuterStatus(recording ? '● gráficos ao vivo' : '● atualizando gráficos');
  }

  function startLiveUpdates() {
    graphsVisible = true;
    if (liveTimer) return;
    liveTick();
    liveTimer = window.setInterval(liveTick, TICK_MS);
  }

  function stopLiveUpdates() {
    graphsVisible = false;
    if (liveTimer) {
      window.clearInterval(liveTimer);
      liveTimer = null;
    }
    pendingScrollDelta = 0;
  }

  function observeStage() {
    const currentView = view();
    const stage = currentView?.querySelector(`#${STAGE_ID}`);
    if (!stage || stage.dataset.liveGraphsObserved === '1') return;
    stage.dataset.liveGraphsObserved = '1';

    if (!('IntersectionObserver' in window)) {
      startLiveUpdates();
      return;
    }

    observer?.disconnect();
    observer = new IntersectionObserver(entries => {
      const visible = entries.some(entry => entry.isIntersecting && entry.intersectionRatio >= 0.18);
      if (visible && currentView.classList.contains('active')) startLiveUpdates();
      else stopLiveUpdates();
    }, {
      threshold: [0, 0.18, 0.4],
      rootMargin: '0px 0px -70px 0px',
    });
    observer.observe(stage);
  }

  function prepare() {
    observeStage();
    const currentFrame = frame();
    if (currentFrame && currentFrame.dataset.liveGraphsPrepared !== '1') {
      currentFrame.dataset.liveGraphsPrepared = '1';
      currentFrame.addEventListener('load', () => {
        if (graphsVisible) window.setTimeout(liveTick, 80);
      });
    }
  }

  window.addEventListener('scroll', () => {
    const current = window.scrollY;
    const delta = current - lastScrollY;
    lastScrollY = current;
    if (!graphsVisible || !delta || !view()?.classList.contains('active')) return;
    pendingScrollDelta += delta;
  }, {passive: true});

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    if (graphsVisible) liveTick();
  });

  document.addEventListener('click', event => {
    if (event.target.closest?.('[data-example-project="repeatai"]')) {
      window.setTimeout(prepare, 0);
      return;
    }

    const button = event.target.closest?.('#repeatai-wizard-actions button');
    if (button && button.textContent.trim() === 'VER GRÁFICOS') {
      window.setTimeout(() => {
        prepare();
        startLiveUpdates();
      }, 100);
    }
  }, {passive: true});

  prepare();
})();
