(() => {
  'use strict';

  // Os efeitos visuais das naves de projeto ficam desativados por estabilidade.
  // O módulo não registra MutationObserver, animações, timers ou handlers de clique.
  // A navegação, análise, testes e criação de tarefas continuam sob responsabilidade
  // do app.js e dos módulos funcionais correspondentes.
  window.__devpilotProjectShipsDisabled = true;

  const cleanup = () => {
    document.getElementById('devpilot-project-ships-style')?.remove();
    document.querySelectorAll('.project-visual-overview').forEach(node => node.remove());
    document.querySelectorAll('#projects-list .project-ship-hangar').forEach(node => node.remove());

    document.querySelectorAll('#projects-list .project-card').forEach(card => {
      card.classList.remove('project-ship-card');
      card.removeAttribute('data-ship-enhanced');
      card.removeAttribute('data-ship-energy');
      card.removeAttribute('data-ship-shield');
      card.removeAttribute('data-ship-readiness');
      card.removeAttribute('data-ship-pending');
      card.style.removeProperty('--ship-accent');
      card.style.removeProperty('--ship-accent-2');

      card.querySelectorAll('.project-status-strip').forEach(node => node.remove());
      card.querySelectorAll('.project-verbose-copy').forEach(node => node.classList.remove('project-verbose-copy'));
      card.querySelectorAll('.project-ship-action').forEach(button => {
        button.classList.remove(
          'project-ship-action',
          'project-ship-analyze',
          'project-ship-tests',
          'project-ship-play',
          'project-ship-task',
          'project-ship-retry',
        );
        button.removeAttribute('data-ship-action');
      });
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', cleanup, {once: true});
  } else {
    cleanup();
  }
})();
