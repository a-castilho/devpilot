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

    const zoomedOut =
      width > 900 && (
        ratio >= 1.12 ||
        (dpr < 0.9 && ratio > 1.02)
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

    const boost = zoomedOut
      ? Math.min(1.42, Math.max(1.08, ratio))
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

    document.dispatchEvent(
      new CustomEvent('devpilot:viewport-adapted', {
        detail: value,
      })
    );
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

  function ensureScript(selector, src, datasetKey) {
    if (document.querySelector(selector)) return;

    const script = document.createElement('script');
    script.src = src;
    script.async = true;
    script.dataset[datasetKey] = '1';
    document.head.appendChild(script);
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

    /*
     * V20 usa somente os dados já renderizados por app.js e não adiciona
     * chamadas, polling ou escritas. Carrega depois das camadas históricas
     * para ser a autoridade visual final da Visão geral.
     */
    ensureStylesheet(
      'link[data-dashboard-user-v20]',
      '/assets/dashboard-user-v20.css?v=20260830-1',
      'dashboardUserV20'
    );
  }

  function loadExecutionsV18() {
    ensureScript(
      'script[data-executions-v18]',
      '/assets/executions-v18.js?v=20260830-1',
      'executionsV18'
    );
  }

  function loadExecutionsFocusV19() {
    ensureScript(
      'script[data-executions-focus-v19]',
      '/assets/executions-focus-v19.js?v=20260830-1',
      'executionsFocusV19'
    );
  }

  loadCss();
  loadExecutionsV18();
  loadExecutionsFocusV19();
  apply();

  window.addEventListener('resize', schedule, {passive: true});
  window.addEventListener('orientationchange', schedule, {passive: true});
  window.visualViewport?.addEventListener('resize', schedule, {passive: true});
  window.visualViewport?.addEventListener('scroll', schedule, {passive: true});

  document.addEventListener('devpilot:view-changed', schedule);
  document.addEventListener('devpilot:dashboard-revealed', schedule);
  document.addEventListener('devpilot:feature-ready', schedule);
})();
