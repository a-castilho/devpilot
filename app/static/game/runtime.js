/* Minimal shared runtime for the standalone game document. */
'use strict';

const state = {
  token: localStorage.getItem('devpilot-token') || '',
  projects: [],
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>'\"]/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '\"': '&quot;',
}[char]));

function toast(message) {
  const element = $('#toast');
  if (!element) return;
  element.textContent = message;
  element.classList.add('show');
  window.setTimeout(() => element.classList.remove('show'), 4200);
}

function errorDetail(data, status = 0) {
  if (typeof data?.detail === 'string') return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map(item => item.msg || 'Entrada inválida').join(' · ');
  if (status >= 500) return `O DevPilot encontrou um erro interno (HTTP ${status}).`;
  if (status >= 400) return `A operação foi recusada (HTTP ${status}).`;
  return 'Falha na operação';
}

function networkErrorMessage(error) {
  if (error?.name === 'AbortError') {
    return 'O DevPilot demorou demais para responder. Verifique a conexão e tente novamente.';
  }
  if (navigator.onLine === false) {
    return 'O dispositivo está sem conexão com o DevPilot.';
  }
  return 'Não foi possível conectar ao DevPilot. Verifique se o servidor continua disponível e tente novamente.';
}

async function requestJson(path, options = {}, attempt = 0) {
  const method = String(options.method || 'GET').toUpperCase();
  const controller = options.signal ? null : new AbortController();
  const timeoutId = controller
    ? window.setTimeout(() => controller.abort(), Number(options.timeoutMs || 15000))
    : 0;

  const headers = {
    Authorization: `Bearer ${state.token}`,
    ...(options.headers || {}),
  };

  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }

  let response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      method,
      headers,
      cache: options.cache || 'no-store',
      signal: options.signal || controller?.signal,
    });
  } catch (error) {
    if (timeoutId) window.clearTimeout(timeoutId);

    if (method === 'GET' && attempt === 0 && navigator.onLine !== false) {
      await new Promise(resolve => window.setTimeout(resolve, 300));
      return requestJson(path, options, attempt + 1);
    }

    throw new Error(networkErrorMessage(error));
  }

  if (timeoutId) window.clearTimeout(timeoutId);

  const data = await response.json().catch(() => ({}));

  if (response.status === 401) {
    localStorage.removeItem('devpilot-token');
    state.token = '';
    document.getElementById('auth-modal')?.showModal?.();
    throw new Error('Sua sessão expirou. Volte ao painel e entre novamente.');
  }

  if (!response.ok) {
    if (method === 'GET' && response.status >= 500 && attempt === 0) {
      await new Promise(resolve => window.setTimeout(resolve, 300));
      return requestJson(path, options, attempt + 1);
    }
    throw new Error(errorDetail(data, response.status));
  }

  return data;
}

async function api(path, options = {}) {
  state.token = String(localStorage.getItem('devpilot-token') || state.token || '');
  if (!state.token) {
    document.getElementById('auth-modal')?.showModal?.();
    throw new Error('Autenticação necessária');
  }
  return requestJson(path, options);
}

function status(value) {
  const normalized = String(value || '').replaceAll('_', ' ');
  return `<span class="status ${esc(value)}">${esc(normalized)}</span>`;
}

// build-game.js expects this symbol because it also supports the dashboard.
// In standalone mode the document already owns the game view, so navigation is a no-op.
function showView() {}

window.__devpilotGameApiReady = true;
