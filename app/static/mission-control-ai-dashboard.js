(() => {
  'use strict';

  const STYLE_ID = 'mission-control-ai-dashboard-style';
  let chartFrame = 0;

  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  const getAppState = () => {
    try {
      return typeof state !== 'undefined' ? state : {projects: [], tasks: [], currentUser: null};
    } catch (_) {
      return {projects: [], tasks: [], currentUser: null};
    }
  };

  const ensureStylesheet = () => {
    if (document.querySelector(`link[data-${STYLE_ID}]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/assets/mission-control-ai-dashboard.css?v=20260829-2';
    link.setAttribute(`data-${STYLE_ID}`, '1');
    document.head.appendChild(link);
  };

  const numberFrom = value => {
    const parsed = Number(String(value ?? '').replace(/[^0-9.-]/g, ''));
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const readMetricSnapshot = target => {
    const snapshot = {};
    target.querySelectorAll(':scope > div').forEach(card => {
      const label = card.querySelector('span')?.textContent?.trim().toUpperCase();
      const value = numberFrom(card.querySelector('strong')?.textContent);
      if (!label) return;
      if (label === 'PROJETOS') snapshot.projects = value;
      if (label === 'TAREFAS') snapshot.tasks = value;
      if (label === 'EM ANDAMENTO') snapshot.active = value;
      if (label === 'CONCLUÍDAS') snapshot.completed = value;
      if (label.includes('APROVA')) snapshot.pending = value;
    });
    return snapshot;
  };

  const statusBuckets = () => {
    const tasks = getAppState().tasks || [];
    const buckets = {active: 0, completed: 0, pending: 0, failed: 0, other: 0};
    tasks.forEach(task => {
      const value = String(task?.status || '').toLowerCase();
      if (['running', 'in_progress', 'processing', 'queued'].includes(value)) buckets.active += 1;
      else if (['completed', 'done', 'success'].includes(value)) buckets.completed += 1;
      else if (['awaiting_approval', 'pending', 'review'].includes(value)) buckets.pending += 1;
      else if (['failed', 'error', 'blocked', 'cancelled', 'rejected'].includes(value)) buckets.failed += 1;
      else buckets.other += 1;
    });
    return buckets;
  };

  const recentActivityPoints = () => {
    const tasks = getAppState().tasks || [];
    const now = new Date();
    const values = Array.from({length: 7}, () => 0);
    tasks.forEach(task => {
      if (!task?.created_at) return;
      const date = new Date(task.created_at);
      if (Number.isNaN(date.getTime())) return;
      const diffDays = Math.floor((new Date(now.getFullYear(), now.getMonth(), now.getDate()) - new Date(date.getFullYear(), date.getMonth(), date.getDate())) / 86400000);
      if (diffDays >= 0 && diffDays < 7) values[6 - diffDays] += 1;
    });
    const max = Math.max(1, ...values);
    return values.map((value, index) => {
      const x = 8 + (index * 84 / 6);
      const y = 42 - (value / max) * 32;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  };

  const renderCharts = () => {
    const target = document.querySelector('#mc-metrics');
    if (!target || target.querySelector('.mc-chart-grid')) return;

    const snapshot = readMetricSnapshot(target);
    const buckets = statusBuckets();
    const total = snapshot.tasks || (buckets.active + buckets.completed + buckets.pending + buckets.failed + buckets.other);
    const completed = snapshot.completed || buckets.completed;
    const active = snapshot.active || buckets.active;
    const pending = snapshot.pending || buckets.pending;
    const failed = buckets.failed;
    const other = Math.max(0, total - completed - active - pending - failed);
    const completion = total > 0 ? Math.max(0, Math.min(100, Math.round((completed / total) * 100))) : 0;

    const categories = [
      ['Concluídas', completed, 'ok'],
      ['Em andamento', active, 'active'],
      ['Aguardando', pending, 'warning'],
      ['Falhas', failed, 'danger'],
      ['Outras', other, 'neutral'],
    ].filter(([, value]) => value > 0);
    const safeTotal = Math.max(1, categories.reduce((sum, [, value]) => sum + value, 0));

    target.innerHTML = `
      <div class="mc-chart-grid" aria-label="Gráficos operacionais">
        <article class="mc-chart-card mc-chart-progress">
          <div class="mc-chart-heading"><span>PROGRESSO</span><small>fluxo concluído</small></div>
          <div class="mc-donut" style="--mc-progress:${completion * 3.6}deg" role="img" aria-label="${completion}% das tarefas concluídas">
            <div><strong>${completion}%</strong><span>concluído</span></div>
          </div>
        </article>

        <article class="mc-chart-card mc-chart-status">
          <div class="mc-chart-heading"><span>DISTRIBUIÇÃO</span><small>estado das missões</small></div>
          <div class="mc-stacked-chart" role="img" aria-label="Distribuição das tarefas por estado">
            ${categories.map(([label, value, tone]) => `<i class="${tone}" style="flex:${Math.max(1, value)}" title="${escapeHtml(label)}: ${value}"></i>`).join('') || '<i class="neutral" style="flex:1"></i>'}
          </div>
          <div class="mc-chart-legend">
            ${categories.map(([label, value, tone]) => `<span><i class="${tone}"></i>${escapeHtml(label)} <small>${Math.round((value / safeTotal) * 100)}%</small></span>`).join('') || '<span><i class="neutral"></i>Sem tarefas</span>'}
          </div>
        </article>

        <article class="mc-chart-card mc-chart-activity">
          <div class="mc-chart-heading"><span>RITMO</span><small>atividade recente</small></div>
          <svg viewBox="0 0 100 50" role="img" aria-label="Atividade recente em sete dias" preserveAspectRatio="none">
            <path d="M8 42H92" class="mc-chart-axis"></path>
            <polyline points="${recentActivityPoints()}" class="mc-chart-line"></polyline>
          </svg>
          <div class="mc-chart-days"><span>-6d</span><span>hoje</span></div>
        </article>
      </div>
    `;
  };

  const scheduleCharts = () => {
    if (chartFrame) cancelAnimationFrame(chartFrame);
    chartFrame = requestAnimationFrame(() => {
      chartFrame = 0;
      renderCharts();
    });
  };

  const observeMetrics = () => {
    const target = document.querySelector('#mc-metrics');
    if (!target || target.dataset.aiChartsObserved === '1') return;
    target.dataset.aiChartsObserved = '1';
    new MutationObserver(scheduleCharts).observe(target, {childList: true, subtree: true, characterData: true});
    scheduleCharts();
  };

  const openCanonicalChat = () => {
    if (typeof window.devpilotOpenChat === 'function') {
      void window.devpilotOpenChat();
      return;
    }

    const modal = document.querySelector('#voice-modal');
    if (modal && !modal.open) modal.showModal?.();
    void window.__devpilotLoadFeature?.('voice');
  };

  const createChatLaunchers = () => {
    if (!document.querySelector('#mc-ai-launcher')) {
      const launcher = document.createElement('button');
      launcher.id = 'mc-ai-launcher';
      launcher.className = 'mc-ai-launcher';
      launcher.type = 'button';
      launcher.setAttribute('aria-label', 'Abrir Chat DevPilot');
      launcher.setAttribute('title', 'Chat DevPilot');
      launcher.innerHTML = '<span aria-hidden="true">✦</span><strong>IA</strong>';
      launcher.addEventListener('click', openCanonicalChat);
      document.body.appendChild(launcher);
    }

    const headerActions = document.querySelector('header .header-actions');
    if (headerActions && !document.querySelector('#mc-ai-header-button')) {
      const button = document.createElement('button');
      button.id = 'mc-ai-header-button';
      button.className = 'ghost mc-ai-header-button';
      button.type = 'button';
      button.textContent = '✦ Chat IA';
      button.setAttribute('aria-label', 'Abrir Chat DevPilot');
      button.addEventListener('click', openCanonicalChat);
      headerActions.prepend(button);
    }
  };

  const bindKeyboardShortcut = () => {
    if (document.documentElement.dataset.mcAiChatShortcut === '1') return;
    document.documentElement.dataset.mcAiChatShortcut = '1';
    document.addEventListener('keydown', event => {
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'i') {
        event.preventDefault();
        openCanonicalChat();
      }
    });
  };

  const init = () => {
    ensureStylesheet();
    createChatLaunchers();
    observeMetrics();
    bindKeyboardShortcut();

    const panel = document.querySelector('#mission-control-panel');
    if (panel && panel.dataset.aiDashboardObserved !== '1') {
      panel.dataset.aiDashboardObserved = '1';
      new MutationObserver(() => {
        observeMetrics();
        scheduleCharts();
      }).observe(panel, {childList: true, subtree: true});
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
