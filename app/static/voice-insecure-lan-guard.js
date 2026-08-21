(() => {
  const startButton = document.querySelector('#voice-start');
  const statusNode = document.querySelector('#voice-status');

  if (!startButton || !statusNode || startButton.dataset.insecureLanGuard === '1') return;

  const originalStart = startButton.onclick;
  if (typeof originalStart !== 'function') return;

  startButton.dataset.insecureLanGuard = '1';

  const isLoopback = () => ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
  const isInsecureLan = () => !window.isSecureContext && !isLoopback();

  const isLikelyMobileDevice = () => {
    if (navigator.userAgentData?.mobile === true) return true;

    const userAgent = String(navigator.userAgent || '');
    if (/Android|iPhone|iPad|iPod|IEMobile|Opera Mini|Mobile/i.test(userAgent)) return true;

    // iPadOS can identify itself as Macintosh while still exposing touch points.
    return /Macintosh/i.test(userAgent) && Number(navigator.maxTouchPoints || 0) > 1;
  };

  const desktopMessage =
    'O navegador bloqueia o microfone neste endereço HTTP. Abra o DevPilot por HTTPS para usar a conversa por voz.';

  const applyDesktopState = () => {
    statusNode.textContent = desktopMessage;
    startButton.setAttribute('title', 'Microfone direto exige HTTPS neste endereço');
    startButton.setAttribute(
      'aria-label',
      'Microfone indisponível em HTTP; abra o DevPilot por HTTPS',
    );
    startButton.dataset.captureUnavailable = 'insecure-http';
  };

  if (isInsecureLan() && !isLikelyMobileDevice()) {
    applyDesktopState();
  }

  startButton.onclick = function guardedInsecureLanVoiceStart(event) {
    if (!isInsecureLan() || isLikelyMobileDevice()) {
      return originalStart.call(startButton, event);
    }

    event?.preventDefault?.();
    event?.stopPropagation?.();
    applyDesktopState();

    if (typeof toast === 'function') {
      toast('Microfone direto exige HTTPS neste endereço.');
    }
  };
})();
