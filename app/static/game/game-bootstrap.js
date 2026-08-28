(() => {
  'use strict';

  if (window.__devpilotStandaloneGameReady) return;
  window.__devpilotStandaloneGameReady = true;

  const backToDashboard = () => window.location.assign('/');
  const trace = (stage, detail = {}) => window.__devpilotGameTrace?.(stage, detail);

  document.getElementById('game-exit')?.addEventListener('click', backToDashboard);
  document.getElementById('game-auth-back')?.addEventListener('click', backToDashboard);

  async function boot() {
    trace('boot:start');
    const token = String(localStorage.getItem('devpilot-token') || '').trim();
    if (!token) {
      trace('boot:no-token');
      document.getElementById('auth-modal')?.showModal?.();
      return;
    }

    try {
      trace('auth:start');
      const response = await fetch('/api/auth/me', {
        headers: {Authorization: `Bearer ${token}`},
        cache: 'no-store',
      });
      trace('auth:end', {status: response.status});
      if (!response.ok) throw new Error('Autenticação necessária');

      if (typeof window.loadBuildGame !== 'function') {
        throw new Error('Motor do Modo Jogo indisponível');
      }

      window.__devpilotGameLoadError = null;
      trace('game-load:start');
      await window.loadBuildGame();
      if (window.__devpilotGameLoadError) throw window.__devpilotGameLoadError;
      trace('game-load:end');
      document.dispatchEvent(new CustomEvent('devpilot:game:standalone-ready'));
      trace('boot:ready');
    } catch (error) {
      trace('boot:error', {message: String(error?.message || error || 'erro')});
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
