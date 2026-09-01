(() => {
  'use strict';

  if (window.__devpilotGameProjectSwitcherV50) return;
  window.__devpilotGameProjectSwitcherV50 = true;

  const VIEW_ID = 'build-game-view';
  const SWITCHER_CLASS = 'game-neon-project-switcher';
  const STYLE_ID = 'game-neon-project-switcher-style';

  function installStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .${SWITCHER_CLASS}{
        grid-column:1/-1;
        display:grid;
        grid-template-columns:42px minmax(0,1fr) 42px;
        gap:9px;
        align-items:end;
        margin:0 0 14px;
        padding:10px;
        border:1px solid rgba(71,126,255,.28);
        border-radius:15px;
        background:rgba(5,17,38,.72);
      }
      .${SWITCHER_CLASS} label{display:grid;gap:5px;min-width:0;margin:0}
      .${SWITCHER_CLASS} label>span{
        color:#73a9ff;
        font-size:.62rem;
        font-weight:900;
        letter-spacing:.1em;
        text-transform:uppercase;
      }
      .${SWITCHER_CLASS} .game-neon-project-select-host{min-width:0}
      .${SWITCHER_CLASS} select{
        width:100%;
        min-width:0;
        height:42px;
        margin:0;
        padding:0 34px 0 12px;
        border:1px solid rgba(91,133,224,.4);
        border-radius:11px;
        background:#091a33;
        color:#eef5ff;
        font-size:.86rem;
        font-weight:800;
        text-overflow:ellipsis;
      }
      .${SWITCHER_CLASS} button{
        width:42px;
        height:42px;
        min-width:42px;
        min-height:42px;
        padding:0;
        border:1px solid rgba(91,133,224,.38);
        border-radius:11px;
        background:#0b1b35;
        color:#77b1ff;
        font-size:1.25rem;
        font-weight:900;
      }
      .${SWITCHER_CLASS} button:disabled{opacity:.35}
      .${SWITCHER_CLASS}.game-neon-project-switcher-focus{
        border-color:rgba(76,145,255,.72);
        box-shadow:0 0 0 2px rgba(57,120,255,.12);
      }
      @media(max-width:420px){
        .${SWITCHER_CLASS}{grid-template-columns:38px minmax(0,1fr) 38px;padding:8px;gap:7px}
        .${SWITCHER_CLASS} button{width:38px;min-width:38px;height:40px;min-height:40px}
        .${SWITCHER_CLASS} select{height:40px;font-size:.8rem}
      }
    `;
    document.head.appendChild(style);
  }

  function projectSelect(view) {
    return view?.querySelector('#build-game-project') || null;
  }

  function triggerProjectChange(select, direction) {
    if (!select || select.options.length < 2) return;
    const total = select.options.length;
    const current = Math.max(0, select.selectedIndex);
    const next = (current + direction + total) % total;
    if (next === current) return;
    select.selectedIndex = next;
    select.dispatchEvent(new Event('change', {bubbles:true}));
  }

  function syncButtons(switcher, select) {
    const multiple = Boolean(select && select.options.length > 1);
    switcher.querySelectorAll('button').forEach(button => { button.disabled = !multiple; });
  }

  function installSwitcher() {
    const view = document.getElementById(VIEW_ID);
    const mission = view?.querySelector('.game-neon-mission');
    const select = projectSelect(view);
    if (!view || !mission || !select) return false;

    installStyle();

    let switcher = mission.querySelector(`.${SWITCHER_CLASS}`);
    if (!switcher) {
      switcher = document.createElement('div');
      switcher.className = SWITCHER_CLASS;
      switcher.innerHTML = `
        <button type="button" data-game-project-prev aria-label="Projeto anterior">‹</button>
        <label>
          <span>Projeto atual</span>
          <div class="game-neon-project-select-host"></div>
        </label>
        <button type="button" data-game-project-next aria-label="Próximo projeto">›</button>
      `;
      mission.insertBefore(switcher, mission.firstElementChild);
    }

    const host = switcher.querySelector('.game-neon-project-select-host');
    if (host && select.parentElement !== host) host.replaceChildren(select);

    switcher.querySelector('[data-game-project-prev]')?.addEventListener('click', () => triggerProjectChange(select, -1));
    switcher.querySelector('[data-game-project-next]')?.addEventListener('click', () => triggerProjectChange(select, 1));
    syncButtons(switcher, select);
    document.documentElement.dataset.devpilotGameProjectSwitcher = 'v50';
    return true;
  }

  function focusSwitcher() {
    if (!installSwitcher()) return;
    const switcher = document.querySelector(`.${SWITCHER_CLASS}`);
    const select = switcher?.querySelector('#build-game-project');
    switcher?.scrollIntoView?.({behavior:'smooth', block:'start'});
    switcher?.classList.add('game-neon-project-switcher-focus');
    window.setTimeout(() => switcher?.classList.remove('game-neon-project-switcher-focus'), 900);
    window.setTimeout(() => select?.focus?.(), 250);
  }

  function interceptProjectsNav() {
    document.addEventListener('click', event => {
      const target = event.target instanceof Element
        ? event.target.closest('[data-game-nav="projects"]')
        : null;
      if (!target) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      focusSwitcher();
    }, true);
  }

  function wrapLoader() {
    const upstream = window.loadBuildGame;
    if (typeof upstream !== 'function' || upstream.__devpilotProjectSwitcherV50) return;

    const wrapped = async function loadBuildGameWithProjectSwitcher(...args) {
      const result = await upstream.apply(this, args);
      installSwitcher();
      return result;
    };
    wrapped.__devpilotProjectSwitcherV50 = true;
    wrapped.__devpilotUpstream = upstream;
    window.loadBuildGame = wrapped;
  }

  interceptProjectsNav();
  wrapLoader();

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => installSwitcher(), {once:true});
  } else {
    installSwitcher();
  }

  document.addEventListener('devpilot:game:standalone-ready', () => installSwitcher());
})();
