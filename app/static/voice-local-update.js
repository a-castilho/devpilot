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

  const setStartLabel = (value) => {
    startButton.textContent = value || originalStartLabel;
  };

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
    setStartLabel(originalStartLabel);
  };

  const insecureLanOrigin = () => {
    if (window.isSecureContext) return false;
    return !['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
  };

  async function dispatchLocalUpdate(transcript, automatic = false) {
    if (dispatching) return;
    if (typeof isSuperAdmin === 'function' && !isSuperAdmin()) {
      toast('Atualização local por voz é exclusiva do Super Admin');
      return;
    }

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

  async function transcribeRecordedAudio(blob) {
    startButton.disabled = true;
    sendButton.disabled = true;
    statusNode.textContent = 'Transcrevendo áudio no modo compatível…';

    const form = new FormData();
    const mime = String(blob.type || 'audio/webm').split(';', 1)[0];
    const extension = {
      'audio/webm': 'webm',
      'audio/ogg': 'ogg',
      'audio/mp4': 'm4a',
      'audio/mpeg': 'mp3',
      'audio/wav': 'wav',
      'audio/aac': 'aac',
      'audio/3gpp': '3gp',
    }[mime] || 'webm';
    form.append('audio', blob, `voice.${extension}`);

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
      setStartLabel(originalStartLabel);
    }
  }

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

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      if (insecureLanOrigin()) {
        statusNode.textContent =
          'O navegador bloqueou o microfone neste endereço HTTP da rede local. Use HTTPS ou localhost para liberar a voz.';
        toast('Microfone bloqueado pelo navegador neste endereço HTTP');
      } else {
        statusNode.textContent = 'Este navegador não oferece captura de áudio compatível.';
        toast('Captura de áudio indisponível neste navegador');
      }
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
      if (denied && insecureLanOrigin()) {
        statusNode.textContent =
          'O Android bloqueou o microfone porque o DevPilot está aberto por HTTP na rede local. Use HTTPS ou localhost.';
      } else if (denied) {
        statusNode.textContent = 'Permissão de microfone negada. Libere o microfone nas permissões do navegador.';
      } else {
        statusNode.textContent = 'Não foi possível abrir o microfone.';
      }
      toast(statusNode.textContent);
    }
  }

  function recognitionErrorMessage(code) {
    if (code === 'no-speech') return 'Nenhuma fala foi detectada. Tente novamente.';
    if (code === 'audio-capture') return 'O navegador não conseguiu acessar o microfone.';
    if (code === 'not-allowed' || code === 'service-not-allowed') {
      if (insecureLanOrigin()) {
        return 'O microfone foi bloqueado neste endereço HTTP da rede local. Use HTTPS ou localhost.';
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
})();
