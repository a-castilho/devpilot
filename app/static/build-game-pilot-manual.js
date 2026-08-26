/* DevPilot Build Game pilot manual: frontend-only documentation inside the ship. */
(() => {
  'use strict';

  if (window.__devpilotBuildGamePilotManualReady) return;
  window.__devpilotBuildGamePilotManualReady = true;

  const ROOT_ID = 'devpilot-game-shell';
  const MODAL_ID = 'build-game-pilot-manual';
  const STYLE_ID = 'build-game-pilot-manual-style';
  let lastFocused = null;

  function installStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .devpilot-game-hud .build-game-pilot-manual-open{min-height:38px;padding:8px 12px;border:1px solid rgba(102,235,215,.28);border-radius:10px;background:rgba(5,18,27,.72);color:#cffff4;font-size:.72rem;font-weight:800;letter-spacing:.04em;cursor:pointer}
      .devpilot-game-hud .build-game-pilot-manual-open:hover,.devpilot-game-hud .build-game-pilot-manual-open:focus-visible{border-color:rgba(102,235,215,.62);outline:none;box-shadow:0 0 0 3px rgba(102,235,215,.1)}
      .build-game-pilot-manual{position:fixed;inset:0;z-index:10050;display:grid;place-items:center;padding:18px;background:rgba(0,4,9,.82);backdrop-filter:blur(8px)}
      .build-game-pilot-manual[hidden]{display:none}
      .build-game-pilot-manual-dialog{width:min(920px,100%);max-height:min(86vh,900px);display:grid;grid-template-rows:auto minmax(0,1fr);overflow:hidden;border:1px solid rgba(101,229,215,.32);border-radius:20px;background:linear-gradient(180deg,#07131e,#040a11);box-shadow:0 30px 90px rgba(0,0,0,.55)}
      .build-game-pilot-manual-head{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:16px 18px;border-bottom:1px solid rgba(101,229,215,.16)}
      .build-game-pilot-manual-head span{display:block;color:#65dfff;font-size:.63rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase}
      .build-game-pilot-manual-head h2{margin:4px 0 0;color:#e9fffb;font-size:clamp(1.2rem,3vw,1.7rem)}
      .build-game-pilot-manual-close{width:40px;height:40px;border:1px solid rgba(255,255,255,.12);border-radius:11px;background:rgba(255,255,255,.04);color:#d7e7e7;font-size:1.15rem;cursor:pointer}
      .build-game-pilot-manual-body{overflow:auto;padding:18px;display:grid;gap:15px;color:#b9c9ce;line-height:1.55}
      .build-game-pilot-manual-intro{margin:0;padding:14px;border:1px solid rgba(101,229,215,.16);border-radius:14px;background:rgba(75,218,193,.055);color:#d7f7f2}
      .build-game-pilot-manual-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
      .build-game-pilot-manual-card{padding:14px;border:1px solid rgba(255,255,255,.08);border-radius:14px;background:rgba(8,19,29,.72)}
      .build-game-pilot-manual-card h3{margin:0 0 7px;color:#dffff9;font-size:.92rem}
      .build-game-pilot-manual-card p{margin:0;font-size:.78rem}
      .build-game-pilot-manual-flow{padding:14px;border:1px solid rgba(97,207,255,.18);border-radius:14px;background:rgba(31,105,145,.07)}
      .build-game-pilot-manual-flow strong{display:block;margin-bottom:8px;color:#a7e9ff;font-size:.72rem;letter-spacing:.08em;text-transform:uppercase}
      .build-game-pilot-manual-flow code{white-space:normal;color:#e8f9ff;font-family:inherit;font-size:.78rem}
      .build-game-pilot-manual-rule{margin:0;padding:13px 14px;border-left:3px solid #65f0c0;background:rgba(101,240,192,.055);color:#d7f6eb;font-size:.8rem}
      @media(max-width:700px){.devpilot-game-hud{grid-template-columns:auto minmax(0,1fr)}.devpilot-game-hud .build-game-pilot-manual-open{grid-column:1/-1;width:100%}.build-game-pilot-manual{padding:8px}.build-game-pilot-manual-dialog{max-height:94vh;border-radius:15px}.build-game-pilot-manual-grid{grid-template-columns:1fr}.build-game-pilot-manual-body{padding:13px}}
    `;
    document.head.appendChild(style);
  }

  function manualMarkup() {
    return `<section class="build-game-pilot-manual" id="${MODAL_ID}" role="dialog" aria-modal="true" aria-labelledby="build-game-pilot-manual-title" hidden>
      <div class="build-game-pilot-manual-dialog">
        <header class="build-game-pilot-manual-head">
          <div><span>DEV-01 · DOCUMENTAÇÃO DE BORDO</span><h2 id="build-game-pilot-manual-title">Manual do Piloto</h2></div>
          <button class="build-game-pilot-manual-close" type="button" data-pilot-manual-close aria-label="Fechar manual">✕</button>
        </header>
        <div class="build-game-pilot-manual-body">
          <p class="build-game-pilot-manual-intro">Você está pilotando um projeto real. O Modo Jogo traduz o trabalho técnico do DevPilot para a linguagem da nave sem inventar estados, resultados ou permissões.</p>
          <div class="build-game-pilot-manual-grid">
            <article class="build-game-pilot-manual-card"><h3>🏛️ Império</h3><p>A organização é o Império. Administradores observam a frota; o piloto trabalha dentro da nave do projeto.</p></article>
            <article class="build-game-pilot-manual-card"><h3>🚀 Nave</h3><p>Cada projeto é uma nave. Nome, missão, progresso e condições devem refletir informações reais do projeto.</p></article>
            <article class="build-game-pilot-manual-card"><h3>🎯 Armas</h3><p>Cada tarefa real é representada como uma arma. Disparar significa solicitar a mesma execução que o DevPilot já executaria fora da metáfora visual.</p></article>
            <article class="build-game-pilot-manual-card"><h3>📡 Sensores</h3><p>Testes, build, CI, segurança, health checks e telemetria confirmam se o disparo atingiu o objetivo. Animação nunca confirma sucesso.</p></article>
            <article class="build-game-pilot-manual-card"><h3>🛡️ Integridade</h3><p>Falhas reais podem aparecer como dano, alerta ou subsistema indisponível. A nave só se recupera quando a condição técnica correspondente é resolvida.</p></article>
            <article class="build-game-pilot-manual-card"><h3>🏁 Missão</h3><p>A missão progride por evidência real: análise, implementação, testes e entrega. Uma fase não deve avançar apenas porque a interface terminou uma animação.</p></article>
          </div>
          <div class="build-game-pilot-manual-flow"><strong>Fluxo de disparo</strong><code>ARMA PRONTA → DISPARAR → EXECUTANDO → SENSORES VERIFICANDO → ALVO CONFIRMADO ou FALHA DETECTADA</code></div>
          <p class="build-game-pilot-manual-rule"><strong>Regra de bordo:</strong> um clique deve produzir no máximo uma execução. O domínio técnico controla a metáfora; a metáfora nunca controla o domínio.</p>
          <p class="build-game-pilot-manual-rule"><strong>Segurança:</strong> esconder ou mostrar controles no cockpit não concede autorização. Permissões reais continuam sendo responsabilidade do backend.</p>
        </div>
      </div>
    </section>`;
  }

  function ensureModal() {
    let modal = document.getElementById(MODAL_ID);
    if (modal) return modal;
    const host = document.createElement('div');
    host.innerHTML = manualMarkup().trim();
    modal = host.firstElementChild;
    if (!modal) return null;
    document.body.appendChild(modal);
    modal.querySelector('[data-pilot-manual-close]')?.addEventListener('click', closeManual);
    modal.addEventListener('click', event => { if (event.target === modal) closeManual(); });
    return modal;
  }

  function openManual(button) {
    const modal = ensureModal();
    if (!modal) return;
    lastFocused = button || document.activeElement;
    modal.hidden = false;
    document.body.dataset.devpilotPilotManualOpen = '1';
    modal.querySelector('[data-pilot-manual-close]')?.focus();
  }

  function closeManual() {
    const modal = document.getElementById(MODAL_ID);
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    delete document.body.dataset.devpilotPilotManualOpen;
    if (lastFocused?.isConnected) lastFocused.focus();
    lastFocused = null;
  }

  function ensureButton() {
    const root = document.getElementById(ROOT_ID);
    const hud = root?.querySelector('.devpilot-game-hud');
    if (!hud || hud.querySelector('[data-pilot-manual-open]')) return false;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'build-game-pilot-manual-open';
    button.dataset.pilotManualOpen = '1';
    button.textContent = '📘 Manual do Piloto';
    button.setAttribute('aria-haspopup', 'dialog');
    button.addEventListener('click', () => openManual(button));
    hud.appendChild(button);
    return true;
  }

  function sync() {
    installStyle();
    ensureModal();
    ensureButton();
  }

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !document.getElementById(MODAL_ID)?.hidden) closeManual();
  });
  document.addEventListener('devpilot:game:entered', sync);
  document.addEventListener('devpilot:game:rendered', sync);
  document.addEventListener('devpilot:feature-ready', event => {
    if (event.detail?.feature === 'game') sync();
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sync, {once: true});
  else sync();
})();