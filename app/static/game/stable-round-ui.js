/* DevPilot game v84 — stable active-round surface outside the polling render target. */
(() => {
  'use strict';

  if (window.__devpilotStableRoundUiV84Ready) return;
  window.__devpilotStableRoundUiV84Ready = true;

  const ROOT_ID = 'devpilot-game-stable-round-v84';
  let lastSignature = '';
  let detailsOpen = false;

  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const controller = () => window.__devpilotGameControllerV73;
  const view = () => document.getElementById('build-game-view');
  const stage = () => document.querySelector('.devpilot-game-stage');

  const statusText = state => {
    if (state.done) return 'Rodada concluída e pronta para entrega.';
    if (state.failed) return state.verifier
      ? 'A validação da etapa falhou. O DevPilot está tratando a falha.'
      : 'A execução da etapa falhou. O DevPilot está tratando a falha.';
    if (state.awaitingGate) return 'Execução concluída. Validando a entrega da etapa…';
    if (state.verifier && state.active) return 'Validando automaticamente a entrega…';
    const map = {
      queued: 'Na fila real de execução…',
      planning: 'Preparando a execução…',
      running: 'Executando automaticamente…',
      review: 'Revisando automaticamente…',
      awaiting_approval: 'Aguardando autorização necessária…',
      blocked: 'Execução bloqueada.',
      paused: 'Execução pausada.',
      canceled: 'Execução anterior encerrada; preparando substituição…'
    };
    return map[String(state.taskStatus || '').toLowerCase()] || 'Preparando a próxima etapa…';
  };

  const signature = state => JSON.stringify([
    state.projectId,
    state.missionId,
    state.goal,
    state.projectName,
    state.completed,
    state.total,
    state.percent,
    state.done,
    state.currentPhaseId,
    state.currentPhaseName,
    state.currentPhaseSummary,
    state.currentPhaseIcon,
    state.taskId,
    state.taskStatus,
    state.verifier,
    state.awaitingGate,
    state.active,
    state.failed,
  ]);

  const ensureRoot = () => {
    const parent = stage();
    if (!parent) return null;
    let root = document.getElementById(ROOT_ID);
    if (!root) {
      root = document.createElement('section');
      root.id = ROOT_ID;
      root.setAttribute('aria-live', 'polite');
      parent.prepend(root);
    }
    return root;
  };

  const setDetailsVisibility = active => {
    const target = view();
    if (!target) return;
    if (!active) {
      target.style.removeProperty('display');
      return;
    }
    target.style.display = detailsOpen ? 'block' : 'none';
  };

  const bindActions = (root, engine) => {
    root.querySelector('[data-stable-refresh]')?.addEventListener('click', async event => {
      const button = event.currentTarget;
      button.disabled = true;
      const old = button.textContent;
      button.textContent = 'Atualizando…';
      try { await engine.refresh?.(); }
      catch (error) { console.error('[DevPilot Stable UI Refresh]', error); }
      finally { if (button.isConnected) { button.disabled = false; button.textContent = old; } }
    });

    root.querySelector('[data-stable-retry]')?.addEventListener('click', async event => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = 'Corrigindo automaticamente…';
      try { await engine.retry?.(); }
      catch (error) {
        console.error('[DevPilot Stable UI Retry]', error);
        if (button.isConnected) {
          button.disabled = false;
          button.textContent = '↻ Corrigir e continuar';
        }
      }
    });

    root.querySelector('[data-stable-details]')?.addEventListener('click', event => {
      detailsOpen = !detailsOpen;
      setDetailsVisibility(true);
      event.currentTarget.textContent = detailsOpen ? 'Ocultar detalhes' : 'Ver detalhes';
    });

    root.querySelector('[data-stable-new]')?.addEventListener('click', async () => {
      detailsOpen = false;
      await engine.reset?.();
      render();
    });
  };

  const render = () => {
    const engine = controller();
    const root = ensureRoot();
    if (!engine || !root) return false;
    const state = engine.snapshot?.();
    if (!state) return false;

    if (!state.hasTasks) {
      root.hidden = true;
      lastSignature = '';
      setDetailsVisibility(false);
      return false;
    }

    root.hidden = false;
    setDetailsVisibility(true);
    const nextSignature = signature(state);
    if (nextSignature === lastSignature) return true;
    lastSignature = nextSignature;

    const message = statusText(state);
    const step2Class = state.done ? 'game74-step done' : 'game74-step active';
    const step3Class = state.done ? 'game74-step active' : 'game74-step';

    root.innerHTML = `
      <section class="game74" data-stable-round-card>
        <div>
          <span class="game74-kicker">${state.done ? 'MISSÃO CUMPRIDA' : 'RODADA EM ANDAMENTO'}</span>
          <h1>${state.done ? 'Entrega concluída' : 'Estamos construindo sua entrega'}</h1>
          <p class="game74-goal">${esc(state.goal)}</p>
        </div>
        <div class="game74-steps" aria-label="Fluxo da rodada">
          <span class="game74-step done"><b>✓</b>Projeto</span>
          <span class="${step2Class}"><b>${state.done ? '✓' : '2'}</b>Executar</span>
          <span class="${step3Class}"><b>3</b>Entregar</span>
        </div>
        <div class="game74-progress-head"><span>${esc(state.projectName)}</span><strong>${state.completed}/${state.total} · ${state.percent}%</strong></div>
        <div class="game74-progress"><i style="width:${Math.max(0, Math.min(100, Number(state.percent) || 0))}%"></i></div>
        ${state.done ? `
          <div class="game74-status">🏆 <strong>Pronto.</strong> A entrega passou pelas etapas e gates da rodada.</div>
        ` : `
          <section class="game74-phase">
            <div class="game74-icon">${esc(state.currentPhaseIcon)}</div>
            <div><small>ETAPA ${state.currentPhaseId}/${state.total}</small><strong>${esc(state.currentPhaseName)}</strong><p>${esc(state.currentPhaseSummary)}</p></div>
          </section>
          <div class="game74-live"><i></i><span>${esc(message)}</span></div>
          <div class="game74-status ${state.failed ? 'game74-error' : ''}">${esc(message)}</div>
        `}
        <div class="game74-actions">
          ${state.failed
            ? '<button class="game74-primary" type="button" data-stable-retry>↻ Corrigir e continuar</button>'
            : `<button class="game74-primary" type="button" disabled>${state.done ? '🏆 Entrega pronta' : '⚙ Trabalhando automaticamente'}</button>`}
          <button class="game74-secondary" type="button" data-stable-details>${detailsOpen ? 'Ocultar detalhes' : 'Ver detalhes'}</button>
          ${state.done
            ? '<button class="game74-secondary" type="button" data-stable-new>＋ Nova rodada</button>'
            : '<button class="game74-secondary" type="button" data-stable-refresh>↻ Atualizar agora</button>'}
        </div>
      </section>`;

    bindActions(root, engine);
    return true;
  };

  let scheduled = false;
  const schedule = () => {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      render();
    });
  };

  document.addEventListener('devpilot:game:state', schedule);
  document.addEventListener('devpilot:game:rendered', schedule);
  document.addEventListener('devpilot:game:recovery-state', schedule);
  document.addEventListener('devpilot:game:core-ready', schedule);
  document.addEventListener('visibilitychange', schedule);
  window.__devpilotStableRoundUiRender = render;
  schedule();
})();
