(() => {
  const MANAGER_ROLES = new Set(['SUPER_ADMIN']);
  const deployState = {items: [], selectedId: '', actionId: '', pollTimer: null};

  function canManageDeploy() {
    return MANAGER_ROLES.has(String(state.currentUser?.role || '').toUpperCase());
  }

  function ensureStyles() {
    if (document.getElementById('deploy-admin-styles')) return;
    const style = document.createElement('style');
    style.id = 'deploy-admin-styles';
    style.textContent = `
      .deploy-admin-grid{display:grid;grid-template-columns:minmax(220px,.8fr) minmax(0,1.6fr);gap:18px;align-items:start}
      .deploy-admin-projects{display:grid;gap:10px}
      .deploy-admin-project{width:100%;text-align:left;border:1px solid var(--border,#26354a);background:transparent;color:inherit;border-radius:14px;padding:13px;cursor:pointer}
      .deploy-admin-project.active{border-color:#36d399;box-shadow:inset 3px 0 #36d399}
      .deploy-admin-project small{display:block;margin-top:5px;opacity:.7}
      .deploy-admin-form{display:grid;gap:14px}
      .deploy-admin-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
      .deploy-admin-status{white-space:pre-wrap;word-break:break-word;max-height:260px;overflow:auto;padding:12px;border-radius:12px;background:rgba(0,0,0,.18);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
      .deploy-admin-note{padding:12px 14px;border:1px solid var(--border,#26354a);border-radius:14px}
      @media(max-width:760px){.deploy-admin-grid{grid-template-columns:1fr}.deploy-admin-actions>*{flex:1 1 auto}}
    `;
    document.head.appendChild(style);
  }

  function ensurePanel() {
    if (!canManageDeploy() || document.getElementById('deploy-admin-view')) return;
    ensureStyles();

    const nav = document.querySelector('.sidebar nav');
    if (!nav) return;
    const button = document.createElement('button');
    button.className = 'nav';
    button.type = 'button';
    button.dataset.view = 'deploy-admin';
    button.dataset.superAdmin = 'true';
    button.textContent = 'Deploy manual';
    nav.insertBefore(button, nav.querySelector('[data-view="reports"]') || null);

    const section = document.createElement('section');
    section.className = 'view';
    section.id = 'deploy-admin-view';
    section.innerHTML = `
      <div class="section-head">
        <div>
          <p>Configurações legadas de deploy por projeto. Execução no host só pode ocorrer por ações nomeadas e fluxos estruturados.</p>
        </div>
        <button class="ghost" type="button" id="deploy-admin-refresh">Atualizar status</button>
      </div>
      <div class="deploy-admin-grid">
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">SUPER ADMIN</span><h3>Projetos</h3></div></div>
          <div id="deploy-admin-projects" class="deploy-admin-projects"><div class="empty">Carregando projetos...</div></div>
        </article>
        <article class="panel">
          <form id="deploy-admin-form" class="deploy-admin-form">
            <div class="panel-title">
              <div><span class="eyebrow">CONFIGURAÇÃO</span><h3 id="deploy-admin-title">Selecione um projeto</h3></div>
              <span id="deploy-admin-badge" class="status">—</span>
            </div>
            <label>Ambiente
              <select name="environment">
                <option value="homolog">Homologação</option>
                <option value="production">Produção</option>
                <option value="development">Desenvolvimento</option>
                <option value="staging">Staging</option>
              </select>
            </label>
            <div class="form-grid">
              <label>Branch esperada<input name="branch" placeholder="main" required></label>
              <label>Timeout (segundos)<input name="timeout_seconds" type="number" min="30" max="3600" value="900" required></label>
            </div>
            <label>Diretório de trabalho
              <input name="workdir" placeholder="devpilot ou /home/usuario/Documents/devpilot" required>
            </label>
            <label class="check"><input name="enabled" type="checkbox"> Manter configuração de deploy registrada para este projeto</label>
            <div class="deploy-admin-note">
              <strong>Execução por shell desativada</strong>
              <p class="hint" id="deploy-admin-security-note">Comandos livres não atravessam mais a fronteira container → host. Use deploy estruturado por provedor/CI ou ações de host nomeadas e auditáveis.</p>
            </div>
            <div class="deploy-admin-actions">
              <button class="primary" type="submit" id="deploy-admin-save">Salvar configuração</button>
              <button class="ghost" type="button" id="deploy-admin-run" disabled>Execução indisponível</button>
            </div>
          </form>
          <div style="margin-top:16px">
            <span class="eyebrow">ÚLTIMA EXECUÇÃO LEGADA</span>
            <div id="deploy-admin-status" class="deploy-admin-status">Nenhum deploy selecionado.</div>
          </div>
        </article>
      </div>
    `;
    const reports = document.getElementById('reports-view');
    (reports?.parentNode || document.querySelector('main')).insertBefore(section, reports || null);

    button.addEventListener('click', () => openDeployView(button, section));
    section.querySelector('#deploy-admin-refresh').addEventListener('click', () => loadDeployments(true));
    section.querySelector('#deploy-admin-form').addEventListener('submit', saveDeployment);
    section.querySelector('#deploy-admin-run').addEventListener('click', runDeployment);
  }

  function openDeployView(button, section) {
    if (!canManageDeploy()) return toast('Acesso restrito ao Super Admin');
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button));
    const title = document.getElementById('page-title');
    if (title) title.textContent = 'Deploy manual';
    loadDeployments();
  }

  function currentItem() {
    return deployState.items.find(item => item.project_id === deployState.selectedId) || null;
  }

  function renderProjectList() {
    const target = document.getElementById('deploy-admin-projects');
    if (!target) return;
    target.innerHTML = deployState.items.map(item => {
      const cfg = item.config || {};
      const last = item.last_run;
      const execution = item.manual_execution_available === false ? 'execução bloqueada' : (cfg.enabled ? 'habilitado' : 'desativado');
      return `
        <button class="deploy-admin-project ${item.project_id === deployState.selectedId ? 'active' : ''}" type="button" data-project-id="${esc(item.project_id)}">
          <strong>${esc(item.project_name)}</strong>
          <small>${esc(cfg.environment || 'homolog')} · ${esc(execution)}</small>
          <small>${last ? `${esc(last.status || 'queued')} · ${new Date(last.created_at).toLocaleString('pt-BR')}` : 'sem execução'}</small>
        </button>`;
    }).join('') || '<div class="empty">Nenhum projeto disponível.</div>';

    target.querySelectorAll('[data-project-id]').forEach(button => {
      button.addEventListener('click', () => {
        deployState.selectedId = button.dataset.projectId;
        renderProjectList();
        fillForm();
      });
    });
  }

  function fillForm() {
    const item = currentItem();
    const form = document.getElementById('deploy-admin-form');
    if (!item || !form) return;
    const cfg = item.config || {};
    const unavailable = item.manual_execution_available === false;
    document.getElementById('deploy-admin-title').textContent = item.project_name;
    document.getElementById('deploy-admin-badge').textContent = unavailable ? 'BLOQUEADO' : (cfg.enabled ? 'HABILITADO' : 'DESATIVADO');
    form.elements.environment.value = cfg.environment || 'homolog';
    form.elements.branch.value = cfg.branch || item.default_branch || 'main';
    form.elements.workdir.value = cfg.workdir || '';
    form.elements.timeout_seconds.value = Number(cfg.timeout_seconds || 900);
    form.elements.enabled.checked = Boolean(cfg.enabled);
    const runButton = document.getElementById('deploy-admin-run');
    if (runButton) {
      runButton.disabled = unavailable || !cfg.enabled;
      runButton.textContent = unavailable ? 'Execução indisponível' : 'Executar deploy';
      runButton.title = unavailable ? String(item.manual_execution_reason || '') : '';
    }
    const note = document.getElementById('deploy-admin-security-note');
    if (note && item.manual_execution_reason) note.textContent = item.manual_execution_reason;
    renderStatus(item.last_run);
  }

  function renderStatus(run) {
    const target = document.getElementById('deploy-admin-status');
    if (!target) return;
    if (!run) {
      target.textContent = 'Nenhuma execução registrada para este projeto.';
      return;
    }
    const parts = [
      `status: ${run.status || 'queued'}`,
      run.environment ? `ambiente: ${run.environment}` : '',
      run.created_at ? `início: ${new Date(run.created_at).toLocaleString('pt-BR')}` : '',
      run.finished_at ? `fim: ${new Date(run.finished_at).toLocaleString('pt-BR')}` : '',
      run.detail ? `\n${run.detail}` : '',
    ].filter(Boolean);
    target.textContent = parts.join('\n');
  }

  async function loadDeployments(force = false) {
    if (!canManageDeploy()) return;
    const active = document.getElementById('deploy-admin-view')?.classList.contains('active');
    if (!active && !force) return;
    try {
      const items = await api('/admin/deployments');
      deployState.items = items;
      if (!deployState.selectedId || !items.some(item => item.project_id === deployState.selectedId)) {
        deployState.selectedId = items[0]?.project_id || '';
      }
      renderProjectList();
      fillForm();
    } catch (error) {
      toast(error.message);
    }
  }

  async function saveDeployment(event) {
    event.preventDefault();
    const item = currentItem();
    if (!item) return toast('Selecione um projeto');
    const form = event.currentTarget;
    const payload = {
      enabled: form.elements.enabled.checked,
      environment: form.elements.environment.value,
      branch: form.elements.branch.value.trim(),
      workdir: form.elements.workdir.value.trim(),
      timeout_seconds: Number(form.elements.timeout_seconds.value || 900),
    };
    try {
      await api(`/admin/deployments/${item.project_id}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      toast('Configuração de deploy salva');
      await loadDeployments(true);
    } catch (error) {
      toast(error.message);
    }
  }

  async function runDeployment() {
    const item = currentItem();
    if (!item) return toast('Selecione um projeto');
    if (item.manual_execution_available === false) {
      return toast(item.manual_execution_reason || 'Execução manual desativada por segurança');
    }
    if (!item.config?.enabled) return toast('Habilite e salve o deploy manual antes de executar');
    const button = document.getElementById('deploy-admin-run');
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Enfileirando...';
    try {
      const result = await api(`/admin/deployments/${item.project_id}/run`, {method: 'POST'});
      deployState.actionId = result.host_action.id;
      renderStatus({...result.host_action, environment: item.config.environment});
      toast('Deploy manual enviado para o host');
      pollAction(result.host_action.id);
    } catch (error) {
      toast(error.message);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function pollAction(actionId) {
    clearTimeout(deployState.pollTimer);
    let attempts = 0;
    const check = async () => {
      attempts += 1;
      try {
        const run = await api(`/admin/deployments/actions/${actionId}`);
        renderStatus(run);
        if (run.status === 'completed' || run.status === 'failed') {
          await loadDeployments(true);
          return;
        }
      } catch (error) {
        if (attempts > 2) toast(error.message);
      }
      if (attempts < 120) deployState.pollTimer = setTimeout(check, 3000);
    };
    deployState.pollTimer = setTimeout(check, 1000);
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
