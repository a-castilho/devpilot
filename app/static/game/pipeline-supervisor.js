/* DevPilot Build Game pipeline supervisor: keep the real delivery pipeline moving without bypassing authorization. */
(() => {
  'use strict';

  if (window.__devpilotGamePipelineSupervisorV46) return;
  window.__devpilotGamePipelineSupervisorV46 = true;

  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const VERIFIER_MARKER = '[DEVPILOT_DELIVERY_VERIFIER_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const MAX_PHASES = 6;
  const LIVE = new Set(['queued', 'planning', 'running', 'review']);
  const RECOVERY_LIVE = new Set(['agent_recovery', 'retesting']);
  const MANUAL_RECOVERY = new Set(['awaiting_intervention', 'intervention_required', 'recovery_exhausted']);
  const reasonLabels = Object.freeze({
    push: 'envio ao Git remoto',
    merge: 'merge de código',
    deploy: 'publicação/deploy',
    production: 'ambiente de produção',
    dependency: 'alteração de dependências',
    destructive: 'operação destrutiva',
    'destructive-migration': 'migração destrutiva',
    credential: 'alteração de credencial',
  });

  let refreshTimer = 0;
  let supervising = false;
  let recoveryTaskId = '';

  const norm = value => String(value || '').split('.').pop().trim().toLowerCase().replaceAll(' ', '_');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#039;',
  }[char]));
  const promptValue = (task, label) => {
    const escaped = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = String(task?.prompt || '').match(new RegExp(`^${escaped}:\\s*(.+)$`, 'mi'));
    return match?.[1]?.trim() || '';
  };
  const phaseFromTask = task => Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  const missionFromTask = task => promptValue(task, 'PARTIDA');
  const isGameTask = task => String(task?.prompt || '').includes(GAME_MARKER);
  const isVerifier = task => String(task?.prompt || '').includes(VERIFIER_MARKER);

  function phaseCard(phaseId) {
    return Array.from(document.querySelectorAll('.build-game-map .build-game-phase'))[phaseId - 1] || null;
  }

  function actionHost(phaseId) {
    return phaseCard(phaseId)?.querySelector('.build-game-phase-actions') || null;
  }

  function installStyle() {
    if (document.getElementById('game-pipeline-supervisor-v46-style')) return;
    const style = document.createElement('style');
    style.id = 'game-pipeline-supervisor-v46-style';
    style.textContent = `
      .game-pipeline-state{display:grid;gap:6px;min-width:min(320px,45vw);max-width:410px;padding:9px 10px;border:1px solid rgba(83,214,255,.2);border-radius:11px;background:rgba(4,18,31,.78)}
      .game-pipeline-state strong{font-size:.72rem;line-height:1.25}.game-pipeline-state small{color:var(--muted,#91a3b8);font-size:.65rem;line-height:1.35}
      .game-pipeline-state.live{border-color:rgba(83,214,255,.26)}.game-pipeline-state.approval{border-color:rgba(255,196,88,.34);background:rgba(63,44,10,.27)}.game-pipeline-state.recovery{border-color:rgba(255,96,128,.32);background:rgba(64,16,32,.28)}
      .game-pipeline-state button{width:100%;min-height:36px!important}.game-pipeline-pulse{display:inline-block;width:7px;height:7px;margin-right:6px;border-radius:50%;background:#55ddff;box-shadow:0 0 12px #55ddff}
      #game-recovery-v46{width:min(760px,94vw);max-height:88vh;padding:0;border:1px solid rgba(76,208,255,.3);border-radius:18px;background:linear-gradient(180deg,#071523,#040b14);color:#eef8ff;box-shadow:0 32px 90px rgba(0,0,0,.7)}
      #game-recovery-v46::backdrop{background:rgba(1,6,13,.84);backdrop-filter:blur(5px)}
      .game-recovery-shell{display:grid;gap:12px;max-height:88vh;padding:18px;overflow:auto}.game-recovery-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.game-recovery-head h2{margin:3px 0 0;font-size:1.35rem}.game-recovery-close{min-width:38px;min-height:38px;border:1px solid rgba(255,255,255,.12);border-radius:9px;background:rgba(255,255,255,.04);color:#b9cada}
      .game-recovery-status,.game-recovery-failure,.game-recovery-guidance{padding:12px;border:1px solid rgba(255,255,255,.09);border-radius:12px;background:rgba(4,17,29,.72)}.game-recovery-status strong,.game-recovery-failure strong{display:block}.game-recovery-status p,.game-recovery-failure p,.game-recovery-guidance p{margin:5px 0 0;color:#9db0bf;font-size:.78rem;line-height:1.5}.game-recovery-failure{border-color:rgba(255,96,128,.25)}
      .game-recovery-track{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.game-recovery-track article{padding:11px;border:1px solid rgba(78,205,255,.15);border-radius:11px;background:rgba(8,25,41,.8)}.game-recovery-track small{display:block;color:#6b879b;font-size:.61rem;font-weight:900;letter-spacing:.08em}.game-recovery-track strong{display:block;margin-top:4px;font-size:.78rem}.game-recovery-track span{display:block;margin-top:4px;color:#90a6b7;font-size:.68rem;line-height:1.4}
      .game-recovery-guidance textarea{width:100%;min-height:110px;margin-top:9px;box-sizing:border-box;padding:10px;border:1px solid rgba(255,198,91,.25);border-radius:9px;background:#06111c;color:#eef8ff;resize:vertical}.game-recovery-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.game-recovery-actions button{min-height:38px}
      @media(max-width:800px){.game-pipeline-state{min-width:0;max-width:none;width:100%}.game-recovery-track{grid-template-columns:1fr}.game-recovery-actions{display:grid}.game-recovery-actions button{width:100%}}
    `;
    document.head.appendChild(style);
  }

  function scheduleRefresh(delay = 4000) {
    window.clearTimeout(refreshTimer);
    const actual = document.visibilityState === 'hidden' ? Math.max(delay, 10000) : delay;
    refreshTimer = window.setTimeout(() => {
      if (typeof window.loadBuildGame === 'function') void window.loadBuildGame();
    }, actual);
  }

  async function fetchMissionTasks() {
    const projectId = localStorage.getItem(PROJECT_KEY) || '';
    const missionId = localStorage.getItem(MISSION_KEY) || '';
    if (!projectId || !missionId || typeof api !== 'function') return {projectId, missionId, tasks:[]};
    const tasks = await api(`/tasks?project_id=${encodeURIComponent(projectId)}&limit=500`);
    const missionTasks = (Array.isArray(tasks) ? tasks : [])
      .filter(task => isGameTask(task) && missionFromTask(task) === missionId)
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    return {projectId, missionId, tasks:missionTasks};
  }

  function currentPipelineTask(tasks) {
    for (let phaseId = 1; phaseId <= MAX_PHASES; phaseId += 1) {
      const latest = tasks.find(task => phaseFromTask(task) === phaseId);
      if (!latest || norm(latest.status) !== 'completed') return {phaseId, task:latest || null};
    }
    return {phaseId:MAX_PHASES + 1, task:null};
  }

  function liveState(phaseId, task) {
    const host = actionHost(phaseId);
    if (!host || !task) return;
    const status = norm(task.status);
    const verifier = isVerifier(task);
    const label = ({queued:'Na fila', planning:'Planejando', running:'Executando', review:'Em revisão'})[status] || status;
    host.innerHTML = `<div class="game-pipeline-state live"><strong><i class="game-pipeline-pulse"></i>${verifier ? 'Gate de entrega' : 'Execução da fase'} · ${esc(label)}</strong><small>Atualização automática ativa. A próxima fase só será liberada depois da prova real da entrega.</small><button class="ghost" type="button" data-pipeline-refresh>Atualizar agora</button></div>`;
  }

  function approvalState(phaseId, task, reasons) {
    const host = actionHost(phaseId);
    if (!host || !task) return;
    const readable = reasons.length ? reasons.map(reason => reasonLabels[reason] || reason).join(', ') : 'autorização explícita solicitada';
    host.innerHTML = `<div class="game-pipeline-state approval"><strong>🛡️ Gate de autorização real</strong><small>Esta etapa pede autorização para: ${esc(readable)}. O jogo não vai contornar esse limite.</small><button class="primary" type="button" data-pipeline-approve="${esc(task.id)}">Autorizar e continuar</button></div>`;
  }

  function recoveryState(phaseId, task, recovery) {
    const host = actionHost(phaseId);
    if (!host || !task) return;
    const state = String(recovery?.state || 'ready_to_recover');
    const labels = {
      ready_to_recover:'Falha confirmada · recuperação disponível',
      agent_recovery:'Agente corrigindo a causa raiz',
      awaiting_intervention:'Aguardando intervenção autorizada',
      intervention_required:'Agente precisa de orientação',
      recovery_exhausted:'Correção sem prova final',
      retesting:'Retestando a execução original',
      resolved:'Fase recuperada',
    };
    host.innerHTML = `<div class="game-pipeline-state recovery"><strong>⚡ ${esc(labels[state] || 'Recuperação da fase')}</strong><small>Falha não vira nova jogada duplicada. A mesma fase entra no protocolo de recuperação e depois é retestada.</small><button class="ghost" type="button" data-pipeline-recovery="${esc(task.id)}">${MANUAL_RECOVERY.has(state) ? 'Intervenção assistida' : state === 'ready_to_recover' ? 'Iniciar recuperação' : 'Abrir recuperação'}</button></div>`;
  }

  async function reconcileApproval(task) {
    try {
      const runtime = await api(`/tasks/${encodeURIComponent(task.id)}/orchestrator`);
      const reasons = Array.isArray(runtime?.gate?.reasons) ? runtime.gate.reasons : [];
      if (!task.requires_approval && reasons.length === 0) {
        await api(`/tasks/${encodeURIComponent(task.id)}/next`, {method:'POST'});
        window.toast?.('Gate antigo reavaliado: nenhuma autorização real é necessária. A fase voltou para a fila.');
        scheduleRefresh(350);
        return {requeued:true, reasons:[]};
      }
      return {requeued:false, reasons};
    } catch (error) {
      console.error('[DEVPILOT_GAME_PIPELINE_APPROVAL]', error);
      return {requeued:false, reasons:[]};
    }
  }

  async function recoveryPayload(taskId) {
    try { return await api(`/tasks/${encodeURIComponent(taskId)}/recovery`); }
    catch (_) { return {task_id:taskId, state:'ready_to_recover', failure:{}}; }
  }

  async function supervise() {
    if (supervising) return;
    supervising = true;
    window.clearTimeout(refreshTimer);
    try {
      const {tasks} = await fetchMissionTasks();
      const {phaseId, task} = currentPipelineTask(tasks);
      if (!task || phaseId > MAX_PHASES) return;
      const status = norm(task.status);

      if (status === 'awaiting_approval') {
        const approval = await reconcileApproval(task);
        if (!approval.requeued) approvalState(phaseId, task, approval.reasons);
        return;
      }

      if (status === 'failed' || status === 'blocked') {
        const recovery = await recoveryPayload(task.id);
        recoveryState(phaseId, task, recovery);
        if (RECOVERY_LIVE.has(String(recovery?.state || ''))) scheduleRefresh(3500);
        return;
      }

      if (LIVE.has(status)) {
        liveState(phaseId, task);
        scheduleRefresh(3500);
      }
    } catch (error) {
      console.error('[DEVPILOT_GAME_PIPELINE]', error);
    } finally {
      supervising = false;
    }
  }

  function ensureRecoveryDialog() {
    let dialog = document.getElementById('game-recovery-v46');
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = 'game-recovery-v46';
    dialog.innerHTML = '<div class="game-recovery-shell"><p>Carregando recuperação…</p></div>';
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
    document.body.appendChild(dialog);
    return dialog;
  }

  function recoveryDescription(state) {
    return ({
      ready_to_recover:'A execução falhou. O agente especializado ainda não iniciou a correção.',
      agent_recovery:'Um agente está removendo a causa raiz sem duplicar a execução original.',
      awaiting_intervention:'A continuação depende de autorização, credencial, permissão ou informação externa.',
      intervention_required:'O agente tentou corrigir, mas precisa de orientação para continuar com segurança.',
      recovery_exhausted:'A recuperação terminou, porém o objetivo original ainda precisa ser comprovado.',
      retesting:'A execução original voltou para a fila e está sendo usada como prova final da correção.',
      resolved:'O objetivo original concluiu depois do protocolo de recuperação.',
    })[state] || 'Acompanhe o protocolo de recuperação.';
  }

  function renderRecovery(data) {
    const dialog = ensureRecoveryDialog();
    const shell = dialog.querySelector('.game-recovery-shell');
    const state = String(data?.state || 'ready_to_recover');
    const failure = data?.failure || {};
    const healing = data?.self_healing || {};
    const recovery = data?.recovery_task || null;
    const manual = Boolean(data?.manual_intervention_required);
    const canResume = Boolean(data?.can_resume_original);
    const attempts = Number(healing?.attempts || data?.original_run?.attempt || 0);
    shell.innerHTML = `
      <div class="game-recovery-head"><div><span class="eyebrow">⚡ RECUPERAÇÃO DA ESTEIRA</span><h2>${esc(data?.task_title || 'Fase do jogo')}</h2></div><button class="game-recovery-close" type="button" data-game-recovery-close>✕</button></div>
      <section class="game-recovery-status"><strong>${esc(state.replaceAll('_',' ').toUpperCase())}</strong><p>${esc(recoveryDescription(state))}</p></section>
      <section class="game-recovery-failure"><strong>${esc(failure.code || 'EXECUTION_FAILED')} · ${esc(failure.category || 'unknown')}</strong><p>${esc(failure.message || 'Falha registrada sem mensagem detalhada.')}</p></section>
      <div class="game-recovery-track">
        <article><small>NÍVEL 1</small><strong>Autocorreção</strong><span>${attempts ? `${attempts} tentativa(s) · ${esc(healing.strategy || 'diagnóstico automático')}` : 'Sem tentativa registrada.'}</span></article>
        <article><small>NÍVEL 2</small><strong>Agente de recuperação</strong><span>${recovery ? `${esc(recovery.status || 'aguardando')} · ${esc(recovery.title || 'missão de recuperação')}` : 'Ainda não iniciado.'}</span></article>
        <article><small>NÍVEL 3</small><strong>Reteste da fase</strong><span>${state === 'resolved' ? 'Objetivo comprovado.' : state === 'retesting' ? 'Prova final em andamento.' : manual ? 'Intervenção necessária.' : 'Aguardando recuperação.'}</span></article>
      </div>
      ${manual ? `<section class="game-recovery-guidance"><strong>Intervenção assistida</strong><p>Informe somente a autorização, condição externa ou contexto que o agente não consegue descobrir sozinho.</p><textarea id="game-recovery-guidance" maxlength="4000" placeholder="Ex.: acesso GitHub já foi liberado; pode validar novamente."></textarea></section>` : ''}
      <div class="game-recovery-actions">
        <button class="ghost" type="button" data-game-recovery-refresh>Atualizar estado</button>
        ${state === 'ready_to_recover' ? '<button class="primary" type="button" data-game-recovery-start>⚡ Iniciar recuperação</button>' : ''}
        ${manual ? '<button class="primary" type="button" data-game-recovery-intervene>Orientar agente e retomar</button>' : ''}
        ${canResume ? '<button class="primary" type="button" data-game-recovery-resume>▶ Retestar fase original</button>' : ''}
      </div>`;
  }

  async function openRecovery(taskId) {
    recoveryTaskId = String(taskId || '');
    const dialog = ensureRecoveryDialog();
    dialog.querySelector('.game-recovery-shell').innerHTML = '<p>Carregando diagnóstico e histórico…</p>';
    if (!dialog.open) dialog.showModal();
    try { renderRecovery(await recoveryPayload(recoveryTaskId)); }
    catch (error) { window.toast?.(error?.message || 'Recuperação indisponível.'); }
  }

  async function recoveryAction(action, body = null) {
    if (!recoveryTaskId) return;
    try {
      const options = {method:'POST'};
      if (body) options.body = JSON.stringify(body);
      const data = await api(`/tasks/${encodeURIComponent(recoveryTaskId)}/recovery/${action}`, options);
      renderRecovery(data);
      window.toast?.('Protocolo de recuperação atualizado.');
      scheduleRefresh(500);
    } catch (error) {
      window.toast?.(error?.message || 'Não foi possível atualizar a recuperação.');
    }
  }

  async function approve(taskId) {
    try {
      await api(`/tasks/${encodeURIComponent(taskId)}/approve`, {method:'POST'});
      try { await api(`/tasks/${encodeURIComponent(taskId)}/next`, {method:'POST'}); } catch (_) {}
      window.toast?.('Etapa autorizada. A esteira voltou para a fila.');
      scheduleRefresh(300);
    } catch (error) {
      window.toast?.(error?.message || 'Não foi possível autorizar esta etapa.');
    }
  }

  function installClicks() {
    document.addEventListener('click', event => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target) return;
      const refresh = target.closest('[data-pipeline-refresh]');
      if (refresh) { event.preventDefault(); void window.loadBuildGame?.(); return; }
      const approval = target.closest('[data-pipeline-approve]');
      if (approval) { event.preventDefault(); void approve(approval.dataset.pipelineApprove); return; }
      const recovery = target.closest('[data-pipeline-recovery]');
      if (recovery) { event.preventDefault(); void openRecovery(recovery.dataset.pipelineRecovery); return; }
      if (target.closest('[data-game-recovery-close]')) { event.preventDefault(); ensureRecoveryDialog().close(); return; }
      if (target.closest('[data-game-recovery-refresh]')) { event.preventDefault(); void openRecovery(recoveryTaskId); return; }
      if (target.closest('[data-game-recovery-start]')) { event.preventDefault(); void recoveryAction('escalate'); return; }
      if (target.closest('[data-game-recovery-resume]')) { event.preventDefault(); void recoveryAction('resume'); return; }
      if (target.closest('[data-game-recovery-intervene]')) {
        event.preventDefault();
        const instruction = String(document.querySelector('#game-recovery-guidance')?.value || '').trim();
        if (instruction.length < 3) { window.toast?.('Descreva a orientação que o agente deve considerar.'); return; }
        void recoveryAction('intervene', {instruction});
      }
    }, true);
  }

  installStyle();
  installClicks();

  const upstreamLoad = window.loadBuildGame;
  if (typeof upstreamLoad === 'function') {
    window.loadBuildGame = async (...args) => {
      const result = await upstreamLoad(...args);
      await supervise();
      return result;
    };
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') scheduleRefresh(150);
  });
  window.setTimeout(() => void supervise(), 150);
})();
