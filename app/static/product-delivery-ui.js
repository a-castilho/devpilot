(() => {
  'use strict';

  const OPERATORS = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);
  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const VERIFIER_MARKER = '[DEVPILOT_DELIVERY_VERIFIER_V1]';
  const MODAL_ID = 'project-delivery-history-modal';
  const CREATE_ENTRY_ID = 'projects-new-project-sticky';
  const LOW_POWER = document.documentElement.classList.contains('devpilot-low-power');
  const CACHE_LIMIT = LOW_POWER ? 12 : 24;
  const DELIVERY_CONCURRENCY = LOW_POWER ? 2 : 4;
  const VISIBLE_CARD_LIMIT = LOW_POWER ? 6 : 12;
  const REFRESH_INTERVAL_MS = LOW_POWER ? 60000 : 30000;
  const HISTORY_TASK_LIMIT = 120;

  const statusCache = new Map();
  const deliveryRequests = new Map();
  const decorationQueue = [];
  const queuedProjects = new Set();
  let activeDecorations = 0;
  let hostObserver = null;
  let viewportObserver = null;
  let refreshTimer = null;

  const projects = () => (typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : []);
  const canOperate = () => OPERATORS.has(String((typeof state !== 'undefined' && state.currentUser?.role) || '').toUpperCase());
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
  const projectById = id => projects().find(project => String(project?.id) === String(id));
  const promptValue = (task, label) => {
    const escaped = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = String(task?.prompt || '').match(new RegExp(`^${escaped}:\\s*(.+)$`, 'mi'));
    return match?.[1]?.trim() || '';
  };
  const isGameTask = task => String(task?.prompt || '').includes(GAME_MARKER);
  const isVerifier = task => String(task?.prompt || '').includes(VERIFIER_MARKER);
  const missionFromTask = task => promptValue(task, 'PARTIDA');
  const phaseFromTask = task => Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  const statusLabel = status => ({pending:'Aguardando publicação',provisioning:'Preparando produto',deploying:'Publicando produto',ready:'Produto pronto',failed:'Falha na publicação',blocked:'Infraestrutura pendente'})[normalize(status)] || 'Aguardando publicação';
  const checkLabel = name => ({backend:'Backend',frontend:'Frontend',database:'Banco',neon:'Banco Neon',render:'Backend Render',vercel:'Frontend Vercel',public_url:'URL pública'})[name] || name || 'Verificação';

  function compactDelivery(value) {
    const delivery = value && typeof value === 'object' ? value : {};
    return {
      status: String(delivery.status || 'pending'),
      url: String(delivery.url || ''),
      checks: Array.isArray(delivery.checks) ? delivery.checks.slice(0, 12) : [],
      last_error: String(delivery.last_error || '').slice(0, 4000),
      updated_at: delivery.updated_at || null,
    };
  }

  function rememberDelivery(projectId, delivery) {
    const key = String(projectId || '');
    if (!key) return compactDelivery(delivery);
    const compact = compactDelivery(delivery);
    statusCache.delete(key);
    statusCache.set(key, compact);
    while (statusCache.size > CACHE_LIMIT) {
      const oldest = statusCache.keys().next().value;
      statusCache.delete(oldest);
    }
    return compact;
  }

  function cachedDelivery(projectId) {
    const key = String(projectId || '');
    if (!statusCache.has(key)) return null;
    const delivery = statusCache.get(key);
    statusCache.delete(key);
    statusCache.set(key, delivery);
    return delivery;
  }

  async function fetchDelivery(projectId, force = false) {
    const key = String(projectId || '');
    if (!key) return compactDelivery({});
    if (deliveryRequests.has(key)) return deliveryRequests.get(key);
    if (!force) {
      const cached = cachedDelivery(key);
      if (cached) return cached;
    }

    const request = api(`/projects/${encodeURIComponent(key)}/delivery`)
      .then(result => rememberDelivery(key, result || {}))
      .catch(() => compactDelivery({}))
      .finally(() => deliveryRequests.delete(key));
    deliveryRequests.set(key, request);
    return request;
  }

  function latestMissionTasks(tasks) {
    const gameTasks = (Array.isArray(tasks) ? tasks : []).filter(isGameTask).sort((a,b) => new Date(b.created_at) - new Date(a.created_at));
    if (!gameTasks.length) return [];
    const missionId = missionFromTask(gameTasks[0]);
    return gameTasks.filter(task => missionFromTask(task) === missionId).sort((a,b) => new Date(a.created_at) - new Date(b.created_at));
  }

  function ensureModal() {
    let modal = document.getElementById(MODAL_ID);
    if (modal) return modal;
    modal = document.createElement('dialog');
    modal.id = MODAL_ID;
    modal.innerHTML = '<div class="project-delivery-history-shell"></div>';
    modal.addEventListener('click', event => { if (event.target === modal) modal.close(); });
    document.body.appendChild(modal);
    return modal;
  }

  function renderHistory(modal, project, tasks, delivery) {
    const missionTasks = latestMissionTasks(tasks);
    const goalTask = missionTasks.find(task => promptValue(task, 'OBJETIVO'));
    const goal = promptValue(goalTask, 'OBJETIVO') || 'Nenhuma partida da esteira encontrada para este projeto.';
    const checks = Array.isArray(delivery?.checks) ? delivery.checks : [];
    const url = String(delivery?.url || '').trim();
    const phases = Array.from({length:7}, (_, index) => {
      const phase = index + 1;
      const phaseTasks = missionTasks.filter(task => phaseFromTask(task) === phase);
      const implementation = phaseTasks.find(task => !isVerifier(task));
      const verifier = phaseTasks.find(task => isVerifier(task));
      return {phase, implementation, verified: normalize(verifier?.status) === 'completed'};
    });
    const shell = modal.querySelector('.project-delivery-history-shell');
    shell.innerHTML = `
      <div class="project-delivery-history-head"><div><span class="eyebrow">📦 ENTREGA DA ESTEIRA</span><h3>${esc(project?.name || 'Projeto')}</h3></div><button type="button" class="link" data-delivery-close>✕</button></div>
      <div class="project-delivery-history-status"><strong>${esc(statusLabel(delivery?.status))}</strong><div>${esc(goal)}</div>${delivery?.last_error ? `<div class="project-delivery-history-error">${esc(delivery.last_error)}</div>` : ''}</div>
      ${missionTasks.length ? `<div class="project-delivery-history-grid">${phases.map(item => `<div class="project-delivery-history-phase"><strong>Fase ${item.phase}: ${esc(item.implementation?.title || 'sem execução registrada')}</strong><span class="${item.verified ? 'project-delivery-history-ok' : 'project-delivery-history-pending'}">${item.verified ? '✓ entrega verificada' : '• verificação pendente'}</span></div>`).join('')}</div>` : ''}
      ${checks.length ? `<div class="project-delivery-history-grid">${checks.map(check => `<div class="project-delivery-history-phase"><strong>${esc(checkLabel(check.name || check.provider))}</strong><span class="${check.ok ? 'project-delivery-history-ok' : 'project-delivery-history-pending'}">${check.ok ? '✓ aprovado' : '• pendente'}${check.status_code ? ` · HTTP ${esc(check.status_code)}` : ''}</span></div>`).join('')}</div>` : ''}
      ${url ? `<a class="project-delivery-history-url" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(url)}</a>` : ''}
      <div class="project-delivery-history-actions">${url && normalize(delivery?.status) === 'ready' ? `<a class="primary" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Abrir sistema ↗</a>` : ''}<button type="button" class="link" data-delivery-refresh="${esc(project?.id)}">Atualizar entrega</button></div>`;
  }

  async function openHistory(project, force = false) {
    if (!project?.id) return;
    const modal = ensureModal();
    modal.querySelector('.project-delivery-history-shell').innerHTML = '<p>Carregando entrega da esteira…</p>';
    if (!modal.open) modal.showModal();
    try {
      const [tasks, delivery] = await Promise.all([
        api(`/tasks?project_id=${encodeURIComponent(project.id)}&limit=${HISTORY_TASK_LIMIT}${force ? `&_=${Date.now()}` : ''}`),
        fetchDelivery(project.id, force),
      ]);
      renderHistory(modal, project, tasks, delivery || compactDelivery({}));
    } catch (error) {
      modal.querySelector('.project-delivery-history-shell').innerHTML = `<button type="button" class="link" data-delivery-close>✕</button><p class="project-delivery-history-error">${esc(error?.message || 'Não foi possível carregar a entrega.')}</p>`;
    }
  }

  function deliveryMarkup(project, delivery) {
    const currentStatus = normalize(delivery?.status || 'pending');
    const checks = Array.isArray(delivery?.checks) ? delivery.checks : [];
    return `
      <div class="product-delivery-status product-delivery-${esc(currentStatus)}"><strong>${esc(statusLabel(currentStatus))}</strong>${checks.map(check => `<span>${check.ok ? '✅' : '⏳'} ${esc(checkLabel(check.name || check.provider))}</span>`).join('')}${delivery?.last_error ? `<div class="product-delivery-error">${esc(delivery.last_error)}</div>` : ''}</div>
      <button type="button" class="product-delivery-history-action" data-delivery-history="${esc(project.id)}">📦 Ver entrega</button>
      ${canOperate() ? `<button type="button" class="link product-delivery-action" data-delivery-action="${esc(project.id)}">${currentStatus === 'ready' ? 'Abrir produto' : ['failed','blocked'].includes(currentStatus) ? 'Tentar novamente' : ['deploying','provisioning'].includes(currentStatus) ? 'Verificar publicação' : 'Publicar produto'}</button>` : ''}`;
  }

  async function decorateCard(project, card, force = false) {
    if (!project?.id || !card || !card.isConnected || !String(project.repository_url || '').trim()) return;
    card.dataset.deliveryProjectId = project.id;
    let box = card.querySelector('.product-delivery-box');
    if (!box) {
      box = document.createElement('div');
      box.className = 'product-delivery-box';
      card.appendChild(box);
    }
    const delivery = await fetchDelivery(project.id, force);
    if (!card.isConnected) return;
    const markup = deliveryMarkup(project, delivery);
    if (box.dataset.deliveryMarkup !== markup) {
      box.innerHTML = markup;
      box.dataset.deliveryMarkup = markup;
    }
  }

  function drainDecorationQueue() {
    while (activeDecorations < DELIVERY_CONCURRENCY && decorationQueue.length) {
      const item = decorationQueue.shift();
      const key = String(item?.project?.id || '');
      if (!item?.card?.isConnected || !key) {
        queuedProjects.delete(key);
        continue;
      }
      activeDecorations += 1;
      void decorateCard(item.project, item.card, item.force).finally(() => {
        activeDecorations -= 1;
        queuedProjects.delete(key);
        drainDecorationQueue();
      });
    }
  }

  function scheduleDecoration(project, card, force = false) {
    const key = String(project?.id || '');
    if (!key || !card?.isConnected || queuedProjects.has(key)) return;
    queuedProjects.add(key);
    decorationQueue.push({project, card, force});
    drainDecorationQueue();
  }

  function cardNearViewport(card) {
    if (!card?.isConnected) return false;
    const rect = card.getBoundingClientRect();
    const height = window.innerHeight || document.documentElement.clientHeight || 800;
    return rect.bottom >= -320 && rect.top <= height + 480;
  }

  function pruneDeliveryState(items) {
    const ids = new Set(items.map(project => String(project?.id || '')).filter(Boolean));
    for (const key of statusCache.keys()) {
      if (!ids.has(key)) statusCache.delete(key);
    }
    decorationQueue.length = 0;
    queuedProjects.clear();
  }

  function observeProjectCards() {
    const host = document.querySelector('#projects-list');
    if (!host) return;
    const cards = [...host.querySelectorAll('.project-card')];
    const items = projects();
    pruneDeliveryState(items);

    cards.forEach((card, index) => {
      const project = items[index];
      if (project?.id) card.dataset.deliveryProjectId = project.id;
    });

    if ('IntersectionObserver' in window) {
      if (!viewportObserver) {
        viewportObserver = new IntersectionObserver(entries => {
          entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            const project = projectById(entry.target.dataset.deliveryProjectId);
            if (project) scheduleDecoration(project, entry.target, false);
          });
        }, {rootMargin:'480px 0px'});
      }
      viewportObserver.disconnect();
      cards.forEach(card => viewportObserver.observe(card));
      return;
    }

    cards.slice(0, VISIBLE_CARD_LIMIT).forEach((card, index) => {
      const project = items[index];
      if (project) scheduleDecoration(project, card, false);
    });
  }

  function refreshVisible(force = false) {
    if (!document.querySelector('#projects-view.active')) return;
    const host = document.querySelector('#projects-list');
    if (!host) return;
    const items = projects();
    [...host.querySelectorAll('.project-card')]
      .map((card, index) => ({card, project:items[index]}))
      .filter(item => item.project && cardNearViewport(item.card))
      .slice(0, VISIBLE_CARD_LIMIT)
      .forEach(item => scheduleDecoration(item.project, item.card, force));
  }

  async function decorateProject(projectId, force = false) {
    const project = projectById(projectId);
    if (!project) return;
    const card = [...document.querySelectorAll('#projects-list .project-card')]
      .find(item => String(item.dataset.deliveryProjectId || '') === String(projectId));
    if (card) await decorateCard(project, card, force);
  }

  async function runAction(project, button) {
    if (!canOperate() || !project?.id) return;
    const current = await fetchDelivery(project.id, true);
    if (normalize(current.status) === 'ready' && current.url) {
      window.open(current.url, '_blank', 'noopener,noreferrer');
      return;
    }
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Processando…';
    try {
      let endpoint = `/projects/${encodeURIComponent(project.id)}/delivery/start`;
      if (['failed','blocked'].includes(normalize(current.status))) endpoint = `/projects/${encodeURIComponent(project.id)}/delivery/retry`;
      else if (['deploying','provisioning'].includes(normalize(current.status))) endpoint = `/projects/${encodeURIComponent(project.id)}/delivery/verify`;
      const delivery = await api(endpoint, {method:'POST'});
      rememberDelivery(project.id, delivery || {});
      await decorateProject(project.id, false);
      window.toast?.(normalize(delivery?.status) === 'ready' ? 'Produto pronto e entrega validada.' : delivery?.last_error || 'Entrega atualizada.');
    } catch (error) {
      window.toast?.(error?.message || 'Falha ao atualizar a entrega.');
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  async function openNewProject(button) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Abrindo…';
    try {
      if (typeof window.__devpilotLoadFeature === 'function') {
        const ready = await window.__devpilotLoadFeature('projectBuilder');
        if (!ready) throw new Error('Não foi possível carregar o cadastro de projeto.');
      }
      const originalEntry = document.querySelector('[data-project-builder-open]');
      if (!originalEntry) throw new Error('Cadastro de projeto indisponível nesta tela.');
      originalEntry.click();
    } catch (error) {
      window.toast?.(error?.message || 'Não foi possível abrir o cadastro de projeto.');
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function ensureCreateEntry() {
    const view = document.querySelector('#projects-view');
    if (!view || document.getElementById(CREATE_ENTRY_ID)) return;
    const entry = document.createElement('div');
    entry.id = CREATE_ENTRY_ID;
    entry.className = 'projects-new-project-sticky';
    entry.innerHTML = '<button type="button" class="primary projects-new-project-sticky-button" data-project-create-sticky>+ Novo projeto</button>';
    view.prepend(entry);
  }

  function installStyle() {
    if (document.getElementById('product-delivery-style')) return;
    const style = document.createElement('style');
    style.id = 'product-delivery-style';
    style.textContent = `
      .projects-new-project-sticky{position:sticky;top:8px;z-index:40;display:flex;justify-content:flex-end;pointer-events:none;margin:0 0 10px}.projects-new-project-sticky-button{pointer-events:auto;box-shadow:0 8px 24px rgba(0,0,0,.28)}
      .product-delivery-box{margin-top:10px;padding-top:10px;border-top:1px solid rgba(127,127,127,.22);display:flex!important;gap:8px;align-items:center;flex-wrap:wrap;visibility:visible!important;opacity:1!important;overflow:visible!important}
      .product-delivery-status{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px;width:100%}.product-delivery-error{width:100%;opacity:.85}.product-delivery-failed strong{color:#ff6b6b}.product-delivery-ready strong{color:#72efc5}
      .product-delivery-history-action{display:inline-flex!important;align-items:center;justify-content:center;min-height:30px;padding:6px 10px;border:1px solid rgba(139,233,253,.45);border-radius:8px;background:rgba(139,233,253,.08);color:#8be9fd;font-weight:800;cursor:pointer}.product-delivery-action{margin-left:auto}
      #${MODAL_ID}{width:min(760px,94vw);max-height:88vh;padding:0;border:1px solid rgba(139,233,253,.24);border-radius:16px;background:#08121f;color:inherit}#${MODAL_ID}::backdrop{background:rgba(0,0,0,.72)}
      .project-delivery-history-shell{display:grid;gap:14px;padding:18px;max-height:88vh;overflow:auto}.project-delivery-history-head{display:flex;justify-content:space-between;gap:12px}.project-delivery-history-head h3{margin:4px 0 0}.project-delivery-history-status,.project-delivery-history-phase{padding:10px 12px;border:1px solid rgba(255,255,255,.09);border-radius:12px;background:rgba(255,255,255,.025)}.project-delivery-history-phase strong{display:block;margin-bottom:4px}.project-delivery-history-grid{display:grid;gap:8px}.project-delivery-history-ok{color:#72efc5}.project-delivery-history-pending{color:#ffc56e}.project-delivery-history-error{color:#ff8f8f;white-space:pre-wrap;overflow-wrap:anywhere}.project-delivery-history-url{padding:10px 12px;border:1px solid rgba(114,239,197,.24);border-radius:10px;color:#8be9fd;overflow-wrap:anywhere}.project-delivery-history-actions{display:flex;gap:8px;flex-wrap:wrap}.project-delivery-history-actions a{text-decoration:none}
      @media(max-width:720px){.projects-new-project-sticky{top:6px}.product-delivery-box>button{width:100%}.product-delivery-action{margin-left:0}.project-delivery-history-actions>*{width:100%}}
    `;
    document.head.appendChild(style);
  }

  function installHostObserver() {
    const host = document.querySelector('#projects-list');
    if (!host || hostObserver) return;
    hostObserver = new MutationObserver(records => {
      const structural = records.some(record => record.target === host);
      if (!structural) return;
      clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(() => observeProjectCards(), 80);
    });
    hostObserver.observe(host, {childList:true});
  }

  function installDelegatedClicks() {
    if (document.documentElement.dataset.projectDeliveryClicks === '1') return;
    document.documentElement.dataset.projectDeliveryClicks = '1';
    document.addEventListener('click', event => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;

      const sticky = target.closest('[data-project-create-sticky]');
      if (sticky) {
        event.preventDefault();
        event.stopPropagation();
        void openNewProject(sticky);
        return;
      }

      const history = target.closest('[data-delivery-history]');
      if (history) {
        event.preventDefault();
        event.stopPropagation();
        const project = projectById(history.dataset.deliveryHistory);
        if (project) void openHistory(project);
        return;
      }

      const action = target.closest('[data-delivery-action]');
      if (action) {
        event.preventDefault();
        event.stopPropagation();
        const project = projectById(action.dataset.deliveryAction);
        if (project) void runAction(project, action);
        return;
      }

      const refresh = target.closest('[data-delivery-refresh]');
      if (refresh) {
        event.preventDefault();
        const project = projectById(refresh.dataset.deliveryRefresh);
        if (project) void openHistory(project, true);
        return;
      }

      if (target.closest('[data-delivery-close]')) {
        event.preventDefault();
        target.closest('dialog')?.close();
      }
    }, true);
  }

  function install() {
    installStyle();
    installDelegatedClicks();
    ensureCreateEntry();
    installHostObserver();
    observeProjectCards();
    if (document.documentElement.dataset.productDeliveryInstalled === '1') return;
    document.documentElement.dataset.productDeliveryInstalled = '1';
    window.setTimeout(() => { ensureCreateEntry(); observeProjectCards(); }, 300);
  }

  document.addEventListener('devpilot:feature-ready', event => { if (event.detail?.feature === 'projects') install(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && document.querySelector('#projects-view.active')) { ensureCreateEntry(); refreshVisible(true); } });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once:true}); else install();
  window.setInterval(() => refreshVisible(true), REFRESH_INTERVAL_MS);
})();
