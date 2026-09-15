/* Final delivery must not remain permanently blocked after the game reaches 100%. */
(() => {
  'use strict';
  if (window.__devpilotDeliveryBlockedRecoveryReady) return;
  window.__devpilotDeliveryBlockedRecoveryReady = true;

  const RETRY_DELAY_MS = 1200;
  const attempted = new Set();
  let leaving = false;
  let timer = 0;

  const controller = () => window.__devpilotGameControllerV73;
  const endpoint = projectId => `/projects/${encodeURIComponent(projectId)}/delivery`;

  const stop = () => {
    leaving = true;
    if (timer) window.clearTimeout(timer);
    timer = 0;
  };

  async function recover(projectId) {
    if (leaving || !projectId || attempted.has(projectId)) return;
    attempted.add(projectId);
    try {
      if (typeof window.__devpilotEnsureAutomaticDelivery === 'function') {
        await window.__devpilotEnsureAutomaticDelivery(projectId);
      } else if (typeof window.api === 'function') {
        await window.api(`${endpoint(projectId)}/retry`, {method: 'POST', timeoutMs: 8000, retry: false});
      }
    } catch (error) {
      console.warn('[DevPilot Delivery Recovery]', error);
    } finally {
      if (!leaving) document.dispatchEvent(new CustomEvent('devpilot:game:rendered'));
    }
  }

  async function inspect() {
    if (leaving || document.hidden) return;
    const state = controller()?.snapshot?.();
    if (!state?.done || !state.projectId || typeof window.api !== 'function') return;
    const projectId = String(state.projectId);
    try {
      const delivery = await window.api(endpoint(projectId), {timeoutMs: 5000, retry: false});
      const status = String(delivery?.status || '').toLowerCase();
      if (status === 'blocked' || status === 'failed') {
        timer = window.setTimeout(() => void recover(projectId), RETRY_DELAY_MS);
      }
    } catch (error) {
      console.warn('[DevPilot Delivery Inspect]', error);
    }
  }

  document.addEventListener('devpilot:game:leaving', stop, {once: true});
  document.addEventListener('devpilot:game:core-ready', () => void inspect());
  document.addEventListener('devpilot:game:rendered', () => void inspect());
  document.addEventListener('visibilitychange', () => { if (!document.hidden) void inspect(); });
  void inspect();
})();
