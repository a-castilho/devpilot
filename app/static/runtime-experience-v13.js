(() => {
  'use strict';

  if (window.__devpilotRuntimeExperienceV13) return;
  window.__devpilotRuntimeExperienceV13 = true;

  const PROJECT_LIMIT = 100;
  const RECENT_MENU_KEY = 'devpilot-smart-menu-recent-v13';
  const detailCache = new Map();
  let projectOptionsPromise = null;
  let projectOptions = [];

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));

  function token() {
    return String(localStorage.getItem('devpilot-token') || '');
  }

  async function getJson(path) {
    const response = await fetch(`/api${path}`, {
      headers: {Authorization: `Bearer ${token()}`},
      cache: 'no-store',
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = typeof data?.detail === 'string'
        ? data.detail
        : 'Falha ao carregar dados';
      throw new Error(message);
    }
    return data;
  }

  function injectStyles() {
    if (document.querySelector('#devpilot-runtime-experience-v13-style')) return;
    const style = document.createElement('style');
    style.id = 'devpilot-runtime-experience-v13-style';
    style.textContent = `
      .dp-v13-decision{display:grid;gap:12px;width:100%;box-sizing:border-box;padding:14px;border:1px solid rgba(53,229,209,.24);border-radius:14px;background:linear-gradient(145deg,rgba(4,30,31,.88),rgba(6,16,27,.97))}
      .dp-v13-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}.dp-v13-head small{display:block;color:#58dfcb;font-size:9px;font-weight:900;letter-spacing:.09em}.dp-v13-head h3{margin:4px 0;color:#f2fbfa;font-size:22px;line-height:1.08}.dp-v13-head p{margin:0;color:#92a9aa;font-size:12px;line-height:1.45}
      .dp-v13-recs{display:grid;gap:8px}.dp-v13-rec{display:grid;grid-template-columns:44px minmax(0,1fr);gap:10px;padding:11px;border:1px solid rgba(255,255,255,.07);border-radius:11px;background:rgba(2,11,19,.72)}
      .dp-v13-priority{display:grid;min-height:34px;place-items:center;align-self:start;border-radius:9px;color:#73e4d2;background:rgba(53,229,209,.1);font-size:11px;font-weight:950}.dp-v13-rec[data-priority="P0"] .dp-v13-priority{color:#ff9786;background:rgba(255,110,87,.11)}.dp-v13-rec[data-priority="P1"] .dp-v13-priority{color:#ffd171;background:rgba(255,191,74,.1)}
      .dp-v13-rec strong{display:block;color:#edf5f7;font-size:14px;line-height:1.35}.dp-v13-rec p{margin:5px 0 0;color:#a1b4bd;font-size:12px;line-height:1.5}
      .dp-v13-tech{border-top:1px solid rgba(255,255,255,.06);padding-top:9px}.dp-v13-tech summary{cursor:pointer;color:#8fa6b1;font-size:11px;font-weight:800}.dp-v13-facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:10px}.dp-v13-facts>div{min-width:0;padding:8px;border-radius:8px;background:rgba(255,255,255,.025)}.dp-v13-facts small{display:block;color:#708898;font-size:8px;font-weight:850}.dp-v13-facts strong{display:block;margin-top:3px;overflow:hidden;color:#c4d2d9;font-size:10px;text-overflow:ellipsis;white-space:nowrap}.dp-v13-tech pre{max-height:220px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;margin:9px 0 0;padding:10px;border-radius:9px;color:#9fb2bc;background:#06111b;font-size:11px;line-height:1.5}
      #tasks-view .task-details-row[hidden],#tasks-view .task-instructions-row[hidden],#tasks-view .task-inline-details[hidden]{display:none!important;height:0!important;min-height:0!important;margin:0!important;padding:0!important;overflow:hidden!important}
      #tasks-view .tasks-v9-details.dp-v13-open,#tasks-view .task-instructions-load.dp-v13-open{color:#66e2cc!important;border-color:rgba(53,229,209,.34)!important;background:rgba(53,229,209,.08)!important}
      .dp-smart-tools{display:grid;gap:9px;padding:8px 10px 10px}.dp-smart-current{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:11px;border:1px solid rgba(53,229,209,.18);border-radius:13px;background:rgba(53,229,209,.055)}.dp-smart-current small,.dp-smart-current strong{display:block}.dp-smart-current small{color:#698d8a;font-size:8px;font-weight:900;letter-spacing:.08em}.dp-smart-current strong{margin-top:3px;overflow:hidden;color:#eaf8f5;font-size:14px;text-overflow:ellipsis;white-space:nowrap}.dp-smart-current button{min-height:38px!important;padding:7px 10px!important;font-size:10px!important}
      .dp-smart-search{display:grid;grid-template-columns:32px minmax(0,1fr);align-items:center;min-height:46px;border:1px solid rgba(93,130,155,.28);border-radius:12px;background:#071521}.dp-smart-search span{display:grid;place-items:center;color:#58daca;font-size:18px}.dp-smart-search input{width:100%;min-width:0;min-height:44px;border:0!important;outline:0!important;background:transparent!important;color:#e4edf2!important;font-size:14px!important}
      .dp-smart-section{margin:3px 0 14px}.dp-smart-section h3{margin:3px 6px 6px;color:#6c8294;font-size:9px;font-weight:900;letter-spacing:.09em;text-transform:uppercase}.dp-smart-row-copy{display:block;min-width:0}.dp-smart-row-copy strong,.dp-smart-row-copy small{display:block}.dp-smart-row-copy strong{overflow:hidden;font-size:13px;text-overflow:ellipsis;white-space:nowrap}.dp-smart-row-copy small{margin-top:2px;color:#657d90;font-size:9px}.dp-smart-empty{padding:24px 12px;color:#71889a;text-align:center;font-size:12px}
      @media(max-width:900px){html,body,.shell,main,.view,.view.active{max-width:100%!important;min-width:0!important}.shell{display:block!important;width:100%!important;grid-template-columns:none!important}.sidebar{left:0!important;right:0!important;width:100vw!important;max-width:100vw!important;min-width:0!important;transform:none!important}.mobile-simple-nav{width:100%!important;max-width:100%!important;grid-template-columns:repeat(4,minmax(0,1fr))!important}.mobile-simple-sheet{left:8px!important;right:8px!important;width:auto!important;max-width:none!important;max-height:82dvh!important;border-radius:20px!important}.mobile-simple-list{display:block!important}.mobile-simple-row{grid-template-columns:38px minmax(0,1fr) 22px!important;min-height:56px!important;margin-bottom:5px;border-radius:12px!important}.mobile-simple-row.active{border-color:rgba(53,229,209,.28)!important;background:rgba(53,229,209,.08)!important}.dp-v13-decision{padding:12px}.dp-v13-head h3{font-size:21px}.dp-v13-rec{grid-template-columns:40px minmax(0,1fr)}.dp-v13-rec strong{font-size:15px}.dp-v13-rec p{font-size:13px}.dp-v13-facts{grid-template-columns:repeat(2,minmax(0,1fr))}.dp-v13-tech pre{max-height:190px;font-size:13px}}
    `;
    document.head.appendChild(style);
  }

  function cleanMarkdown(value) {
    return String(value || '')
      .replace(/```[\s\S]*?```/g, '')
      .replace(/`([^`]*)`/g, '$1')
      .replace(/\*\*/g, '')
      .replace(/__/g, '')
      .replace(/^#+\s*/gm, '')
      .trim();
  }

  function simpleExplanation(title, priority) {
    let text = cleanMarkdown(title);
    const replacements = [
      [/\bisolamento\b/gi, 'separação das partes para uma não interferir na outra'],
      [/\bruntime\b/gi, 'parte do sistema que está funcionando naquele momento'],
      [/\bregressão\b/gi, 'problema novo em algo que já funcionava'],
      [/\bfallback\b/gi, 'alternativa usada quando o caminho principal falha'],
      [/\brace condition\b/gi, 'duas ações acontecendo juntas e se atrapalhando'],
      [/\bidempotência\b/gi, 'garantia de que repetir a ação não duplica resultados'],
      [/\bRBAC\b/g, 'controle do que cada tipo de usuário pode fazer'],
      [/\btimeout\b/gi, 'tempo máximo que o sistema espera'],
      [/\bendpoint\b/gi, 'ponto de comunicação com o servidor'],
      [/\blazy loading\b/gi, 'carregamento somente quando for necessário'],
    ];
    replacements.forEach(([pattern, replacement]) => {
      text = text.replace(pattern, replacement);
    });
    text = text.replace(/^(corrigir|ajustar|implementar|garantir)\s+/i, '').trim();
    const prefix = {P0: 'Faça primeiro', P1: 'Faça em seguida', P2: 'Depois melhore', P3: 'Quando possível'}[priority] || 'Recomendação';
    return `${prefix}: ${text}`;
  }

  function extractRecommendations(prompt) {
    const lines = String(prompt || '').split(/\r?\n/);
    const found = [];
    let inside = false;
    let current = null;

    const pushCurrent = () => {
      if (!current) return;
      current.title = cleanMarkdown(current.title);
      if (current.title) found.push(current);
      current = null;
    };

    for (const raw of lines) {
      const line = String(raw || '').trim();
      const heading = line.replace(/^#+\s*/, '').toLowerCase();
      if (heading.startsWith('recomendaç') || heading.startsWith('recomendac')) {
        pushCurrent();
        inside = true;
        continue;
      }
      if (inside && /^#{1,6}\s+/.test(line)) {
        pushCurrent();
        break;
      }
      if (!inside) continue;

      const bullet = line.match(/^(?:[-*•]|\d+[.)])\s*(.+)$/);
      if (bullet) {
        pushCurrent();
        let content = cleanMarkdown(bullet[1]);
        const match = content.match(/^(P[0-3])\s*[—–:\-]\s*(.+)$/i);
        current = {
          priority: match ? match[1].toUpperCase() : 'P2',
          title: match ? match[2] : content,
        };
        continue;
      }
      if (current && line) current.title += ` ${cleanMarkdown(line)}`;
    }
    pushCurrent();

    if (!found.length) {
      lines.forEach(raw => {
        const line = cleanMarkdown(String(raw || '').trim().replace(/^(?:[-*•]|\d+[.)])\s*/, ''));
        const match = line.match(/^(P[0-3])\s*[—–:\-]\s*(.+)$/i);
        if (match) found.push({priority: match[1].toUpperCase(), title: match[2]});
      });
    }

    const order = {P0: 0, P1: 1, P2: 2, P3: 3};
    return found.sort((a, b) => (order[a.priority] ?? 9) - (order[b.priority] ?? 9)).slice(0, 8);
  }

  function technicalContext(prompt) {
    const lines = String(prompt || '').split(/\r?\n/);
    const out = [];
    let skipping = false;
    for (const raw of lines) {
      const line = String(raw || '');
      const clean = line.trim();
      const heading = clean.replace(/^#+\s*/, '').toLowerCase();
      if (heading.startsWith('recomendaç') || heading.startsWith('recomendac')) {
        skipping = true;
        continue;
      }
      if (skipping && /^#{1,6}\s+/.test(clean)) skipping = false;
      if (!skipping) out.push(line);
    }
    return cleanMarkdown(out.join('\n')) || 'Sem contexto técnico adicional.';
  }

  function formatDate(value) {
    if (!value) return '—';
    try {
      return new Date(value).toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'});
    } catch (_) {
      return String(value);
    }
  }

  function decisionHtml(task) {
    const recommendations = extractRecommendations(task.prompt);
    const recs = recommendations.length
      ? recommendations.map(item => `
          <article class="dp-v13-rec" data-priority="${esc(item.priority)}">
            <span class="dp-v13-priority">${esc(item.priority)}</span>
            <div><strong>${esc(item.title)}</strong><p>${esc(simpleExplanation(item.title, item.priority))}</p></div>
          </article>`).join('')
      : `<article class="dp-v13-rec"><span class="dp-v13-priority">✓</span><div><strong>Nenhuma recomendação específica</strong><p>Esta tarefa não registrou ações prioritárias. O contexto técnico continua disponível abaixo.</p></div></article>`;

    return `
      <section class="dp-v13-decision">
        <header class="dp-v13-head"><div><small>RECOMENDAÇÕES · O MAIS IMPORTANTE</small><h3>O que fazer agora</h3><p>A análise foi organizada em decisões simples, na ordem de prioridade.</p></div></header>
        <div class="dp-v13-recs">${recs}</div>
        <details class="dp-v13-tech">
          <summary>Ver explicação técnica completa</summary>
          <div class="dp-v13-facts">
            <div><small>Projeto</small><strong>${esc(task.project_name || 'Projeto')}</strong></div>
            <div><small>Origem</small><strong>${esc(task.source || 'DevPilot')}</strong></div>
            <div><small>Criada</small><strong>${esc(formatDate(task.created_at))}</strong></div>
            <div><small>Atualizada</small><strong>${esc(formatDate(task.updated_at))}</strong></div>
          </div>
          <pre>${esc(technicalContext(task.prompt))}</pre>
        </details>
      </section>`;
  }

  function closeAllDetails(except = null) {
    document.querySelectorAll('[data-task-details-row], .task-inline-details').forEach(element => {
      if (element === except) return;
      element.hidden = true;
      element.style.setProperty('display', 'none', 'important');
      const id = element.dataset.taskDetailsRow || element.dataset.taskInstructions || '';
      if (!id) return;
      const button = document.querySelector(`.tasks-v9-details[data-id="${CSS.escape(id)}"], .task-instructions-load[data-id="${CSS.escape(id)}"]`);
      if (button) {
        button.textContent = 'Detalhes';
        button.setAttribute('aria-expanded', 'false');
        button.classList.remove('dp-v13-open');
      }
    });
  }

  async function toggleDetails(button) {
    const id = String(button.dataset.id || '');
    if (!id) return;

    const detailRow = document.querySelector(`[data-task-details-row="${CSS.escape(id)}"]`);
    const detailPanel = document.querySelector(`[data-task-details="${CSS.escape(id)}"]`);
    const inlinePanel = document.querySelector(`[data-task-instructions="${CSS.escape(id)}"]`);
    const container = detailRow || inlinePanel;
    const panel = detailPanel || inlinePanel;
    if (!container || !panel) return;

    const open = container.dataset.dpV13Open === '1';
    if (open) {
      container.dataset.dpV13Open = '0';
      container.hidden = true;
      container.style.setProperty('display', 'none', 'important');
      button.textContent = 'Detalhes';
      button.setAttribute('aria-expanded', 'false');
      button.classList.remove('dp-v13-open');
      return;
    }

    closeAllDetails(container);
    container.dataset.dpV13Open = '1';
    container.hidden = false;
    container.style.removeProperty('display');
    button.textContent = 'Ocultar';
    button.setAttribute('aria-expanded', 'true');
    button.classList.add('dp-v13-open');

    if (panel.dataset.dpV13Loaded === '1') return;
    panel.innerHTML = '<div class="dp-v13-decision">Organizando recomendações…</div>';

    try {
      let task = detailCache.get(id);
      if (!task) {
        task = await getJson(`/ui/tasks/${encodeURIComponent(id)}`);
        detailCache.set(id, task);
      }
      if (container.dataset.dpV13Open !== '1') return;
      panel.innerHTML = decisionHtml(task);
      panel.dataset.dpV13Loaded = '1';
    } catch (error) {
      panel.innerHTML = `<div class="dp-v13-decision">${esc(error.message || 'Não foi possível carregar os detalhes.')}</div>`;
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest?.('.tasks-v9-details, .task-instructions-load');
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    void toggleDetails(button);
  }, true);

  async function loadAllProjectOptions() {
    if (projectOptions.length) return projectOptions;
    if (projectOptionsPromise) return projectOptionsPromise;
    projectOptionsPromise = getJson(`/ui/projects?limit=${PROJECT_LIMIT}`)
      .then(rows => {
        projectOptions = Array.isArray(rows) ? rows : [];
        if (typeof state !== 'undefined') state.projects = projectOptions;
        return projectOptions;
      })
      .finally(() => { projectOptionsPromise = null; });
    return projectOptionsPromise;
  }

  function fillProjectSelect(select, {allLabel = false, selected = ''} = {}) {
    if (!select) return;
    const current = String(selected || select.value || '');
    select.innerHTML = [
      `<option value="">${allLabel ? 'Todos os projetos' : 'Selecione um projeto'}</option>`,
      ...projectOptions.map(project => `<option value="${esc(project.id)}">${esc(project.name)}</option>`),
    ].join('');
    if (current && projectOptions.some(project => String(project.id) === current)) select.value = current;
  }

  async function hydrateProjectCombos(selectedProjectId = '') {
    try {
      await loadAllProjectOptions();
      fillProjectSelect(document.querySelector('#tasks-v9-project'), {allLabel: true});
      fillProjectSelect(document.querySelector('#task-project'), {selected: selectedProjectId});
      fillProjectSelect(document.querySelector('#voice-project'), {selected: document.querySelector('#voice-project')?.value || ''});
    } catch (error) {
      console.warn('[DevPilot] Falha ao carregar todos os projetos', error);
    }
  }

  document.addEventListener('devpilot:tasks-rendered', () => {
    closeAllDetails();
    window.setTimeout(() => void hydrateProjectCombos(), 0);
  });

  document.addEventListener('click', event => {
    const trigger = event.target.closest?.('[data-open="task-modal"], [data-project-task]');
    if (!trigger) return;
    const selected = trigger.dataset.projectTask || '';
    window.setTimeout(() => void hydrateProjectCombos(selected), 20);
    window.setTimeout(() => void hydrateProjectCombos(selected), 180);
  }, true);

  function recentIds() {
    try {
      const value = JSON.parse(localStorage.getItem(RECENT_MENU_KEY) || '[]');
      return Array.isArray(value) ? value.slice(0, 5) : [];
    } catch (_) {
      return [];
    }
  }

  function rememberNav(item) {
    const key = item.dataset.view || item.dataset.linuxView || item.dataset.exampleProject || item.textContent.trim();
    const next = [key, ...recentIds().filter(value => value !== key)].slice(0, 5);
    localStorage.setItem(RECENT_MENU_KEY, JSON.stringify(next));
  }

  function navItems() {
    const nav = document.querySelector('.sidebar > nav');
    if (!nav) return [];
    return [...nav.querySelectorAll(':scope > .nav')].filter(item => !item.hidden && !item.classList.contains('nav-super-admin-forbidden'));
  }

  function navLabel(item) {
    return String(item.textContent || item.getAttribute('aria-label') || 'Abrir').replace(/\s+/g, ' ').trim();
  }

  function navKey(item) {
    return item.dataset.view || item.dataset.linuxView || item.dataset.exampleProject || navLabel(item);
  }

  function navGroup(item) {
    const view = String(item.dataset.view || '').toLowerCase();
    const text = navLabel(item).toLowerCase();
    if (['overview', 'projects', 'tasks', 'providers'].includes(view)) return 'Principal';
    if (text.includes('super admin') || text.includes('cloud') || text.includes('token') || text.includes('investia') || text.includes('rag') || text.includes('voz')) return 'Super Admin';
    if (['reports', 'audit', 'organizations', 'profile', 'users'].includes(view)) return 'Gestão';
    return 'Ferramentas';
  }

  function navIcon(item) {
    const icons = {overview: '⌂', projects: '▦', tasks: '✓', providers: '✦', organizations: '◎', reports: '≣', audit: '⌁'};
    if (item.dataset.exampleProject) return '◫';
    if (item.dataset.linuxView === '1') return '>_';
    return icons[item.dataset.view] || '›';
  }

  function ensureSmartMenu() {
    if (window.innerWidth > 900) return false;
    const sheet = document.querySelector('.mobile-simple-sheet');
    const list = sheet?.querySelector('.mobile-simple-list');
    if (!sheet || !list) return false;

    let tools = sheet.querySelector('.dp-smart-tools');
    if (!tools) {
      tools = document.createElement('div');
      tools.className = 'dp-smart-tools';
      tools.innerHTML = `
        <div class="dp-smart-current"><div><small>VOCÊ ESTÁ EM</small><strong>DevPilot</strong></div><button type="button" class="primary dp-smart-action">+ Nova tarefa</button></div>
        <label class="dp-smart-search"><span>⌕</span><input type="search" placeholder="Buscar tela ou função…" autocomplete="off"></label>`;
      sheet.querySelector('.mobile-simple-sheet-head')?.after(tools);
      tools.querySelector('input')?.addEventListener('input', () => renderSmartMenu(sheet));
      tools.querySelector('.dp-smart-action')?.addEventListener('click', () => {
        sheet.querySelector('.mobile-simple-close')?.click();
        window.devpilotOpenTaskModal?.({source: 'mobile-smart-menu'});
      });
    }
    renderSmartMenu(sheet);
    return true;
  }

  function renderSmartMenu(sheet) {
    const list = sheet.querySelector('.mobile-simple-list');
    const search = String(sheet.querySelector('.dp-smart-search input')?.value || '').trim().toLowerCase();
    const all = navItems();
    const filtered = all.filter(item => !search || `${navLabel(item)} ${navGroup(item)}`.toLowerCase().includes(search));
    const active = all.find(item => item.classList.contains('active'));
    const current = sheet.querySelector('.dp-smart-current strong');
    if (current) current.textContent = active ? navLabel(active) : 'DevPilot';

    const map = new Map(all.map(item => [navKey(item), item]));
    const recent = recentIds().map(key => map.get(key)).filter(Boolean).filter(item => filtered.includes(item));
    const groups = [];
    if (recent.length && !search) groups.push(['Recentes', recent]);
    ['Principal', 'Gestão', 'Super Admin', 'Ferramentas'].forEach(name => {
      const items = filtered.filter(item => navGroup(item) === name && !(recent.includes(item) && !search));
      if (items.length) groups.push([name, items]);
    });

    list.replaceChildren();
    if (!groups.length) {
      const empty = document.createElement('div');
      empty.className = 'dp-smart-empty';
      empty.textContent = 'Nenhuma função encontrada.';
      list.appendChild(empty);
      return;
    }

    groups.forEach(([name, items]) => {
      const section = document.createElement('section');
      section.className = 'dp-smart-section';
      const heading = document.createElement('h3');
      heading.textContent = name;
      section.appendChild(heading);
      items.forEach(item => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `mobile-simple-row${item.classList.contains('active') ? ' active' : ''}`;
        button.innerHTML = `<span class="mobile-simple-icon">${navIcon(item)}</span><span class="dp-smart-row-copy"><strong>${esc(navLabel(item))}</strong><small>${name}</small></span><span class="mobile-simple-arrow">›</span>`;
        button.addEventListener('click', () => {
          rememberNav(item);
          sheet.querySelector('.mobile-simple-close')?.click();
          item.click();
        });
        section.appendChild(button);
      });
      list.appendChild(section);
    });
  }

  document.addEventListener('click', event => {
    if (!event.target.closest?.('[data-simple-menu-open]')) return;
    window.setTimeout(ensureSmartMenu, 0);
    window.setTimeout(ensureSmartMenu, 60);
  });

  function bootstrapMobileMenuEnhancement(attempt = 0) {
    if (window.innerWidth > 900) return;
    if (ensureSmartMenu()) return;
    if (attempt < 50) window.setTimeout(() => bootstrapMobileMenuEnhancement(attempt + 1), 120);
  }

  function loadAdaptiveV15() {
    if (
      window.__devpilotViewportAdaptiveV15 ||
      document.querySelector('script[data-viewport-adaptive-v15]')
    ) return;

    const script = document.createElement('script');
    script.src = '/assets/viewport-adaptive-v15.js?v=20260830-1';
    script.async = true;
    script.dataset.viewportAdaptiveV15 = '1';
    document.head.appendChild(script);
  }

  injectStyles();
  loadAdaptiveV15();
  void hydrateProjectCombos();
  bootstrapMobileMenuEnhancement();
  document.documentElement.dataset.devpilotExperience = 'v13';
  console.info('[DevPilot] Runtime Experience V13 ativo');
})();
