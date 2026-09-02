/* DevPilot game v73 — simple UI bound directly to the real game controller. */
(() => {
  'use strict';

  if (window.__devpilotGameUiV73Ready) return;
  window.__devpilotGameUiV73Ready = true;

  const ROOT_ID = 'devpilot-game-ui-v73';
  const STYLE_ID = 'devpilot-game-ui-v73-style';
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
      .game73{display:grid;gap:18px;padding:clamp(20px,4vw,38px);border:1px solid rgba(75,231,215,.3);border-radius:26px;background:radial-gradient(circle at 95% 0,rgba(66,200,255,.15),transparent 34%),linear-gradient(145deg,#0d2234,#071523);box-shadow:0 24px 70px #0005}
      .game73-kicker{color:#55f3e4;font-size:.72rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}
      .game73 h1{margin:3px 0;color:#fff;font-size:clamp(1.8rem,6vw,3rem);line-height:1.05;letter-spacing:-.035em}
      .game73 p{margin:0;color:#9eb0c2}.game73-goal{color:#fff!important;font-size:1.08rem;font-weight:850;overflow-wrap:anywhere}
      .game73-fields{display:grid;grid-template-columns:minmax(210px,.75fr) minmax(300px,1.4fr);gap:14px}.game73 label{display:grid;gap:8px;color:#d5e0eb;font-size:.8rem;font-weight:850}
      .game73 select,.game73 textarea{width:100%;border:1px solid #294158;border-radius:15px;background:#061421;color:#f4f9ff;padding:14px;outline:none}.game73 select{min-height:56px}.game73 textarea{min-height:110px;resize:vertical}.game73 select:focus,.game73 textarea:focus{border-color:#55f3e4;box-shadow:0 0 0 4px #55f3e41a}
      .game73-primary{width:100%;min-height:64px;border:0;border-radius:17px;background:linear-gradient(135deg,#55f3e4,#45bcf5);color:#03131c;font-size:1.05rem;font-weight:950;cursor:pointer;touch-action:manipulation}.game73-primary:disabled{opacity:.65;cursor:wait}
      .game73-status{padding:13px 15px;border-radius:14px;background:#0c2938;color:#a9bdce}.game73-error{border:1px solid #ff6577;color:#ffd9df;background:#3a1420}
      .game73-progress-head{display:flex;justify-content:space-between;gap:12px}.game73-progress-head strong{color:#55f3e4}.game73-progress{height:12px;overflow:hidden;border-radius:999px;background:#ffffff12}.game73-progress i{display:block;height:100%;background:linear-gradient(90deg,#55f3e4,#45bcf5)}
      .game73-phase{display:grid;grid-template-columns:48px 1fr;gap:12px;align-items:center;padding:15px;border:1px solid #254258;border-radius:16px;background:#081c2b}.game73-icon{display:grid;place-items:center;width:46px;height:46px;border-radius:14px;background:#12374a;font-size:1.3rem}.game73-phase small{color:#55f3e4;font-weight:900}.game73-phase strong{display:block;color:#fff}.game73-phase p{font-size:.8rem}
      .game73-actions{display:grid;grid-template-columns:minmax(0,1fr) auto auto auto;gap:8px}.game73-secondary{min-height:48px;padding:10px 14px;border:1px solid #2b455e;border-radius:13px;background:#0b1d2e;color:#dce9f6;font-weight:850;cursor:pointer}
      @media(max-width:720px){.game73{padding:20px 15px;border-radius:20px}.game73-fields{grid-template-columns:1fr}.game73-actions{grid-template-columns:1fr 1fr}.game73-actions .game73-primary{grid-column:1/-1}.game73-secondary{width:100%}}
    `;
    document.head.appendChild(style);
  };

  const statusText = state => {
    if (state.done) return 'Rodada concluída';
    if (state.failed) return state.verifier ? 'A verificação da etapa falhou' : 'A execução da etapa falhou';
    if (state.awaitingGate) return 'Execução concluída. Validando a entrega da etapa…';
    if (state.verifier && state.active) return 'Gate independente validando a entrega…';
    if (state.active) {
      const map = {
        queued: 'Na fila de execução',
        running: 'Executando automaticamente',
        review: 'Em revisão',
        awaiting_approval: 'Aguardando aprovação',
        blocked: 'Execução bloqueada'
      };
      return map[state.taskStatus] || 'Executando automaticamente';
    }
    return 'Preparando a próxima etapa…';
  };

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
      const options = projectRows().map(project => `<option value="${esc(project.id)}" ${String(project.id) === String(state.projectId) ? 'selected' : ''}>${esc(project.name)}</option>`).join('');
      host.innerHTML = `
        <section class="game73">
          <div><span class="game73-kicker">NOVA RODADA</span><h1>O que vamos entregar?</h1><p>Escolha o projeto, descreva o resultado e toque uma única vez em Jogar agora.</p></div>
          <div class="game73-fields">
            <label>Projeto<select data-game73-project>${options}</select></label>
            <label>Entrega da rodada<textarea data-game73-goal maxlength="500" placeholder="Ex.: criar login com usuário e perfil">${esc(state.goal)}</textarea></label>
          </div>
          <button class="game73-primary" type="button" data-game73-start>🚀 Jogar agora</button>
          <div class="game73-status" data-game73-status>Depois do clique, Planejamento, Implementação, Execução, Testes, Documentação, Git e Entrega seguem pela esteira real.</div>
        </section>`;

      const button = host.querySelector('[data-game73-start]');
      const status = host.querySelector('[data-game73-status]');
      button.onclick = async () => {
        const projectId = host.querySelector('[data-game73-project]')?.value || '';
        const goal = host.querySelector('[data-game73-goal]')?.value || '';
        button.disabled = true;
        button.textContent = '🚀 Iniciando rodada…';
        status.classList.remove('game73-error');
        status.textContent = 'Criando Planejamento na esteira real…';
        try {
          await engine.startRound({projectId, goal});
        } catch (error) {
          button.disabled = false;
          button.textContent = '🚀 Jogar agora';
          status.classList.add('game73-error');
          status.textContent = error?.message || 'Falha ao iniciar a rodada';
        }
      };
      return true;
    }

    host.innerHTML = `
      <section class="game73">
        <div><span class="game73-kicker">${state.done ? 'MISSÃO CUMPRIDA' : 'RODADA AUTOMÁTICA'}</span><h1>${state.done ? 'Entrega concluída' : 'Construindo sua entrega'}</h1><p class="game73-goal">${esc(state.goal)}</p></div>
        <div class="game73-progress-head"><span>${esc(state.projectName)}</span><strong>${state.completed}/${state.total} · ${state.percent}%</strong></div>
        <div class="game73-progress"><i style="width:${state.percent}%"></i></div>
        ${state.done ? `<div class="game73-status">🏆 A entrega passou pelas sete etapas e pelos gates independentes.</div>` : `<section class="game73-phase"><div class="game73-icon">${esc(state.currentPhaseIcon)}</div><div><small>ETAPA ${state.currentPhaseId}/${state.total}</small><strong>${esc(state.currentPhaseName)}</strong><p>${esc(state.currentPhaseSummary)}</p></div></section><div class="game73-status ${state.failed ? 'game73-error' : ''}">${esc(statusText(state))}</div>`}
        <div class="game73-actions">
          ${state.failed ? '<button class="game73-primary" type="button" data-game73-retry>↻ Tentar novamente</button>' : `<button class="game73-primary" type="button" disabled>${state.done ? '🏆 Rodada concluída' : '⚙ Rodada automática'}</button>`}
          <button class="game73-secondary" type="button" data-game73-refresh>↻ Atualizar</button>
          <button class="game73-secondary" type="button" data-game73-details>Detalhes</button>
          <button class="game73-secondary" type="button" data-game73-new>＋ Nova rodada</button>
        </div>
      </section>`;

    host.querySelector('[data-game73-refresh]')?.addEventListener('click', async event => {
      const button = event.currentTarget;
      button.disabled = true;
      try { await engine.refresh(); }
      catch (error) { console.error('[DevPilot Game Refresh]', error); }
      finally { button.disabled = false; }
    });

    host.querySelector('[data-game73-retry]')?.addEventListener('click', async event => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = 'Tentando novamente…';
      try { await engine.retry(); }
      catch (error) {
        button.disabled = false;
        button.textContent = error?.message || '↻ Tentar novamente';
      }
    });

    host.querySelector('[data-game73-new]')?.addEventListener('click', () => void engine.reset());
    host.querySelector('[data-game73-details]')?.addEventListener('click', event => {
      const showing = shell.classList.toggle('show-details');
      event.currentTarget.textContent = showing ? 'Ocultar detalhes' : 'Detalhes';
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
