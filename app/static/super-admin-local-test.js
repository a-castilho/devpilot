(() => {
  'use strict';

  const ROLE = 'SUPER_ADMIN';
  const MANUAL_KEY = 'devpilot-super-admin-local-test-manual';
  let snapshot = null;
  let mounted = false;

  const isSuperAdmin = () => String((typeof state !== 'undefined' && state.currentUser?.role) || '').toUpperCase() === ROLE;
  const escapeHtml = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const safeUrl = value => {
    try {
      const url = new URL(String(value || ''));
      return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
    } catch (_) {
      return '';
    }
  };

  const readManual = () => {
    try {
      const value = JSON.parse(localStorage.getItem(MANUAL_KEY) || '{}');
      return value && typeof value === 'object' ? value : {};
    } catch (_) {
      return {};
    }
  };

  const saveManual = value => localStorage.setItem(MANUAL_KEY, JSON.stringify(value));

  function ensureStyles() {
    if (document.getElementById('super-admin-local-test-style')) return;
    const style = document.createElement('style');
    style.id = 'super-admin-local-test-style';
    style.textContent = `
      .local-test-shell{display:grid;gap:16px}
      .local-test-hero{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;align-items:center;padding:18px;border:1px solid var(--border,#26354a);border-radius:18px;background:linear-gradient(135deg,rgba(26,71,92,.32),rgba(9,22,38,.76))}
      .local-test-hero h2{margin:4px 0 8px}.local-test-hero p{margin:0;color:var(--muted,#9eacc2)}
      .local-test-grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(260px,.9fr);gap:16px}
      .local-test-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
      .local-test-metric{padding:13px;border:1px solid var(--border,#26354a);border-radius:14px}.local-test-metric strong{display:block;margin-top:4px;font-size:1.15rem;overflow-wrap:anywhere}
      .local-test-checks{display:grid;gap:9px}.local-test-check{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px;align-items:start;padding:11px;border:1px solid var(--border,#26354a);border-radius:12px}
      .local-test-check i{display:grid;place-items:center;width:25px;height:25px;border-radius:999px;font-style:normal;font-weight:900;background:rgba(255,255,255,.06)}
      .local-test-check.ok i{color:#72efc5}.local-test-check.fail i{color:#ffc56e}.local-test-check small{display:block;margin-top:3px;color:var(--muted,#9eacc2)}
      .local-test-url{display:grid;gap:8px}.local-test-url code{display:block;padding:11px;border:1px solid var(--border,#26354a);border-radius:12px;overflow-wrap:anywhere}
      .local-test-actions{display:flex;gap:8px;flex-wrap:wrap}.local-test-actions>*{min-height:40px}
      .local-test-manual{display:grid;gap:9px}.local-test-manual label{display:flex;gap:9px;align-items:flex-start;padding:10px;border:1px solid var(--border,#26354a);border-radius:11px}.local-test-manual input{margin-top:3px}
      @media(max-width:800px){.local-test-hero,.local-test-grid{grid-template-columns:1fr}.local-test-hero .primary{width:100%}.local-test-summary{grid-template-columns:1fr}.local-test-actions>*{width:100%}}
    `;
    document.head.appendChild(style);
  }

  function removePanel() {
    document.querySelector('[data-local-test-nav]')?.remove();
    document.getElementById('super-admin-local-test-view')?.remove();
    mounted = false;
  }

  function openView(button, section) {
    if (!isSuperAdmin()) {
      if (typeof toast === 'function') toast('Acesso exclusivo do Super Admin');
      return;
    }
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button));
    const title = document.getElementById('page-title');
    if (title) title.textContent = 'Teste local/mobile';
    void loadContext();
  }

  function ensurePanel() {
    if (!isSuperAdmin()) {
      if (mounted) removePanel();
      return;
    }
    if (document.getElementById('super-admin-local-test-view')) {
      mounted = true;
      return;
    }
    const nav = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!nav || !main) return;
    ensureStyles();

    const button = document.createElement('button');
    button.className = 'nav';
    button.type = 'button';
    button.dataset.view = 'super-admin-local-test';
    button.dataset.localTestNav = '1';
    button.textContent = 'Teste local/mobile';
    nav.insertBefore(button, nav.querySelector('[data-view="cloud-admin"]') || nav.querySelector('[data-view="reports"]') || null);

    const section = document.createElement('section');
    section.className = 'view';
    section.id = 'super-admin-local-test-view';
    section.innerHTML = `
      <div class="local-test-shell">
        <div class="local-test-hero">
          <div>
            <span class="eyebrow">SUPER ADMIN · DIAGNÓSTICO AUTORIZADO</span>
            <h2>Teste local e mobile do DevPilot</h2>
            <p>Executa somente verificações pré-definidas do próprio DevPilot. Não aceita comandos shell, hosts arbitrários ou credenciais.</p>
          </div>
          <button class="primary" type="button" id="local-test-run">Executar teste agora</button>
        </div>
        <div id="local-test-summary" class="local-test-summary"></div>
        <div class="local-test-grid">
          <article class="panel">
            <div class="panel-title"><div><span class="eyebrow">AUTOMÁTICO</span><h3>Verificações do sistema</h3></div><span class="status" id="local-test-status">AGUARDANDO</span></div>
            <div id="local-test-checks" class="local-test-checks"><div class="empty">Abra este painel e execute o teste.</div></div>
          </article>
          <article class="panel">
            <div class="panel-title"><div><span class="eyebrow">CELULAR</span><h3>URL e validação visual</h3></div></div>
            <div id="local-test-url" class="local-test-url"></div>
            <div style="margin-top:14px"><strong>Checklist manual</strong><div id="local-test-manual" class="local-test-manual" style="margin-top:9px"></div></div>
          </article>
        </div>
      </div>
    `;
    const anchor = document.getElementById('cloud-admin-view') || document.getElementById('reports-view');
    (anchor?.parentNode || main).insertBefore(section, anchor || null);
    button.addEventListener('click', () => openView(button, section));
    section.querySelector('#local-test-run').addEventListener('click', runTest);
    mounted = true;
  }

  function render(data = {}) {
    snapshot = data;
    const summary = document.getElementById('local-test-summary');
    const checks = document.getElementById('local-test-checks');
    const status = document.getElementById('local-test-status');
    const urlBox = document.getElementById('local-test-url');
    const manual = document.getElementById('local-test-manual');
    if (!summary || !checks || !status || !urlBox || !manual) return;

    const passed = Number.isFinite(Number(data.passed)) ? Number(data.passed) : null;
    const total = Number.isFinite(Number(data.total)) ? Number(data.total) : null;
    summary.innerHTML = `
      <div class="local-test-metric"><span class="eyebrow">PERFIL</span><strong>${escapeHtml(data.role || 'SUPER_ADMIN')}</strong><small>autorização exigida no backend</small></div>
      <div class="local-test-metric"><span class="eyebrow">LINUX IP</span><strong>${escapeHtml(data.linux_ip || '—')}</strong><small>interface local detectada</small></div>
      <div class="local-test-metric"><span class="eyebrow">RESULTADO</span><strong>${passed === null ? '—' : `${passed}/${total}`}</strong><small>verificações automáticas</small></div>
    `;

    const items = Array.isArray(data.checks) ? data.checks : [];
    checks.innerHTML = items.length ? items.map(item => `
      <div class="local-test-check ${item.ok ? 'ok' : 'fail'}">
        <i>${item.ok ? '✓' : '!'}</i>
        <div><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.detail || '')}</small></div>
      </div>
    `).join('') : '<div class="empty">Clique em “Executar teste agora” para rodar o diagnóstico.</div>';
    status.textContent = items.length ? (data.ok ? 'APROVADO' : 'ATENÇÃO') : 'PRONTO';

    const mobileUrl = safeUrl(data.mobile_url);
    urlBox.innerHTML = mobileUrl ? `
      <code>${escapeHtml(mobileUrl)}</code>
      <div class="local-test-actions">
        <a class="primary" href="${escapeHtml(mobileUrl)}" target="_blank" rel="noopener noreferrer">Abrir no celular ↗</a>
        <button class="ghost" type="button" id="local-test-copy">Copiar URL</button>
      </div>
    ` : '<div class="empty">URL da rede local ainda não disponível.</div>';
    document.getElementById('local-test-copy')?.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(mobileUrl);
        if (typeof toast === 'function') toast('URL local copiada.');
      } catch (_) {
        if (typeof toast === 'function') toast('Não foi possível copiar a URL automaticamente.');
      }
    });

    const manualState = readManual();
    const checklist = Array.isArray(data.manual_checklist) ? data.manual_checklist : [];
    manual.innerHTML = checklist.map((label, index) => `
      <label><input type="checkbox" data-local-manual="${index}" ${manualState[index] ? 'checked' : ''}><span>${escapeHtml(label)}</span></label>
    `).join('') || '<div class="empty">Checklist indisponível.</div>';
    manual.querySelectorAll('[data-local-manual]').forEach(input => {
      input.addEventListener('change', () => {
        const value = readManual();
        value[input.dataset.localManual] = input.checked;
        saveManual(value);
      });
    });
  }

  async function loadContext() {
    if (!isSuperAdmin()) return;
    try {
      render(await api('/admin/local-test'));
    } catch (error) {
      if (typeof toast === 'function') toast(error?.message || 'Não foi possível carregar o teste local.');
    }
  }

  async function runTest() {
    if (!isSuperAdmin()) return;
    const button = document.getElementById('local-test-run');
    if (button) {
      button.disabled = true;
      button.textContent = 'Testando…';
    }
    try {
      const result = await api('/admin/local-test/run', {method: 'POST'});
      render(result);
      if (typeof toast === 'function') toast(result.ok ? 'Teste local concluído.' : 'Teste concluído com pontos de atenção.');
    } catch (error) {
      if (typeof toast === 'function') toast(error?.message || 'Falha ao executar o teste local.');
    } finally {
      if (button?.isConnected) {
        button.disabled = false;
        button.textContent = 'Executar teste agora';
      }
    }
  }

  const boot = () => {
    ensurePanel();
    window.setTimeout(ensurePanel, 600);
    window.setTimeout(ensurePanel, 1600);
    const root = document.body;
    if (root && !root.dataset.localTestObserved) {
      root.dataset.localTestObserved = '1';
      new MutationObserver(ensurePanel).observe(root, {childList: true, subtree: true});
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
