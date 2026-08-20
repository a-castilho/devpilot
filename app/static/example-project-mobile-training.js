(() => {
  const MOBILE = matchMedia('(max-width:760px)').matches || matchMedia('(pointer:coarse)').matches;
  const FALLBACK = '/examples/repeatai/index.html';
  let active = false, timer = 0, lastScroll = scrollY, rafMove = 0, rafScroll = 0, pendingMove = null, pendingDelta = 0;

  const view = () => document.getElementById('project-example-view');

  function frameDoc(frame) {
    try { return frame?.contentDocument || frame?.contentWindow?.document || null; }
    catch (_) { return null; }
  }

  function injectStyles() {
    if (document.getElementById('repeatai-mobile-training-styles')) return;
    const style = document.createElement('style');
    style.id = 'repeatai-mobile-training-styles';
    style.textContent = `
      #repeatai-wizard-start,#repeatai-train-horn{display:none!important}
      .repeatai-mobile-keyboard{width:min(560px,100%);margin-top:14px;border:1px solid #36506d;border-radius:12px;padding:13px 14px;background:#071320;color:#eef7ff;font:600 16px/1.3 system-ui,sans-serif;outline:none}
      .repeatai-mobile-keyboard:focus{border-color:#3be4d0}
      .example-project-caption .repeatai-mobile-live{display:inline-flex;align-items:center;gap:6px;color:#3be4d0;font-weight:800}
      .example-project-caption .repeatai-mobile-live:before{content:'';width:7px;height:7px;border-radius:50%;background:#3be4d0}
      @media(max-width:760px){.repeatai-wizard-title{font-size:clamp(25px,8vw,38px)!important}.repeatai-wizard-copy{font-size:14px!important;line-height:1.45}.example-project-stage{contain:layout paint style}.example-project-frame{min-height:620px!important}}
    `;
    document.head.appendChild(style);
  }

  function syncWizard(v) {
    if (!v) return;
    const title = v.querySelector('#repeatai-wizard-title');
    const copy = v.querySelector('#repeatai-wizard-copy');
    const kicker = v.querySelector('#repeatai-wizard-kicker');

    v.querySelector('#repeatai-train-horn')?.remove();

    if (title?.textContent.trim() === 'MOVA O MOUSE LOUCAMENTE') {
      title.textContent = 'MOVA O MOUSE E CLIQUE NA TELA LOUCAMENTE';
    }
    if (kicker?.textContent.trim() === 'MOUSE' && copy) {
      copy.textContent = MOBILE
        ? 'Arraste o dedo rapidamente e toque várias vezes. A captura é limitada para manter o celular fluido.'
        : 'Faça trajetórias rápidas e variadas e clique várias vezes nesta área.';
    }

    if (!MOBILE) return;
    const body = v.querySelector('.repeatai-wizard-body');
    const actions = v.querySelector('#repeatai-wizard-actions');
    let input = v.querySelector('#repeatai-mobile-keyboard');
    const keyboard = kicker?.textContent.trim() === 'TECLADO';

    if (!keyboard) { input?.remove(); return; }
    if (input || !body) return;

    input = document.createElement('input');
    input.id = 'repeatai-mobile-keyboard';
    input.className = 'repeatai-mobile-keyboard';
    input.type = 'text';
    input.autocomplete = 'off';
    input.spellcheck = false;
    input.placeholder = 'Toque aqui e digite para treinar';
    if (actions) body.insertBefore(input, actions); else body.appendChild(input);
    setTimeout(() => input.focus({preventScroll:true}), 60);
  }

  function mark(v, on) {
    active = on;
    const live = v?.querySelector('#repeatai-mobile-live');
    if (live) live.textContent = on ? 'treinando · modo leve' : 'mobile pronto';

    clearTimeout(timer);
    if (on) timer = setTimeout(() => stopCapture(v), 60000);
  }

  function enhanceFrame(v) {
    const frame = v?.querySelector('#repeatai-frame');
    const doc = frameDoc(frame);
    if (!frame || !doc?.body) return false;

    if (doc.documentElement.dataset.devpilotMobileTraining !== 'lite') {
      doc.documentElement.dataset.devpilotMobileTraining = 'lite';
      const style = doc.createElement('style');
      style.textContent = '@media(max-width:760px){.chart-line{filter:none!important}.chart-point{animation:none!important}.status.live .dot{box-shadow:none!important}.event-stream{max-height:180px}}';
      doc.head.appendChild(style);

      let last = 0;
      doc.addEventListener('pointermove', e => {
        if (e.pointerType === 'mouse') return;
        const now = performance.now();
        if (now - last < 80) return;
        last = now;
        doc.dispatchEvent(new MouseEvent('mousemove',{clientX:e.clientX,clientY:e.clientY,bubbles:true}));
      }, {passive:true});
    }

    if (frame.dataset.autoTrain === '1') {
      frame.dataset.autoTrain = '0';
      startCapture(v);
    }
    return true;
  }

  function startCapture(v) {
    const frame = v?.querySelector('#repeatai-frame');
    const doc = frameDoc(frame);
    if (!frame || !doc) { if (frame) frame.dataset.autoTrain = '1'; return false; }

    const duration = doc.getElementById('duration');
    const start = doc.getElementById('start');
    const stop = doc.getElementById('stop');
    if (duration && !duration.disabled) duration.value = '60';
    if (start && !start.disabled) start.click();
    mark(v, Boolean(stop && !stop.disabled));
    return active;
  }

  function stopCapture(v) {
    const doc = frameDoc(v?.querySelector('#repeatai-frame'));
    const stop = doc?.getElementById('stop');
    if (stop && !stop.disabled) stop.click();
    mark(v, false);
  }

  function forceFallback(frame) {
    if (!MOBILE || !frame) return false;
    const src = frame.getAttribute('src') || '';
    if (src.includes(FALLBACK) || frame.dataset.mobileFallbackForced === '1') return false;
    frame.dataset.mobileFallbackForced = '1';
    frame.src = `${FALLBACK}?mobile=1&t=${Date.now()}`;
    return true;
  }

  function ensureLiveStatus(v) {
    v?.querySelector('#repeatai-train-horn')?.remove();
    const caption = v?.querySelector('.example-project-caption');
    if (caption && !v.querySelector('#repeatai-mobile-live')) {
      const live = document.createElement('span');
      live.id = 'repeatai-mobile-live';
      live.className = 'repeatai-mobile-live';
      live.textContent = MOBILE ? 'mobile pronto' : 'tempo real';
      caption.querySelector('span')?.replaceWith(live);
    }
  }

  function autoStartTraining(v) {
    if (!v || !v.classList.contains('active') || v.dataset.autoTrainingStarted === '1') return;
    v.dataset.autoTrainingStarted = '1';

    const title = v.querySelector('#repeatai-wizard-title');
    if (title?.textContent.trim() === 'VAMOS CARREGAR A IA') {
      v.querySelector('#repeatai-wizard-actions button')?.click();
    }
    syncWizard(v);

    const frame = v.querySelector('#repeatai-frame');
    if (!frame) return;
    frame.dataset.autoTrain = '1';
    if (!forceFallback(frame) && enhanceFrame(v)) startCapture(v);
  }

  function bridge(v) {
    if (!MOBILE || v.dataset.mobileBridge === 'lite') return;
    v.dataset.mobileBridge = 'lite';

    addEventListener('pointermove', e => {
      if (!v.classList.contains('active') || e.pointerType === 'mouse') return;
      pendingMove = {x:e.clientX,y:e.clientY};
      if (rafMove) return;
      rafMove = requestAnimationFrame(() => {
        rafMove = 0;
        const p = pendingMove; pendingMove = null;
        if (p) dispatchEvent(new MouseEvent('mousemove',{clientX:p.x,clientY:p.y,bubbles:false}));
      });
    }, {passive:true});

    addEventListener('scroll', () => {
      const current = scrollY;
      if (!v.classList.contains('active')) { lastScroll = current; return; }
      pendingDelta += current - lastScroll;
      lastScroll = current;
      if (rafScroll) return;

      rafScroll = requestAnimationFrame(() => {
        rafScroll = 0;
        const delta = pendingDelta; pendingDelta = 0;
        if (!delta) return;
        dispatchEvent(new WheelEvent('wheel',{deltaY:delta,bubbles:false}));
        if (active) frameDoc(v.querySelector('#repeatai-frame'))?.dispatchEvent(new WheelEvent('wheel',{deltaY:delta,bubbles:true}));
      });
    }, {passive:true});
  }

  function prepare(v) {
    if (!v) return;
    ensureLiveStatus(v);
    syncWizard(v);
    bridge(v);

    const frame = v.querySelector('#repeatai-frame');
    if (frame && frame.dataset.mobileTrainingPrepared !== 'lite') {
      frame.dataset.mobileTrainingPrepared = 'lite';
      frame.addEventListener('load', () => {
        if (MOBILE && forceFallback(frame)) return;
        enhanceFrame(v);
      });
    }

    const kicker = v.querySelector('#repeatai-wizard-kicker');
    if (kicker && kicker.dataset.mobileStepObserved !== 'lite') {
      kicker.dataset.mobileStepObserved = 'lite';
      new MutationObserver(() => syncWizard(v)).observe(kicker,{childList:true,characterData:true,subtree:true});
    }

    autoStartTraining(v);
  }

  injectStyles();
  prepare(view());

  document.addEventListener('click', e => {
    if (!e.target.closest?.('[data-example-project="repeatai"]')) return;
    setTimeout(() => prepare(view()), 0);
  }, {passive:true});

  document.addEventListener('visibilitychange', () => {
    if (document.hidden && active) stopCapture(view());
  });
})();