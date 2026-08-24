(() => {
  const token = () => localStorage.getItem('devpilot-token') || '';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let currentData = null;

  async function api(path) {
    const response = await fetch(path, {headers: {Authorization: `Bearer ${token()}`}});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha ao carregar o painel do Super Admin');
    return data;
  }

  async function isSuperAdmin() {
    try {
      const me = await api('/api/auth/me');
      return String(me.role || '').toUpperCase() === 'SUPER_ADMIN';
    } catch (_) {
      return false;
    }
  }

  function activate(section, button, title) {
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
    document.querySelectorAll('.nav').forEach(nav => nav.classList.toggle('active', nav === button));
    const pageTitle = document.querySelector('#page-title');
    if (pageTitle) pageTitle.textContent = title;
  }

  function installShell() {
    if (document.querySelector('[data-view="super-admin-system"]')) {
      return document.querySelector('[data-view="super-admin-system"]');
    }
    const nav = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!nav || !main) return null;

    const button = document.createElement('button');
    button.className = 'nav system-map-nav';
    button.type = 'button';
    button.dataset.view = 'super-admin-system';
    button.innerHTML = '<span class="system-map-nav-dot"></span> Super Admin';
    const first = nav.querySelector('.nav');
    if (first?.nextSibling) nav.insertBefore(button, first.nextSibling);
    else nav.appendChild(button);

    const section = document.createElement('section');
    section.className = 'view system-map-view';
    section.id = 'super-admin-system-view';
    section.innerHTML = `
      <div class="system-map-hero">
        <div>
          <span class="eyebrow">SUPER ADMIN · ARQUITETURA VIVA</span>
          <h2>Fluxo interativo do sistema</h2>
          <p>Veja como cada parte real do DevPilot se conecta. Os números e estados vêm do backend; clique em qualquer bloco para inspecionar suas conexões e abrir o módulo correspondente.</p>
        </div>
        <button class="primary" id="system-map-refresh" type="button">Atualizar mapa</button>
      </div>
      <div id="system-map-content"><div class="empty">Carregando arquitetura…</div></div>`;
    main.appendChild(section);

    button.addEventListener('click', () => {
      activate(section, button, 'Super Admin · Sistema');
      load();
    });
    section.querySelector('#system-map-refresh').addEventListener('click', load);
    return button;
  }

  function statusText(status) {
    return ({online:'online', warn:'atenção', configured:'configurado', idle:'ocioso'})[status] || status || 'desconhecido';
  }

  function groupTitle(group) {
    return ({
      interfaces: 'Clientes / Interfaces',
      entry: 'Ponto de entrada',
      core: 'Backend / Orquestração',
      data: 'Dados / Auditoria',
      external: 'Integrações externas',
    })[group] || group;
  }

  function nodeConnections(nodeId, edges, nodes) {
    const byId = Object.fromEntries(nodes.map(node => [node.id, node]));
    return edges
      .filter(edge => edge.from === nodeId || edge.to === nodeId)
      .map(edge => ({
        ...edge,
        direction: edge.from === nodeId ? 'out' : 'in',
        peer: byId[edge.from === nodeId ? edge.to : edge.from],
      }));
  }

  function renderInspector(nodeId) {
    if (!currentData) return;
    const node = currentData.nodes.find(item => item.id === nodeId);
    const target = document.querySelector('#system-map-inspector');
    if (!node || !target) return;
    const connections = nodeConnections(node.id, currentData.edges, currentData.nodes);

    document.querySelectorAll('.system-map-node').forEach(card => {
      const id = card.dataset.nodeId;
      const connected = connections.some(item => item.peer?.id === id);
      card.classList.toggle('selected', id === node.id);
      card.classList.toggle('connected', connected);
      card.classList.toggle('dimmed', id !== node.id && !connected);
    });
    document.querySelectorAll('.system-map-edge').forEach(edge => {
      const active = edge.dataset.from === node.id || edge.dataset.to === node.id;
      edge.classList.toggle('active', active);
      edge.classList.toggle('dimmed', !active);
    });

    target.innerHTML = `
      <div class="system-map-inspector-head">
        <span class="system-map-node-icon">${esc(node.icon)}</span>
        <div><span class="eyebrow">${esc(groupTitle(node.group))}</span><h3>${esc(node.label)}</h3></div>
        <span class="system-map-status ${esc(node.status)}">${esc(statusText(node.status))}</span>
      </div>
      <strong class="system-map-inspector-value">${esc(node.value)}</strong>
      <p>${esc(node.detail)}</p>
      <div class="system-map-inspector-links">
        ${connections.map(item => `
          <button type="button" data-inspect-node="${esc(item.peer?.id || '')}">
            <span>${item.direction === 'out' ? '→' : '←'} ${esc(item.peer?.label || item.peer?.id || '')}</span>
            <small>${esc(item.label)} · ${esc(item.type)}</small>
          </button>`).join('') || '<div class="empty">Nenhuma conexão cadastrada.</div>'}
      </div>
      ${node.target_view ? `<button class="primary system-map-open" type="button" data-open-view="${esc(node.target_view)}">Abrir módulo</button>` : ''}`;

    target.querySelectorAll('[data-inspect-node]').forEach(button => {
      button.addEventListener('click', () => renderInspector(button.dataset.inspectNode));
    });
    target.querySelector('[data-open-view]')?.addEventListener('click', event => {
      const view = event.currentTarget.dataset.openView;
      const nav = document.querySelector(`.nav[data-view="${CSS.escape(view)}"]`);
      if (nav) nav.click();
    });
  }

  function render(data) {
    currentData = data;
    const target = document.querySelector('#system-map-content');
    if (!target) return;
    const summary = data.summary || {};
    const groups = ['interfaces', 'entry', 'core', 'data', 'external'];

    target.innerHTML = `
      ${data.warnings?.length ? `<div class="system-map-alerts">${data.warnings.map(item => `<div><b>!</b><span>${esc(item)}</span></div>`).join('')}</div>` : ''}

      <div class="system-map-flow" aria-label="Fluxo geral">
        ${(data.flow || []).map((step, index) => `
          <article><span>${esc(step.order)}</span><div><strong>${esc(step.label)}</strong><small>${esc(step.detail)}</small></div></article>${index < data.flow.length - 1 ? '<i>→</i>' : ''}
        `).join('')}
      </div>

      <div class="system-map-metrics">
        <article><span>Usuários</span><strong>${esc(summary.users ?? 0)}</strong><small>contas no workspace</small></article>
        <article><span>Projetos</span><strong>${esc(summary.projects ?? 0)}</strong><small>projetos conectados</small></article>
        <article><span>Tarefas ativas</span><strong>${esc(summary.active_tasks ?? 0)}</strong><small>fila e execução</small></article>
        <article><span>Repositórios</span><strong>${esc(summary.repositories ?? 0)}</strong><small>Git sincronizado</small></article>
        <article><span>IAs ativas</span><strong>${esc(summary.providers ?? 0)}</strong><small>provedores habilitados</small></article>
        <article><span>Auditoria 24h</span><strong>${esc(summary.audit_24h ?? 0)}</strong><small>eventos registrados</small></article>
      </div>

      <div class="system-map-layout">
        <div class="system-map-board">
          <div class="system-map-columns">
            ${groups.map(group => `
              <section class="system-map-group group-${esc(group)}">
                <header><span>${esc(groupTitle(group))}</span></header>
                <div class="system-map-group-nodes">
                  ${data.nodes.filter(node => node.group === group).map(node => {
                    const connectionCount = nodeConnections(node.id, data.edges, data.nodes).length;
                    return `<button type="button" class="system-map-node" data-node-id="${esc(node.id)}">
                      <span class="system-map-node-icon">${esc(node.icon)}</span>
                      <span class="system-map-node-copy"><strong>${esc(node.label)}</strong><small>${esc(node.detail)}</small></span>
                      <span class="system-map-node-meta"><b>${esc(node.value)}</b><i class="system-map-status ${esc(node.status)}">${esc(statusText(node.status))}</i><small>${connectionCount} conexão(ões)</small></span>
                    </button>`;
                  }).join('') || '<div class="empty">Sem componentes.</div>'}
                </div>
              </section>`).join('')}
          </div>

          <div class="system-map-edge-list" aria-label="Conexões do sistema">
            <div class="system-map-edge-head"><span class="eyebrow">CONEXÕES</span><strong>Fluxos reais entre componentes</strong></div>
            ${data.edges.map(edge => {
              const from = data.nodes.find(node => node.id === edge.from);
              const to = data.nodes.find(node => node.id === edge.to);
              return `<button type="button" class="system-map-edge type-${esc(edge.type)}" data-from="${esc(edge.from)}" data-to="${esc(edge.to)}">
                <span>${esc(from?.label || edge.from)}</span><i>→</i><span>${esc(to?.label || edge.to)}</span><small>${esc(edge.label)} · ${esc(edge.type)}</small>
              </button>`;
            }).join('')}
          </div>
        </div>

        <aside class="panel system-map-inspector" id="system-map-inspector">
          <div class="empty">Selecione um bloco para ver suas conexões.</div>
        </aside>
      </div>

      <div class="system-map-legend">
        <span><i class="online"></i> Online confirmado</span>
        <span><i class="configured"></i> Configurado, sem presumir conectividade</span>
        <span><i class="warn"></i> Requer atenção</span>
        <span><b>→</b> Requisição síncrona</span>
        <span><b>⇢</b> Fila / evento assíncrono</span>
      </div>
      <p class="system-map-generated">Atualizado em ${new Date(data.generated_at).toLocaleString('pt-BR')}</p>`;

    target.querySelectorAll('.system-map-node').forEach(card => {
      card.addEventListener('click', () => renderInspector(card.dataset.nodeId));
    });
    target.querySelectorAll('.system-map-edge').forEach(edge => {
      edge.addEventListener('click', () => renderInspector(edge.dataset.from));
    });
    if (data.nodes.length) renderInspector(data.nodes.find(node => node.id === 'api')?.id || data.nodes[0].id);
  }

  async function load() {
    const target = document.querySelector('#system-map-content');
    if (target) target.classList.add('loading');
    try {
      render(await api('/api/super-admin/voice/system-map'));
    } catch (error) {
      if (target) target.innerHTML = `<div class="empty">${esc(error.message)}</div>`;
    } finally {
      if (target) target.classList.remove('loading');
    }
  }

  async function boot() {
    if (!token() || !(await isSuperAdmin())) return;
    const button = installShell();
    if (!button) return;
    const active = document.querySelector('.view.active');
    const overview = document.querySelector('#overview-view');
    if (active === overview) button.click();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
