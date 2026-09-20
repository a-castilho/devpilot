(() => {
  'use strict';

  if (window.__devpilotChatRequestWatchdogReady) return;
  window.__devpilotChatRequestWatchdogReady = true;

  const nativeFetch = window.fetch.bind(window);
  const CHAT_REQUEST_TIMEOUT_MS = 45000;

  const requestPath = input => {
    try {
      const raw = typeof input === 'string' || input instanceof URL ? input : input?.url;
      return new URL(raw, window.location.href).pathname;
    } catch (_) {
      return '';
    }
  };

  window.fetch = function devpilotBoundedFetch(input, init = {}) {
    if (requestPath(input) !== '/api/chat') return nativeFetch(input, init);

    const controller = new AbortController();
    const upstreamSignal = init?.signal;
    let timedOut = false;
    let detachUpstream = null;

    if (upstreamSignal) {
      const relayAbort = () => {
        try { controller.abort(upstreamSignal.reason); }
        catch (_) { controller.abort(); }
      };
      if (upstreamSignal.aborted) relayAbort();
      else {
        upstreamSignal.addEventListener('abort', relayAbort, {once: true});
        detachUpstream = () => upstreamSignal.removeEventListener('abort', relayAbort);
      }
    }

    const timeoutId = window.setTimeout(() => {
      timedOut = true;
      try { controller.abort(new DOMException('Chat timeout', 'TimeoutError')); }
      catch (_) { controller.abort(); }
    }, CHAT_REQUEST_TIMEOUT_MS);

    return nativeFetch(input, {...init, signal: controller.signal})
      .catch(error => {
        if (!timedOut) throw error;
        const timeoutError = new Error(
          'O chat demorou mais de 45 segundos. A tentativa foi interrompida para não deixar a tela travada.'
        );
        timeoutError.name = 'TimeoutError';
        throw timeoutError;
      })
      .finally(() => {
        window.clearTimeout(timeoutId);
        detachUpstream?.();
      });
  };

  /*
   * O bundle de voz ainda carrega módulos legados antes do layout canônico.
   * Esta camada é carregada por último e mantém somente uma superfície visual
   * de conversa, sem alterar os handlers de captura/voz estabilizados.
   */
  const installSingleChatLayout = () => {
    const modal = document.querySelector('#voice-modal');
    const panel = modal?.querySelector('.voice-modal-enhanced');
    if (!modal || !panel) return false;

    const canonicalConversation = panel.querySelector('#voice-visible-conversation');
    const composer = panel.querySelector('.voice-chatgpt-composer');
    const stage = panel.querySelector('.voice-chatgpt-stage');
    if (!canonicalConversation || !composer || !stage) return false;

    panel.dataset.singleChatLayout = '1';

    const removeLegacySurfaces = () => {
      panel.querySelectorAll(
        '#voice-chat-log, #voice-chat-preview, .voice-conversation-controls, .voice-playback-controls'
      ).forEach(node => {
        if (node === canonicalConversation || node.contains(canonicalConversation)) return;
        node.remove();
      });

      /* Evita uma segunda conversa criada por carregamento repetido do layout. */
      const conversations = [...panel.querySelectorAll('#voice-visible-conversation')];
      conversations.slice(1).forEach(node => node.remove());

      const modeSwitches = [...panel.querySelectorAll('.voice-chat-mode-switch')];
      modeSwitches.slice(1).forEach(node => node.remove());

      const profileBanners = [...panel.querySelectorAll('.voice-chat-profile-banner')];
      profileBanners.slice(1).forEach(node => node.remove());
    };

    removeLegacySurfaces();

    if (!document.querySelector('style[data-devpilot-single-chat-layout="1"]')) {
      const style = document.createElement('style');
      style.dataset.devpilotSingleChatLayout = '1';
      style.textContent = `
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"]{
          width:min(900px,calc(100vw - 28px));
          max-width:900px;
          max-height:min(92dvh,860px);
          padding:14px 14px 12px;
          border:1px solid rgba(255,255,255,.10);
          border-radius:24px;
          background:linear-gradient(180deg,rgba(17,23,29,.985),rgba(12,18,23,.99));
          box-shadow:0 28px 90px rgba(0,0,0,.52);
          overflow:hidden;
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-chatgpt-stage{
          width:100%;
          max-width:none;
          min-height:0;
          margin:0;
          padding:0 2px;
          display:flex;
          flex-direction:column;
          gap:8px;
          overflow:hidden;
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-visual.voice-chatgpt-orb{
          width:58px;
          height:58px;
          margin:0 auto -2px;
          flex:0 0 auto;
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-chatgpt-orb .pulse-orb{
          width:46px;
          height:46px;
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-chat-mode-switch,
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-chat-profile-banner,
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] #voice-visible-conversation{
          width:min(100%,820px);
          margin-inline:auto;
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-chat-mode-switch{
          flex:0 0 auto;
          margin-top:0;
          background:rgba(7,13,18,.50);
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-chat-profile-banner{
          flex:0 0 auto;
          background:transparent;
          border:0;
          padding:4px 4px 2px;
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] #voice-visible-conversation{
          flex:1 1 auto;
          min-height:190px;
          max-height:min(52dvh,520px);
          padding:12px 8px 18px;
          border-top:1px solid rgba(255,255,255,.06);
          border-bottom:1px solid rgba(255,255,255,.06);
          background:rgba(3,8,12,.16);
          scroll-padding-block:16px;
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-visible-turn{
          max-width:min(88%,720px);
          border-radius:17px;
          box-shadow:none;
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-visible-turn[data-role="user"]{
          background:rgba(76,88,98,.42);
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-visible-turn[data-role="assistant"]{
          width:auto;
          background:transparent;
          border-color:transparent;
          padding-left:8px;
          padding-right:8px;
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-chatgpt-status{
          flex:0 0 auto;
          margin:2px auto 0;
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-composer.voice-chatgpt-composer{
          width:min(100%,820px);
          margin:10px auto 0;
          flex:0 0 auto;
          border-radius:22px;
          background:rgba(27,35,43,.99);
          box-shadow:0 12px 34px rgba(0,0,0,.32),inset 0 1px 0 rgba(255,255,255,.035);
        }
        #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-chatgpt-options{
          bottom:82px;
        }
        @media(max-width:640px){
          #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"]{
            width:calc(100vw - 8px);
            max-height:calc(100dvh - 10px);
            padding:10px 8px 8px;
            border-radius:18px;
          }
          #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-visual.voice-chatgpt-orb{
            width:44px;
            height:44px;
          }
          #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-chatgpt-orb .pulse-orb{
            width:36px;
            height:36px;
          }
          #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] #voice-visible-conversation{
            min-height:150px;
            max-height:50dvh;
            padding:9px 2px 14px;
          }
          #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-visible-turn{
            max-width:94%;
          }
          #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-visible-turn[data-role="assistant"]{
            width:94%;
          }
          #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-chat-profile-banner{
            padding-inline:2px;
          }
          #voice-modal .voice-modal-enhanced[data-single-chat-layout="1"] .voice-composer.voice-chatgpt-composer{
            margin-top:7px;
          }
        }
      `;
      document.head.appendChild(style);
    }

    if (!panel.__devpilotSingleChatObserver) {
      const observer = new MutationObserver(() => removeLegacySurfaces());
      observer.observe(panel, {childList:true, subtree:true});
      panel.__devpilotSingleChatObserver = observer;
    }

    return true;
  };

  const ensureSingleChatLayout = () => {
    if (installSingleChatLayout()) return;
    let attempts = 0;
    const retry = window.setInterval(() => {
      attempts += 1;
      if (installSingleChatLayout() || attempts >= 20) window.clearInterval(retry);
    }, 120);
  };

  ensureSingleChatLayout();
  document.addEventListener('devpilot:chat-opened', ensureSingleChatLayout);
})();
