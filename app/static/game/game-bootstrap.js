(() => {
  'use strict';

  if (window.__devpilotStandaloneGameReady) return;
  window.__devpilotStandaloneGameReady = true;

  const backToDashboard = () => window.location.assign('/');
  const trace = (stage, detail = {}) => window.__devpilotGameTrace?.(stage, detail);

  document.getElementById('game-exit')?.addEventListener('click', backToDashboard);
  document.getElementById('game-auth-back')?.addEventListener('click', backToDashboard);

  function showBootError(error) {
    const message = String(error?.message || 'Falha inesperada');
    const target = document.getElementById('build-game-view');
    if (!target) return;

    target.innerHTML = `
      <div class="empty">
        <strong>Não foi possível iniciar o jogo.</strong>
        <p>${message}</p>
        <div class="hero-actions">
          <button class="primary" id="game-error-retry" type="button">Tentar novamente</button>
          <button class="ghost" id="game-error-back" type="button">Voltar ao painel</button>
        </div>
      </div>
    `;

    document.getElementById('game-error-retry')?.addEventListener('click', () => void boot());
    document.getElementById('game-error-back')?.addEventListener('click', backToDashboard);
  }

  async function boot() {
    trace('boot:start');

    const token = String(localStorage.getItem('devpilot-token') || '').trim();
    if (!token) {
      trace('boot:no-token');
      document.getElementById('auth-modal')?.showModal?.();
      return;
    }

    try {
      if (typeof window.api !== 'function' || !window.__devpilotGameApiReady) {
        throw new Error('Runtime de comunicação do Modo Jogo indisponível');
      }

      trace('auth:start');
      await window.api('/auth/me');
      trace('auth:end', {status: 200});

      if (typeof window.loadBuildGame !== 'function') {
        throw new Error('Motor do Modo Jogo indisponível');
      }

      window.__devpilotGameLoadError = null;
      trace('game-load:start');
      await window.loadBuildGame();

      if (window.__devpilotGameLoadError) {
        throw window.__devpilotGameLoadError;
      }

      trace('game-load:end');
      document.dispatchEvent(new CustomEvent('devpilot:game:standalone-ready'));
      trace('boot:ready');
    } catch (error) {
      window.__devpilotGameLoadError = error;
      trace('boot:error', {message: String(error?.message || error || 'erro')});
      console.error('[DevPilot Game Standalone]', error);
      showBootError(error);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => void boot(), {once: true});
  } else {
    void boot();
  }
})();
