(() => {
  'use strict';

  if (window.__devpilotChatControl?.installed) return;

  let resolveReady;
  const ready = new Promise(resolve => { resolveReady = resolve; });
  const control = window.__devpilotChatControl = {
    installed: true,
    enabled: false,
    reason: 'Chat desligado por padrão pelo controle da plataforma.',
    source: 'default',
    updatedAt: null,
    ready,
  };

  const token = () => localStorage.getItem('devpilot-token') || '';
  const headers = () => ({
    Authorization: `Bearer ${token()}`,
    'Content-Type': 'application/json',
  });

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

  async function refreshControl({settleReady = false} = {}) {
    try {
      const data = await request('/chat/control');
      applyControl(data);
    } catch (_) {
      // Fail closed: if control state cannot be read, chat stays disabled.
      applyControl({
        enabled: false,
        reason: 'Estado do chat indisponível; mantido desligado por segurança.',
        source: 'fail-closed',
      });
    } finally {
      if (settleReady && resolveReady) {
        resolveReady(control);
        resolveReady = null;
      }
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
      html[data-devpilot-chat-enabled="false"] #voice-modal{display:none!important}
      @media(max-width:760px){.chat-control-shell{grid-template-columns:1fr}}
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
          <span class="eyebrow">EFEITO DO INTERRUPTOR</span>
          <h3>Backend + interface</h3>
          <p class="chat-control-note">Desligado: /api/chat e /api/voice/chat recusam novas conversas, os controles de conversa somem da interface e os módulos pesados de chat/voz não entram no boot após recarregar.</p>
          <p class="chat-control-note">Ligado: o Super Admin libera novamente o chat. A página recarrega para inicializar os módulos conversacionais de forma controlada.</p>
          <p class="chat-control-note">Toda alteração do interruptor é registrada na auditoria da plataforma.</p>
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
    await refreshControl({settleReady: true});
    if (await currentRole() === 'SUPER_ADMIN') ensureSuperAdminView();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, {once: true});
  } else {
    void initialize();
  }
})();
