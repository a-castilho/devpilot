/* DevPilot game v91 — stable round surface with repair outcome and exact failure position. */
(() => {
  'use strict';

  if (window.__devpilotStableRoundUiV91Ready) return;
  window.__devpilotStableRoundUiV91Ready = true;

  const ROOT_ID = 'devpilot-game-stable-round-v91';
  const TERMINAL_RECOVERY_STATES = new Set([
    'awaiting_intervention',
    'intervention_required',
    'recovery_exhausted',
  ]);
  const recoveryStates = new Map();
  let lastSignature = '';
  let detailsOpen = false;

  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const recoverableFailure = state => ['failed', 'blocked'].includes(normalize(state?.taskStatus));
  const canceledExecution = state => ['canceled', 'cancelled'].includes(normalize(state?.taskStatus));

  const controller = () => window.__devpilotGameControllerV73;
  const view = () => document.getElementById('build-game-view');
  const stage = () => document.querySelector('.devpilot-game-stage');
  const recoveryFor = state => {
    const taskId = String(state?.taskId || '').trim();
    return recoveryStates.get(taskId) || window.__devpilotGameRecoveryForTask?.(taskId) || null;
  };
  const recoveryCategory = recovery => normalize(
    recovery?.failure?.category
    || recovery?.recovery_task?.failure?.category
    || recovery?.self_healing?.category
  );
  const systemManagedGitHubRecovery = recovery => Boolean(
    recoveryCategory(recovery) === 'github_auth'
    && (
      String(recovery?.state || '') === 'awaiting_intervention'
      || recovery?.recovery_task?.requires_approval
    )
  );
  const isTerminalRecovery = recovery => Boolean(
    TERMINAL_RECOVERY_STATES.has(String(recovery?.state || ''))
    && !systemManagedGitHubRecovery(recovery)
  );

  const recoveryStateText = recovery => {
    if (systemManagedGitHubRecovery(recovery)) {
      return 'Revalidando automaticamente as credenciais GitHub cadastradas';
    }
    const map = {
      ready_to_recover: 'Falha detectada; preparando correção automática',
      agent_recovery: 'Correção automática em execução',
      retesting: 'Correção aplicada; retestando a mesma etapa',
      resolved: 'Falha corrigida',
      awaiting_intervention: 'Aguardando intervenção necessária',
      intervention_required: 'Intervenção necessária para continuar',
      recovery_exhausted: 'Correção automática não resolveu a falha',
    };
    return map[String(recovery?.state || '')] || 'Diagnóstico da falha em andamento';
  };

  const statusText = (state, recovery) => {
    if (state.done) return 'Rodada concluída e pronta para entrega.';
    if (recoverableFailure(state)) {
      const recoveryState = String(recovery?.state || '');
      if (recoveryState === 'agent_recovery') return 'Corrigindo a causa da falha automaticamente…';
      if (recoveryState === 'retesting') return 'Correção aplicada. Retestando esta mesma etapa…';
      if (recoveryState === 'resolved') return 'Falha corrigida. Retomando a rodada…';
      if (systemManagedGitHubRecovery(recovery)) return 'Revalidando automaticamente as credenciais GitHub cadastradas…';
      if (isTerminalRecovery(recovery)) return 'A correção automática parou com diagnóstico. Veja o motivo e a posição abaixo.';
      if (normalize(state.taskStatus) === 'blocked') return 'A execução foi bloqueada. Diagnosticando a causa para retomar esta mesma etapa…';
      return state.verifier
        ? 'A validação falhou. Enviando o mesmo gate para recuperação segura…'
        : 'A execução falhou. Enviando a mesma etapa para recuperação segura…';
    }
    if (canceledExecution(state)) return 'A execução anterior foi encerrada. Recriando esta mesma etapa automaticamente…';
    if (state.awaitingGate) return 'Execução concluída. Validando a entrega da etapa…';
    if (state.verifier && state.active) return 'Validando automaticamente a entrega…';
    const map = {
      queued: 'Na fila real de execução…',
      planning: 'Preparando a execução…',
      running: 'Executando automaticamente…',
      review: 'Revisando automaticamente…',
      awaiting_approval: 'Aguardando autorização necessária…',
      paused: 'Execução pausada.',
    };
    return map[normalize(state.taskStatus)] || 'Preparando a próxima etapa…';
  };

  const diagnosticHtml = (state, recovery) => {
    if (!recoverableFailure(state)) return '';
    const failure = recovery?.failure || recovery?.recovery_task?.failure || null;
    const reason = failure?.message
      || recovery?.recovery_task?.failure?.message
      || 'Falha registrada. O DevPilot está consultando o diagnóstico do backend.';
    const code = failure?.code || recovery?.recovery_task?.failure?.code || 'EXECUTION_FAILED';
    const category = failure?.category || recovery?.recovery_task?.failure?.category || 'unknown';
    const phaseName = state.currentPhaseName || `Etapa ${state.currentPhaseId || '?'}`;
    const position = `${state.verifier ? 'Gate da etapa' : 'Etapa'} ${state.currentPhaseId || '?'} · ${phaseName}`;
    const attempt = recovery?.original_run?.attempt;
    const recoveryTask = recovery?.recovery_task;
    const manual = Boolean(
      (recovery?.manual_intervention_required || isTerminalRecovery(recovery))
      && !systemManagedGitHubRecovery(recovery)
    );

    return `
      <section data-game-recovery-diagnostic role="status" style="margin-top:10px;padding:11px 12px;border:1px solid rgba(255,92,113,.52);border-radius:10px;background:rgba(88,13,27,.34);display:grid;gap:7px">
        <strong style="font-size:12px">Diagnóstico da falha</strong>
        <div style="display:grid;grid-template-columns:minmax(90px,.35fr) 1fr;gap:5px 10px;font-size:11px">
          <span style="opacity:.72">Posição</span><b data-game-recovery-position>${esc(position)}${attempt ? ` · tentativa ${esc(attempt)}` : ''}</b>
          <span style="opacity:.72">Motivo</span><span data-game-recovery-reason>${esc(reason)}</span>
          <span style="opacity:.72">Código</span><code data-game-recovery-code>${esc(code)} · ${esc(category)}</code>
          <span style="opacity:.72">Correção</span><span data-game-recovery-state>${esc(recoveryStateText(recovery))}</span>
          ${recoveryTask?.status ? `<span style="opacity:.72">Tarefa de reparo</span><span>${esc(recoveryTask.status)}${recoveryTask.id ? ` · ${esc(recoveryTask.id)}` : ''}</span>` : ''}
        </div>
        ${manual ? '<p data-game-recovery-manual style="margin:1px 0 0;font-size:11px"><strong>O DevPilot não vai inventar credencial, permissão ou decisão humana.</strong> Corrija a condição externa indicada acima e use “Atualizar diagnóstico”.</p>' : ''}
      </section>`;
  };

  const signature = (state, recovery) => JSON.stringify([
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
    recovery?.state,
    recovery?.manual_intervention_required,
    recovery?.failure?.category,
    recovery?.failure?.code,
    recovery?.failure?.message,
    recovery?.original_run?.attempt,
    recovery?.recovery_task?.id,
    recovery?.recovery_task?.status,
    recovery?.recovery_task?.failure?.message,
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
    target.style.setProperty('display', detailsOpen ? 'block' : 'none', 'important');
  };

  const bindActions = (root, engine, state) => {
    root.querySelectorAll('[data-stable-refresh]').forEach(button => button.addEventListener('click', async event => {
      const current = event.currentTarget;
      current.disabled = true;
      const old = current.textContent;
      current.textContent = recoverableFailure(state) ? 'Atualizando diagnóstico…' : 'Atualizando…';
      try {
        if (recoverableFailure(state) && state.taskId) await window.__devpilotGameRefreshRecovery?.(state.taskId);
        await engine.refresh?.();
      } catch (error) {
        console.error('[DevPilot Stable UI Refresh]', error);
      } finally {
        if (current.isConnected) {
          current.disabled = false;
          current.textContent = old;
        }
      }
    }));

    root.querySelector('[data-stable-retry]')?.addEventListener('click', async event => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = recoverableFailure(state) ? 'Corrigindo automaticamente…' : 'Recriando etapa…';
      try {
        await engine.retry?.();
      } catch (error) {
        console.error('[DevPilot Stable UI Retry]', error);
        if (button.isConnected) {
          button.disabled = false;
          button.textContent = recoverableFailure(state) ? '↻ Corrigir e continuar' : '↻ Recriar e continuar';
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

    const recovery = recoveryFor(state);
    const failed = recoverableFailure(state);
    const canceled = canceledExecution(state);
    root.hidden = false;
    setDetailsVisibility(true);
    const nextSignature = signature(state, recovery);
    if (nextSignature === lastSignature) return true;
    lastSignature = nextSignature;

    const message = statusText(state, recovery);
    const terminalRecovery = failed && isTerminalRecovery(recovery);
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
          <div class="game74-status ${failed ? 'game74-error' : ''}">${esc(message)}</div>
          ${diagnosticHtml(state, recovery)}
        `}
        <div class="game74-actions">
          ${failed
            ? (terminalRecovery
              ? '<button class="game74-primary" type="button" data-stable-refresh>↻ Atualizar diagnóstico</button>'
              : '<button class="game74-primary" type="button" data-stable-retry>↻ Corrigir e continuar</button>')
            : (canceled
              ? '<button class="game74-primary" type="button" data-stable-retry>↻ Recriar e continuar</button>'
              : `<button class="game74-primary" type="button" disabled>${state.done ? '🏆 Entrega pronta' : '⚙ Trabalhando automaticamente'}</button>`)}
          <button class="game74-secondary" type="button" data-stable-details>${detailsOpen ? 'Ocultar detalhes' : 'Ver detalhes'}</button>
          ${state.done
            ? '<button class="game74-secondary" type="button" data-stable-new>＋ Nova rodada</button>'
            : ((failed || canceled) ? '' : '<button class="game74-secondary" type="button" data-stable-refresh>↻ Atualizar agora</button>')}
        </div>
      </section>`;

    bindActions(root, engine, state);
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
  document.addEventListener('devpilot:game:recovery-state', event => {
    const taskId = String(event?.detail?.taskId || '').trim();
    if (taskId && event?.detail?.recovery) recoveryStates.set(taskId, event.detail.recovery);
    schedule();
  });
  document.addEventListener('devpilot:game:core-ready', schedule);
  document.addEventListener('visibilitychange', schedule);
  window.__devpilotStableRoundUiRender = render;
  schedule();
})();
