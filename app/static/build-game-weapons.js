/* DevPilot Build Game weapons workshop: every real analysis/action becomes a ship weapon. */
(() => {
  'use strict';

  const PROJECT_KEY = 'devpilot-build-game-project';
  const WORKSHOP_ATTR = 'data-build-game-weapons-workshop';
  const STYLE_ID = 'build-game-weapons-workshop-style';
  const ACTIVE_STATUSES = new Set(['awaiting_approval', 'queued', 'running', 'review']);
  const MISS_STATUSES = new Set(['failed', 'cancelled']);

  const WEAPONS = [
    {key:'analysis', icon:'📡', name:'Radar de análise', action:'Análise', description:'Mapeia o sistema, diagnóstico, auditoria e revisão antes do disparo.'},
    {key:'correction', icon:'🎯', name:'Canhão de correção', action:'Correção', description:'Ataca defeitos confirmados, regressões e correções derivadas de análise.'},
    {key:'development', icon:'⚡', name:'Laser construtor', action:'Desenvolvimento', description:'Constrói funcionalidades, integrações e novas capacidades do projeto.'},
    {key:'testing', icon:'🧪', name:'Torpedo de testes', action:'Teste / validação', description:'Valida comportamento real, smoke, regressão, build e critérios de aceite.'},
    {key:'security', icon:'🛡️', name:'Escudo interceptor', action:'Segurança', description:'Detecta e bloqueia riscos de acesso, autorização, segredos e infraestrutura.'},
    {key:'deploy', icon:'🚀', name:'Míssil de deploy', action:'Deploy', description:'Leva uma versão validada até homologação ou publicação controlada.'},
    {key:'infrastructure', icon:'🛰️', name:'Drone de infraestrutura', action:'Infraestrutura / Linux', description:'Provisiona e opera recursos de ambiente, cloud, Linux e serviços de apoio.'},
    {key:'execution', icon:'💥', name:'Canhão de execução', action:'Execução / comando', description:'Representa ações operacionais que não pertencem a uma especialidade acima.'},
  ];

  const WEAPON_BY_KEY = Object.fromEntries(WEAPONS.map(item => [item.key, item]));
  let workshopOpen = false;
  let requestedProjectId = '';
  let requestSequence = 0;
  let lastLoadedProjectId = '';

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[char]);
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');
  const cleanText = value => String(value || '').toLocaleLowerCase('pt-BR');
  const toastMessage = message => { if (typeof toast === 'function') toast(message); };

  function installStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .project-actions [data-project-weapons],#projects-list [data-project-weapons]{border-color:rgba(255,174,76,.45);background:rgba(77,42,8,.38);color:#ffd28b}
      .build-game-cockpit [data-cockpit-weapons]{border-color:rgba(255,174,76,.42);color:#ffd28b}
      .build-game-weapons-workshop{display:grid;gap:14px;padding:18px;border:1px solid rgba(255,174,76,.28);border-radius:18px;background:radial-gradient(circle at 88% 5%,rgba(255,164,67,.12),transparent 34%),linear-gradient(145deg,rgba(20,13,7,.96),rgba(4,12,20,.98));box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}
      .build-game-weapons-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}
      .build-game-weapons-head h2{margin:4px 0 6px;font-size:clamp(1.35rem,3vw,2rem)}
      .build-game-weapons-head p{max-width:760px;margin:0;color:var(--muted,#9eacc2);font-size:.78rem;line-height:1.55}
      .build-game-weapons-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
      .build-game-weapons-summary{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:9px}
      .build-game-weapons-stat{padding:12px;border:1px solid rgba(255,255,255,.08);border-radius:13px;background:rgba(5,14,23,.72)}
      .build-game-weapons-stat span{display:block;font-size:.61rem;font-weight:800;letter-spacing:.08em;color:#a58e72;text-transform:uppercase}
      .build-game-weapons-stat strong{display:block;margin-top:5px;font-size:1.45rem;color:#fff1da}
      .build-game-weapons-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
      .build-game-weapon-card{display:grid;gap:9px;min-width:0;padding:13px;border:1px solid rgba(255,174,76,.16);border-radius:15px;background:linear-gradient(150deg,rgba(24,24,27,.78),rgba(6,13,21,.94))}
      .build-game-weapon-card[data-used="1"]{border-color:rgba(255,174,76,.34)}
      .build-game-weapon-title{display:flex;gap:9px;align-items:center;min-width:0}.build-game-weapon-icon{display:grid;place-items:center;width:38px;height:38px;flex:0 0 auto;border-radius:11px;background:rgba(255,174,76,.09);font-size:1.15rem}.build-game-weapon-title div{min-width:0}.build-game-weapon-title strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#fff2dc}.build-game-weapon-title small{display:block;margin-top:2px;color:#a58e72;font-size:.61rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase}
      .build-game-weapon-card p{margin:0;color:var(--muted,#8fa0af);font-size:.69rem;line-height:1.45}
      .build-game-weapon-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.build-game-weapon-metrics div{padding:7px;border-radius:9px;background:rgba(255,255,255,.035)}.build-game-weapon-metrics span{display:block;color:#7f8d99;font-size:.55rem;text-transform:uppercase}.build-game-weapon-metrics strong{display:block;margin-top:2px;color:#e8eef2;font-size:.86rem}
      .build-game-weapon-maturity{display:flex;align-items:center;justify-content:space-between;gap:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,.06);font-size:.63rem;color:#8796a2}.build-game-weapon-maturity b{color:#ffd28b}
      .build-game-weapon-last{min-width:0;color:#8595a1;font-size:.62rem}.build-game-weapon-last b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#cbd4da;margin-bottom:2px}
      .build-game-weapons-log{padding:12px;border:1px solid rgba(255,255,255,.07);border-radius:14px;background:rgba(4,12,20,.66)}.build-game-weapons-log h3{margin:0 0 8px;font-size:.92rem}.build-game-weapon-log-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.05);font-size:.68rem}.build-game-weapon-log-row:last-child{border-bottom:0}.build-game-weapon-log-row small{display:block;margin-top:2px;color:#7e8e9a}.build-game-weapon-log-row b{color:#ffd28b}.build-game-weapons-empty{padding:14px;color:#93a0aa;font-size:.72rem;text-align:center}
      .build-game-weapons-error{padding:12px;border:1px solid rgba(255,106,106,.25);border-radius:12px;color:#e2a7a7;background:rgba(61,13,13,.18);font-size:.72rem}
      @media(max-width:1050px){.build-game-weapons-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.build-game-weapons-summary{grid-template-columns:repeat(3,minmax(0,1fr))}}
      @media(max-width:700px){.build-game-weapons-head{flex-direction:column}.build-game-weapons-actions{justify-content:flex-start}.build-game-weapons-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.build-game-weapons-grid{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  function classifyTask(task) {
    const source = normalize(task?.source);
    const title = cleanText(task?.title);
    const prompt = cleanText(task?.prompt);
    const type = cleanText(task?.type);
    const text = `${type} ${source} ${title} ${prompt}`;
    const mode = prompt.match(/\[devpilot_mode=([^\]]+)\]/i)?.[1]?.toLowerCase() || '';

    if (/seguran|security|authz|authn|vulnerab|secret|permiss|acesso/.test(text)) return 'security';
    if (/deploy|homolog|publica[cç][aã]o|release|vercel|render/.test(text)) return 'deploy';
    if (/infra|linux|cloud|docker|container|servidor|provision/.test(text)) return 'infrastructure';
    if (source === 'execution-verification' || /\[post-execution-verification\]|\[devpilot_stage=verify\]|\btest|teste|pytest|smoke|lint|build|valida[cç]/.test(text)) return 'testing';
    if (mode === 'fix' || /corre[cç]|corrigir|bug|falha|regress/.test(text)) return 'correction';
    if (source === 'analysis-action' || /\[analysis-action\]|\[devpilot_stage=(execute|correct)\]/.test(prompt)) return 'correction';
    if (mode === 'analysis-read-only' || mode === 'review' || /an[aá]lis|diagn[oó]st|audit|revis[aã]o|review/.test(text)) return 'analysis';
    if (mode === 'develop' || /desenvolv|implementar|criar|feature|integra[cç][aã]o|construir/.test(text)) return 'development';
    return 'execution';
  }

  function maturity(completed) {
    if (completed >= 6) return 'Avançada';
    if (completed >= 3) return 'Operacional';
    if (completed >= 1) return 'Calibração';
    return 'Protótipo';
  }

  function groupTasks(tasks) {
    const groups = Object.fromEntries(WEAPONS.map(item => [item.key, []]));
    tasks.forEach(task => groups[classifyTask(task)]?.push(task));
    return groups;
  }

  function stats(tasks) {
    const total = tasks.length;
    const hits = tasks.filter(task => normalize(task?.status) === 'completed').length;
    const misses = tasks.filter(task => MISS_STATUSES.has(normalize(task?.status))).length;
    const inFlight = tasks.filter(task => ACTIVE_STATUSES.has(normalize(task?.status))).length;
    const blocked = tasks.filter(task => normalize(task?.status) === 'blocked').length;
    const resolved = hits + misses;
    const accuracy = resolved ? Math.round((hits / resolved) * 100) : 0;
    return {total, hits, misses, inFlight, blocked, resolved, accuracy};
  }

  function projectIdFromView(view) {
    return String(view?.querySelector('#build-game-project')?.value || requestedProjectId || localStorage.getItem(PROJECT_KEY) || '').trim();
  }

  function statusLabel(value) {
    return ({
      awaiting_approval:'aguardando aprovação', queued:'na fila', running:'em voo', review:'em revisão',
      completed:'acertou o alvo', failed:'errou o alvo', cancelled:'cancelado', blocked:'travado'
    })[normalize(value)] || normalize(value) || 'sem status';
  }

  function weaponCard(weapon, tasks) {
    const data = stats(tasks);
    const last = [...tasks].sort((a,b) => new Date(b?.created_at || 0) - new Date(a?.created_at || 0))[0];
    return `<article class="build-game-weapon-card" data-weapon="${weapon.key}" data-used="${data.total ? '1' : '0'}">
      <div class="build-game-weapon-title"><span class="build-game-weapon-icon" aria-hidden="true">${weapon.icon}</span><div><strong>${esc(weapon.name)}</strong><small>${esc(weapon.action)}</small></div></div>
      <p>${esc(weapon.description)}</p>
      <div class="build-game-weapon-metrics">
        <div><span>Disparos</span><strong>${data.total}</strong></div>
        <div><span>Acertos</span><strong>${data.hits}</strong></div>
        <div><span>Precisão</span><strong>${data.resolved ? `${data.accuracy}%` : '—'}</strong></div>
      </div>
      <div class="build-game-weapon-maturity"><span>Maturidade por uso real</span><b>${maturity(data.hits)}</b></div>
      <div class="build-game-weapon-last">${last ? `<b>${esc(last.title || 'Ação sem título')}</b>${esc(statusLabel(last.status))}` : 'Ainda não utilizada neste projeto.'}</div>
    </article>`;
  }

  function recentLog(tasks) {
    const recent = [...tasks].sort((a,b) => new Date(b?.created_at || 0) - new Date(a?.created_at || 0)).slice(0, 8);
    if (!recent.length) return '<div class="build-game-weapons-empty">Nenhuma análise ou ação registrada ainda para este projeto.</div>';
    return recent.map(task => {
      const weapon = WEAPON_BY_KEY[classifyTask(task)] || WEAPON_BY_KEY.execution;
      return `<div class="build-game-weapon-log-row"><div><b>${weapon.icon} ${esc(weapon.name)}</b><small>${esc(task.title || 'Ação sem título')}</small></div><span>${esc(statusLabel(task.status))}</span></div>`;
    }).join('');
  }

  function workshopMarkup(tasks) {
    const data = stats(tasks);
    const groups = groupTasks(tasks);
    return `<div class="build-game-weapons-head">
      <div><span class="eyebrow">OFICINA DE ARMAS · DESENVOLVIMENTO</span><h2>⚔️ Armas da nave</h2><p>Cada análise ou ação real do DevPilot é tratada como um tipo de arma. O arsenal abaixo usa as tarefas verdadeiras do projeto: conclusão é acerto, falha/cancelamento é erro, execução é disparo em voo e bloqueio permanece travado — sem inventar resultados.</p></div>
      <div class="build-game-weapons-actions"><button class="ghost" type="button" data-weapons-refresh>Atualizar arsenal</button><button class="link" type="button" data-weapons-close>Voltar à missão</button></div>
    </div>
    <div class="build-game-weapons-summary" aria-label="Telemetria geral das armas">
      <div class="build-game-weapons-stat"><span>Disparos</span><strong>${data.total}</strong></div>
      <div class="build-game-weapons-stat"><span>Acertos</span><strong>${data.hits}</strong></div>
      <div class="build-game-weapons-stat"><span>Erros</span><strong>${data.misses}</strong></div>
      <div class="build-game-weapons-stat"><span>Em voo / travados</span><strong>${data.inFlight}/${data.blocked}</strong></div>
      <div class="build-game-weapons-stat"><span>Precisão resolvida</span><strong>${data.resolved ? `${data.accuracy}%` : '—'}</strong></div>
    </div>
    <div class="build-game-weapons-grid">${WEAPONS.map(weapon => weaponCard(weapon, groups[weapon.key])).join('')}</div>
    <section class="build-game-weapons-log"><h3>Últimos disparos · ação → arma</h3>${recentLog(tasks)}</section>`;
  }

  function ensureWorkshop(view) {
    const shell = view?.querySelector('.build-game-shell');
    if (!shell) return null;
    let workshop = shell.querySelector(`[${WORKSHOP_ATTR}]`);
    if (workshop) return workshop;
    workshop = document.createElement('section');
    workshop.className = 'build-game-weapons-workshop';
    workshop.setAttribute(WORKSHOP_ATTR, '');
    workshop.setAttribute('aria-label', 'Desenvolvimento das armas da nave');
    const cockpit = shell.querySelector('[data-build-game-cockpit]');
    if (cockpit) cockpit.insertAdjacentElement('afterend', workshop);
    else shell.prepend(workshop);
    return workshop;
  }

  function bindWorkshop(workshop, view) {
    workshop.querySelector('[data-weapons-refresh]')?.addEventListener('click', () => refreshWorkshop(view, true));
    workshop.querySelector('[data-weapons-close]')?.addEventListener('click', () => {
      workshopOpen = false;
      workshop.remove();
      const title = document.querySelector('#page-title');
      if (title) title.textContent = 'Jogo de construção';
    });
  }

  async function refreshWorkshop(view, force = false) {
    if (!workshopOpen || !view) return;
    const projectId = projectIdFromView(view);
    const workshop = ensureWorkshop(view);
    if (!workshop) return;
    if (!projectId) {
      workshop.innerHTML = '<div class="build-game-weapons-error">Selecione um projeto para abrir o arsenal.</div>';
      return;
    }
    if (!force && lastLoadedProjectId === projectId && workshop.dataset.loaded === '1') return;

    const sequence = ++requestSequence;
    workshop.dataset.loaded = '0';
    workshop.innerHTML = '<div class="build-game-weapons-empty">Carregando análises e ações reais do projeto…</div>';
    try {
      const tasks = typeof api === 'function' ? await api(`/tasks?project_id=${encodeURIComponent(projectId)}&limit=500`) : [];
      if (sequence !== requestSequence || !workshop.isConnected) return;
      const projectTasks = Array.isArray(tasks) ? tasks : [];
      workshop.innerHTML = workshopMarkup(projectTasks);
      workshop.dataset.loaded = '1';
      lastLoadedProjectId = projectId;
      bindWorkshop(workshop, view);
    } catch (error) {
      if (sequence !== requestSequence || !workshop.isConnected) return;
      workshop.innerHTML = `<div class="build-game-weapons-error">Arsenal indisponível: ${esc(error?.message || 'falha ao carregar tarefas')}</div>`;
    }
  }

  function openWorkshop(view) {
    if (!view) return;
    workshopOpen = true;
    lastLoadedProjectId = '';
    const title = document.querySelector('#page-title');
    if (title) title.textContent = 'Armas da nave';
    const workshop = ensureWorkshop(view);
    void refreshWorkshop(view, true).then(() => {
      const current = view.querySelector(`[${WORKSHOP_ATTR}]`) || workshop;
      current?.scrollIntoView({behavior:'smooth', block:'start'});
    });
  }

  function openProjectWeapons(projectId, sourceButton) {
    requestedProjectId = String(projectId || '').trim();
    if (requestedProjectId) localStorage.setItem(PROJECT_KEY, requestedProjectId);
    const actions = sourceButton?.parentElement;
    const gameButton = actions?.querySelector('[data-project-build-game]');
    if (gameButton) gameButton.click();
    else if (typeof showView === 'function') {
      showView('build-game');
      if (typeof window.loadBuildGame === 'function') void window.loadBuildGame();
    }
    window.setTimeout(() => {
      const view = document.querySelector('#build-game-view');
      const select = view?.querySelector('#build-game-project');
      if (select && requestedProjectId && String(select.value) !== requestedProjectId) {
        select.value = requestedProjectId;
        select.dispatchEvent(new Event('change', {bubbles:true}));
      }
      window.setTimeout(() => openWorkshop(document.querySelector('#build-game-view')), 30);
    }, 30);
  }

  function enhanceProjectCards() {
    document.querySelectorAll('#projects-list [data-project-task]').forEach(taskButton => {
      const actions = taskButton.parentElement;
      if (!actions || actions.querySelector('[data-project-weapons]')) return;
      const button = document.createElement('button');
      button.className = 'link';
      button.type = 'button';
      button.dataset.projectWeapons = taskButton.dataset.projectTask;
      button.textContent = '⚔ Armas';
      button.title = 'Abrir desenvolvimento das armas da nave';
      button.addEventListener('click', () => openProjectWeapons(button.dataset.projectWeapons, button));
      const gameButton = actions.querySelector('[data-project-build-game]');
      if (gameButton) gameButton.insertAdjacentElement('afterend', button);
      else actions.insertBefore(button, taskButton);
    });
  }

  function enhanceCockpit() {
    const view = document.querySelector('#build-game-view');
    const cockpit = view?.querySelector('[data-build-game-cockpit]');
    if (!view || !cockpit || cockpit.querySelector('[data-cockpit-weapons]')) return;
    const actions = cockpit.querySelector('.cockpit-comms-actions') || cockpit.querySelector('.build-game-cockpit-console');
    if (!actions) return;
    const button = document.createElement('button');
    button.className = 'ghost';
    button.type = 'button';
    button.dataset.cockpitWeapons = '1';
    button.textContent = '⚔ Armas';
    button.addEventListener('click', () => openWorkshop(view));
    actions.prepend(button);
  }

  function sync() {
    enhanceProjectCards();
    enhanceCockpit();
    if (workshopOpen) {
      const view = document.querySelector('#build-game-view');
      const workshop = ensureWorkshop(view);
      if (workshop && workshop.dataset.loaded !== '1') void refreshWorkshop(view, false);
    }
  }

  function boot() {
    installStyle();
    sync();
    const main = document.querySelector('main') || document.body;
    if (!main || main.dataset.buildGameWeaponsObserved === '1') return;
    main.dataset.buildGameWeaponsObserved = '1';
    let queued = false;
    new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; sync(); });
    }).observe(main, {childList:true, subtree:true});
    document.addEventListener('devpilot:build-game-new-session', () => {
      if (workshopOpen) {
        lastLoadedProjectId = '';
        void refreshWorkshop(document.querySelector('#build-game-view'), true);
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();
})();