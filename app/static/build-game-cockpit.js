/* DevPilot Build Game cockpit: spaceship interior HUD + DevPilotVoz bridge. */
(() => {
  'use strict';

  const STYLE_ID = 'build-game-cockpit-style';
  const STYLE_URL = '/assets/build-game-cockpit.css?v=20260824-1';
  const GAME_PROJECT_KEY = 'devpilot-build-game-project';
  const GAME_MISSION_KEY = 'devpilot-build-game-mission';
  const VOICE_PROJECT_KEY = 'devpilot-chat-active-project-id';
  const VOICE_DIAGNOSTIC_URL = '/api/super-admin/voice';
  const LINUX_INFRA_MARKER = '[DEVPILOT_GAME_LINUX_INFRA_V1]';
  const LINUX_INFRA_COST = 50;
  const ACTIVE_TASK_STATUSES = new Set(['awaiting_approval', 'queued', 'running', 'review', 'blocked']);
  const REFUND_TASK_STATUSES = new Set(['failed', 'cancelled']);
  let voiceTestSequence = 0;
  let linuxRefreshSequence = 0;
  const linuxRefreshInFlight = new Map();

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[char]);

  const toastMessage = message => {
    if (typeof toast === 'function') toast(message);
  };

  const token = () => localStorage.getItem('devpilot-token') || '';
  const gameProjectId = () => String(localStorage.getItem(GAME_PROJECT_KEY) || '').trim();
  const gameMissionId = () => String(localStorage.getItem(GAME_MISSION_KEY) || '').trim();
  const normalizeStatus = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const link = document.createElement('link');
    link.id = STYLE_ID;
    link.rel = 'stylesheet';
    link.href = STYLE_URL;
    document.head.appendChild(link);
  }

  function gameSnapshot(view) {
    const project = view.querySelector('.build-game-score > div:nth-child(3) strong')?.textContent?.trim() || 'Projeto';
    const progress = view.querySelector('.build-game-score > div:nth-child(1) strong')?.textContent?.trim() || '0/6 fases';
    const xp = view.querySelector('.build-game-score > div:nth-child(2) strong')?.textContent?.trim() || '0 XP';
    const current = view.querySelector('.build-game-phase.current .build-game-phase-copy strong')?.textContent?.trim()
      || (view.querySelector('.build-game-victory') ? 'Missão concluída' : 'Aguardando rota');
    return {project, progress, xp, current};
  }

  function currentProject(view) {
    const projectId = String(view.querySelector('#build-game-project')?.value || gameProjectId()).trim();
    const projects = typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : [];
    return projects.find(project => String(project?.id) === projectId) || null;
  }

  function automaticGoal(view) {
    const project = currentProject(view);
    const description = String(project?.description || '').trim();
    if (description) return description;

    const selectedName = view.querySelector('#build-game-project')?.selectedOptions?.[0]?.textContent?.trim();
    const scoreName = view.querySelector('.build-game-score > div:nth-child(3) strong')?.textContent?.trim();
    const projectName = String(project?.name || selectedName || scoreName || 'selecionado').trim();
    return `Evoluir o projeto ${projectName} com uma entrega funcional, testada e verificável.`;
  }

  function ensurePlayableGoal(button) {
    const view = button?.closest?.('#build-game-view') || document.querySelector('#build-game-view');
    const input = view?.querySelector('#build-game-goal');
    if (!view || !input || String(input.value || '').trim()) return false;

    input.value = automaticGoal(view);
    input.dispatchEvent(new Event('input', {bubbles: true}));
    input.dispatchEvent(new Event('change', {bubbles: true}));
    toastMessage('Objetivo definido automaticamente. Iniciando a fase…');
    return true;
  }

  function installGoalGuard() {
    if (document.documentElement.dataset.buildGameGoalGuard === '1') return;
    document.documentElement.dataset.buildGameGoalGuard = '1';
    document.addEventListener('click', event => {
      const button = event.target?.closest?.('#build-game-view [data-play-phase]');
      if (button) ensurePlayableGoal(button);
    }, true);
  }

  function setVoiceProjectContext() {
    const projectId = gameProjectId();
    if (!projectId) return false;

    const bridge = window.devpilotChatProjectContext;
    if (bridge && typeof bridge.setProjectId === 'function') {
      const applied = bridge.setProjectId(projectId);
      if (applied) return true;
    }

    localStorage.setItem(VOICE_PROJECT_KEY, projectId);
    window.dispatchEvent(new CustomEvent('devpilot:active-project-changed', {
      detail: {project_id: projectId},
    }));
    return true;
  }

  function updateVoiceState(view, state, message) {
    const comms = view.querySelector('[data-cockpit-comms]');
    const label = view.querySelector('[data-cockpit-voice-status]');
    if (!comms || !label) return;
    comms.dataset.state = state;
    label.textContent = message;
  }

  async function testVoiceLink(view, announce = true) {
    const sequence = ++voiceTestSequence;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 4500);
    updateVoiceState(view, 'checking', 'Testando DevPilotVoz…');
    setVoiceProjectContext();

    try {
      const response = await fetch(VOICE_DIAGNOSTIC_URL, {
        method: 'GET',
        headers: token() ? {Authorization: `Bearer ${token()}`} : {},
        cache: 'no-store',
        signal: controller.signal,
      });
      const data = await response.json().catch(() => ({}));
      if (sequence !== voiceTestSequence || !view.isConnected) return false;
      if (response.ok) {
        const chain = Array.isArray(data.chain) ? data.chain : [];
        const configured = chain.filter(item => item && item.configured).length;
        const last = data.last_transcription && typeof data.last_transcription === 'object'
          ? `${data.last_transcription.provider || 'voz'} · ${data.last_transcription.model || 'modelo'}`
          : '';
        const message = last
          ? `Online · última: ${last}`
          : `Online · ${configured} rota(s) configurada(s)`;
        updateVoiceState(view, 'online', message);
        document.dispatchEvent(new CustomEvent('devpilot:build-game-voice-link', {
          detail: {ok: true, project_id: gameProjectId(), configured_routes: configured},
        }));
        if (announce) toastMessage('DevPilotVoz conectado ao projeto da partida');
        return true;
      }

      if (response.status === 403) {
        const voiceClientReady = Boolean(document.querySelector('#voice-modal') && document.querySelector('#voice-dock'));
        const message = voiceClientReady
          ? 'Interface pronta · ligação não verificada (diagnóstico exclusivo do Super Admin)'
          : 'Interface DevPilotVoz não encontrada';
        updateVoiceState(view, 'warn', message);
        document.dispatchEvent(new CustomEvent('devpilot:build-game-voice-link', {
          detail: {
            ok: null,
            project_id: gameProjectId(),
            diagnostic_restricted: true,
            voice_client_ready: voiceClientReady,
          },
        }));
        if (announce) {
          toastMessage(voiceClientReady
            ? 'Interface DevPilotVoz pronta; diagnóstico de ligação não autorizado para este perfil'
            : 'Interface DevPilotVoz indisponível');
        }
        return false;
      }

      const detail = typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`;
      throw new Error(detail);
    } catch (error) {
      if (sequence !== voiceTestSequence || !view.isConnected) return false;
      const reason = error?.name === 'AbortError' ? 'tempo limite excedido' : (error?.message || 'falha de comunicação');
      updateVoiceState(view, 'warn', `Sem ligação · ${reason}`);
      document.dispatchEvent(new CustomEvent('devpilot:build-game-voice-link', {
        detail: {ok: false, project_id: gameProjectId(), reason},
      }));
      if (announce) toastMessage(`Falha ao testar DevPilotVoz: ${reason}`);
      return false;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function openVoice(view) {
    const projectLinked = setVoiceProjectContext();
    const dock = document.querySelector('#voice-dock');
    const modal = document.querySelector('#voice-modal');
    if (!dock || !modal) {
      updateVoiceState(view, 'warn', 'Interface DevPilotVoz não encontrada');
      toastMessage('DevPilotVoz não está disponível nesta tela');
      return;
    }

    dock.click();
    window.setTimeout(() => setVoiceProjectContext(), 0);
    updateVoiceState(
      view,
      'checking',
      projectLinked ? 'Canal aberto · projeto sincronizado · aguardando comando' : 'Canal aberto · aguardando comando',
    );
  }

  async function gameApi(path, options = {}) {
    if (typeof api === 'function') return api(path, options);
    const response = await fetch(`/api${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token() ? {Authorization: `Bearer ${token()}`} : {}),
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
    return data;
  }

  function linuxEarned(view) {
    const xpText = view.querySelector('.build-game-score > div:nth-child(2) strong')?.textContent || '0';
    const xp = Number(String(xpText).match(/\d+/)?.[0] || 0);
    return Math.floor(xp / 10);
  }

  function isLinuxInfraTask(task) {
    const prompt = String(task?.prompt || '');
    const mission = gameMissionId();
    return prompt.includes(LINUX_INFRA_MARKER) && (!mission || prompt.includes(`PARTIDA: ${mission}`));
  }

  function linuxEconomy(view, tasks) {
    const earned = linuxEarned(view);
    const requests = (Array.isArray(tasks) ? tasks : []).filter(isLinuxInfraTask)
      .sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
    const latest = requests[0] || null;
    const latestStatus = normalizeStatus(latest?.status);
    const reserved = latest && !REFUND_TASK_STATUSES.has(latestStatus);
    const balance = Math.max(0, earned - (reserved ? LINUX_INFRA_COST : 0));
    const active = Boolean(latest && ACTIVE_TASK_STATUSES.has(latestStatus));
    const ready = latestStatus === 'completed';
    return {earned, balance, latest, latestStatus, active, ready};
  }

  function linuxWalletMarkup(economy) {
    let stateLabel = `Custa ${LINUX_INFRA_COST} Linux`;
    let buttonLabel = `Ativar infra dedicada · ${LINUX_INFRA_COST} Linux`;
    let disabled = economy.balance < LINUX_INFRA_COST;
    if (economy.active) {
      stateLabel = 'Provisionamento em andamento';
      buttonLabel = 'Infra Linux sendo preparada';
      disabled = true;
    } else if (economy.ready) {
      stateLabel = 'Infra dedicada ativa';
      buttonLabel = 'Infra Linux ativa';
      disabled = true;
    } else if (economy.latest && REFUND_TASK_STATUSES.has(economy.latestStatus)) {
      stateLabel = 'Tentativa anterior falhou · Linux devolvido';
    }

    return `<article class="panel build-game-linux-wallet" data-linux-wallet style="border-color:rgba(104,240,187,.28);background:linear-gradient(145deg,rgba(6,28,25,.9),rgba(3,11,18,.96))">
      <div class="panel-title" style="gap:12px;align-items:center">
        <div><span class="eyebrow">MOEDA DE INFRAESTRUTURA</span><h3 style="margin:.2rem 0">🐧 Linux · ${economy.balance}</h3></div>
        <strong style="font-size:.82rem">${esc(stateLabel)}</strong>
      </div>
      <p style="margin:.35rem 0 .8rem;color:var(--muted,#9eacc2)">Cada 10 XP concluídos valem 1 Linux. Use Linux para obter uma sandbox dedicada da partida, isolada do host e vinculada somente ao seu projeto.</p>
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <button class="primary" type="button" data-linux-infra-buy ${disabled ? 'disabled' : ''}>${esc(buttonLabel)}</button>
        <small style="color:var(--muted,#9eacc2)">Ganho: ${economy.earned} · Saldo: ${economy.balance} · Sem acesso privilegiado ao host</small>
      </div>
    </article>`;
  }

  async function fetchProjectTasks(projectId) {
    if (!projectId) return [];
    const tasks = await gameApi(`/tasks?project_id=${encodeURIComponent(projectId)}&limit=500`);
    return Array.isArray(tasks) ? tasks : [];
  }

  async function activateLinuxInfra(view, button) {
    const projectId = String(view.querySelector('#build-game-project')?.value || gameProjectId()).trim();
    const mission = gameMissionId();
    if (!projectId || !mission) return toastMessage('Inicie uma partida antes de ativar a Infra Linux');

    button.disabled = true;
    const original = button.textContent;
    button.textContent = 'Validando saldo…';
    try {
      const tasks = await fetchProjectTasks(projectId);
      const economy = linuxEconomy(view, tasks);
      if (economy.active || economy.ready) return toastMessage('Esta partida já possui uma Infra Linux dedicada');
      if (economy.balance < LINUX_INFRA_COST) return toastMessage(`Saldo insuficiente: são necessários ${LINUX_INFRA_COST} Linux`);

      const project = currentProject(view);
      const prompt = `${LINUX_INFRA_MARKER}\n[DEVPILOT_MODE=develop]\nPARTIDA: ${mission}\nPROJETO: ${projectId}\nCUSTO_LINUX: ${LINUX_INFRA_COST}\n\nOBJETIVO:\nProvisionar uma infraestrutura Linux dedicada para esta partida e vinculada exclusivamente ao jogador/projeto selecionado.\n\nREQUISITOS OBRIGATÓRIOS:\n- Use somente provedores, contas e credenciais cloud já autorizados e gerenciados pelo DevPilot; nunca exponha tokens no frontend, logs ou resultado.\n- Crie sandbox/container/VM isolada por tenant e projeto, sem --privileged, sem montar docker.sock e sem acesso administrativo ao host do DevPilot.\n- A identidade do jogador deve ser propagada pelo backend; não confie em user_id fornecido pelo navegador.\n- Aplique limites de CPU, memória, disco, processos e tempo de vida. Prefira rootless/unprivileged e imagem Linux mínima mantida.\n- O terminal da sandbox deve ser acessível apenas após autenticação do DevPilot e autorização do proprietário; SUPER_ADMIN pode auditar/administrar, mas outros usuários não podem acessar.\n- Restrinja rede e portas ao necessário para jogar/testar o projeto. Não exponha SSH ou serviços diretamente à Internet sem camada autenticada.\n- Registre auditoria de criação, início, parada, acesso e destruição da sandbox, sem registrar segredos.\n- O provisionamento deve ser idempotente para a chave partida+projeto; não crie infraestrutura duplicada ao repetir a tarefa.\n- Não crie recurso pago fora dos limites/quota já configurados. Se não houver capacidade segura/autorizada, finalize como bloqueado/falha com motivo explícito.\n- Ao concluir, devolva no resultado o identificador da sandbox, status, limites aplicados e URL/rota autenticada de acesso quando existir.\n\nCRITÉRIO DE VITÓRIA:\nA Infra Linux está pronta somente quando o ambiente isolado foi realmente provisionado, o acesso do jogador foi validado e não existe caminho de privilégio para o host.`;

      await gameApi('/tasks', {
        method: 'POST',
        body: JSON.stringify({
          project_id: projectId,
          title: `[Jogo] Infra Linux dedicada · ${project?.name || projectId}`,
          prompt,
          source: 'dashboard',
          priority: 90,
          requires_approval: false,
        }),
      });
      toastMessage(`${LINUX_INFRA_COST} Linux reservados · provisionamento iniciado`);
      document.dispatchEvent(new CustomEvent('devpilot:build-game-linux-infra', {
        detail: {project_id: projectId, mission_id: mission, cost: LINUX_INFRA_COST},
      }));
      await refreshLinuxEconomy(view);
    } catch (error) {
      toastMessage(error?.message || 'Falha ao ativar Infra Linux');
    } finally {
      if (button.isConnected) {
        button.disabled = false;
        button.textContent = original;
      }
    }
  }

  async function refreshLinuxEconomy(view) {
    const shell = view.querySelector('.build-game-shell');
    if (!shell) return;
    const projectId = String(view.querySelector('#build-game-project')?.value || gameProjectId()).trim();
    if (!projectId) return;

    const requestKey = `${projectId}:${gameMissionId()}:${linuxEarned(view)}`;
    const pending = linuxRefreshInFlight.get(requestKey);
    if (pending) return pending;

    const sequence = ++linuxRefreshSequence;
    const request = (async () => {
      try {
        const tasks = await fetchProjectTasks(projectId);
        if (sequence !== linuxRefreshSequence || !view.isConnected) return;
        const economy = linuxEconomy(view, tasks);
        const fingerprint = [
          projectId,
          gameMissionId(),
          economy.earned,
          economy.balance,
          economy.latest?.id || '',
          economy.latestStatus,
        ].join(':');
        const existingWallet = shell.querySelector('[data-linux-wallet]');
        if (existingWallet?.dataset.linuxWalletFingerprint === fingerprint) return;

        const host = document.createElement('div');
        host.innerHTML = linuxWalletMarkup(economy).trim();
        const wallet = host.firstElementChild;
        if (!wallet) return;
        wallet.dataset.linuxWalletFingerprint = fingerprint;
        existingWallet?.remove();
        const cockpit = shell.querySelector('[data-build-game-cockpit]');
        if (cockpit) cockpit.insertAdjacentElement('afterend', wallet);
        else shell.prepend(wallet);
        wallet.querySelector('[data-linux-infra-buy]')?.addEventListener('click', event => activateLinuxInfra(view, event.currentTarget));
      } catch (error) {
        if (sequence === linuxRefreshSequence) toastMessage(`Moeda Linux indisponível: ${error?.message || 'falha ao carregar'}`);
      }
    })();

    linuxRefreshInFlight.set(requestKey, request);
    try {
      return await request;
    } finally {
      if (linuxRefreshInFlight.get(requestKey) === request) linuxRefreshInFlight.delete(requestKey);
    }
  }

  function cockpitMarkup(snapshot) {
    return `
      <section class="build-game-cockpit" data-build-game-cockpit aria-label="Skin visão de dentro da nave">
        <div class="build-game-cockpit-window" aria-hidden="true">
          <div class="build-game-cockpit-crosshair"></div>
          <div class="build-game-cockpit-hud">
            <div>
              <span class="cockpit-kicker">DEV-01 · VISÃO DA CABINE</span>
              <strong>${esc(snapshot.project)}</strong>
              <small>ROTA ATUAL · ${esc(snapshot.current)}</small>
            </div>
            <div class="cockpit-hud-progress"><b>${esc(snapshot.progress)}</b><span>${esc(snapshot.xp)}</span></div>
          </div>
        </div>
        <div class="build-game-cockpit-console">
          <div class="cockpit-gauge"><span>NAVE</span><strong>DEV PILOT / ONLINE</strong><small>controle de missão ativo</small></div>
          <div class="cockpit-gauge"><span>NAVEGAÇÃO</span><strong>${esc(snapshot.progress)}</strong><small>${esc(snapshot.current)}</small></div>
          <div class="cockpit-gauge"><span>ENERGIA</span><strong>${esc(snapshot.xp)}</strong><small>experiência acumulada</small></div>
          <div class="cockpit-comms" data-cockpit-comms data-state="checking">
            <div>
              <span class="cockpit-comms-label">COMMS · DEVPILOTVOZ</span>
              <div class="cockpit-comms-state"><i class="cockpit-comms-light"></i><span data-cockpit-voice-status aria-live="polite">Verificando ligação…</span></div>
            </div>
            <div class="cockpit-comms-actions">
              <button class="ghost" type="button" data-cockpit-test-voice>Testar ligação</button>
              <button class="primary" type="button" data-cockpit-open-voice>Falar com DevPilotVoz</button>
            </div>
          </div>
        </div>
      </section>`;
  }

  function enhance(view) {
    const shell = view.querySelector('.build-game-shell');
    if (!shell) return;
    view.classList.add('build-game-cockpit-view');

    const goalInput = view.querySelector('#build-game-goal');
    if (goalInput) {
      goalInput.placeholder = 'Opcional — se vazio, o DevPilot define automaticamente.';
      goalInput.setAttribute('aria-label', 'Objetivo da partida; opcional, será definido automaticamente se vazio');
    }

    const existing = shell.querySelector('[data-build-game-cockpit]');
    if (existing) {
      if (!shell.querySelector('[data-linux-wallet]')) void refreshLinuxEconomy(view);
      return;
    }

    const host = document.createElement('div');
    host.innerHTML = cockpitMarkup(gameSnapshot(view)).trim();
    const cockpit = host.firstElementChild;
    if (!cockpit) return;
    shell.prepend(cockpit);

    cockpit.querySelector('[data-cockpit-test-voice]')?.addEventListener('click', () => testVoiceLink(view, true));
    cockpit.querySelector('[data-cockpit-open-voice]')?.addEventListener('click', () => openVoice(view));
    testVoiceLink(view, false);
    void refreshLinuxEconomy(view);
  }

  function sync() {
    const view = document.querySelector('#build-game-view');
    if (!view) return;
    enhance(view);
  }

  function boot() {
    ensureStyle();
    installGoalGuard();
    sync();
    const main = document.querySelector('main') || document.body;
    if (!main || main.dataset.buildGameCockpitObserved === '1') return;
    main.dataset.buildGameCockpitObserved = '1';
    let queued = false;
    new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        sync();
      });
    }).observe(main, {childList: true, subtree: true});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();