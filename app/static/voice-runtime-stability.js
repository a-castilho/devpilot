(() => {
  'use strict';

  if (window.__devpilotVoiceRuntimeStabilityReady) return;
  window.__devpilotVoiceRuntimeStabilityReady = true;

  const modal = document.querySelector('#voice-modal');
  const panel = modal?.querySelector('.voice-modal-enhanced');
  const transcript = modal?.querySelector('#voice-transcript');
  const statusNode = modal?.querySelector('#voice-status');
  const startButton = modal?.querySelector('#voice-start');
  const stopButton = modal?.querySelector('#voice-stop');

  if (!modal || !panel || !transcript || !statusNode || !startButton) return;

  let sessionActive = false;
  let sessionEpoch = 0;
  let captureEpoch = 0;
  let recognition = null;
  let recorder = null;
  let stream = null;
  let audioContext = null;
  let analyserTimer = null;
  let hardStopTimer = null;
  let preferRecorder = false;
  let requestController = null;

  const normalize = value => String(value || '').trim().replace(/\s+/g, ' ');
  const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms));

  function setSessionUi(active) {
    panel.classList.toggle('voice-session-active', active);
    startButton.setAttribute('aria-pressed', active ? 'true' : 'false');
  }

  function clearTimers() {
    if (analyserTimer) window.clearInterval(analyserTimer);
    if (hardStopTimer) window.clearTimeout(hardStopTimer);
    analyserTimer = null;
    hardStopTimer = null;
  }

  function stopTracks() {
    try { stream?.getTracks?.().forEach(track => track.stop()); } catch (_) {}
    stream = null;
  }

  function closeAudioContext() {
    try { audioContext?.close?.(); } catch (_) {}
    audioContext = null;
  }

  function cleanupCapture({abortRequest = false} = {}) {
    clearTimers();
    try { recognition?.abort?.(); } catch (_) {}
    recognition = null;

    if (recorder?.state === 'recording') {
      try { recorder.stop(); } catch (_) {}
    }
    recorder = null;
    stopTracks();
    closeAudioContext();

    if (abortRequest) {
      try { requestController?.abort?.(); } catch (_) {}
      requestController = null;
    }
  }

  function stopSession(message = 'Voz desligada. Digite uma mensagem ou ligue o microfone.') {
    sessionActive = false;
    sessionEpoch += 1;
    captureEpoch += 1;
    cleanupCapture({abortRequest: true});
    setSessionUi(false);
    statusNode.textContent = message;
  }

  function supportedMimeType() {
    if (!window.MediaRecorder?.isTypeSupported) return '';
    return [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
    ].find(type => MediaRecorder.isTypeSupported(type)) || '';
  }

  function extensionFor(type) {
    const value = String(type || '').toLowerCase();
    if (value.includes('ogg')) return 'ogg';
    if (value.includes('mp4')) return 'm4a';
    if (value.includes('mpeg')) return 'mp3';
    if (value.includes('wav')) return 'wav';
    return 'webm';
  }

  function errorDetail(data, fallback) {
    if (typeof data?.detail === 'string' && data.detail.trim()) return data.detail.trim();
    if (Array.isArray(data?.detail)) {
      const message = data.detail.map(item => item?.msg).filter(Boolean).join(' · ');
      if (message) return message;
    }
    return fallback;
  }

  async function transcribe(blob, expectedSession) {
    if (!blob?.size) return {text: '', recoverable: true};
    const type = String(blob.type || 'audio/webm').split(';', 1)[0] || 'audio/webm';
    const form = new FormData();
    form.append('audio', new Blob([blob], {type}), `voice.${extensionFor(type)}`);

    requestController?.abort?.();
    requestController = new AbortController();
    const timeoutId = window.setTimeout(() => requestController?.abort?.(), 25000);

    try {
      const token = localStorage.getItem('devpilot-token') || '';
      const response = await fetch('/api/voice/transcriptions', {
        method: 'POST',
        headers: {Authorization: `Bearer ${token}`},
        body: form,
        cache: 'no-store',
        signal: requestController.signal,
      });
      const data = await response.json().catch(() => ({}));
      if (expectedSession !== sessionEpoch || !sessionActive) return {text: '', recoverable: true};
      if (response.ok) return {text: normalize(data?.text), recoverable: false};

      if (response.status === 422) {
        return {
          text: '',
          recoverable: true,
          message: 'Não consegui entender esse trecho. Continuo ouvindo…',
        };
      }
      if (response.status === 413 || response.status === 415) {
        return {
          text: '',
          recoverable: true,
          message: errorDetail(data, 'O áudio capturado não pôde ser processado. Tentando novamente…'),
        };
      }
      return {
        text: '',
        recoverable: false,
        message: errorDetail(data, `Falha na transcrição (${response.status}).`),
      };
    } catch (error) {
      if (error?.name === 'AbortError') {
        return {
          text: '',
          recoverable: sessionActive,
          message: sessionActive
            ? 'A transcrição demorou demais. Continuo ouvindo…'
            : 'Transcrição cancelada.',
        };
      }
      return {
        text: '',
        recoverable: true,
        message: 'Falha de rede na transcrição. Vou tentar ouvir novamente…',
      };
    } finally {
      window.clearTimeout(timeoutId);
      requestController = null;
    }
  }

  async function submitRecognizedText(text, expectedSession) {
    const value = normalize(text);
    if (!value || expectedSession !== sessionEpoch || !sessionActive) return;

    const submit = window.devpilotVoiceConversationSubmit;
    if (typeof submit !== 'function') {
      stopSession('Chat interno do DevPilot indisponível. Atualize a página e tente novamente.');
      return;
    }

    transcript.value = value;
    transcript.dispatchEvent(new Event('input', {bubbles: true}));
    statusNode.textContent = 'DevPilot está pensando…';

    try {
      await submit();
    } catch (error) {
      const message = error?.message || 'Não foi possível conversar com o DevPilot.';
      statusNode.textContent = message;
      window.toast?.(message);
    } finally {
      transcript.value = '';
      transcript.dispatchEvent(new Event('input', {bubbles: true}));
    }

    if (sessionActive && expectedSession === sessionEpoch) {
      await sleep(260);
      if (sessionActive && expectedSession === sessionEpoch) void startListening(expectedSession);
    }
  }

  function startNativeRecognition(SpeechRecognition, expectedSession) {
    const cycle = ++captureEpoch;
    let completed = false;
    let captured = '';

    recognition = new SpeechRecognition();
    recognition.lang = 'pt-BR';
    recognition.interimResults = false;
    recognition.continuous = false;
    statusNode.textContent = 'Ouvindo… fale com o DevPilot.';

    recognition.onresult = event => {
      if (cycle !== captureEpoch || expectedSession !== sessionEpoch) return;
      captured = [...event.results].map(item => item?.[0]?.transcript || '').join(' ');
    };

    recognition.onerror = event => {
      if (cycle !== captureEpoch || expectedSession !== sessionEpoch || completed) return;
      completed = true;
      recognition = null;
      const code = String(event?.error || '');

      if (['network', 'service-not-allowed', 'language-not-supported'].includes(code)) {
        preferRecorder = true;
        statusNode.textContent = 'Reconhecimento do navegador indisponível. Usando captura compatível…';
        window.setTimeout(() => {
          if (sessionActive && expectedSession === sessionEpoch) void startRecorderCapture(expectedSession);
        }, 120);
        return;
      }
      if (code === 'no-speech' || code === 'aborted') {
        if (sessionActive && expectedSession === sessionEpoch) {
          statusNode.textContent = 'Não ouvi fala. Continuo ouvindo…';
          window.setTimeout(() => void startListening(expectedSession), 260);
        }
        return;
      }
      if (code === 'not-allowed') {
        stopSession('Microfone bloqueado. Libere a permissão do site e tente novamente.');
        return;
      }
      statusNode.textContent = 'Falha no reconhecimento. Tentando captura compatível…';
      preferRecorder = true;
      window.setTimeout(() => {
        if (sessionActive && expectedSession === sessionEpoch) void startRecorderCapture(expectedSession);
      }, 120);
    };

    recognition.onend = () => {
      recognition = null;
      if (completed || cycle !== captureEpoch || expectedSession !== sessionEpoch || !sessionActive) return;
      completed = true;
      const value = normalize(captured);
      if (value) {
        void submitRecognizedText(value, expectedSession);
        return;
      }
      statusNode.textContent = 'Não ouvi fala. Continuo ouvindo…';
      window.setTimeout(() => {
        if (sessionActive && expectedSession === sessionEpoch) void startListening(expectedSession);
      }, 260);
    };

    try {
      recognition.start();
    } catch (_) {
      recognition = null;
      preferRecorder = true;
      window.setTimeout(() => {
        if (sessionActive && expectedSession === sessionEpoch) void startRecorderCapture(expectedSession);
      }, 80);
    }
  }

  async function startRecorderCapture(expectedSession) {
    if (!sessionActive || expectedSession !== sessionEpoch) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      stopSession('Este navegador não oferece captura de microfone compatível.');
      return;
    }

    const cycle = ++captureEpoch;
    let speechDetected = false;
    let lastSpeechAt = 0;
    let startedAt = Date.now();
    const chunks = [];

    try {
      statusNode.textContent = 'Abrindo o microfone…';
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true},
      });
      if (!sessionActive || expectedSession !== sessionEpoch || cycle !== captureEpoch) {
        stopTracks();
        return;
      }

      const mime = supportedMimeType();
      recorder = new MediaRecorder(stream, mime ? {mimeType: mime} : undefined);
      recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
      recorder.onerror = () => {
        if (cycle !== captureEpoch) return;
        cleanupCapture();
        stopSession('Falha ao gravar o áudio.');
      };
      recorder.onstop = async () => {
        if (cycle !== captureEpoch) return;
        clearTimers();
        const type = recorder?.mimeType || mime || 'audio/webm';
        const blob = new Blob(chunks, {type});
        recorder = null;
        stopTracks();
        closeAudioContext();

        if (!sessionActive || expectedSession !== sessionEpoch) return;
        if (!speechDetected && blob.size < 64000) {
          statusNode.textContent = 'Não ouvi fala. Continuo ouvindo…';
          window.setTimeout(() => void startListening(expectedSession), 260);
          return;
        }

        statusNode.textContent = 'Transcrevendo…';
        const result = await transcribe(blob, expectedSession);
        if (!sessionActive || expectedSession !== sessionEpoch) return;
        if (result.text) {
          await submitRecognizedText(result.text, expectedSession);
          return;
        }
        if (result.recoverable) {
          statusNode.textContent = result.message || 'Não ouvi fala. Continuo ouvindo…';
          window.setTimeout(() => void startListening(expectedSession), 320);
          return;
        }
        stopSession(result.message || 'A transcrição não está disponível agora.');
      };

      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        try {
          audioContext = new AudioContext();
          const source = audioContext.createMediaStreamSource(stream);
          const analyser = audioContext.createAnalyser();
          analyser.fftSize = 512;
          source.connect(analyser);
          const samples = new Uint8Array(analyser.fftSize);
          analyserTimer = window.setInterval(() => {
            if (recorder?.state !== 'recording') return;
            analyser.getByteTimeDomainData(samples);
            let peak = 0;
            for (const sample of samples) peak = Math.max(peak, Math.abs(sample - 128));
            const now = Date.now();
            if (peak >= 10) {
              speechDetected = true;
              lastSpeechAt = now;
            }
            if (speechDetected && now - lastSpeechAt > 900 && now - startedAt > 900) {
              try { recorder.stop(); } catch (_) {}
            }
          }, 100);
        } catch (_) {
          closeAudioContext();
        }
      }

      recorder.start(250);
      startedAt = Date.now();
      statusNode.textContent = 'Ouvindo… fale com o DevPilot.';
      hardStopTimer = window.setTimeout(() => {
        if (recorder?.state === 'recording' && cycle === captureEpoch) {
          try { recorder.stop(); } catch (_) {}
        }
      }, 8000);
    } catch (error) {
      cleanupCapture();
      if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') {
        stopSession('Microfone bloqueado. Libere a permissão do site e tente novamente.');
        return;
      }
      stopSession('Não foi possível abrir o microfone.');
    }
  }

  function startListening(expectedSession = sessionEpoch) {
    if (!sessionActive || expectedSession !== sessionEpoch) return;
    cleanupCapture();
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!preferRecorder && SpeechRecognition) {
      startNativeRecognition(SpeechRecognition, expectedSession);
      return;
    }
    void startRecorderCapture(expectedSession);
  }

  function startSession() {
    if (sessionActive) return;
    sessionActive = true;
    sessionEpoch += 1;
    setSessionUi(true);
    statusNode.textContent = 'Ligando o microfone…';
    startListening(sessionEpoch);
  }

  // Este módulo é carregado por último. Ele neutraliza somente os handlers de
  // captura concorrentes; a estrutura visual e o chat canônico permanecem os mesmos.
  startButton.addEventListener('click', event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (sessionActive) stopSession();
    else startSession();
  }, true);

  stopButton?.addEventListener('click', event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    stopSession();
  }, true);

  modal.addEventListener('close', () => {
    sessionActive = false;
    sessionEpoch += 1;
    captureEpoch += 1;
    cleanupCapture({abortRequest: true});
    setSessionUi(false);
  });
})();
