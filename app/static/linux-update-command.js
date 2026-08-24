(() => {
  'use strict';

  const token = () => localStorage.getItem('devpilot-token') || '';
  if (!token()) return;

  const api = async (path, options = {}) => {
    const response = await fetch(path, {
      ...options,
      headers: {
        Authorization: `Bearer ${token()}`,
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
    }
    return data;
  };

  const setHint = text => {
    const hint = document.querySelector('#linux-view #linux-hint');
    if (hint) hint.textContent = text;
  };

  const ensureButton = () => {
    const actions = document.querySelector('#linux-view .linux-actions');
    if (!actions) return null;

    let button = actions.querySelector('#linux-update-local');
    if (button) return button;

    button = document.createElement('button');
    button.id = 'linux-update-local';
    button.type = 'button';
    button.className = 'linux-action';
    button.hidden = true;
    button.textContent = 'Atualizar';
    button.title = 'Atualiza o DevPilot local com backup, main canônica, rebuild seguro e health check.';
    actions.insertBefore(button, actions.querySelector('#linux-more-toggle'));
    return button;
  };

  const configureAccess = async () => {
    const button = ensureButton();
    if (!button) return false;

    try {
      const status = await api('/api/linux/status');
      const superAdmin = status?.profile?.role === 'SUPER_ADMIN';
      button.hidden = !superAdmin;
      button.disabled = !superAdmin;
      if (superAdmin) {
        button.dataset.linuxUpdateReady = '1';
      }
      return superAdmin;
    } catch {
      button.hidden = true;
      button.disabled = true;
      return false;
    }
  };

  const runUpdate = async event => {
    const button = event.currentTarget;
    if (!button || button.dataset.linuxUpdateBusy === '1') return;

    button.dataset.linuxUpdateBusy = '1';
    button.disabled = true;
    const previousText = button.textContent;
    button.textContent = 'Atualizando…';
    setHint('Enviando atualização segura para o Linux host…');

    try {
      const result = await api('/api/voice/system-actions', {
        method: 'POST',
        body: JSON.stringify({transcript: 'atualizar local'}),
      });
      const id = result?.host_action?.id;
      setHint(id
        ? `Atualização enviada ao Linux. Ação ${id} em processamento; a interface pode reconectar durante o rebuild.`
        : 'Atualização enviada ao Linux; a interface pode reconectar durante o rebuild.');
      button.textContent = 'Atualização enviada';
    } catch (error) {
      setHint(`Falha ao solicitar atualização: ${error.message}`);
      button.textContent = previousText;
      button.disabled = false;
      button.dataset.linuxUpdateBusy = '0';
    }
  };

  const bind = async () => {
    const button = ensureButton();
    if (!button) return false;
    if (button.dataset.linuxUpdateBound !== '1') {
      button.dataset.linuxUpdateBound = '1';
      button.addEventListener('click', runUpdate);
    }
    await configureAccess();
    return true;
  };

  const boot = () => {
    let attempts = 0;
    const timer = window.setInterval(async () => {
      attempts += 1;
      if (await bind() || attempts >= 40) window.clearInterval(timer);
    }, 250);
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
