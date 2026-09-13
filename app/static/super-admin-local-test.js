(() => {
  'use strict';

  if (window.__devpilotSuperAdminBundleBridgeV1) return;
  window.__devpilotSuperAdminBundleBridgeV1 = true;

  const revision = (() => {
    try { return new URL(document.currentScript?.src || '', location.href).searchParams.get('v') || Date.now(); }
    catch (_) { return Date.now(); }
  })();

  const load = name => new Promise(resolve => {
    if (Array.from(document.scripts).some(script => String(script.src || '').includes(`/assets/${name}`))) {
      resolve(true);
      return;
    }
    const script = document.createElement('script');
    script.src = `/assets/${name}?v=${encodeURIComponent(revision)}`;
    script.async = false;
    script.onload = () => resolve(true);
    script.onerror = () => { console.error(`[DevPilot] Falha ao carregar ${name}`); resolve(false); };
    document.body.appendChild(script);
  });

  void load('super-admin-local-test-core.js')
    .then(() => load('blueprint-admin.js'))
    .then(() => load('blueprint-admin-navigation-fix.js'));
})();
