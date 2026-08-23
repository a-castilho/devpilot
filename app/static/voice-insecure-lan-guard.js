(() => {
  const startButton = document.querySelector('#voice-start');
  const statusNode = document.querySelector('#voice-status');
  const modal = document.querySelector('#voice-modal');
  const transcript = document.querySelector('#voice-transcript');
  const sendButton = document.querySelector('#voice-chat-send');

  if (!startButton || !statusNode || !modal || startButton.dataset.insecureLanGuard === '3') return;

  const originalStart = startButton.onclick;
  if (typeof originalStart !== 'function') return;

  startButton.dataset.insecureLanGuard = '3';

  const isLoopback = () => ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
  const isInsecureLan = () => !window.isSecureContext && !isLoopback();

  const isLikelyMobileDevice = () => {
    if (navigator.userAgentData?.mobile === true) return true;

    const userAgent = String(navigator.userAgent || '');
    if (/Android|iPhone|iPad|iPod|IEMobile|Opera Mini|Mobile/i.test(userAgent)) return true;

    // iPadOS can identify itself as Macintosh while still exposing touch points.
    return /Macintosh/i.test(userAgent) && Number(navigator.maxTouchPoints || 0) > 1;
  };

  const ensureMobileLayoutFix = () => {
    if (!isLikelyMobileDevice()) return;
    if (document.querySelector('link[data-voice-mobile-fix]')) return;

    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/assets/voice-mobile-fix.css?v=20260823-1';
    link.dataset.voiceMobileFix = '1';
    document.head.appendChild(link);
  };

  const localMicrophoneUrl = () => {
    const url = new URL(window.location.href);
    url.hostname = '127.0.0.1';
    return url.toString();
  };

  const ensureLocalMicrophoneButton = () => {
    if (!isInsecureLan() || isLikelyMobileDevice()) return;
    if (modal.querySelector('#voice-open-loopback')) return;

    const actions = modal.querySelector('.voice-enhanced-actions') || modal.querySelector('.hero-actions');
    if (!actions) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.id = 'voice-open-loopback';
    button.className = 'ghost voice-loopback-button';
    button.textContent = 'Abrir microfone local';
    button.setAttribute('title', 'Abrir o DevPilot em 127.0.0.1 para permitir microfone direto');
    button.onclick = () => window.location.assign(localMicrophoneUrl());
    actions.appendChild(button);
  };

  const applyDesktopState = () => {
    statusNode.textContent =
      'Este endereço HTTP da rede não libera microfone direto. Abra o DevPilot em 127.0.0.1 ou use HTTPS.';
    startButton.setAttribute('title', 'Microfone direto exige HTTPS ou localhost');
    startButton.setAttribute('aria-label', 'Microfone direto exige HTTPS ou localhost');
    startButton.dataset.captureMode = 'insecure-lan';
    ensureLocalMicrophoneButton();
  };

  const mobileAudioInput = document.createElement('input');
  mobileAudioInput.type = 'file';
  mobileAudioInput.accept = 'audio/*,.webm,.ogg,.m4a,.mp4,.mp3,.wav,.aac,.3gp,.3g2';
  mobileAudioInput.setAttribute('capture', 'user');
  mobileAudioInput.hidden = true;
  mobileAudioInput.tabIndex = -1;
  mobileAudioInput.setAttribute('aria-hidden', 'true');
  mobileAudioInput.dataset.voiceMobileLanCapture = '1';
  modal.appendChild(mobileAudioInput);

  const openMobileRecorder = () => {
    ensureMobileLayoutFix();
    statusNode.textContent = 'Abrindo o gravador do celular… grave a mensagem e confirme.';
    startButton.disabled = true;
    mobileAudioInput.value = '';
    mobileAudioInput.click();
    window.setTimeout(() => {
      startButton.disabled = false;
    }, 400);
  };

  const uploadMobileAudio = async (file) => {
    if (!file?.size) {
      statusNode.textContent = 'Nenhum áudio foi capturado. Toque no microfone para tentar novamente.';
      return;
    }

    const form = new FormData();
    form.append('audio', file, file.name || 'voice-mobile.m4a');

    startButton.disabled = true;
    statusNode.textContent = 'Transcrevendo áudio…';

    try {
      if (typeof api !== 'function') throw new Error('API de transcrição indisponível.');
      const data = await api('/voice/transcriptions', {method: 'POST', body: form});
      const text = String(data?.text || '').trim();
      if (!text) {
        statusNode.textContent = 'Nenhuma fala foi reconhecida. Toque no microfone e tente novamente.';
        return;
      }

      // A transcrição não deve ficar visível no composer. Entregamos o texto
      // apenas de forma síncrona ao fluxo já existente e ele é limpo no envio.
      if (!transcript || !sendButton) throw new Error('Composer de voz indisponível.');
      transcript.value = text;
      transcript.dispatchEvent(new Event('input', {bubbles: true}));
      sendButton.click();
      transcript.value = '';
      transcript.dispatchEvent(new Event('input', {bubbles: true}));
    } catch (error) {
      const message = error?.message || 'Falha na transcrição do áudio.';
      statusNode.textContent = message;
      if (typeof toast === 'function') toast(message);
    } finally {
      startButton.disabled = false;
      mobileAudioInput.value = '';
    }
  };

  mobileAudioInput.addEventListener('change', async () => {
    const file = mobileAudioInput.files?.[0];
    if (!file) {
      statusNode.textContent = 'Gravação cancelada. Toque no microfone para tentar novamente.';
      startButton.disabled = false;
      return;
    }
    await uploadMobileAudio(file);
  });

  ensureMobileLayoutFix();

  if (isInsecureLan()) {
    if (isLikelyMobileDevice()) {
      statusNode.textContent = 'Modo móvel: toque no microfone para gravar sua mensagem.';
      startButton.setAttribute('title', 'Gravar mensagem no celular');
      startButton.setAttribute('aria-label', 'Gravar mensagem no celular');
      startButton.dataset.captureMode = 'mobile-device-recorder';
    } else {
      applyDesktopState();
    }
  }

  startButton.onclick = function guardedInsecureLanVoiceStart(event) {
    if (isInsecureLan() && isLikelyMobileDevice()) {
      event?.preventDefault?.();
      openMobileRecorder();
      return;
    }

    if (isInsecureLan()) {
      applyDesktopState();
      if (typeof toast === 'function') {
        toast('Microfone direto exige HTTPS ou acesso local em 127.0.0.1.');
      }
    }

    return originalStart.call(startButton, event);
  };

  const modalOpenObserver = new MutationObserver(() => {
    if (!modal.open) return;
    ensureMobileLayoutFix();
    if (isInsecureLan() && isLikelyMobileDevice()) {
      statusNode.textContent = 'Modo móvel: toque no microfone para gravar sua mensagem.';
    }
  });
  modalOpenObserver.observe(modal, {attributes: true, attributeFilter: ['open']});
})();
