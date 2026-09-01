(() => {
  'use strict';

  if (window.__devpilotProjectsMutationGuard) return;
  window.__devpilotProjectsMutationGuard = true;

  const NativeMutationObserver = window.MutationObserver;
  if (typeof NativeMutationObserver !== 'function') return;

  const INTERNAL_SELECTOR = '.product-delivery-box, #projects-new-project-sticky';

  function mutationIsInternal(record) {
    const target = record?.target;
    const element = target instanceof Element ? target : target?.parentElement;
    return Boolean(element?.closest?.(INTERNAL_SELECTOR));
  }

  class ProjectsSafeMutationObserver extends NativeMutationObserver {
    constructor(callback) {
      super((records, observer) => {
        const relevant = Array.from(records || []).filter(record => !mutationIsInternal(record));
        if (relevant.length) callback(relevant, observer);
      });
    }
  }

  window.MutationObserver = ProjectsSafeMutationObserver;

  // product-delivery-ui cria seu observer de forma síncrona durante o carregamento.
  // Restauramos a implementação nativa logo depois para não afetar outros módulos.
  window.setTimeout(() => {
    if (window.MutationObserver === ProjectsSafeMutationObserver) {
      window.MutationObserver = NativeMutationObserver;
    }
  }, 1500);
})();
