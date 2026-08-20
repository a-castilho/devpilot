(() => {
  const VIEW_ID = 'project-example-view';

  function frameDocument(frame) {
    try {
      return frame?.contentDocument || frame?.contentWindow?.document || null;
    } catch (_) {
      return null;
    }
  }

  function analysisTarget(doc) {
    if (!doc) return null;
    const patterns = doc.getElementById('patterns');
    return patterns?.closest('.panel.patterns') || patterns || null;
  }

  function scrollToAnalysis(doc) {
    const target = analysisTarget(doc);
    if (!target) return false;
    target.setAttribute('tabindex', '-1');
    try {
      target.scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (_) {
      target.scrollIntoView();
    }
    window.setTimeout(() => target.focus({preventScroll: true}), 260);
    return true;
  }

  function bindFrame(frame) {
    const doc = frameDocument(frame);
    if (!doc?.body || doc.documentElement.dataset.devpilotAnalysisScroll === '1') return;
    doc.documentElement.dataset.devpilotAnalysisScroll = '1';

    const analyze = doc.getElementById('analyze');
    if (analyze) {
      analyze.addEventListener('click', () => {
        window.setTimeout(() => scrollToAnalysis(doc), 30);
      });
    }

    doc.querySelectorAll('.nav button').forEach(button => {
      if (button.textContent.trim().toLowerCase() !== 'padrões') return;
      button.addEventListener('click', event => {
        event.preventDefault();
        scrollToAnalysis(doc);
      });
    });
  }

  function prepare() {
    const view = document.getElementById(VIEW_ID);
    const frame = view?.querySelector('#repeatai-frame');
    if (!frame) return;

    if (frame.dataset.analysisScrollPrepared !== '1') {
      frame.dataset.analysisScrollPrepared = '1';
      frame.addEventListener('load', () => bindFrame(frame));
    }
    bindFrame(frame);
  }

  prepare();

  document.addEventListener('click', event => {
    if (!event.target.closest?.('[data-example-project="repeatai"]')) return;
    window.setTimeout(prepare, 0);
  }, {passive: true});
})();
