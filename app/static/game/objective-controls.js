/* DevPilot standalone game objective controls.
 * Keeps the objective visible in the isolated game skin and delegates all
 * state transitions to the existing Build Game runtime.
 */
(() => {
  'use strict';

  if (window.__devpilotGameObjectiveControlsReady) return;
  window.__devpilotGameObjectiveControlsReady = true;

  const ROOT_ID = 'devpilot-game-objective-controls';
  const STYLE_ID = 'devpilot-game-objective-controls-style';

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
    if (!input || document.activeElement === textarea) return;
    const value = String(input.value || '');
    if (textarea.value !== value) textarea.value = value;
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
    input.value = value;
    input.dispatchEvent(new Event('input', {bubbles: true}));
    input.dispatchEvent(new Event('change', {bubbles: true}));
    const status = document.querySelector('[data-objective-status]');
    if (status) status.textContent = 'SALVO';
    toastMessage('Objetivo salvo');
    return true;
  };

  const currentPhaseButton = view => view.querySelector('.build-game-phase.current [data-play-phase]')
    || view.querySelector('[data-play-phase]:not([disabled])');

  const startCurrentPhase = (view, textarea) => {
    if (!persistGoal(view, textarea)) return;
    const button = currentPhaseButton(view);
    if (button) {
      button.click();
      return;
    }
    const active = view.querySelector('.build-game-phase.current .build-game-phase-actions button');
    if (active) {
      active.scrollIntoView({behavior: 'smooth', block: 'center'});
      toastMessage('A fase atual já está em andamento');
      return;
    }
    toastMessage('Nenhuma fase disponível para iniciar agora');
  };

  const mount = () => {
    const view = document.querySelector('#build-game-view');
    const shell = view?.querySelector('.build-game-shell');
    if (!view || !shell || document.getElementById(ROOT_ID)) return false;

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
    if (textarea.value.trim()) host.querySelector('[data-objective-status]').textContent = 'SALVO';

    textarea.addEventListener('input', () => {
      host.querySelector('[data-objective-status]').textContent = 'ALTERADO';
    });
    host.querySelector('[data-objective-save]').addEventListener('click', () => persistGoal(view, textarea));
    host.querySelector('[data-objective-start]').addEventListener('click', () => startCurrentPhase(view, textarea));
    host.querySelector('[data-objective-new]').addEventListener('click', () => {
      const button = view.querySelector('#build-game-new');
      if (!button) return toastMessage('Ação Nova partida indisponível');
      button.click();
    });
    host.querySelector('[data-objective-refresh]').addEventListener('click', async () => {
      if (typeof window.loadBuildGame !== 'function') return window.location.reload();
      await window.loadBuildGame();
    });

    const runtimeInput = baseGoal(view);
    runtimeInput?.addEventListener('input', () => syncFromRuntime(view, textarea));
    return true;
  };

  const observer = new MutationObserver(() => {
    if (mount()) return;
    const view = document.querySelector('#build-game-view');
    const host = document.getElementById(ROOT_ID);
    const textarea = host?.querySelector('#devpilot-game-objective');
    if (view && textarea) syncFromRuntime(view, textarea);
  });

  observer.observe(document.documentElement, {childList: true, subtree: true});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once: true});
  else mount();
})();
