(() => {
  'use strict';

  if (window.__devpilotVoiceProjectAutoloadReady) return;
  window.__devpilotVoiceProjectAutoloadReady = true;

  const modal = document.querySelector('#voice-modal');
  const select = modal?.querySelector('#voice-project');
  if (!modal || !select) return;

  const ACTIVE_PROJECT_STORAGE_KEY = 'devpilot-chat-active-project-id';
  const normalizeProjectId = value => String(value ?? '').trim();

  const ensureGeneralOption = () => {
    if ([...select.options].some(option => normalizeProjectId(option.value) === '')) return;
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'Geral — sem projeto específico';
    select.prepend(option);
  };

  const syncActiveProjectSelection = () => {
    ensureGeneralOption();
    const stored = normalizeProjectId(localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY));
    if (stored) {
      const option = [...select.options].find(item => normalizeProjectId(item.value) === stored);
      if (option) select.value = option.value;
    }
    document.dispatchEvent(new CustomEvent('devpilot:active-project-changed', {
      detail: {
        project_id: normalizeProjectId(select.value) || null,
        source: 'voice-project-options-ready',
      },
    }));
  };

  let loading = null;
  const ensureProjects = async () => {
    try {
      if (typeof state !== 'undefined' && Array.isArray(state.projects) && state.projects.length) {
        if (![...select.options].some(option => normalizeProjectId(option.value)) && typeof fillProjects === 'function') {
          fillProjects();
        }
        syncActiveProjectSelection();
        return state.projects;
      }
      if (loading) return loading;
      if (typeof loadProjects !== 'function') return [];
      loading = Promise.resolve(loadProjects())
        .then(projects => {
          syncActiveProjectSelection();
          return projects;
        })
        .finally(() => { loading = null; });
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