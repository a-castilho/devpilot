/* Compatibility shim: final delivery start/recovery is owned by the backend reconciler. */
(() => {
  'use strict';
  if (window.__devpilotDeliveryBlockedRecoveryReady) return;
  window.__devpilotDeliveryBlockedRecoveryReady = true;

  // Intentionally no browser-side mutation and no provider retry timer here.
  // stable-delivery-url.js observes persisted state; the backend detects Gate 7/7,
  // starts delivery, applies the shared lease/backoff and validates the final URL.
})();
