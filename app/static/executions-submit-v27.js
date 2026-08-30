(() => {
  'use strict';

  if (window.__devpilotExecutionsSubmitV27) return;
  window.__devpilotExecutionsSubmitV27 = true;

  const qs = (selector, root = document) => root.querySelector(selector);

  function notify(message) {
    if (typeof window.toast === 'function') {
      window.toast(message);
      return;
    }
    const toast = qs('#toast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    window.setTimeout(() => toast.classList.remove('show'), 3600);
  }

  function errorMessage(data, status) {
    if (typeof data?.detail === 'string') return data.detail;
    if (Array.isArray(data?.detail)) {
      return data.detail.map(item => item?.msg || 'Entrada inválida').join(' · ');
    }
    return `Não foi possível registrar a execução${status ? ` (HTTP ${status})` : ''}`;
  }

  function visibleContext(value) {
    const text = String(value || '').trim();
    const marker = 'Contexto do usuário:';
    const index = text.lastIndexOf(marker);
    return index >= 0 ? text.slice(index + marker.length).trim() : text;
  }

  function automaticTitle(prompt) {
    const clean = visibleContext(prompt)
      .replace(/^[-#*\s]+/, '')
      .replace(/\s+/g, ' ')
      .trim();
    if (!clean) return 'Nova execução';
    return clean.length > 88 ? `${clean.slice(0, 85).trim()}…` : clean;
  }

  async function refreshExecutions() {
    try {
      if (typeof window.devpilotNavigate === 'function') {
        await window.devpilotNavigate('tasks', {history: true});
      } else {
        qs('.nav[data-view="tasks"]')?.click?.();
      }
    } catch (_) {}

    window.setTimeout(() => {
      try {
        if (typeof window.loadAllTasks === 'function') {
          void window.loadAllTasks(true, 20);
          return;
        }
        qs('#tasks-v9-refresh')?.click?.();
      } catch (_) {}
    }, 120);
  }

  async function submitExecution(event) {
    event.preventDefault();
    event.stopPropagation();

    const form = event.currentTarget;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.dataset.executionSubmitting === '1') return;

    const modal = form.closest('dialog');
    const submit = qs('#task-submit', form) || qs('[type="submit"]', form);
    const originalText = submit?.textContent || 'Registrar execução';
    const data = new FormData(form);

    const projectId = String(data.get('project_id') || '').trim();
    const prompt = String(data.get('prompt') || '').trim();
    const rawTitle = String(data.get('title') || '').trim();
    const title = rawTitle || automaticTitle(prompt);

    if (!projectId) {
      notify('Selecione um projeto para registrar a execução.');
      qs('#task-project', form)?.focus?.();
      return;
    }

    if (!visibleContext(prompt)) {
      notify('Descreva o que deve ser executado.');
      qs('#task-context', form)?.focus?.();
      return;
    }

    const priorityRaw = Number(data.get('priority') || 50);
    const priority = Number.isFinite(priorityRaw)
      ? Math.max(0, Math.min(100, priorityRaw))
      : 50;

    const payload = {
      project_id: projectId,
      title,
      prompt,
      priority,
      requires_approval: data.get('requires_approval') === 'on',
      source: modal?.dataset.taskSource || 'dashboard',
    };

    const token = localStorage.getItem('devpilot-token') || '';
    if (!token) {
      notify('Autenticação necessária para registrar a execução.');
      qs('#auth-modal')?.showModal?.();
      return;
    }

    form.dataset.executionSubmitting = '1';
    if (submit) {
      submit.disabled = true;
      submit.setAttribute('aria-busy', 'true');
      submit.textContent = 'Registrando execução…';
    }

    try {
      const response = await fetch('/api/tasks', {
        method: 'POST',
        cache: 'no-store',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const body = await response.json().catch(() => ({}));

      if (response.status === 401) {
        localStorage.removeItem('devpilot-token');
        qs('#auth-modal')?.showModal?.();
        throw new Error('Autenticação necessária');
      }

      if (!response.ok) {
        throw new Error(errorMessage(body, response.status));
      }

      modal?.close?.();
      form.reset();
      delete modal?.dataset.taskSource;

      document.dispatchEvent(new CustomEvent('devpilot:execution-created', {
        detail: {execution: body, payload},
      }));

      notify('Execução registrada com sucesso.');
      await refreshExecutions();
    } catch (error) {
      console.error('[DevPilot] Falha ao registrar execução', error);
      notify(error?.message || 'Não foi possível registrar a execução.');
    } finally {
      delete form.dataset.executionSubmitting;
      if (submit) {
        submit.disabled = false;
        submit.removeAttribute('aria-busy');
        submit.textContent = originalText.includes('tarefa') || originalText.includes('desenvolvimento')
          ? 'Registrar execução'
          : originalText;
      }
    }
  }

  function install() {
    const form = qs('#task-form');
    if (!(form instanceof HTMLFormElement)) return false;
    if (form.dataset.executionSubmitV27 === '1') return true;

    form.noValidate = true;
    form.setAttribute('novalidate', 'novalidate');

    const title = form.querySelector('input[name="title"]');
    if (title) {
      title.required = false;
      title.removeAttribute('required');
      title.placeholder = 'Opcional · se vazio, o DevPilot gera pelo contexto';
    }

    const project = form.querySelector('[name="project_id"]');
    project?.removeAttribute('required');

    const context = form.querySelector('[name="prompt"]');
    context?.removeAttribute('required');

    form.onsubmit = submitExecution;
    form.dataset.executionSubmitV27 = '1';

    const submit = qs('#task-submit', form);
    if (submit && /tarefa|desenvolvimento/i.test(submit.textContent || '')) {
      submit.textContent = 'Registrar execução';
    }

    return true;
  }

  const scheduleInstall = () => window.requestAnimationFrame(install);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scheduleInstall, {once: true});
  } else {
    scheduleInstall();
  }

  document.addEventListener('devpilot:feature-ready', scheduleInstall);
  document.addEventListener('devpilot:dashboard-revealed', scheduleInstall);
  document.addEventListener('devpilot:view-changed', scheduleInstall);

  [80, 250, 700, 1400].forEach(delay => window.setTimeout(install, delay));

  document.documentElement.dataset.devpilotExecutionSubmit = 'v27';
  console.info('[DevPilot] Execução Submit V27 ativo');
})();
