/* DevPilot final delivery auto-progress — keep the idempotent backend delivery state machine moving until a real URL is ready. */
(() => {
  'use strict';
  if (window.__devpilotDeliveryAutoProgressReady) return;
  window.__devpilotDeliveryAutoProgressReady = true;

  const ACTIVE_MS = 7000;
  const PASSIVE_MS = 15000;
  const inFlight = new Set();
  const timers = new Map();
  const terminal = new Set(['ready']);

  const controller = () => window.__devpilotGameControllerV73;
  const normalized = value => String(value || 'pending').toLowerCase();
  const safeUrl = value => /^https:\/\//i.test(String(value || '').trim());
  const delivered = state => normalized(state?.status) === 'ready' && safeUrl(state?.url);
  const endpoint = projectId => `/projects/${encodeURIComponent(projectId)}/delivery`;

  function clear(projectId) {
    const timer = timers.get(projectId);
    if (timer) window.clearTimeout(timer);
    timers.delete(projectId);
  }

  function schedule(projectId, delay = ACTIVE_MS) {
    clear(projectId);
    timers.set(projectId, window.setTimeout(() => {
      timers.delete(projectId);
      void advance(projectId);
    }, delay));
  }

  async function advance(projectId) {
    if (!projectId || inFlight.has(projectId) || typeof window.api !== 'function') return;
    inFlight.add(projectId);
    try {
      let state = await window.api(endpoint(projectId));
      if (delivered(state)) {
        clear(projectId);
        document.dispatchEvent(new CustomEvent('devpilot:game:delivery-ready', {detail: {projectId, delivery: state}}));
        document.dispatchEvent(new CustomEvent('devpilot:game:state'));
        return;
      }

      // /auto is intentionally idempotent and authenticated with normal project access.
      // Unlike the UI-only validator, it continues provisioning Render/Vercel after an
      // intermediate provider becomes ready, so "deploying" cannot stall forever.
      state = await window.api(`${endpoint(projectId)}/auto`, {method: 'POST'});
      if (delivered(state)) {
        clear(projectId);
        document.dispatchEvent(new CustomEvent('devpilot:game:delivery-ready', {detail: {projectId, delivery: state}}));
        document.dispatchEvent(new CustomEvent('devpilot:game:state'));
        return;
      }

      document.dispatchEvent(new CustomEvent('devpilot:game:delivery-progress', {detail: {projectId, delivery: state}}));
      schedule(projectId, terminal.has(normalized(state?.status)) ? PASSIVE_MS : ACTIVE_MS);
    } catch (error) {
      console.warn('[DevPilot delivery auto-progress]', error);
      schedule(projectId, PASSIVE_MS);
    } finally {
      inFlight.delete(projectId);
    }
  }

  function sync() {
    const snapshot = controller()?.snapshot?.();
    if (!snapshot?.done || !snapshot.projectId) return;
    const projectId = String(snapshot.projectId);
    if (!timers.has(projectId) && !inFlight.has(projectId)) void advance(projectId);
  }

  document.addEventListener('devpilot:game:state', sync);
  document.addEventListener('devpilot:game:rendered', sync);
  document.addEventListener('devpilot:game:core-ready', sync);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) sync(); });
  sync();
})();
