(() => {
  'use strict';
  if (window.__devpilotCanonicalChatBootstrap) return;
  window.__devpilotCanonicalChatBootstrap = true;

  let loading = false;
  const load = () => {
    if (loading || window.__devpilotCanonicalChatLoaded) return;
    const panel = document.querySelector('#voice-modal .voice-modal-enhanced');
    const conversation = panel?.querySelector('#voice-visible-conversation');
    if (!panel || !conversation) return;
    loading = true;
    const script = document.createElement('script');
    script.src = '/assets/chat-canonical-runtime.js?v=20260911-chat-reform-1';
    script.async = false;
    script.dataset.devpilotCanonicalChat = '1';
    script.onload = () => { window.__devpilotCanonicalChatLoaded = true; loading = false; };
    script.onerror = () => { loading = false; console.error('[DevPilot] Falha ao carregar o runtime canônico do chat'); };
    document.body.appendChild(script);
  };

  document.addEventListener('devpilot:feature-ready', event => {
    if (event?.detail?.feature === 'voice') window.requestAnimationFrame(load);
  });
  document.addEventListener('devpilot:chat-opened', () => window.requestAnimationFrame(load));
  window.addEventListener('pageshow', () => window.requestAnimationFrame(load));
  window.requestAnimationFrame(load);
})();
