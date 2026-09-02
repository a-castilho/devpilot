/* DevPilot Build Game victory reward: expose a verified test URL after the final phase. */
(() => {
  'use strict';

  const PROJECT_KEY = 'devpilot-build-game-project';
  const AUTO_KEY = 'devpilot-build-game-delivery-auto';
  const OPERATORS = new Set(['SUPER_ADMIN', 'OWNER', 'ADMIN']);
  const inFlight = new Set();
  const validationTimers = new Map();
  const AUTO_RETRY_COOLDOWN_MS = 60_000;
  const AUTO_VALIDATION_DELAY_MS = 5_000;
  const MAX_AUTO_VALIDATIONS = 6;

  const escapeHtml = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const safeUrl = value => {
    const candidate = String(value || '').trim();
    return /^https:\/\//i.test(candidate) ? candidate : '';
  };

  const role = () => String((typeof state !== 'undefined' && state.currentUser?.role) || '').toUpperCase();
  const canOperate = () => OPERATORS.has(role());
  const projectId = () => String(localStorage.getItem(PROJECT_KEY) || '').trim();
  const currentProject = () => {
    const rows = typeof state !== 'undefined' && Array.isArray(state.projects) ? state.projects : [];
    return rows.find(project => String(project?.id) === projectId()) || null;
  };
  const deliveryMode = () => String(currentProject()?.delivery_mode || 'code').trim().toLowerCase();
  const requiresPublicUrl = () => deliveryMode() === 'web';
  const normalizedStatus = delivery => String(delivery?.status || 'pending').toLowerCase();
  const missionDelivered = delivery => !requiresPublicUrl() || (normalizedStatus(delivery) === 'ready' && Boolean(safeUrl(delivery?.url)));
  const autoKey = id => `${AUTO_KEY}:${id}`;

  const statusText = status => ({
    pending: 'Publicação final pendente',
    provisioning: 'Preparando ambiente de teste',
    deploying: 'Publicando e validando URL',
    ready: 'URL de teste liberada',
    failed: 'A publicação precisa ser corrigida',
    blocked: 'Publicação aguardando infraestrutura',
  })[status] || 'Preparando entrega final';

  const actionFor = status => {
    if (status === 'failed' || status === 'blocked') {
      return {endpoint: 'retry', label: '↻ Corrigir publicação e gerar URL'};
    }
    if (status === 'deploying' || status === 'provisioning') {
      return {endpoint: 'validate-url', label: 'Verificar URL real'};
    }
    return {endpoint: 'start', label: '🚀 Publicar e gerar URL'};
  };

  const directChild = (panel, predicate) => Array.from(panel.children || []).find(predicate) || null;

  const setMissionGate = (panel, delivery = {}) => {
    const delivered = missionDelivered(delivery);
    const eyebrow = directChild(panel, element => element.classList?.contains('eyebrow'));
    const heading = directChild(panel, element => element.tagName === 'H3');
    const summary = directChild(panel, element => element.tagName === 'P');

    if (summary && !panel.dataset.gameOriginalVictorySummary) {
      panel.dataset.gameOriginalVictorySummary = String(summary.textContent || '').trim();
    }
    const originalSummary = panel.dataset.gameOriginalVictorySummary || '';

    if (delivered) {
      panel.dataset.gameMissionDelivered = '1';
      if (eyebrow) eyebrow.textContent = 'MISSÃO CONCLUÍDA';
      if (requiresPublicUrl()) {
        if (heading) heading.textContent = '🏆 Sistema entregue e URL validada';
        if (summary) summary.textContent = `${originalSummary}${originalSummary ? ' ' : ''}URL pública validada e pronta para teste.`;
      } else {
        if (heading) heading.textContent = '🏆 Entrega técnica concluída';
        if (summary) summary.textContent = `${originalSummary}${originalSummary ? ' ' : ''}Código, testes e evidências da rodada foram concluídos. Publicação externa é opcional para este tipo de projeto.`;
      }
      return;
    }

    panel.dataset.gameMissionDelivered = '0';
    if (eyebrow) eyebrow.textContent = 'CHEFE FINAL VENCIDO · ENTREGA PENDENTE';
    if (heading) heading.textContent = '🚀 Falta publicar e validar a URL';
    if (summary) {
      summary.textContent = `${originalSummary}${originalSummary ? ' ' : ''}A missão só será concluída quando uma URL pública real responder com sucesso.`;
    }
  };

  const installStyle = () => {
    if (document.querySelector('#build-game-url-bonus-style')) return;
    const style = document.createElement('style');
    style.id = 'build-game-url-bonus-style';
    style.textContent = `
      .build-game-url-bonus{display:grid;gap:10px;margin-top:15px;padding:15px;border:1px solid rgba(95,224,255,.28);border-radius:14px;background:linear-gradient(135deg,rgba(28,100,91,.24),rgba(8,22,39,.8))}
      .build-game-url-bonus .eyebrow{color:#72efc5}
      .build-game-url-bonus-head{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}
      .build-game-url-bonus-head strong{font-size:1rem}
      .build-game-url-bonus-state{padding:5px 9px;border:1px solid rgba(114,239,197,.25);border-radius:999px;font-size:.68rem;font-weight:800;letter-spacing:.06em;color:#72efc5}
      .build-game-url-bonus p{margin:0;color:var(--muted,#9eacc2)}
      .build-game-url-value{display:block;padding:10px 12px;border:1px solid rgba(255,255,255,.09);border-radius:10px;background:rgba(0,0,0,.2);font:600 .78rem ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere;color:#8be9fd;text-decoration:none}
      .build-game-url-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
      .build-game-url-actions .primary{display:inline-flex;align-items:center;justify-content:center;text-decoration:none}
      .build-game-url-error{font-size:.76rem;color:#ffc56e}
      @media(max-width:800px){.build-game-url-actions>*{width:100%}.build-game-url-bonus-head{align-items:flex-start}}
    `;
    document.head.appendChild(style);
  };

  const rewardHost = panel => {
    let host = panel.querySelector('.build-game-url-bonus');
    if (!host) {
      host = document.createElement('div');
      host.className = 'build-game-url-bonus';
      panel.appendChild(host);
    }
    return host;
  };

  const render = (panel, delivery = {}) => {
    setMissionGate(panel, delivery);
    const host = rewardHost(panel);
    const status = normalizedStatus(delivery);
    const url = safeUrl(delivery.url);

    if (missionDelivered(delivery)) {
      localStorage.removeItem(autoKey(projectId()));
      if (requiresPublicUrl()) {
        host.innerHTML = `
          <span class="eyebrow">🎁 ENTREGA FINAL CONCLUÍDA</span>
          <div class="build-game-url-bonus-head">
            <strong>URL de teste liberada</strong>
            <span class="build-game-url-bonus-state">PRONTO PARA TESTAR</span>
          </div>
          <p>A missão foi concluída porque o ambiente publicado respondeu ao teste real de disponibilidade.</p>
          <a class="build-game-url-value" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>
          <div class="build-game-url-actions"><a class="primary" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Abrir sistema ↗</a></div>
        `;
      } else {
        host.innerHTML = `
          <span class="eyebrow">🎁 ENTREGA DE DESENVOLVIMENTO CONCLUÍDA</span>
          <div class="build-game-url-bonus-head">
            <strong>Rodada pronta para continuar o projeto</strong>
            <span class="build-game-url-bonus-state">CÓDIGO VALIDADO</span>
          </div>
          <p>As sete etapas foram aprovadas. Este projeto não exige URL pública para concluir a rodada.</p>
          ${url ? `<a class="build-game-url-value" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>` : ''}
        `;
      }
      return;
    }

    const action = actionFor(status);
    const canRun = canOperate();
    const pendingCopy = status === 'pending'
      ? 'O chefe final foi vencido, mas a missão ainda não terminou. O DevPilot precisa publicar o sistema e validar uma URL real antes de concluir.'
      : status === 'blocked'
        ? 'A entrega final está bloqueada. O DevPilot tentará reutilizar a infraestrutura cadastrada ou localizar um deploy público válido antes de liberar a missão.'
        : status === 'failed'
          ? 'A publicação falhou. A missão permanece aberta e a correção pode ser executada novamente sem perder o progresso da partida.'
          : 'A publicação está em andamento. A missão só muda para concluída depois que a URL pública responder ao teste real.';

    host.innerHTML = `
      <span class="eyebrow">🚀 ENTREGA FINAL OBRIGATÓRIA</span>
      <div class="build-game-url-bonus-head">
        <strong>${escapeHtml(statusText(status))}</strong>
        <span class="build-game-url-bonus-state">URL REAL PENDENTE</span>
      </div>
      <p>${escapeHtml(pendingCopy)}</p>
      ${delivery.last_error ? `<div class="build-game-url-error">${escapeHtml(delivery.last_error)}</div>` : ''}
      <div class="build-game-url-actions">
        ${canRun ? `<button class="primary" type="button" data-game-url-action="${action.endpoint}">${escapeHtml(action.label)}</button>` : '<span class="build-game-url-error">A missão permanece pendente até a administração concluir a publicação.</span>'}
      </div>
    `;

    host.querySelector('[data-game-url-action]')?.addEventListener('click', event => {
      void runAction(panel, event.currentTarget);
    });
  };

  const fetchDelivery = async id => api(`/projects/${encodeURIComponent(id)}/delivery`);
  const validateDelivery = async id => api(`/projects/${encodeURIComponent(id)}/delivery/validate-url`, {method: 'POST'});

  const shouldAutoAttempt = id => {
    const last = Number(localStorage.getItem(autoKey(id)) || 0);
    return !last || Date.now() - last >= AUTO_RETRY_COOLDOWN_MS;
  };

  const markAutoAttempt = id => localStorage.setItem(autoKey(id), String(Date.now()));

  const scheduleValidation = (panel, id, attempt = 1) => {
    if (!id || attempt > MAX_AUTO_VALIDATIONS || missionDelivered({
      status: panel.dataset.gameDeliveryStatus,
      url: panel.dataset.gameDeliveryUrl,
    })) return;

    const previousTimer = validationTimers.get(id);
    if (previousTimer) window.clearTimeout(previousTimer);

    const timer = window.setTimeout(async () => {
      validationTimers.delete(id);
      if (!panel.isConnected || inFlight.has(id)) return;
      try {
        const delivery = await validateDelivery(id);
        panel.dataset.gameDeliveryStatus = normalizedStatus(delivery);
        panel.dataset.gameDeliveryUrl = safeUrl(delivery?.url);
        render(panel, delivery || {});
        if (missionDelivered(delivery)) {
          if (typeof toast === 'function') toast('🏆 Missão concluída: URL real validada.');
          return;
        }
        if (['deploying', 'provisioning'].includes(normalizedStatus(delivery))) {
          scheduleValidation(panel, id, attempt + 1);
        }
      } catch (_) {
        if (attempt < MAX_AUTO_VALIDATIONS) scheduleValidation(panel, id, attempt + 1);
      }
    }, AUTO_VALIDATION_DELAY_MS);
    validationTimers.set(id, timer);
  };

  const runAction = async (panel, button) => {
    const id = projectId();
    if (!id || inFlight.has(id)) return;
    const action = String(button?.dataset.gameUrlAction || 'start');
    if (!['start', 'retry', 'validate-url'].includes(action)) return;
    if (action !== 'validate-url' && !canOperate()) return;

    inFlight.add(id);
    const original = button?.textContent || '';
    if (button) {
      button.disabled = true;
      button.textContent = action === 'validate-url' ? 'Verificando…' : 'Publicando…';
    }
    try {
      const delivery = action === 'validate-url'
        ? await validateDelivery(id)
        : await api(`/projects/${encodeURIComponent(id)}/delivery/${action}`, {method: 'POST'});
      panel.dataset.gameDeliveryStatus = normalizedStatus(delivery);
      panel.dataset.gameDeliveryUrl = safeUrl(delivery?.url);
      render(panel, delivery || {});
      if (missionDelivered(delivery)) {
        if (typeof toast === 'function') toast('🏆 Missão concluída: URL real validada.');
      } else if (delivery?.status === 'blocked') {
        if (typeof toast === 'function') toast('Chefe final vencido; a missão aguarda a publicação da URL.');
      } else if (delivery?.status === 'failed') {
        if (typeof toast === 'function') toast(delivery.last_error || 'A publicação precisa ser corrigida.');
      } else {
        if (typeof toast === 'function') toast('Publicação em andamento; a missão ainda não foi concluída.');
        scheduleValidation(panel, id);
      }
    } catch (error) {
      if (typeof toast === 'function') toast(error?.message || 'Não foi possível concluir a publicação da URL.');
      try {
        render(panel, await fetchDelivery(id));
      } catch (_) {
        render(panel, {status: 'failed', last_error: 'Não foi possível consultar a publicação agora.'});
      }
    } finally {
      inFlight.delete(id);
      if (button?.isConnected) {
        button.disabled = false;
        button.textContent = original;
      }
    }
  };

  const automaticDelivery = async (panel, id, delivery) => {
    let current = delivery || {};
    if (!requiresPublicUrl()) return current;
    let status = normalizedStatus(current);

    if (missionDelivered(current)) {
      return validateDelivery(id);
    }

    if (canOperate() && ['pending', 'blocked', 'failed'].includes(status) && shouldAutoAttempt(id)) {
      markAutoAttempt(id);
      const action = status === 'pending' ? 'start' : 'retry';
      current = await api(`/projects/${encodeURIComponent(id)}/delivery/${action}`, {method: 'POST'});
      status = normalizedStatus(current);
    }

    if (['deploying', 'provisioning'].includes(status)) {
      const validated = await validateDelivery(id);
      if (missionDelivered(validated)) return validated;
      scheduleValidation(panel, id);
      return validated;
    }

    return current;
  };

  const hydrate = async panel => {
    const id = projectId();
    if (!id || panel.dataset.gameUrlBonusLoading === '1') return;
    panel.dataset.gameUrlBonusLoading = '1';
    installStyle();
    setMissionGate(panel, {status: 'provisioning'});
    const host = rewardHost(panel);
    host.innerHTML = requiresPublicUrl()
      ? '<span class="eyebrow">🚀 ENTREGA FINAL</span><strong>Publicando e validando URL real…</strong>'
      : '<span class="eyebrow">📦 ENTREGA FINAL</span><strong>Consolidando entrega técnica…</strong>';
    try {
      let delivery = await fetchDelivery(id);
      delivery = await automaticDelivery(panel, id, delivery);
      panel.dataset.gameDeliveryStatus = normalizedStatus(delivery);
      panel.dataset.gameDeliveryUrl = safeUrl(delivery?.url);
      render(panel, delivery || {});
    } catch (_) {
      render(panel, {status: 'pending', last_error: 'A entrega final ainda não pôde ser validada.'});
    } finally {
      panel.dataset.gameUrlBonusLoading = '0';
    }
  };

  const scan = () => {
    const panel = document.querySelector('#build-game-view .build-game-victory');
    if (!panel || panel.dataset.gameUrlBonusBound === '1') return;
    panel.dataset.gameUrlBonusBound = '1';
    setMissionGate(panel, {status: 'provisioning'});
    void hydrate(panel);
  };

  const boot = () => {
    scan();
    const root = document.querySelector('#build-game-view') || document.body;
    if (!root || root.dataset.gameUrlBonusObserved === '1') return;
    root.dataset.gameUrlBonusObserved = '1';
    new MutationObserver(scan).observe(root, {childList: true, subtree: true});
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
  window.setTimeout(boot, 700);
})();
