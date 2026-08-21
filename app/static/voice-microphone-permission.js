(() => {
  const startButton = document.querySelector('#voice-start');
  const statusNode = document.querySelector('#voice-status');

  if (!startButton || !statusNode || startButton.dataset.permissionGuard === '1') return;

  const originalStart = startButton.onclick;
  if (typeof originalStart !== 'function') return;

  startButton.dataset.permissionGuard = '1';

  const isLocalSecureOrigin = () =>
    window.isSecureContext || ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);

  const stopProbeStream = (stream) => {
    try {
      stream?.getTracks?.().forEach((track) => track.stop());
    } catch (_) {
      // Best effort only: this stream exists just to trigger/check permission.
    }
  };

  const permissionMessage = (error) => {
    if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') {
      return 'Permissão de microfone negada. Clique no ícone de permissões ao lado do endereço, permita Microfone e toque em Iniciar novamente.';
    }
    if (error?.name === 'NotFoundError' || error?.name === 'DevicesNotFoundError') {
      return 'Nenhum microfone foi encontrado neste computador.';
    }
    if (error?.name === 'NotReadableError' || error?.name === 'TrackStartError') {
      return 'O microfone está ocupado ou indisponível para o navegador.';
    }
    return 'Não foi possível solicitar acesso ao microfone.';
  };

  async function requestMicrophonePermission() {
    if (!navigator.mediaDevices?.getUserMedia) return true;

    statusNode.textContent = 'Solicitando permissão para usar o microfone…';

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stopProbeStream(stream);
      statusNode.textContent = 'Microfone permitido. Iniciando reconhecimento…';
      return true;
    } catch (error) {
      statusNode.textContent = permissionMessage(error);
      if (typeof toast === 'function') toast(statusNode.textContent);
      return false;
    }
  }

  startButton.onclick = async function guardedVoiceStart(event) {
    // While recording, the original handler must stop immediately; requesting
    // permission again here would delay the stop action.
    if (/parar/i.test(startButton.textContent || '')) {
      return originalStart.call(startButton, event);
    }

    // LAN HTTP cannot use getUserMedia reliably; preserve the existing mobile
    // file-capture fallback implemented by voice-local-update.js.
    if (!isLocalSecureOrigin()) {
      return originalStart.call(startButton, event);
    }

    const allowed = await requestMicrophonePermission();
    if (!allowed) return;

    return originalStart.call(startButton, event);
  };
})();
