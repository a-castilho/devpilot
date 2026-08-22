(() => {
  const investiaState = {
    projects: [],
    configs: [],
    selectedId: '',
    costs: [],
  };

  function isSuperAdmin() {
    return String(state.currentUser?.role || '').toUpperCase() === 'SUPER_ADMIN';
  }

  function ensureStyles() {
    if (document.getElementById('investia-admin-styles')) return;
    const style = document.createElement('style');
    style.id = 'investia-admin-styles';
    style.textContent = `
      .investia-grid{display:grid;grid-template-columns:minmax(220px,.72fr) minmax(0,1.7fr);gap:18px;align-items:start}
      .investia-projects{display:grid;gap:9px;max-height:72vh;overflow:auto}
      .investia-project{width:100%;text-align:left;border:1px solid var(--border,#26354a);background:transparent;color:inherit;border-radius:14px;padding:13px;cursor:pointer}
      .investia-project.active{border-color:#36d399;box-shadow:inset 3px 0 #36d399}
      .investia-project small{display:block;margin-top:4px;opacity:.7}
      .investia-form{display:grid;gap:14px}
      .investia-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
      .investia-cost-row{display:grid;grid-template-columns:1fr auto auto;gap:10px;align-items:center;padding:10px 0;border-bottom:1px solid var(--border,#26354a)}
      .investia-cost-row:last-child{border-bottom:0}
      .investia-result{white-space:pre-wrap;padding:12px;border-radius:12px;background:rgba(0,0,0,.18);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
      .investia-note{padding:12px 14px;border:1px solid var(--border,#26354a);border-radius:14px}
      .devai-publication{display:grid;gap:12px;padding:14px;border:1px solid var(--border,#26354a);border-radius:14px}
      .devai-publication-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
      .devai-publication-actions{display:flex;gap:10px;flex-wrap:wrap}
      .devai-publication-actions button{min-width:150px}
      @media(max-width:760px){.investia-grid{grid-template-columns:1fr}.investia-cost-row{grid-template-columns:1fr}.investia-actions>*,.devai-publication-actions>*{flex:1 1 auto}}
    `;
    document.head.appendChild(style);
  }

  function ensurePanel() {
    if (!isSuperAdmin() || document.getElementById('investia-admin-view')) return;
    ensureStyles();

    const nav = document.querySelector('.sidebar nav');
    if (!nav) return;
    const button = document.createElement('button');
    button.className = 'nav';
    button.type = 'button';
    button.dataset.view = 'investia-admin';
    button.textContent = 'DevAI Invest';
    nav.insertBefore(button, nav.querySelector('[data-view="reports"]') || null);

    const section = document.createElement('section');
    section.className = 'view';
    section.id = 'investia-admin-view';
    section.innerHTML = `
      <div class="section-head">
        <div>
          <span class="eyebrow">SUPER ADMIN</span>
          <h2>DevAI Invest</h2>
          <p>Administração dos projetos do DevPilot que podem ser publicados no DevAI Invest. O produto de investimento permanece separado do DevPilot.</p>
        </div>
        <button class="ghost" type="button" id="investia-refresh">Atualizar</button>
      </div>
      <div class="investia-grid">
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">DEVPILOT</span><h3>Projetos</h3></div></div>
          <div id="investia-projects" class="investia-projects"><div class="empty">Carregando projetos...</div></div>
        </article>
        <div style="display:grid;gap:18px">
          <article class="panel">
            <form id="investia-project-form" class="investia-form">
              <div class="panel-title">
                <div><span class="eyebrow">CAPTAÇÃO</span><h3 id="investia-title">Selecione um projeto</h3></div>
                <span id="investia-badge" class="status">NÃO CONFIGURADO</span>
              </div>
              <div class="form-grid">
                <label>Chave externa<input name="external_project_key" placeholder="meu-projeto" required></label>
                <label>Moeda<input name="currency" value="BRL" maxlength="3" required></label>
              </div>
              <div class="form-grid">
                <label>Meta de captação<input name="funding_target" type="number" min="0.01" step="0.01" required></label>
                <label>Captação máxima<input name="maximum_funding" type="number" min="0.01" step="0.01" required></label>
              </div>
              <div class="form-grid">
                <label>Captação mínima<input name="minimum_funding" type="number" min="0" step="0.01" value="0"></label>
                <label>% do líquido aos investidores<input name="investor_share_percentage" type="number" min="0" max="100" step="0.0001" required></label>
              </div>
              <div class="form-grid">
                <label>Investimento mínimo<input name="minimum_investment" type="number" min="0.01" step="0.01" value="1"></label>
                <label>Máximo por investidor<input name="maximum_investment_per_user" type="number" min="0.01" step="0.01" placeholder="sem limite"></label>
              </div>
              <div class="form-grid">
                <label>Status do projeto
                  <select name="status">
                    <option value="draft">Rascunho</option>
                    <option value="fundraising">Captando</option>
                    <option value="funded">Captado</option>
                    <option value="operating">Operando</option>
                    <option value="distributing">Distribuindo</option>
                    <option value="completed">Concluído</option>
                    <option value="paused">Pausado</option>
                    <option value="cancelled">Cancelado</option>
                  </select>
                </label>
                <label>Estado de publicação
                  <input id="devai-publication-readonly" value="Não publicado" readonly>
                </label>
              </div>
              <input name="public_enabled" type="checkbox" hidden>
              <label>Notas administrativas<textarea name="notes" rows="3"></textarea></label>

              <div class="devai-publication">
                <div class="devai-publication-head">
                  <div>
                    <strong>Publicação no DevAI Invest</strong>
                    <p class="hint" id="devai-publication-help">Configure e salve o projeto antes de publicar.</p>
                  </div>
                  <span id="devai-publication-badge" class="status">NÃO PUBLICADO</span>
                </div>
                <div class="devai-publication-actions">
                  <button class="primary" type="button" id="devai-publish">Publicar no DevAI Invest</button>
                  <button class="ghost" type="button" id="devai-pause">Pausar no DevAI Invest</button>
                  <button class="ghost" type="button" id="devai-unpublish">Remover do DevAI Invest</button>
                </div>
              </div>

              <div class="investia-note">
                <strong>Regra financeira</strong>
                <p class="hint">O retorno é calculado sobre o resultado líquido. Custos só entram na dedução depois de aprovados pelo Super Admin.</p>
              </div>
              <div class="investia-actions">
                <button class="primary" type="submit">Salvar configuração</button>
              </div>
            </form>
          </article>

          <article class="panel">
            <div class="panel-title"><div><span class="eyebrow">CUSTOS</span><h3>Infraestrutura e desenvolvimento</h3></div></div>
            <form id="investia-cost-form" class="investia-form">
              <div class="form-grid">
                <label>Categoria
                  <select name="category">
                    <option value="infrastructure">Infraestrutura</option>
                    <option value="development">Desenvolvimento</option>
                    <option value="operations">Operação</option>
                    <option value="fees">Taxas</option>
                    <option value="taxes">Impostos</option>
                    <option value="other">Outros</option>
                  </select>
                </label>
                <label>Valor<input name="amount" type="number" min="0.01" step="0.01" required></label>
              </div>
              <label>Descrição<input name="description" required></label>
              <label>Comprovante / referência<input name="receipt_reference" placeholder="URL, nota fiscal ou referência"></label>
              <div class="investia-actions"><button class="ghost" type="submit">Adicionar custo</button></div>
            </form>
            <div id="investia-costs" style="margin-top:12px"><div class="empty">Configure um projeto primeiro.</div></div>
          </article>

          <article class="panel">
            <div class="panel-title"><div><span class="eyebrow">SIMULAÇÃO</span><h3>Distribuição líquida</h3></div></div>
            <form id="investia-preview-form" class="investia-form">
              <div class="form-grid">
                <label>Resultado bruto<input name="gross_result" type="number" min="0" step="0.01" required></label>
                <label>Total captado<input name="total_captured" type="number" min="0.01" step="0.01" required></label>
              </div>
              <label>Aporte do usuário para simulação<input name="investment_amount" type="number" min="0" step="0.01" placeholder="opcional"></label>
              <div class="investia-actions"><button class="ghost" type="submit">Calcular retorno</button></div>
            </form>
            <div id="investia-preview-result" class="investia-result" style="margin-top:12px">Nenhuma simulação executada.</div>
          </article>
        </div>
      </div>
    `;
    const reports = document.getElementById('reports-view');
    (reports?.parentNode || document.querySelector('main')).insertBefore(section, reports || null);

    button.addEventListener('click', () => openView(button, section));
    section.querySelector('#investia-refresh').addEventListener('click', () => loadAll(true));
    section.querySelector('#investia-project-form').addEventListener('submit', saveProjectConfig);
    section.querySelector('#investia-cost-form').addEventListener('submit', addCost);
    section.querySelector('#investia-preview-form').addEventListener('submit', previewDistribution);
    section.querySelector('#devai-publish').addEventListener('click', () => changePublication('publish'));
    section.querySelector('#devai-pause').addEventListener('click', () => changePublication('pause'));
    section.querySelector('#devai-unpublish').addEventListener('click', () => changePublication('unpublish'));
  }

  function openView(button, section) {
    if (!isSuperAdmin()) return toast('Acesso exclusivo do Super Admin');
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button));
    const title = document.getElementById('page-title');
    if (title) title.textContent = 'DevAI Invest';
    loadAll();
  }

  function selectedProject() {
    return investiaState.projects.find(item => item.id === investiaState.selectedId) || null;
  }

  function selectedConfig() {
    return investiaState.configs.find(item => item.project_id === investiaState.selectedId) || null;
  }

  function publicationState(cfg) {
    if (!cfg?.public_enabled) return 'not_published';
    if (String(cfg.status || '') === 'paused') return 'paused';
    return 'published';
  }

  function publicationLabel(value) {
    if (value === 'published') return 'PUBLICADO';
    if (value === 'paused') return 'PAUSADO';
    return 'NÃO PUBLICADO';
  }

  function renderPublication() {
    const cfg = selectedConfig();
    const stateValue = publicationState(cfg);
    const badge = document.getElementById('devai-publication-badge');
    const readonly = document.getElementById('devai-publication-readonly');
    const help = document.getElementById('devai-publication-help');
    const publish = document.getElementById('devai-publish');
    const pause = document.getElementById('devai-pause');
    const unpublish = document.getElementById('devai-unpublish');
    if (!badge || !readonly || !help || !publish || !pause || !unpublish) return;

    badge.textContent = publicationLabel(stateValue);
    readonly.value = publicationLabel(stateValue);
    publish.disabled = !cfg || stateValue === 'published';
    pause.disabled = !cfg || stateValue !== 'published';
    unpublish.disabled = !cfg || stateValue === 'not_published';

    if (!cfg) {
      help.textContent = 'Configure e salve o projeto antes de publicar.';
    } else if (stateValue === 'paused') {
      help.textContent = 'O projeto continua visível no DevAI Invest, mas não aceita novos aportes.';
      publish.textContent = 'Retomar no DevAI Invest';
    } else if (stateValue === 'published') {
      help.textContent = 'Projeto publicado. Novos aportes dependem do status de captação.';
      publish.textContent = 'Publicar no DevAI Invest';
    } else {
      help.textContent = 'Projeto configurado e ainda não publicado no DevAI Invest.';
      publish.textContent = 'Publicar no DevAI Invest';
    }
  }

  function renderProjects() {
    const target = document.getElementById('investia-projects');
    if (!target) return;
    target.innerHTML = investiaState.projects.map(project => {
      const cfg = investiaState.configs.find(item => item.project_id === project.id);
      const pub = publicationState(cfg);
      return `
        <button class="investia-project ${project.id === investiaState.selectedId ? 'active' : ''}" type="button" data-id="${esc(project.id)}">
          <strong>${esc(project.name)}</strong>
          <small>${esc(project.slug || '')}</small>
          <small>${cfg ? `${esc(cfg.status || 'draft')} · ${publicationLabel(pub).toLowerCase()}` : 'não configurado'}</small>
        </button>`;
    }).join('') || '<div class="empty">Nenhum projeto no DevPilot.</div>';

    target.querySelectorAll('[data-id]').forEach(button => {
      button.addEventListener('click', async () => {
        investiaState.selectedId = button.dataset.id;
        renderProjects();
        fillProjectForm();
        await loadCosts();
      });
    });
  }

  function fillProjectForm() {
    const project = selectedProject();
    const cfg = selectedConfig();
    const form = document.getElementById('investia-project-form');
    if (!project || !form) return;

    document.getElementById('investia-title').textContent = project.name;
    document.getElementById('investia-badge').textContent = cfg ? String(cfg.status || 'draft').toUpperCase() : 'NÃO CONFIGURADO';
    form.elements.external_project_key.disabled = Boolean(cfg);
    form.elements.external_project_key.value = cfg?.external_project_key || project.slug || '';
    form.elements.currency.value = cfg?.currency || 'BRL';
    form.elements.funding_target.value = cfg?.funding_target ?? '';
    form.elements.minimum_funding.value = cfg?.minimum_funding ?? '0';
    form.elements.maximum_funding.value = cfg?.maximum_funding ?? '';
    form.elements.minimum_investment.value = cfg?.minimum_investment ?? '1';
    form.elements.maximum_investment_per_user.value = cfg?.maximum_investment_per_user ?? '';
    form.elements.investor_share_percentage.value = cfg?.investor_share_percentage ?? '';
    form.elements.status.value = cfg?.status || 'draft';
    form.elements.public_enabled.checked = Boolean(cfg?.public_enabled);
    form.elements.notes.value = cfg?.notes || '';
    renderPublication();
  }

  function numberOrNull(value) {
    const clean = String(value ?? '').trim();
    return clean === '' ? null : Number(clean);
  }

  async function saveProjectConfig(event) {
    event.preventDefault();
    const project = selectedProject();
    if (!project) return toast('Selecione um projeto');
    const cfg = selectedConfig();
    const form = event.currentTarget;
    const payload = {
      currency: form.elements.currency.value.trim().toUpperCase(),
      funding_target: Number(form.elements.funding_target.value),
      minimum_funding: Number(form.elements.minimum_funding.value || 0),
      maximum_funding: Number(form.elements.maximum_funding.value),
      minimum_investment: Number(form.elements.minimum_investment.value || 1),
      maximum_investment_per_user: numberOrNull(form.elements.maximum_investment_per_user.value),
      investor_share_percentage: Number(form.elements.investor_share_percentage.value),
      status: form.elements.status.value,
      public_enabled: Boolean(cfg?.public_enabled),
      notes: form.elements.notes.value,
    };
    if (!cfg) payload.external_project_key = form.elements.external_project_key.value.trim();

    try {
      await api(`/admin/investia/projects/${project.id}`, {
        method: cfg ? 'PATCH' : 'POST',
        body: JSON.stringify(payload),
      });
      toast('Configuração do DevAI Invest salva');
      await loadAll(true);
    } catch (error) {
      toast(error.message);
    }
  }

  async function changePublication(action) {
    const cfg = selectedConfig();
    const project = selectedProject();
    if (!project) return toast('Selecione um projeto');
    if (!cfg) return toast('Salve a configuração antes de publicar');

    const labels = {
      publish: 'Projeto publicado no DevAI Invest',
      pause: 'Projeto pausado no DevAI Invest',
      unpublish: 'Projeto removido do DevAI Invest',
    };

    try {
      await api(`/investia/admin/projects/${project.id}/${action}`, {method: 'POST'});
      toast(labels[action] || 'Publicação atualizada');
      await loadAll(true);
    } catch (error) {
      toast(error.message);
    }
  }

  async function loadCosts() {
    const cfg = selectedConfig();
    const target = document.getElementById('investia-costs');
    if (!target) return;
    if (!cfg) {
      investiaState.costs = [];
      target.innerHTML = '<div class="empty">Configure o projeto antes de cadastrar custos.</div>';
      return;
    }
    try {
      investiaState.costs = await api(`/admin/investia/projects/${investiaState.selectedId}/costs`);
      renderCosts();
    } catch (error) {
      target.innerHTML = `<div class="empty">${esc(error.message)}</div>`;
    }
  }

  function renderCosts() {
    const target = document.getElementById('investia-costs');
    if (!target) return;
    target.innerHTML = investiaState.costs.map(cost => `
      <div class="investia-cost-row">
        <div>
          <strong>${esc(cost.description)}</strong>
          <div class="hint">${esc(cost.category)} · R$ ${Number(cost.amount || 0).toLocaleString('pt-BR', {minimumFractionDigits:2})} · ${esc(cost.status)}</div>
        </div>
        ${cost.status === 'pending' ? `<button class="ghost" type="button" data-approve="${esc(cost.id)}">Aprovar</button>` : '<span></span>'}
        ${cost.status === 'pending' ? `<button class="ghost" type="button" data-reject="${esc(cost.id)}">Rejeitar</button>` : '<span></span>'}
      </div>
    `).join('') || '<div class="empty">Nenhum custo cadastrado.</div>';

    target.querySelectorAll('[data-approve]').forEach(button => button.addEventListener('click', () => changeCost(button.dataset.approve, 'approve')));
    target.querySelectorAll('[data-reject]').forEach(button => button.addEventListener('click', () => changeCost(button.dataset.reject, 'reject')));
  }

  async function addCost(event) {
    event.preventDefault();
    const cfg = selectedConfig();
    if (!cfg) return toast('Configure o projeto primeiro');
    const form = event.currentTarget;
    const payload = {
      category: form.elements.category.value,
      description: form.elements.description.value.trim(),
      amount: Number(form.elements.amount.value),
      receipt_reference: form.elements.receipt_reference.value.trim(),
    };
    try {
      await api(`/admin/investia/projects/${investiaState.selectedId}/costs`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      form.reset();
      toast('Custo cadastrado; aguardando aprovação');
      await loadCosts();
    } catch (error) {
      toast(error.message);
    }
  }

  async function changeCost(costId, action) {
    try {
      await api(`/admin/investia/costs/${costId}/${action}`, {method: 'POST'});
      toast(action === 'approve' ? 'Custo aprovado' : 'Custo rejeitado');
      await loadCosts();
      await loadConfigs();
    } catch (error) {
      toast(error.message);
    }
  }

  async function previewDistribution(event) {
    event.preventDefault();
    const cfg = selectedConfig();
    if (!cfg) return toast('Configure o projeto primeiro');
    const form = event.currentTarget;
    const investment = numberOrNull(form.elements.investment_amount.value);
    const payload = {
      gross_result: Number(form.elements.gross_result.value),
      total_captured: Number(form.elements.total_captured.value),
      investment_amount: investment,
    };
    try {
      const result = await api(`/admin/investia/projects/${investiaState.selectedId}/distribution-preview`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      const lines = [
        `Resultado bruto: R$ ${Number(result.gross_result).toLocaleString('pt-BR', {minimumFractionDigits:2})}`,
        `Custos aprovados: R$ ${Number(result.approved_costs).toLocaleString('pt-BR', {minimumFractionDigits:2})}`,
        `Resultado líquido: R$ ${Number(result.net_result).toLocaleString('pt-BR', {minimumFractionDigits:2})}`,
        `Percentual dos investidores: ${Number(result.investor_share_percentage).toLocaleString('pt-BR')}%`,
        `Pool distribuível: R$ ${Number(result.distributable_pool).toLocaleString('pt-BR', {minimumFractionDigits:2})}`,
      ];
      if (result.participation_percentage != null) lines.push(`Participação simulada: ${Number(result.participation_percentage).toLocaleString('pt-BR')}%`);
      if (result.investor_return != null) lines.push(`Retorno simulado: R$ ${Number(result.investor_return).toLocaleString('pt-BR', {minimumFractionDigits:2})}`);
      document.getElementById('investia-preview-result').textContent = lines.join('\n');
    } catch (error) {
      toast(error.message);
    }
  }

  async function loadConfigs() {
    investiaState.configs = await api('/admin/investia/projects');
  }

  async function loadAll(force = false) {
    if (!isSuperAdmin()) return;
    const active = document.getElementById('investia-admin-view')?.classList.contains('active');
    if (!active && !force) return;
    try {
      const [projects] = await Promise.all([api('/projects'), loadConfigs()]);
      investiaState.projects = projects;
      if (!investiaState.selectedId || !projects.some(item => item.id === investiaState.selectedId)) {
        investiaState.selectedId = projects[0]?.id || '';
      }
      renderProjects();
      fillProjectForm();
      await loadCosts();
    } catch (error) {
      toast(error.message);
    }
  }

  let roleChecks = 0;
  const waitForRole = () => {
    roleChecks += 1;
    if (state.currentUser) {
      ensurePanel();
      return;
    }
    if (roleChecks < 40) setTimeout(waitForRole, 250);
  };
  waitForRole();
})();