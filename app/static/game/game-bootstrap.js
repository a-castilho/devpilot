(() => {
  'use strict';

  if (window.__devpilotStandaloneGameReady) return;
  window.__devpilotStandaloneGameReady = true;

  const backToDashboard = () => window.location.assign('/');

  document.getElementById('game-exit')?.addEventListener('click', backToDashboard);
  document.getElementById('game-auth-back')?.addEventListener('click', backToDashboard);

  async function boot() {
    const token = String(localStorage.getItem('devpilot-token') || '').trim();
    if (!token) {
      document.getElementById('auth-modal')?.showModal?.();
      return;
    }

    try {
      const response = await fetch('/api/auth/me', {
        headers: {Authorization: `Bearer ${token}`},
        cache: 'no-store',
      });
      if (!response.ok) throw new Error('Autenticação necessária');

      if (typeof window.loadBuildGame !== 'function') {
        throw new Error('Motor do Modo Jogo indisponível');
      }

      await window.loadBuildGame();
      document.dispatchEvent(new CustomEvent('devpilot:game:standalone-ready'));
    } catch (error) {
      console.error('[DevPilot Game Standalone]', error);
      const target = document.getElementById('build-game-view');
      if (target) {
        target.innerHTML = `<div class="empty"><strong>Não foi possível iniciar o jogo.</strong><p>${String(error?.message || 'Falha inesperada')}</p><button class="primary" id="game-error-back" type="button">Voltar ao painel</button></div>`;
        document.getElementById('game-error-back')?.addEventListener('click', backToDashboard);
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => void boot(), {once: true});
  } else {
    void boot();
  }
})();
