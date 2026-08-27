(() => {
  'use strict';

  if (window.__devpilotStandaloneGameReady) return;
  window.__devpilotStandaloneGameReady = true;

  const TOKEN_KEY = 'devpilot-token';
  let logoutStarted = false;

  const returnToLogin = () => window.location.replace('/');

  const logoutFromGame = () => {
    if (logoutStarted) return;
    logoutStarted = true;
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.clear();
    window.location.replace('/');
  };

  document.getElementById('game-exit')?.addEventListener('click', logoutFromGame);
  document.getElementById('game-auth-back')?.addEventListener('click', returnToLogin);

  async function boot() {
    const token = String(localStorage.getItem(TOKEN_KEY) || '').trim();
    if (!token) {
      document.getElementById('auth-modal')?.showModal?.();
      return;
    }

    try {
      const response = await fetch('/api/auth/me', {
        headers: {Authorization: `Bearer ${token}`},
        cache: 'no-store',
      });
      if (!response.ok) {
        localStorage.removeItem(TOKEN_KEY);
        document.getElementById('auth-modal')?.showModal?.();
        return;
      }

      if (typeof window.loadBuildGame !== 'function') {
        throw new Error('Motor do Modo Jogo indisponível');
      }

      await window.loadBuildGame();
      document.dispatchEvent(new CustomEvent('devpilot:game:standalone-ready'));
    } catch (error) {
      console.error('[DevPilot Game Standalone]', error);
      const target = document.getElementById('build-game-view');
      if (target) {
        target.innerHTML = `<div class="empty"><strong>Não foi possível iniciar o jogo.</strong><p>${String(error?.message || 'Falha inesperada')}</p><button class="primary" id="game-error-back" type="button">Sair e voltar ao login</button></div>`;
        document.getElementById('game-error-back')?.addEventListener('click', logoutFromGame);
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => void boot(), {once: true});
  } else {
    void boot();
  }
})();
