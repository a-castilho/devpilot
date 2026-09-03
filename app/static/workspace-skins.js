(() => {
  'use strict';

  if (window.__devpilotWorkspaceSkinsV94) return;
  window.__devpilotWorkspaceSkinsV94 = true;

  const STORAGE_KEY = 'devpilot-workspace-skin';
  const CSS_ID = 'devpilot-workspace-skins-css';
  const PICKER_ID = 'devpilot-workspace-skin-picker';
  const SKINS = Object.freeze([
    {id:'black', label:'Preto', color:'#000000', themeColor:'#000000'},
    {id:'yellow', label:'Amarelo', color:'#ffd84d', themeColor:'#151000'},
    {id:'red', label:'Vermelho', color:'#ff526b', themeColor:'#150407'},
    {id:'blue', label:'Azul', color:'#4d94ff', themeColor:'#030b18'},
    {id:'green', label:'Verde', color:'#42d99c', themeColor:'#03110c'},
    {id:'white', label:'Branco', color:'#ffffff', themeColor:'#f5f7fa'},
  ]);

  function ensureStylesheet() {
    if (document.getElementById(CSS_ID)) return;
    const link = document.createElement('link');
    link.id = CSS_ID;
    link.rel = 'stylesheet';
    link.href = '/assets/workspace-skins.css?v=20260903-v94';
    document.head.appendChild(link);
  }

  function resolveSkin(id) {
    return SKINS.find(skin => skin.id === id) || SKINS[0];
  }

  function updateThemeColor(color) {
    let meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'theme-color';
      document.head.appendChild(meta);
    }
    meta.content = color;
  }

  function syncPicker(activeId) {
    document.querySelectorAll(`#${PICKER_ID} [data-skin]`).forEach(button => {
      const active = button.dataset.skin === activeId;
      button.setAttribute('aria-pressed', String(active));
    });
  }

  function applySkin(id, announce = false) {
    const skin = resolveSkin(id);
    document.documentElement.dataset.workspaceSkin = skin.id;
    document.documentElement.removeAttribute('data-workspace-tone');
    localStorage.setItem(STORAGE_KEY, skin.id);
    updateThemeColor(skin.themeColor);
    syncPicker(skin.id);
    document.dispatchEvent(new CustomEvent('devpilot:workspace-skin', {detail:{skin:skin.id}}));
    if (announce) window.toast?.(`Skin alterada para ${skin.label}.`);
  }

  function removeLegacyPicker() {
    document.querySelectorAll('.workspace-tone-picker').forEach(element => element.remove());
    document.documentElement.removeAttribute('data-workspace-tone');
  }

  function buildPicker() {
    if (document.getElementById(PICKER_ID)) return;

    const picker = document.createElement('div');
    picker.id = PICKER_ID;
    picker.className = 'workspace-skin-picker is-collapsed';
    picker.dataset.collapsed = 'true';
    picker.setAttribute('aria-label', 'Skins do DevPilot');

    const swatches = document.createElement('div');
    swatches.id = `${PICKER_ID}-swatches`;
    swatches.className = 'workspace-skin-swatches';
    swatches.setAttribute('role', 'group');
    swatches.setAttribute('aria-label', 'Escolha uma cor');
    swatches.setAttribute('aria-hidden', 'true');

    SKINS.forEach(skin => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'workspace-skin-swatch';
      button.dataset.skin = skin.id;
      button.style.setProperty('--swatch', skin.color);
      button.setAttribute('aria-label', `Skin ${skin.label}`);
      button.setAttribute('aria-pressed', 'false');
      button.tabIndex = -1;
      button.addEventListener('click', () => applySkin(skin.id, true));
      swatches.appendChild(button);
    });

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'workspace-skin-toggle';
    toggle.textContent = '‹';
    toggle.setAttribute('aria-controls', swatches.id);
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Mostrar seletor de cores');

    toggle.addEventListener('click', () => {
      const collapsed = picker.dataset.collapsed !== 'false';
      const nextCollapsed = !collapsed;
      picker.dataset.collapsed = String(nextCollapsed);
      picker.classList.toggle('is-collapsed', nextCollapsed);
      swatches.setAttribute('aria-hidden', String(nextCollapsed));
      toggle.setAttribute('aria-expanded', String(!nextCollapsed));
      toggle.setAttribute('aria-label', nextCollapsed ? 'Mostrar seletor de cores' : 'Esconder seletor de cores');
      toggle.textContent = nextCollapsed ? '‹' : '›';
      swatches.querySelectorAll('.workspace-skin-swatch').forEach(button => {
        button.tabIndex = nextCollapsed ? -1 : 0;
      });
    });

    picker.append(swatches, toggle);
    document.body.appendChild(picker);
    syncPicker(resolveSkin(localStorage.getItem(STORAGE_KEY)).id);
  }

  function initialize() {
    ensureStylesheet();
    removeLegacyPicker();
    buildPicker();
    applySkin(localStorage.getItem(STORAGE_KEY) || 'black', false);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once:true});
  } else {
    initialize();
  }
})();
