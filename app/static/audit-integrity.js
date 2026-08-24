(() => {
  const PANEL_ID = 'audit-integrity-panel';

  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  }[char]));

  const installStyle = () => {
    if (document.querySelector('#audit-integrity-style')) return;
    const style = document.createElement('style');
    style.id = 'audit-integrity-style';
    style.textContent = `
      .audit-integrity{margin-bottom:14px;padding:16px;display:grid;gap:13px}
      .audit-integrity-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap}
      .audit-integrity-head h3{margin:3px 0 4px}.audit-integrity-head p{margin:0;color:var(--muted);font-size:12px}
      .audit-integrity-badges{display:flex;gap:7px;flex-wrap:wrap}
      .audit-integrity-badge{display:inline-flex;align-items:center;gap:6px;padding:6px 9px;border:1px solid var(--line);border-radius:999px;font-size:11px;font-weight:700}
      .audit-integrity-badge.good{border-color:rgba(70,210,145,.45)}
      .audit-integrity-badge.warn{border-color:rgba(245,187,70,.55)}
      .audit-integrity-badge.bad{border-color:rgba(244,91,105,.55)}
      .audit-integrity-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
      .audit-integrity-stat{padding:10px;border:1px solid var(--line);border-radius:12px;background:var(--surface2)}
      .audit-integrity-stat small{display:block;color:var(--muted);font-size:10px;margin-bottom:4px}.audit-integrity-stat strong{font-size:13px;overflow-wrap:anywhere}
      .audit-integrity-error{padding:10px;border:1px solid rgba(244,91,105,.45);border-radius:10px;font-size:12px}
      @media(max-width:800px){.audit-integrity-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:480px){.audit-integrity-grid{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  };

  const ensurePanel = () => {
    installStyle();
    const view = document.querySelector('#audit-view');
    const timeline = view?.querySelector('#audit-list');
    if (!view || !timeline) return null;
    let panel = view.querySelector(`#${PANEL_ID}`);
    if (!panel) {
      panel = document.createElement('article');
      panel.id = PANEL_ID;
      panel.className = 'panel audit-integrity';
      timeline.parentNode.insertBefore(panel, timeline);
    }
    return panel;
  };

  const token = () => localStorage.getItem('devpilot-token') || '';

  const getJson = async path => {
    const response = await fetch(path, {
      headers: {Authorization: `Bearer ${token()}`},
      cache: 'no-store',
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data?.detail === 'string' ? data.detail : `HTTP ${response.status}`;
      throw new Error(detail);
    }
    return data;
  };

  const renderLoading = panel => {
    panel.innerHTML = `
      <div class="audit-integrity-head">
        <div><span class="eyebrow">AUDITORIA IMUTÁVEL</span><h3>Verificando integridade…</h3><p>Conferindo hash-chain e assinatura do usuário Linux.</p></div>
      </div>`;
  };

  const render = (panel, data) => {
    const identity = data.current_linux_identity?.linux_identity || {};
    const keyId = data.current_linux_identity?.signing_key_id || '';
    const valid = Boolean(data.valid);
    const fullySigned = Boolean(data.fully_linux_signed);
    const integrityClass = valid ? 'good' : 'bad';
    const signatureClass = fullySigned ? 'good' : 'warn';
    const integrityLabel = valid ? '✓ CADEIA ÍNTEGRA' : '! QUEBRA DETECTADA';
    const signatureLabel = fullySigned ? '✓ ASSINADA PELO LINUX' : 'LEGADO / SEM ASSINATURA';

    panel.innerHTML = `
      <div class="audit-integrity-head">
        <div>
          <span class="eyebrow">AUDITORIA IMUTÁVEL</span>
          <h3>Prova de integridade</h3>
          <p>Cada assinatura identifica o usuário Linux efetivo que executa o Agent.</p>
        </div>
        <div class="audit-integrity-badges">
          <span class="audit-integrity-badge ${integrityClass}">${integrityLabel}</span>
          <span class="audit-integrity-badge ${signatureClass}">${signatureLabel}</span>
          <button class="ghost" type="button" data-audit-verify>Verificar agora</button>
        </div>
      </div>
      <div class="audit-integrity-grid">
        <div class="audit-integrity-stat"><small>Usuário Linux</small><strong>${esc(identity.username || 'indisponível')}</strong></div>
        <div class="audit-integrity-stat"><small>UID / GID</small><strong>${identity.euid ?? '—'} / ${identity.egid ?? '—'}</strong></div>
        <div class="audit-integrity-stat"><small>Host</small><strong>${esc(identity.hostname || '—')}</strong></div>
        <div class="audit-integrity-stat"><small>Chave</small><strong>${esc(keyId ? keyId.slice(0, 16) : '—')}</strong></div>
        <div class="audit-integrity-stat"><small>Eventos verificados</small><strong>${Number(data.events_checked || 0)}</strong></div>
        <div class="audit-integrity-stat"><small>Assinados Linux</small><strong>${Number(data.linux_signed_events || 0)}</strong></div>
        <div class="audit-integrity-stat"><small>Legados / sem assinatura</small><strong>${Number(data.legacy_or_unsigned_events || 0)}</strong></div>
        <div class="audit-integrity-stat"><small>Falhas de integridade</small><strong>${Array.isArray(data.invalid_events) ? data.invalid_events.length : 0}</strong></div>
      </div>
      ${data.linux_agent_error ? `<div class="audit-integrity-error">Linux Agent: ${esc(data.linux_agent_error)}</div>` : ''}
    `;
    panel.querySelector('[data-audit-verify]')?.addEventListener('click', loadIntegrity);
  };

  const renderError = (panel, error) => {
    panel.innerHTML = `
      <div class="audit-integrity-head">
        <div><span class="eyebrow">AUDITORIA IMUTÁVEL</span><h3>Não foi possível verificar agora</h3><p>${esc(error?.message || error)}</p></div>
        <button class="ghost" type="button" data-audit-verify>Tentar novamente</button>
      </div>`;
    panel.querySelector('[data-audit-verify]')?.addEventListener('click', loadIntegrity);
  };

  async function loadIntegrity() {
    const panel = ensurePanel();
    if (!panel) return;
    renderLoading(panel);
    try {
      render(panel, await getJson('/api/audit/integrity'));
    } catch (error) {
      renderError(panel, error);
    }
  }

  document.addEventListener('click', event => {
    const nav = event.target.closest?.('[data-view="audit"]');
    if (nav) window.setTimeout(loadIntegrity, 0);
  });

  document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('#audit-view.active')) loadIntegrity();
  });
})();
