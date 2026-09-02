/* DevPilot game v78 — detalhes úteis e visíveis dentro do card principal. */
(() => {
  'use strict';

  if (window.__devpilotGameDetailsV78Ready) return;
  window.__devpilotGameDetailsV78Ready = true;

  const PANEL_ATTR = 'data-game78-details-panel';
  let opened = false;

  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const controller = () => window.__devpilotGameControllerV73;
  const statusLabel = state => {
    if (state.done) return 'Concluída';
    if (state.failed) return state.verifier ? 'Falha na validação' : 'Falha na execução';
    if (state.awaitingGate) return 'Aguardando validação';
    if (state.verifier && state.active) return 'Validando';
    const map = {
      queued: 'Na fila',
      running: 'Executando',
      review: 'Em revisão',
      awaiting_approval: 'Aguardando aprovação',
      blocked: 'Bloqueada',
      completed: 'Concluída',
      failed: 'Falhou',
      cancelled: 'Cancelada',
      canceled: 'Cancelada'
    };
    return map[state.taskStatus] || state.taskStatus || 'Preparando';
  };

  const ensureStyle = () => {
    if (document.getElementById('devpilot-game-details-v78-style')) return;
    const style = document.createElement('style');
    style.id = 'devpilot-game-details-v78-style';
    style.textContent = `
      [${PANEL_ATTR}]{display:grid;gap:12px;padding:16px;border:1px solid #2a4b63;border-radius:16px;background:#061522;scroll-margin-top:84px}
      [${PANEL_ATTR}] h3{margin:0;color:#fff;font-size:1rem}
      .game78-details-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
      .game78-detail{min-width:0;padding:11px;border-radius:12px;background:#0b2232}
      .game78-detail small{display:block;margin-bottom:3px;color:#6f91a8;font-size:.68rem;font-weight:850;text-transform:uppercase;letter-spacing:.07em}
      .game78-detail strong{display:block;color:#eaf7ff;overflow-wrap:anywhere}
      .game78-detail-wide{grid-column:1/-1}
      .game78-detail-note{margin:0!important;padding:11px;border-radius:12px;background:#0b2931;color:#bfe8e3!important;font-size:.82rem}
      .game78-detail-error{background:#381621!important;color:#ffd7de!important}
      @media(max-width:540px){.game78-details-grid{grid-template-columns:1fr}.game78-detail-wide{grid-column:auto}}
    `;
    document.head.appendChild(style);
  };

  const panelHtml = state => {
    const progress = `${Number(state.completed || 0)}/${Number(state.total || 0)} · ${Number(state.percent || 0)}%`;
    const taskId = state.taskId ? `#${esc(state.taskId)}` : 'Ainda não criada';
    const type = state.verifier ? 'Gate de validação' : 'Execução da etapa';
    const note = state.failed
      ? 'A etapa falhou. O DevPilot deve iniciar a correção automática e repetir esta etapa antes de avançar.'
      : state.done
        ? 'Todas as etapas e validações da rodada foram concluídas.'
        : 'A esteira continua automaticamente. Este painel acompanha a tarefa real da rodada.';

    return `
      <h3>Detalhes da rodada</h3>
      <div class="game78-details-grid">
        <div class="game78-detail game78-detail-wide"><small>Objetivo</small><strong>${esc(state.goal || '—')}</strong></div>
        <div class="game78-detail"><small>Projeto</small><strong>${esc(state.projectName || state.projectId || '—')}</strong></div>
        <div class="game78-detail"><small>Progresso</small><strong>${esc(progress)}</strong></div>
        <div class="game78-detail"><small>Etapa atual</small><strong>${esc(state.currentPhaseId || 0)}/${esc(state.total || 0)} · ${esc(state.currentPhaseName || '—')}</strong></div>
        <div class="game78-detail"><small>Status</small><strong>${esc(statusLabel(state))}</strong></div>
        <div class="game78-detail"><small>Tipo</small><strong>${esc(type)}</strong></div>
        <div class="game78-detail"><small>Tarefa</small><strong>${taskId}</strong></div>
      </div>
      <p class="game78-detail-note ${state.failed ? 'game78-detail-error' : ''}">${esc(note)}</p>`;
  };

  const renderPanel = ({scroll = false} = {}) => {
    if (!opened) return;
    const engine = controller();
    const card = document.querySelector('#devpilot-game-ui-v73 .game74');
    if (!engine || !card) return;

    ensureStyle();
    let panel = card.querySelector(`[${PANEL_ATTR}]`);
    if (!panel) {
      panel = document.createElement('section');
      panel.setAttribute(PANEL_ATTR, '');
      panel.setAttribute('role', 'region');
      panel.setAttribute('aria-label', 'Detalhes da rodada');
      const actions = card.querySelector('.game74-actions');
      if (actions) card.insertBefore(panel, actions);
      else card.appendChild(panel);
    }
    panel.innerHTML = panelHtml(engine.snapshot());

    const button = card.querySelector('[data-game73-details]');
    if (button) {
      button.textContent = 'Ocultar detalhes';
      button.setAttribute('aria-expanded', 'true');
    }
    if (scroll) window.setTimeout(() => panel.scrollIntoView({behavior:'smooth', block:'nearest'}), 0);
  };

  const closePanel = () => {
    opened = false;
    document.querySelector(`[${PANEL_ATTR}]`)?.remove();
    const button = document.querySelector('[data-game73-details]');
    if (button) {
      button.textContent = 'Ver detalhes';
      button.setAttribute('aria-expanded', 'false');
    }
    document.querySelector('.devpilot-game-v73-shell')?.classList.remove('show-details');
  };

  document.addEventListener('click', event => {
    const button = event.target?.closest?.('[data-game73-details]');
    if (!button) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    opened = !opened;
    if (opened) renderPanel({scroll:true});
    else closePanel();
  }, true);

  document.addEventListener('devpilot:game:state', () => {
    if (opened) window.setTimeout(() => renderPanel(), 0);
  });
  document.addEventListener('devpilot:game:rendered', () => {
    if (opened) window.setTimeout(() => renderPanel(), 0);
  });
})();
