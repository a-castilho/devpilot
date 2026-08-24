(() => {
  const startButton = document.querySelector('#voice-start');
  const statusNode = document.querySelector('#voice-status');
  const modal = document.querySelector('#voice-modal');
  const transcript = document.querySelector('#voice-transcript');
  const sendButton = document.querySelector('#voice-chat-send');
  const voicePanel = modal?.querySelector('.voice-modal');

  if (!startButton || !statusNode || !modal || startButton.dataset.insecureLanGuard === '5') return;

  const originalStart = startButton.onclick;
  if (typeof originalStart !== 'function') return;

  startButton.dataset.insecureLanGuard = '5';

  const isLoopback = () => ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
  const isInsecureLan = () => !window.isSecureContext && !isLoopback();

  const isLikelyMobileDevice = () => {
    if (navigator.userAgentData?.mobile === true) return true;

    const userAgent = String(navigator.userAgent || '');
    if (/Android|iPhone|iPad|iPod|IEMobile|Opera Mini|Mobile/i.test(userAgent)) return true;

    return /Macintosh/i.test(userAgent) && Number(navigator.maxTouchPoints || 0) > 1;
  };

  const hasNativeSpeechRecognition = () => Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);

  const ensureMobileLayoutFix = () => {
    if (!isLikelyMobileDevice()) return;
    if (!document.querySelector('link[data-voice-mobile-fix]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = '/assets/voice-mobile-fix.css?v=20260823-1';
      link.dataset.voiceMobileFix = '1';
      document.head.appendChild(link);
    }

    if (!document.querySelector('link[data-voice-conversation-mode]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = '/assets/voice-conversation-mode.css?v=20260823-1';
      link.dataset.voiceConversationMode = '1';
      document.head.appendChild(link);
    }
  };

  const conversationModeCard = () => modal.querySelector('#voice-conversation-mode');

  const setConversationModeState = (state, text) => {
    const card = conversationModeCard();
    if (!card) return;
    card.dataset.state = state;
    const body = card.querySelector('[data-voice-conversation-text]');
    if (body && text) body.textContent = text;
  };

  const resetConversationMode = () => {
    const card = conversationModeCard();
    if (!card) return;
    setConversationModeState(
      'ready',
      'Toque no microfone para conversar com o DevPilot ou digite uma mensagem.',
    );
    card.hidden = true;
  };

  const isVoiceSessionActive = () => Boolean(
    startButton.getAttribute('aria-pressed') === 'true'
      || voicePanel?.classList.contains('voice-session-active'),
  );

  const isBlockedStatus = (value) => /bloquead|não permite|https|não foi possível abrir o microfone/.test(value);

  const syncConversationModeState = () => {
    if (!isInsecureLan() || !isLikelyMobileDevice()) return;
    const card = conversationModeCard();
    if (!card) return;

    const value = String(statusNode.textContent || '').toLowerCase();
    const active = isVoiceSessionActive();

    if (!active) {
      if (isBlockedStatus(value)) {
        card.hidden = false;
        setConversationModeState(
          'blocked',
          'O Android bloqueou o microfone neste endereço HTTP. Para voz contínua, abra o DevPilot por HTTPS.',
        );
        return;
      }
      resetConversationMode();
      return;
    }

    card.hidden = false;

    if (/ouvindo|microfone ativo|abrindo o microfone/.test(value)) {
      setConversationModeState('active', 'Microfone ativo. Pode falar com o DevPilot.');
      return;
    }

    if (/ligando|solicitando|ativando captura|reconhecimento nativo indisponível/.test(value)) {
      setConversationModeState('starting', 'Ligando o microfone. Aguarde até aparecer “Ouvindo…”.');
      return;
    }

    if (isBlockedStatus(value)) {
      setConversationModeState(
        'blocked',
        'O Android bloqueou o microfone neste endereço HTTP. Para voz contínua, abra o DevPilot por HTTPS.',
      );
    }
  };

  const focusTextComposer = () => {
    if (typeof window.devpilotVoiceStop === 'function' && isVoiceSessionActive()) {
      window.devpilotVoiceStop('Modo texto ativo. Digite sua mensagem para o DevPilot.');
    } else {
      statusNode.textContent = 'Modo texto ativo. Digite sua mensagem para o DevPilot.';
    }
    resetConversationMode();
    transcript?.focus?.();
  };

  const showConversationMode = () => {
    ensureMobileLayoutFix();
    const card = ensureConversationModeCard();
    if (!card) return;
    card.hidden = false;
    setConversationModeState(
      'ready',
      'Toque em Conversar agora. O DevPilot vai tentar usar o reconhecimento de voz do próprio navegador, sem abrir câmera ou seletor de arquivos.',
    );
  };

  const canUseEnhancedConversation = () => Boolean(
    modal.querySelector('.voice-modal-enhanced') && sendButton && transcript,
  );

  const startConversationMode = (event) => {
    event?.preventDefault?.();
    event?.stopPropagation?.();
    showConversationMode();

    if (!canUseEnhancedConversation()) {
      const message = 'A interface de conversa ainda não terminou de carregar. Reabra esta tela e tente novamente.';
      statusNode.textContent = message;
      setConversationModeState('blocked', message);
      return;
    }

    if (isInsecureLan() && !hasNativeSpeechRecognition()) {
      const message = 'Este navegador bloqueia voz contínua neste endereço HTTP. Para conversar pelo microfone, abra o DevPilot por HTTPS.';
      statusNode.textContent = message;
      setConversationModeState('blocked', message);
      if (typeof toast === 'function') toast(message);
      return;
    }

    statusNode.textContent = 'Modo conversar: ligando o microfone…';
    setConversationModeState('starting', 'Ligando o microfone. Fale normalmente quando aparecer “Ouvindo…”.');

    try {
      const result = originalStart.call(startButton, event);
      syncConversationModeState();
      if (result?.catch) {
        result.catch((error) => {
          const message = error?.message || 'Não foi possível iniciar o modo conversar.';
          statusNode.textContent = message;
          setConversationModeState('blocked', message);
          syncConversationModeState();
          if (typeof toast === 'function') toast(message);
        });
      }
    } catch (error) {
      const message = error?.message || 'Não foi possível iniciar o modo conversar.';
      statusNode.textContent = message;
      setConversationModeState('blocked', message);
      syncConversationModeState();
      if (typeof toast === 'function') toast(message);
    }
  };

  function ensureConversationModeCard() {
    let card = conversationModeCard();
    if (card || !voicePanel) return card;

    card = document.createElement('section');
    card.id = 'voice-conversation-mode';
    card.className = 'voice-conversation-mode';
    card.dataset.state = 'ready';
    card.hidden = true;
    card.setAttribute('aria-live', 'polite');
    card.innerHTML = `
      <div class="voice-conversation-mode__header">
        <span class="voice-conversation-mode__label">Modo conversar</span>
        <h3 class="voice-conversation-mode__title">Converse com o DevPilot</h3>
      </div>
      <p class="voice-conversation-mode__text" data-voice-conversation-text>
        Toque em Conversar agora para ligar a voz sem abrir câmera ou seletor de arquivos.
      </p>
      <p class="voice-conversation-mode__hint">
        Em endereço HTTP da rede local, o Android pode bloquear o microfone. Se isso acontecer, use HTTPS.
      </p>
      <div class="voice-conversation-mode__actions">
        <button type="button" class="voice-conversation-mode__button voice-conversation-mode__button--primary" data-voice-conversation-start>
          Conversar agora
        </button>
        <button type="button" class="voice-conversation-mode__button voice-conversation-mode__button--secondary" data-voice-conversation-text-mode>
          Texto
        </button>
      </div>
    `;

    const composer = voicePanel.querySelector('.voice-chatgpt-composer, .voice-composer');
    if (composer) composer.before(card);
    else voicePanel.appendChild(card);

    card.querySelector('[data-voice-conversation-start]')?.addEventListener('click', startConversationMode);
    card.querySelector('[data-voice-conversation-text-mode]')?.addEventListener('click', focusTextComposer);
    return card;
  }

  const applyDesktopState = () => {
    statusNode.textContent = 'Este endereço HTTP da rede não libera microfone direto. Use HTTPS ou abra o DevPilot localmente em 127.0.0.1.';
    startButton.setAttribute('title', 'Microfone direto exige HTTPS ou localhost');
    startButton.setAttribute('aria-label', 'Microfone direto exige HTTPS ou localhost');
    startButton.dataset.captureMode = 'insecure-lan';
  };

  ensureMobileLayoutFix();

  if (isInsecureLan()) {
    if (isLikelyMobileDevice()) {
      ensureConversationModeCard();
      startButton.setAttribute('title', 'Modo conversar');
      startButton.setAttribute('aria-label', 'Abrir modo conversar');
      startButton.dataset.captureMode = 'conversation-mode';
      statusNode.textContent = 'Modo conversar disponível. Toque no microfone para começar.';
    } else {
      applyDesktopState();
    }
  }

  startButton.onclick = function guardedInsecureLanVoiceStart(event) {
    if (isInsecureLan() && isLikelyMobileDevice()) {
      startConversationMode(event);
      return;
    }

    if (isInsecureLan()) applyDesktopState();
    return originalStart.call(startButton, event);
  };

  const statusObserver = new MutationObserver(syncConversationModeState);
  statusObserver.observe(statusNode, {childList: true, subtree: true, characterData: true});

  const voiceStateObserver = new MutationObserver(syncConversationModeState);
  voiceStateObserver.observe(startButton, {attributes: true, attributeFilter: ['aria-pressed']});
  if (voicePanel) {
    voiceStateObserver.observe(voicePanel, {attributes: true, attributeFilter: ['class']});
  }

  modal.addEventListener('close', resetConversationMode);

  const modalOpenObserver = new MutationObserver(() => {
    if (!modal.open) return;
    ensureMobileLayoutFix();
    if (isInsecureLan() && isLikelyMobileDevice()) {
      ensureConversationModeCard();
      resetConversationMode();
      statusNode.textContent = 'Modo conversar disponível. Toque no microfone para começar.';
      syncConversationModeState();
    }
  });
  modalOpenObserver.observe(modal, {attributes: true, attributeFilter: ['open']});
})();