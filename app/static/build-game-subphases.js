/* DevPilot Build Game corrective subphases: real failures become gated repair missions. */
(() => {
  'use strict';

  if (window.__devpilotBuildGameSubphasesReady) return;
  window.__devpilotBuildGameSubphasesReady = true;

  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const SUBPHASE_MARKER = '[DEVPILOT_BUILD_GAME_SUBPHASE_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';
  const GUARD_PREFIX = 'devpilot-build-game-subphase-created';
  const MAX_SUBPHASES = 12;
  const PHASE_NAMES = ['Mapa da missão','Primeiro circuito','Regras blindadas','Interface jogável','Batalha de testes','Chefe final'];
  const FAILURE_STATUSES = new Set(['failed', 'blocked']);
  let syncInFlight = null;

  const normalize = value => String(value || '').toLowerCase().replaceAll(' ', '_');
  const escapeRegExp = value => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const promptValue = (task, label) => {
    const match = String(task?.prompt || '').match(new RegExp(`^${escapeRegExp(label)}:\\s*(.+)$`, 'mi'));
    return match?.[1]?.trim() || '';
  };
  const phaseFromTask = task => Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  const missionFromTask = task => promptValue(task, 'PARTIDA');
  const isGameTask = task => String(task?.prompt || '').includes(GAME_MARKER);
  const isSubphaseTask = task => String(task?.prompt || '').includes(SUBPHASE_MARKER);
  const createdAt = task => new Date(task?.created_at || 0).getTime();
  const correctionNumber = task => Number(promptValue(task, 'SUBFASE').split('.')[1]) || 0;

  const installStyle = () => {
    if (document.querySelector('#build-game-subphases-style')) return;
    const style = document.createElement('style');
    style.id = 'build-game-subphases-style';
    style.textContent = `
      #build-game-view .build-game-phase{min-width:0;box-sizing:border-box}
      .build-game-subphases{grid-column:1/-1;width:100%;min-width:0;box-sizing:border-box;margin:4px 0 0;padding:12px 0 0 16px;border-left:2px solid rgba(101,223,255,.2);display:grid;gap:8px;overflow:hidden}
      .build-game-subphases-head{min-width:0;display:flex;align-items:center;justify-content:space-between;gap:10px;color:var(--muted,#9eacc2);font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;font-weight:800;flex-wrap:wrap}
      .build-game-subphase{width:100%;min-width:0;box-sizing:border-box;display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:10px;align-items:center;padding:10px 12px;border:1px solid rgba(101,223,255,.12);border-radius:12px;background:rgba(4,13,24,.62)}
      .build-game-subphase.completed{border-color:rgba(104,240,187,.22)}
      .build-game-subphase.failed,.build-game-subphase.blocked{border-color:rgba(255,116,116,.28)}
      .build-game-subphase-icon{display:grid;place-items:center;width:32px;height:32px;border-radius:10px;background:rgba(255,255,255,.05)}
      .build-game-subphase-copy{min-width:0;overflow:hidden}.build-game-subphase-copy small{display:block;color:#65dfff;font-size:.64rem;font-weight:800;letter-spacing:.06em}.build-game-subphase-copy strong{display:block;margin:2px 0;font-size:.82rem;overflow-wrap:anywhere}.build-game-subphase-copy p{margin:0;color:var(--muted,#9eacc2);font-size:.72rem;white-space:normal;overflow-wrap:anywhere}
      .build-game-subphase-state{min-width:0;max-width:100%;display:flex;align-items:center;gap:7px;justify-content:flex-end;flex-wrap:wrap}
      .build-game-subphase-error{grid-column:1/-1;min-width:0;box-sizing:border-box;padding:8px 10px;border-radius:9px;background:rgba(255,97,97,.07);color:#ffb1b1;font-size:.72rem;overflow-wrap:anywhere}
      .build-game-subphase-wait{grid-column:1/-1;min-width:0;box-sizing:border-box;padding:9px 11px;border:1px dashed rgba(255,190,94,.28);border-radius:10px;color:#e5c18c;font-size:.72rem;overflow-wrap:anywhere}
      @media(max-width:800px){.build-game-subphases{margin:4px 0 0;padding:10px 0 0 10px}.build-game-subphase{grid-template-columns:32px minmax(0,1fr);padding:10px}.build-game-subphase-state{grid-column:1/-1;justify-content:flex-start}}
      @media(max-width:520px){.build-game-subphases{padding-left:8px}.build-game-subphase{grid-template-columns:28px minmax(0,1fr);gap:8px}.build-game-subphase-icon{width:28px;height:28px}.build-game-subphases-head{font-size:.62rem}}
    `;
    document.head.appendChild(style);
  };

  const failureByTask = summaries => new Map((Array.isArray(summaries) ? summaries : []).map(item => [String(item.task_id), item]));

  const correctionPrompt = ({phaseId, number, goal, missionId, failedTask, failure}) => {
    const reason = String(failure?.failure_reason || 'A execução terminou com falha ou bloqueio sem mensagem detalhada.').slice(0, 4000);
    const category = String(failure?.failure_category || 'unknown');
    const code = String(failure?.failure_code || 'EXECUTION_FAILED');
    const logUrl = String(failure?.log_url || 'indisponível');
    return `${GAME_MARKER}\n${SUBPHASE_MARKER}\n[DEVPILOT_MODE=fix]\nPARTIDA: ${missionId}\nFASE: ${phaseId}/6\nSUBFASE: ${phaseId}.${number}\nOBJETIVO: ${goal}\nTAREFA_ORIGEM: ${failedTask.id}\nCATEGORIA_FALHA: ${category}\nCODIGO_FALHA: ${code}\nLOG_DA_FALHA: ${logUrl}\nMOTIVO_DA_SUBFASE: ${reason}\n\nMISSÃO DA SUBFASE:\nCorrija a causa raiz da falha que interrompeu a fase ${phaseId} (${PHASE_NAMES[phaseId - 1] || 'fase do jogo'}). Esta é uma correção obrigatória criada automaticamente pelo Jogo de construção.\n\nREGRAS DA CORREÇÃO:\n- Leia AGENTS.md e preserve as regras e mudanças válidas do projeto.\n- Use o motivo, categoria e código da falha acima como evidência inicial; consulte os registros reais disponíveis antes de decidir a correção.\n- Corrija a causa raiz, não apenas a mensagem superficial.\n- Repita exatamente a verificação que falhou quando ela puder ser identificada e execute os testes relacionados.\n- Não silencie teste, não remova assert válido, não introduza mock indevido e não transforme erro em sucesso por fallback.\n- Não exponha credenciais e não contorne autenticação ou autorização.\n- Se a falha exigir autorização externa, pare de forma segura e descreva a autorização necessária.\n- Registre no resultado o erro encontrado, a correção aplicada e as evidências de validação.\n- Não avance para a próxima fase. Esta subfase precisa terminar como concluída para liberar a progressão.\n\nCRITÉRIO DE VITÓRIA DA SUBFASE:\nA causa da falha foi corrigida e a verificação que a revelou, junto dos testes aplicáveis, foi executada novamente sem falhas não resolvidas.`;
  };

  const createCorrection = async ({projectId, missionId, phaseId, number, goal, failedTask, failure}) => {
    const guardKey = `${GUARD_PREFIX}:${failedTask.id}`;
    if (localStorage.getItem(guardKey)) return false;
    localStorage.setItem(guardKey, 'creating');
    try {
      await api('/tasks', {
        method: 'POST',
        body: JSON.stringify({
          project_id: projectId,
          title: `[Jogo] Fase ${phaseId}.${number} · Correção ${number} · ${PHASE_NAMES[phaseId - 1] || 'Subfase'}`,
          prompt: correctionPrompt({phaseId, number, goal, missionId, failedTask, failure}),
          source: 'dashboard',
          priority: Math.min(100, 86 + number),
          requires_approval: Boolean(failure?.requires_authorization)
        })
      });
      localStorage.setItem(guardKey, 'created');
      toast(failure?.requires_authorization ? `Subfase ${phaseId}.${number} criada · aguarda autorização` : `Subfase ${phaseId}.${number} criada para corrigir a falha`);
      return true;
    } catch (error) {
      localStorage.removeItem(guardKey);
      toast(`Falha ao criar subfase: ${error.message}`);
      return false;
    }
  };

  const context = async () => {
    const projectId = localStorage.getItem(PROJECT_KEY) || '';
    const missionId = localStorage.getItem(MISSION_KEY) || '';
    if (!projectId || !missionId) return null;
    const [tasks, summaries] = await Promise.all([
      api(`/tasks?project_id=${encodeURIComponent(projectId)}&limit=500`),
      api('/task-runs/latest?limit=500')
    ]);
    const missionTasks = (Array.isArray(tasks) ? tasks : [])
      .filter(task => isGameTask(task) && missionFromTask(task) === missionId)
      .sort((a, b) => createdAt(b) - createdAt(a));
    return {projectId, missionId, missionTasks, failures: failureByTask(summaries)};
  };

  const renderPhaseSubphases = (phaseId, phaseTasks, failures) => {
    const card = document.querySelectorAll('#build-game-view .build-game-phase')[phaseId - 1];
    if (!card) return;
    card.querySelector('.build-game-subphases')?.remove();
    const corrections = phaseTasks.filter(isSubphaseTask).sort((a, b) => createdAt(a) - createdAt(b));
    if (!corrections.length) return;

    const container = document.createElement('div');
    container.className = 'build-game-subphases';
    container.innerHTML = `<div class="build-game-subphases-head"><span>Subfases · erros e correções</span><span>${corrections.length} correção${corrections.length === 1 ? '' : 'ões'}</span></div>`;
    corrections.forEach((task, index) => {
      const taskStatus = normalize(task.status);
      const failure = failures.get(String(task.id));
      const reason = promptValue(task, 'MOTIVO_DA_SUBFASE');
      const row = document.createElement('div');
      row.className = `build-game-subphase ${taskStatus}`;
      row.innerHTML = `
        <div class="build-game-subphase-icon" aria-hidden="true">${taskStatus === 'completed' ? '✓' : taskStatus === 'failed' || taskStatus === 'blocked' ? '!' : '↻'}</div>
        <div class="build-game-subphase-copy"><small>SUBFASE ${phaseId}.${correctionNumber(task) || index + 1}</small><strong>${taskStatus === 'completed' ? 'Correção validada' : 'Correção da fase em andamento'}</strong><p>${esc(reason || failure?.failure_reason || 'Subfase criada a partir de uma falha real da execução.')}</p></div>
        <div class="build-game-subphase-state">${status(task.status)}</div>
        ${failure?.failure_reason && FAILURE_STATUSES.has(taskStatus) ? `<div class="build-game-subphase-error"><b>${esc(failure.failure_code || 'EXECUTION_FAILED')}</b> · ${esc(failure.failure_reason)}</div>` : ''}`;
      container.appendChild(row);
    });
    card.appendChild(container);
  };

  const syncSubphases = async ({allowCreate = true} = {}) => {
    installStyle();
    const data = await context();
    if (!data) return false;
    let created = false;
    for (let phaseId = 1; phaseId <= 6; phaseId += 1) {
      const phaseTasks = data.missionTasks.filter(task => phaseFromTask(task) === phaseId);
      if (!phaseTasks.length) continue;
      const latest = phaseTasks[0];
      const corrections = phaseTasks.filter(isSubphaseTask);
      const latestStatus = normalize(latest.status);
      const failure = data.failures.get(String(latest.id)) || {
        task_id: latest.id,
        task_status: latestStatus,
        failure_reason: latestStatus === 'blocked' ? 'A execução ficou bloqueada e precisa de uma correção antes de continuar.' : 'A execução falhou e precisa de uma correção antes de continuar.',
        failure_category: 'unknown',
        failure_code: latestStatus === 'blocked' ? 'EXECUTION_BLOCKED' : 'EXECUTION_FAILED',
        requires_authorization: false,
        log_url: null
      };
      if (allowCreate && FAILURE_STATUSES.has(latestStatus) && corrections.length < MAX_SUBPHASES) {
        const made = await createCorrection({projectId:data.projectId,missionId:data.missionId,phaseId,number:corrections.length + 1,goal:promptValue(latest, 'OBJETIVO'),failedTask:latest,failure});
        created = created || made;
      }
      renderPhaseSubphases(phaseId, phaseTasks, data.failures);
      if (corrections.length >= MAX_SUBPHASES && FAILURE_STATUSES.has(latestStatus)) {
        const card = document.querySelectorAll('#build-game-view .build-game-phase')[phaseId - 1];
        const container = card?.querySelector('.build-game-subphases');
        if (container && !container.querySelector('.build-game-subphase-wait')) container.insertAdjacentHTML('beforeend', `<div class="build-game-subphase-wait">Limite de ${MAX_SUBPHASES} subfases automáticas atingido nesta fase. Revise o erro antes de continuar.</div>`);
      }
    }
    return created;
  };

  const scheduleSync = ({allowCreate = true} = {}) => {
    if (syncInFlight) return syncInFlight;
    syncInFlight = Promise.resolve()
      .then(() => syncSubphases({allowCreate}))
      .catch(error => console.error('DevPilot build-game subphases:', error))
      .finally(() => { syncInFlight = null; });
    return syncInFlight;
  };

  const install = () => {
    if (typeof api !== 'function') return window.setTimeout(install, 50);
    installStyle();
    document.addEventListener('devpilot:game:state', () => { void scheduleSync({allowCreate: true}); });
    document.addEventListener('devpilot:build-game-new-session', () => { void scheduleSync({allowCreate: true}); });
    if (document.querySelector('#build-game-view.active')) void scheduleSync({allowCreate: true});
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once: true});
  else install();
})();
