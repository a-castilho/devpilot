(() => {
  'use strict';

  if (window.__devpilotProjectAutoDelivery) return;
  window.__devpilotProjectAutoDelivery = true;

  const POLL_MS = 30000;
  const inFlight = new Set();

  const projects = () => (typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : []);

  function projectCard(projectId) {
    return [...document.querySelectorAll('#projects-list .project-card')]
      .find(card => String(card.dataset.deliveryProjectId || card.dataset.projectId || '') === String(projectId));
  }

  function showUrl(project, current) {
    const url = String(current?.url || '').trim();
    if (!url || String(current?.status || '').toLowerCase() !== 'ready') return;
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

  async function observe(project) {
    if (!project?.id || !String(project.repository_url || '').trim() || typeof api !== 'function') return;
    const key = String(project.id);
    if (inFlight.has(key)) return;
    inFlight.add(key);
    try {
      const current = await api(`/projects/${encodeURIComponent(key)}/delivery`);
      showUrl(project, current || {});
      document.dispatchEvent(new CustomEvent('devpilot:delivery:updated', {detail: current || {}}));
    } catch (error) {
      console.warn('[DevPilot] não foi possível consultar a entrega:', error?.message || error);
    } finally {
      inFlight.delete(key);
    }
  }

  async function tick() {
    if (document.visibilityState === 'hidden') return;
    for (const project of projects().slice(0, 24)) {
      await observe(project);
    }
  }

  document.addEventListener('devpilot:features-ready', () => void tick());
  document.addEventListener('devpilot:authenticated-ui-ready', () => setTimeout(() => void tick(), 1500));
  document.addEventListener('devpilot:delivery:ready', () => void tick());
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void tick();
  });
  setInterval(() => void tick(), POLL_MS);
  setTimeout(() => void tick(), 3000);
})();
