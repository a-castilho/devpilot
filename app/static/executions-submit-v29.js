(() => {
  'use strict';

  if (window.__devpilotCanonicalExecutionSubmitV30) return;
  if (window.__devpilotExecutionsSubmitV29) return;
  window.__devpilotExecutionsSubmitV29 = true;

  const qs = (selector, root = document) => root.querySelector(selector);
  const handled = new WeakSet();

  function notify(message) {
    if (typeof window.toast === 'function') {
      window.toast(message);
      return;
    }
    const node = qs('#toast');
    if (!node) return;
    node.textContent = message;
    node.classList.add('show');
    window.setTimeout(() => node.classList.remove('show'), 4200);
  }

  function detailMessage(body, status) {
    if (typeof body?.detail === 'string') return body.detail;
    if (Array.isArray(body?.detail)) {
      return body.detail.map(item => item?.msg || 'Entrada inválida').join(' · ');
    }
    return `Não foi possível salvar a execução${status ? ` (HTTP ${status})` : ''}`;
  }

  function visibleContext(value) {
    const text = String(value || '').trim();
    const marker = 'Contexto do usuário:';
    const index = text.lastIndexOf(marker);
    return index >= 0 ? text.slice(index + marker.length).trim() : text;
  }

  function automaticTitle(prompt) {
    const text = visibleContext(prompt)
      .replace(/^[-#*\s]+/, '')
      .replace(/\s+/g, ' ')
      .trim();
    if (!text) return 'Nova execução';
    return text.length > 88 ? `${text.slice(0, 85).trim()}…` : text;
  }

  async function apiJson(path, options = {}) {
    const token = String(localStorage.getItem('devpilot-token') || '');
    if (!token) throw new Error('Autenticação necessária para salvar a execução.');

    const response = await fetch(`/api${path}`, {
      ...options,
      cache: 'no-store',
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options.body ? {'Content-Type': 'application/json'} : {}),
        ...(options.headers || {}),
      },
    });

    const body = await response.json().catch(() => ({}));
    if (response.status === 401) {
      localStorage.removeItem('devpilot-token');
      qs('#auth-modal')?.showModal?.();
      throw new Error('Autenticação necessária');
    }
    if (!response.ok) throw new Error(detailMessage(body, response.status));
    return body;
  }

  async function verifyCreated(id) {
    if (!id) return false;
    try {
      const detail = await apiJson(`/ui/tasks/${encodeURIComponent(id)}`);
      return String(detail?.id || '') === String(id);
    } catch (_) {
      try {
        const list = await apiJson('/ui/tasks?limit=50');
        return Array.isArray(list) && list.some(item => String(item?.id || '') === String(id));
      } catch (_) {
        return false;
      }
    }
  }

  async function refreshList() {
    try {
      if (typeof window.devpilotNavigate === 'function') {
        await window.devpilotNavigate('tasks', {history: true});
      } else {
        qs('.nav[data-view="tasks"]')?.click?.();
      }
    } catch (_) {}

    window.setTimeout(() => {
      if (typeof window.loadAllTasks === 'function') {
        void window.loadAllTasks(true, 20);
      } else {
        qs('#tasks-v9-refresh')?.click?.();
      }
    }, 100);
  }

  async function save(form) {
    if (window.__devpilotCanonicalExecutionSubmitV30) return;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.dataset.executionSubmittingV29 === '1') return;

    const modal = form.closest('dialog');
    const submit = qs('#task-submit', form) || qs('[type="submit"]', form);
    const originalText = submit?.textContent || 'Registrar execução';
    const data = new FormData(form);

    const projectId = String(data.get('project_id') || '').trim();
    const prompt = String(data.get('prompt') || '').trim();
    const rawTitle = String(data.get('title') || '').trim();
    const title = rawTitle || automaticTitle(prompt);

    if (!projectId) {
      notify('Selecione um projeto para salvar a execução.');
      qs('[name="project_id"]', form)?.focus?.();
      return;
    }
    if (!visibleContext(prompt)) {
      notify('Descreva o que deve ser executado.');
      qs('[name="prompt"]', form)?.focus?.();
      return;
    }

    const priorityNumber = Number(data.get('priority') || 50);
    const payload = {
      project_id: projectId,
      title,
      prompt,
      priority: Number.isFinite(priorityNumber) ? Math.max(0, Math.min(100, priorityNumber)) : 50,
      requires_approval: data.get('requires_approval') === 'on',
      source: modal?.dataset.taskSource || 'dashboard',
    };

    form.dataset.executionSubmittingV29 = '1';
    if (submit) {
      submit.disabled = true;
      submit.setAttribute('aria-busy', 'true');
      submit.textContent = 'Salvando execução…';
    }

    try {
      const created = await apiJson('/tasks', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      const id = String(created?.id || '');
      if (!id) throw new Error('O servidor não retornou o identificador da execução salva.');

      const persisted = await verifyCreated(id);
      if (!persisted) {
        throw new Error('A API respondeu sucesso, mas a execução não pôde ser confirmada após a gravação.');
      }

      modal?.close?.();
      form.reset();
      if (modal) delete modal.dataset.taskSource;

      document.dispatchEvent(new CustomEvent('devpilot:execution-created', {
        detail: {execution: created, persisted: true},
      }));

      notify('Execução salva com sucesso.');
      await refreshList();
    } catch (error) {
      console.error('[DevPilot] Falha ao salvar execução', error);
      notify(error?.message || 'Não foi possível salvar a execução.');
    } finally {
      delete form.dataset.executionSubmittingV29;
      if (submit) {
        submit.disabled = false;
        submit.removeAttribute('aria-busy');
        submit.textContent = /tarefa|desenvolvimento|análise/i.test(originalText)
          ? 'Salvar execução'
          : (originalText || 'Salvar execução');
      }
    }
  }

  function prepareForm(form) {
    if (window.__devpilotCanonicalExecutionSubmitV30) return;
    if (!(form instanceof HTMLFormElement)) return;
    form.noValidate = true;
    form.setAttribute('novalidate', 'novalidate');
    form.querySelectorAll('[required]').forEach(field => field.removeAttribute('required'));
    const submit = qs('#task-submit', form) || qs('[type="submit"]', form);
    if (submit && /tarefa|desenvolvimento|análise|registrar/i.test(submit.textContent || '')) {
      submit.textContent = 'Salvar execução';
    }
    form.dataset.executionSubmitV29 = '1';
  }

  function intercept(event) {
    if (window.__devpilotCanonicalExecutionSubmitV30) return;
    const form = event.target instanceof HTMLFormElement
      ? event.target
      : event.target?.closest?.('form');
    if (!form || form.id !== 'task-form') return;

    event.preventDefault();
    event.stopImmediatePropagation();

    if (handled.has(event)) return;
    handled.add(event);
    prepareForm(form);
    void save(form);
  }

  document.addEventListener('submit', intercept, true);

  document.addEventListener('click', event => {
    if (window.__devpilotCanonicalExecutionSubmitV30) return;
    const button = event.target?.closest?.('#task-submit');
    if (!button) return;
    const form = button.form || qs('#task-form');
    if (form) prepareForm(form);
  }, true);

  function install() {
    if (window.__devpilotCanonicalExecutionSubmitV30) return;
    const form = qs('#task-form');
    if (form) prepareForm(form);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, {once: true});
  } else {
    install();
  }

  document.addEventListener('devpilot:feature-ready', install);
  document.addEventListener('devpilot:dashboard-revealed', install);
  document.addEventListener('devpilot:view-changed', install);
  [100, 400, 900, 1800].forEach(delay => window.setTimeout(install, delay));

  document.documentElement.dataset.devpilotExecutionSubmit = 'v29';
  console.info('[DevPilot] Execução Submit V29 legado ativo');
})();
