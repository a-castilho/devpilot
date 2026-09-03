/* DevPilot game v90 — troca de contexto entre projetos sem interromper rodadas. */
(() => {
  'use strict';

  if (window.__devpilotGameProjectSwitchV90Ready) return;
  window.__devpilotGameProjectSwitchV90Ready = true;

  const STYLE_ID = 'devpilot-game-project-switch-v90-style';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const ACTIVE_SELECTOR = '[data-game90-project-switch]';
  const PROGRESS_SELECTOR = '#devpilot-game-stable-round-v84 .game74-progress-head, #devpilot-game-ui-v73 .game74-progress-head';
  let scheduled = false;

  const controller = () => window.__devpilotGameControllerV73;
  const projectRows = () => Array.isArray(window.__devpilotGameState?.projects)
    ? window.__devpilotGameState.projects
    : [];
  const currentState = () => controller()?.snapshot?.() || {};

  const installStyle = () => {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .game74-progress-head.game90-project-progress{align-items:end}
      .game90-project-switch{display:grid;min-width:0;flex:1;gap:6px;color:#d5e0eb;font-size:.76rem;font-weight:850}
      .game90-project-switch>span{color:#8fa5b9;font-size:.7rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase}
      .game90-project-switch select{width:100%;min-width:0;min-height:48px;padding:10px 12px;border:1px solid #294158;border-radius:13px;background:#061421;color:#f4f9ff;font:inherit;font-size:.9rem;outline:none}
      .game90-project-switch select:focus{border-color:#55f3e4;box-shadow:0 0 0 4px #55f3e41a}
      .game90-project-switch select:disabled{opacity:.65}
      .game90-project-progress-value{flex:0 0 auto;padding-bottom:12px;white-space:nowrap;color:#55f3e4}
      @media(max-width:520px){.game74-progress-head.game90-project-progress{align-items:stretch;flex-direction:column}.game90-project-progress-value{padding:0;text-align:right}}
    `;
    document.head.appendChild(style);
  };

  const waitForRender = timeoutMs => new Promise(resolve => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      document.removeEventListener('devpilot:game:rendered', finish);
      resolve();
    };
    const timer = window.setTimeout(finish, timeoutMs || 5000);
    document.addEventListener('devpilot:game:rendered', finish, {once:true});
  });

  const switchProject = async projectId => {
    const targetProject = String(projectId || '').trim();
    const state = currentState();
    if (!targetProject || targetProject === String(state.projectId || '')) return false;
    if (!projectRows().some(project => String(project.id) === targetProject)) {
      throw new Error('Projeto selecionado não encontrado');
    }

    const canonical = document.getElementById('build-game-project');
    if (canonical) {
      canonical.value = targetProject;
      const rendered = waitForRender(5000);
      canonical.dispatchEvent(new Event('change', {bubbles:true}));
      await rendered;
      return true;
    }

    // Fallback defensivo para um boot parcial: persiste somente o contexto e recarrega o jogo.
    // Nenhuma tarefa é cancelada, apagada ou reiniciada.
    localStorage.setItem(PROJECT_KEY, targetProject);
    localStorage.removeItem(MISSION_KEY);
    window.location.reload();
    return true;
  };

  const buildOption = (project, selectedProjectId) => {
    const option = document.createElement('option');
    option.value = String(project.id);
    option.textContent = String(project.name || `Projeto ${project.id}`);
    option.selected = String(project.id) === String(selectedProjectId || '');
    return option;
  };

  const mountOnProgressHead = (progressHead, state) => {
    if (!progressHead) return false;
    progressHead.classList.add('game90-project-progress');
    let label = progressHead.querySelector('.game90-project-switch');
    let select = progressHead.querySelector(ACTIVE_SELECTOR);
    if (!label || !select) {
      label = document.createElement('label');
      label.className = 'game90-project-switch';
      const caption = document.createElement('span');
      caption.textContent = 'Projeto';
      select = document.createElement('select');
      select.dataset.game90ProjectSwitch = '1';
      select.setAttribute('aria-label', 'Trocar projeto do Modo Jogo');
      label.append(caption, select);
      progressHead.firstElementChild?.replaceWith(label);
    }

    select.replaceChildren(...projectRows().map(project => buildOption(project, state.projectId)));
    const progress = progressHead.querySelector('strong');
    if (progress) progress.classList.add('game90-project-progress-value');

    select.onchange = async event => {
      const control = event.currentTarget;
      const previousProject = String(currentState().projectId || '');
      const targetProject = String(control.value || '');
      if (!targetProject || targetProject === previousProject) return;
      control.disabled = true;
      try {
        await switchProject(targetProject);
      } catch (error) {
        console.error('[DevPilot Game Project Switch]', error);
        control.value = previousProject;
        control.disabled = false;
      }
    };
    return true;
  };

  const mountActiveSelector = () => {
    installStyle();
    const state = currentState();
    if (!state.hasTasks) return false;
    const progressHeads = [...document.querySelectorAll(PROGRESS_SELECTOR)];
    if (!progressHeads.length) return false;
    return progressHeads.map(progressHead => mountOnProgressHead(progressHead, state)).some(Boolean);
  };

  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    window.setTimeout(() => {
      scheduled = false;
      mountActiveSelector();
    }, 0);
  };

  // A tela de nova rodada já possui seu próprio combo. Em captura, fazemos esse combo
  // também trocar o contexto do projeto para que seja possível voltar a uma rodada ativa.
  document.addEventListener('change', event => {
    const control = event.target?.closest?.('[data-game73-project]');
    if (!control) return;
    const targetProject = String(control.value || '');
    const state = currentState();
    if (!targetProject || targetProject === String(state.projectId || '')) return;
    void switchProject(targetProject).catch(error => console.error('[DevPilot Game Project Switch]', error));
  }, true);

  document.addEventListener('devpilot:game:state', schedule);
  document.addEventListener('devpilot:game:rendered', schedule);
  document.addEventListener('devpilot:game:error', schedule);
  window.__devpilotGameSwitchProjectV90 = switchProject;
  window.__devpilotGameMountProjectSwitchV90 = mountActiveSelector;
  schedule();
})();
