(() => {
  'use strict';

  if (window.__devpilotMobileVoiceCaptureFinalReady) return;
  window.__devpilotMobileVoiceCaptureFinalReady = true;

  const isMobile = () => {
    if (navigator.userAgentData?.mobile === true) return true;
    const ua = String(navigator.userAgent || '');
    return /Android|iPhone|iPad|iPod|IEMobile|Opera Mini|Mobile/i.test(ua)
      || (/Macintosh/i.test(ua) && Number(navigator.maxTouchPoints || 0) > 1);
  };
  if (!isMobile()) return;

  const modal = document.querySelector('#voice-modal');
  const button = modal?.querySelector('#voice-start');
  const status = modal?.querySelector('#voice-status');
  const transcript = modal?.querySelector('#voice-transcript');
  if (!modal || !button || !status || !transcript) return;

  let recorder = null;
  let stream = null;
  let chunks = [];
  let timer = null;
  let busy = false;

  const cleanup = () => {
    if (timer) window.clearTimeout(timer);
    timer = null;
    try { stream?.getTracks?.().forEach(track => track.stop()); } catch (_) {}
    stream = null;
    recorder = null;
    chunks = [];
    button.removeAttribute('aria-pressed');
  };

  const submitText = async (text) => {
    const value = String(text || '').trim();
    if (!value) throw new Error('Nenhuma fala foi reconhecida.');
    transcript.value = value;
    transcript.dispatchEvent(new Event('input', {bubbles: true}));
    if (typeof window.devpilotVoiceConversationSubmit === 'function') {
      await window.devpilotVoiceConversationSubmit();
      transcript.value = '';
      transcript.dispatchEvent(new Event('input', {bubbles: true}));
    }
  };

  const transcribe = async (blob, filename = 'voice.webm') => {
    if (!blob?.size) throw new Error('Nenhum áudio foi capturado.');
    const form = new FormData();
    form.append('audio', blob, filename);
    const data = await api('/voice/transcriptions', {method: 'POST', body: form});
    await submitText(data?.text);
  };

  const stopSecureRecording = () => {
    if (recorder?.state === 'recording') recorder.stop();
  };

  const startSecureRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      throw new Error('Este navegador não oferece captura de microfone compatível.');
    }
    status.textContent = 'Solicitando acesso ao microfone…';
    stream = await navigator.mediaDevices.getUserMedia({audio: true});
    const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
      .find(type => MediaRecorder.isTypeSupported?.(type)) || '';
    chunks = [];
    recorder = new MediaRecorder(stream, mime ? {mimeType: mime} : undefined);
    recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
    recorder.onerror = () => {
      cleanup();
      busy = false;
      status.textContent = 'Falha ao gravar o áudio.';
    };
    recorder.onstop = async () => {
      const type = recorder?.mimeType || mime || 'audio/webm';
      const blob = new Blob(chunks, {type});
      cleanup();
      try {
        status.textContent = 'Transcrevendo…';
        await transcribe(blob, type.includes('ogg') ? 'voice.ogg' : 'voice.webm');
        status.textContent = 'Pronto. Toque no microfone para falar novamente.';
      } catch (error) {
        status.textContent = error?.message || 'Falha na transcrição do áudio.';
        window.toast?.(status.textContent);
      } finally {
        busy = false;
      }
    };
    recorder.start(250);
    button.setAttribute('aria-pressed', 'true');
    status.textContent = 'Ouvindo… toque novamente para parar.';
    timer = window.setTimeout(stopSecureRecording, 8000);
  };

  const openSystemRecorder = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'audio/*,.webm,.ogg,.m4a,.mp4,.mp3,.wav,.aac,.3gp,.3g2';
    input.setAttribute('capture', '');
    input.hidden = true;
    modal.appendChild(input);
    input.addEventListener('change', async () => {
      const file = input.files?.[0];
      if (!file) {
        busy = false;
        input.remove();
        return;
      }
      try {
        status.textContent = 'Transcrevendo…';
        await transcribe(file, file.name || 'voice.webm');
        status.textContent = 'Pronto. Toque no microfone para falar novamente.';
      } catch (error) {
        status.textContent = error?.message || 'Falha na transcrição do áudio.';
        window.toast?.(status.textContent);
      } finally {
        busy = false;
        input.remove();
      }
    }, {once: true});
    status.textContent = 'Abrindo o gravador do celular…';
    input.click();
  };

  button.addEventListener('click', async event => {
    event.preventDefault();
    event.stopImmediatePropagation();

    if (recorder?.state === 'recording') {
      stopSecureRecording();
      return;
    }
    if (busy) return;
    busy = true;

    try {
      if (window.isSecureContext) {
        await startSecureRecording();
      } else {
        openSystemRecorder();
      }
    } catch (error) {
      cleanup();
      busy = false;
      const denied = error?.name === 'NotAllowedError' || error?.name === 'SecurityError';
      status.textContent = denied
        ? 'Microfone bloqueado pelo navegador. Libere a permissão do site e tente novamente.'
        : (error?.message || 'Não foi possível abrir o microfone.');
      window.toast?.(status.textContent);
    }
  }, true);

  modal.addEventListener('close', () => {
    try { if (recorder?.state === 'recording') recorder.stop(); } catch (_) {}
    cleanup();
    busy = false;
  });

  button.dataset.captureMode = window.isSecureContext ? 'mobile-get-user-media' : 'system-recorder';
  button.setAttribute('title', 'Gravar voz no celular');
  button.setAttribute('aria-label', 'Gravar voz no celular');
})();