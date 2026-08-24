/* DevPilot Build Game cockpit: spaceship interior HUD + DevPilotVoz bridge. */
(() => {
  'use strict';

  const STYLE_ID = 'build-game-cockpit-style';
  const STYLE_URL = '/assets/build-game-cockpit.css?v=20260824-1';
  const GAME_PROJECT_KEY = 'devpilot-build-game-project';
  const VOICE_PROJECT_KEY = 'devpilot-chat-active-project-id';
  const VOICE_DIAGNOSTIC_URL = '/api/super-admin/voice';
  let voiceTestSequence = 0;

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[char]);

  const toastMessage = message => {
    if (typeof toast === 'function') toast(message);
  };

  const token = () => localStorage.getItem('devpilot-token') || '';
  const gameProjectId = () => String(localStorage.getItem(GAME_PROJECT_KEY) || '').trim();

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

    const existing = shell.querySelector('[data-build-game-cockpit]');
    if (existing) return;

    const host = document.createElement('div');
    host.innerHTML = cockpitMarkup(gameSnapshot(view)).trim();
    const cockpit = host.firstElementChild;
    if (!cockpit) return;
    shell.prepend(cockpit);

    cockpit.querySelector('[data-cockpit-test-voice]')?.addEventListener('click', () => testVoiceLink(view, true));
    cockpit.querySelector('[data-cockpit-open-voice]')?.addEventListener('click', () => openVoice(view));
    testVoiceLink(view, false);
  }

  function sync() {
    const view = document.querySelector('#build-game-view');
    if (!view) return;
    enhance(view);
  }

  function boot() {
    ensureStyle();
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
