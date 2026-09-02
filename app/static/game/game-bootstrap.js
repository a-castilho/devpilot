(() => {
  'use strict';

  if (window.__devpilotStandaloneGameReady) return;
  window.__devpilotStandaloneGameReady = true;

  const BOOT_TIMEOUT_MS = 20000;
  const backToDashboard = () => window.location.assign('/');
  const trace = (stage, detail = {}) => window.__devpilotGameTrace?.(stage, detail);
  const gameTarget = () => document.getElementById('build-game-view');

  document.getElementById('game-exit')?.addEventListener('click', backToDashboard);
  document.getElementById('game-auth-back')?.addEventListener('click', backToDashboard);

  function showBooting(message = 'Carregando missão, projeto e esteira do jogo…') {
    const target = gameTarget();
    if (!target || target.querySelector('.build-game-shell')) return;
    target.innerHTML = `
      <div class="empty" data-game-boot-state="loading" role="status">
        <strong>Preparando Modo Jogo…</strong>
        <p>${message}</p>
      </div>
    `;
  }

  function showBootError(error) {
    const message = String(error?.message || 'Falha inesperada');
    const target = gameTarget();
    if (!target) return;

    target.innerHTML = `
      <div class="empty" data-game-boot-state="error" role="alert">
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

  function withTimeout(promise, label) {
    return Promise.race([
      Promise.resolve(promise),
      new Promise((_, reject) => {
        window.setTimeout(() => reject(new Error(`${label} excedeu ${Math.round(BOOT_TIMEOUT_MS / 1000)}s`)), BOOT_TIMEOUT_MS);
      }),
    ]);
  }

  async function boot() {
    trace('boot:start');
    showBooting();

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
      await withTimeout(window.api('/auth/me'), 'Autenticação do jogo');
      trace('auth:end', {status: 200});

      if (typeof window.loadBuildGame !== 'function') {
        throw new Error('Motor do Modo Jogo indisponível');
      }

      window.__devpilotGameLoadError = null;
      trace('game-load:start');
      await withTimeout(window.loadBuildGame(), 'Carregamento do Modo Jogo');

      if (window.__devpilotGameLoadError) {
        throw window.__devpilotGameLoadError;
      }

      const target = gameTarget();
      if (!target?.querySelector('.build-game-shell')) {
        throw new Error('O motor do jogo carregou, mas não renderizou a interface. Atualize a versão local e tente novamente.');
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
