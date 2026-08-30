(() => {
  'use strict';

  const startedAt = Date.now();
  const seenKey = 'devpilot-token-usage-seen-v1';
  const POLL_INTERVAL_MS = 15000;
  let seen = new Set();
  let pollTimer = null;
  let balloonTimer = null;

  try {
    const stored = JSON.parse(sessionStorage.getItem(seenKey) || '[]');
    if (Array.isArray(stored)) seen = new Set(stored.slice(-100));
  } catch (_) {}

  const format = value => Number(value || 0).toLocaleString('pt-BR');
  const formatUsd = value => Number(value || 0).toLocaleString('pt-BR', {style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 4});
  const formatBrl = value => value == null ? '—' : Number(value || 0).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL', minimumFractionDigits: 2, maximumFractionDigits: 4});
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
      .token-admin-metric small{display:block;margin-top:5px;color:var(--muted,#8ea0b7)}
      .token-admin-metric.warn{border-color:rgba(245,158,11,.55)}
      .token-admin-metric.danger{border-color:rgba(239,68,68,.65)}
      .token-admin-table{width:100%;border-collapse:collapse}
      .token-admin-table th,.token-admin-table td{padding:11px 10px;text-align:left;white-space:nowrap;border-bottom:1px solid rgba(128,160,200,.12)}
      .token-admin-table th{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted,#8ea0b7)}
      .token-admin-table td:first-child{white-space:normal;min-width:180px}
      .token-admin-recent{display:grid;gap:8px}
      .token-admin-event{display:grid;grid-template-columns:minmax(180px,1.5fr) 1fr 1fr auto;gap:12px;align-items:center;padding:11px 12px;border-radius:12px;background:rgba(128,160,200,.06)}
      .token-admin-event small{color:var(--muted,#8ea0b7)}
      .token-cost-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
      .token-budget-form{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:10px;align-items:end}
      .token-budget-form label{display:grid;gap:6px;font-size:12px;color:var(--muted,#8ea0b7)}
      .token-budget-form input{width:100%}
      .token-budget-switch{display:flex!important;align-items:center;gap:8px;padding-bottom:9px}
      .token-budget-switch input{width:auto}
      .token-price-status{font-size:11px;padding:3px 7px;border-radius:999px;background:rgba(128,160,200,.12)}
      .token-price-status.unpriced{background:rgba(245,158,11,.14)}
      @media(max-width:1100px){.token-cost-grid{grid-template-columns:1fr}.token-budget-form{grid-template-columns:repeat(2,minmax(120px,1fr))}}
      @media(max-width:900px){.token-admin-metrics{grid-template-columns:repeat(2,minmax(120px,1fr))}.token-admin-event{grid-template-columns:1fr 1fr}.token-admin-event time{grid-column:1/-1}.token-admin-table-wrap{overflow:auto}}
      @media(max-width:640px){.token-usage-balloon{left:12px;bottom:78px;max-width:calc(100vw - 24px)}.token-admin-metrics{grid-template-columns:1fr 1fr}.token-budget-form{grid-template-columns:1fr}}
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
    if (document.hidden) return;
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
    if (title) title.textContent = 'Tokens e custos de IA';
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
    button.textContent = 'Custos IA';
    const auditButton = nav.querySelector('[data-view="audit"]');
    nav.insertBefore(button, auditButton || null);

    const section = document.createElement('section');
    section.className = 'view';
    section.id = 'token-usage-view';
    section.innerHTML = `
      <div class="token-admin-shell">
        <div class="section-head token-admin-toolbar">
          <div><p>Tokens reais, custo financeiro versionado e limites de segurança por consumo.</p></div>
          <label>Período
            <select id="token-admin-days">
              <option value="7">7 dias</option>
              <option value="30" selected>30 dias</option>
              <option value="90">90 dias</option>
              <option value="365">365 dias</option>
            </select>
          </label>
        </div>
        <div class="token-admin-metrics" id="cost-admin-metrics"></div>
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">PROTEÇÃO FINANCEIRA</span><h3>Orçamento global de IA</h3></div></div>
          <form class="token-budget-form" id="token-workspace-budget">
            <label>Limite diário (US$)<input type="number" min="0" step="0.01" id="budget-daily" value="0"></label>
            <label>Limite mensal (US$)<input type="number" min="0" step="0.01" id="budget-monthly" value="0"></label>
            <label>Alerta em %<input type="number" min="1" max="100" step="1" id="budget-warning" value="80"></label>
            <label class="token-budget-switch"><input type="checkbox" id="budget-hard-stop"> Bloquear ao atingir limite</label>
            <button class="primary" type="submit">Salvar orçamento</button>
          </form>
          <div id="budget-status" class="muted" style="margin-top:10px"></div>
        </article>
        <div class="token-cost-grid">
          <article class="panel">
            <div class="panel-title"><div><span class="eyebrow">CUSTO POR PROJETO</span><h3>Onde a IA está gastando</h3></div></div>
            <div class="token-admin-table-wrap"><table class="token-admin-table"><thead><tr><th>Projeto</th><th>Custo</th><th>Eventos</th><th>Sem preço</th></tr></thead><tbody id="cost-admin-projects"></tbody></table></div>
          </article>
          <article class="panel">
            <div class="panel-title"><div><span class="eyebrow">CUSTO POR MODELO</span><h3>Provedores e modelos</h3></div></div>
            <div class="token-admin-table-wrap"><table class="token-admin-table"><thead><tr><th>Modelo</th><th>Custo</th><th>Eventos</th><th>Sem preço</th></tr></thead><tbody id="cost-admin-models"></tbody></table></div>
          </article>
        </div>
        <div class="token-admin-metrics" id="token-admin-metrics"></div>
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">TOKENS POR USUÁRIO</span><h3>Consumo acumulado</h3></div></div>
          <div class="token-admin-table-wrap"><table class="token-admin-table"><thead><tr><th>Usuário</th><th>Total</th><th>Entrada</th><th>Saída</th><th>Cache</th><th>Eventos</th><th>Último uso</th></tr></thead><tbody id="token-admin-users"></tbody></table></div>
        </article>
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">LEDGER FINANCEIRO</span><h3>Últimos custos</h3></div></div>
          <div class="token-admin-recent" id="cost-admin-recent"></div>
        </article>
        <article class="panel">
          <div class="panel-title"><div><span class="eyebrow">TOKENS</span><h3>Últimos consumos</h3></div></div>
          <div class="token-admin-recent" id="token-admin-recent"></div>
        </article>
      </div>`;
    const auditView = document.getElementById('audit-view');
    main.insertBefore(section, auditView || null);
    button.addEventListener('click', () => activateAdminView(button));
    section.querySelector('#token-admin-days')?.addEventListener('change', loadAdminSummary);
    section.querySelector('#token-workspace-budget')?.addEventListener('submit', saveWorkspaceBudget);
  }

  function renderBudget(costData) {
    const section = document.getElementById('token-usage-view');
    if (!section) return;
    const budget = (costData.budgets || []).find(item => item.scope_type === 'workspace');
    section.querySelector('#budget-daily').value = Number(budget?.daily_limit_usd || 0);
    section.querySelector('#budget-monthly').value = Number(budget?.monthly_limit_usd || 0);
    section.querySelector('#budget-warning').value = Number(budget?.warning_percent || 80);
    section.querySelector('#budget-hard-stop').checked = Boolean(budget?.hard_stop);
    const status = section.querySelector('#budget-status');
    if (!budget) {
      status.textContent = 'Nenhum limite global configurado. O ledger continua registrando os custos normalmente.';
      return;
    }
    const dailyPct = Math.round(Number(budget.daily_ratio || 0) * 100);
    const monthlyPct = Math.round(Number(budget.monthly_ratio || 0) * 100);
    status.textContent = `Hoje: ${formatUsd(budget.daily_spent_usd || 0)} (${dailyPct}%) · Mês: ${formatUsd(budget.monthly_spent_usd || 0)} (${monthlyPct}%)${budget.blocked ? ' · BLOQUEADO' : budget.warning ? ' · ALERTA' : ''}`;
  }

  async function saveWorkspaceBudget(event) {
    event.preventDefault();
    const section = document.getElementById('token-usage-view');
    if (!section) return;
    try {
      await api('/token-usage/admin/budgets', {
        method: 'PUT',
        body: JSON.stringify({
          scope_type: 'workspace',
          scope_id: '',
          daily_limit_usd: Number(section.querySelector('#budget-daily').value || 0),
          monthly_limit_usd: Number(section.querySelector('#budget-monthly').value || 0),
          warning_percent: Number(section.querySelector('#budget-warning').value || 80),
          hard_stop: Boolean(section.querySelector('#budget-hard-stop').checked),
        }),
      });
      if (typeof toast === 'function') toast('Orçamento de IA salvo');
      await loadAdminSummary();
    } catch (error) {
      if (typeof toast === 'function') toast(error.message || 'Falha ao salvar orçamento');
    }
  }

  function renderCostSummary(data) {
    const section = document.getElementById('token-usage-view');
    if (!section) return;
    const totals = data.totals || {};
    const coverageClass = Number(totals.unpriced_events || 0) > 0 ? 'warn' : '';
    section.querySelector('#cost-admin-metrics').innerHTML = [
      ['Custo', formatUsd(totals.cost_usd), data.usd_brl_rate ? formatBrl(totals.cost_brl) : 'USD autoritativo', ''],
      ['Cobertura', `${Number(totals.coverage_percent || 0).toLocaleString('pt-BR')}%`, `${format(totals.priced_events)} precificados`, coverageClass],
      ['Sem preço', format(totals.unpriced_events), 'visíveis, não somados ao custo', coverageClass],
      ['Eventos IA', format(totals.events), `preços ${esc(data.pricing_version || '')}`, ''],
      ['Câmbio', data.usd_brl_rate ? `R$ ${Number(data.usd_brl_rate).toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 4})}` : 'Não definido', 'DEVPILOT_USD_BRL_RATE', ''],
    ].map(([label, value, small, cls]) => `<div class="token-admin-metric ${cls || ''}"><span>${label}</span><strong>${value}</strong><small>${small || ''}</small></div>`).join('');

    section.querySelector('#cost-admin-projects').innerHTML = (data.by_project || []).map(item => `
      <tr><td><strong>${esc(item.project_name)}</strong></td><td>${formatUsd(item.cost_usd)}</td><td>${format(item.events)}</td><td>${format(item.unpriced_events)}</td></tr>
    `).join('') || '<tr><td colspan="4" class="empty">Nenhum custo registrado.</td></tr>';

    section.querySelector('#cost-admin-models').innerHTML = (data.by_model || []).map(item => `
      <tr><td><strong>${esc(item.model)}</strong><br><small>${esc(item.provider)}</small></td><td>${formatUsd(item.cost_usd)}</td><td>${format(item.events)}</td><td>${format(item.unpriced_events)}</td></tr>
    `).join('') || '<tr><td colspan="4" class="empty">Nenhum modelo registrado.</td></tr>';

    section.querySelector('#cost-admin-recent').innerHTML = (data.recent || []).map(item => `
      <div class="token-admin-event"><div><strong>${esc(item.project_name)}</strong><br><small>${esc(item.user_name)} · ${esc(item.operation)}</small></div><div>${esc(item.provider)} · ${esc(item.model)}<br><span class="token-price-status ${item.pricing_status === 'priced' ? '' : 'unpriced'}">${item.pricing_status === 'priced' ? 'precificado' : 'sem preço'}</span></div><strong>${item.pricing_status === 'priced' ? formatUsd(item.cost_usd) : `${format(item.billable_quantity)} ${esc(item.billable_unit)}`}</strong><time>${new Date(item.created_at).toLocaleString('pt-BR')}</time></div>
    `).join('') || '<div class="empty">Nenhum custo registrado.</div>';

    renderBudget(data);
  }

  function renderTokenSummary(data, projectNames = new Map()) {
    const section = document.getElementById('token-usage-view');
    if (!section) return;
    const totals = data.totals || {};
    section.querySelector('#token-admin-metrics').innerHTML = [
      ['Tokens', format(totals.total_tokens)],
      ['Entrada', format(totals.input_tokens)],
      ['Saída', format(totals.output_tokens)],
      ['Cache', format(totals.cached_input_tokens)],
      ['Consumos', format(totals.events)],
    ].map(([label, value]) => `<div class="token-admin-metric"><span>${label}</span><strong>${value}</strong></div>`).join('');

    section.querySelector('#token-admin-users').innerHTML = (data.by_user || []).map(item => `
      <tr><td><strong>${esc(item.name || item.email || 'Sistema / legado')}</strong>${item.email && item.name !== item.email ? `<br><small>${esc(item.email)}</small>` : ''}</td><td><strong>${format(item.total_tokens)}</strong></td><td>${format(item.input_tokens)}</td><td>${format(item.output_tokens)}</td><td>${format(item.cached_input_tokens)}</td><td>${format(item.events)}</td><td>${item.last_used_at ? new Date(item.last_used_at).toLocaleString('pt-BR') : '—'}</td></tr>
    `).join('') || '<tr><td colspan="7" class="empty">Nenhum consumo registrado no período.</td></tr>';

    section.querySelector('#token-admin-recent').innerHTML = (data.recent || []).slice(0, 30).map(item => `
      <div class="token-admin-event"><div><strong>${esc(item.project_id ? (projectNames.get(String(item.project_id)) || 'Projeto não identificado') : 'Sem projeto')}</strong><br><small>${esc(item.user_name || item.user_email || 'Sistema / legado')} · ${esc(item.operation)}</small></div><div>${esc(item.provider)} · ${esc(item.model)}</div><strong>${format(item.total_tokens)} tokens</strong><time>${new Date(item.created_at).toLocaleString('pt-BR')}</time></div>
    `).join('') || '<div class="empty">Nenhum consumo registrado.</div>';
  }

  async function loadAdminSummary() {
    const section = document.getElementById('token-usage-view');
    if (!section || !section.classList.contains('active')) return;
    const days = Number(section.querySelector('#token-admin-days')?.value || 30);
    try {
      const [tokenData, costData] = await Promise.all([
        api(`/token-usage/admin/summary?days=${days}`),
        api(`/token-usage/admin/cost-summary?days=${days}`),
      ]);
      const projectNames = new Map(
        (costData.by_project || [])
          .filter(item => item.project_id)
          .map(item => [String(item.project_id), item.project_name])
      );
      renderTokenSummary(tokenData, projectNames);
      renderCostSummary(costData);
    } catch (error) {
      if (typeof toast === 'function') toast(error.message || 'Falha ao carregar custos de IA');
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
    pollTimer = setInterval(pollUsage, POLL_INTERVAL_MS);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();

  window.addEventListener('beforeunload', () => {
    if (pollTimer) clearInterval(pollTimer);
  }, {once: true});
})();