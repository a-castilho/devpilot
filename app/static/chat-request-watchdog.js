(() => {
  'use strict';

  if (window.__devpilotChatRequestWatchdogReady) return;
  window.__devpilotChatRequestWatchdogReady = true;

  const nativeFetch = window.fetch.bind(window);
  const CHAT_REQUEST_TIMEOUT_MS = 45000;

  const requestPath = input => {
    try {
      const raw = typeof input === 'string' || input instanceof URL ? input : input?.url;
      return new URL(raw, window.location.href).pathname;
    } catch (_) {
      return '';
    }
  };

  window.fetch = function devpilotBoundedFetch(input, init = {}) {
    if (requestPath(input) !== '/api/chat') return nativeFetch(input, init);

    const controller = new AbortController();
    const upstreamSignal = init?.signal;
    let timedOut = false;
    let detachUpstream = null;

    if (upstreamSignal) {
      const relayAbort = () => {
        try { controller.abort(upstreamSignal.reason); }
        catch (_) { controller.abort(); }
      };
      if (upstreamSignal.aborted) relayAbort();
      else {
        upstreamSignal.addEventListener('abort', relayAbort, {once: true});
        detachUpstream = () => upstreamSignal.removeEventListener('abort', relayAbort);
      }
    }

    const timeoutId = window.setTimeout(() => {
      timedOut = true;
      try { controller.abort(new DOMException('Chat timeout', 'TimeoutError')); }
      catch (_) { controller.abort(); }
    }, CHAT_REQUEST_TIMEOUT_MS);

    return nativeFetch(input, {...init, signal: controller.signal})
      .catch(error => {
        if (!timedOut) throw error;
        const timeoutError = new Error(
          'O chat demorou mais de 45 segundos. A tentativa foi interrompida para não deixar a tela travada.'
        );
        timeoutError.name = 'TimeoutError';
        throw timeoutError;
      })
      .finally(() => {
        window.clearTimeout(timeoutId);
        detachUpstream?.();
      });
  };
})();
