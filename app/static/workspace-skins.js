(() => {
  const STORAGE_KEY = 'devpilot-workspace-skin';
  const PICKER_COLLAPSED_KEY = 'devpilot-workspace-skin-picker-collapsed';
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
    link.href = '/assets/workspace-skins.css?v=20260821-hide1';
    document.head.appendChild(link);
  }

  function removeEscapedNewlineArtifact() {
    const removeFrom = parent => {
      if (!parent) return;
      [...parent.childNodes].forEach(node => {
        if (node.nodeType !== Node.TEXT_NODE) return;
        const value = String(node.nodeValue || '').trim();
        if (value === '\\n' || value === '\\r\\n') node.remove();
      });
    };

    removeFrom(document.body);
    removeFrom(document.documentElement);
  }

  function validSkin(id) {
    return SKINS.some(skin => skin.id === id);
  }

  function currentSkinId() {
    const active = document.documentElement.dataset.workspaceSkin;
    return validSkin(active) ? active : 'black';
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

  function isPickerCollapsed() {
    return localStorage.getItem(PICKER_COLLAPSED_KEY) === '1';
  }

  function setPickerCollapsed(collapsed, persist = true) {
    const picker = document.getElementById(PICKER_ID);
    if (!picker) return;

    const swatches = picker.querySelector('.workspace-skin-swatches');
    const toggle = picker.querySelector('.workspace-skin-toggle');

    picker.classList.toggle('is-collapsed', collapsed);
    picker.dataset.collapsed = String(collapsed);

    if (swatches) {
      swatches.setAttribute('aria-hidden', String(collapsed));
      swatches.querySelectorAll('.workspace-skin-swatch').forEach(button => {
        button.tabIndex = collapsed ? -1 : 0;
      });
    }

    if (toggle) {
      toggle.textContent = collapsed ? '‹' : '›';
      toggle.setAttribute('aria-expanded', String(!collapsed));
      toggle.setAttribute('aria-label', collapsed ? 'Mostrar seletor de cores' : 'Esconder seletor de cores');
      toggle.title = collapsed ? 'Mostrar cores' : 'Esconder cores';
    }

    if (persist) {
      localStorage.setItem(PICKER_COLLAPSED_KEY, collapsed ? '1' : '0');
    }
  }

  function togglePicker() {
    const picker = document.getElementById(PICKER_ID);
    if (!picker) return;
    setPickerCollapsed(!picker.classList.contains('is-collapsed'));
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

    if (announce && typeof toast === 'function') toast(`Skin alterada para ${skin.label}.`);
    document.dispatchEvent(new CustomEvent('devpilot:workspace-skin', {detail: {skin: skin.id}}));
  }

  function removeLegacyTonePicker() {
    document.querySelectorAll('.workspace-tone-picker').forEach(element => element.remove());
    document.documentElement.removeAttribute('data-workspace-tone');
  }

  function buildPicker() {
    if (document.getElementById(PICKER_ID)) return;

    const picker = document.createElement('div');
    picker.id = PICKER_ID;
    picker.className = 'workspace-skin-picker';
    picker.setAttribute('aria-label', 'Skins do DevPilot');

    const swatches = document.createElement('div');
    swatches.className = 'workspace-skin-swatches';
    swatches.setAttribute('role', 'group');
    swatches.setAttribute('aria-label', 'Escolha uma cor');

    SKINS.forEach(skin => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'workspace-skin-swatch';
      button.dataset.skin = skin.id;
      button.dataset.label = skin.label;
      button.style.setProperty('--swatch', skin.color);
      button.setAttribute('aria-label', `Skin ${skin.label}`);
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => applySkin(skin.id, true));
      swatches.appendChild(button);
    });

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'workspace-skin-toggle';
    toggle.textContent = '›';
    toggle.setAttribute('aria-controls', `${PICKER_ID}-swatches`);
    toggle.addEventListener('click', togglePicker);

    swatches.id = `${PICKER_ID}-swatches`;
    picker.append(swatches, toggle);
    document.body.appendChild(picker);
  }

  function initialize() {
    ensureStylesheet();
    removeEscapedNewlineArtifact();
    removeLegacyTonePicker();
    buildPicker();

    const saved = localStorage.getItem(STORAGE_KEY);
    applySkin(validSkin(saved) ? saved : 'black', false);
    setPickerCollapsed(isPickerCollapsed(), false);

    // O seletor antigo ou texto residual podem ser recriados por outro bundle.
    const observer = new MutationObserver(() => {
      removeEscapedNewlineArtifact();
      const legacy = document.querySelector('.workspace-tone-picker');
      if (legacy) legacy.remove();
      if (document.documentElement.hasAttribute('data-workspace-tone')) {
        document.documentElement.removeAttribute('data-workspace-tone');
      }
    });
    observer.observe(document.body, {childList: true, subtree: true});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once: true});
  } else {
    initialize();
  }
})();
