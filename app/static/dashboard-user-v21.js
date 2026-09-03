(() => {
  'use strict';

  if (window.__devpilotDashboardUserV21) return;
  window.__devpilotDashboardUserV21 = true;

  const qs = (selector, root = document) => root.querySelector(selector);

  function injectStyles() {
    if (qs('#devpilot-dashboard-user-v21-style')) return;

    const style = document.createElement('style');
    style.id = 'devpilot-dashboard-user-v21-style';
    style.textContent = `
      #overview-view.dp-dashboard-v21{display:grid!important;gap:14px!important;width:100%!important;max-width:100%!important;min-width:0!important;padding:0 0 28px!important}
      #overview-view .dp-v21-topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:46px;padding:10px 14px;border:1px solid rgba(59,226,207,.22);border-radius:14px;background:linear-gradient(90deg,rgba(21,75,83,.30),rgba(7,22,36,.74))}
      #overview-view .dp-v21-topbar-copy{min-width:0}#overview-view .dp-v21-topbar small{display:block;color:#59ddcf;font-size:9px;font-weight:900;letter-spacing:.09em}#overview-view .dp-v21-topbar strong{display:block;margin-top:2px;color:#e8f7f4;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      #overview-view .dp-v21-live{display:inline-flex;align-items:center;gap:7px;flex:0 0 auto;padding:7px 10px;border-radius:999px;color:#8fe9da;background:rgba(53,229,209,.07);font-size:10px;font-weight:800}#overview-view .dp-v21-live::before{content:'';width:7px;height:7px;border-radius:50%;background:#50dcb9;box-shadow:0 0 13px rgba(80,220,185,.72)}
      #overview-view .command-center{display:grid!important;grid-template-columns:minmax(0,1.55fr) minmax(290px,.75fr)!important;gap:14px!important;align-items:stretch!important;padding:22px!important;border-radius:22px!important;border:1px solid rgba(76,156,197,.25)!important;background:linear-gradient(120deg,rgba(8,34,49,.98),rgba(7,22,37,.98) 58%,rgba(11,29,45,.98))!important;box-shadow:0 18px 55px rgba(0,0,0,.24)!important}
      #overview-view .command-center-copy h2{font-size:clamp(30px,3.3vw,48px)!important;max-width:780px!important;letter-spacing:-.04em!important}#overview-view .command-center-copy>p{font-size:14px!important;max-width:720px!important;color:#96aebe!important}#overview-view .command-center-copy>.eyebrow{color:#65e3d5!important}
      #overview-view .attention-card{align-self:stretch!important;min-height:100%!important;border-radius:17px!important;background:linear-gradient(145deg,rgba(14,38,53,.92),rgba(5,19,30,.96))!important}#overview-view .attention-card.danger{background:linear-gradient(145deg,rgba(58,23,31,.85),rgba(8,19,30,.97))!important}#overview-view .attention-card.warning{background:linear-gradient(145deg,rgba(62,48,17,.55),rgba(8,20,30,.97))!important}
      #overview-view .overview-metrics{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:10px!important}
      #overview-view .overview-metric{position:relative!important;min-height:116px!important;padding:16px 17px 15px 20px!important;border-radius:16px!important;background:linear-gradient(150deg,rgba(13,33,50,.98),rgba(6,20,33,.98))!important}
      #overview-view .overview-metric::before{content:'';position:absolute;left:0;top:14px;bottom:14px;width:3px;border-radius:999px;background:#42d9c7;box-shadow:0 0 15px rgba(66,217,199,.30)}#overview-view .overview-metric.approval::before{background:#f0c258}#overview-view .overview-metric.completed::before{background:#56d6a9}#overview-view .overview-metric.active::before{background:#52aef4}#overview-view .overview-metric>strong{font-size:clamp(30px,3.1vw,43px)!important}
      #overview-view .operations-strip{display:grid!important;grid-template-columns:minmax(210px,.55fr) minmax(0,1.45fr)!important;grid-template-areas:'head progress' 'breakdown breakdown';align-items:center!important;gap:10px 16px!important;padding:14px 16px!important;border-radius:16px!important}#overview-view .operation-heading{grid-area:head!important;align-items:center!important}#overview-view .progress-track{grid-area:progress!important;height:9px!important}#overview-view .status-breakdown{grid-area:breakdown!important}
      #overview-view .dp-v21-data-note{margin:-5px 2px 1px;padding:7px 10px;border-radius:10px;border:1px solid rgba(96,151,181,.13);background:rgba(7,20,32,.50);color:#7894a5;font-size:10px;line-height:1.45}
      #overview-view .dp-v21-data-note b{color:#9bc5c0}
      #overview-view .overview-grid{display:grid!important;grid-template-columns:minmax(0,1.7fr) minmax(250px,.6fr)!important;gap:12px!important}#overview-view .activity-panel{padding:16px!important}#overview-view .quick-panel{padding:16px!important;position:sticky;top:12px}#overview-view .panel-title h3{font-size:18px!important}#overview-view #recent-tasks{gap:7px!important}
      #overview-view .recent-task{min-height:60px!important;grid-template-columns:11px minmax(0,1fr) auto!important;padding:10px 12px!important;border-color:rgba(92,139,170,.08)!important;background:rgba(255,255,255,.021)!important}#overview-view .recent-task:hover{border-color:rgba(65,222,203,.25)!important;background:rgba(55,214,194,.055)!important}#overview-view .task-copy strong{font-size:13px!important}#overview-view .task-copy small{font-size:10px!important}
      #overview-view .quick-grid{gap:8px!important}#overview-view .quick-action{min-height:59px!important;padding:9px 11px!important;border-color:rgba(91,140,173,.14)!important}#overview-view .quick-action:hover{border-color:rgba(59,222,205,.27)!important;background:rgba(59,222,205,.045)!important}#overview-view .quick-action strong{font-size:12px!important}#overview-view .quick-action small{font-size:10px!important}
      #overview-view .system-overview{min-height:50px!important;border-radius:13px!important;background:rgba(5,16,28,.76)!important}
      @media(max-width:1100px){#overview-view .command-center{grid-template-columns:minmax(0,1fr) minmax(250px,.7fr)!important}#overview-view .overview-grid{grid-template-columns:minmax(0,1fr) minmax(230px,.58fr)!important}}
      @media(max-width:900px){#overview-view .dp-v21-topbar{margin:0 2px}#overview-view .command-center{grid-template-columns:minmax(0,1fr)!important;padding:15px!important}#overview-view .attention-card{min-height:auto!important}#overview-view .overview-metrics{grid-template-columns:repeat(2,minmax(0,1fr))!important}#overview-view .operations-strip{grid-template-columns:minmax(0,1fr)!important;grid-template-areas:'head' 'progress' 'breakdown'!important}#overview-view .status-breakdown{grid-template-columns:repeat(2,minmax(0,1fr))!important}#overview-view .overview-grid{grid-template-columns:minmax(0,1fr)!important}#overview-view .quick-panel{position:static!important}}
      @media(max-width:520px){#overview-view .dp-v21-topbar{align-items:flex-start;padding:10px 11px}#overview-view .dp-v21-live{font-size:9px;padding:6px 8px}#overview-view .command-center-copy h2{font-size:29px!important}#overview-view .overview-metric{min-height:104px!important;padding:13px 13px 12px 17px!important}#overview-view .overview-metric>strong{font-size:30px!important}#overview-view .status-breakdown{grid-template-columns:minmax(0,1fr)!important}#overview-view .recent-task{grid-template-columns:9px minmax(0,1fr)!important}#overview-view .recent-task>.status{grid-column:2;justify-self:start}}
    `;
    document.head.appendChild(style);
  }

  function recentTasks() {
    try {
      if (typeof state !== 'undefined' && Array.isArray(state.tasks)) {
        return state.tasks.slice(0, 20);
      }
    } catch (_) {
      // Global state may not exist yet while the shell is still booting.
    }
    return [];
  }

  function recentSnapshot() {
    const tasks = recentTasks();
    const normalized = value => String(value || '').toLowerCase();
    const count = accepted => tasks.filter(task => accepted.includes(normalized(task.status))).length;
    return {
      tasks,
      total: tasks.length,
      active: count(['queued', 'planning', 'running', 'in_progress', 'approved', 'processing', 'review']),
      approvals: count(['awaiting_approval']),
      failed: count(['failed', 'error', 'blocked']),
      completed: count(['completed', 'done']),
    };
  }

  function projectCount(overview, view) {
    const value = Number(overview?.projects);
    if (Number.isFinite(value) && value >= 0) return value;
    const rendered = Number(qs('#metrics .overview-metric.projects strong', view)?.textContent || 0);
    return Number.isFinite(rendered) && rendered >= 0 ? rendered : 0;
  }

  function applyTruthfulSnapshot(overview = {}) {
    const view = qs('#overview-view');
    if (!view) return;

    const snapshot = recentSnapshot();
    const projects = projectCount(overview, view);
    const completionRate = snapshot.total
      ? Math.round((snapshot.completed / snapshot.total) * 100)
      : 0;
    const scope = snapshot.total === 1
      ? '1 execução mais recente'
      : `${snapshot.total} execuções mais recentes`;

    const metrics = qs('#metrics', view);
    if (metrics) {
      const values = [
        ['Projetos', projects, 'Projetos registrados', 'projects'],
        ['Em andamento', snapshot.active, `No recorte de ${scope}`, 'active'],
        ['Aguardando você', snapshot.approvals, `No recorte de ${scope}`, 'approval'],
        ['Concluídas recentes', snapshot.completed, `No recorte de ${scope}`, 'completed'],
      ];
      metrics.innerHTML = values.map(([name, value, detail, tone]) => `
        <article class="metric overview-metric ${tone}">
          <span>${name}</span><strong>${value}</strong><small>${detail}</small>
        </article>
      `).join('');
    }

    const summary = qs('#overview-summary', view);
    if (summary) {
      summary.textContent = snapshot.total
        ? `Visão operacional das ${scope}. Os números históricos não são misturados com este painel.`
        : 'Nenhuma execução recente foi carregada. Atualize o painel para consultar o estado atual.';
    }

    const attention = qs('#attention-card', view);
    if (attention) {
      let content;
      if (snapshot.approvals) {
        content = ['✓', 'AGUARDANDO SUA DECISÃO', `${snapshot.approvals} aprovação(ões) recente(s)`, 'Abra Execuções para revisar o que realmente está pendente.', 'warning'];
      } else if (snapshot.active) {
        content = ['↻', 'DEVPILOT TRABALHANDO', `${snapshot.active} execução(ões) recente(s) em andamento`, 'Você pode acompanhar cada etapa em Execuções.', 'active'];
      } else if (snapshot.failed) {
        content = ['!', 'FALHAS NO RECORTE RECENTE', `${snapshot.failed} falha(s) entre as execuções recentes`, 'Falhas históricas não são tratadas aqui como pendências atuais.', 'danger'];
      } else {
        content = ['✓', 'RECORTE RECENTE EM DIA', 'Nada exige sua atenção neste recorte', 'Novas atividades aparecerão aqui quando forem carregadas.', 'success'];
      }
      attention.className = `attention-card ${content[4]}`;
      attention.innerHTML = `<span class="attention-icon">${content[0]}</span><div><small>${content[1]}</small><strong>${content[2]}</strong><p>${content[3]}</p></div>`;
      attention.onclick = () => {
        if (snapshot.approvals || snapshot.active || snapshot.failed) {
          if (typeof showView === 'function') showView('tasks');
        }
      };
    }

    const rate = qs('#completion-rate', view);
    const bar = qs('#completion-bar', view);
    if (rate) rate.textContent = `${completionRate}%`;
    if (bar) bar.style.width = `${Math.min(100, completionRate)}%`;

    const breakdown = qs('#status-breakdown', view);
    if (breakdown) {
      breakdown.innerHTML = [
        ['Em andamento', snapshot.active, 'active'],
        ['Aguardando aprovação', snapshot.approvals, 'approval'],
        ['Com falha', snapshot.failed, 'failed'],
        ['Concluídas', snapshot.completed, 'completed'],
      ].map(([label, value, tone]) => `<span class="breakdown-item ${tone}"><i></i><b>${value}</b> ${label}</span>`).join('');
    }

    let note = qs('.dp-v21-data-note', view);
    if (!note) {
      note = document.createElement('div');
      note.className = 'dp-v21-data-note';
      const strip = qs('.operations-strip', view);
      if (strip?.parentNode) strip.insertAdjacentElement('afterend', note);
    }
    if (note) {
      note.innerHTML = `<b>Fonte do painel:</b> ${scope} carregadas por /api/ui/tasks. Projetos vêm de /api/overview. O painel não soma falhas antigas ou conclusões históricas com o estado recente.`;
    }
  }

  function patchOverviewRenderer() {
    if (window.__devpilotTruthfulOverviewPatched) return true;
    if (typeof window.renderOverview !== 'function') return false;

    const original = window.renderOverview;
    window.renderOverview = function devpilotTruthfulRenderOverview(overview) {
      const result = original.apply(this, arguments);
      window.requestAnimationFrame(() => applyTruthfulSnapshot(overview || {}));
      return result;
    };
    window.__devpilotTruthfulOverviewPatched = true;
    return true;
  }

  function install() {
    const view = qs('#overview-view');
    if (!view) return false;

    if (view.dataset.dashboardV21 !== '1') {
      view.dataset.dashboardV21 = '1';
      view.classList.add('dp-dashboard-v21');

      const command = qs('.command-center', view);
      const topbar = document.createElement('section');
      topbar.className = 'dp-v21-topbar';
      topbar.setAttribute('aria-label', 'Central operacional');
      topbar.innerHTML = `
        <div class="dp-v21-topbar-copy">
          <small>CENTRAL OPERACIONAL</small>
          <strong>Veja o que está acontecendo, o que precisa de você e o que acabou de mudar.</strong>
        </div>
        <span class="dp-v21-live">Dados reais · recorte recente</span>`;

      if (command) view.insertBefore(topbar, command);
      else view.prepend(topbar);

      const heroEyebrow = qs('.command-center-copy .eyebrow', view);
      const heroTitle = qs('.command-center-copy h2', view);
      if (heroEyebrow) heroEyebrow.textContent = 'AGORA';
      if (heroTitle) heroTitle.textContent = 'O que está acontecendo neste momento.';

      const operationEyebrow = qs('.operation-heading .eyebrow', view);
      const operationTitle = qs('.operation-heading h3', view);
      if (operationEyebrow) operationEyebrow.textContent = 'FLUXO DAS EXECUÇÕES';
      if (operationTitle) operationTitle.textContent = 'Recorte recente, sem misturar histórico';

      const activityEyebrow = qs('.activity-panel .panel-title .eyebrow', view);
      const activityTitle = qs('.activity-panel .panel-title h3', view);
      if (activityEyebrow) activityEyebrow.textContent = 'ÚLTIMAS MUDANÇAS';
      if (activityTitle) activityTitle.textContent = 'Últimas execuções';

      const quickEyebrow = qs('.quick-panel .panel-title .eyebrow', view);
      const quickTitle = qs('.quick-panel .panel-title h3', view);
      if (quickEyebrow) quickEyebrow.textContent = 'IR DIRETO';
      if (quickTitle) quickTitle.textContent = 'Ações e áreas';

      const quickExecution = [...view.querySelectorAll('.quick-action strong')]
        .find(node => /desenvolvimento|execuções/i.test(node.textContent || ''));
      if (quickExecution) quickExecution.textContent = 'Execuções';
    }

    injectStyles();
    patchOverviewRenderer();
    applyTruthfulSnapshot();
    document.documentElement.dataset.devpilotDashboard = 'v36';
    document.dispatchEvent(new CustomEvent('devpilot:dashboard-v21-ready'));
    return true;
  }

  function installWhenAvailable() {
    if (install()) return;
    console.warn('[DevPilot] Dashboard V21 aguardará o próximo evento de lifecycle.');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', installWhenAvailable, {once:true});
  } else {
    installWhenAvailable();
  }

  document.addEventListener('devpilot:dashboard-revealed', installWhenAvailable);
  document.addEventListener('devpilot:view-changed', event => {
    if (event.detail?.view === 'overview' || qs('#overview-view.active')) installWhenAvailable();
  });
})();
