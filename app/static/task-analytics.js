(() => {
  const root = () => document.querySelector('#task-analytics');
  const clean = value => String(value || '').replaceAll('_', ' ').trim();
  const normalizeStatus = value => clean(value).toLowerCase().replaceAll(' ', '_');
  const ptStatus = value => ({
    awaiting_approval:'Aguardando aprovação',queued:'Na fila',running:'Executando',
    review:'Em revisão',completed:'Concluída',failed:'Falhou',cancelled:'Cancelada',blocked:'Bloqueada'
  })[normalizeStatus(value)] || clean(value) || 'Sem status';
  const countBy = (items, selector) => items.reduce((acc,item) => {
    const key = selector(item); acc[key] = (acc[key] || 0) + 1; return acc;
  }, {});
  const taskType = task => {
    if (task.type) return clean(task.type);
    const source = String(task.source || '').toLowerCase();
    const title = String(task.title || '');
    const prompt = String(task.prompt || '');
    const lowerPrompt = prompt.toLocaleLowerCase('pt-BR');
    const text = (title + ' ' + prompt).toLocaleLowerCase('pt-BR');
    const actionSignals = [
      'correção baseada na análise',
      'correcao baseada na analise',
      'ação recomendada',
      'acao recomendada',
      'execute as correções',
      'execute as correcoes',
      'não faça uma nova análise',
      'nao faca uma nova analise'
    ];

    if (
      source === 'analysis' ||
      source === 'analysis-action' ||
      lowerPrompt.includes('[analysis-action]') ||
      lowerPrompt.includes('[analysis-run:') ||
      lowerPrompt.includes('[devpilot_stage=execute]') ||
      lowerPrompt.includes('[devpilot_stage=correct]') ||
      actionSignals.some(signal => text.includes(signal))
    ) return 'Execução';

    if (
      source === 'execution-verification' ||
      lowerPrompt.includes('[post-execution-verification]') ||
      lowerPrompt.includes('[devpilot_stage=verify]')
    ) return 'Análise';

    const mode = prompt.match(/\[DEVPILOT_MODE=([^\]]+)\]/i)?.[1]?.toLowerCase();
    if (mode === 'analysis-read-only' || mode === 'review') return 'Análise';
    if (mode === 'develop' || mode === 'fix') return 'Execução';

    return /an[aá]lis|audit|diagn[oó]st|revis/.test(text) ? 'Análise' : 'Execução';
  };
  const bars = values => {
    const entries = Object.entries(values).sort((a,b) => b[1] - a[1]);
    const max = Math.max(1, ...entries.map(([,value]) => value));
    if (!entries.length) return '<div class="task-empty-chart">Sem dados para exibir.</div>';
    return '<div class="task-bars">' + entries.map(([label,value]) =>
      '<div class="task-bar-row"><span class="task-bar-label">'+esc(label)+'</span>'+
      '<div class="task-bar-track"><div class="task-bar-fill" style="width:'+((value/max)*100).toFixed(1)+'%"></div></div>'+
      '<strong class="task-bar-value">'+value+'</strong></div>'
    ).join('') + '</div>';
  };

  const taskFromRow = row => {
    const cells = [...row.querySelectorAll('td')];
    if (cells.length < 4) return null;
    const hasTypeColumn = cells.length >= 6;
    const statusIndex = hasTypeColumn ? 3 : 2;
    const priorityIndex = hasTypeColumn ? 4 : 3;
    const title = cells[0]?.querySelector('strong')?.textContent?.trim() || '';
    const source = cells[1]?.textContent?.trim() || '';
    const type = hasTypeColumn ? cells[2]?.textContent?.trim() || '' : '';
    const statusNode = cells[statusIndex]?.querySelector('.status');
    const statusClass = [...(statusNode?.classList || [])].find(name => name !== 'status');
    const status = normalizeStatus(statusClass || statusNode?.textContent || cells[statusIndex]?.textContent);
    const priority = Number(String(cells[priorityIndex]?.textContent || '').replace(/[^0-9.-]/g, '')) || 0;
    return {title, prompt:'', source, type, status, priority};
  };

  const tasksFromTable = () => [
    ...document.querySelectorAll('#tasks-table tr.task-main-row[data-task-id], #tasks-table tr[data-task-id]')
  ].map(taskFromRow).filter(Boolean);

  const analyticsTasks = () => {
    const stateTasks = typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks : [];
    const tableTasks = tasksFromTable();
    if (!stateTasks.length && tableTasks.length) return tableTasks;
    if (tableTasks.length && tableTasks.length !== stateTasks.length) return tableTasks;
    return stateTasks.length ? stateTasks : tableTasks;
  };

  window.renderTaskAnalytics = () => {
    const target = root();
    if (!target) return;
    const tasks = analyticsTasks();
    const statusValues = countBy(tasks, task => ptStatus(task.status));
    const typeValues = countBy(tasks, taskType);
    const sourceValues = countBy(tasks, task => ({
      voice:'Voz',dashboard:'Painel',api:'API',analysis:'Análise automática',
      'analysis-action':'Execução automática','execution-verification':'Validação automática'
    })[String(task.source || '').toLowerCase()] || clean(task.source) || 'Outra');
    const completed = tasks.filter(task => normalizeStatus(task.status) === 'completed').length;
    const active = tasks.filter(task => ['awaiting_approval','queued','running','review','blocked'].includes(normalizeStatus(task.status))).length;
    const avgPriority = tasks.length ? Math.round(tasks.reduce((sum,task) => sum + Number(task.priority || 0), 0) / tasks.length) : 0;
    const priority = [
      ['Baixa · 0–39',tasks.filter(t => Number(t.priority || 0) < 40).length],
      ['Média · 40–69',tasks.filter(t => Number(t.priority || 0) >= 40 && Number(t.priority || 0) < 70).length],
      ['Alta · 70–100',tasks.filter(t => Number(t.priority || 0) >= 70).length]
    ];
    target.innerHTML =
      '<div class="task-analytics-head"><div><span class="eyebrow">VISÃO ANALÍTICA</span><h2>Gráficos das tarefas</h2></div><p>Atualizados automaticamente com os dados exibidos abaixo.</p></div>'+
      '<div class="task-kpis">'+
        '<div class="task-kpi"><span>Total</span><strong>'+tasks.length+'</strong><small>tarefas registradas</small></div>'+
        '<div class="task-kpi"><span>Em andamento</span><strong>'+active+'</strong><small>fila, execução e revisão</small></div>'+
        '<div class="task-kpi"><span>Concluídas</span><strong>'+completed+'</strong><small>'+(tasks.length ? Math.round(completed/tasks.length*100) : 0)+'% do total</small></div>'+
        '<div class="task-kpi"><span>Prioridade média</span><strong>'+avgPriority+'</strong><small>escala de 0 a 100</small></div>'+
      '</div>'+
      '<div class="task-charts-grid">'+
        '<article class="task-chart"><h3>Tarefas por status</h3>'+bars(statusValues)+'</article>'+
        '<article class="task-chart"><h3>Análise × execução</h3>'+bars(typeValues)+'</article>'+
        '<article class="task-chart"><h3>Origem das tarefas</h3>'+bars(sourceValues)+'</article>'+
        '<article class="task-chart"><h3>Distribuição de prioridade</h3><div class="task-priority">'+priority.map(([label,value]) => '<div class="task-priority-item"><i></i><strong>'+value+'</strong><span>'+label+'</span></div>').join('')+'</div></article>'+
      '</div>';
  };

  const observeTasks = () => {
    const table = document.querySelector('#tasks-table');
    if (!table || table.dataset.analyticsObserved === '1') return;
    table.dataset.analyticsObserved = '1';
    let scheduled = false;
    new MutationObserver(() => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        window.renderTaskAnalytics();
      });
    }).observe(table, {childList:true, subtree:true, characterData:true});
  };

  const boot = () => {
    observeTasks();
    window.renderTaskAnalytics();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();

/*
 * Legacy game/system assets used to be appended synchronously as soon as the
 * analytics module loaded. That bypassed the authenticated boot scheduler and
 * produced a burst of compilation, observers and duplicate build-game code on
 * the main thread. Keep compatibility, but only after the main UI is ready and
 * load one asset at a time during idle periods.
 */
(() => {
  'use strict';
  const LEGACY_GAME_EXTRAS = [
    {name:'system-tests.js', marker:'system-tests-loader'},
    {name:'build-game-subphases.js', marker:'build-game-subphases-loader'},
    {name:'build-game-new-session.js', marker:'build-game-new-session-loader'},
    {name:'build-game-url-bonus.js', marker:'build-game-url-bonus-loader'},
    {name:'build-game-weapons.js', marker:'build-game-weapons-loader'},
  ];
  const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms));
  const whenIdle = () => new Promise(resolve => {
    if ('requestIdleCallback' in window) window.requestIdleCallback(() => resolve(), {timeout: 2200});
    else window.setTimeout(resolve, 220);
  });
  const tokenExists = () => Boolean(localStorage.getItem('devpilot-token'));

  function alreadyLoaded(name) {
    return [...document.scripts].some(script => {
      if (!script.src) return false;
      try { return new URL(script.src, location.href).pathname === `/assets/${name}`; }
      catch (_) { return false; }
    });
  }

  function loadAsset(asset) {
    if (!tokenExists() || alreadyLoaded(asset.name) || document.querySelector(`script[data-${asset.marker}]`)) {
      return Promise.resolve(true);
    }
    return new Promise(resolve => {
      const script = document.createElement('script');
      script.src = `/assets/${asset.name}?v=20260825-postboot1`;
      script.async = false;
      script.dataset[asset.marker.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = 'true';
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.body.appendChild(script);
    });
  }

  async function loadLegacyExtras() {
    if (!tokenExists()) return;
    await sleep(1200);
    for (const asset of LEGACY_GAME_EXTRAS) {
      if (!tokenExists()) break;
      while (document.hidden && tokenExists()) await sleep(1200);
      await whenIdle();
      await loadAsset(asset);
      await sleep(450);
    }
  }

  const start = () => { void loadLegacyExtras(); };
  if (window.__devpilotBoot?.phase === 'ready') start();
  else document.addEventListener('devpilot:authenticated-ui-ready', start, {once:true});
})();

/* Compatibility guard: old workers could leave successful game tasks in review forever. */
(() => {
  if (typeof api !== 'function' || api.__buildGameReviewCompat) return;
  const baseApi = api;
  const wrappedApi = async (path, options = {}) => {
    const data = await baseApi(path, options);
    if (typeof path !== 'string' || !path.startsWith('/tasks?') || !Array.isArray(data)) return data;
    return data.map(task => {
      const gameTask = String(task?.prompt || '').includes('[DEVPILOT_BUILD_GAME_V1]');
      const legacyReview = String(task?.status || '').toLowerCase() === 'review';
      if (gameTask && legacyReview && task?.requires_approval !== true) return {...task, status:'completed'};
      return task;
    });
  };
  wrappedApi.__buildGameReviewCompat = true;
  api = wrappedApi;
})();
