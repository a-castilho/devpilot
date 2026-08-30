(() => {
  'use strict';

  if (window.__devpilotViewportAdaptiveV15) return;
  window.__devpilotViewportAdaptiveV15 = true;

  const root = document.documentElement;
  let frame = 0;

  function metrics() {
    const viewport = window.visualViewport;
    const width = Math.max(1, Number(viewport?.width || window.innerWidth || 1));
    const height = Math.max(1, Number(viewport?.height || window.innerHeight || 1));
    const screenWidth = Math.max(
      1,
      Number(window.screen?.availWidth || window.screen?.width || width)
    );
    const screenHeight = Math.max(
      1,
      Number(window.screen?.availHeight || window.screen?.height || height)
    );
    const ratio = width / screenWidth;
    const dpr = Number(window.devicePixelRatio || 1);

    /*
     * Em desktop, zoom-out aumenta a viewport CSS acima do espaço físico da
     * tela. ratio é mais estável que depender apenas de DPR em Linux/HiDPI.
     */
    const zoomedOut =
      width > 900 && (
        ratio >= 1.08 ||
        (dpr < 0.95 && ratio > 1.01)
      );

    const physicalWidth = Math.min(screenWidth, width);
    const physicalHeight = Math.min(screenHeight, height);
    const compact =
      physicalWidth <= 1280 ||
      height <= 820 ||
      zoomedOut;
    const short =
      physicalHeight <= 820 ||
      height <= 760;

    /*
     * V15 limitava a compensação em 1.42 e deixava 67%/50% fisicamente
     * minúsculos. A escala agora acompanha o zoom observado, com limite de
     * segurança para não transformar uma janela estreita em layout gigante.
     */
    const boost = zoomedOut
      ? Math.min(2.25, Math.max(1.08, ratio))
      : 1;

    return {
      width,
      height,
      screenWidth,
      screenHeight,
      ratio,
      dpr,
      zoomedOut,
      compact,
      short,
      boost,
    };
  }

  function apply() {
    frame = 0;
    const value = metrics();

    root.classList.toggle('dp-zoom-out', value.zoomedOut);
    root.classList.toggle('dp-space-compact', value.compact);
    root.classList.toggle('dp-space-short', value.short);
    root.classList.toggle('dp-vp-phone', value.width <= 600);
    root.classList.toggle('dp-vp-tablet', value.width > 600 && value.width <= 900);
    root.classList.toggle('dp-vp-notebook', value.width > 900 && value.compact);
    root.classList.toggle('dp-vp-wide', value.width > 1280 && !value.compact);

    root.style.setProperty('--dp-ui-boost', value.boost.toFixed(3));
    root.style.setProperty('--dp-viewport-width', `${Math.round(value.width)}px`);
    root.style.setProperty('--dp-viewport-height', `${Math.round(value.height)}px`);

    root.dataset.dpViewport =
      value.width <= 600
        ? 'phone'
        : value.width <= 900
          ? 'tablet'
          : value.compact
            ? 'compact'
            : 'wide';

    root.dataset.dpZoom = value.zoomedOut ? 'out' : 'normal';
    root.dataset.dpBoost = value.boost.toFixed(2);

    document.dispatchEvent(new CustomEvent('devpilot:viewport-adapted', {
      detail: value,
    }));
  }

  function schedule() {
    if (frame) return;
    frame = window.requestAnimationFrame(apply);
  }

  function ensureStylesheet(selector, href, datasetKey) {
    if (document.querySelector(selector)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    link.dataset[datasetKey] = '1';
    document.head.appendChild(link);
  }

  function loadCss() {
    ensureStylesheet(
      'link[data-layout-adaptive-v15]',
      '/assets/layout-adaptive-v15.css?v=20260830-1',
      'layoutAdaptiveV15'
    );
    ensureStylesheet(
      'link[data-sidebar-responsive-v16]',
      '/assets/sidebar-responsive-v16.css?v=20260830-1',
      'sidebarResponsiveV16'
    );
    ensureStylesheet(
      'link[data-sidebar-state-v24]',
      '/assets/sidebar-state-v24.css?v=20260830-1',
      'sidebarStateV24'
    );
    ensureStylesheet(
      'link[data-dashboard-user-v20]',
      '/assets/dashboard-user-v20.css?v=20260830-1',
      'dashboardUserV20'
    );
    ensureStylesheet(
      'link[data-users-layout-v25]',
      '/assets/users-layout-v25.css?v=20260830-1',
      'usersLayoutV25'
    );
    ensureStylesheet(
      'link[data-page-navigation-v26]',
      '/assets/page-navigation-v26.css?v=20260830-1',
      'pageNavigationV26'
    );
    ensureStylesheet(
      'link[data-layout-scale-v36]',
      '/assets/layout-scale-v36.css?v=20260830-1',
      'layoutScaleV36'
    );
  }

  loadCss();
  apply();

  window.addEventListener('resize', schedule, {passive:true});
  window.addEventListener('orientationchange', schedule, {passive:true});
  window.visualViewport?.addEventListener('resize', schedule, {passive:true});
  window.visualViewport?.addEventListener('scroll', schedule, {passive:true});

  document.addEventListener('devpilot:view-changed', schedule);
  document.addEventListener('devpilot:dashboard-revealed', schedule);
  document.addEventListener('devpilot:feature-ready', schedule);

  console.info('[DevPilot] Viewport Adaptive V36 escala física ativa');
})();
