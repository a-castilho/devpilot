/* Delivery resilience for Build Game.
 *
 * Delivery mutations can legitimately outlive the compact mobile HTTP timeout while
 * cloud providers and the autonomous repair worker continue in the background.
 * A browser timeout must therefore never overwrite the authoritative server state.
 */
(() => {
  'use strict';

  const originalApi = window.api;
  if (typeof originalApi !== 'function' || window.__devpilotDeliveryResilienceInstalled) return;

  window.__devpilotDeliveryResilienceInstalled = true;
  window.__devpilotDeliveryState = window.__devpilotDeliveryState || null;

  const DELIVERY_MUTATION = /^\/projects\/([^/]+)\/delivery\/(start|retry|auto|validate-url)$/;
  const DELIVERY_READ = /^\/projects\/([^/]+)\/delivery$/;
  const LONG_DELIVERY_TIMEOUT_MS = 60_000;
  const RECOVERY_READ_TIMEOUT_MS = 8_000;

  const remember = (path, value) => {
    if ((DELIVERY_MUTATION.test(path) || DELIVERY_READ.test(path)) && value && typeof value === 'object') {
      window.__devpilotDeliveryState = value;
      window.dispatchEvent(new CustomEvent('devpilot:delivery-state', {detail: value}));
    }
    return value;
  };

  const timeoutLike = error => {
    const message = String(error?.message || error || '').toLowerCase();
    return message.includes('demorou demais') || message.includes('timeout') || message.includes('aborted');
  };

  window.api = async function resilientApi(path, options = {}) {
    const rawPath = String(path || '');
    const mutation = rawPath.match(DELIVERY_MUTATION);
    const method = String(options?.method || 'GET').toUpperCase();

    if (!mutation || method !== 'POST') {
      return remember(rawPath, await originalApi(rawPath, options));
    }

    const projectId = mutation[1];
    const requestOptions = {
      ...options,
      timeoutMs: Math.max(Number(options?.timeoutMs || 0), LONG_DELIVERY_TIMEOUT_MS),
    };

    try {
      return remember(rawPath, await originalApi(rawPath, requestOptions));
    } catch (error) {
      if (!timeoutLike(error)) throw error;

      // The POST may still be running on the server. Read the persisted state instead
      // of presenting a false publication failure to the user.
      try {
        const current = await originalApi(`/projects/${encodeURIComponent(projectId)}/delivery`, {
          timeoutMs: RECOVERY_READ_TIMEOUT_MS,
          retry: true,
        });
        if (current && typeof current === 'object') {
          current.client_request_recovered = true;
          current.client_request_message = 'A operação continua no servidor; o estado foi recuperado após o tempo limite do navegador.';
          return remember(`/projects/${projectId}/delivery`, current);
        }
      } catch (_) {
        // Preserve the original timeout only when the authoritative state also cannot
        // be consulted.
      }
      throw error;
    }
  };

  const statusCopy = delivery => {
    const status = String(delivery?.status || '').toLowerCase();
    const gate = String(delivery?.delivery_gate || '').toLowerCase();
    const repairStatus = String(delivery?.repair_task_status || '').toLowerCase();
    const stall = delivery?.stall_recovery && typeof delivery.stall_recovery === 'object'
      ? delivery.stall_recovery
      : null;

    if (gate === 'repair_exhausted') {
      return {
        title: 'Autocorreção esgotada',
        badge: 'DIAGNÓSTICO NECESSÁRIO',
        message: delivery?.last_error || 'As tentativas automáticas seguras foram esgotadas. O projeto não será mostrado como publicando indefinidamente.',
        disable: false,
        button: '↻ Tentar nova correção',
      };
    }

    if (status === 'repairing' || gate === 'repairing_product') {
      const suffix = repairStatus ? ` · ${repairStatus}` : '';
      const stallMessage = stall?.status === 'requeued'
        ? ' A fila ficou parada e o DevPilot a reativou automaticamente.'
        : '';
      return {
        title: `Corrigindo produto final${suffix}`,
        badge: 'AUTOCORREÇÃO ATIVA',
        message: `O DevPilot está materializando o produto real no branch de entrega antes de publicar a URL.${stallMessage}`,
        disable: true,
        button: 'Autocorreção em andamento…',
      };
    }

    if (delivery?.client_request_recovered) {
      return {
        title: 'Operação continua no servidor',
        badge: 'ESTADO RECUPERADO',
        message: delivery.client_request_message,
        disable: status === 'deploying' || status === 'provisioning',
        button: 'Verificar andamento',
      };
    }

    return null;
  };

  const reconcileUi = () => {
    const delivery = window.__devpilotDeliveryState;
    if (!delivery) return;
    const copy = statusCopy(delivery);
    if (!copy) return;

    const panel = document.querySelector('#build-game-view .build-game-victory');
    const host = panel?.querySelector('.build-game-url-bonus');
    if (!host) return;

    const title = host.querySelector('.build-game-url-bonus-head strong');
    const badge = host.querySelector('.build-game-url-bonus-state');
    const paragraph = host.querySelector('p');
    const button = host.querySelector('[data-game-url-action]');
    const error = host.querySelector('.build-game-url-error');

    if (title) title.textContent = copy.title;
    if (badge) badge.textContent = copy.badge;
    if (paragraph) paragraph.textContent = copy.message;
    if (error && String(delivery.status || '').toLowerCase() === 'repairing') error.remove();
    if (button) {
      button.disabled = Boolean(copy.disable);
      button.textContent = copy.button;
      if (String(delivery.delivery_gate || '').toLowerCase() === 'repair_exhausted') {
        button.dataset.gameUrlAction = 'retry';
      } else if (copy.disable) {
        button.dataset.gameUrlAction = 'validate-url';
      }
    }
  };

  window.addEventListener('devpilot:delivery-state', () => queueMicrotask(reconcileUi));
  const root = document.querySelector('#build-game-view') || document.body;
  new MutationObserver(reconcileUi).observe(root, {childList: true, subtree: true, characterData: true});
  window.setInterval(reconcileUi, 1500);
})();
