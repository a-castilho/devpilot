/* DevPilot standalone game objective controls.
 * Keeps the objective visible in the isolated game skin and delegates all
 * state transitions to the existing Build Game runtime. No DOM observer is
 * used: mounting follows explicit game render events from action-runtime.js.
 */
(() => {
  'use strict';

  if (window.__devpilotGameObjectiveControlsReady) return;
  window.__devpilotGameObjectiveControlsReady = true;

  const ROOT_ID = 'devpilot-game-objective-controls';
  const STYLE_ID = 'devpilot-game-objective-controls-style';
  let scheduled = false;

  const toastMessage = message => {
    if (typeof window.toast === 'function') window.toast(message);
    else {
      const node = document.querySelector('#toast');
      if (!node) return;
      node.textContent = message;
      node.classList.add('show');
      window.setTimeout(() => node.classList.remove('show'), 2200);
    }
  };

  const runAction = (key, action) => typeof window.__devpilotGameRunAction === 'function'
    ? window.__devpilotGameRunAction(key, action)
    : Promise.resolve().then(action);

  const ensureStyle = () => {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .devpilot-game-objective{margin:0 0 18px;padding:18px 20px;border:1px solid rgba(108,92,255,.52);border-radius:20px;background:linear-gradient(135deg,rgba(12,18,52,.96),rgba(52,0,85,.92));box-shadow:0 18px 48px rgba(23,0,75,.16)}
      .devpilot-game-objective-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:12px}
      .devpilot-game-objective-head span{display:block;color:#6ea8ff;font-size:.68rem;font-weight:900;letter-spacing:.14em;text-transform:uppercase}
      .devpilot-game-objective-head strong{display:block;margin-top:4px;font-size:1.08rem;color:#fff}
      .devpilot-game-objective-status{min-width:80px;text-align:right;color:#9ea8c5;font-size:.72rem}
      .devpilot-game-objective textarea{display:block;width:100%;min-height:96px;resize:vertical;padding:13px 14px;border:1px solid rgba(122,112,255,.56);border-radius:14px;background:rgba(4,9,28,.74);color:#fff;font:inherit;line-height:1.45;outline:none;box-sizing:border-box}
      .devpilot-game-objective textarea:focus{border-color:#00e7d8;box-shadow:0 0 0 3px rgba(0,231,216,.10)}
      .devpilot-game-objective-actions{display:grid;grid-template-columns:minmax(180px,1.15fr) minmax(150px,.9fr) minmax(130px,.75fr) minmax(110px,.6fr);gap:10px;margin-top:12px}
      .devpilot-game-objective-actions button{min-height:44px;border-radius:12px;font-weight:800;cursor:pointer}
      .devpilot-game-objective-actions button:disabled{opacity:.58;cursor:wait}
      .devpilot-game-objective-actions .objective-primary{border:1px solid #15e7d0;background:linear-gradient(135deg,#00d9c7,#35f0cf);color:#041018}
      .devpilot-game-objective-actions .objective-secondary{border:1px solid rgba(117,91,255,.74);background:rgba(46,20,116,.75);color:#fff}
      .devpilot-game-objective-actions .objective-ghost{border:1px solid rgba(117,91,255,.48);background:rgba(8,14,40,.62);color:#dce4ff}
      .devpilot-game-objective-help{margin:9px 2px 0;color:#9ea8c5;font-size:.72rem}
      @media(max-width:760px){.devpilot-game-objective{padding:15px}.devpilot-game-objective-head{display:block}.devpilot-game-objective-status{text-align:left;margin-top:6px}.devpilot-game-objective-actions{grid-template-columns:1fr 1fr}.devpilot-game-objective-actions button:first-child{grid-column:1/-1}}
      @media(max-width:460px){.devpilot-game-objective-actions{grid-template-columns:1fr}.devpilot-game-objective-actions button:first-child{grid-column:auto}}
    `;
    document.head.appendChild(style);
  };

  const baseGoal = view => view?.querySelector('#build-game-goal');

  const syncFromRuntime = (view, textarea) => {
    const input = baseGoal(view);
    if (!input || !textarea || document.activeElement === textarea) return;
    const value = String(input.value || '');
    if (textarea.value !== value) textarea.value = value;
    const status = document.querySelector('[data-objective-status]');
    if (status && value.trim()) status.textContent = 'SALVO';
  };

  const persistGoal = (view, textarea) => {
    const input = baseGoal(view);
    const value = String(textarea.value || '').trim();
    if (!value) {
      textarea.focus();
      toastMessage('Defina o objetivo da partida antes de continuar');
      return false;
    }
    if (!input) {
      toastMessage('Campo base do objetivo ainda está carregando');
      return false;
    }
    if (input.value !== value) input.value = value;
    input.dispatchEvent(new Event('input', {bubbles:true}));
    input.dispatchEvent(new Event('change', {bubbles:true}));
    const status = document.querySelector('[data-objective-status]');
    if (status) status.textContent = 'SALVO';
    toastMessage('Objetivo salvo');
    return true;
  };

  const currentPhaseButton = view => view.querySelector('.build-game-phase.current [data-play-phase]')
    || view.querySelector('[data-play-phase]:not([disabled])');

  const startCurrentPhase = async (view, textarea, trigger) => {
    if (!persistGoal(view, textarea)) return false;
    const button = currentPhaseButton(view);
    if (button) {
      trigger.disabled = true;
      button.scrollIntoView({block:'center'});
      button.click();
      window.setTimeout(() => {
        if (trigger.isConnected) trigger.disabled = false;
      }, 1200);
      return true;
    }
    const active = view.querySelector('.build-game-phase.current .build-game-phase-actions button');
    if (active) {
      active.scrollIntoView({block:'center'});
      toastMessage('A fase atual já está em andamento');
      return false;
    }
    toastMessage('Nenhuma fase disponível para iniciar agora');
    return false;
  };

  const mount = () => {
    const view = document.querySelector('#build-game-view');
    const shell = view?.querySelector('.build-game-shell');
    if (!view || !shell) return false;

    const existing = document.getElementById(ROOT_ID);
    if (existing) {
      syncFromRuntime(view, existing.querySelector('#devpilot-game-objective'));
      return true;
    }

    ensureStyle();
    const host = document.createElement('section');
    host.id = ROOT_ID;
    host.className = 'devpilot-game-objective';
    host.setAttribute('aria-label', 'Objetivo e ações da partida');
    host.innerHTML = `
      <div class="devpilot-game-objective-head">
        <div><span>OBJETIVO DA PARTIDA</span><strong>O que esta rodada precisa entregar?</strong></div>
        <div class="devpilot-game-objective-status" data-objective-status>NÃO SALVO</div>
      </div>
      <textarea id="devpilot-game-objective" maxlength="500" placeholder="Ex.: criar login e senha com perfis de usuário, testes e fluxo mobile funcional"></textarea>
      <div class="devpilot-game-objective-actions">
        <button class="objective-primary" type="button" data-objective-start>Salvar e iniciar fase</button>
        <button class="objective-secondary" type="button" data-objective-save>Salvar objetivo</button>
        <button class="objective-ghost" type="button" data-objective-new>Nova partida</button>
        <button class="objective-ghost" type="button" data-objective-refresh>Atualizar</button>
      </div>
      <p class="devpilot-game-objective-help">O objetivo fica vinculado ao projeto e à partida atual e é enviado para a tarefa real de cada fase.</p>
    `;

    const phaseMap = shell.querySelector('.build-game-map');
    const score = shell.querySelector('.build-game-score');
    if (phaseMap) shell.insertBefore(host, phaseMap);
    else if (score?.nextSibling) shell.insertBefore(host, score.nextSibling);
    else shell.prepend(host);

    const textarea = host.querySelector('#devpilot-game-objective');
    syncFromRuntime(view, textarea);

    textarea.addEventListener('input', () => {
      host.querySelector('[data-objective-status]').textContent = 'ALTERADO';
    });

    const saveButton = host.querySelector('[data-objective-save]');
    saveButton.addEventListener('click', () => {
      void runAction('objective-save', async () => persistGoal(view, textarea));
    });

    const startButton = host.querySelector('[data-objective-start]');
    startButton.addEventListener('click', () => {
      void runAction('objective-start', () => startCurrentPhase(view, textarea, startButton));
    });

    const newButton = host.querySelector('[data-objective-new]');
    newButton.addEventListener('click', () => {
      void runAction('objective-new', async () => {
        const button = view.querySelector('#build-game-new');
        if (!button) return toastMessage('Ação Nova partida indisponível');
        newButton.disabled = true;
        button.click();
        window.setTimeout(() => {
          if (newButton.isConnected) newButton.disabled = false;
        }, 900);
      });
    });

    const refreshButton = host.querySelector('[data-objective-refresh]');
    refreshButton.addEventListener('click', () => {
      void runAction('game-refresh', async () => {
        if (typeof window.loadBuildGame !== 'function') return window.location.reload();
        refreshButton.disabled = true;
        try {
          await window.loadBuildGame();
        } finally {
          if (refreshButton.isConnected) refreshButton.disabled = false;
        }
      });
    });

    const runtimeInput = baseGoal(view);
    runtimeInput?.addEventListener('input', () => syncFromRuntime(view, textarea));
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
  document.addEventListener('devpilot:game:core-ready', scheduleMount);
  document.addEventListener('devpilot:game:standalone-ready', scheduleMount);
  document.addEventListener('devpilot:game:enhancements-ready', scheduleMount);
  scheduleMount();
})();
