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
  const publicUrls = new Map();

  const projects = () => (typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : []);
  const tasks = () => (typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks : []);
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const safePublicUrl = value => {
    const candidate = String(value || '').trim();
    return /^https:\/\//i.test(candidate) ? candidate : '';
  };

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

  function ensureAccessLink(host, project, url, extraClass = '') {
    if (!host || !project?.id || !url) return null;
    let link = host.querySelector(`.project-access-link[data-project-id="${CSS.escape(String(project.id))}"]`);
    if (!link) {
      link = document.createElement('a');
      link.className = `project-access-link ${extraClass}`.trim();
      link.dataset.projectId = String(project.id);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.addEventListener('click', event => event.stopPropagation());
      host.appendChild(link);
    }
    link.href = url;
    link.title = `Abrir ${project.name || 'projeto'} · ${url}`;
    link.setAttribute('aria-label', `Abrir projeto ${project.name || ''}`.trim());
    link.innerHTML = '<span aria-hidden="true">🌐</span> Abrir projeto <span aria-hidden="true">↗</span>';
    return link;
  }

  function decorateProjectCard(project, url) {
    const card = projectCard(project.id);
    if (!card) return;

    let link = card.querySelector('.project-public-url');
    if (!link) {
      link = document.createElement('a');
      link.className = 'project-public-url project-access-link';
      link.dataset.projectId = String(project.id);
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.addEventListener('click', event => event.stopPropagation());
      link.style.cssText = 'display:flex;align-items:center;justify-content:center;gap:6px;margin-top:10px;padding:10px 12px;border:1px solid rgba(54,211,153,.28);border-radius:12px;color:#7ce7cf;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:800';
      const box = card.querySelector('.product-delivery-box') || card;
      box.appendChild(link);
    }
    link.href = url;
    link.innerHTML = '<span aria-hidden="true">🌐</span> Abrir projeto <span aria-hidden="true">↗</span>';
    link.title = `Abrir ${project.name || 'projeto'} · ${url}`;
  }

  function decorateExecutionLinks(project, url) {
    const taskById = new Map(tasks().map(task => [String(task?.id || ''), task]));
    document.querySelectorAll('#tasks-table tr.task-main-row[data-task-id], #tasks-table tr.tasks-v9-row[data-task-id]').forEach(row => {
      const task = taskById.get(String(row.dataset.taskId || ''));
      if (!task || String(task.project_id || '') !== String(project.id)) return;
      const host = row.querySelector('.tasks-v9-main, .task-primary-cell, td');
      const link = ensureAccessLink(host, project, url, 'project-access-link-execution');
      if (!link) return;
      link.style.cssText = 'display:inline-flex;align-items:center;gap:5px;margin-top:7px;padding:6px 9px;border:1px solid rgba(54,211,153,.28);border-radius:9px;color:#7ce7cf;text-decoration:none;font-size:.76rem;font-weight:800;max-width:100%';
    });
  }

  function renderOverviewLinks() {
    const recentHost = document.querySelector('#recent-tasks');
    if (!recentHost) return;

    let host = document.querySelector('#overview-project-access-links');
    if (!publicUrls.size) {
      host?.remove();
      return;
    }

    if (!host) {
      host = document.createElement('div');
      host.id = 'overview-project-access-links';
      host.style.cssText = 'display:grid;gap:7px;margin-top:12px;padding-top:12px;border-top:1px solid rgba(255,255,255,.08)';
      recentHost.insertAdjacentElement('afterend', host);
    }

    const recentProjectIds = [...new Set(tasks().slice(0, 6).map(task => String(task?.project_id || '')).filter(Boolean))];
    const ordered = [
      ...recentProjectIds.map(id => projects().find(project => String(project?.id) === id)).filter(Boolean),
      ...projects().filter(project => !recentProjectIds.includes(String(project?.id))),
    ];
    const visible = ordered.filter(project => publicUrls.has(String(project?.id))).slice(0, 6);

    if (!visible.length) {
      host.remove();
      return;
    }

    host.innerHTML = '<strong style="font-size:.78rem;letter-spacing:.04em;color:#9eacc2">PROJETOS DISPONÍVEIS PARA TESTE</strong>';
    visible.forEach(project => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:9px;min-width:0';
      const name = document.createElement('span');
      name.textContent = project.name || 'Projeto';
      name.title = project.name || 'Projeto';
      name.style.cssText = 'min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.8rem;color:#c8d3e6';
      row.appendChild(name);
      const link = ensureAccessLink(row, project, publicUrls.get(String(project.id)), 'project-access-link-overview');
      if (link) link.style.cssText = 'display:inline-flex;align-items:center;gap:4px;flex:0 0 auto;padding:6px 8px;border:1px solid rgba(54,211,153,.28);border-radius:9px;color:#7ce7cf;text-decoration:none;font-size:.72rem;font-weight:800';
      host.appendChild(row);
    });
  }

  function showUrl(project, current) {
    const url = safePublicUrl(current?.url);
    const key = String(project?.id || '');
    if (!key) return;

    if (!url) {
      publicUrls.delete(key);
      renderOverviewLinks();
      return;
    }

    publicUrls.set(key, url);
    decorateProjectCard(project, url);
    decorateExecutionLinks(project, url);
    renderOverviewLinks();
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
    renderOverviewLinks();
  }

  document.addEventListener('devpilot:features-ready', () => void tick());
  document.addEventListener('devpilot:authenticated-ui-ready', () => setTimeout(() => void tick(), 1500));
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void tick();
  });
  document.addEventListener('click', event => {
    const view = event.target.closest?.('[data-view]')?.dataset.view;
    if (view === 'projects' || view === 'tasks' || view === 'overview') {
      setTimeout(() => void tick(), 150);
    }
  });
  setInterval(() => void tick(), POLL_MS);
  setTimeout(() => void tick(), 3000);
})();
