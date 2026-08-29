(() => {
  'use strict';

  if (window.__devpilotInsecureLanRecorderFallbackReady) return;
  window.__devpilotInsecureLanRecorderFallbackReady = true;

  const startButton = document.querySelector('#voice-start');
  const statusNode = document.querySelector('#voice-status');
  const modal = document.querySelector('#voice-modal');
  const transcriptInput = document.querySelector('#voice-transcript');

  if (!startButton || !statusNode || !modal || !transcriptInput) return;

  const isLoopback = () => ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
  const isMobile = () => {
    if (navigator.userAgentData?.mobile === true) return true;
    const userAgent = String(navigator.userAgent || '');
    if (/Android|iPhone|iPad|iPod|IEMobile|Opera Mini|Mobile/i.test(userAgent)) return true;
    return /Macintosh/i.test(userAgent) && Number(navigator.maxTouchPoints || 0) > 1;
  };
  const mustUseRecorderFallback = () => !window.isSecureContext && !isLoopback() && isMobile();

  if (!mustUseRecorderFallback()) return;

  const audioInput = document.createElement('input');
  audioInput.type = 'file';
  audioInput.accept = 'audio/*,.webm,.ogg,.m4a,.mp4,.mp3,.wav,.aac,.3gp,.3g2';
  audioInput.setAttribute('capture', '');
  audioInput.hidden = true;
  audioInput.tabIndex = -1;
  audioInput.setAttribute('aria-hidden', 'true');
  modal.appendChild(audioInput);

  const normalizeAudioType = (file) => {
    const raw = String(file?.type || '').split(';', 1)[0].toLowerCase();
    const aliases = {
      'audio/x-m4a': 'audio/mp4',
      'audio/m4a': 'audio/mp4',
      'audio/x-wav': 'audio/wav',
      'video/3gpp': 'audio/3gpp',
      'video/3gpp2': 'audio/3gpp2',
      'application/octet-stream': '',
    };
    const normalized = Object.prototype.hasOwnProperty.call(aliases, raw) ? aliases[raw] : raw;
    if (normalized.startsWith('audio/')) return normalized;

    const extension = String(file?.name || '').split('.').pop()?.toLowerCase();
    return {
      webm: 'audio/webm', ogg: 'audio/ogg', oga: 'audio/ogg', m4a: 'audio/mp4', mp4: 'audio/mp4',
      mp3: 'audio/mpeg', wav: 'audio/wav', aac: 'audio/aac', '3gp': 'audio/3gpp', '3g2': 'audio/3gpp2',
    }[extension] || 'audio/webm';
  };

  async function transcribe(file) {
    if (!file) return;

    startButton.disabled = true;
    statusNode.textContent = 'Áudio recebido. Transcrevendo…';

    const mime = normalizeAudioType(file);
    const upload = String(file.type || '').split(';', 1)[0].toLowerCase() === mime
      ? file
      : new Blob([file], {type: mime});
    const form = new FormData();
    form.append('audio', upload, file.name || 'voice.webm');

    try {
      const data = await api('/voice/transcriptions', {method: 'POST', body: form});
      const text = String(data?.text || '').trim();
      transcriptInput.value = text;
      transcriptInput.dispatchEvent(new Event('input', {bubbles: true}));
      statusNode.textContent = text
        ? 'Transcrição pronta. Revise e envie para o DevPilot.'
        : 'Nenhuma fala foi reconhecida. Tente novamente.';
    } catch (error) {
      statusNode.textContent = error?.message || 'Falha ao transcrever o áudio.';
      window.toast?.(statusNode.textContent);
    } finally {
      startButton.disabled = false;
      audioInput.value = '';
    }
  }

  audioInput.addEventListener('change', () => void transcribe(audioInput.files?.[0]));

  startButton.addEventListener('click', (event) => {
    if (!mustUseRecorderFallback()) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    statusNode.textContent = 'Abrindo o gravador do celular… fale e confirme a gravação.';
    audioInput.value = '';
    audioInput.click();
  }, true);

  startButton.dataset.captureMode = 'system-recorder';
  startButton.setAttribute('title', 'Gravar voz no celular');
  startButton.setAttribute('aria-label', 'Gravar voz no celular');
  statusNode.textContent = 'Microfone móvel pronto. Toque no botão para gravar sua mensagem.';
})();
