(() => {
  const NAV_LABEL = 'Exemplo de projeto';
  const FALLBACK_URL = '/examples/repeatai/index.html';
  const WIZARD_TARGETS = {
    mouse: 1800,
    keyboard: 24,
    scroll: 3200,
  };


  function injectStyles() {
    if (document.getElementById('example-project-styles')) return;
    const style = document.createElement('style');
    style.id = 'example-project-styles';
    style.textContent = `
      #project-example-view{padding:0}
      .repeatai-wizard{
        margin-top:16px;
        border:1px solid var(--line);
        border-radius:16px;
        overflow:hidden;
        background:
          radial-gradient(circle at 85% -20%,rgba(59,228,208,.16),transparent 34%),
          linear-gradient(145deg,#101b2a,#0b141f);
        box-shadow:var(--shadow);
        outline:none
      }
      .repeatai-wizard:focus-visible{box-shadow:0 0 0 2px rgba(59,228,208,.35),var(--shadow)}
      .repeatai-wizard-head{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px 20px;border-bottom:1px solid var(--line)}
      .repeatai-wizard-brand{display:flex;align-items:center;gap:11px}
      .repeatai-wizard-mark{width:38px;height:38px;border-radius:11px;display:grid;place-items:center;background:linear-gradient(135deg,#3be4d0,#67a3ff);color:#06111c;font-weight:950;font-size:17px}
      .repeatai-wizard-brand strong{display:block;color:var(--text);font-size:15px}
      .repeatai-wizard-brand small{display:block;color:var(--muted);font-size:10px;margin-top:1px;letter-spacing:.08em}
      .repeatai-wizard-stepcount{color:var(--muted);font-size:11px;font-weight:800;white-space:nowrap}
      .repeatai-wizard-body{padding:26px 22px 24px;text-align:center;min-height:230px;display:grid;align-content:center;justify-items:center}
      .repeatai-wizard-kicker{margin:0 0 7px;color:#3be4d0;font-size:10px;font-weight:950;letter-spacing:.16em}
      .repeatai-wizard-title{margin:0;max-width:820px;color:var(--text);font-size:clamp(26px,4vw,44px);line-height:1.04;letter-spacing:-.035em}
      .repeatai-wizard-copy{margin:12px auto 0;max-width:680px;color:var(--muted);font-size:13px}
      .repeatai-wizard-progress{width:min(620px,100%);height:10px;margin-top:22px;border:1px solid #26394e;border-radius:999px;background:#08121e;overflow:hidden}
      .repeatai-wizard-progress > span{display:block;width:0;height:100%;border-radius:inherit;background:linear-gradient(90deg,#3be4d0,#67a3ff);transition:width .15s ease}
      .repeatai-wizard-meter{margin-top:9px;color:#b8c8da;font-size:11px;font-variant-numeric:tabular-nums}
      .repeatai-wizard-actions{display:flex;justify-content:center;gap:9px;margin-top:20px;flex-wrap:wrap}
      .repeatai-wizard-actions button{min-width:150px}
      .repeatai-wizard-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid var(--line);background:#09131f}
      .repeatai-wizard-chip{padding:11px 12px;border-right:1px solid var(--line);color:#687e96;font-size:10px;font-weight:850;text-align:center;text-transform:uppercase;letter-spacing:.04em}
      .repeatai-wizard-chip:last-child{border-right:0}
      .repeatai-wizard-chip.active{color:#dffef9;background:#102438}
      .repeatai-wizard-chip.done{color:#3be4d0;background:#0d201f}
      .example-project-caption{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:16px 2px 8px;color:var(--muted);font-size:11px}
      .example-project-caption strong{color:var(--text);font-size:13px}
      .example-project-stage{
        position:relative;
        min-height:calc(100vh - 150px);
        overflow:hidden;
        border:1px solid var(--line);
        border-radius:14px;
        background:#0b0f14;
        box-shadow:var(--shadow)
      }
      .example-project-frame{
        display:block;
        width:100%;
        height:calc(100vh - 150px);
        min-height:640px;
        border:0;
        background:#0b0f14
      }
      .example-project-loading{
        position:absolute;
        inset:0;
        z-index:1;
        display:grid;
        place-items:center;
        color:var(--muted);
        font-size:13px;
        background:#0b0f14
      }
      .example-project-loading[hidden]{display:none}
      @media(max-width:760px){
        .repeatai-wizard{margin-top:10px;border-radius:12px}
        .repeatai-wizard-head{padding:14px}
        .repeatai-wizard-body{padding:22px 14px;min-height:250px}
        .repeatai-wizard-steps{grid-template-columns:1fr 1fr}
        .repeatai-wizard-chip:nth-child(2){border-right:0}
        .repeatai-wizard-chip:nth-child(-n+2){border-bottom:1px solid var(--line)}
        .example-project-caption{margin-top:12px}
        .example-project-stage{min-height:calc(100vh - 132px);border-radius:10px}
        .example-project-frame{height:calc(100vh - 132px);min-height:620px}
      }
    `;
    document.head.appendChild(style);
  }

  function buildNav() {
    const navRoot = document.querySelector('.sidebar nav');
    if (!navRoot) return null;

    let button = navRoot.querySelector('[data-example-project="repeatai"]');
    if (button) return button;

    button = document.createElement('button');
    button.className = 'nav';
    button.type = 'button';
    button.dataset.exampleProject = 'repeatai';
    button.textContent = NAV_LABEL;

    const projects = navRoot.querySelector('.nav[data-view="projects"]');
    if (projects?.nextSibling) navRoot.insertBefore(button, projects.nextSibling);
    else navRoot.appendChild(button);
    return button;
  }

  function buildView() {
    let view = document.getElementById('project-example-view');
    if (view) return view;

    view = document.createElement('section');
    view.className = 'view';
    view.id = 'project-example-view';
    view.innerHTML = `
      <section class="repeatai-wizard" id="repeatai-wizard" tabindex="0" aria-live="polite">
        <div class="repeatai-wizard-head">
          <div class="repeatai-wizard-brand">
            <span class="repeatai-wizard-mark">R</span>
            <div><strong>RepetAI</strong><small>WIZARD DE CARREGAMENTO DA IA</small></div>
          </div>
          <span class="repeatai-wizard-stepcount" id="repeatai-wizard-stepcount">INÍCIO</span>
        </div>
        <div class="repeatai-wizard-body">
          <p class="repeatai-wizard-kicker" id="repeatai-wizard-kicker">TREINAMENTO RÁPIDO</p>
          <h2 class="repeatai-wizard-title" id="repeatai-wizard-title">VAMOS CARREGAR A IA</h2>
          <p class="repeatai-wizard-copy" id="repeatai-wizard-copy">Em poucos segundos o RepetAI coleta somente sinais de interação para preparar a análise.</p>
          <div class="repeatai-wizard-progress" aria-hidden="true"><span id="repeatai-wizard-progress"></span></div>
          <div class="repeatai-wizard-meter" id="repeatai-wizard-meter">pronto para começar</div>
          <div class="repeatai-wizard-actions" id="repeatai-wizard-actions">
            <button class="primary" type="button" id="repeatai-wizard-start">COMEÇAR</button>
          </div>
        </div>
        <div class="repeatai-wizard-steps">
          <div class="repeatai-wizard-chip active" data-wizard-chip="0">Carregar IA</div>
          <div class="repeatai-wizard-chip" data-wizard-chip="1">Mouse</div>
          <div class="repeatai-wizard-chip" data-wizard-chip="2">Teclado</div>
          <div class="repeatai-wizard-chip" data-wizard-chip="3">Scroll</div>
        </div>
      </section>

      <div class="example-project-caption">
        <strong>Gráficos e dados técnicos</strong>
        <span>atualização em tempo real</span>
      </div>
      <div class="example-project-stage" id="repeatai-stage">
        <div class="example-project-loading" id="repeatai-loading">Abrindo RepetAI…</div>
        <iframe
          class="example-project-frame"
          id="repeatai-frame"
          title="RepetAI — exemplo de projeto"
          referrerpolicy="no-referrer"
          hidden
        ></iframe>
      </div>`;

    document.querySelector('main')?.appendChild(view);
    setupWizard(view);
    return view;
  }

  function setupWizard(view) {
    const wizard = view.querySelector('#repeatai-wizard');
    if (!wizard || wizard.dataset.ready === '1') return;
    wizard.dataset.ready = '1';

    const state = {
      step: 0,
      mouseDistance: 0,
      lastMouse: null,
      keys: 0,
      scrollDistance: 0,
      complete: false,
      progressTimer: null,
      lastProgressPaintAt: 0,
      pendingProgress: null,
      pendingMeter: '',
    };

    const title = view.querySelector('#repeatai-wizard-title');
    const kicker = view.querySelector('#repeatai-wizard-kicker');
    const copy = view.querySelector('#repeatai-wizard-copy');
    const meter = view.querySelector('#repeatai-wizard-meter');
    const progress = view.querySelector('#repeatai-wizard-progress');
    const actions = view.querySelector('#repeatai-wizard-actions');
    const stepcount = view.querySelector('#repeatai-wizard-stepcount');
    const chips = [...view.querySelectorAll('[data-wizard-chip]')];

    function isActive() {
      return view.classList.contains('active') && !state.complete;
    }

    function setProgress(value) {
      const percent = Math.max(0, Math.min(100, value));
      progress.style.width = `${percent}%`;
    }

    function scheduleProgress(value, label) {
      state.pendingProgress = value;
      state.pendingMeter = label;
      if (state.progressTimer) return;

      const elapsed = performance.now() - state.lastProgressPaintAt;
      const delay = Math.max(0, 80 - elapsed);
      state.progressTimer = window.setTimeout(() => {
        state.progressTimer = null;
        state.lastProgressPaintAt = performance.now();
        setProgress(state.pendingProgress ?? 0);
        meter.textContent = state.pendingMeter;
      }, delay);
    }

    function paintChips() {
      chips.forEach((chip, index) => {
        chip.classList.toggle('done', index < state.step || state.complete);
        chip.classList.toggle('active', !state.complete && index === state.step);
      });
    }

    function focusWizard() {
      window.setTimeout(() => wizard.focus({preventScroll: true}), 30);
    }

    function renderStep() {
      if (state.progressTimer) {
        window.clearTimeout(state.progressTimer);
        state.progressTimer = null;
      }
      paintChips();
      actions.innerHTML = '';
      state.lastMouse = null;

      if (state.step === 0) {
        stepcount.textContent = 'INÍCIO';
        kicker.textContent = 'TREINAMENTO RÁPIDO';
        title.textContent = 'VAMOS CARREGAR A IA';
        copy.textContent = 'Em poucos segundos o RepetAI coleta somente sinais de interação para preparar a análise.';
        meter.textContent = 'pronto para começar';
        setProgress(0);
        const button = document.createElement('button');
        button.className = 'primary';
        button.type = 'button';
        button.textContent = 'COMEÇAR';
        button.addEventListener('click', () => {
          state.step = 1;
          renderStep();
        });
        actions.appendChild(button);
        return;
      }

      if (state.step === 1) {
        stepcount.textContent = 'PASSO 1 DE 3';
        kicker.textContent = 'MOUSE';
        title.textContent = 'MOVA O MOUSE LOUCAMENTE';
        copy.textContent = 'Faça trajetórias rápidas e variadas nesta área. Só distância e movimento são usados.';
        meter.textContent = '0% de movimento capturado';
        setProgress(0);
        focusWizard();
        return;
      }

      if (state.step === 2) {
        stepcount.textContent = 'PASSO 2 DE 3';
        kicker.textContent = 'TECLADO';
        title.textContent = 'DIGITE LOUCAMENTE';
        copy.textContent = 'Digite normalmente. O conteúdo das teclas não é armazenado; o wizard conta apenas eventos.';
        meter.textContent = `0 / ${WIZARD_TARGETS.keyboard} eventos de teclado`;
        setProgress(0);
        focusWizard();
        return;
      }

      stepcount.textContent = 'PASSO 3 DE 3';
      kicker.textContent = 'SCROLL';
      title.textContent = 'USE SCROLL LOUCAMENTE';
      copy.textContent = 'Role para cima e para baixo nesta página para completar a carga inicial.';
      meter.textContent = '0% de scroll capturado';
      setProgress(0);
      focusWizard();
    }

    function completeWizard() {
      state.complete = true;
      state.step = 4;
      paintChips();
      stepcount.textContent = 'CONCLUÍDO';
      kicker.textContent = 'REPETAI PRONTO';
      title.textContent = 'IA CARREGADA';
      copy.textContent = 'Treinamento inicial concluído. Os gráficos e dados técnicos continuam logo abaixo.';
      meter.textContent = '100% · mouse + teclado + scroll';
      setProgress(100);
      actions.innerHTML = '';
      const button = document.createElement('button');
      button.className = 'primary';
      button.type = 'button';
      button.textContent = 'VER GRÁFICOS';
      button.addEventListener('click', () => {
        view.querySelector('#repeatai-stage')?.scrollIntoView({behavior: 'smooth', block: 'start'});
      });
      actions.appendChild(button);
    }

    function onMouseMove(event) {
      if (!isActive() || state.step !== 1) return;
      const point = {x: event.clientX, y: event.clientY};
      if (state.lastMouse) {
        state.mouseDistance += Math.hypot(point.x - state.lastMouse.x, point.y - state.lastMouse.y);
      }
      state.lastMouse = point;
      const percent = Math.min(100, (state.mouseDistance / WIZARD_TARGETS.mouse) * 100);
      scheduleProgress(percent, `${Math.round(percent)}% de movimento capturado`);
      if (state.mouseDistance >= WIZARD_TARGETS.mouse) {
        state.step = 2;
        renderStep();
      }
    }

    function onPointerMove(event) {
      if (event.pointerType === 'mouse') return;
      onMouseMove(event);
    }

    function onKeyDown() {
      if (!isActive() || state.step !== 2) return;
      state.keys += 1;
      const percent = Math.min(100, (state.keys / WIZARD_TARGETS.keyboard) * 100);
      setProgress(percent);
      meter.textContent = `${Math.min(state.keys, WIZARD_TARGETS.keyboard)} / ${WIZARD_TARGETS.keyboard} eventos de teclado`;
      if (state.keys >= WIZARD_TARGETS.keyboard) {
        state.step = 3;
        renderStep();
      }
    }

    function onWheel(event) {
      if (!isActive() || state.step !== 3) return;
      state.scrollDistance += Math.abs(Number(event.deltaY) || 0);
      const percent = Math.min(100, (state.scrollDistance / WIZARD_TARGETS.scroll) * 100);
      scheduleProgress(percent, `${Math.round(percent)}% de scroll capturado`);
      if (state.scrollDistance >= WIZARD_TARGETS.scroll) completeWizard();
    }

    window.addEventListener('mousemove', onMouseMove, {passive: true});
    window.addEventListener('pointermove', onPointerMove, {passive: true});
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('wheel', onWheel, {passive: true});

    renderStep();
  }

  async function loadRepetAI(view, force = false) {
    const frame = view.querySelector('#repeatai-frame');
    const loading = view.querySelector('#repeatai-loading');
    if (!frame || frame.dataset.loading === '1') return;
    if (!force && frame.dataset.ready === '1') return;

    frame.dataset.loading = '1';
    frame.dataset.ready = '0';
    frame.hidden = true;
    loading.hidden = false;
    loading.textContent = 'Abrindo RepetAI…';

    // O exemplo integrado usa a versão compilada e amostrada. A versão local
    // completa pode ter gráficos próprios e não é carregada dentro deste frame.
    const target = FALLBACK_URL;

    const onLoad = () => {
      frame.hidden = false;
      frame.dataset.loading = '0';
      frame.dataset.ready = '1';
      frame.dataset.source = 'compilado';
      loading.hidden = true;
      frame.removeEventListener('load', onLoad);
    };

    frame.addEventListener('load', onLoad);
    frame.src = force ? `${target}${target.includes('?') ? '&' : '?'}t=${Date.now()}` : target;
  }

  function showExample(navButton) {
    const view = buildView();

    document.querySelectorAll('.view').forEach(item => {
      item.classList.toggle('active', item.id === 'project-example-view');
    });
    document.querySelectorAll('.nav').forEach(button => {
      button.classList.toggle('active', button === navButton);
    });

    const title = document.getElementById('page-title');
    if (title) title.textContent = 'Exemplo de projeto · RepetAI';

    loadRepetAI(view);
    view.querySelector('#repeatai-wizard')?.focus({preventScroll: true});
  }

  injectStyles();
  const navButton = buildNav();
  navButton?.addEventListener('click', () => showExample(navButton));
})();