(() => {
  'use strict';

  const STORAGE_KEY = 'devpilot-workspace-skin';
  const CSS_ID = 'devpilot-workspace-skins-css';
  const PICKER_ID = 'devpilot-workspace-skin-picker';
  const SKINS = [
    {id: 'black', label: 'Preto', color: '#000000', themeColor: '#000000'},
    {id: 'yellow', label: 'Amarelo', color: '#ffd84d', themeColor: '#151000'},
    {id: 'red', label: 'Vermelho', color: '#ff526b', themeColor: '#150407'},
    {id: 'blue', label: 'Azul', color: '#4d94ff', themeColor: '#030b18'},
    {id: 'green', label: 'Verde', color: '#42d99c', themeColor: '#03110c'},
    {id: 'white', label: 'Branco', color: '#ffffff', themeColor: '#f5f7fa'},
  ];

  function ensureStylesheet() {
    if (document.getElementById(CSS_ID)) return;
    const link = document.createElement('link');
    link.id = CSS_ID;
    link.rel = 'stylesheet';
    link.href = '/assets/workspace-skins.css?v=20260904-click-safe';
    document.head.appendChild(link);
  }

  function validSkin(id) {
    return SKINS.some(skin => skin.id === id);
  }

  function updateThemeColor(skin) {
    let meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'theme-color';
      document.head.appendChild(meta);
    }
    meta.content = skin.themeColor;
  }

  function syncPicker(skin) {
    const picker = document.getElementById(PICKER_ID);
    if (!picker) return;
    picker.querySelectorAll('.workspace-skin-swatch').forEach(button => {
      const selected = button.dataset.skin === skin.id;
      button.setAttribute('aria-pressed', String(selected));
      button.title = selected ? `${skin.label} selecionado` : `Usar skin ${button.dataset.label}`;
    });
  }

  function applySkin(id, announce = false) {
    const skin = SKINS.find(item => item.id === id) || SKINS[0];
    const root = document.documentElement;
    root.removeAttribute('data-workspace-tone');
    root.dataset.workspaceSkin = skin.id;
    localStorage.setItem(STORAGE_KEY, skin.id);
    updateThemeColor(skin);
    syncPicker(skin);
    if (announce && typeof window.toast === 'function') {
      window.toast(`Skin alterada para ${skin.label}.`);
    }
    document.dispatchEvent(new CustomEvent('devpilot:workspace-skin', {detail:{skin: skin.id}}));
  }

  function removeLegacyArtifactsOnce() {
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
      button.dataset.label = skin.label;
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
    toggle.title = 'Mostrar cores';
    toggle.addEventListener('click', () => {
      const collapsed = !picker.classList.contains('is-collapsed');
      picker.classList.toggle('is-collapsed', collapsed);
      picker.dataset.collapsed = String(collapsed);
      swatches.setAttribute('aria-hidden', String(collapsed));
      swatches.querySelectorAll('.workspace-skin-swatch').forEach(button => {
        button.tabIndex = collapsed ? -1 : 0;
      });
      toggle.textContent = collapsed ? '‹' : '›';
      toggle.setAttribute('aria-expanded', String(!collapsed));
      toggle.setAttribute('aria-label', collapsed ? 'Mostrar seletor de cores' : 'Esconder seletor de cores');
      toggle.title = collapsed ? 'Mostrar cores' : 'Esconder cores';
    });

    picker.append(swatches, toggle);
    document.body.appendChild(picker);
  }

  function initialize() {
    ensureStylesheet();
    removeLegacyArtifactsOnce();
    buildPicker();
    const saved = localStorage.getItem(STORAGE_KEY);
    applySkin(validSkin(saved) ? saved : 'black', false);
    window.__devpilotWorkspaceSkinsReady = true;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once:true});
  } else {
    initialize();
  }
})();
