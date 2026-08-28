(() => {
  'use strict';

  const ROLE = 'SUPER_ADMIN';
  let tasks = [];
  let loading = false;

  function isSuperAdmin() {
    return String(state.currentUser?.role || '').toUpperCase() === ROLE;
  }

  function html(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function safeUrl(value) {
    try {
      const url = new URL(String(value || ''));
      return ['https:', 'http:'].includes(url.protocol) ? url.href : '';
    } catch (_) {
      return '';
    }
  }

  function statusLabel(value) {
    return String(value || 'unknown').replaceAll('_', ' ');
  }

  function ensureStyles() {
    if (document.getElementById('super-admin-task-panel-styles')) return;
    const style = document.createElement('style');
    style.id = 'super-admin-task-panel-styles';
    style.textContent = `
      .sat-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}
      .sat-metric{border:1px solid var(--border,#26354a);border-radius:14px;padding:12px}
      .sat-metric strong{display:block;font-size:22px;margin-top:4px}
      .sat-list{display:grid;gap:10px}
      .sat-item{border:1px solid var(--border,#26354a);border-radius:14px;padding:14px;display:grid;gap:9px}
      .sat-head,.sat-meta,.sat-actions{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
      .sat-title{font-weight:700}
      .sat-meta{font-size:12px;opacity:.75;justify-content:flex-start}
      .sat-empty{padding:18px;border:1px dashed var(--border,#26354a);border-radius:14px;opacity:.75}
      @media(max-width:760px){.sat-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.sat-head{align-items:flex-start}.sat-actions{width:100%}.sat-actions>*{flex:1 1 auto}}
    `;
    document.head.appendChild(style);
  }

  function ensurePanel() {
    if (!isSuperAdmin() || document.getElementById('super-admin-tasks-view')) return;
    ensureStyles();

    const nav = document.querySelector('.sidebar nav');
    if (!nav) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'nav';
    button.dataset.view = 'super-admin-tasks';
    button.textContent = 'Tarefas ADM';
    nav.insertBefore(button, nav.querySelector('[data-view="cloud-admin"]') || nav.querySelector('[data-view="reports"]') || null);

    const section = document.createElement('section');
    section.id = 'super-admin-tasks-view';
    section.className = 'view';
    section.innerHTML = `
      <div class="section-head">
        <div>
          <span class="eyebrow">SUPER ADMIN · EXECUÇÃO AUDITÁVEL</span>
          <p>Trabalhos de implementação criados pelo Super Admin, com projeto, status, prioridade e evidência de entrega.</p>
        </div>
        <button class="ghost" type="button" id="super-admin-tasks-refresh">Atualizar</button>
      </div>
      <div id="super-admin-tasks-summary" class="sat-summary"></div>
      <article class="panel">
        <div class="panel-title">
          <div><span class="eyebrow">MINHAS TAREFAS</span><h3>Fila do Super Admin</h3></div>
          <span class="status" id="super-admin-task-count">0</span>
        </div>
        <div id="super-admin-task-list" class="sat-list"><div class="sat-empty">Carregando tarefas…</div></div>
      </article>
    `;

    const reports = document.getElementById('reports-view');
    const main = reports?.parentNode || document.querySelector('main');
    main?.insertBefore(section, reports || null);

    button.addEventListener('click', () => openPanel(button, section));
    section.querySelector('#super-admin-tasks-refresh')?.addEventListener('click', () => loadTasks(true));
  }

  function openPanel(button, section) {
    if (!isSuperAdmin()) return toast('Acesso exclusivo do Super Admin');
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button));
    const title = document.getElementById('page-title');
    if (title) title.textContent = 'Tarefas do Super Admin';
    void loadTasks();
  }

  function renderSummary() {
    const target = document.getElementById('super-admin-tasks-summary');
    if (!target) return;
    const active = tasks.filter(item => ['queued', 'planning', 'running', 'review', 'awaiting_approval'].includes(String(item.status))).length;
    const completed = tasks.filter(item => String(item.status) === 'completed').length;
    const failed = tasks.filter(item => ['failed', 'blocked'].includes(String(item.status))).length;
    const withPr = tasks.filter(item => safeUrl(item.pull_request_url)).length;
    target.innerHTML = [
      ['ATIVAS', active],
      ['CONCLUÍDAS', completed],
      ['BLOQUEADAS/FALHAS', failed],
      ['COM PR', withPr],
    ].map(([label, value]) => `<div class="sat-metric"><span class="eyebrow">${label}</span><strong>${value}</strong></div>`).join('');
  }

  function renderTasks() {
    renderSummary();
    const count = document.getElementById('super-admin-task-count');
    if (count) count.textContent = String(tasks.length);
    const target = document.getElementById('super-admin-task-list');
    if (!target) return;

    if (!tasks.length) {
      target.innerHTML = '<div class="sat-empty">Nenhuma tarefa própria do Super Admin foi registrada ainda. Crie pelo fluxo de tarefas do DevPilot ou pela API administrativa.</div>';
      return;
    }

    target.innerHTML = tasks.map(item => {
      const pr = safeUrl(item.pull_request_url);
      return `
        <div class="sat-item">
          <div class="sat-head">
            <div>
              <div class="sat-title">${html(item.title)}</div>
              <div class="sat-meta"><span>${html(item.project_name || item.project_id)}</span><span>·</span><span>${html(item.source)}</span><span>·</span><span>prioridade ${html(item.priority)}</span></div>
            </div>
            <span class="status ${html(item.status)}">${html(statusLabel(item.status))}</span>
          </div>
          <div class="sat-meta"><span>Atualizada ${new Date(item.updated_at || item.created_at).toLocaleString('pt-BR')}</span></div>
          <div class="sat-actions">
            <button class="link" type="button" data-sat-open-task="${html(item.id)}">Ver tarefa</button>
            ${pr ? `<a class="link" href="${html(pr)}" target="_blank" rel="noopener noreferrer">Abrir PR</a>` : '<span></span>'}
          </div>
        </div>
      `;
    }).join('');

    target.querySelectorAll('[data-sat-open-task]').forEach(button => {
      button.addEventListener('click', () => {
        const taskId = button.dataset.satOpenTask;
        const tasksNav = document.querySelector('.nav[data-view="tasks"]');
        tasksNav?.click();
        window.setTimeout(() => {
          const row = document.querySelector(`[data-task-instructions="${CSS.escape(taskId)}"]`);
          row?.scrollIntoView?.({behavior: 'smooth', block: 'center'});
        }, 300);
      });
    });
  }

  async function loadTasks(force = false) {
    if (!isSuperAdmin() || loading) return;
    if (tasks.length && !force) return renderTasks();
    loading = true;
    const target = document.getElementById('super-admin-task-list');
    if (target) target.innerHTML = '<div class="sat-empty">Carregando tarefas…</div>';
    try {
      const payload = await api('/ui/super-admin/tasks?limit=50');
      tasks = Array.isArray(payload) ? payload : [];
      renderTasks();
    } catch (error) {
      if (target) target.innerHTML = `<div class="sat-empty">${html(error.message || 'Falha ao carregar tarefas.')}</div>`;
      toast(error.message || 'Falha ao carregar tarefas do Super Admin');
    } finally {
      loading = false;
    }
  }

  ensurePanel();
  document.addEventListener('devpilot:dashboard-revealed', ensurePanel);
  document.addEventListener('devpilot:authenticated-core-ready', ensurePanel);
})();
