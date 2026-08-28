(() => {
  'use strict';

  if (window.__devpilotOrganizationCredentialsReady) return;
  window.__devpilotOrganizationCredentialsReady = true;

  const MANAGED_ORGANIZATION = 'a-castilho';
  const organizationForm = document.querySelector('#organization-form');
  const organizationsView = document.querySelector('#organizations-view');

  function ensureCreateCredentialField() {
    if (!organizationForm || organizationForm.querySelector('input[name="access_token"]')) return;
    const submit = organizationForm.querySelector('button[type="submit"]');
    if (!submit) return;

    const label = document.createElement('label');
    label.dataset.organizationCredentialField = '1';
    label.append('Fine-grained PAT do GitHub');

    const input = document.createElement('input');
    input.name = 'access_token';
    input.type = 'password';
    input.autocomplete = 'new-password';
    input.spellcheck = false;
    input.placeholder = 'Informe somente no DevPilot';
    label.appendChild(input);

    const hint = document.createElement('p');
    hint.className = 'hint';
    hint.textContent = 'Para a-castilho, use um Fine-grained PAT com Resource owner = a-castilho. A credencial é armazenada no vault criptografado e nunca retorna pela API.';

    submit.before(label, hint);
  }

  function ensureRecoveryDialog() {
    let dialog = document.querySelector('#organization-credential-modal');
    if (dialog) return dialog;

    dialog = document.createElement('dialog');
    dialog.id = 'organization-credential-modal';
    dialog.innerHTML = `
      <form class="modal" id="organization-credential-form">
        <button class="close" type="button" aria-label="Fechar">×</button>
        <span class="eyebrow">CREDENCIAL GITHUB</span>
        <h2>Atualizar credencial da organização</h2>
        <p class="hint">Use este fluxo quando o GitHub informar token inválido, expirado ou sem acesso. O token anterior não é exibido.</p>
        <label>Organização<select name="organization_id" required></select></label>
        <label>Novo Fine-grained PAT<input name="access_token" type="password" autocomplete="new-password" spellcheck="false" required minlength="8" placeholder="Cole o novo token somente aqui"></label>
        <label class="check" data-owner-confirmation hidden><input name="owner_confirmed" type="checkbox"> Confirmo que o Resource owner do token é a-castilho</label>
        <small>O DevPilot envia a credencial apenas ao endpoint administrativo, grava no vault criptografado e limpa este campo após a tentativa.</small>
        <button class="primary" type="submit">Salvar e validar</button>
      </form>`;
    document.body.appendChild(dialog);

    dialog.querySelector('.close')?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => {
      const token = dialog.querySelector('input[name="access_token"]');
      const confirmation = dialog.querySelector('input[name="owner_confirmed"]');
      if (token) token.value = '';
      if (confirmation) confirmation.checked = false;
    });
    return dialog;
  }

  function organizations() {
    return Array.isArray(window.state?.organizations)
      ? window.state.organizations
      : (typeof state !== 'undefined' && Array.isArray(state.organizations) ? state.organizations : []);
  }

  function selectedOrganization(dialog) {
    const id = dialog.querySelector('select[name="organization_id"]')?.value || '';
    return organizations().find(item => String(item.id) === String(id));
  }

  function syncOwnerConfirmation(dialog) {
    const item = selectedOrganization(dialog);
    const wrapper = dialog.querySelector('[data-owner-confirmation]');
    const checkbox = dialog.querySelector('input[name="owner_confirmed"]');
    const managed = String(item?.external_login || '').toLowerCase() === MANAGED_ORGANIZATION;
    if (wrapper) wrapper.hidden = !managed;
    if (checkbox) {
      checkbox.required = managed;
      if (!managed) checkbox.checked = false;
    }
  }

  function fillOrganizationSelect(dialog) {
    const select = dialog.querySelector('select[name="organization_id"]');
    if (!select) return false;
    const items = organizations();
    select.replaceChildren();
    if (!items.length) return false;

    const preferred = items.find(item => item.sync_status === 'failed' || item.last_sync_error) || items[0];
    for (const item of items) {
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = `${item.name} (@${item.external_login})${item === preferred ? ' · requer atenção' : ''}`;
      option.selected = item === preferred;
      select.appendChild(option);
    }
    syncOwnerConfirmation(dialog);
    return true;
  }

  async function openRecovery() {
    if (typeof isSuperAdmin === 'function' && !isSuperAdmin()) {
      if (typeof toast === 'function') toast('Acesso exclusivo do Super Admin');
      return;
    }

    if (typeof loadOrganizations === 'function') await loadOrganizations();
    const dialog = ensureRecoveryDialog();
    if (!fillOrganizationSelect(dialog)) {
      if (typeof toast === 'function') toast('Nenhuma organização cadastrada para atualizar.');
      return;
    }
    dialog.showModal?.();
    dialog.querySelector('input[name="access_token"]')?.focus();
  }

  function ensureRecoveryButton() {
    const head = organizationsView?.querySelector('.section-head');
    if (!head || head.querySelector('[data-organization-credential-recovery]')) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'ghost';
    button.dataset.organizationCredentialRecovery = '1';
    button.textContent = 'Atualizar credencial GitHub';
    button.addEventListener('click', () => void openRecovery());

    const primary = head.querySelector('[data-open="organization-modal"]');
    if (primary) primary.before(button);
    else head.appendChild(button);
  }

  function bindRecoveryForm() {
    const dialog = ensureRecoveryDialog();
    const form = dialog.querySelector('#organization-credential-form');
    if (!form || form.dataset.bound === '1') return;
    form.dataset.bound = '1';

    dialog.querySelector('select[name="organization_id"]')?.addEventListener('change', () => syncOwnerConfirmation(dialog));

    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (typeof isSuperAdmin === 'function' && !isSuperAdmin()) {
        if (typeof toast === 'function') toast('Acesso exclusivo do Super Admin');
        return;
      }

      const data = new FormData(form);
      const organizationId = String(data.get('organization_id') || '').trim();
      const tokenInput = form.querySelector('input[name="access_token"]');
      const token = String(data.get('access_token') || '').trim();
      const item = selectedOrganization(dialog);
      const managed = String(item?.external_login || '').toLowerCase() === MANAGED_ORGANIZATION;
      const confirmed = data.get('owner_confirmed') === 'on';
      const submit = form.querySelector('button[type="submit"]');

      if (!organizationId || token.length < 8) {
        if (typeof toast === 'function') toast('Informe a organização e um novo token GitHub válido.');
        tokenInput?.focus();
        return;
      }
      if (managed && !confirmed) {
        if (typeof toast === 'function') toast('Confirme que o Resource owner do token é a-castilho.');
        form.querySelector('input[name="owner_confirmed"]')?.focus();
        return;
      }

      const original = submit?.textContent || 'Salvar e validar';
      if (submit) {
        submit.disabled = true;
        submit.textContent = 'Salvando…';
      }

      try {
        await api(`/organizations/${encodeURIComponent(organizationId)}`, {
          method: 'PATCH',
          body: JSON.stringify({access_token: token}),
        });
        if (tokenInput) tokenInput.value = '';
        dialog.close();
        if (typeof toast === 'function') toast('Credencial atualizada. Validando acesso ao GitHub…');
        if (typeof syncOrganization === 'function') await syncOrganization(organizationId);
        if (typeof state !== 'undefined') state.organizations = [];
        if (typeof loadOrganizations === 'function') await loadOrganizations();
      } catch (error) {
        if (tokenInput) tokenInput.value = '';
        if (typeof toast === 'function') toast(error.message || 'Falha ao atualizar a credencial GitHub.');
      } finally {
        if (submit) {
          submit.disabled = false;
          submit.textContent = original;
        }
      }
    });
  }

  ensureCreateCredentialField();
  ensureRecoveryButton();
  bindRecoveryForm();
})();
