(() => {
  const OPERATORS = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);
  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const VERIFIER_MARKER = '[DEVPILOT_DELIVERY_VERIFIER_V1]';
  const DELIVERY_MODAL_ID = 'project-delivery-history-modal';
  const initialProjectIds = new Set();
  const autoStarted = new Set();
  const statusCache = new Map();
  let initialized = false;

  function role() {
    return String((typeof state !== 'undefined' && state.currentUser?.role) || '').toUpperCase();
  }

  function canOperate() {
    return OPERATORS.has(role());
  }

  function projects() {
    return typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : [];
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function normalize(value) {
    return String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  }

  function promptValue(task, label) {
    const escaped = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = String(task?.prompt || '').match(new RegExp(`^${escaped}:\\s*(.+)$`, 'mi'));
    return match?.[1]?.trim() || '';
  }

  function missionFromTask(task) {
    return promptValue(task, 'PARTIDA');
  }

  function phaseFromTask(task) {
    return Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  }

  function isGameTask(task) {
    return String(task?.prompt || '').includes(GAME_MARKER);
  }

  function isVerifier(task) {
    return String(task?.prompt || '').includes(VERIFIER_MARKER);
  }

  function statusLabel(value) {
    const labels = {
      pending: 'Aguardando publicação',
      provisioning: 'Preparando produto',
      deploying: 'Publicando produto',
      ready: 'Produto pronto',
      failed: 'Falha na publicação',
      blocked: 'Infraestrutura pendente',
    };
    return labels[value] || 'Aguardando publicação';
  }

  function checkLabel(name) {
    return {backend: 'Backend', frontend: 'Frontend', database: 'Banco', neon: 'Banco Neon', render: 'Backend Render', vercel: 'Frontend Vercel', public_url: 'URL pública'}[name] || name;
  }

  function deliveryMarkup(delivery) {
    const status = String(delivery?.status || 'pending');
    const checks = Array.isArray(delivery?.checks) ? delivery.checks : [];
    const checkHtml = checks.length
      ? `<div class="product-delivery-checks">${checks.map(check =>
          `<span title="${check.status_code ? `HTTP ${Number(check.status_code)}` : 'verificação'}">${check.ok ? '✅' : '⏳'} ${escapeHtml(checkLabel(check.name || check.provider))}</span>`
        ).join('')}</div>`
      : '';
    const error = delivery?.last_error
      ? `<div class="product-delivery-error">${escapeHtml(delivery.last_error)}</div>`
      : '';
    return `
      <div class="product-delivery-status product-delivery-${escapeHtml(status)}">
        <strong>${escapeHtml(statusLabel(status))}</strong>
        ${checkHtml}
        ${error}
      </div>
    `;
  }

  function actionText(delivery) {
    const status = String(delivery?.status || 'pending');
    if (status === 'ready') return 'Abrir produto';
    if (status === 'failed' || status === 'blocked') return 'Tentar novamente';
    if (status === 'deploying' || status === 'provisioning') return 'Verificar publicação';
    return 'Publicar produto';
  }

  async function fetchDelivery(projectId, force = false) {
    if (!force && statusCache.has(projectId)) return statusCache.get(projectId);
    try {
      const result = await api(`/projects/${projectId}/delivery`);
      statusCache.set(projectId, result || {});
      return result || {};
    } catch (_) {
      return {};
    }
  }

  async function runAction(project, button) {
    if (!canOperate()) return;
    const current = await fetchDelivery(project.id, true);
    if (current.status === 'ready' && current.url) {
      window.open(current.url, '_blank', 'noopener,noreferrer');
      return;
    }

    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Processando…';
    try {
      let endpoint = `/projects/${project.id}/delivery/start`;
      if (current.status === 'failed' || current.status === 'blocked') {
        endpoint = `/projects/${project.id}/delivery/retry`;
      } else if (current.status === 'deploying' || current.status === 'provisioning') {
        endpoint = `/projects/${project.id}/delivery/verify`;
      }
      const delivery = await api(endpoint, {method: 'POST'});
      statusCache.set(project.id, delivery || {});
      renderCards();
      if (delivery?.status === 'ready') {
        toast('Produto pronto e entrega validada.');
      } else if (delivery?.status === 'blocked') {
        toast('A entrega está aguardando a infraestrutura aplicável ao projeto.');
      } else if (delivery?.status === 'failed') {
        toast(delivery.last_error || 'Não foi possível publicar o produto.');
      } else {
        toast('Produto em publicação. Acompanhe o status no card.');
      }
    } catch (error) {
      toast(error.message || 'Falha ao publicar o produto');
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function latestMissionTasks(tasks) {
    const gameTasks = (Array.isArray(tasks) ? tasks : []).filter(isGameTask);
    if (!gameTasks.length) return [];
    gameTasks.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    const missionId = missionFromTask(gameTasks[0]);
    return gameTasks
      .filter(task => missionFromTask(task) === missionId)
      .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  }

  function ensureDeliveryModal() {
    let modal = document.getElementById(DELIVERY_MODAL_ID);
    if (modal) return modal;
    modal = document.createElement('dialog');
    modal.id = DELIVERY_MODAL_ID;
    modal.innerHTML = '<div class="project-delivery-history-shell"><p>Carregando entrega…</p></div>';
    document.body.appendChild(modal);
    modal.addEventListener('click', event => {
      if (event.target === modal) modal.close();
    });
    return modal;
  }

  function renderDeliveryHistory(modal, project, tasks, delivery) {
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
      phases.push({phase, implementation, verified: normalize(verifier?.status) === 'completed'});
    }

    const shell = modal.querySelector('.project-delivery-history-shell');
    shell.innerHTML = `
      <div class="project-delivery-history-head">
        <div><span class="eyebrow">📦 ENTREGA DA ESTEIRA</span><h3>${escapeHtml(project?.name || 'Projeto')}</h3></div>
        <button type="button" class="link project-delivery-history-close" aria-label="Fechar">✕</button>
      </div>
      <div class="project-delivery-history-status">
        <strong>${escapeHtml(statusLabel(normalize(delivery?.status)))}</strong>
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
        ${checks.map(check => `<div class="project-delivery-history-phase"><strong>${escapeHtml(checkLabel(check.name || check.provider || 'Verificação'))}</strong><span class="${check.ok ? 'project-delivery-history-ok' : 'project-delivery-history-pending'}">${check.ok ? '✓ aprovado' : '• pendente'}${check.status_code ? ` · HTTP ${escapeHtml(check.status_code)}` : ''}</span></div>`).join('')}
      </div>` : ''}
      ${url ? `<a class="project-delivery-history-url" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>` : ''}
      <div class="project-delivery-history-actions">
        ${url && normalize(delivery?.status) === 'ready' ? `<a class="primary" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Abrir sistema ↗</a>` : ''}
        <button type="button" class="link project-delivery-history-refresh">Atualizar entrega</button>
      </div>
    `;
    shell.querySelector('.project-delivery-history-close')?.addEventListener('click', () => modal.close());
    shell.querySelector('.project-delivery-history-refresh')?.addEventListener('click', () => void openDeliveryHistory(project, true));
  }

  async function openDeliveryHistory(project, force = false) {
    if (!project?.id) return;
    const modal = ensureDeliveryModal();
    const shell = modal.querySelector('.project-delivery-history-shell');
    shell.innerHTML = '<p>Carregando entrega da esteira…</p>';
    if (!modal.open) modal.showModal();
    try {
      const [tasks, delivery] = await Promise.all([
        api(`/tasks?project_id=${encodeURIComponent(project.id)}&limit=500${force ? `&_=${Date.now()}` : ''}`),
        api(`/projects/${encodeURIComponent(project.id)}/delivery${force ? `?_=${Date.now()}` : ''}`),
      ]);
      statusCache.set(project.id, delivery || {});
      renderDeliveryHistory(modal, project, tasks, delivery || {});
    } catch (error) {
      shell.innerHTML = `<div class="project-delivery-history-head"><strong>Entrega da esteira</strong><button type="button" class="link project-delivery-history-close">✕</button></div><p class="project-delivery-history-error">${escapeHtml(error?.message || 'Não foi possível carregar a entrega.')}</p>`;
      shell.querySelector('.project-delivery-history-close')?.addEventListener('click', () => modal.close());
    }
  }

  function cardForIndex(host, index) {
    return host.querySelectorAll('.project-card')[index] || null;
  }

  async function decorateCard(project, card) {
    if (!project || !card || !String(project.repository_url || '').trim()) return;
    let box = card.querySelector('.product-delivery-box');
    if (!box) {
      box = document.createElement('div');
      box.className = 'product-delivery-box';
      const row = card.querySelector('.list-row') || card;
      row.appendChild(box);
    }

    const delivery = await fetchDelivery(project.id);
    box.innerHTML = deliveryMarkup(delivery);

    const historyButton = document.createElement('button');
    historyButton.type = 'button';
    historyButton.className = 'link product-delivery-history-action';
    historyButton.textContent = 'Ver entrega';
    historyButton.addEventListener('click', () => void openDeliveryHistory(project));
    box.appendChild(historyButton);

    if (!canOperate()) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'link product-delivery-action';
    button.textContent = actionText(delivery);
    button.addEventListener('click', () => runAction(project, button));
    box.appendChild(button);
  }

  function renderCards() {
    const host = document.querySelector('#projects-list');
    if (!host) return;
    projects().forEach((project, index) => {
      const card = cardForIndex(host, index);
      if (card) void decorateCard(project, card);
    });
  }

  async function startNewProjects() {
    if (!canOperate()) return;
    for (const project of projects()) {
      if (!project?.id || initialProjectIds.has(project.id) || autoStarted.has(project.id)) continue;
      if (!String(project.repository_url || '').trim()) continue;
      autoStarted.add(project.id);
      try {
        const current = await fetchDelivery(project.id, true);
        if (!current.status || current.status === 'pending') {
          const delivery = await api(`/projects/${project.id}/delivery/start`, {method: 'POST'});
          statusCache.set(project.id, delivery || {});
          if (delivery?.status === 'ready') {
            toast(`Produto ${project.name || ''} pronto para abrir.`);
          } else if (delivery?.status === 'blocked') {
            toast('Projeto criado. A entrega está aguardando infraestrutura.');
          } else {
            toast('Projeto criado. Publicação do produto iniciada.');
          }
        }
      } catch (error) {
        toast(error.message || 'Projeto criado, mas a publicação precisa ser retomada.');
      }
    }
    renderCards();
  }

  function installStyle() {
    if (document.querySelector('#product-delivery-style')) return;
    const style = document.createElement('style');
    style.id = 'product-delivery-style';
    style.textContent = `
      .product-delivery-box{margin-top:10px;padding-top:10px;border-top:1px solid rgba(127,127,127,.22);display:flex;gap:8px;align-items:center;flex-wrap:wrap}
      .product-delivery-status{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px;width:100%}
      .product-delivery-ready strong{color:#2fbf71}.product-delivery-failed strong{color:#e05d5d}.product-delivery-blocked strong{color:#d59b2c}
      .product-delivery-checks{display:flex;gap:8px;flex-wrap:wrap}.product-delivery-error{opacity:.78;width:100%}
      .product-delivery-action{margin-left:auto}
      #${DELIVERY_MODAL_ID}{width:min(760px,94vw);max-height:88vh;padding:0;border:1px solid rgba(139,233,253,.24);border-radius:16px;background:#08121f;color:inherit}
      #${DELIVERY_MODAL_ID}::backdrop{background:rgba(0,0,0,.72);backdrop-filter:blur(3px)}
      .project-delivery-history-shell{display:grid;gap:14px;padding:18px;max-height:88vh;overflow:auto}
      .project-delivery-history-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.project-delivery-history-head h3{margin:4px 0 0}
      .project-delivery-history-status,.project-delivery-history-phase{padding:10px 12px;border:1px solid rgba(255,255,255,.09);border-radius:12px;background:rgba(255,255,255,.025)}
      .project-delivery-history-status strong,.project-delivery-history-phase strong{display:block;margin-bottom:4px}.project-delivery-history-error{color:#ff8f8f;white-space:pre-wrap;overflow-wrap:anywhere;margin-top:8px}
      .project-delivery-history-grid{display:grid;gap:8px}.project-delivery-history-ok{color:#72efc5}.project-delivery-history-pending{color:#ffc56e}
      .project-delivery-history-url{display:block;padding:10px 12px;border:1px solid rgba(114,239,197,.24);border-radius:10px;color:#8be9fd;overflow-wrap:anywhere;text-decoration:none}
      .project-delivery-history-actions{display:flex;gap:8px;flex-wrap:wrap}.project-delivery-history-actions a{text-decoration:none}
      @media(max-width:720px){.product-delivery-box{align-items:flex-start}.product-delivery-action{margin-left:0}.product-delivery-box>button{width:100%}.project-delivery-history-actions>*{width:100%}}
    `;
    document.head.appendChild(style);
  }

  function install() {
    installStyle();
    const host = document.querySelector('#projects-list');
    if (!host) return;
    if (!initialized) {
      projects().forEach(project => project?.id && initialProjectIds.add(project.id));
      initialized = true;
    }
    if (!host.dataset.productDeliveryObserved) {
      host.dataset.productDeliveryObserved = '1';
      new MutationObserver(() => {
        renderCards();
        void startNewProjects();
      }).observe(host, {childList: true, subtree: false});
    }
    renderCards();
    void startNewProjects();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, {once: true});
  } else {
    install();
  }
  window.setTimeout(install, 800);
  const refreshVisibleProjects = () => {
    if (document.hidden) return;
    if (!document.querySelector('#projects-view.active')) return;
    statusCache.clear();
    renderCards();
  };

  document.addEventListener('visibilitychange', refreshVisibleProjects);
  window.setInterval(refreshVisibleProjects, 30000);
})();
