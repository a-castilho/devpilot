(() => {
  'use strict';

  if (window.__devpilotChatControl?.installed) return;

  let releaseDeferred;
  const ready = new Promise(resolve => { releaseDeferred = resolve; });
  const control = window.__devpilotChatControl = {
    installed: true,
    enabled: false,
    reason: 'Chat desligado por padrão pelo controle da plataforma.',
    source: 'default',
    updatedAt: null,
    ready,
    deferredReleased: false,
    releaseDeferred() {
      if (control.deferredReleased) return;
      control.deferredReleased = true;
      releaseDeferred?.(control);
      releaseDeferred = null;
    },
  };

  const token = () => localStorage.getItem('devpilot-token') || '';
  const headers = () => ({
    Authorization: `Bearer ${token()}`,
    'Content-Type': 'application/json',
  });

  // O loader global de main.py aguarda control.ready antes de iniciar dezenas de
  // módulos opcionais. A Promise permanece pendente de propósito. Cada área libera
  // apenas o mínimo necessário e recursos pesados exigem intenção explícita.
  const FEATURE_BUNDLES = {
    organizations: ['organization-normalization-ui.js'],
    projects: [
      'project-provisioning.js',
      'project-builder.js',
      'project-description-profile.js',
      'mobile-project-card-compact.js',
    ],
    tasks: [
      'tasks-lazy-load.js',
    ],
    'task-create': [
      'task-modal.js',
      'task-image-upload.js',
    ],
    'task-advanced': [
      'task-analytics.js',
      'task-failures.js',
    ],
    'task-analysis': [
      'approval-slider.js',
      'analysis-commercial-proposal.js',
      'analysis-failure-actions.js',
      'analysis-incomplete-commercial.js',
    ],
    providers: ['provider-models.js', 'provider-ollama.js'],
    reports: ['reports.js'],
    audit: ['audit-integrity.js'],
  };

  const loadedAssets = new Set();
  const loadingAssets = new Map();

  const idle = () => new Promise(resolve => {
    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(() => resolve(), {timeout: 1400});
    } else {
      window.setTimeout(resolve, 100);
    }
  });

  const sleep = ms => new Promise(resolve => window.setTimeout(resolve, ms));

  function alreadyLoaded(name) {
    return [...document.scripts].some(script => {
      if (!script.src) return false;
      try { return new URL(script.src, location.href).pathname === `/assets/${name}`; }
      catch (_) { return false; }
    });
  }

  function loadAsset(name) {
    if (loadedAssets.has(name) || alreadyLoaded(name)) {
      loadedAssets.add(name);
      return Promise.resolve(true);
    }
    if (loadingAssets.has(name)) return loadingAssets.get(name);

    const task = new Promise(resolve => {
      const script = document.createElement('script');
      script.src = `/assets/${name}?v=20260825-development-safe-v3`;
      script.async = false;
      script.dataset.devpilotFeatureLazy = '1';
      script.onload = () => {
        loadedAssets.add(name);
        loadingAssets.delete(name);
        resolve(true);
      };
      script.onerror = () => {
        loadingAssets.delete(name);
        resolve(false);
      };
      document.body.appendChild(script);
    });
    loadingAssets.set(name, task);
    return task;
  }

  async function loadBundle(view) {
    const names = FEATURE_BUNDLES[view] || [];
    for (const name of names) {
      await idle();
      await loadAsset(name);
      await sleep(180);
    }
    if (view === 'tasks') ensureTaskAdvancedControl();
    return true;
  }

  window.__devpilotLoadFeature = loadBundle;

  function ensureTaskAdvancedControl() {
    const view = document.querySelector('#tasks-view');
    if (!view || view.querySelector('[data-task-advanced-load]')) return;

    const holder = document.createElement('div');
    holder.className = 'task-safe-tools';
    holder.innerHTML = `
      <button type="button" class="ghost" data-task-advanced-load>
        Carregar gráficos e diagnósticos
      </button>
      <small data-task-advanced-status>Carregamento opcional para manter a tela leve.</small>`;

    const head = view.querySelector('.section-head');
    if (head) head.appendChild(holder);
    else view.prepend(holder);

    const button = holder.querySelector('[data-task-advanced-load]');
    const status = holder.querySelector('[data-task-advanced-status]');
    button.addEventListener('click', async () => {
      if (button.dataset.loaded === '1') return;
      button.disabled = true;
      button.textContent = 'Carregando recursos avançados…';
      status.textContent = 'Carregando em etapas para não bloquear a interface.';
      await loadBundle('task-advanced');
      button.dataset.loaded = '1';
      button.textContent = 'Gráficos e diagnósticos carregados';
      status.textContent = 'Recursos avançados ativos nesta sessão.';
      if (typeof renderTasks === 'function') renderTasks();
      if (typeof window.renderTaskAnalytics === 'function') window.renderTaskAnalytics();
    });
  }

  function installFeatureLazyLoading() {
    if (document.documentElement.dataset.featureLazyInstalled === '1') return;
    document.documentElement.dataset.featureLazyInstalled = '1';

    document.addEventListener('click', event => {
      const nav = event.target.closest?.('.nav[data-view]');
      if (nav) void loadBundle(String(nav.dataset.view || ''));

      const opener = event.target.closest?.('[data-open="task-modal"]');
      if (opener) void loadBundle('task-create');

      const projectBuilder = event.target.closest?.('[data-project-builder-open]');
      if (projectBuilder) void loadBundle('projects');

      const taskLog = event.target.closest?.('.task-log-link');
      if (taskLog && taskLog.dataset.analysisReady !== '1') {
        event.preventDefault();
        event.stopImmediatePropagation();
        taskLog.dataset.analysisReady = 'loading';
        void (async () => {
          await loadBundle('task-analysis');
          taskLog.dataset.analysisReady = '1';
          taskLog.click();
        })();
      }
    }, true);
  }

  function setAssistantPresentation(enabled, reason = '') {
    document.documentElement.dataset.devpilotChatEnabled = enabled ? 'true' : 'false';

    const heroButton = document.querySelector('#voice-hero');
    const dock = document.querySelector('.voice-dock');
    const dockButton = document.querySelector('#voice-dock');
    const modal = document.querySelector('#voice-modal');
    const pulse = document.querySelector('.pulse-card');

    if (heroButton) {
      heroButton.hidden = !enabled;
      heroButton.disabled = !enabled;
      heroButton.setAttribute('aria-disabled', enabled ? 'false' : 'true');
    }
    if (dock) dock.hidden = !enabled;
    if (dockButton) {
      dockButton.disabled = !enabled;
      dockButton.setAttribute('aria-disabled', enabled ? 'false' : 'true');
    }
    if (!enabled && modal?.open) modal.close();

    if (pulse) {
      pulse.dataset.chatControlState = enabled ? 'enabled' : 'disabled';
      const strong = pulse.querySelector('strong');
      const small = pulse.querySelector('small');
      if (strong) strong.textContent = enabled ? 'Assistente disponível' : 'Chat desligado';
      if (small) small.textContent = enabled
        ? 'Toque para iniciar um comando de voz'
        : (reason || 'Controle central do Super Admin');
    }

    document.dispatchEvent(new CustomEvent('devpilot:chat-control-changed', {
      detail: {enabled, reason},
    }));
  }

  function applyControl(data) {
    control.enabled = Boolean(data?.enabled);
    control.reason = String(data?.reason || '').trim();
    control.source = String(data?.source || 'stored');
    control.updatedAt = data?.updated_at || null;
    setAssistantPresentation(control.enabled, control.reason);
    renderControlView();
  }

  async function request(path, options = {}) {
    const response = await fetch(`/api${path}`, {
      ...options,
      cache: 'no-store',
      headers: {...headers(), ...(options.headers || {})},
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data?.detail === 'string' ? data.detail : `HTTP ${response.status}`;
      throw new Error(detail);
    }
    return data;
  }

  async function refreshControl() {
    try {
      const data = await request('/chat/control');
      applyControl(data);
    } catch (_) {
      applyControl({
        enabled: false,
        reason: 'Estado do chat indisponível; mantido desligado por segurança.',
        source: 'fail-closed',
      });
    }
    return control;
  }

  async function currentRole() {
    const immediate = typeof state !== 'undefined'
      ? String(state.currentUser?.role || '').toUpperCase()
      : '';
    if (immediate) return immediate;
    try {
      const user = await request('/auth/me');
      return String(user?.role || '').toUpperCase();
    } catch (_) {
      return '';
    }
  }

  function injectStyles() {
    if (document.querySelector('style[data-chat-control-style]')) return;
    const style = document.createElement('style');
    style.dataset.chatControlStyle = '1';
    style.textContent = `
      .chat-control-shell{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(260px,.7fr);gap:18px}
      .chat-control-card{padding:20px;border:1px solid var(--line);border-radius:16px;background:var(--surface,#0f1b2d)}
      .chat-control-status{display:flex;align-items:center;gap:10px;margin:12px 0 18px}
      .chat-control-dot{width:12px;height:12px;border-radius:50%;background:#ff5d6c;box-shadow:0 0 14px #ff5d6c88}
      .chat-control-card[data-enabled="true"] .chat-control-dot{background:#35e58a;box-shadow:0 0 14px #35e58a88}
      .chat-control-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
      .chat-control-reason{width:100%;min-height:82px;resize:vertical}
      .chat-control-note{color:var(--muted);font-size:12px;line-height:1.5}
      .task-safe-tools{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:10px}
      .task-safe-tools small{color:var(--muted);font-size:11px}
      html[data-devpilot-chat-enabled="false"] #voice-modal{display:none!important}
      @media(max-width:760px){.chat-control-shell{grid-template-columns:1fr}.task-safe-tools{align-items:stretch}.task-safe-tools button{width:100%}}
    `;
    document.head.appendChild(style);
  }

  function showControlView(nav, section) {
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === nav));
    const title = document.querySelector('#page-title');
    if (title) title.textContent = 'Controle do chat';
    renderControlView();
  }

  function ensureSuperAdminView() {
    if (document.querySelector('#chat-control-view')) return;
    const navRoot = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!navRoot || !main) return;

    const nav = document.createElement('button');
    nav.type = 'button';
    nav.className = 'nav';
    nav.dataset.view = 'chat-control';
    nav.dataset.superAdmin = 'true';
    nav.dataset.chatControlNav = '1';
    nav.textContent = 'Controle do chat';

    const section = document.createElement('section');
    section.className = 'view';
    section.id = 'chat-control-view';
    section.innerHTML = `
      <div class="section-head"><p>Interruptor global do assistente conversacional. Somente o Super Admin pode alterar este estado.</p></div>
      <div class="chat-control-shell">
        <article class="chat-control-card" data-chat-control-card>
          <span class="eyebrow">CONTROLE GLOBAL</span>
          <h2>Chat do DevPilot</h2>
          <div class="chat-control-status"><span class="chat-control-dot"></span><strong data-chat-control-label>DESLIGADO</strong></div>
          <label>Motivo / observação
            <textarea class="chat-control-reason" data-chat-control-reason maxlength="500" placeholder="Ex.: manutenção, diagnóstico de desempenho, economia de recursos..."></textarea>
          </label>
          <div class="chat-control-actions">
            <button type="button" class="ghost" data-chat-control-off>Desligar chat</button>
            <button type="button" class="primary" data-chat-control-on>Ligar chat</button>
          </div>
        </article>
        <article class="chat-control-card">
          <span class="eyebrow">BOOT SEGURO</span>
          <h3>Recursos sob demanda</h3>
          <p class="chat-control-note">A Visão geral carrega somente o núcleo. Desenvolvimento abre primeiro em modo leve; gráficos, diagnósticos e análise avançada só são ativados por ação explícita.</p>
          <p class="chat-control-note">Chat e voz continuam desligados quando o interruptor global estiver OFF.</p>
        </article>
      </div>`;

    navRoot.appendChild(nav);
    main.appendChild(section);
    nav.addEventListener('click', () => showControlView(nav, section));
    section.querySelector('[data-chat-control-off]')?.addEventListener('click', () => updateControl(false));
    section.querySelector('[data-chat-control-on]')?.addEventListener('click', () => updateControl(true));
    renderControlView();
  }

  function renderControlView() {
    const card = document.querySelector('[data-chat-control-card]');
    if (!card) return;
    card.dataset.enabled = control.enabled ? 'true' : 'false';
    const label = card.querySelector('[data-chat-control-label]');
    const reason = card.querySelector('[data-chat-control-reason]');
    const off = card.querySelector('[data-chat-control-off]');
    const on = card.querySelector('[data-chat-control-on]');
    if (label) label.textContent = control.enabled ? 'LIGADO' : 'DESLIGADO';
    if (reason && document.activeElement !== reason) reason.value = control.reason || '';
    if (off) off.disabled = !control.enabled;
    if (on) on.disabled = control.enabled;
  }

  async function updateControl(enabled) {
    const reason = String(document.querySelector('[data-chat-control-reason]')?.value || '').trim();
    const buttons = document.querySelectorAll('[data-chat-control-off],[data-chat-control-on]');
    buttons.forEach(button => { button.disabled = true; });
    try {
      const data = await request('/super-admin/chat/control', {
        method: 'PUT',
        body: JSON.stringify({enabled, reason}),
      });
      applyControl(data);
      if (typeof toast === 'function') toast(enabled ? 'Chat ligado pelo Super Admin' : 'Chat desligado pelo Super Admin');
      window.setTimeout(() => window.location.reload(), 350);
    } catch (error) {
      if (typeof toast === 'function') toast(error.message || 'Falha ao alterar o chat');
      renderControlView();
    }
  }

  async function initialize() {
    injectStyles();
    installFeatureLazyLoading();
    await refreshControl();
    if (await currentRole() === 'SUPER_ADMIN') ensureSuperAdminView();
    document.documentElement.dataset.devpilotSafeBoot = 'true';
    document.dispatchEvent(new CustomEvent('devpilot:safe-core-ready'));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once: true});
  } else {
    void initialize();
  }
})();
