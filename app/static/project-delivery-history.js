/* DevPilot project delivery history: make the latest Build Game delivery consultable from Projects. */
(() => {
  'use strict';

  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const VERIFIER_MARKER = '[DEVPILOT_DELIVERY_VERIFIER_V1]';
  const MODAL_ID = 'project-delivery-history-modal';

  const escapeHtml = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const promptValue = (task, label) => {
    const escaped = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = String(task?.prompt || '').match(new RegExp(`^${escaped}:\\s*(.+)$`, 'mi'));
    return match?.[1]?.trim() || '';
  };

  const missionFromTask = task => promptValue(task, 'PARTIDA');
  const phaseFromTask = task => Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  const isGameTask = task => String(task?.prompt || '').includes(GAME_MARKER);
  const isVerifier = task => String(task?.prompt || '').includes(VERIFIER_MARKER);
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');

  const latestMissionTasks = tasks => {
    const gameTasks = (Array.isArray(tasks) ? tasks : []).filter(isGameTask);
    if (!gameTasks.length) return [];
    gameTasks.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    const missionId = missionFromTask(gameTasks[0]);
    return gameTasks
      .filter(task => missionFromTask(task) === missionId)
      .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  };

  const installStyle = () => {
    if (document.querySelector('#project-delivery-history-style')) return;
    const style = document.createElement('style');
    style.id = 'project-delivery-history-style';
    style.textContent = `
      .project-delivery-history-button{margin-left:6px}
      #${MODAL_ID}{width:min(760px,94vw);max-height:88vh;padding:0;border:1px solid rgba(139,233,253,.24);border-radius:16px;background:#08121f;color:inherit}
      #${MODAL_ID}::backdrop{background:rgba(0,0,0,.72);backdrop-filter:blur(3px)}
      .project-delivery-history-shell{display:grid;gap:14px;padding:18px;max-height:88vh;overflow:auto}
      .project-delivery-history-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
      .project-delivery-history-head h3{margin:4px 0 0}.project-delivery-history-close{min-width:40px}
      .project-delivery-history-status{padding:10px 12px;border:1px solid rgba(255,255,255,.09);border-radius:12px;background:rgba(255,255,255,.025)}
      .project-delivery-history-status strong{display:block;margin-bottom:4px}
      .project-delivery-history-error{color:#ff8f8f;white-space:pre-wrap;overflow-wrap:anywhere}
      .project-delivery-history-grid{display:grid;gap:8px}.project-delivery-history-phase{padding:10px 12px;border:1px solid rgba(255,255,255,.08);border-radius:10px;background:rgba(255,255,255,.025)}
      .project-delivery-history-phase strong{display:block;margin-bottom:4px}.project-delivery-history-ok{color:#72efc5}.project-delivery-history-pending{color:#ffc56e}
      .project-delivery-history-url{display:block;padding:10px 12px;border:1px solid rgba(114,239,197,.24);border-radius:10px;color:#8be9fd;overflow-wrap:anywhere;text-decoration:none}
      .project-delivery-history-actions{display:flex;gap:8px;flex-wrap:wrap}.project-delivery-history-actions a{text-decoration:none}
      @media(max-width:720px){.project-delivery-history-button{margin-left:0}.project-delivery-history-actions>*{width:100%}}
    `;
    document.head.appendChild(style);
  };

  const ensureModal = () => {
    let modal = document.getElementById(MODAL_ID);
    if (modal) return modal;
    modal = document.createElement('dialog');
    modal.id = MODAL_ID;
    modal.innerHTML = '<div class="project-delivery-history-shell"><p>Carregando entrega…</p></div>';
    document.body.appendChild(modal);
    modal.addEventListener('click', event => {
      if (event.target === modal) modal.close();
    });
    return modal;
  };

  const statusLabel = delivery => ({
    pending: 'Aguardando publicação',
    provisioning: 'Preparando ambiente',
    deploying: 'Publicação em andamento',
    ready: 'Produto pronto',
    failed: 'Falha na publicação',
    blocked: 'Infraestrutura pendente',
  })[normalize(delivery?.status)] || 'Entrega registrada';

  const render = (modal, project, tasks, delivery) => {
    const missionTasks = latestMissionTasks(tasks);
    const goalTask = missionTasks.find(task => promptValue(task, 'OBJETIVO'));
    const goal = promptValue(goalTask, 'OBJETIVO') || 'Nenhuma partida da esteira encontrada para este projeto.';
    const checks = Array.isArray(delivery?.checks) ? delivery.checks : [];
    const url = String(delivery?.url || '').trim();
    const phases = [];

    for (let phase = 1; phase <= 6; phase += 1) {
      const phaseTasks = missionTasks.filter(task => phaseFromTask(task) === phase);
      const implementation = phaseTasks.find(task => !isVerifier(task));
      const verifier = phaseTasks.find(task => isVerifier(task));
      phases.push({
        phase,
        implementation,
        verified: normalize(verifier?.status) === 'completed',
      });
    }

    const shell = modal.querySelector('.project-delivery-history-shell');
    shell.innerHTML = `
      <div class="project-delivery-history-head">
        <div><span class="eyebrow">📦 ENTREGA DA ESTEIRA</span><h3>${escapeHtml(project?.name || 'Projeto')}</h3></div>
        <button type="button" class="link project-delivery-history-close" aria-label="Fechar">✕</button>
      </div>
      <div class="project-delivery-history-status">
        <strong>${escapeHtml(statusLabel(delivery))}</strong>
        <div>${escapeHtml(goal)}</div>
        ${delivery?.last_error ? `<div class="project-delivery-history-error">${escapeHtml(delivery.last_error)}</div>` : ''}
      </div>
      ${missionTasks.length ? `<div class="project-delivery-history-grid">
        ${phases.map(item => `
          <div class="project-delivery-history-phase">
            <strong>Fase ${item.phase}: ${escapeHtml(item.implementation?.title || 'sem execução registrada')}</strong>
            <span class="${item.verified ? 'project-delivery-history-ok' : 'project-delivery-history-pending'}">${item.verified ? '✓ entrega verificada' : '• verificação pendente'}</span>
          </div>
        `).join('')}
      </div>` : ''}
      ${checks.length ? `<div class="project-delivery-history-grid">
        ${checks.map(check => `<div class="project-delivery-history-phase"><strong>${escapeHtml(check.name || check.provider || 'Verificação')}</strong><span class="${check.ok ? 'project-delivery-history-ok' : 'project-delivery-history-pending'}">${check.ok ? '✓ aprovado' : '• pendente'}${check.status_code ? ` · HTTP ${escapeHtml(check.status_code)}` : ''}</span></div>`).join('')}
      </div>` : ''}
      ${url ? `<a class="project-delivery-history-url" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>` : ''}
      <div class="project-delivery-history-actions">
        ${url && normalize(delivery?.status) === 'ready' ? `<a class="primary" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Abrir sistema ↗</a>` : ''}
        <button type="button" class="link project-delivery-history-refresh">Atualizar entrega</button>
      </div>
    `;

    shell.querySelector('.project-delivery-history-close')?.addEventListener('click', () => modal.close());
    shell.querySelector('.project-delivery-history-refresh')?.addEventListener('click', () => void openDelivery(project, true));
  };

  const openDelivery = async (project, force = false) => {
    if (!project?.id || typeof api !== 'function') return;
    installStyle();
    const modal = ensureModal();
    const shell = modal.querySelector('.project-delivery-history-shell');
    shell.innerHTML = '<p>Carregando entrega da esteira…</p>';
    if (!modal.open) modal.showModal();
    try {
      const [tasks, delivery] = await Promise.all([
        api(`/tasks?project_id=${encodeURIComponent(project.id)}&limit=500${force ? `&_=${Date.now()}` : ''}`),
        api(`/projects/${encodeURIComponent(project.id)}/delivery${force ? `?_=${Date.now()}` : ''}`),
      ]);
      render(modal, project, tasks, delivery || {});
    } catch (error) {
      shell.innerHTML = `<div class="project-delivery-history-head"><strong>Entrega da esteira</strong><button type="button" class="link project-delivery-history-close">✕</button></div><p class="project-delivery-history-error">${escapeHtml(error?.message || 'Não foi possível carregar a entrega.')}</p>`;
      shell.querySelector('.project-delivery-history-close')?.addEventListener('click', () => modal.close());
    }
  };

  const decorateCards = () => {
    const host = document.querySelector('#projects-list');
    if (!host || typeof state === 'undefined' || !Array.isArray(state.projects)) return;
    const cards = [...host.querySelectorAll('.project-card')];
    cards.forEach((card, index) => {
      const project = state.projects[index];
      if (!project?.id || card.querySelector('.project-delivery-history-button')) return;
      const row = card.querySelector('.list-row');
      const actions = row?.querySelector('div') || row || card;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'link project-delivery-history-button';
      button.textContent = 'Ver entrega';
      button.dataset.projectDeliveryHistory = project.id;
      button.addEventListener('click', () => void openDelivery(project));
      actions.appendChild(button);
    });
  };

  const install = () => {
    installStyle();
    decorateCards();
    const host = document.querySelector('#projects-list');
    if (host && host.dataset.projectDeliveryHistoryObserved !== '1') {
      host.dataset.projectDeliveryHistoryObserved = '1';
      new MutationObserver(decorateCards).observe(host, {childList:true, subtree:false});
    }
  };

  document.addEventListener('devpilot:authenticated-ui-ready', install);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once:true});
  else install();
  window.setTimeout(install, 900);
})();
