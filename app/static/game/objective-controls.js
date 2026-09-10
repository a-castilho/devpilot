/* DevPilot game v74 — fluxo simples, contínuo e em uma única tela. */
(() => {
  'use strict';

  if (window.__devpilotGameUiV73Ready) return;
  window.__devpilotGameUiV73Ready = true;

  const ROOT_ID = 'devpilot-game-ui-v73';
  const STYLE_ID = 'devpilot-game-ui-v74-style';
  const DRAFT_PROJECT_KEY = 'devpilot-game-v74-project';
  const DRAFT_GOAL_KEY = 'devpilot-game-v74-goal';
  let scheduled = false;

  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const controller = () => window.__devpilotGameControllerV73;
  const projectRows = () => Array.isArray(window.__devpilotGameState?.projects)
    ? window.__devpilotGameState.projects
    : [];

  const installStyle = () => {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .devpilot-game-v73-shell>.build-game-hero,
      .devpilot-game-v73-shell>.build-game-round-contract,
      .devpilot-game-v73-shell>.build-game-score,
      .devpilot-game-v73-shell>.build-game-progress,
      .devpilot-game-v73-shell>.build-game-map,
      .devpilot-game-v73-shell>article.panel,
      .devpilot-game-v73-shell>.build-game-victory{display:none!important}
      .devpilot-game-v73-shell.show-details>.build-game-map,
      .devpilot-game-v73-shell.show-details>article.panel{display:grid!important}
      .game74{display:grid;gap:20px;padding:clamp(20px,4vw,38px);border:1px solid rgba(75,231,215,.3);border-radius:26px;background:radial-gradient(circle at 95% 0,rgba(66,200,255,.15),transparent 34%),linear-gradient(145deg,#0d2234,#071523);box-shadow:0 24px 70px #0005}
      .game74-kicker{color:#55f3e4;font-size:.72rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}
      .game74 h1{margin:3px 0;color:#fff;font-size:clamp(1.85rem,6vw,3rem);line-height:1.05;letter-spacing:-.035em}
      .game74 p{margin:0;color:#9eb0c2}.game74-goal{color:#fff!important;font-size:1.08rem;font-weight:850;overflow-wrap:anywhere}
      .game74-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:12px;border:1px solid #223d55;border-radius:16px;background:#06131f99}.game74-step{display:grid;place-items:center;gap:6px;color:#71879b;font-size:.72rem;font-weight:850}.game74-step b{display:grid;place-items:center;width:34px;height:34px;border-radius:999px;background:#132638;color:#b2c1cf}.game74-step.active{color:#55f3e4}.game74-step.active b{background:linear-gradient(135deg,#55f3e4,#45bcf5);color:#03131c}.game74-step.done{color:#95e8d7}.game74-step.done b{background:#143b3a;color:#55f3e4}
      .game74-fields{display:grid;grid-template-columns:minmax(210px,.75fr) minmax(300px,1.4fr);gap:14px}.game74 label{display:grid;gap:8px;color:#d5e0eb;font-size:.82rem;font-weight:850}
      .game74 select,.game74 textarea{width:100%;border:1px solid #294158;border-radius:15px;background:#061421;color:#f4f9ff;padding:14px;outline:none}.game74 select{min-height:56px}.game74 textarea{min-height:124px;resize:vertical}.game74 select:focus,.game74 textarea:focus{border-color:#55f3e4;box-shadow:0 0 0 4px #55f3e41a}
      .game74-suggestions{display:flex;flex-wrap:wrap;gap:8px}.game74-chip{min-height:38px;padding:8px 12px;border:1px solid #31516b;border-radius:999px;background:#0a1b2a;color:#cde0ef;font-weight:800;cursor:pointer}.game74-chip:hover,.game74-chip:focus{border-color:#55f3e4;color:#fff}
      .game74-primary{width:100%;min-height:64px;border:0;border-radius:17px;background:linear-gradient(135deg,#55f3e4,#45bcf5);color:#03131c;font-size:1.08rem;font-weight:950;cursor:pointer;touch-action:manipulation;box-shadow:0 16px 34px #25cfd229}.game74-primary:disabled{opacity:.52;cursor:not-allowed;box-shadow:none}
      .game74-help{text-align:center;color:#7f94a7!important;font-size:.82rem}.game74-status{padding:13px 15px;border-radius:14px;background:#0c2938;color:#a9bdce}.game74-status strong{color:#fff}.game74-error{border:1px solid #ff6577;color:#ffd9df;background:#3a1420}
      .game74-progress-head{display:flex;justify-content:space-between;gap:12px}.game74-progress-head strong{color:#55f3e4}.game74-progress{height:12px;overflow:hidden;border-radius:999px;background:#ffffff12}.game74-progress i{display:block;height:100%;background:linear-gradient(90deg,#55f3e4,#45bcf5);transition:width .35s ease}
      .game74-phase{display:grid;grid-template-columns:48px 1fr;gap:12px;align-items:center;padding:15px;border:1px solid #254258;border-radius:16px;background:#081c2b}.game74-icon{display:grid;place-items:center;width:46px;height:46px;border-radius:14px;background:#12374a;font-size:1.3rem}.game74-phase small{color:#55f3e4;font-weight:900}.game74-phase strong{display:block;color:#fff}.game74-phase p{font-size:.8rem}
      .game74-live{display:flex;align-items:center;gap:9px;color:#b8c9d8}.game74-live i{width:9px;height:9px;border-radius:999px;background:#55f3e4;box-shadow:0 0 0 5px #55f3e414;animation:game74pulse 1.5s infinite}@keyframes game74pulse{50%{opacity:.45;transform:scale(.8)}}
      .game74-actions{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px}.game74-secondary{min-height:48px;padding:10px 14px;border:1px solid #2b455e;border-radius:13px;background:#0b1d2e;color:#dce9f6;font-weight:850;cursor:pointer}.game74-secondary:disabled{opacity:.5;cursor:not-allowed}
      @media(max-width:720px){.game74{padding:20px 15px;border-radius:20px;gap:18px}.game74-fields{grid-template-columns:1fr}.game74-actions{grid-template-columns:1fr 1fr}.game74-actions .game74-primary{grid-column:1/-1}.game74-secondary{width:100%}.game74 h1{font-size:2rem}}
    `;
    document.head.appendChild(style);
  };

  const statusText = state => {
    if (state.done) return 'Rodada concluída e pronta para entrega.';
    if (state.failed) return state.verifier ? 'A verificação da etapa falhou.' : 'A execução da etapa falhou.';
    if (state.awaitingGate) return 'Execução concluída. Validando a entrega da etapa…';
    if (state.verifier && state.active) return 'Validando automaticamente a entrega…';
    if (state.active) {
      const map = {
        queued: 'Na fila de execução…',
        running: 'Executando automaticamente…',
        review: 'Revisando automaticamente…',
        awaiting_approval: 'Aguardando aprovação…',
        blocked: 'Execução bloqueada.'
      };
      return map[state.taskStatus] || 'Executando automaticamente…';
    }
    return 'Preparando a próxima etapa…';
  };

  const draftProject = state => localStorage.getItem(DRAFT_PROJECT_KEY) || state.projectId || '';
  const draftGoal = state => localStorage.getItem(DRAFT_GOAL_KEY) || state.goal || '';

  const mount = () => {
    const engine = controller();
    const view = document.getElementById('build-game-view');
    const shell = view?.querySelector('.build-game-shell');
    if (!engine || !view || !shell) return false;

    installStyle();
    shell.classList.add('devpilot-game-v73-shell');
    document.getElementById(ROOT_ID)?.remove();

    const host = document.createElement('section');
    host.id = ROOT_ID;
    shell.prepend(host);
    const state = engine.snapshot();

    if (!state.hasTasks) {
      const selectedDraftProject = draftProject(state);
      const selectedDraftGoal = draftGoal(state);
      const options = projectRows().map(project => `<option value="${esc(project.id)}" ${String(project.id) === String(selectedDraftProject) ? 'selected' : ''}>${esc(project.name)}</option>`).join('');
      host.innerHTML = `
        <section class="game74">
          <div><span class="game74-kicker">NOVA RODADA</span><h1>O que vamos entregar?</h1><p>Você só precisa escolher o projeto, dizer o resultado e tocar em Jogar agora.</p></div>
          <div class="game74-steps" aria-label="Fluxo da rodada"><span class="game74-step active"><b>1</b>Projeto</span><span class="game74-step"><b>2</b>Entrega</span><span class="game74-step"><b>3</b>Jogar</span></div>
          <div class="game74-fields">
            <label>1. Escolha o projeto<select data-game73-project>${options}</select></label>
            <label>2. Descreva sua entrega<textarea data-game73-goal maxlength="500" placeholder="Ex.: criar login e senha com perfil de usuário">${esc(selectedDraftGoal)}</textarea></label>
          </div>
          <div class="game74-suggestions" aria-label="Exemplos de entrega">
            <button class="game74-chip" type="button" data-game74-example="Criar tela de login e senha com perfil de usuário">Tela de login</button>
            <button class="game74-chip" type="button" data-game74-example="Criar cadastro completo de usuário com validações">Cadastro</button>
            <button class="game74-chip" type="button" data-game74-example="Criar dashboard responsivo com as informações principais do projeto">Dashboard</button>
          </div>
          <button class="game74-primary" type="button" data-game73-start>🚀 Jogar agora</button>
          <p class="game74-help">Depois do clique você fica nesta tela. O DevPilot planeja, implementa, testa e entrega automaticamente.</p>
          <div class="game74-status" data-game73-status><strong>Pronto para começar.</strong> Preencha a entrega da rodada.</div>
        </section>`;

      const project = host.querySelector('[data-game73-project]');
      const goal = host.querySelector('[data-game73-goal]');
      const button = host.querySelector('[data-game73-start]');
      const status = host.querySelector('[data-game73-status]');

      const syncStartState = () => {
        const valid = Boolean(project?.value && String(goal?.value || '').trim().length >= 3);
        button.disabled = !valid;
        status.classList.remove('game74-error');
        status.innerHTML = valid
          ? '<strong>Tudo pronto.</strong> Toque em Jogar agora para iniciar a rodada.'
          : '<strong>Falta só a entrega.</strong> Escreva em poucas palavras o que quer receber.';
      };

      project?.addEventListener('change', () => {
        localStorage.setItem(DRAFT_PROJECT_KEY, project.value || '');
        syncStartState();
      });
      goal?.addEventListener('input', () => {
        localStorage.setItem(DRAFT_GOAL_KEY, goal.value || '');
        syncStartState();
      });
      host.querySelectorAll('[data-game74-example]').forEach(chip => chip.addEventListener('click', () => {
        if (!goal) return;
        goal.value = chip.dataset.game74Example || '';
        localStorage.setItem(DRAFT_GOAL_KEY, goal.value);
        goal.focus();
        syncStartState();
      }));

      let startInFlight = false;
      let pointerStartedAt = 0;
      const startRoundFromUi = async event => {
        event?.preventDefault?.();
        if (startInFlight) return;
        const projectId = String(project?.value || '').trim();
        const targetGoal = String(goal?.value || '').trim();
        if (!projectId || targetGoal.length < 3) {
          syncStartState();
          goal?.focus();
          return;
        }
        startInFlight = true;
        button.disabled = true;
        button.textContent = '🚀 Iniciando rodada…';
        status.classList.remove('game74-error');
        status.innerHTML = '<strong>Rodada iniciada.</strong> Criando Planejamento na esteira real…';
        try {
          const liveEngine = controller();
          if (!liveEngine || typeof liveEngine.startRound !== 'function') throw new Error('Controlador do jogo ainda não está pronto');
          await liveEngine.startRound({projectId, goal: targetGoal});
          localStorage.removeItem(DRAFT_GOAL_KEY);
          localStorage.setItem(DRAFT_PROJECT_KEY, projectId);
          document.dispatchEvent(new CustomEvent('devpilot:game:rendered', {detail:{source:'game74-start'}}));
        } catch (error) {
          startInFlight = false;
          button.disabled = false;
          button.textContent = '🚀 Jogar agora';
          status.classList.add('game74-error');
          status.textContent = error?.message || 'Falha ao iniciar a rodada';
        }
      };
      button.addEventListener('pointerup', event => {
        if (event.pointerType && event.pointerType !== 'touch' && event.pointerType !== 'pen') return;
        pointerStartedAt = Date.now();
        void startRoundFromUi(event);
      });
      button.addEventListener('click', event => {
        if (Date.now() - pointerStartedAt < 900) {
          event.preventDefault();
          return;
        }
        void startRoundFromUi(event);
      });
      syncStartState();
      return true;
    }

    const step1Class = 'game74-step done';
    const step2Class = state.done ? 'game74-step done' : 'game74-step active';
    const step3Class = state.done ? 'game74-step active' : 'game74-step';
    host.innerHTML = `
      <section class="game74">
        <div><span class="game74-kicker">${state.done ? 'MISSÃO CUMPRIDA' : 'RODADA EM ANDAMENTO'}</span><h1>${state.done ? 'Entrega concluída' : 'Estamos construindo sua entrega'}</h1><p class="game74-goal">${esc(state.goal)}</p></div>
        <div class="game74-steps" aria-label="Fluxo da rodada"><span class="${step1Class}"><b>✓</b>Projeto</span><span class="${step2Class}"><b>${state.done ? '✓' : '2'}</b>Executar</span><span class="${step3Class}"><b>${state.done ? '3' : '3'}</b>Entregar</span></div>
        <div class="game74-progress-head"><span>${esc(state.projectName)}</span><strong>${state.completed}/${state.total} · ${state.percent}%</strong></div>
        <div class="game74-progress"><i style="width:${state.percent}%"></i></div>
        ${state.done ? `<div class="game74-status">🏆 <strong>Pronto.</strong> A entrega passou pelas sete etapas e pelos gates independentes.</div>` : `<section class="game74-phase"><div class="game74-icon">${esc(state.currentPhaseIcon)}</div><div><small>ETAPA ${state.currentPhaseId}/${state.total}</small><strong>${esc(state.currentPhaseName)}</strong><p>${esc(state.currentPhaseSummary)}</p></div></section><div class="game74-live"><i></i><span>${esc(statusText(state))}</span></div><div class="game74-status ${state.failed ? 'game74-error' : ''}">${esc(statusText(state))}</div>`}
        <div class="game74-actions">
          ${state.failed ? '<button class="game74-primary" type="button" data-game73-retry>↻ Corrigir e continuar</button>' : `<button class="game74-primary" type="button" disabled>${state.done ? '🏆 Entrega pronta' : '⚙ Trabalhando automaticamente'}</button>`}
          <button class="game74-secondary" type="button" data-game73-details>Ver detalhes</button>
          ${state.done ? '<button class="game74-secondary" type="button" data-game73-new>＋ Nova rodada</button>' : '<button class="game74-secondary" type="button" data-game73-refresh>↻ Atualizar agora</button>'}
        </div>
      </section>`;

    host.querySelector('[data-game73-refresh]')?.addEventListener('click', async event => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = 'Atualizando…';
      try { await engine.refresh(); }
      catch (error) { console.error('[DevPilot Game Refresh]', error); }
      finally { button.disabled = false; button.textContent = '↻ Atualizar agora'; }
    });

    host.querySelector('[data-game73-retry]')?.addEventListener('click', async event => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = 'Corrigindo…';
      try { await engine.retry(); }
      catch (error) {
        button.disabled = false;
        button.textContent = error?.message || '↻ Corrigir e continuar';
      }
    });

    host.querySelector('[data-game73-new]')?.addEventListener('click', () => void engine.reset());
    host.querySelector('[data-game73-details]')?.addEventListener('click', event => {
      const showing = shell.classList.toggle('show-details');
      event.currentTarget.textContent = showing ? 'Ocultar detalhes' : 'Ver detalhes';
    });
    return true;
  };

  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    window.setTimeout(() => {
      scheduled = false;
      mount();
    }, 0);
  };

  document.addEventListener('devpilot:game:state', schedule);
  document.addEventListener('devpilot:game:rendered', schedule);
  document.addEventListener('devpilot:game:error', schedule);
  schedule();
})();
