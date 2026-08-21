(() => {
  'use strict';

  const startedAt = Date.now();
  const seenKey = 'devpilot-token-usage-seen-v1';
  let seen = new Set();
  let pollTimer = null;
  let balloonTimer = null;

  try {
    const stored = JSON.parse(sessionStorage.getItem(seenKey) || '[]');
    if (Array.isArray(stored)) seen = new Set(stored.slice(-100));
  } catch (_) {}

  const format = value => Number(value || 0).toLocaleString('pt-BR');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));

  function persistSeen() {
    try {
      sessionStorage.setItem(seenKey, JSON.stringify([...seen].slice(-100)));
    } catch (_) {}
  }

  function injectStyles() {
    if (document.getElementById('token-usage-styles')) return;
    const style = document.createElement('style');
    style.id = 'token-usage-styles';
    style.textContent = `
      .token-usage-balloon{position:fixed;left:18px;bottom:18px;z-index:2800;min-width:220px;max-width:min(340px,calc(100vw - 36px));padding:13px 15px;border:1px solid rgba(117,164,255,.25);border-radius:14px;background:rgba(8,18,34,.96);box-shadow:0 18px 50px rgba(0,0,0,.35);backdrop-filter:blur(12px);color:#eef5ff;opacity:0;transform:translateY(18px);pointer-events:none;transition:opacity .2s ease,transform .2s ease}
      .token-usage-balloon.show{opacity:1;transform:translateY(0)}
      .token-usage-balloon span{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#8fb5ff}
      .token-usage-balloon strong{display:block;margin-top:3px;font-size:21px;line-height:1.15}
      .token-usage-balloon small{display:block;margin-top:5px;color:#aab8ca;line-height:1.35}
      .token-admin-shell{display:grid;gap:18px}
      .token-admin-toolbar{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap}
      .token-admin-toolbar select{min-width:150px}
      .token-admin-metrics{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:12px}
      .token-admin-metric{padding:16px;border-radius:14px;background:var(--panel,#0c1727);border:1px solid rgba(128,160,200,.14)}
      .token-admin-metric span{display:block;font-size:12px;color:var(--muted,#8ea0b7)}
      .token-admin-metric strong{display:block;margin-top:5px;font-size:22px}
      .token-admin-table{width:100%;border-collapse:collapse}
      .token-admin-table th,.token-admin-table td{padding:11px 10px;text-align:left;white-space:nowrap;border-bottom:1px solid rgba(128,160,200,.12)}
      .token-admin-table th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted,#8ea0b7)}
      .token-admin-table td:first-child{white-space:normal;min-width:180px}
      .token-admin-recent{display:grid;gap:8px}
      .token-admin-event{display:grid;grid-template-columns:minmax(180px,1.5fr) 1fr 1fr auto;gap:12px;align-items:center;padding:11px 12px;border-radius:12px;background:rgba(128,160,200,.06)}
      .token-admin-event small{color:var(--muted,#8ea0b7)}
      @media(max-width:900px){.token-admin-metrics{grid-template-columns:repeat(2,minmax(120px,1fr))}.token-admin-event{grid-template-columns:1fr 1fr}.token-admin-event time{grid-column:1/-1}.token-admin-table-wrap{overflow:auto}}
      @media(max-width:640px){.token-usage-balloon{left:12px;bottom:78px;max-width:calc(100vw - 24px)}.token-admin-metrics{grid-template-columns:1fr 1fr}}
    `;
    document.head.appendChild(style);
  }

  function ensureBalloon() {
    let balloon = document.getElementById('token-usage-balloon');
    if (balloon) return balloon;
    balloon = document.createElement('div');
    balloon.id = 'token-usage-balloon';
    balloon.className = 'token-usage-balloon';
    balloon.setAttribute('role', 'status');
    balloon.setAttribute('aria-live', 'polite');
    document.body.appendChild(balloon);
    return balloon;
  }

  function showBalloon(records) {
    if (!records.length) return;
    const totals = records.reduce((acc, item) => {
      acc.input += Number(item.input_tokens || 0);
      acc.output += Number(item.output_tokens || 0);
      acc.cached += Number(item.cached_input_tokens || 0);
      acc.total += Number(item.total_tokens || 0);
      return acc;
    }, {input: 0, output: 0, cached: 0, total: 0});
    if (totals.total <= 0) return;

    const balloon = ensureBalloon();
    balloon.innerHTML = `<span>Tokens gastos</span><strong>${format(totals.total)} tokens</strong><small>Entrada ${format(totals.input)} · Saída ${format(totals.output)}${totals.cached ? ` · Cache ${format(totals.cached)}` : ''}</small>`;
    balloon.classList.add('show');
    clearTimeout(balloonTimer);
    balloonTimer = setTimeout(() => balloon.classList.remove('show'), 5200);
  }

  async function pollUsage() {
    if (typeof api !== 'function') return;
    try {
      const items = await api('/token-usage/me?limit=10');
      const fresh = [];
      for (const item of [...items].reverse()) {
        if (!item?.id || seen.has(item.id)) continue;
        const created = new Date(item.created_at).getTime();
        seen.add(item.id);
        if (seen.size > 100) seen = new Set([...seen].slice(-100));
        if (created >= startedAt - 500) fresh.push(item);
      }
      persistSeen();
      if (fresh.length) showBalloon(fresh);
    } catch (_) {
      // Authentication and provider errors are handled by the primary UI.
    }
  }

  function activateAdminView(button) {
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view.id === 'token-usage-view'));
    document.querySelectorAll('.nav').forEach(nav => nav.classList.toggle('active', nav === button));
    const title = document.getElementById('page-title');
    if (title) title.textContent = 'Gestão de tokens';
    loadAdminSummary();
  }

  function installAdminView() {
    if (document.getElementById('token-usage-view')) return;
    const nav = document.querySelector('.sidebar nav');
    const main = document.querySelector('.shell main');
    if (!nav || !main) return;

    const button = document.createElement('button');
    button.className = 'nav';
    button.type = 'button';
    button.dataset.view = 'token-usage';
    button.textContent = 'Tokens';
    const auditButton = nav.querySelector('[data-view="audit"]');
    nav.insertBefore(button, auditButton || null);

    const section = document.createElement('section');
    section.className = 'view';
    section.id = 'token-usage-view';
    section.innerHTML = `
      <div class="token-admin-shell">
        <div class="section-head token-admin-toolbar">
          <div><p>Consumo real informado pelos provedores, consolidado por usuário.</p></div>
          <label>Período
            <select id="token-admin-days">
              <option value="7">7 dias</option>
              <option value="30" selected>30 dias</option>
              <option value="90">90 dias</option>
              <option value="365">365 dias</option>
            </select>
          </label>
        </div>
        <div class="token-admin-metrics" id="token-admin-metrics"></div>
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">POR USUÁRIO</span><h3>Consumo acumulado</h3></div></div>
          <div class="token-admin-table-wrap"><table class="token-admin-table"><thead><tr><th>Usuário</th><th>Total</th><th>Entrada</th><th>Saída</th><th>Cache</th><th>Eventos</th><th>Último uso</th></tr></thead><tbody id="token-admin-users"></tbody></table></div>
        </article>
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">HISTÓRICO</span><h3>Últimos consumos</h3></div></div>
          <div class="token-admin-recent" id="token-admin-recent"></div>
        </article>
      </div>`;
    const auditView = document.getElementById('audit-view');
    main.insertBefore(section, auditView || null);
    button.addEventListener('click', () => activateAdminView(button));
    section.querySelector('#token-admin-days')?.addEventListener('change', loadAdminSummary);
  }

  async function loadAdminSummary() {
    const section = document.getElementById('token-usage-view');
    if (!section || !section.classList.contains('active')) return;
    const days = Number(section.querySelector('#token-admin-days')?.value || 30);
    try {
      const data = await api(`/token-usage/admin/summary?days=${days}`);
      const totals = data.totals || {};
      section.querySelector('#token-admin-metrics').innerHTML = [
        ['Total', `${format(totals.total_tokens)} tokens`],
        ['Entrada', format(totals.input_tokens)],
        ['Saída', format(totals.output_tokens)],
        ['Cache', format(totals.cached_input_tokens)],
        ['Consumos', format(totals.events)],
      ].map(([label, value]) => `<div class="token-admin-metric"><span>${label}</span><strong>${value}</strong></div>`).join('');

      section.querySelector('#token-admin-users').innerHTML = (data.by_user || []).map(item => `
        <tr><td><strong>${esc(item.name || item.email || 'Sistema / legado')}</strong>${item.email && item.name !== item.email ? `<br><small>${esc(item.email)}</small>` : ''}</td><td><strong>${format(item.total_tokens)}</strong></td><td>${format(item.input_tokens)}</td><td>${format(item.output_tokens)}</td><td>${format(item.cached_input_tokens)}</td><td>${format(item.events)}</td><td>${item.last_used_at ? new Date(item.last_used_at).toLocaleString('pt-BR') : '—'}</td></tr>
      `).join('') || '<tr><td colspan="7" class="empty">Nenhum consumo registrado no período.</td></tr>';

      section.querySelector('#token-admin-recent').innerHTML = (data.recent || []).slice(0, 30).map(item => `
        <div class="token-admin-event"><div><strong>${esc(item.user_name || item.user_email || 'Sistema / legado')}</strong><br><small>${esc(item.operation)}</small></div><div>${esc(item.provider)} · ${esc(item.model)}</div><strong>${format(item.total_tokens)} tokens</strong><time>${new Date(item.created_at).toLocaleString('pt-BR')}</time></div>
      `).join('') || '<div class="empty">Nenhum consumo registrado.</div>';
    } catch (error) {
      if (typeof toast === 'function') toast(error.message || 'Falha ao carregar consumo de tokens');
    }
  }

  async function boot() {
    injectStyles();
    ensureBalloon();
    if (typeof api !== 'function') return;
    try {
      const user = await api('/auth/me');
      if (String(user?.role || '').toUpperCase() === 'SUPER_ADMIN') installAdminView();
    } catch (_) {}
    await pollUsage();
    pollTimer = setInterval(pollUsage, 4000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();

  window.addEventListener('beforeunload', () => {
    if (pollTimer) clearInterval(pollTimer);
  }, {once: true});
})();
