(() => {
  const startButton = document.querySelector('#voice-start');
  const transcriptInput = document.querySelector('#voice-transcript');
  const statusNode = document.querySelector('#voice-status');
  const modal = document.querySelector('#voice-modal');

  if (!startButton || !transcriptInput || !statusNode || !modal) return;
  if (startButton.dataset.browserCompatV2 === '1') return;
  startButton.dataset.browserCompatV2 = '1';

  const DEFAULT_LABEL = '● Iniciar';
  const FALLBACK_LABEL = '● Usar gravador';
  const MAX_RECORDING_MS = 12000;

  let recorder = null;
  let stream = null;
  let timer = null;
  let recognition = null;
  let fallbackMode = false;

  const isLoopback = () => ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
  const isSecureForMedia = () => window.isSecureContext || isLoopback();

  const setLabel = (label) => {
    startButton.textContent = label || DEFAULT_LABEL;
  };

  const cleanup = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    try {
      stream?.getTracks?.().forEach((track) => track.stop());
    } catch (_) {
      // Best effort cleanup only.
    }
    stream = null;
    recorder = null;
    if (!fallbackMode) setLabel(DEFAULT_LABEL);
  };

  const mobileAudioInput = document.createElement('input');
  mobileAudioInput.type = 'file';
  mobileAudioInput.accept = 'audio/*,.webm,.ogg,.m4a,.mp4,.mp3,.wav,.aac,.3gp,.3g2';
  mobileAudioInput.setAttribute('capture', 'microphone');
  mobileAudioInput.hidden = true;
  mobileAudioInput.tabIndex = -1;
  mobileAudioInput.setAttribute('aria-hidden', 'true');
  modal.appendChild(mobileAudioInput);

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

  function preferredMimeType() {
    if (!window.MediaRecorder?.isTypeSupported) return '';
    return [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/ogg',
      'audio/mp4',
    ].find((type) => MediaRecorder.isTypeSupported(type)) || '';
  }

  async function transcribeAudio(blob, filename = '') {
    if (!blob?.size) {
      statusNode.textContent = 'Nenhum áudio foi capturado. Tente novamente.';
      return;
    }

    const mime = normalizedAudioType(blob, filename);
    const currentType = String(blob.type || '').split(';', 1)[0].toLowerCase();
    const uploadBlob = currentType === mime ? blob : new Blob([blob], { type: mime });
    const form = new FormData();
    form.append('audio', uploadBlob, filename || `voice.${audioExtension(mime)}`);

    startButton.disabled = true;
    statusNode.textContent = 'Transcrevendo áudio…';

    try {
      if (typeof api !== 'function') throw new Error('API de transcrição indisponível');
      const data = await api('/voice/transcriptions', {
        method: 'POST',
        body: form,
      });
      transcriptInput.value = String(data?.text || '').trim();
      statusNode.textContent = transcriptInput.value
        ? 'Transcrição pronta. Revise antes de enviar.'
        : 'Nenhuma fala foi reconhecida. Tente novamente.';
      fallbackMode = false;
      setLabel(DEFAULT_LABEL);
    } catch (error) {
      statusNode.textContent = error?.message || 'Falha na transcrição do áudio.';
      if (typeof toast === 'function') toast(statusNode.textContent);
    } finally {
      startButton.disabled = false;
    }
  }

  function openDeviceRecorder() {
    fallbackMode = true;
    setLabel(FALLBACK_LABEL);
    statusNode.textContent = 'Use o gravador do dispositivo ou selecione um áudio.';
    mobileAudioInput.value = '';
    mobileAudioInput.click();
  }

  mobileAudioInput.addEventListener('change', async () => {
    const file = mobileAudioInput.files?.[0];
    if (!file) {
      statusNode.textContent = 'Gravação cancelada. Toque em Usar gravador para tentar novamente.';
      setLabel(FALLBACK_LABEL);
      return;
    }

    statusNode.textContent = 'Áudio recebido. Preparando transcrição…';
    await transcribeAudio(file, file.name || 'voice.m4a');
    mobileAudioInput.value = '';
  });

  function microphoneFailureMessage(error) {
    const name = String(error?.name || '');

    if (name === 'NotAllowedError' || name === 'SecurityError') {
      return 'O navegador não liberou o microfone. Use o gravador do dispositivo ou tente Iniciar novamente e aceite a solicitação.';
    }
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      return 'O navegador não encontrou uma entrada de áudio. Use o gravador do dispositivo.';
    }
    if (name === 'NotReadableError' || name === 'TrackStartError' || name === 'AbortError') {
      return 'O microfone está ocupado ou temporariamente indisponível. Use o gravador do dispositivo.';
    }
    if (name === 'OverconstrainedError' || name === 'ConstraintNotSatisfiedError') {
      return 'A configuração de áudio não é aceita neste navegador. Usando modo compatível.';
    }
    return 'A captura direta não está disponível. Use o gravador do dispositivo.';
  }

  async function startRecorder() {
    if (recorder?.state === 'recording') {
      statusNode.textContent = 'Finalizando gravação…';
      recorder.stop();
      return;
    }

    try {
      statusNode.textContent = 'Solicitando acesso ao microfone…';

      // audio:true is intentionally used instead of vendor-specific constraints.
      // It is the most interoperable request across Chromium, Firefox and Safari.
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const mimeType = preferredMimeType();
      const options = mimeType ? { mimeType } : undefined;
      recorder = new MediaRecorder(stream, options);
      const chunks = [];

      recorder.ondataavailable = (event) => {
        if (event.data?.size) chunks.push(event.data);
      };

      recorder.onerror = () => {
        statusNode.textContent = 'Falha durante a gravação. Use o gravador do dispositivo.';
        fallbackMode = true;
        cleanup();
        setLabel(FALLBACK_LABEL);
      };

      recorder.onstop = async () => {
        const type = recorder?.mimeType || mimeType || 'audio/webm';
        const blob = new Blob(chunks, { type });
        cleanup();
        await transcribeAudio(blob);
      };

      fallbackMode = false;
      recorder.start(250);
      setLabel('■ Parar');
      statusNode.textContent = 'Ouvindo… fale agora.';

      timer = window.setTimeout(() => {
        if (recorder?.state === 'recording') recorder.stop();
      }, MAX_RECORDING_MS);
    } catch (error) {
      cleanup();
      fallbackMode = true;
      statusNode.textContent = microphoneFailureMessage(error);
      setLabel(FALLBACK_LABEL);
      if (typeof toast === 'function') toast(statusNode.textContent);
    }
  }

  function startSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      openDeviceRecorder();
      return;
    }

    try {
      recognition = new SpeechRecognition();
      recognition.lang = 'pt-BR';
      recognition.interimResults = true;
      recognition.continuous = false;
      statusNode.textContent = 'Ouvindo…';

      recognition.onresult = (event) => {
        transcriptInput.value = [...event.results]
          .map((result) => result[0]?.transcript || '')
          .join(' ')
          .trim();
      };

      recognition.onerror = () => {
        recognition = null;
        fallbackMode = true;
        statusNode.textContent = 'O reconhecimento nativo falhou. Use o gravador do dispositivo.';
        setLabel(FALLBACK_LABEL);
      };

      recognition.onend = () => {
        recognition = null;
        if (transcriptInput.value.trim()) {
          fallbackMode = false;
          statusNode.textContent = 'Transcrição pronta. Revise antes de enviar.';
          setLabel(DEFAULT_LABEL);
        }
      };

      recognition.start();
    } catch (_) {
      recognition = null;
      openDeviceRecorder();
    }
  }

  startButton.onclick = async () => {
    if (recorder?.state === 'recording') {
      recorder.stop();
      return;
    }

    if (fallbackMode) {
      openDeviceRecorder();
      return;
    }

    if (!isSecureForMedia()) {
      statusNode.textContent = 'Captura direta exige HTTPS. Abrindo o gravador do dispositivo…';
      openDeviceRecorder();
      return;
    }

    if (navigator.mediaDevices?.getUserMedia && window.MediaRecorder) {
      await startRecorder();
      return;
    }

    if (window.SpeechRecognition || window.webkitSpeechRecognition) {
      startSpeechRecognition();
      return;
    }

    openDeviceRecorder();
  };

  modal.addEventListener('close', () => {
    try {
      recognition?.abort?.();
    } catch (_) {
      // Browser-specific abort errors are harmless on close.
    }
    recognition = null;

    if (recorder?.state === 'recording') {
      try {
        recorder.stop();
      } catch (_) {
        cleanup();
      }
    } else {
      cleanup();
    }

    fallbackMode = false;
    setLabel(DEFAULT_LABEL);
  });

  const engine = navigator.mediaDevices?.getUserMedia && window.MediaRecorder
    ? 'media-recorder'
    : (window.SpeechRecognition || window.webkitSpeechRecognition ? 'speech-recognition' : 'file-capture');
  modal.dataset.voiceEngine = engine;
})();
