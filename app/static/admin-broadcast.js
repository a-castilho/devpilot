(() => {
  'use strict';

  const ROLE = 'SUPER_ADMIN';
  const POLL_MS = 2500;
  let since = new Date().toISOString();
  let timer = null;
  let polling = false;

  const token = () => localStorage.getItem('devpilot-token') || '';
  const role = () => String((typeof state !== 'undefined' && state.currentUser?.role) || '').toUpperCase();
  const isSuperAdmin = () => role() === ROLE;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  })[char]);

  async function request(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      cache: 'no-store',
      headers: {
        ...(options.body ? {'Content-Type': 'application/json'} : {}),
        ...(token() ? {Authorization: `Bearer ${token()}`} : {}),
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha no canal de mensagens');
    return data;
  }

  function installStyles() {
    if (document.getElementById('admin-broadcast-style')) return;
    const style = document.createElement('style');
    style.id = 'admin-broadcast-style';
    style.textContent = `
      .admin-broadcast-stack{position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:9998;width:min(760px,calc(100vw - 24px));display:grid;gap:8px;pointer-events:none}
      .admin-broadcast-banner{pointer-events:auto;display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:11px;align-items:start;padding:13px 14px;border:1px solid rgba(120,210,255,.34);border-radius:15px;background:rgba(6,17,28,.96);box-shadow:0 18px 45px rgba(0,0,0,.38);backdrop-filter:blur(12px)}
      .admin-broadcast-banner[data-level="success"]{border-color:rgba(91,239,180,.45)}
      .admin-broadcast-banner[data-level="warning"]{border-color:rgba(255,193,92,.52)}
      .admin-broadcast-banner[data-level="critical"]{border-color:rgba(255,100,120,.58)}
      .admin-broadcast-icon{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:rgba(255,255,255,.07);font-weight:900}
      .admin-broadcast-copy strong{display:block;font-size:.8rem;letter-spacing:.06em;text-transform:uppercase}.admin-broadcast-copy p{margin:4px 0 0;white-space:pre-wrap;overflow-wrap:anywhere}.admin-broadcast-copy small{display:block;margin-top:6px;opacity:.68}
      .admin-broadcast-close{border:0;background:transparent;color:inherit;font-size:20px;cursor:pointer;line-height:1}
      .admin-broadcast-launch{position:fixed;right:18px;bottom:84px;z-index:9997;min-height:44px;padding:0 15px;border-radius:999px;border:1px solid rgba(103,232,213,.36);background:#0b1b28;color:#dffefa;font-weight:800;box-shadow:0 14px 34px rgba(0,0,0,.3);cursor:pointer}
      .admin-broadcast-modal{position:fixed;inset:0;z-index:9999;display:grid;place-items:center;padding:18px;background:rgba(0,0,0,.58)}
      .admin-broadcast-modal[hidden]{display:none}.admin-broadcast-card{width:min(560px,100%);padding:18px;border:1px solid rgba(104,230,211,.28);border-radius:18px;background:#07121d;box-shadow:0 26px 70px rgba(0,0,0,.5)}
      .admin-broadcast-card h3{margin:4px 0 7px}.admin-broadcast-card p{margin:0 0 14px;opacity:.72}.admin-broadcast-card textarea,.admin-broadcast-card select{width:100%;box-sizing:border-box;margin-top:8px}.admin-broadcast-card textarea{min-height:130px;resize:vertical}.admin-broadcast-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:14px;flex-wrap:wrap}
      @media(max-width:640px){.admin-broadcast-launch{right:12px;bottom:74px}.admin-broadcast-banner{grid-template-columns:auto minmax(0,1fr) auto}.admin-broadcast-actions>*{flex:1}}
    `;
    document.head.appendChild(style);
  }

  function ensureStack() {
    let stack = document.querySelector('.admin-broadcast-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.className = 'admin-broadcast-stack';
      stack.setAttribute('aria-live', 'assertive');
      stack.setAttribute('aria-relevant', 'additions');
      document.body.appendChild(stack);
    }
    return stack;
  }

  function showBroadcast(item) {
    if (!item?.id || !item.message) return;
    const stack = ensureStack();
    if (stack.querySelector(`[data-broadcast-id="${CSS.escape(String(item.id))}"]`)) return;
    const banner = document.createElement('article');
    banner.className = 'admin-broadcast-banner';
    banner.dataset.broadcastId = String(item.id);
    banner.dataset.level = String(item.level || 'info');
    const date = new Date(item.created_at);
    const when = Number.isNaN(date.getTime()) ? '' : date.toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'});
    banner.innerHTML = `
      <div class="admin-broadcast-icon">${item.level === 'critical' ? '!' : '✦'}</div>
      <div class="admin-broadcast-copy">
        <strong>Mensagem do Super Admin</strong>
        <p>${esc(item.message)}</p>
        <small>${esc(item.sender || 'Super Admin')}${when ? ` · ${esc(when)}` : ''}</small>
      </div>
      <button class="admin-broadcast-close" type="button" aria-label="Fechar mensagem">×</button>`;
    banner.querySelector('.admin-broadcast-close')?.addEventListener('click', () => banner.remove());
    stack.appendChild(banner);
  }

  async function poll() {
    if (polling || !token()) return;
    polling = true;
    try {
      const data = await request(`/api/admin/broadcast?since=${encodeURIComponent(since)}`);
      const items = Array.isArray(data.items) ? data.items : [];
      items.forEach(showBroadcast);
      if (data.server_time) since = new Date(data.server_time).toISOString();
    } catch (error) {
      if (!/401|token|access/i.test(String(error?.message || ''))) console.debug('broadcast poll:', error?.message || error);
    } finally {
      polling = false;
    }
  }

  function ensureComposer() {
    const existingButton = document.querySelector('[data-admin-broadcast-launch]');
    const existingModal = document.querySelector('#admin-broadcast-modal');
    if (!isSuperAdmin()) {
      existingButton?.remove();
      existingModal?.remove();
      return;
    }
    if (existingButton && existingModal) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'admin-broadcast-launch';
    button.dataset.adminBroadcastLaunch = '1';
    button.textContent = '📣 Mensagem global';
    document.body.appendChild(button);

    const modal = document.createElement('div');
    modal.id = 'admin-broadcast-modal';
    modal.className = 'admin-broadcast-modal';
    modal.hidden = true;
    modal.innerHTML = `
      <form class="admin-broadcast-card" id="admin-broadcast-form">
        <span class="eyebrow">SUPER ADMIN · TODOS CONECTADOS</span>
        <h3>Enviar mensagem global</h3>
        <p>A mensagem aparecerá na tela de todos os usuários autenticados que estiverem conectados ao DevPilot.</p>
        <label>Prioridade
          <select name="level">
            <option value="info">Informação</option>
            <option value="success">Sucesso</option>
            <option value="warning">Atenção</option>
            <option value="critical">Crítica</option>
          </select>
        </label>
        <label>Mensagem
          <textarea name="message" maxlength="1200" required placeholder="Digite a mensagem para todos os conectados"></textarea>
        </label>
        <div class="admin-broadcast-actions">
          <button class="ghost" type="button" data-broadcast-cancel>Cancelar</button>
          <button class="primary" type="submit">Enviar para todos</button>
        </div>
      </form>`;
    document.body.appendChild(modal);

    const close = () => { modal.hidden = true; };
    button.addEventListener('click', () => { modal.hidden = false; modal.querySelector('textarea')?.focus(); });
    modal.querySelector('[data-broadcast-cancel]')?.addEventListener('click', close);
    modal.addEventListener('click', event => { if (event.target === modal) close(); });
    modal.querySelector('#admin-broadcast-form')?.addEventListener('submit', async event => {
      event.preventDefault();
      const form = event.currentTarget;
      const submit = form.querySelector('button[type="submit"]');
      const message = String(new FormData(form).get('message') || '').trim();
      const level = String(new FormData(form).get('level') || 'info');
      if (!message) return;
      submit.disabled = true;
      submit.textContent = 'Enviando…';
      try {
        const result = await request('/api/admin/broadcast', {
          method: 'POST',
          body: JSON.stringify({message, level}),
        });
        if (result.broadcast) showBroadcast(result.broadcast);
        form.reset();
        close();
        window.toast?.('Mensagem enviada para todos os usuários conectados.');
      } catch (error) {
        window.toast?.(error?.message || 'Não foi possível enviar a mensagem global.');
      } finally {
        submit.disabled = false;
        submit.textContent = 'Enviar para todos';
      }
    });
  }

  function boot() {
    installStyles();
    ensureStack();
    ensureComposer();
    void poll();
    timer = window.setInterval(() => {
      ensureComposer();
      void poll();
    }, POLL_MS);
    window.addEventListener('beforeunload', () => window.clearInterval(timer), {once:true});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();
})();
