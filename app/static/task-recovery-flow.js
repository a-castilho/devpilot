(() => {
  'use strict';

  if (window.__devpilotTaskRecoveryFlowV104) return;
  window.__devpilotTaskRecoveryFlowV104 = true;
  window.__devpilotTaskRecoveryFlow = true;

  const MODAL_ID = 'task-recovery-modal';
  const FAILURE_STATUSES = new Set(['failed', 'blocked']);
  const ACTIVE_RECOVERY = new Set(['agent_recovery', 'retesting']);
  const PLATFORM_STDIN_MARKERS = [
    'reading additional input from stdin',
    'failed to read prompt from stdin',
    'no prompt provided via stdin',
  ];

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#039;',
  }[char]));
  const norm = value => String(value || '').split('.').pop().trim().toLowerCase().replaceAll(' ', '_');

  const STATE_LABELS = {
    ready_to_recover: 'FALHA CONFIRMADA · RECUPERAÇÃO DISPONÍVEL',
    agent_recovery: 'AGENTE DE RECUPERAÇÃO EM MISSÃO',
    awaiting_intervention: 'AGUARDANDO INTERVENÇÃO AUTORIZADA',
    intervention_required: 'AGENTE NÃO CONSEGUIU RESOLVER SOZINHO',
    recovery_exhausted: 'CORREÇÃO FEITA, MAS O RETESTE AINDA FALHOU',
    retesting: 'RETESTANDO EXECUÇÃO ORIGINAL',
    resolved: 'MISSÃO RECUPERADA',
  };

  const FAILURE_GUIDANCE = {
    github_auth: 'Atualize ou autorize a credencial GitHub em Organizações. Depois registre abaixo que o acesso foi restabelecido para o agente confirmar e continuar.',
    codex_auth: 'Autorize o Codex no ambiente de execução. Depois informe abaixo que a autenticação foi concluída.',
    filesystem_permission: 'Ajuste somente a permissão necessária no ambiente autorizado. O agente não deve elevar permissões sozinho.',
    database: 'Restabeleça o banco/serviço afetado ou indique ao agente qual ambiente autorizado deve ser usado. Nenhuma operação insegura sobre dados será feita automaticamente.',
    git_network: 'A rede já recebeu tentativas automáticas. Se a conectividade estiver normal agora, retome a missão para uma nova validação.',
    repository_state: 'O agente tentou isolar o checkout inconsistente. Se ainda falhou, informe qualquer restrição do repositório antes de uma nova correção.',
    unknown: 'Descreva o que você sabe sobre a falha, o comportamento esperado ou qualquer condição externa que o agente não consegue descobrir sozinho.',
  };

  function platformStdinFailure(data, failure) {
    const evidence = [
      failure?.category,
      failure?.code,
      failure?.message,
      failure?.technical_message,
      data?.platform_recovery?.kind,
    ].map(value => String(value || '').toLowerCase()).join('\n');
    return (
      evidence.includes('executor_runtime') ||
      evidence.includes('executor_stdin_blocked') ||
      PLATFORM_STDIN_MARKERS.some(marker => evidence.includes(marker))
    );
  }

  function injectStyle() {
    if (document.getElementById('task-recovery-flow-style')) return;
    const style = document.createElement('style');
    style.id = 'task-recovery-flow-style';
    style.textContent = `
      .task-recovery-action{position:relative;display:inline-flex!important;align-items:center;justify-content:center;gap:6px;min-height:32px!important;padding:6px 10px!important;border:1px solid rgba(255,111,145,.5)!important;border-radius:9px!important;background:linear-gradient(135deg,rgba(96,22,46,.74),rgba(30,21,44,.9))!important;color:#ffd5df!important;font-size:8px!important;font-weight:900!important;letter-spacing:.04em;text-transform:uppercase;box-shadow:inset 0 0 18px rgba(255,69,120,.08),0 0 16px rgba(255,69,120,.08);cursor:pointer}
      .task-recovery-action::before{content:'⚡';font-size:11px}.task-recovery-action:hover{border-color:#ff7799!important;box-shadow:0 0 22px rgba(255,88,137,.2)}
      #${MODAL_ID}{width:min(880px,94vw);max-height:90vh;padding:0;border:1px solid rgba(91,210,255,.3);border-radius:20px;background:radial-gradient(circle at 80% 0,rgba(33,88,130,.18),transparent 35%),linear-gradient(180deg,#071321,#040b14);color:#edf7ff;box-shadow:0 34px 100px rgba(0,0,0,.72),0 0 50px rgba(57,184,255,.08)}
      #${MODAL_ID}::backdrop{background:rgba(1,5,12,.82);backdrop-filter:blur(6px)}
      .recovery-shell{display:grid;gap:14px;max-height:90vh;padding:20px;overflow:auto;scrollbar-width:thin}.recovery-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.recovery-head h2{margin:4px 0 0;font-size:clamp(22px,3vw,34px);line-height:1.05}.recovery-head .eyebrow{color:#63d9ff}.recovery-close{border:1px solid rgba(255,255,255,.12);border-radius:9px;background:rgba(255,255,255,.04);color:#a9bdd0;min-width:38px;min-height:38px;cursor:pointer}
      .recovery-state{display:grid;grid-template-columns:auto minmax(0,1fr);gap:12px;align-items:center;padding:13px 15px;border:1px solid rgba(102,205,255,.2);border-radius:14px;background:rgba(9,27,43,.72)}.recovery-state-orb{width:34px;height:34px;border-radius:50%;background:radial-gradient(circle,#75e8ff 0 20%,#1477a1 22% 44%,rgba(20,119,161,.2) 46%);box-shadow:0 0 22px rgba(72,214,255,.45)}.recovery-state strong{display:block;color:#dff8ff;font-size:11px;letter-spacing:.08em}.recovery-state p{margin:4px 0 0;color:#8fa7bb;font-size:11px;line-height:1.45}
      .recovery-failure{display:grid;gap:7px;padding:13px 15px;border:1px solid rgba(255,103,134,.24);border-radius:14px;background:rgba(54,13,28,.42)}.recovery-failure code{width:max-content;max-width:100%;padding:4px 7px;border-radius:7px;background:#080d15;color:#ffabc0;font-size:9px;overflow-wrap:anywhere}.recovery-failure p{margin:0;color:#d0aab5;font-size:11px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere}
      .recovery-correction{display:grid;gap:5px;padding:12px 14px;border:1px solid rgba(90,224,255,.22);border-radius:12px;background:rgba(8,38,52,.52)}.recovery-correction strong{color:#70e8ff;font-size:9px;letter-spacing:.08em}.recovery-correction p{margin:0;color:#b6d7e4;font-size:10px;line-height:1.5}
      .recovery-track{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.recovery-stage{position:relative;min-width:0;padding:14px;border:1px solid rgba(122,158,190,.16);border-radius:14px;background:linear-gradient(180deg,rgba(14,28,44,.88),rgba(7,17,29,.92))}.recovery-stage::before{content:'';position:absolute;left:13px;top:13px;width:7px;height:7px;border-radius:50%;background:#5d7185;box-shadow:0 0 10px currentColor}.recovery-stage.active::before{background:#59d7ff;box-shadow:0 0 14px #59d7ff}.recovery-stage.warning::before{background:#ffc661;box-shadow:0 0 14px #ffc661}.recovery-stage.success::before{background:#54e6a5;box-shadow:0 0 14px #54e6a5}.recovery-stage span,.recovery-stage strong,.recovery-stage small{display:block;padding-left:14px}.recovery-stage span{color:#718aa0;font-size:8px;font-weight:900;letter-spacing:.08em;text-transform:uppercase}.recovery-stage strong{margin-top:5px;color:#e8f4fc;font-size:12px}.recovery-stage small{margin-top:5px;color:#8197aa;font-size:9px;line-height:1.4}
      .recovery-intervention{display:grid;gap:10px;padding:14px;border:1px solid rgba(255,197,91,.24);border-radius:14px;background:linear-gradient(135deg,rgba(76,50,13,.34),rgba(18,20,27,.8))}.recovery-intervention strong{color:#ffe2a7}.recovery-intervention p{margin:0;color:#bea985;font-size:10px;line-height:1.5}.recovery-intervention textarea{width:100%;min-height:110px;box-sizing:border-box;padding:11px;border:1px solid rgba(255,197,91,.24);border-radius:10px;background:#07111b;color:#eaf3f8;resize:vertical;outline:none}.recovery-intervention textarea:focus{border-color:#ffc75f;box-shadow:0 0 0 3px rgba(255,199,95,.08)}
      .recovery-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.recovery-actions button{min-height:38px;padding:8px 12px;border-radius:9px;font-size:10px;font-weight:850;cursor:pointer}.recovery-primary{border:1px solid #1a9bc8;background:linear-gradient(135deg,#0f7099,#125376);color:white}.recovery-warning{border:1px solid #a97d2f;background:#493717;color:#ffe0a0}.recovery-ghost{border:1px solid rgba(255,255,255,.13);background:rgba(255,255,255,.04);color:#b4c5d4}.recovery-actions button:disabled{opacity:.5;cursor:progress}
      .recovery-live{display:inline-flex;align-items:center;gap:7px;color:#72e8ba;font-size:9px}.recovery-live i{width:7px;height:7px;border-radius:50%;background:#53e6a6;box-shadow:0 0 12px #53e6a6}
      @media(max-width:720px){.recovery-track{grid-template-columns:1fr}.recovery-actions{display:grid}.recovery-actions button{width:100%}.recovery-shell{padding:14px}}
      @media(prefers-reduced-motion:reduce){#${MODAL_ID} *{animation:none!important;transition:none!important}}
    `;
    document.head.appendChild(style);
  }

  function ensureModal() {
    let modal = document.getElementById(MODAL_ID);
    if (modal) return modal;
    modal = document.createElement('dialog');
    modal.id = MODAL_ID;
    modal.innerHTML = '<div class="recovery-shell"><p>Carregando diagnóstico…</p></div>';
    modal.addEventListener('click', event => { if (event.target === modal) modal.close(); });
    document.body.appendChild(modal);
    return modal;
  }

  function stageClass(condition, warning = false) {
    if (condition) return warning ? 'warning' : 'active';
    return '';
  }

  function render(data) {
    const modal = ensureModal();
    const shell = modal.querySelector('.recovery-shell');
    const sourceFailure = data?.failure || {};
    const platform = platformStdinFailure(data, sourceFailure);
    const taskStatus = norm(data?.task_status);
    const healing = data?.self_healing || {};
    const recovery = platform ? null : (data?.recovery_task || null);
    const serverState = String(data?.state || 'ready_to_recover');
    const stateName = platform
      ? (['queued','planning','running','review'].includes(taskStatus) ? 'retesting' : taskStatus === 'completed' ? 'resolved' : 'ready_to_recover')
      : serverState;
    const manual = platform ? false : Boolean(data?.manual_intervention_required);
    const canResume = platform ? false : Boolean(data?.can_resume_original);
    const failure = platform ? {
      ...sourceFailure,
      category:'executor_runtime',
      code:'EXECUTOR_STDIN_BLOCKED',
      message:'O runner do DevPilot bloqueou antes de executar o prompt porque o Codex tentou ler entrada adicional pelo stdin. O projeto não é a causa desta falha.',
      recommended_action:'Reexecutar exatamente esta tarefa no runner DevPilot corrigido. Não alterar o projeto e não iniciar agente de recuperação do repositório.',
    } : sourceFailure;
    const category = String(failure.category || 'unknown');
    const attempts = Number(healing.attempts || data?.original_run?.attempt || 0);
    const recoveryStatus = norm(recovery?.status);
    const agentSuccess = recoveryStatus === 'completed' && String(recovery?.run_status || '') === 'success';
    const agentActive = ['queued','planning','running','review'].includes(recoveryStatus);
    const autoResolved = String(healing.status || '') === 'resolved';

    const stateDescription = platform
      ? (stateName === 'retesting'
          ? 'A tarefa original está sendo executada novamente no runner corrigido. Nenhuma missão de recuperação do projeto participa deste reteste.'
          : stateName === 'resolved'
            ? 'A tarefa original concluiu no runner corrigido.'
            : 'A causa está no runtime do DevPilot, não no código do projeto. O próximo passo seguro é retestar exatamente a tarefa original.')
      : ({
          ready_to_recover:'A autocorreção terminou sem remover a causa. Uma missão especializada pode assumir o diagnóstico sem duplicar a execução original.',
          agent_recovery:'Um agente está trabalhando especificamente na causa raiz. A execução original permanece parada para evitar repetir o erro.',
          awaiting_intervention:'A falha depende de autorização, credencial, permissão ou informação que o agente não pode inventar.',
          intervention_required:'O agente de recuperação tentou resolver, mas ainda precisa de contexto ou ação externa.',
          recovery_exhausted:'A missão de recuperação chegou ao fim, mas o objetivo original ainda não foi comprovado. Oriente o agente ou reteste quando a condição externa estiver resolvida.',
          retesting:'A execução original voltou para a fila para provar que a causa raiz realmente foi removida.',
          resolved:'A execução original concluiu depois do fluxo de recuperação.',
        })[stateName] || 'Acompanhe o estado da recuperação.';

    const stateLabel = platform
      ? (stateName === 'retesting' ? 'RETESTANDO NO RUNNER CORRIGIDO' : stateName === 'resolved' ? 'RUNNER VALIDADO' : 'FALHA DO RUNTIME · RETESTE DISPONÍVEL')
      : (STATE_LABELS[stateName] || stateName.toUpperCase());
    const eyebrow = platform ? '⚙ CORREÇÃO DO RUNTIME DE EXECUÇÃO' : '⚡ PROTOCOLO DE RECUPERAÇÃO';
    const correction = String(failure.recommended_action || '').trim();

    const track = platform ? `
      <div class="recovery-track">
        <div class="recovery-stage warning"><span>NÍVEL 1</span><strong>Falha do runtime identificada</strong><small>O prompt não foi executado corretamente por causa do stdin do runner.</small></div>
        <div class="recovery-stage success"><span>NÍVEL 2</span><strong>Recovery de projeto dispensada</strong><small>Não alterar repositório, credenciais ou código para corrigir uma falha interna do DevPilot.</small></div>
        <div class="recovery-stage ${stateName === 'resolved' ? 'success' : stateName === 'retesting' ? 'active' : ''}"><span>NÍVEL 3</span><strong>Reteste da tarefa original</strong><small>${stateName === 'resolved' ? 'Execução comprovada.' : stateName === 'retesting' ? 'Execução original em andamento.' : 'Aguardando seu comando para reexecutar a mesma tarefa.'}</small></div>
      </div>` : `
      <div class="recovery-track">
        <div class="recovery-stage ${autoResolved ? 'success' : attempts ? 'warning' : ''}"><span>NÍVEL 1</span><strong>Autocorreção</strong><small>${attempts ? `${attempts} tentativa(s) automática(s) · ${esc(healing.strategy || 'diagnóstico automático')}` : 'Sem tentativa registrada.'}</small></div>
        <div class="recovery-stage ${agentSuccess ? 'success' : stageClass(agentActive || Boolean(recovery), recoveryStatus === 'failed' || recoveryStatus === 'blocked')}"><span>NÍVEL 2</span><strong>Agente de recuperação</strong><small>${recovery ? `${esc(recovery.title || 'Missão de recuperação')} · ${esc(recovery.status || 'aguardando')}` : 'Ainda não iniciado.'}</small></div>
        <div class="recovery-stage ${stateName === 'resolved' ? 'success' : stageClass(stateName === 'retesting', manual)}"><span>NÍVEL 3</span><strong>Reteste / intervenção</strong><small>${stateName === 'resolved' ? 'Objetivo original comprovado.' : stateName === 'retesting' ? 'Execução original em prova final.' : manual ? 'Ação humana assistida necessária.' : 'Aguardando a missão de recuperação.'}</small></div>
      </div>`;

    shell.innerHTML = `
      <div class="recovery-head"><div><span class="eyebrow">${eyebrow}</span><h2>${esc(data?.task_title || 'Execução')}</h2></div><button class="recovery-close" type="button" data-recovery-close>✕</button></div>
      <div class="recovery-state"><span class="recovery-state-orb" aria-hidden="true"></span><div><strong>${esc(stateLabel)}</strong><p>${esc(stateDescription)}</p></div></div>
      <div class="recovery-failure"><code>${esc(failure.code || 'EXECUTION_FAILED')} · ${esc(category)}</code><p>${esc(failure.message || 'Falha registrada sem mensagem detalhada.')}</p></div>
      ${correction ? `<div class="recovery-correction"><strong>CORREÇÃO CORRETA</strong><p>${esc(correction)}</p></div>` : ''}
      ${track}
      ${manual ? `<div class="recovery-intervention"><strong>INTERVENÇÃO ASSISTIDA</strong><p>${esc(FAILURE_GUIDANCE[category] || FAILURE_GUIDANCE.unknown)}</p><textarea id="task-recovery-guidance" maxlength="4000" placeholder="Ex.: credencial atualizada e validada; pode retestar. Ou: o serviço correto é X e deve usar a porta Y..."></textarea></div>` : ''}
      <div class="recovery-actions">
        ${ACTIVE_RECOVERY.has(stateName) ? '<span class="recovery-live"><i></i> fluxo em andamento</span>' : ''}
        <button type="button" class="recovery-ghost" data-recovery-refresh>Atualizar estado</button>
        ${stateName === 'ready_to_recover' ? `<button type="button" class="recovery-primary" data-recovery-start>${platform ? '▶ Reexecutar tarefa no runner corrigido' : '⚡ Iniciar missão de recuperação'}</button>` : ''}
        ${manual ? '<button type="button" class="recovery-warning" data-recovery-intervene>Orientar agente e retomar</button>' : ''}
        ${canResume ? '<button type="button" class="recovery-primary" data-recovery-resume>▶ Retestar execução original</button>' : ''}
      </div>`;
    modal.dataset.taskId = String(data?.task_id || '');
    modal.dataset.platformRecovery = platform ? '1' : '0';
  }

  async function fetchRecovery(taskId) {
    return api(`/tasks/${encodeURIComponent(taskId)}/recovery`);
  }

  async function refreshModal() {
    const modal = ensureModal();
    const taskId = String(modal.dataset.taskId || '');
    if (!taskId) return;
    const shell = modal.querySelector('.recovery-shell');
    shell.setAttribute('aria-busy', 'true');
    try { render(await fetchRecovery(taskId)); }
    catch (error) { window.toast?.(error?.message || 'Não foi possível atualizar a recuperação.'); }
    finally { shell.removeAttribute('aria-busy'); }
  }

  async function openRecovery(taskId) {
    const modal = ensureModal();
    modal.dataset.taskId = String(taskId || '');
    modal.querySelector('.recovery-shell').innerHTML = '<p>Carregando diagnóstico e histórico de autocorreção…</p>';
    if (!modal.open) modal.showModal();
    try { render(await fetchRecovery(taskId)); }
    catch (error) {
      modal.querySelector('.recovery-shell').innerHTML = `<div class="recovery-head"><h2>Recuperação indisponível</h2><button class="recovery-close" type="button" data-recovery-close>✕</button></div><div class="recovery-failure"><p>${esc(error?.message || 'Não foi possível carregar o fluxo de recuperação.')}</p></div>`;
    }
  }

  async function perform(path, button, options = {}) {
    const modal = ensureModal();
    const taskId = String(modal.dataset.taskId || '');
    if (!taskId) return;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Processando…';
    try {
      const data = await api(`/tasks/${encodeURIComponent(taskId)}/recovery/${path}`, {method:'POST', ...options});
      render(data);
      window.toast?.('Fluxo de recuperação atualizado.');
      if (typeof window.loadAllTasks === 'function') void window.loadAllTasks(true, 20);
      else if (typeof window.load === 'function') void window.load();
    } catch (error) {
      window.toast?.(error?.message || 'Não foi possível atualizar a recuperação.');
      button.disabled = false;
      button.textContent = original;
    }
  }

  async function retryPlatformTask(button) {
    const modal = ensureModal();
    const taskId = String(modal.dataset.taskId || '');
    if (!taskId) return;
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Reenfileirando tarefa original…';
    try {
      await api(`/tasks/${encodeURIComponent(taskId)}/retry`, {method:'POST'});
      render(await fetchRecovery(taskId));
      window.toast?.('Tarefa original reenfileirada no runner corrigido.');
      if (typeof window.loadAllTasks === 'function') void window.loadAllTasks(true, 20);
      else if (typeof window.load === 'function') void window.load();
    } catch (error) {
      window.toast?.(error?.message || 'Não foi possível reenfileirar a tarefa original.');
      button.disabled = false;
      button.textContent = original;
    }
  }

  function decorateRows() {
    const tasks = typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks : [];
    document.querySelectorAll('#tasks-table .tasks-v9-row[data-task-id], #tasks-table .task-main-row[data-task-id]').forEach(row => {
      const taskId = String(row.dataset.taskId || '');
      const task = tasks.find(item => String(item.id) === taskId);
      const actions = row.querySelector('.tasks-v9-actions, .task-actions') || row.lastElementChild;
      const failed = task && String(task.source || '') !== 'failure-recovery' && FAILURE_STATUSES.has(norm(task.status));
      const existing = actions?.querySelector('.task-recovery-action');
      if (!failed) { existing?.remove(); return; }
      if (!actions || existing) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'task-recovery-action';
      button.dataset.taskRecovery = taskId;
      button.textContent = 'Recuperar';
      button.title = 'Abrir diagnóstico e executar somente a correção apropriada para a causa detectada';
      actions.prepend(button);
    });
  }

  function installClicks() {
    if (document.documentElement.dataset.taskRecoveryClicks === '1') return;
    document.documentElement.dataset.taskRecoveryClicks = '1';
    document.addEventListener('click', event => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;
      const open = target.closest('[data-task-recovery]');
      if (open) { event.preventDefault(); event.stopPropagation(); void openRecovery(open.dataset.taskRecovery); return; }
      if (target.closest('[data-recovery-close]')) { event.preventDefault(); ensureModal().close(); return; }
      const refresh = target.closest('[data-recovery-refresh]');
      if (refresh) { event.preventDefault(); void refreshModal(); return; }
      const start = target.closest('[data-recovery-start]');
      if (start) {
        event.preventDefault();
        if (ensureModal().dataset.platformRecovery === '1') void retryPlatformTask(start);
        else void perform('escalate', start);
        return;
      }
      const intervene = target.closest('[data-recovery-intervene]');
      if (intervene) {
        event.preventDefault();
        const instruction = String(document.querySelector('#task-recovery-guidance')?.value || '').trim();
        if (instruction.length < 3) { window.toast?.('Descreva a intervenção ou informação que o agente deve considerar.'); return; }
        void perform('intervene', intervene, {body:JSON.stringify({instruction})});
        return;
      }
      const resume = target.closest('[data-recovery-resume]');
      if (resume) { event.preventDefault(); void perform('resume', resume); }
    }, true);
  }

  function install() {
    injectStyle();
    installClicks();
    decorateRows();
  }

  document.addEventListener('devpilot:tasks-rendered', decorateRows);
  document.addEventListener('devpilot:view-changed', event => { if (event.detail?.view === 'tasks') window.setTimeout(decorateRows, 30); });
  document.addEventListener('devpilot:feature-ready', event => { if (event.detail?.feature === 'tasks') install(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once:true}); else install();
})();