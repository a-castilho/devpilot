(() => {
  const STYLE_ID = 'devpilot-analysis-failure-actions-style';

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .analysis-proposal-card.analysis-incomplete{border-color:#6a4f2b;background:linear-gradient(145deg,#21190d,#0e1824);position:sticky;top:0}
      .analysis-proposal-card.analysis-incomplete .analysis-review-badge{border-color:#8d632c;background:#31220f;color:#ffd58b}
      .analysis-incomplete-content{display:grid;gap:13px}
      .analysis-incomplete-alert{display:grid;grid-template-columns:36px minmax(0,1fr);gap:11px;padding:13px;border:1px solid #5f4828;border-radius:11px;background:#17150f}
      .analysis-incomplete-icon{width:34px;height:34px;display:grid;place-items:center;border-radius:9px;background:#493415;color:#ffd58b;font-size:17px;font-weight:900}
      .analysis-incomplete-alert strong{display:block;color:#fff3dc;font-size:13px}
      .analysis-incomplete-alert p{margin:4px 0 0;color:#c4b79f;font-size:11px;line-height:1.5}
      .analysis-incomplete-code{display:inline-flex;width:max-content;max-width:100%;padding:5px 7px;border-radius:7px;background:#08111b;color:#8da5bd;font:700 9px ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}
      .analysis-incomplete-actions{display:flex;gap:9px;flex-wrap:wrap}
      .analysis-incomplete-actions button{min-height:38px;padding:8px 12px;border-radius:9px;font:inherit;font-size:11px;font-weight:850;cursor:pointer}
      .analysis-fix-credential{border:1px solid #2b8b7d;background:#12342f;color:#70edd8}
      .analysis-retry-task{border:1px solid #355b80;background:#10263c;color:#dcecff}
      .analysis-incomplete-actions button:disabled{opacity:.55;cursor:not-allowed}
      .analysis-incomplete-note{margin:0;color:#8397ad;font-size:10px;line-height:1.45}
      #github-credential-repair-modal{width:min(520px,calc(100vw - 28px));padding:0;border:1px solid #29445f;border-radius:17px;background:#091625;color:#edf6ff;box-shadow:0 26px 80px #000b}
      #github-credential-repair-modal::backdrop{background:#020711c9;backdrop-filter:blur(5px)}
      #github-credential-repair-modal .credential-repair-form{display:grid;gap:14px;padding:24px}
      #github-credential-repair-modal h2{margin:3px 0 0;font-size:20px}
      #github-credential-repair-modal p{margin:0;color:#8fa4bd;font-size:11px;line-height:1.55}
      #github-credential-repair-modal label{display:grid;gap:6px;color:#c8d7e7;font-size:11px;font-weight:800}
      #github-credential-repair-modal input{width:100%;min-height:42px;padding:9px 11px;border:1px solid #294964;border-radius:9px;background:#06111e;color:#edf7ff;outline:none}
      #github-credential-repair-modal input:focus{border-color:#35e5d1;box-shadow:0 0 0 3px #35e5d112}
      #github-credential-repair-modal .credential-repair-actions{display:flex;justify-content:flex-end;gap:9px;flex-wrap:wrap}
      #github-credential-repair-modal .credential-repair-status{min-height:16px;color:#879db5;font-size:10px}
      #github-credential-repair-modal .credential-repair-status.error{color:#ff9eb0}
      #github-credential-repair-modal .credential-repair-status.success{color:#72e7aa}
      @media(max-width:640px){.analysis-incomplete-actions{display:grid}.analysis-incomplete-actions button{width:100%}#github-credential-repair-modal .credential-repair-actions{display:grid}#github-credential-repair-modal .credential-repair-actions button{width:100%}}
    `;
    document.head.appendChild(style);
  }

  function runIdFromLink(link) {
    const match = String(link?.getAttribute('href') || '').match(/task-runs\/([^/?#]+)/);
    return match ? match[1] : null;
  }

  function taskFor(run) {
    return typeof state !== 'undefined' && Array.isArray(state.tasks)
      ? state.tasks.find(task => task.id === run?.task_id) || null
      : null;
  }

  function projectFor(task) {
    return task && typeof state !== 'undefined' && Array.isArray(state.projects)
      ? state.projects.find(project => project.id === task.project_id) || null
      : null;
  }

  function organizationFor(project) {
    return project?.organization_id && typeof state !== 'undefined' && Array.isArray(state.organizations)
      ? state.organizations.find(organization => organization.id === project.organization_id) || null
      : null;
  }

  function isAdmin() {
    return typeof isSuperAdmin === 'function' && isSuperAdmin();
  }

  function normalizeRepository(value) {
    return String(value || '')
      .trim()
      .replace(/^git@github\.com:/i, '')
      .replace(/^https?:\/\/github\.com\//i, '')
      .replace(/\.git$/i, '')
      .replace(/^\/+|\/+$/g, '')
      .toLowerCase();
  }

  function repositoryVisibleInSync(repositories, project, syncResult) {
    const expected = normalizeRepository(project?.repository_url);
    const syncedAt = syncResult?.organization?.last_synced_at
      ? new Date(syncResult.organization.last_synced_at).getTime()
      : 0;
    if (!expected) return false;

    return repositories.some(repository => {
      if (normalizeRepository(repository.clone_url || repository.full_name) !== expected) return false;
      if (!syncedAt || !repository.last_seen_at) return true;
      const seenAt = new Date(repository.last_seen_at).getTime();
      return Number.isFinite(seenAt) && Math.abs(seenAt - syncedAt) < 5000;
    });
  }

  async function retrySameTask(taskId, button) {
    if (!taskId) return;
    const original = button?.textContent || 'Testar novamente';
    if (button) {
      button.disabled = true;
      button.textContent = 'Retomando…';
    }
    try {
      await api(`/tasks/${taskId}/retry`, {method: 'POST'});
      document.getElementById('task-log-modal')?.close();
      if (typeof toast === 'function') toast('A mesma análise foi recolocada na fila, sem criar tarefa duplicada.');
      if (typeof load === 'function') await load();
    } catch (error) {
      if (typeof toast === 'function') toast(error.message || 'Não foi possível testar novamente.');
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = original;
      }
    }
  }

  function ensureCredentialDialog() {
    let dialog = document.getElementById('github-credential-repair-modal');
    if (dialog) return dialog;

    dialog = document.createElement('dialog');
    dialog.id = 'github-credential-repair-modal';
    dialog.innerHTML = `
      <form class="credential-repair-form" id="github-credential-repair-form">
        <div><span class="eyebrow">CORRIGIR CREDENCIAL</span><h2>Restabelecer acesso ao GitHub</h2></div>
        <p id="github-credential-repair-context">Informe uma credencial com acesso de leitura ao repositório.</p>
        <label>Token GitHub<input name="access_token" type="password" autocomplete="off" placeholder="github_pat_... ou ghp_..." required></label>
        <p>O token é salvo no vault. O DevPilot valida a organização e confirma que o repositório da tarefa está acessível antes de retomar a análise.</p>
        <div class="credential-repair-status" id="github-credential-repair-status"></div>
        <div class="credential-repair-actions"><button type="button" class="ghost" data-close-credential>Cancelar</button><button type="submit" class="primary">Salvar, validar e retomar</button></div>
      </form>`;
    document.body.appendChild(dialog);
    dialog.querySelector('[data-close-credential]').onclick = () => dialog.close();
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });

    const form = dialog.querySelector('#github-credential-repair-form');
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const status = dialog.querySelector('#github-credential-repair-status');
      const submit = form.querySelector('button[type="submit"]');
      const token = String(new FormData(form).get('access_token') || '').trim();
      const task = typeof state !== 'undefined'
        ? state.tasks.find(item => item.id === dialog.dataset.taskId)
        : null;
      const project = typeof state !== 'undefined'
        ? state.projects.find(item => item.id === dialog.dataset.projectId)
        : null;
      const organizationId = dialog.dataset.organizationId || '';

      if (!token || !task || !project || !organizationId) {
        status.className = 'credential-repair-status error';
        status.textContent = 'Não foi possível identificar a organização e a tarefa desta análise.';
        return;
      }

      submit.disabled = true;
      submit.textContent = 'Validando acesso…';
      status.className = 'credential-repair-status';
      status.textContent = 'Salvando a credencial e verificando o repositório…';

      try {
        await api(`/organizations/${organizationId}`, {
          method: 'PATCH',
          body: JSON.stringify({access_token: token}),
        });
        const syncResult = await api(`/organizations/${organizationId}/sync`, {
          method: 'POST',
          body: JSON.stringify({import_projects: false}),
        });
        const repositories = await api(`/organizations/${organizationId}/repositories`);
        if (!repositoryVisibleInSync(repositories, project, syncResult)) {
          throw new Error('A credencial foi salva, mas ainda não possui acesso ao repositório desta análise.');
        }

        status.className = 'credential-repair-status success';
        status.textContent = 'Acesso confirmado. Retomando a mesma análise…';
        await api(`/tasks/${task.id}/retry`, {method: 'POST'});
        form.reset();
        dialog.close();
        document.getElementById('task-log-modal')?.close();
        if (typeof toast === 'function') toast('Credencial validada. A mesma análise foi retomada automaticamente.');
        if (typeof load === 'function') await load();
      } catch (error) {
        status.className = 'credential-repair-status error';
        status.textContent = error.message || 'Não foi possível validar a credencial.';
      } finally {
        submit.disabled = false;
        submit.textContent = 'Salvar, validar e retomar';
      }
    });
    return dialog;
  }

  function openCredentialRepair(run) {
    const task = taskFor(run);
    const project = projectFor(task);
    const organization = organizationFor(project);
    if (!isAdmin()) return typeof toast === 'function' && toast('A correção da credencial GitHub exige perfil Super Admin.');
    if (!task || !project || !organization) return typeof toast === 'function' && toast('O projeto precisa estar vinculado a uma organização GitHub.');

    const dialog = ensureCredentialDialog();
    dialog.dataset.taskId = task.id;
    dialog.dataset.projectId = project.id;
    dialog.dataset.organizationId = organization.id;
    dialog.querySelector('#github-credential-repair-context').textContent = `${project.name} · ${organization.name}. A análise só será retomada após confirmar acesso ao repositório.`;
    const status = dialog.querySelector('#github-credential-repair-status');
    status.className = 'credential-repair-status';
    status.textContent = '';
    const input = dialog.querySelector('input[name="access_token"]');
    input.value = '';
    if (!dialog.open) dialog.showModal();
    input.focus();
  }

  function applyIncompleteState(run) {
    if (!run || String(run.status || '').toLowerCase() !== 'failed') return;
    const dialog = document.getElementById('task-log-modal');
    if (!dialog?.open) return;
    const proposal = dialog.querySelector('.analysis-proposal-card');
    const clientCard = dialog.querySelector('#task-client-card');
    const content = proposal?.querySelector('.analysis-proposal-content');
    if (!proposal || !clientCard || !content) return;

    const failure = run.failure && typeof run.failure === 'object' ? run.failure : {};
    const githubAuth = String(failure.category || '') === 'github_auth';
    const task = taskFor(run);
    const project = projectFor(task);
    const organization = organizationFor(project);
    const expectedTitle = githubAuth ? 'Restabeleça o acesso ao repositório' : 'Resolva o bloqueio antes de continuar';

    const alreadyStable = proposal.dataset.failureRunId === run.id
      && proposal.classList.contains('analysis-incomplete')
      && proposal.querySelector('.analysis-incomplete-actions')
      && proposal.querySelector('.analysis-proposal-head h3')?.textContent === expectedTitle
      && clientCard.querySelector(':scope > .eyebrow')?.textContent === 'DIAGNÓSTICO AUTOMÁTICO DA FALHA';
    if (alreadyStable) return;

    dialog.dataset.analysisIncomplete = 'true';
    proposal.dataset.failureRunId = run.id;
    proposal.classList.add('analysis-incomplete');
    const clientEyebrow = clientCard.querySelector(':scope > .eyebrow');
    if (clientEyebrow) clientEyebrow.textContent = 'DIAGNÓSTICO AUTOMÁTICO DA FALHA';

    const head = proposal.querySelector('.analysis-proposal-head');
    const eyebrow = head?.querySelector('.eyebrow');
    const title = head?.querySelector('h3');
    const badge = head?.querySelector('.analysis-review-badge');
    if (eyebrow) eyebrow.textContent = 'AÇÃO NECESSÁRIA';
    if (title) title.textContent = expectedTitle;
    if (badge) badge.textContent = 'ANÁLISE INCOMPLETA';

    content.className = 'analysis-proposal-content analysis-incomplete-content';
    content.innerHTML = '';

    const alert = document.createElement('div');
    alert.className = 'analysis-incomplete-alert';
    alert.innerHTML = '<div class="analysis-incomplete-icon">!</div><div><strong></strong><p></p></div>';
    alert.querySelector('strong').textContent = githubAuth ? 'O código ainda não foi analisado.' : 'A análise técnica não foi concluída.';
    alert.querySelector('p').textContent = failure.message || 'A execução foi interrompida antes de produzir uma análise técnica confiável.';
    content.appendChild(alert);

    if (failure.code) {
      const code = document.createElement('span');
      code.className = 'analysis-incomplete-code';
      code.textContent = failure.code;
      content.appendChild(code);
    }

    const actions = document.createElement('div');
    actions.className = 'analysis-incomplete-actions';
    if (githubAuth) {
      const fix = document.createElement('button');
      fix.type = 'button';
      fix.className = 'analysis-fix-credential';
      fix.textContent = 'Corrigir credencial';
      fix.disabled = !isAdmin() || !organization;
      fix.title = fix.disabled ? 'Exige Super Admin e organização GitHub vinculada.' : 'Atualizar a credencial, validar o acesso e retomar esta mesma análise.';
      fix.onclick = () => openCredentialRepair(run);
      actions.appendChild(fix);
    }

    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'analysis-retry-task';
    retry.textContent = 'Testar novamente';
    retry.onclick = () => retrySameTask(run.task_id, retry);
    actions.appendChild(retry);
    content.appendChild(actions);

    const note = document.createElement('p');
    note.className = 'analysis-incomplete-note';
    note.textContent = githubAuth
      ? 'A proposta comercial fica bloqueada até o DevPilot acessar o repositório e concluir a auditoria. A retomada reutiliza a tarefa atual.'
      : 'Estimativas comerciais só são exibidas depois de uma análise técnica concluída com sucesso.';
    content.appendChild(note);
  }

  async function inspectRun(runId) {
    if (!runId) return;
    try {
      const run = await api(`/task-runs/${runId}`);
      if (String(run.status || '').toLowerCase() !== 'failed') return;
      [0, 120, 420, 1000].forEach(delay => window.setTimeout(() => applyIncompleteState(run), delay));
    } catch (_) {
      // A tela original continuará mostrando o erro de carregamento do log.
    }
  }

  injectStyles();
  ensureCredentialDialog();
  document.addEventListener('click', event => {
    const link = event.target.closest?.('.task-log-link');
    const runId = runIdFromLink(link);
    if (runId) inspectRun(runId);
  }, true);
})();
