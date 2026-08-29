(() => {
  'use strict';

  if (window.__devpilotVoiceProjectAutoloadReady) return;
  window.__devpilotVoiceProjectAutoloadReady = true;

  const modal = document.querySelector('#voice-modal');
  const select = modal?.querySelector('#voice-project');
  if (!modal || !select) return;

  let loading = null;
  const ensureProjects = async () => {
    try {
      if (typeof state !== 'undefined' && Array.isArray(state.projects) && state.projects.length) return state.projects;
      if (loading) return loading;
      if (typeof loadProjects !== 'function') return [];
      loading = Promise.resolve(loadProjects()).finally(() => { loading = null; });
      return await loading;
    } catch (error) {
      window.toast?.(error?.message || 'Não foi possível carregar os projetos.');
      return [];
    }
  };

  const refreshOnOpen = () => {
    if (modal.open) void ensureProjects();
  };

  new MutationObserver(refreshOnOpen).observe(modal, {attributes: true, attributeFilter: ['open']});

  modal.addEventListener('click', event => {
    if (event.target?.closest?.('.voice-chatgpt-options-button, .mobile-chat-project-trigger, .voice-project-control')) {
      void ensureProjects();
    }
  }, true);

  if (modal.open) void ensureProjects();
})();