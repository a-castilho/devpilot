(() => {
  const LOCAL_UPDATE_PATTERNS = [
    /^(?:atualizar|atualize|atualiza|sincronizar|sincronize)\s+(?:o\s+)?(?:devpilot\s+)?local(?:\s+(?:no\s+)?linux)?$/i,
    /^(?:atualizar|atualize|atualiza)\s+(?:o\s+)?linux(?:\s+local)?$/i,
  ];

  const normalize = (value) => String(value || '').trim().replace(/\s+/g, ' ');
  const isLocalUpdate = (value) => LOCAL_UPDATE_PATTERNS.some((pattern) => pattern.test(normalize(value)));
  const startButton = document.querySelector('#voice-start');
  const sendButton = document.querySelector('#voice-send');
  const transcriptInput = document.querySelector('#voice-transcript');
  const statusNode = document.querySelector('#voice-status');
  const modal = document.querySelector('#voice-modal');

  if (!startButton || !sendButton || !transcriptInput || !statusNode || !modal) return;

  const originalSend = sendButton.onclick;
  const originalStartLabel = startButton.textContent;
  let dispatching = false;
  let recognition = null;
  let mediaRecorder = null;
  let mediaStream = null;
  let recordingTimer = null;
  let preferCompatibleMode = false;

  const insecureLanOrigin = () => {
    if (window.isSecureContext) return false;
    return !['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
  };

  const idleStartLabel = () => (insecureLanOrigin() ? '● Gravar' : originalStartLabel);

  const setStartLabel = (value) => {
    startButton.textContent = value || idleStartLabel();
  };

  const mobileAudioInput = document.createElement('input');
  mobileAudioInput.type = 'file';
  mobileAudioInput.accept = 'audio/*,.webm,.ogg,.m4a,.mp4,.mp3,.wav,.aac,.3gp,.3g2';
  mobileAudioInput.setAttribute('capture', '');
  mobileAudioInput.hidden = true;
  mobileAudioInput.tabIndex = -1;
  mobileAudioInput.setAttribute('aria-hidden', 'true');
  modal.appendChild(mobileAudioInput);

  const stopMediaStream = () => {
    if (recordingTimer) {
      clearTimeout(recordingTimer);
      recordingTimer = null;
    }
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }
    mediaRecorder = null;
    setStartLabel(idleStartLabel());
  };

  async function dispatchLocalUpdate(transcript, automatic = false) {
    if (dispatching) return;

    dispatching = true;
    startButton.disabled = true;
    sendButton.disabled = true;
    statusNode.textContent = automatic
      ? 'Comando reconhecido. Atualizando o Linux automaticamente…'
      : 'Enviando atualização local ao Linux…';

    try {
      const data = await api('/voice/system-actions', {
        method: 'POST',
        body: JSON.stringify({ transcript: normalize(transcript), project_id: null }),
      });
      modal.close();
      toast(data.message || 'Atualização local enviada ao Linux');
      if ('speechSynthesis' in window) {
        speechSynthesis.cancel();
        speechSynthesis.speak(new SpeechSynthesisUtterance('Atualização local enviada ao Linux.'));
      }
      if (typeof load === 'function') load();
    } catch (error) {
      statusNode.textContent = 'Falha ao iniciar atualização local.';
      toast(error.message || 'Falha ao iniciar atualização local');
    } finally {
      dispatching = false;
      startButton.disabled = false;
      sendButton.disabled = false;
    }
  }

  async function acceptTranscript(value) {
    const transcript = normalize(value);
    transcriptInput.value = transcript;
    if (!transcript) {
      statusNode.textContent = 'Nenhuma fala foi reconhecida. Tente novamente.';
      return;
    }
    if (isLocalUpdate(transcript)) {
      await dispatchLocalUpdate(transcript, true);
      return;
    }
    statusNode.textContent = 'Transcrição pronta. Revise antes de enviar.';
  }

  function normalizedAudioType(blob, filename = '') {
    const aliases = {
      'audio/x-m4a': 'audio/mp4',
      'audio/m4a': 'audio/mp4',
      'audio/x-wav': 'audio/wav',
      'video/3gpp': 'audio/3gpp',
      'video/3gpp2': 'audio/3gpp2',
      'application/octet-stream': '',
    };
    const byExtension = {
      webm: 'audio/webm',
      ogg: 'audio/ogg',
      oga: 'audio/ogg',
      m4a: 'audio/mp4',
      mp4: 'audio/mp4',
      mp3: 'audio/mpeg',
      wav: 'audio/wav',
      aac: 'audio/aac',
      '3gp': 'audio/3gpp',
      '3g2': 'audio/3gpp2',
    };
    const raw = String(blob?.type || '').split(';', 1)[0].toLowerCase();
    const normalized = Object.prototype.hasOwnProperty.call(aliases, raw) ? aliases[raw] : raw;
    if (normalized.startsWith('audio/')) return normalized;
    const extension = String(filename || '').split('.').pop()?.toLowerCase();
    return byExtension[extension] || 'audio/webm';
  }

  function audioExtension(mime) {
    return {
      'audio/webm': 'webm',
      'audio/ogg': 'ogg',
      'audio/mp4': 'm4a',
      'audio/mpeg': 'mp3',
      'audio/wav': 'wav',
      'audio/aac': 'aac',
      'audio/3gpp': '3gp',
      'audio/3gpp2': '3g2',
    }[mime] || 'webm';
  }

  async function transcribeRecordedAudio(blob, filename = '') {
    startButton.disabled = true;
    sendButton.disabled = true;
    statusNode.textContent = 'Transcrevendo áudio…';

    const mime = normalizedAudioType(blob, filename);
    const uploadBlob = String(blob?.type || '').split(';', 1)[0].toLowerCase() === mime
      ? blob
      : new Blob([blob], { type: mime });
    const form = new FormData();
    const uploadName = filename || `voice.${audioExtension(mime)}`;
    form.append('audio', uploadBlob, uploadName);

    try {
      const data = await api('/voice/transcriptions', {
        method: 'POST',
        body: form,
      });
      await acceptTranscript(data.text);
    } catch (error) {
      statusNode.textContent = error.message || 'Falha na transcrição do áudio.';
      toast(error.message || 'Falha na transcrição do áudio');
    } finally {
      startButton.disabled = false;
      sendButton.disabled = false;
      setStartLabel(idleStartLabel());
    }
  }

  function startMobileDeviceCapture() {
    statusNode.textContent = 'Abrindo o gravador do celular… grave o comando e confirme.';
    mobileAudioInput.value = '';
    mobileAudioInput.click();
  }

  mobileAudioInput.addEventListener('change', async () => {
    const file = mobileAudioInput.files?.[0];
    if (!file) {
      statusNode.textContent = 'Gravação cancelada. Toque em Gravar para tentar novamente.';
      return;
    }
    statusNode.textContent = 'Áudio recebido. Preparando transcrição…';
    await transcribeRecordedAudio(file, file.name || 'voice.m4a');
    mobileAudioInput.value = '';
  });

  function preferredMimeType() {
    if (!window.MediaRecorder?.isTypeSupported) return '';
    return [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
    ].find((type) => MediaRecorder.isTypeSupported(type)) || '';
  }

  async function startCompatibleCapture() {
    if (mediaRecorder?.state === 'recording') {
      statusNode.textContent = 'Finalizando gravação…';
      mediaRecorder.stop();
      return;
    }

    if (insecureLanOrigin()) {
      startMobileDeviceCapture();
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      statusNode.textContent = 'Este navegador não oferece captura direta. Selecione ou grave um arquivo de áudio.';
      startMobileDeviceCapture();
      return;
    }

    try {
      statusNode.textContent = 'Solicitando acesso ao microfone…';
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      const mimeType = preferredMimeType();
      const options = mimeType ? { mimeType } : undefined;
      mediaRecorder = new MediaRecorder(mediaStream, options);
      const chunks = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data?.size) chunks.push(event.data);
      };
      mediaRecorder.onerror = () => {
        statusNode.textContent = 'Falha ao gravar o áudio.';
        toast('Falha ao gravar o áudio');
        stopMediaStream();
      };
      mediaRecorder.onstop = async () => {
        const type = mediaRecorder?.mimeType || mimeType || 'audio/webm';
        const blob = new Blob(chunks, { type });
        stopMediaStream();
        if (!blob.size) {
          statusNode.textContent = 'Nenhum áudio foi capturado. Tente novamente.';
          return;
        }
        await transcribeRecordedAudio(blob);
      };

      mediaRecorder.start(250);
      setStartLabel('■ Parar');
      statusNode.textContent = 'Ouvindo no modo compatível… fale agora.';
      recordingTimer = window.setTimeout(() => {
        if (mediaRecorder?.state === 'recording') mediaRecorder.stop();
      }, 12000);
    } catch (error) {
      stopMediaStream();
      const denied = error?.name === 'NotAllowedError' || error?.name === 'SecurityError';
      if (denied) {
        statusNode.textContent = 'Acesso direto ao microfone negado. Abrindo o gravador do celular…';
        startMobileDeviceCapture();
      } else {
        statusNode.textContent = 'Não foi possível abrir o microfone.';
        toast(statusNode.textContent);
      }
    }
  }

  function recognitionErrorMessage(code) {
    if (code === 'no-speech') return 'Nenhuma fala foi detectada. Tente novamente.';
    if (code === 'audio-capture') return 'O navegador não conseguiu acessar o microfone.';
    if (code === 'not-allowed' || code === 'service-not-allowed') {
      preferCompatibleMode = true;
      if (insecureLanOrigin()) {
        return 'O navegador bloqueou a captura direta. Toque em Gravar para usar o gravador do celular.';
      }
      return 'Permissão de microfone negada. Libere o microfone nas permissões do navegador.';
    }
    if (code === 'network') {
      preferCompatibleMode = true;
      return 'O serviço de voz do navegador falhou. Toque em Iniciar novamente para usar o modo compatível.';
    }
    if (code === 'language-not-supported') {
      preferCompatibleMode = true;
      return 'O reconhecimento pt-BR do navegador não está disponível. Toque em Iniciar novamente para usar o modo compatível.';
    }
    return `Falha no reconhecimento de voz${code ? ` (${code})` : ''}.`;
  }

  function startNativeRecognition(SpeechRecognition) {
    let hadError = false;
    recognition = new SpeechRecognition();
    recognition.lang = 'pt-BR';
    recognition.interimResults = true;
    recognition.continuous = false;
    statusNode.textContent = 'Ouvindo…';

    recognition.onresult = (event) => {
      transcriptInput.value = [...event.results].map((result) => result[0].transcript).join(' ');
    };

    recognition.onend = async () => {
      recognition = null;
      if (hadError) return;
      await acceptTranscript(transcriptInput.value);
    };

    recognition.onerror = (event) => {
      hadError = true;
      recognition = null;
      statusNode.textContent = recognitionErrorMessage(event?.error);
      toast(statusNode.textContent);
    };

    try {
      recognition.start();
    } catch (error) {
      recognition = null;
      preferCompatibleMode = true;
      statusNode.textContent = 'O reconhecimento nativo não iniciou. Toque em Iniciar novamente para usar o modo compatível.';
      toast(statusNode.textContent);
    }
  }

  sendButton.onclick = async (event) => {
    const transcript = normalize(transcriptInput.value);
    if (isLocalUpdate(transcript)) {
      event?.preventDefault?.();
      await dispatchLocalUpdate(transcript, false);
      return;
    }
    if (typeof originalSend === 'function') return originalSend.call(sendButton, event);
  };

  startButton.onclick = async () => {
    if (mediaRecorder?.state === 'recording') {
      mediaRecorder.stop();
      return;
    }

    if (insecureLanOrigin()) {
      startMobileDeviceCapture();
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (preferCompatibleMode || !SpeechRecognition) {
      await startCompatibleCapture();
      return;
    }

    startNativeRecognition(SpeechRecognition);
  };

  modal.addEventListener('close', () => {
    try {
      recognition?.abort?.();
    } catch (_) {
      // Ignore browser-specific abort errors.
    }
    if (mediaRecorder?.state === 'recording') {
      mediaRecorder.stop();
    } else {
      stopMediaStream();
    }
  });

  if (insecureLanOrigin()) {
    setStartLabel(idleStartLabel());
    statusNode.textContent = 'Modo móvel ativo: toque em Gravar e use o gravador do celular.';
  }
})();