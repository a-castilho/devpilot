(() => {
  'use strict';

  if (window.__devpilotProjectAutoDelivery) return;
  window.__devpilotProjectAutoDelivery = true;

  const ACTIVE = new Set(['queued','planning','running','in_progress','approved','processing','review','awaiting_approval']);
  const FAILURE = new Set(['failed','error','blocked']);
  const DELIVERY_PROGRESS = new Set(['pending','provisioning','deploying']);
  const DELIVERY_RETRYABLE = new Set(['failed','blocked']);
  const MAX_RETRIES_PER_SESSION = 3;
  const POLL_MS = 30000;
  const retryCount = new Map();
  const inFlight = new Set();

  const projects = () => (typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : []);
  const tasks = () => (typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks : []);
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));

  function projectTasks(projectId) {
    return tasks().filter(task => String(task?.project_id || '') === String(projectId || ''));
  }

  function buildReady(project) {
    const items = projectTasks(project.id);
    if (!items.length) return false;
    if (items.some(item => ACTIVE.has(normalize(item.status)))) return false;
    if (items.some(item => FAILURE.has(normalize(item.status)))) return false;
    return items.some(item => ['completed','done'].includes(normalize(item.status)));
  }

  async function delivery(projectId) {
    try {
      return await api(`/projects/${encodeURIComponent(projectId)}/delivery`);
    } catch (_) {
      return null;
    }
  }

  function projectCard(projectId) {
    return [...document.querySelectorAll('#projects-list .project-card')]
      .find(card => String(card.dataset.deliveryProjectId || card.dataset.projectId || '') === String(projectId));
  }

  function showUrl(project, current) {
    const url = String(current?.url || '').trim();
    if (!url) return;
    const card = projectCard(project.id);
    if (!card) return;

    let link = card.querySelector('.project-public-url');
    if (!link) {
      link = document.createElement('a');
      link.className = 'project-public-url';
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.style.cssText = 'display:block;margin-top:10px;padding:10px 12px;border:1px solid rgba(54,211,153,.28);border-radius:12px;color:#7ce7cf;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:800';
      const box = card.querySelector('.product-delivery-box') || card;
      box.appendChild(link);
    }
    link.href = url;
    link.textContent = `🌐 ${url}`;
    link.title = `Abrir ${project.name || 'projeto'}`;
  }

  async function advance(project) {
    if (!project?.id || !String(project.repository_url || '').trim()) return;
    const key = String(project.id);
    if (inFlight.has(key)) return;

    const current = await delivery(key);
    if (!current) return;
    showUrl(project, current);

    const status = normalize(current.status || 'pending');
    if (status === 'ready' && current.url) return;
    if (!buildReady(project)) return;

    const retries = retryCount.get(key) || 0;
    if (DELIVERY_RETRYABLE.has(status) && retries >= MAX_RETRIES_PER_SESSION) return;
    if (!DELIVERY_PROGRESS.has(status) && !DELIVERY_RETRYABLE.has(status)) return;

    inFlight.add(key);
    try {
      const result = await api(`/projects/${encodeURIComponent(key)}/delivery/auto`, {method:'POST'});
      if (DELIVERY_RETRYABLE.has(status)) retryCount.set(key, retries + 1);
      showUrl(project, result || {});
      if (normalize(result?.status) === 'ready' && result?.url) {
        window.toast?.(`Produto publicado: ${result.url}`);
      }
    } catch (error) {
      if (DELIVERY_RETRYABLE.has(status)) retryCount.set(key, retries + 1);
      console.warn('[DevPilot] entrega automática pendente:', error?.message || error);
    } finally {
      inFlight.delete(key);
    }
  }

  async function tick() {
    if (document.visibilityState === 'hidden') return;
    const items = projects();
    for (const project of items.slice(0, 24)) {
      await advance(project);
    }
  }

  document.addEventListener('devpilot:features-ready', () => void tick());
  document.addEventListener('devpilot:authenticated-ui-ready', () => setTimeout(() => void tick(), 1500));
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void tick();
  });
  setInterval(() => void tick(), POLL_MS);
  setTimeout(() => void tick(), 3000);
})();
