/* Minimal shared runtime for the standalone game document. */
'use strict';

const state = {
  token: localStorage.getItem('devpilot-token') || '',
  projects: [],
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
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

async function api(path, options = {}) {
  const headers = {Authorization: `Bearer ${state.token}`, ...options.headers};
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(`/api${path}`, {...options, headers, cache: options.cache || 'no-store'});
  if (response.status === 401) {
    localStorage.removeItem('devpilot-token');
    document.getElementById('auth-modal')?.showModal?.();
    throw new Error('Autenticação necessária');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(errorDetail(data));
  return data;
}

function status(value) {
  const normalized = String(value || '').replaceAll('_', ' ');
  return `<span class="status ${esc(value)}">${esc(normalized)}</span>`;
}

// build-game.js expects this symbol because it also supports the dashboard.
// In standalone mode the document already owns the game view, so navigation is a no-op.
function showView() {}
