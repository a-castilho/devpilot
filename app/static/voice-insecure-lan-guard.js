(() => {
  const startButton = document.querySelector('#voice-start');
  const statusNode = document.querySelector('#voice-status');
  const modal = document.querySelector('#voice-modal');

  if (!startButton || !statusNode || !modal || startButton.dataset.insecureLanGuard === '2') return;

  const originalStart = startButton.onclick;
  if (typeof originalStart !== 'function') return;

  startButton.dataset.insecureLanGuard = '2';

  const isLoopback = () => ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
  const isInsecureLan = () => !window.isSecureContext && !isLoopback();

  const isLikelyMobileDevice = () => {
    if (navigator.userAgentData?.mobile === true) return true;

    const userAgent = String(navigator.userAgent || '');
    if (/Android|iPhone|iPad|iPod|IEMobile|Opera Mini|Mobile/i.test(userAgent)) return true;

    // iPadOS can identify itself as Macintosh while still exposing touch points.
    return /Macintosh/i.test(userAgent) && Number(navigator.maxTouchPoints || 0) > 1;
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
      'Este endereço HTTP da rede não libera o microfone direto. Use Gravar no modo compatível ou abra o acesso local para liberar o microfone.';
    startButton.setAttribute('title', 'Usar captura compatível neste endereço HTTP');
    startButton.setAttribute(
      'aria-label',
      'Usar captura compatível; para microfone direto, abra o acesso local',
    );
    startButton.dataset.captureMode = 'insecure-lan-fallback';
    delete startButton.dataset.captureUnavailable;
    ensureLocalMicrophoneButton();
  };

  if (isInsecureLan() && !isLikelyMobileDevice()) {
    applyDesktopState();
  }

  startButton.onclick = function guardedInsecureLanVoiceStart(event) {
    if (isInsecureLan() && !isLikelyMobileDevice()) {
      applyDesktopState();
      if (typeof toast === 'function') {
        toast('Usando modo compatível. Para microfone direto, abra o acesso local.');
      }
    }

    // Nunca bloqueie o manipulador original: em HTTP de rede ele contém o
    // fallback de gravação/arquivo; em origem segura ele usa o microfone direto.
    return originalStart.call(startButton, event);
  };
})();
