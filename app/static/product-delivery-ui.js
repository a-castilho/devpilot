(() => {
  'use strict';

  const OPERATORS = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);
  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const VERIFIER_MARKER = '[DEVPILOT_DELIVERY_VERIFIER_V1]';
  const MODAL_ID = 'project-delivery-history-modal';
  const statusCache = new Map();
  let observer = null;
  let rendering = false;

  const projects = () => (typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : []);
  const canOperate = () => OPERATORS.has(String((typeof state !== 'undefined' && state.currentUser?.role) || '').toUpperCase());
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
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

  async function fetchDelivery(projectId, force = false) {
    if (!force && statusCache.has(projectId)) return statusCache.get(projectId);
    try {
      const result = await api(`/projects/${encodeURIComponent(projectId)}/delivery`);
      statusCache.set(projectId, result || {});
      return result || {};
    } catch (_) {
      return {};
    }
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
    const phases = Array.from({length:6}, (_, index) => {
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
      <div class="project-delivery-history-actions">${url && normalize(delivery?.status) === 'ready' ? `<a class="primary" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Abrir sistema ↗</a>` : ''}<button type="button" class="link" data-delivery-refresh>Atualizar entrega</button></div>`;
    shell.querySelector('[data-delivery-close]')?.addEventListener('click', () => modal.close());
    shell.querySelector('[data-delivery-refresh]')?.addEventListener('click', () => void openHistory(project, true));
  }

  async function openHistory(project, force = false) {
    const modal = ensureModal();
    modal.querySelector('.project-delivery-history-shell').innerHTML = '<p>Carregando entrega da esteira…</p>';
    if (!modal.open) modal.showModal();
    try {
      const [tasks, delivery] = await Promise.all([
        api(`/tasks?project_id=${encodeURIComponent(project.id)}&limit=500${force ? `&_=${Date.now()}` : ''}`),
        api(`/projects/${encodeURIComponent(project.id)}/delivery${force ? `?_=${Date.now()}` : ''}`),
      ]);
      statusCache.set(project.id, delivery || {});
      renderHistory(modal, project, tasks, delivery || {});
    } catch (error) {
      modal.querySelector('.project-delivery-history-shell').innerHTML = `<button type="button" class="link" onclick="this.closest('dialog').close()">✕</button><p class="project-delivery-history-error">${esc(error?.message || 'Não foi possível carregar a entrega.')}</p>`;
    }
  }

  async function runAction(project, button) {
    if (!canOperate()) return;
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
      statusCache.set(project.id, delivery || {});
      decorateAll(true);
      if (normalize(delivery?.status) === 'ready') toast('Produto pronto e entrega validada.');
      else if (normalize(delivery?.status) === 'failed') toast(delivery.last_error || 'Não foi possível publicar o produto.');
      else toast('Entrega atualizada.');
    } catch (error) {
      toast(error?.message || 'Falha ao atualizar a entrega.');
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  async function decorateCard(project, card, force = false) {
    if (!project?.id || !card || !String(project.repository_url || '').trim()) return;
    card.dataset.deliveryProjectId = project.id;
    let box = card.querySelector('.product-delivery-box');
    if (!box) {
      box = document.createElement('div');
      box.className = 'product-delivery-box';
      card.appendChild(box);
    }
    const delivery = await fetchDelivery(project.id, force);
    const status = normalize(delivery?.status || 'pending');
    const checks = Array.isArray(delivery?.checks) ? delivery.checks : [];
    box.innerHTML = `
      <div class="product-delivery-status product-delivery-${esc(status)}"><strong>${esc(statusLabel(status))}</strong>${checks.map(check => `<span>${check.ok ? '✅' : '⏳'} ${esc(checkLabel(check.name || check.provider))}</span>`).join('')}${delivery?.last_error ? `<div class="product-delivery-error">${esc(delivery.last_error)}</div>` : ''}</div>
      <button type="button" class="product-delivery-history-action" data-delivery-history="${esc(project.id)}">📦 Ver entrega</button>
      ${canOperate() ? `<button type="button" class="link product-delivery-action">${status === 'ready' ? 'Abrir produto' : ['failed','blocked'].includes(status) ? 'Tentar novamente' : ['deploying','provisioning'].includes(status) ? 'Verificar publicação' : 'Publicar produto'}</button>` : ''}`;
    box.querySelector('[data-delivery-history]')?.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); void openHistory(project); });
    box.querySelector('.product-delivery-action')?.addEventListener('click', event => { event.preventDefault(); event.stopPropagation(); void runAction(project, event.currentTarget); });
  }

  function decorateAll(force = false) {
    if (rendering) return;
    const host = document.querySelector('#projects-list');
    if (!host) return;
    rendering = true;
    const cards = [...host.querySelectorAll('.project-card')];
    const items = projects();
    Promise.all(items.map((project, index) => decorateCard(project, cards[index], force))).finally(() => { rendering = false; });
  }

  function installStyle() {
    if (document.getElementById('product-delivery-style')) return;
    const style = document.createElement('style');
    style.id = 'product-delivery-style';
    style.textContent = `
      .product-delivery-box{margin-top:10px;padding-top:10px;border-top:1px solid rgba(127,127,127,.22);display:flex!important;gap:8px;align-items:center;flex-wrap:wrap;visibility:visible!important;opacity:1!important;overflow:visible!important}
      .product-delivery-status{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:12px;width:100%}.product-delivery-error{width:100%;opacity:.85}.product-delivery-failed strong{color:#ff6b6b}.product-delivery-ready strong{color:#72efc5}
      .product-delivery-history-action{display:inline-flex!important;align-items:center;justify-content:center;min-height:30px;padding:6px 10px;border:1px solid rgba(139,233,253,.45);border-radius:8px;background:rgba(139,233,253,.08);color:#8be9fd;font-weight:800;cursor:pointer;visibility:visible!important;opacity:1!important;position:relative!important;z-index:3!important}
      .product-delivery-action{margin-left:auto}
      #${MODAL_ID}{width:min(760px,94vw);max-height:88vh;padding:0;border:1px solid rgba(139,233,253,.24);border-radius:16px;background:#08121f;color:inherit}#${MODAL_ID}::backdrop{background:rgba(0,0,0,.72)}
      .project-delivery-history-shell{display:grid;gap:14px;padding:18px;max-height:88vh;overflow:auto}.project-delivery-history-head{display:flex;justify-content:space-between;gap:12px}.project-delivery-history-head h3{margin:4px 0 0}.project-delivery-history-status,.project-delivery-history-phase{padding:10px 12px;border:1px solid rgba(255,255,255,.09);border-radius:12px;background:rgba(255,255,255,.025)}.project-delivery-history-phase strong{display:block;margin-bottom:4px}.project-delivery-history-grid{display:grid;gap:8px}.project-delivery-history-ok{color:#72efc5}.project-delivery-history-pending{color:#ffc56e}.project-delivery-history-error{color:#ff8f8f;white-space:pre-wrap;overflow-wrap:anywhere}.project-delivery-history-url{padding:10px 12px;border:1px solid rgba(114,239,197,.24);border-radius:10px;color:#8be9fd;overflow-wrap:anywhere}.project-delivery-history-actions{display:flex;gap:8px;flex-wrap:wrap}.project-delivery-history-actions a{text-decoration:none}
      @media(max-width:720px){.product-delivery-box>button{width:100%}.product-delivery-action{margin-left:0}.project-delivery-history-actions>*{width:100%}}
    `;
    document.head.appendChild(style);
  }

  function installObserver() {
    const host = document.querySelector('#projects-list');
    if (!host || observer) return;
    observer = new MutationObserver(() => window.setTimeout(() => decorateAll(false), 0));
    observer.observe(host, {childList:true, subtree:true});
  }

  function install() {
    installStyle();
    installObserver();
    decorateAll(false);
    window.setTimeout(() => decorateAll(false), 250);
    window.setTimeout(() => decorateAll(false), 900);
  }

  document.addEventListener('devpilot:feature-ready', event => { if (event.detail?.feature === 'projects') install(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && document.querySelector('#projects-view.active')) decorateAll(true); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once:true}); else install();
  window.setInterval(() => { if (document.querySelector('#projects-view.active')) decorateAll(false); }, 5000);
})();
