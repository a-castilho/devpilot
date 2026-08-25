(() => {
  'use strict';

  const MAX_ERROR_TEXT = 220;
  const TASK_GET_TTL_MS = 5000;
  const TASK_GET_HIDDEN_TTL_MS = 30000;
  const taskReadsInFlight = new Map();
  const taskReadCache = new Map();

  function normalizeErrorDetail(data, raw, status) {
    if (typeof data?.detail === 'string' && data.detail.trim()) return data.detail.trim();
    if (Array.isArray(data?.detail)) {
      const detail = data.detail
        .map(item => item?.msg || item?.message || String(item || ''))
        .filter(Boolean)
        .join(' · ');
      if (detail) return detail;
    }

    for (const key of ['message', 'error', 'title']) {
      if (typeof data?.[key] === 'string' && data[key].trim()) return data[key].trim();
    }

    const text = String(raw || '').replace(/\s+/g, ' ').trim();
    if (text && !/^</.test(text)) return text.slice(0, MAX_ERROR_TEXT);
    return `Falha na operação (HTTP ${status})`;
  }

  function isTaskCollectionRead(path, method) {
    return method === 'GET' && /^\/tasks(?:\?|$)/.test(String(path || ''));
  }

  function clearTaskReadCache() {
    taskReadCache.clear();
  }

  async function performApiRequest(path, options, token) {
    const headers = {'Authorization': `Bearer ${token}`, ...options.headers};
    if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';

    let response;
    try {
      response = await fetch(`/api${path}`, {...options, headers});
    } catch (_) {
      throw new Error('Sem conexão com o DevPilot. Verifique a rede e tente novamente.');
    }

    const raw = await response.text();
    let data = {};
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch (_) {
        data = {};
      }
    }

    if (response.status === 401) {
      document.querySelector('#auth-modal')?.showModal?.();
      throw new Error('Autenticação necessária');
    }
    if (!response.ok) throw new Error(normalizeErrorDetail(data, raw, response.status));
    return data;
  }

  function installDetailedApiErrors() {
    if (typeof api !== 'function' || api.__devpilotDetailedErrors) return;

    const improvedApi = async (path, options = {}) => {
      const token = localStorage.getItem('devpilot-token') || '';
      const method = String(options.method || 'GET').toUpperCase();
      const taskRead = isTaskCollectionRead(path, method);
      const requestKey = taskRead ? `${token}:${path}` : '';

      if (taskRead) {
        const cached = taskReadCache.get(requestKey);
        const ttl = document.hidden ? TASK_GET_HIDDEN_TTL_MS : TASK_GET_TTL_MS;
        if (cached && Date.now() - cached.savedAt < ttl) return cached.data;

        const pending = taskReadsInFlight.get(requestKey);
        if (pending) return pending;
      } else if (method !== 'GET' && /^\/tasks(?:\/|\?|$)/.test(String(path || ''))) {
        clearTaskReadCache();
      }

      const request = performApiRequest(path, options, token);
      if (!taskRead) return request;

      taskReadsInFlight.set(requestKey, request);
      try {
        const data = await request;
        taskReadCache.set(requestKey, {savedAt: Date.now(), data});
        return data;
      } finally {
        if (taskReadsInFlight.get(requestKey) === request) taskReadsInFlight.delete(requestKey);
      }
    };

    improvedApi.__devpilotDetailedErrors = true;
    improvedApi.__devpilotTaskReadCoalescing = true;
    api = improvedApi;
  }

  function installBudgetValidation() {
    document.addEventListener('submit', event => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement) || form.id !== 'token-workspace-budget') return;

      const daily = Number(form.querySelector('#budget-daily')?.value || 0);
      const monthly = Number(form.querySelector('#budget-monthly')?.value || 0);
      if (daily > 0 || monthly > 0) return;

      event.preventDefault();
      event.stopImmediatePropagation();
      const status = document.querySelector('#budget-status');
      if (status) {
        status.textContent = 'Informe um limite diário ou mensal acima de US$ 0 para criar o orçamento.';
        status.dataset.validation = 'error';
      }
      if (typeof toast === 'function') toast('Informe um limite diário ou mensal');
      form.querySelector('#budget-daily')?.focus();
    }, true);
  }

  function installMobileCostStyles() {
    if (document.getElementById('token-usage-mobile-fix-styles')) return;
    const style = document.createElement('style');
    style.id = 'token-usage-mobile-fix-styles';
    style.textContent = `
      #budget-status[data-validation="error"]{color:var(--amber,#ffbb55)}
      @media(max-width:640px){
        .token-cost-grid .token-admin-table-wrap{overflow:visible!important;max-width:100%}
        .token-cost-grid .token-admin-table{display:block;width:100%;min-width:0!important}
        .token-cost-grid .token-admin-table thead{display:none}
        .token-cost-grid .token-admin-table tbody{display:grid;gap:10px;width:100%}
        .token-cost-grid .token-admin-table tr{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:5px 12px;width:100%;padding:12px;border:1px solid rgba(128,160,200,.16);border-radius:12px;background:rgba(128,160,200,.045)}
        .token-cost-grid .token-admin-table td{display:block;min-width:0!important;padding:0!important;border:0!important;white-space:normal!important;overflow-wrap:anywhere}
        .token-cost-grid .token-admin-table td:first-child{grid-column:1/-1;min-width:0!important;margin-bottom:3px}
        .token-cost-grid .token-admin-table td:nth-child(2){font-weight:800}
        .token-cost-grid .token-admin-table td:nth-child(3){text-align:right;color:var(--muted,#8ea0b7)}
        .token-cost-grid .token-admin-table td:nth-child(3)::before{content:'Eventos ';font-size:10px;text-transform:uppercase;letter-spacing:.06em}
        .token-cost-grid .token-admin-table td:nth-child(4){grid-column:1/-1;color:var(--muted,#8ea0b7);font-size:12px}
        .token-cost-grid .token-admin-table td:nth-child(4)::before{content:'Sem preço: ';font-size:10px;text-transform:uppercase;letter-spacing:.06em}
        .token-cost-grid .token-admin-table td.empty{grid-column:1/-1!important;text-align:center!important;padding:18px 8px!important}
      }
      @media(max-width:900px){
        body.mobile-route .toast{left:12px!important;right:12px!important;bottom:calc(150px + env(safe-area-inset-bottom))!important;z-index:160!important;max-width:none!important}
        body.mobile-route .token-admin-shell{min-width:0;width:100%}
        body.mobile-route .token-cost-grid{min-width:0;width:100%}
      }
    `;
    document.head.appendChild(style);
  }

  installDetailedApiErrors();
  installBudgetValidation();
  installMobileCostStyles();
})();