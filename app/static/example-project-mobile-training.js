(() => {
  const MOBILE = matchMedia('(max-width:760px)').matches || matchMedia('(pointer:coarse)').matches;
  const FALLBACK = '/examples/repeatai/index.html';
  const MOVE_INTERVAL = 140;
  const SCROLL_INTERVAL = 180;

  let captureActive = false;
  let captureTimer = 0;
  let lastMoveAt = 0;
  let lastScrollAt = 0;
  let lastScrollY = window.scrollY;
  let pendingScrollDelta = 0;

  const getView = () => document.getElementById('project-example-view');

  function getFrameDoc(frame) {
    try {
      return frame?.contentDocument || frame?.contentWindow?.document || null;
    } catch (_) {
      return null;
    }
  }

  function currentStep(view) {
    return view?.querySelector('#repeatai-wizard-kicker')?.textContent.trim() || '';
  }

  function injectStyles() {
    if (document.getElementById('repeatai-mobile-training-styles')) return;
    const style = document.createElement('style');
    style.id = 'repeatai-mobile-training-styles';
    style.textContent = `
      #repeatai-train-horn{display:none!important}
      .repeatai-mobile-keyboard{width:min(560px,100%);margin-top:14px;border:1px solid #36506d;border-radius:12px;padding:13px 14px;background:#071320;color:#eef7ff;font:600 16px/1.3 system-ui,sans-serif;outline:none}
      .repeatai-mobile-keyboard:focus{border-color:#3be4d0}
      .example-project-caption .repeatai-mobile-live{display:inline-flex;align-items:center;gap:6px;color:#3be4d0;font-weight:800}
      .example-project-caption .repeatai-mobile-live:before{content:'';width:7px;height:7px;border-radius:50%;background:#3be4d0}
      @media(max-width:760px){
        .repeatai-wizard-title{font-size:clamp(25px,8vw,38px)!important}
        .repeatai-wizard-copy{font-size:14px!important;line-height:1.45}
        .example-project-stage{box-shadow:none!important}
      }
    `;
    document.head.appendChild(style);
  }

  function ensureStatus(view) {
    view?.querySelector('#repeatai-train-horn')?.remove();
    const caption = view?.querySelector('.example-project-caption');
    if (!caption || view.querySelector('#repeatai-mobile-live')) return;

    const live = document.createElement('span');
    live.id = 'repeatai-mobile-live';
    live.className = 'repeatai-mobile-live';
    live.textContent = MOBILE ? 'mobile econômico' : 'tempo real';
    caption.querySelector('span')?.replaceWith(live);
  }

  function setStatus(view, text) {
    const live = view?.querySelector('#repeatai-mobile-live');
    if (live) live.textContent = text;
  }

  function syncWizard(view) {
    if (!view) return;
    view.querySelector('#repeatai-train-horn')?.remove();

    const title = view.querySelector('#repeatai-wizard-title');
    const copy = view.querySelector('#repeatai-wizard-copy');
    const kicker = view.querySelector('#repeatai-wizard-kicker');
    const step = kicker?.textContent.trim() || '';

    if (title?.textContent.trim() === 'MOVA O MOUSE LOUCAMENTE') {
      title.textContent = 'MOVA O DEDO E TOQUE NA TELA';
    }

    if (step === 'MOUSE' && copy && MOBILE) {
      copy.textContent = 'Arraste o dedo e toque na tela. A amostragem é limitada para manter o navegador fluido.';
    }

    if (step === 'SCROLL' && copy && MOBILE) {
      copy.textContent = 'Role esta página normalmente para cima e para baixo. O scroll permanece nativo do navegador.';
    }

    if (!MOBILE) return;

    const body = view.querySelector('.repeatai-wizard-body');
    const actions = view.querySelector('#repeatai-wizard-actions');
    let input = view.querySelector('#repeatai-mobile-keyboard');

    if (step !== 'TECLADO') {
      input?.remove();
      return;
    }

    if (input || !body) return;

    input = document.createElement('input');
    input.id = 'repeatai-mobile-keyboard';
    input.className = 'repeatai-mobile-keyboard';
    input.type = 'text';
    input.autocomplete = 'off';
    input.autocapitalize = 'off';
    input.spellcheck = false;
    input.placeholder = 'Toque aqui e digite para treinar';
    input.setAttribute('aria-label', 'Área de digitação para treinamento');

    if (actions) body.insertBefore(input, actions);
    else body.appendChild(input);

    setTimeout(() => input.focus({preventScroll:true}), 60);
  }

  function markCapture(view, active) {
    captureActive = active;
    clearTimeout(captureTimer);
    setStatus(view, active ? 'treinando · modo econômico' : 'mobile econômico');
    if (active) captureTimer = setTimeout(() => stopCapture(view), 45000);
  }

  function startCapture(view) {
    const frame = view?.querySelector('#repeatai-frame');
    const doc = getFrameDoc(frame);
    if (!frame || !doc) {
      if (frame) frame.dataset.startCaptureWhenReady = '1';
      return false;
    }

    const duration = doc.getElementById('duration');
    const start = doc.getElementById('start');
    const stop = doc.getElementById('stop');
    if (duration && !duration.disabled) duration.value = '60';
    if (start && !start.disabled) start.click();

    const active = Boolean(stop && !stop.disabled);
    markCapture(view, active);
    return active;
  }

  function stopCapture(view) {
    const doc = getFrameDoc(view?.querySelector('#repeatai-frame'));
    const stop = doc?.getElementById('stop');
    if (stop && !stop.disabled) stop.click();
    markCapture(view, false);
  }

  function forceFallback(frame) {
    if (!MOBILE || !frame) return false;
    const src = frame.getAttribute('src') || '';
    if (src.includes(FALLBACK) || frame.dataset.mobileFallbackForced === '1') return false;

    frame.dataset.mobileFallbackForced = '1';
    frame.src = `${FALLBACK}?mobile=native-scroll&t=${Date.now()}`;
    return true;
  }

  function tuneFrame(view) {
    const frame = view?.querySelector('#repeatai-frame');
    const doc = getFrameDoc(frame);
    if (!frame || !doc?.body) return false;

    if (doc.documentElement.dataset.devpilotMobileTraining !== 'native-scroll') {
      doc.documentElement.dataset.devpilotMobileTraining = 'native-scroll';
      const style = doc.createElement('style');
      style.textContent = `
        @media(max-width:760px){
          html,body{overscroll-behavior-y:auto!important;-webkit-overflow-scrolling:touch}
          .chart-line{filter:none!important}
          .chart-point{animation:none!important}
          .status.live .dot{box-shadow:none!important}
          .metric,.panel{box-shadow:none!important}
          .event-stream{max-height:160px}
        }
      `;
      doc.head.appendChild(style);

      let frameLastMove = 0;
      doc.addEventListener('pointermove', event => {
        if (event.pointerType === 'mouse') return;
        const stop = doc.getElementById('stop');
        if (!stop || stop.disabled) return;
        const now = performance.now();
        if (now - frameLastMove < MOVE_INTERVAL) return;
        frameLastMove = now;
        doc.dispatchEvent(new MouseEvent('mousemove', {
          clientX: event.clientX,
          clientY: event.clientY,
          bubbles: true,
        }));
      }, {passive:true});
    }

    if (frame.dataset.startCaptureWhenReady === '1') {
      frame.dataset.startCaptureWhenReady = '0';
      startCapture(view);
    }
    return true;
  }

  function bridgeWizardOnly(view) {
    if (!MOBILE || !view || view.dataset.mobileBridge === 'native-scroll') return;
    view.dataset.mobileBridge = 'native-scroll';

    window.addEventListener('pointermove', event => {
      if (!view.classList.contains('active')) return;
      if (event.pointerType === 'mouse') return;
      if (currentStep(view) !== 'MOUSE') return;

      const now = performance.now();
      if (now - lastMoveAt < MOVE_INTERVAL) return;
      lastMoveAt = now;
      window.dispatchEvent(new MouseEvent('mousemove', {
        clientX: event.clientX,
        clientY: event.clientY,
        bubbles: false,
      }));
    }, {passive:true});

    /* Android touch scrolling does not emit WheelEvent. We only synthesize a
       low-frequency wheel for the wizard progress. It is never forwarded to
       the iframe, so the browser keeps complete ownership of the real scroll. */
    window.addEventListener('scroll', () => {
      const current = window.scrollY;
      const delta = current - lastScrollY;
      lastScrollY = current;
      if (!view.classList.contains('active') || !delta || currentStep(view) !== 'SCROLL') return;

      pendingScrollDelta += delta;
      const now = performance.now();
      if (now - lastScrollAt < SCROLL_INTERVAL) return;
      lastScrollAt = now;

      const batchedDelta = pendingScrollDelta;
      pendingScrollDelta = 0;
      window.dispatchEvent(new WheelEvent('wheel', {
        deltaY: batchedDelta,
        bubbles: false,
      }));
    }, {passive:true});
  }

  function prepare(view) {
    if (!view) return;
    ensureStatus(view);
    syncWizard(view);
    bridgeWizardOnly(view);

    const frame = view.querySelector('#repeatai-frame');
    if (frame && frame.dataset.mobileTrainingPrepared !== 'native-scroll') {
      frame.dataset.mobileTrainingPrepared = 'native-scroll';
      frame.addEventListener('load', () => {
        if (MOBILE && forceFallback(frame)) return;
        tuneFrame(view);
      });
    }

    const kicker = view.querySelector('#repeatai-wizard-kicker');
    if (kicker && kicker.dataset.mobileStepObserved !== 'native-scroll') {
      kicker.dataset.mobileStepObserved = 'native-scroll';
      new MutationObserver(() => {
        syncWizard(view);
        if (currentStep(view) === 'REPETAI PRONTO' && captureActive) stopCapture(view);
      }).observe(kicker, {childList:true, characterData:true, subtree:true});
    }
  }

  injectStyles();
  prepare(getView());

  document.addEventListener('click', event => {
    const view = getView();
    if (!view) return;

    if (event.target.closest?.('[data-example-project="repeatai"]')) {
      setTimeout(() => prepare(getView()), 0);
      return;
    }

    const actionButton = event.target.closest?.('#repeatai-wizard-actions button');
    if (!actionButton || !view.contains(actionButton)) return;

    if (actionButton.textContent.trim() === 'COMEÇAR') {
      setTimeout(() => {
        prepare(view);
        startCapture(view);
      }, 0);
    }
  });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden && captureActive) stopCapture(getView());
  });
})();