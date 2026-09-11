(() => {
  const modal = document.querySelector('#voice-modal');
  const panel = modal?.querySelector('.voice-modal');
  const transcript = modal?.querySelector('#voice-transcript');
  const project = modal?.querySelector('#voice-project');
  const statusNode = modal?.querySelector('#voice-status');
  const startButton = modal?.querySelector('#voice-start');
  const modeSelect = modal?.querySelector('#voice-output-mode');
  const playbackWrapper = modal?.querySelector('.voice-conversation-controls');
  const chatLog = modal?.querySelector('#voice-chat-log');

  if (!modal || !panel || !transcript || !project || !statusNode || !startButton) return;
  if (panel.dataset.voiceEnhancedUi === '6') return;
  panel.dataset.voiceEnhancedUi = '6';

  modal.querySelector('#voice-upload')?.remove();
  modal.querySelector('#voice-upload-input')?.remove();
  modal.querySelector('#voice-send')?.remove();

  if (!document.querySelector('link[data-voice-enhanced-ui]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/assets/voice-enhanced-ui.css?v=20260822-chatgpt2';
    link.dataset.voiceEnhancedUi = '1';
    document.head.appendChild(link);
  }

  panel.classList.add('voice-modal-enhanced');
  panel.classList.remove('voice-session-active');
  transcript.rows = 1;
  transcript.placeholder = 'Mensagem para o DevPilot';
  transcript.setAttribute('aria-label', 'Mensagem para o DevPilot');
  transcript.setAttribute('autocomplete', 'off');
  transcript.setAttribute('enterkeyhint', 'send');
  statusNode.setAttribute('aria-live', 'polite');

  const heading = panel.querySelector('.voice-enhanced-heading');
  heading?.remove();

  const eyebrow = panel.querySelector(':scope > .eyebrow');
  const title = panel.querySelector(':scope > h2');
  eyebrow?.remove();
  title?.remove();

  const oldActions = panel.querySelector('.voice-enhanced-actions') || panel.querySelector('.hero-actions');
  const oldVisual = panel.querySelector('.voice-visual');

  const stage = document.createElement('section');
  stage.className = 'voice-chatgpt-stage';
  stage.setAttribute('aria-label', 'Conversa com o DevPilot');

  const response = document.createElement('div');
  response.id = 'voice-chat-preview';
  response.className = 'voice-chat-preview';
  response.hidden = true;
  response.innerHTML = '<span>DevPilot</span><p></p>';

  const status = document.createElement('div');
  status.className = 'voice-chatgpt-status';
  status.appendChild(statusNode);

  stage.append(response, status);

  const composer = document.createElement('div');
  composer.className = 'voice-composer voice-chatgpt-composer';

  const optionsButton = document.createElement('button');
  optionsButton.type = 'button';
  optionsButton.className = 'voice-chatgpt-options-button';
  optionsButton.setAttribute('aria-label', 'Opções da conversa');
  optionsButton.setAttribute('title', 'Opções da conversa');
  optionsButton.setAttribute('aria-expanded', 'false');
  optionsButton.textContent = '+';

  const transcriptControl = document.createElement('label');
  transcriptControl.className = 'voice-transcript-control';
  transcriptControl.appendChild(transcript);

  const sendButton = document.createElement('button');
  sendButton.type = 'button';
  sendButton.id = 'voice-chat-send';
  sendButton.className = 'voice-composer-button voice-send-button';
  sendButton.setAttribute('aria-label', 'Enviar mensagem');
  sendButton.setAttribute('title', 'Enviar mensagem');
  sendButton.textContent = '↑';

  startButton.classList.add('voice-composer-button', 'voice-record-button');
  startButton.textContent = '';
  startButton.setAttribute('aria-label', 'Ligar conversa por voz');
  startButton.setAttribute('title', 'Ligar conversa por voz');

  const stopButton = document.createElement('button');
  stopButton.type = 'button';
  stopButton.id = 'voice-stop';
  stopButton.className = 'voice-composer-button voice-stop-button';
  stopButton.setAttribute('aria-label', 'Desligar conversa por voz');
  stopButton.setAttribute('title', 'Desligar conversa por voz');

  composer.append(optionsButton, transcriptControl, sendButton, startButton, stopButton);

  const options = document.createElement('div');
  options.className = 'voice-chatgpt-options';
  options.hidden = true;
  options.setAttribute('aria-label', 'Opções da conversa');

  const projectControl = document.createElement('label');
  projectControl.className = 'voice-project-control';
  projectControl.innerHTML = '<span>Projeto</span>';
  projectControl.appendChild(project);
  options.appendChild(projectControl);

  if (modeSelect) {
    const outputControl = document.createElement('label');
    outputControl.className = 'voice-output-control';
    outputControl.innerHTML = '<span>Voz do DevPilot</span>';
    outputControl.appendChild(modeSelect);
    options.appendChild(outputControl);
  }

  panel.insertBefore(options, panel.firstChild);
  panel.append(stage, composer);

  oldVisual?.remove();
  oldActions?.remove();
  playbackWrapper?.remove();

  const closeButton = panel.querySelector('.close');
  if (closeButton) {
    closeButton.setAttribute('aria-label', 'Fechar conversa');
    closeButton.setAttribute('title', 'Fechar conversa');
  }

  const ensureGeneralProject = () => {
    if ([...project.options].some((option) => option.value === '')) return;
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'Geral — sem projeto específico';
    project.prepend(option);
  };

  const closeOptions = () => {
    options.hidden = true;
    optionsButton.setAttribute('aria-expanded', 'false');
  };

  optionsButton.addEventListener('click', (event) => {
    event.stopPropagation();
    ensureGeneralProject();
    const opening = options.hidden;
    options.hidden = !opening;
    optionsButton.setAttribute('aria-expanded', opening ? 'true' : 'false');
  });
  options.addEventListener('click', (event) => event.stopPropagation());
  document.addEventListener('click', closeOptions);

  const setPreview = (text) => {
    const value = String(text || '').trim();
    const paragraph = response.querySelector('p');
    if (!paragraph) return;
    paragraph.textContent = value;
    response.hidden = !value;
  };

  if (chatLog) {
    const syncPreview = () => {
      const latest = [...chatLog.querySelectorAll('.voice-chat-turn[data-role="assistant"] p')].pop();
      if (latest?.textContent) setPreview(latest.textContent);
    };
    new MutationObserver(syncPreview).observe(chatLog, {childList: true, subtree: true});
    syncPreview();
  }

  let voiceEnabled = false;
  let sessionToken = 0;
  let captureToken = 0;
  let recognition = null;
  let mediaRecorder = null;
  let mediaStream = null;
  let recordingTimer = null;
  let preferCompatibleCapture = false;
  let submitting = false;

  const localUpdatePatterns = [
    /^(?:atualizar|atualize|atualiza|sincronizar|sincronize)\s+(?:o\s+)?(?:devpilot\s+)?local(?:\s+(?:no\s+)?linux)?$/i,
    /^(?:atualizar|atualize|atualiza)\s+(?:o\s+)?linux(?:\s+local)?$/i,
    /^(?:reiniciar|reinicie|restart)\s+(?:o\s+)?(?:linux|servidor|devpilot|api(?:\s+e\s+worker)?)$/i,
  ];

  const normalize = (value) => String(value || '').trim().replace(/\s+/g, ' ');
  const isLocalUpdate = (value) => localUpdatePatterns.some((pattern) => pattern.test(normalize(value)));

  const resizeTranscript = () => {
    transcript.style.height = 'auto';
    transcript.style.height = `${Math.min(Math.max(transcript.scrollHeight, 28), 112)}px`;
    sendButton.disabled = !normalize(transcript.value) || submitting;
  };

  transcript.addEventListener('input', resizeTranscript);
  resizeTranscript();

  const cleanupMedia = () => {
    if (recordingTimer) {
      clearTimeout(recordingTimer);
      recordingTimer = null;
    }
    try {
      mediaStream?.getTracks?.().forEach((track) => track.stop());
    } catch (_) {
      // Best effort only.
    }
    mediaStream = null;
    mediaRecorder = null;
  };

  const pauseCapture = () => {
    captureToken += 1;
    try {
      recognition?.abort?.();
    } catch (_) {
      // Browser-specific recognition cleanup is best effort.
    }
    recognition = null;

    if (mediaRecorder?.state === 'recording') {
      try {
        mediaRecorder.stop();
      } catch (_) {
        // Best effort only.
      }
    }
    cleanupMedia();
  };

  const updateVoiceState = () => {
    panel.classList.toggle('voice-session-active', voiceEnabled);
    startButton.setAttribute('aria-pressed', voiceEnabled ? 'true' : 'false');
    if (!voiceEnabled && !submitting) statusNode.textContent = 'Voz desligada. Digite uma mensagem ou ligue o microfone.';
  };

  const stopConversation = (message = 'Voz desligada. Digite uma mensagem ou ligue o microfone.') => {
    voiceEnabled = false;
    sessionToken += 1;
    pauseCapture();
    try {
      window.speechSynthesis?.cancel?.();
    } catch (_) {
      // Best effort only.
    }
    statusNode.textContent = message;
    updateVoiceState();
  };

  const transcribeAudio = async (blob) => {
    if (!blob?.size) throw new Error('Nenhum áudio foi capturado.');
    const type = String(blob.type || 'audio/webm').split(';', 1)[0] || 'audio/webm';
    const extension = type.includes('ogg') ? 'ogg' : type.includes('mp4') ? 'm4a' : 'webm';
    const form = new FormData();
    form.append('audio', new Blob([blob], {type}), `voice.${extension}`);
    const data = await api('/voice/transcriptions', {method: 'POST', body: form});
    return normalize(data?.text);
  };

  const runLocalUpdate = async (text) => {
    const data = await api('/voice/system-actions', {
      method: 'POST',
      body: JSON.stringify({transcript: normalize(text), project_id: null}),
    });
    const message = String(data?.message || 'Atualização local enviada ao Linux.');
    setPreview(message);
    if (typeof toast === 'function') toast(message);
    stopConversation('Comando enviado. A conversa por voz foi desligada.');
  };

  const submitCurrent = async (expectedSession = sessionToken, textOverride = '') => {
    const text = normalize(textOverride || transcript.value);
    if (!text || submitting) return;

    // O composer é apenas para texto digitado. Transcrição de voz nunca deve
    // aparecer nele e qualquer texto enviado deve sumir imediatamente.
    transcript.value = '';
    resizeTranscript();

    submitting = true;
    sendButton.disabled = true;
    statusNode.textContent = 'DevPilot está pensando…';

    try {
      if (isLocalUpdate(text)) {
        await runLocalUpdate(text);
        return;
      }

      if (typeof window.devpilotVoiceConversationSubmit !== 'function') {
        throw new Error('Chat interno do DevPilot indisponível.');
      }

      // O módulo legado de conversa lê o textarea sincronicamente. Entregamos
      // o texto somente durante a chamada e limpamos antes que o navegador pinte.
      transcript.value = text;
      const submitPromise = window.devpilotVoiceConversationSubmit();
      transcript.value = '';
      resizeTranscript();
      await submitPromise;
    } catch (error) {
      transcript.value = '';
      resizeTranscript();
      const message = error?.message || 'Não foi possível conversar com o DevPilot.';
      statusNode.textContent = message;
      if (typeof toast === 'function') toast(message);
    } finally {
      submitting = false;
      transcript.value = '';
      resizeTranscript();
    }

    if (voiceEnabled && expectedSession === sessionToken) {
      statusNode.textContent = 'Ouvindo… fale com o DevPilot.';
      window.setTimeout(() => startListening(expectedSession), 220);
    } else if (!voiceEnabled) {
      statusNode.textContent = 'Pronto. Digite outra mensagem ou ligue o microfone.';
    }
  };

  const startNativeRecognition = (SpeechRecognition, expectedSession) => {
    const cycle = ++captureToken;
    let hadError = false;
    let capturedText = '';
    transcript.value = '';
    resizeTranscript();

    recognition = new SpeechRecognition();
    recognition.lang = 'pt-BR';
    recognition.interimResults = true;
    recognition.continuous = false;
    statusNode.textContent = 'Ouvindo… fale com o DevPilot.';

    recognition.onresult = (event) => {
      if (cycle !== captureToken || expectedSession !== sessionToken) return;
      capturedText = [...event.results].map((item) => item[0].transcript).join(' ');
    };

    recognition.onerror = (event) => {
      if (cycle !== captureToken || expectedSession !== sessionToken) return;
      hadError = true;
      recognition = null;
      const code = String(event?.error || '');
      if (['network', 'language-not-supported', 'service-not-allowed'].includes(code)) {
        preferCompatibleCapture = true;
        statusNode.textContent = 'Reconhecimento nativo indisponível. Ativando captura compatível…';
        window.setTimeout(() => {
          if (voiceEnabled && expectedSession === sessionToken) startCompatibleCapture(expectedSession);
        }, 180);
        return;
      }
      if (code === 'no-speech') {
        statusNode.textContent = 'Não ouvi fala. Continuo escutando…';
        window.setTimeout(() => {
          if (voiceEnabled && expectedSession === sessionToken) startListening(expectedSession);
        }, 320);
        return;
      }
      const message = code === 'not-allowed'
        ? 'Microfone bloqueado. Libere a permissão no navegador.'
        : 'Não foi possível usar o microfone.';
      stopConversation(message);
      if (typeof toast === 'function') toast(message);
    };

    recognition.onend = () => {
      recognition = null;
      if (hadError || cycle !== captureToken || expectedSession !== sessionToken || !voiceEnabled) return;
      const text = normalize(capturedText);
      capturedText = '';
      if (text) {
        submitCurrent(expectedSession, text);
      } else {
        window.setTimeout(() => {
          if (voiceEnabled && expectedSession === sessionToken) startListening(expectedSession);
        }, 260);
      }
    };

    try {
      recognition.start();
    } catch (_) {
      recognition = null;
      preferCompatibleCapture = true;
      statusNode.textContent = 'Ativando captura compatível…';
      window.setTimeout(() => {
        if (voiceEnabled && expectedSession === sessionToken) startCompatibleCapture(expectedSession);
      }, 120);
    }
  };

  const startCompatibleCapture = async (expectedSession) => {
    if (!voiceEnabled || expectedSession !== sessionToken || submitting) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      stopConversation('Este navegador não permite captura contínua de voz neste endereço.');
      return;
    }

    const cycle = ++captureToken;
    try {
      statusNode.textContent = 'Abrindo o microfone…';
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true},
      });
      if (!voiceEnabled || expectedSession !== sessionToken || cycle !== captureToken) {
        cleanupMedia();
        return;
      }

      const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
        .find((type) => MediaRecorder.isTypeSupported?.(type)) || '';
      mediaRecorder = new MediaRecorder(mediaStream, mime ? {mimeType: mime} : undefined);
      const chunks = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data?.size) chunks.push(event.data);
      };
      mediaRecorder.onerror = () => {
        if (cycle !== captureToken) return;
        cleanupMedia();
        stopConversation('Falha ao gravar o áudio.');
      };
      mediaRecorder.onstop = async () => {
        const type = mediaRecorder?.mimeType || mime || 'audio/webm';
        const blob = new Blob(chunks, {type});
        cleanupMedia();
        if (cycle !== captureToken || expectedSession !== sessionToken || !voiceEnabled) return;

        try {
          statusNode.textContent = 'Transcrevendo…';
          const text = await transcribeAudio(blob);
          if (cycle !== captureToken || expectedSession !== sessionToken || !voiceEnabled) return;
          if (!text) {
            statusNode.textContent = 'Não ouvi fala. Continuo escutando…';
            window.setTimeout(() => startListening(expectedSession), 260);
            return;
          }
          await submitCurrent(expectedSession, text);
        } catch (error) {
          const message = error?.message || 'Falha na transcrição do áudio.';
          stopConversation(message);
          if (typeof toast === 'function') toast(message);
        }
      };

      mediaRecorder.start(250);
      statusNode.textContent = 'Ouvindo… fale com o DevPilot.';
      recordingTimer = window.setTimeout(() => {
        if (mediaRecorder?.state === 'recording' && cycle === captureToken) mediaRecorder.stop();
      }, 8000);
    } catch (error) {
      cleanupMedia();
      const message = error?.name === 'NotAllowedError' || error?.name === 'SecurityError'
        ? 'Microfone bloqueado. Libere a permissão no navegador.'
        : 'Não foi possível abrir o microfone.';
      stopConversation(message);
      if (typeof toast === 'function') toast(message);
    }
  };

  function startListening(expectedSession = sessionToken) {
    if (!voiceEnabled || expectedSession !== sessionToken || submitting) return;
    pauseCapture();

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!preferCompatibleCapture && SpeechRecognition) {
      startNativeRecognition(SpeechRecognition, expectedSession);
      return;
    }
    startCompatibleCapture(expectedSession);
  }

  const startConversation = () => {
    if (voiceEnabled) return;
    voiceEnabled = true;
    sessionToken += 1;
    panel.classList.add('voice-session-active');
    startButton.setAttribute('aria-pressed', 'true');
    statusNode.textContent = 'Ligando o microfone…';
    startListening(sessionToken);
  };

  startButton.onclick = (event) => {
    event?.preventDefault?.();
    startConversation();
  };

  stopButton.onclick = (event) => {
    event?.preventDefault?.();
    stopConversation();
  };

  sendButton.onclick = async () => {
    const text = normalize(transcript.value);
    if (!text || submitting) return;
    const expectedSession = sessionToken;
    if (voiceEnabled) pauseCapture();
    await submitCurrent(expectedSession, text);
  };

  transcript.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    sendButton.click();
  });

  modal.addEventListener('close', () => {
    closeOptions();
    voiceEnabled = false;
    sessionToken += 1;
    pauseCapture();
    try {
      window.speechSynthesis?.cancel?.();
    } catch (_) {
      // Best effort only.
    }
    setPreview('');
    transcript.value = '';
    resizeTranscript();
    panel.classList.remove('voice-session-active');
  });

  const modalOpenObserver = new MutationObserver(() => {
    if (!modal.open) return;
    ensureGeneralProject();
    statusNode.textContent = 'Voz desligada. Digite uma mensagem ou ligue o microfone.';
    updateVoiceState();
    window.setTimeout(() => transcript.focus({preventScroll: true}), 80);
  });
  modalOpenObserver.observe(modal, {attributes: true, attributeFilter: ['open']});

  ensureGeneralProject();
  updateVoiceState();
  window.devpilotVoiceStop = stopConversation;
})();