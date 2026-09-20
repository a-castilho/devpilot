/* Compatibility shim: final delivery recovery is owned by the backend reconciler. */
(() => {
  'use strict';
  if (window.__devpilotDeliveryBlockedRecoveryReady) return;
  window.__devpilotDeliveryBlockedRecoveryReady = true;

  // Intentionally no browser-side mutation and no provider retry timer here.
  // stable-delivery-url.js observes persisted state; delivery-gate.js performs
  // only the initial handoff to /delivery/auto.
})();
