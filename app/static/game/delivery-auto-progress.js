/* DevPilot delivery auto-progress compatibility stub.
 * Final delivery is owned by the backend worker. This asset intentionally performs no POSTs.
 */
(() => {
  'use strict';
  if (window.__devpilotDeliveryAutoProgressReady) return;
  window.__devpilotDeliveryAutoProgressReady = true;
  document.dispatchEvent(new CustomEvent('devpilot:delivery:observer-ready'));
})();
