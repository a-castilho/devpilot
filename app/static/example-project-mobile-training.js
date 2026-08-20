(() => {
  const FALLBACK_URL = '/examples/repeatai/index.html';
  const MOBILE =
    window.matchMedia('(max-width: 760px)').matches ||
    window.matchMedia('(pointer: coarse)').matches;

  let trainingActive = false;
  let trainingTimer = null;
  let parentLastScrollY = window.scrollY;

  function injectStyles() {
    if (document.getElementById('repeatai-mobile-training-styles')) return;

    const style = document.createElement('style');
    style.id = 'repeatai-mobile-training-styles';
    style.textContent = `
      .repeatai-train-horn{
        margin-top:14px;
        width:min(310px,92%);
        min-height:74px;
        border:0 !important;
        border-radius:999px !important;
        display:flex;
        align-items:center;
        justify-content:center;
        gap:12px;
        background:
          radial-gradient(circle at 28% 22%,#ff8a82 0,#ff3b30 34%,#be0000 100%) !important;
        color:#fff !important;
        font-size:16px !important;
        font-weight:950 !important;
        letter-spacing:.05em;
        box-shadow:
          0 12px 30px rgba(190,0,0,.35),
          0 0 0 6px rgba(255,59,48,.09);
        cursor:pointer;
        touch-action:manipulation;
        transition:transform .16s ease,filter .16s ease,box-shadow .16s ease
      }
      .repeatai-train-horn:hover,
      .repeatai-train-horn:active{
        transform:scale(1.025);
        filter:brightness(1.08)
      }
      .repeatai-train-horn.active{
        animation:repeataiHornPulse .9s ease-out infinite;
        background:
          radial-gradient(circle at 28% 22%,#ff9c95 0,#ff3026 34%,#990000 100%) !important
      }
      .repeatai-train-horn-icon{
        width:46px;
        height:46px;
        border-radius:50%;
        display:grid;
        place-items:center;
        background:rgba(255,255,255,.16);
        border:1px solid rgba(255,255,255,.28);
        font-size:26px;
        line-height:1
      }
      .repeatai-train-horn-copy{
        display:grid;
        text-align:left;
        line-height:1.05
      }
      .repeatai-train-horn-copy small{
        margin-top:5px;
        color:#ffd7d4;
        font-size:9px;
        font-weight:850;
        letter-spacing:.08em
      }
      .repeatai-mobile-keyboard{
        width:min(560px,100%);
        margin-top:14px;
        border:1px solid #36506d;
        border-radius:12px;
        padding:13px 14px;
        background:#071320;
        color:#eef7ff;
        font:600 16px/1.3 system-ui,sans-serif;
        outline:none
      }
      .repeatai-mobile-keyboard:focus{
        border-color:#3be4d0;
        box-shadow:0 0 0 3px rgba(59,228,208,.12)
      }
      .example-project-caption .repeatai-mobile-live{
        display:inline-flex;
        align-items:center;
        gap:6px;
        color:#3be4d0;
        font-weight:800
      }
      .example-project-caption .repeatai-mobile-live::before{
        content:'';
        width:7px;
        height:7px;
        border-radius:50%;
        background:#3be4d0;
        box-shadow:0 0 10px #3be4d0;
        animation:repeataiLiveDot 1s ease-in-out infinite
      }
      @keyframes repeataiHornPulse{
        0%{box-shadow:0 12px 30px rgba(190,0,0,.35),0 0 0 0 rgba(255,59,48,.45)}
        70%{box-shadow:0 12px 30px rgba(190,0,0,.35),0 0 0 18px rgba(255,59,48,0)}
        100%{box-shadow:0 12px 30px rgba(190,0,0,.35),0 0 0 0 rgba(255,59,48,0)}
      }
      @keyframes repeataiLiveDot{
        0%,100%{opacity:1;transform:scale(1)}
        50%{opacity:.4;transform:scale(.72)}
      }
      @media(max-width:760px){
        .repeatai-wizard-title{font-size:clamp(25px,8vw,38px) !important}
        .repeatai-wizard-copy{font-size:14px !important;line-height:1.45}
        .repeatai-train-horn{width:100%;min-height:82px;margin-top:16px}
        .example-project-stage.mobile-training-ready{
          overflow:visible !important;
          min-height:780px !important
        }
        .example-project-frame.mobile-training-ready{
          min-height:780px !important;
          overflow:hidden !important
        }
      }
    `;
    document.head.appendChild(style);
  }

  function viewIsActive(view) {
    return Boolean(view && view.classList.contains('active'));
  }

  function replaceMouseInstruction(view) {
    const title = view.querySelector('#repeatai-wizard-title');
    const copy = view.querySelector('#repeatai-wizard-copy');
    const kicker = view.querySelector('#repeatai-wizard-kicker');

    if (!title) return;

    if (title.textContent.trim() === 'MOVA O MOUSE LOUCAMENTE') {
      title.textContent = 'MOVA O MOUSE E CLIQUE NA TELA LOUCAMENTE';
    }

    if (kicker?.textContent.trim() === 'MOUSE' && copy) {
      copy.textContent = MOBILE
        ? 'Arraste o dedo rapidamente, faça trajetórias variadas e clique várias vezes na tela. Só sinais de interação são usados.'
        : 'Faça trajetórias rápidas e variadas e clique várias vezes nesta área. Só sinais de interação são usados.';
    }
  }

  function syncMobileKeyboard(view) {
    if (!MOBILE) return;

    const body = view.querySelector('.repeatai-wizard-body');
    const kicker = view.querySelector('#repeatai-wizard-kicker');
    if (!body || !kicker) return;

    let input = view.querySelector('#repeatai-mobile-keyboard');
    const keyboardStep = kicker.textContent.trim() === 'TECLADO';

    if (!keyboardStep) {
      input?.remove();
      return;
    }

    if (input) return;

    input = document.createElement('input');
    input.id = 'repeatai-mobile-keyboard';
    input.className = 'repeatai-mobile-keyboard';
    input.type = 'text';
    input.autocomplete = 'off';
    input.autocapitalize = 'off';
    input.spellcheck = false;
    input.placeholder = 'Toque aqui e digite para treinar';
    input.setAttribute('aria-label', 'Área de digitação para treinamento');

    const actions = view.querySelector('#repeatai-wizard-actions');
    if (actions) body.insertBefore(input, actions);
    else body.appendChild(input);

    window.setTimeout(() => input.focus({preventScroll: true}), 80);
  }

  function bridgeWizardMobile(view) {
    if (!MOBILE || view.dataset.mobileBridge === '1') return;
    view.dataset.mobileBridge = '1';

    window.addEventListener('pointermove', event => {
      if (!viewIsActive(view) || event.pointerType === 'mouse') return;
      window.dispatchEvent(new MouseEvent('mousemove', {
        clientX: event.clientX,
        clientY: event.clientY,
        bubbles: false,
      }));
    }, {passive: true});

    window.addEventListener('scroll', () => {
      if (!viewIsActive(view)) {
        parentLastScrollY = window.scrollY;
        return;
      }

      const current = window.scrollY;
      const delta = current - parentLastScrollY;
      parentLastScrollY = current;
      if (!delta) return;

      window.dispatchEvent(new WheelEvent('wheel', {
        deltaY: delta,
        bubbles: false,
      }));

      bridgeScrollToFrame(view, delta);
    }, {passive: true});
  }

  function sameOriginFrameDocument(frame) {
    try {
      return frame.contentDocument || frame.contentWindow?.document || null;
    } catch (_) {
      return null;
    }
  }

  function bridgeScrollToFrame(view, delta) {
    if (!trainingActive) return;
    const frame = view.querySelector('#repeatai-frame');
    const doc = frame ? sameOriginFrameDocument(frame) : null;
    if (!doc) return;

    doc.dispatchEvent(new WheelEvent('wheel', {
      deltaY: delta,
      bubbles: true,
    }));
  }

  function frameUsesFallback(frame) {
    const src = frame.getAttribute('src') || '';
    return src.includes('/examples/repeatai/index.html');
  }

  function forceCompiledMobile(frame) {
    if (!MOBILE || !frame) return;
    if (frameUsesFallback(frame)) return;

    frame.src = `${FALLBACK_URL}?mobile=1&t=${Date.now()}`;
  }

  function resizeFrameToContent(frame) {
    if (!MOBILE) return;
    const doc = sameOriginFrameDocument(frame);
    if (!doc) return;

    const bodyHeight = doc.body?.scrollHeight || 0;
    const rootHeight = doc.documentElement?.scrollHeight || 0;
    const height = Math.max(780, bodyHeight, rootHeight) + 12;
    const stage = frame.closest('.example-project-stage');

    frame.style.height = `${height}px`;
    frame.style.minHeight = `${height}px`;
    frame.classList.add('mobile-training-ready');

    if (stage) {
      stage.style.height = `${height}px`;
      stage.style.minHeight = `${height}px`;
      stage.classList.add('mobile-training-ready');
    }
  }

  function enhanceFrame(view) {
    const frame = view.querySelector('#repeatai-frame');
    if (!frame) return false;

    const doc = sameOriginFrameDocument(frame);
    if (!doc?.body) return false;

    if (doc.documentElement.dataset.devpilotMobileTraining !== '1') {
      doc.documentElement.dataset.devpilotMobileTraining = '1';

      const style = doc.createElement('style');
      style.textContent = `
        @media(max-width:760px){
          .chart{height:250px !important;min-height:250px !important}
          .panel{overflow:visible !important}
          .chart-line{filter:drop-shadow(0 0 5px rgba(59,228,208,.55))}
          .chart-point{animation:devpilotChartPulse .75s ease-in-out infinite alternate}
        }
        @keyframes devpilotChartPulse{to{r:6;opacity:.6}}
      `;
      doc.head.appendChild(style);

      const synthMove = (x, y) => {
        doc.dispatchEvent(new MouseEvent('mousemove', {
          clientX: x,
          clientY: y,
          bubbles: true,
        }));
      };

      doc.addEventListener('pointermove', event => {
        if (event.pointerType === 'mouse') return;
        synthMove(event.clientX, event.clientY);
      }, {passive: true});

      doc.addEventListener('touchmove', event => {
        const touch = event.touches?.[0];
        if (!touch) return;
        synthMove(touch.clientX, touch.clientY);
      }, {passive: true});

      const resize = () => resizeFrameToContent(frame);
      window.setTimeout(resize, 0);
      window.setTimeout(resize, 250);
      window.setTimeout(resize, 1000);

      if ('ResizeObserver' in window) {
        const observer = new ResizeObserver(resize);
        observer.observe(doc.documentElement);
        frame._repeataiResizeObserver = observer;
      }
    }

    resizeFrameToContent(frame);

    if (frame.dataset.autoTrain === '1') {
      frame.dataset.autoTrain = '0';
      startFrameCapture(view);
    }

    return true;
  }

  function startFrameCapture(view) {
    const frame = view.querySelector('#repeatai-frame');
    if (!frame) return false;

    const doc = sameOriginFrameDocument(frame);
    if (!doc) {
      frame.dataset.autoTrain = '1';
      forceCompiledMobile(frame);
      return false;
    }

    const start = doc.getElementById('start');
    const stop = doc.getElementById('stop');
    const duration = doc.getElementById('duration');

    if (duration && !duration.disabled) duration.value = '120';
    if (start && !start.disabled) start.click();

    trainingActive = Boolean(stop && !stop.disabled);
    markTraining(view, trainingActive);
    resizeFrameToContent(frame);
    return trainingActive;
  }

  function stopFrameCapture(view) {
    const frame = view.querySelector('#repeatai-frame');
    const doc = frame ? sameOriginFrameDocument(frame) : null;
    const stop = doc?.getElementById('stop');

    if (stop && !stop.disabled) stop.click();
    trainingActive = false;
    markTraining(view, false);
  }

  function markTraining(view, active) {
    const button = view.querySelector('#repeatai-train-horn');
    const live = view.querySelector('#repeatai-mobile-live');
    if (!button) return;

    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', active ? 'true' : 'false');

    const label = button.querySelector('strong');
    const small = button.querySelector('small');
    if (label) label.textContent = active ? 'PARAR TREINO' : 'TREINAR IA';
    if (small) small.textContent = active ? 'CAPTURA ATIVA · GRÁFICO 1S' : 'BUZINA VERMELHA · TOQUE PARA COMEÇAR';
    if (live) live.textContent = active ? 'treinando · gráfico 1s' : 'mobile pronto';

    window.clearTimeout(trainingTimer);
    if (active) {
      trainingTimer = window.setTimeout(() => {
        if (trainingActive) stopFrameCapture(view);
      }, 120000);
    }
  }

  function startTraining(view) {
    if (trainingActive) {
      stopFrameCapture(view);
      return;
    }

    navigator.vibrate?.([90, 50, 90]);

    const currentTitle = view.querySelector('#repeatai-wizard-title');
    const currentActions = view.querySelector('#repeatai-wizard-actions');
    if (currentTitle?.textContent.trim() === 'VAMOS CARREGAR A IA') {
      currentActions?.querySelector('button')?.click();
    }

    replaceMouseInstruction(view);
    syncMobileKeyboard(view);

    const frame = view.querySelector('#repeatai-frame');
    if (frame) {
      frame.dataset.autoTrain = '1';
      forceCompiledMobile(frame);
      if (enhanceFrame(view)) startFrameCapture(view);
    }

    view.querySelector('#repeatai-stage')?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
  }

  function ensureHorn(view) {
    const body = view.querySelector('.repeatai-wizard-body');
    const actions = view.querySelector('#repeatai-wizard-actions');
    if (!body || !actions) return;

    if (!view.querySelector('#repeatai-train-horn')) {
      const horn = document.createElement('button');
      horn.id = 'repeatai-train-horn';
      horn.className = 'repeatai-train-horn';
      horn.type = 'button';
      horn.setAttribute('aria-pressed', 'false');
      horn.setAttribute('aria-label', 'Treinar inteligência artificial');
      horn.innerHTML = `
        <span class="repeatai-train-horn-icon" aria-hidden="true">📣</span>
        <span class="repeatai-train-horn-copy">
          <strong>TREINAR IA</strong>
          <small>BUZINA VERMELHA · TOQUE PARA COMEÇAR</small>
        </span>`;
      horn.addEventListener('click', () => startTraining(view));
      actions.insertAdjacentElement('afterend', horn);
    }

    const caption = view.querySelector('.example-project-caption');
    if (caption && !view.querySelector('#repeatai-mobile-live')) {
      const live = document.createElement('span');
      live.id = 'repeatai-mobile-live';
      live.className = 'repeatai-mobile-live';
      live.textContent = MOBILE ? 'mobile pronto' : 'tempo real';
      caption.querySelector('span')?.replaceWith(live);
    }
  }

  function prepareFrame(view) {
    const frame = view.querySelector('#repeatai-frame');
    if (!frame || frame.dataset.mobileTrainingPrepared === '1') return;
    frame.dataset.mobileTrainingPrepared = '1';

    frame.addEventListener('load', () => {
      if (MOBILE && !frameUsesFallback(frame)) {
        forceCompiledMobile(frame);
        return;
      }
      enhanceFrame(view);
    });

    if (MOBILE) {
      const srcObserver = new MutationObserver(() => {
        if (!frame.getAttribute('src')) return;
        if (!frameUsesFallback(frame)) forceCompiledMobile(frame);
      });
      srcObserver.observe(frame, {attributes: true, attributeFilter: ['src']});
      frame._repeataiSrcObserver = srcObserver;
    }
  }

  function enhanceView(view) {
    if (!view) return;

    ensureHorn(view);
    prepareFrame(view);
    bridgeWizardMobile(view);
    replaceMouseInstruction(view);
    syncMobileKeyboard(view);

    if (view.dataset.mobileTrainingObserver !== '1') {
      view.dataset.mobileTrainingObserver = '1';
      const observer = new MutationObserver(() => {
        ensureHorn(view);
        replaceMouseInstruction(view);
        syncMobileKeyboard(view);
      });
      observer.observe(view, {childList: true, subtree: true, characterData: true});
    }
  }

  function scan() {
    enhanceView(document.getElementById('project-example-view'));
  }

  injectStyles();
  scan();

  const rootObserver = new MutationObserver(scan);
  rootObserver.observe(document.documentElement, {childList: true, subtree: true});
})();