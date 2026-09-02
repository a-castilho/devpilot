/* DevPilot standalone game — simple one-click launcher.
 * The real Build Game runtime remains the source of truth. This module only
 * presents project + delivery + play as a clear first step.
 */
(() => {
  'use strict';

  if (window.__devpilotGameObjectiveControlsReady) return;
  window.__devpilotGameObjectiveControlsReady = true;

  const ROOT_ID = 'devpilot-game-quick-start';
  const STYLE_ID = 'devpilot-game-quick-start-style';
  let scheduled = false;

  const toastMessage = message => {
    if (typeof window.toast === 'function') return window.toast(message);
    const node = document.querySelector('#toast');
    if (!node) return;
    node.textContent = message;
    node.classList.add('show');
    window.setTimeout(() => node.classList.remove('show'), 2200);
  };

  const runAction = (key, action) => typeof window.__devpilotGameRunAction === 'function'
    ? window.__devpilotGameRunAction(key, action)
    : Promise.resolve().then(action);

  const ensureStyle = () => {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .build-game-shell.devpilot-simple-game>.build-game-hero{display:none}
      .devpilot-game-quick-start{position:relative;overflow:hidden;padding:clamp(20px,4vw,38px);border:1px solid rgba(76,226,214,.32);border-radius:28px;background:radial-gradient(circle at 88% 8%,rgba(38,220,208,.18),transparent 34%),linear-gradient(145deg,#0c2235,#091522 62%,#111935);box-shadow:0 24px 70px rgba(0,0,0,.28)}
      .devpilot-game-quick-start:after{content:'🚀';position:absolute;right:clamp(18px,5vw,54px);top:18px;font-size:clamp(4rem,11vw,8rem);opacity:.09;transform:rotate(9deg);pointer-events:none}
      .devpilot-game-kicker{display:inline-flex;align-items:center;gap:8px;color:#55f3e4;font-size:.72rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}
      .devpilot-game-kicker:before{content:'';width:8px;height:8px;border-radius:50%;background:#55f3e4;box-shadow:0 0 16px #55f3e4}
      .devpilot-game-quick-start h1{max-width:720px;margin:10px 0 8px;color:#fff;font-size:clamp(1.75rem,5vw,3rem);line-height:1.05;letter-spacing:-.035em}
      .devpilot-game-quick-start-intro{max-width:690px;margin:0 0 24px;color:#a9bbce;font-size:clamp(.92rem,2vw,1.05rem);line-height:1.55}
      .devpilot-game-quick-fields{display:grid;grid-template-columns:minmax(210px,.8fr) minmax(320px,1.6fr);gap:16px;align-items:start}
      .devpilot-game-quick-field{display:grid;gap:8px;color:#c9d7e5;font-size:.82rem;font-weight:800}
      .devpilot-game-step{display:inline-grid;place-items:center;width:25px;height:25px;margin-right:7px;border:1px solid rgba(85,243,228,.35);border-radius:8px;background:rgba(85,243,228,.1);color:#55f3e4;font-size:.72rem}
      .devpilot-game-quick-field select,.devpilot-game-quick-field textarea{box-sizing:border-box;width:100%;border:1px solid rgba(131,164,193,.32);border-radius:15px;background:rgba(3,12,23,.76);color:#f5fbff;font:inherit;font-weight:650;outline:none}
      .devpilot-game-quick-field select{min-height:56px;padding:0 15px}
      .devpilot-game-quick-field textarea{min-height:112px;padding:15px;resize:vertical;line-height:1.45}
      .devpilot-game-quick-field select:focus,.devpilot-game-quick-field textarea:focus{border-color:#55f3e4;box-shadow:0 0 0 4px rgba(85,243,228,.1)}
      .devpilot-game-quick-field textarea[readonly]{opacity:.82;cursor:default}
      .devpilot-game-play{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;min-height:62px;margin-top:18px;border:0;border-radius:16px;background:linear-gradient(135deg,#55f3e4,#43baf4);color:#03121c;font:inherit;font-size:1.05rem;font-weight:950;cursor:pointer;box-shadow:0 14px 32px rgba(67,186,244,.2);touch-action:manipulation}
      .devpilot-game-play:hover{filter:brightness(1.06);transform:translateY(-1px)}
      .devpilot-game-play:disabled{opacity:.62;cursor:wait;transform:none}
      .devpilot-game-quick-note{display:block;margin-top:11px;color:#7f96aa;font-size:.75rem;text-align:center}
      .devpilot-game-running-actions{display:flex;flex-wrap:wrap;gap:9px;margin-top:18px}
      .devpilot-game-running-actions button{min-height:44px;padding:9px 14px;border:1px solid rgba(113,153,186,.35);border-radius:12px;background:rgba(8,25,41,.74);color:#dcecff;font:inherit;font-weight:800;cursor:pointer}
      .devpilot-simple-game:not(.devpilot-game-started)>.build-game-round-contract,.devpilot-simple-game:not(.devpilot-game-started)>.build-game-score,.devpilot-simple-game:not(.devpilot-game-started)>.build-game-progress,.devpilot-simple-game:not(.devpilot-game-started)>.build-game-map,.devpilot-simple-game:not(.devpilot-game-started)>article.panel{display:none!important}
      .devpilot-simple-game.devpilot-game-started:not(.devpilot-game-details)>.build-game-round-contract,.devpilot-simple-game.devpilot-game-started:not(.devpilot-game-details)>article.panel{display:none!important}
      .devpilot-simple-game.devpilot-game-started:not(.devpilot-game-details) .build-game-phase:not(.current){display:none!important}
      .devpilot-simple-game.devpilot-game-started .devpilot-game-quick-fields{grid-template-columns:minmax(210px,.7fr) minmax(320px,1.3fr)}
      @media(max-width:720px){
        .devpilot-game-quick-start{padding:20px 16px;border-radius:20px}
        .devpilot-game-quick-start:after{font-size:5rem;right:10px}
        .devpilot-game-quick-fields,.devpilot-simple-game.devpilot-game-started .devpilot-game-quick-fields{grid-template-columns:1fr}
        .devpilot-game-quick-field textarea{min-height:104px}
        .devpilot-game-play{min-height:60px}
      }
    `;
    document.head.appendChild(style);
  };

  const runtimeGoal = view => view?.querySelector('#build-game-goal');
  const runtimeProject = view => view?.querySelector('#build-game-project');
  const currentPhaseButton = view => view?.querySelector('.build-game-phase.current [data-play-phase]:not([disabled])')
    || view?.querySelector('[data-play-phase]:not([disabled])');

  const persistGoal = (view, textarea) => {
    const input = runtimeGoal(view);
    const value = String(textarea?.value || '').trim();
    if (!value) {
      textarea?.focus();
      toastMessage('Conte em uma frase o que você quer receber nesta rodada');
      return false;
    }
    if (!input) {
      toastMessage('A entrega ainda está carregando. Tente novamente.');
      return false;
    }
    input.value = value;
    input.dispatchEvent(new Event('input', {bubbles:true}));
    input.dispatchEvent(new Event('change', {bubbles:true}));
    return true;
  };

  const startGame = async (view, textarea, trigger) => {
    if (!runtimeProject(view)?.value) {
      toastMessage('Escolha um projeto para jogar');
      return false;
    }
    if (!persistGoal(view, textarea)) return false;
    const phaseButton = currentPhaseButton(view);
    if (!phaseButton) {
      toastMessage('A rodada ainda está preparando a primeira etapa');
      return false;
    }
    trigger.disabled = true;
    trigger.textContent = 'Preparando sua rodada…';
    phaseButton.click();
    window.setTimeout(() => {
      if (!trigger.isConnected) return;
      trigger.disabled = false;
      trigger.textContent = '🚀 Criar e jogar';
    }, 1800);
    return true;
  };

  const mount = () => {
    const view = document.querySelector('#build-game-view');
    const shell = view?.querySelector('.build-game-shell');
    const baseProject = runtimeProject(view);
    const baseGoal = runtimeGoal(view);
    if (!view || !shell || !baseProject || !baseGoal) return false;

    const started = baseGoal.readOnly || baseGoal.dataset.roundGoalLocked === 'true';
    shell.classList.add('devpilot-simple-game');
    shell.classList.toggle('devpilot-game-started', started);

    document.getElementById(ROOT_ID)?.remove();
    ensureStyle();

    const host = document.createElement('section');
    host.id = ROOT_ID;
    host.className = 'devpilot-game-quick-start';
    host.setAttribute('aria-label', started ? 'Rodada em andamento' : 'Começar nova rodada');
    host.innerHTML = `
      <span class="devpilot-game-kicker">${started ? 'RODADA EM ANDAMENTO' : 'NOVO JOGO'}</span>
      <h1>${started ? 'Sua entrega está sendo construída' : 'O que vamos construir hoje?'}</h1>
      <p class="devpilot-game-quick-start-intro">${started
        ? 'Acompanhe a etapa atual. O DevPilot cuida da esteira técnica por você.'
        : 'Escolha o projeto, descreva a entrega e comece. É só isso.'}</p>
      <div class="devpilot-game-quick-fields">
        <label class="devpilot-game-quick-field"><span><b class="devpilot-game-step">1</b>Escolha o projeto</span>
          <select id="devpilot-game-project">${baseProject.innerHTML}</select>
        </label>
        <label class="devpilot-game-quick-field"><span><b class="devpilot-game-step">2</b>Entrega da rodada</span>
          <textarea id="devpilot-game-delivery" maxlength="500" ${started ? 'readonly aria-readonly="true"' : ''}
            placeholder="Ex.: criar uma tela de login simples para cliente e administrador">${String(baseGoal.value || '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')}</textarea>
        </label>
      </div>
      ${started ? `
        <div class="devpilot-game-running-actions">
          <button type="button" data-simple-refresh>↻ Atualizar progresso</button>
          <button type="button" data-simple-new>＋ Nova rodada</button>
          <button type="button" data-simple-details>Ver detalhes</button>
        </div>
      ` : `
        <button class="devpilot-game-play" type="button" data-simple-play>🚀 Criar e jogar</button>
        <small class="devpilot-game-quick-note">O jogo começa pelo planejamento e segue sozinho, etapa por etapa.</small>
      `}
    `;

    shell.prepend(host);

    const project = host.querySelector('#devpilot-game-project');
    project.value = baseProject.value;
    project.addEventListener('change', () => {
      baseProject.value = project.value;
      baseProject.dispatchEvent(new Event('change', {bubbles:true}));
    });

    const delivery = host.querySelector('#devpilot-game-delivery');
    host.querySelector('[data-simple-play]')?.addEventListener('click', event => {
      void runAction('simple-game-start', () => startGame(view, delivery, event.currentTarget));
    });
    host.querySelector('[data-simple-refresh]')?.addEventListener('click', () => {
      void runAction('simple-game-refresh', () => window.loadBuildGame?.());
    });
    host.querySelector('[data-simple-new]')?.addEventListener('click', () => {
      view.querySelector('#build-game-new')?.click();
    });
    host.querySelector('[data-simple-details]')?.addEventListener('click', event => {
      const showing = shell.classList.toggle('devpilot-game-details');
      event.currentTarget.textContent = showing ? 'Ocultar detalhes' : 'Ver detalhes';
    });
    return true;
  };

  const scheduleMount = () => {
    if (scheduled) return;
    scheduled = true;
    window.setTimeout(() => {
      scheduled = false;
      mount();
    }, 0);
  };

  document.addEventListener('devpilot:game:rendered', scheduleMount);
  scheduleMount();
})();