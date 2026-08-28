/* Minimal shared runtime for the standalone game document. */
'use strict';

const GAME_TASK_LIMIT = 80;
const API_TIMEOUT_MS = 15000;
const inflightGets = new Map();

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
  window.setTimeout(() => element.classList.remove('show'), 3200);
}

function errorDetail(data) {
  if (typeof data?.detail === 'string') return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map(item => item.msg || 'Entrada inválida').join(' · ');
  return 'Falha na operação';
}

function normalizeGamePath(path) {
  const value = String(path || '');
  if (!value.startsWith('/tasks?')) return value;

  const [pathname, query = ''] = value.split('?', 2);
  const params = new URLSearchParams(query);
  const requestedLimit = Number(params.get('limit') || GAME_TASK_LIMIT);
  if (!Number.isFinite(requestedLimit) || requestedLimit > GAME_TASK_LIMIT) {
    params.set('limit', String(GAME_TASK_LIMIT));
  }
  return `${pathname}?${params.toString()}`;
}

async function requestApi(path, options = {}) {
  const normalizedPath = normalizeGamePath(path);
  const headers = {Authorization: `Bearer ${state.token}`, ...options.headers};
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  try {
    const response = await fetch(`/api${normalizedPath}`, {
      ...options,
      headers,
      cache: options.cache || 'no-store',
      signal: options.signal || controller.signal,
    });
    if (response.status === 401) {
      localStorage.removeItem('devpilot-token');
      document.getElementById('auth-modal')?.showModal?.();
      throw new Error('Autenticação necessária');
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorDetail(data));
    return data;
  } catch (error) {
    if (error?.name === 'AbortError') throw new Error('Servidor demorou para responder');
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

function api(path, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();
  const normalizedPath = normalizeGamePath(path);
  if (method !== 'GET') return requestApi(normalizedPath, options);

  const key = normalizedPath;
  if (inflightGets.has(key)) return inflightGets.get(key);

  const request = requestApi(normalizedPath, options).finally(() => inflightGets.delete(key));
  inflightGets.set(key, request);
  return request;
}

function status(value) {
  const normalized = String(value || '').replaceAll('_', ' ');
  return `<span class="status ${esc(value)}">${esc(normalized)}</span>`;
}

// build-game.js expects this symbol because it also supports the dashboard.
// In standalone mode the document already owns the game view, so navigation is a no-op.
function showView() {}
