(() => {
  const token = () => localStorage.getItem('devpilot-token') || '';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list = value => Array.isArray(value) ? value : [];

  async function api(path) {
    const response = await fetch(path, {
      headers: {Authorization: `Bearer ${token()}`},
      cache: 'no-store',
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha ao carregar o painel de voz');
    return data && typeof data === 'object' ? data : {};
  }

  async function isSuperAdmin() {
    try {
      const me = await api('/api/auth/me');
      return String(me.role || '').toUpperCase() === 'SUPER_ADMIN';
    } catch (_) {
      return false;
    }
  }

  function shellMarkup() {
    return `
      <div class="voice-admin-hero">
        <div>
          <span class="eyebrow">SUPER ADMIN · DEVPILVOZ</span>
          <h2>Operação de voz em tempo real</h2>
          <p>Confirme qual provedor transcreveu a última fala, a ordem de fallback, conexões cadastradas e uso das últimas 24 horas.</p>
        </div>
        <button class="primary" id="voice-admin-refresh" type="button">Atualizar diagnóstico</button>
      </div>
      <div id="voice-admin-content" aria-live="polite"><div class="empty">Carregando diagnóstico…</div></div>`;
  }

  function bindSectionControls(section) {
    const refresh = section?.querySelector('#voice-admin-refresh');
    if (refresh && refresh.dataset.voiceAdminBound !== 'true') {
      refresh.addEventListener('click', load);
      refresh.dataset.voiceAdminBound = 'true';
    }
  }

  function ensureSection(main = document.querySelector('main')) {
    if (!main) return null;
    let section = document.querySelector('#voice-admin-view');
    if (!section) {
      section = document.createElement('section');
      section.className = 'view voice-admin-view';
      section.id = 'voice-admin-view';
      main.appendChild(section);
    } else if (!section.isConnected || section.parentElement !== main) {
      main.appendChild(section);
    }
    section.classList.add('view', 'voice-admin-view');
    if (!section.querySelector('#voice-admin-content') || !section.querySelector('.voice-admin-hero')) {
      section.innerHTML = shellMarkup();
    }
    bindSectionControls(section);
    return section;
  }

  function activate(button) {
    const section = ensureSection();
    if (!section) {
      window.toast?.('Não foi possível abrir a Administração de voz. Atualize a página.');
      return;
    }
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active', view === section));
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button));
    const title = document.querySelector('#page-title');
    if (title) title.textContent = 'Administração de voz';
    load();
  }

  function installShell() {
    const nav = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!nav || !main) return;

    let button = nav.querySelector('[data-view="voice-admin"]');
    if (!button) {
      button = document.createElement('button');
      button.type = 'button';
      button.dataset.view = 'voice-admin';
      button.innerHTML = '<span class="voice-admin-nav-dot"></span> Admin Voz';
      nav.appendChild(button);
    }

    button.classList.add('nav', 'nav-super-admin-item');
    button.dataset.superAdmin = 'true';
    button.dataset.navGroup = 'super-admin';
    button.type = 'button';
    if (!button.textContent.trim()) button.innerHTML = '<span class="voice-admin-nav-dot"></span> Admin Voz';

    const section = ensureSection(main);
    if (!section) return;

    if (button.dataset.voiceAdminBound !== 'true') {
      button.addEventListener('click', () => activate(button));
      button.dataset.voiceAdminBound = 'true';
    }

    // Repair a partially mounted shell immediately. This covers cases where the
    // navigation item was already active but the view was never inserted.
    if (button.classList.contains('active') || section.classList.contains('active')) {
      activate(button);
    }
  }

  function statusPill(ok, text) {
    return `<span class="voice-admin-pill ${ok ? 'ok' : 'warn'}">${ok ? '✓' : '!'} ${esc(text)}</span>`;
  }

  function formatDate(value) {
    if (!value) return 'horário indisponível';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'horário indisponível' : date.toLocaleString('pt-BR');
  }

  function render(data) {
    const target = document.querySelector('#voice-admin-content');
    if (!target) return;

    const warnings = list(data.warnings);
    const chain = list(data.chain);
    const connections = list(data.connections);
    const usage = list(data.usage_24h);
    const events = list(data.recent_events);
    const last = data.last_transcription && typeof data.last_transcription === 'object' ? data.last_transcription : null;
    const lastText = last
      ? `${esc(last.provider || '—')} · ${esc(last.model || '—')}`
      : 'Nenhuma transcrição registrada';
    const lastMeta = last
      ? `${formatDate(last.created_at)} · ${last.fallback ? 'fallback acionado' : 'provedor principal'}`
      : 'Fale com o DevPilVoz para gerar o primeiro diagnóstico.';

    target.innerHTML = `
      ${warnings.length ? `<div class="voice-admin-alerts">${warnings.map(w => `<div><b>!</b><span>${esc(w)}</span></div>`).join('')}</div>` : ''}

      <div class="voice-admin-metrics">
        <article><span>Última transcrição</span><strong>${lastText}</strong><small>${esc(lastMeta)}</small></article>
        <article><span>Conexões cadastradas</span><strong>${connections.length}</strong><small>${connections.filter(x => x && x.enabled).length} ativas</small></article>
        <article><span>Transcrições 24h</span><strong>${usage.reduce((sum, x) => sum + Number(x?.requests || 0), 0)}</strong><small>registradas pelo backend</small></article>
      </div>

      <div class="voice-admin-grid">
        <article class="panel voice-admin-panel">
          <div class="panel-title"><div><span class="eyebrow">ROTEAMENTO</span><h3>Cadeia real de transcrição</h3></div></div>
          <div class="voice-admin-chain">
            ${chain.map((item, index) => `
              <div class="voice-admin-chain-row">
                <div class="voice-admin-order">${esc(item?.order ?? index + 1)}</div>
                <div><strong>${esc(item?.label || item?.provider || 'Provedor')}</strong><small>${esc(item?.role || '—')} · ${esc(item?.model || '—')}</small></div>
                ${statusPill(Boolean(item?.configured), item?.configured ? 'Configurado' : 'Sem credencial')}
              </div>${index < chain.length - 1 ? '<div class="voice-admin-arrow">↓ falha / limite</div>' : ''}
            `).join('') || '<div class="empty">Nenhuma rota de transcrição configurada.</div>'}
          </div>
        </article>

        <article class="panel voice-admin-panel">
          <div class="panel-title"><div><span class="eyebrow">PROVEDORES</span><h3>Conexões e participação na voz</h3></div></div>
          <div class="voice-admin-connections">
            ${connections.map(item => `
              <div class="voice-admin-connection">
                <div><strong>${esc(item?.label || item?.provider || 'Provedor')}</strong><small>${esc(item?.provider || '—')} · ${esc(list(item?.models).join(', ') || 'sem modelos selecionados')}</small></div>
                <div class="voice-admin-badges">
                  ${statusPill(Boolean(item?.enabled), item?.enabled ? 'Ativo' : 'Pausado')}
                  ${statusPill(Boolean(item?.used_by_voice_transcription), item?.used_by_voice_transcription ? 'Usado no STT' : 'Fora do STT')}
                </div>
              </div>`).join('') || '<div class="empty">Nenhuma conexão cadastrada.</div>'}
          </div>
        </article>
      </div>

      <div class="voice-admin-grid">
        <article class="panel voice-admin-panel">
          <div class="panel-title"><div><span class="eyebrow">ÚLTIMAS 24 HORAS</span><h3>Uso por provedor/modelo</h3></div></div>
          <div class="voice-admin-usage">
            ${usage.map(item => `<div><strong>${esc(item?.provider || '—')}</strong><span>${esc(item?.model || '—')}</span><b>${Number(item?.requests || 0)} requisição(ões)</b></div>`).join('') || '<div class="empty">Ainda não há uso registrado nas últimas 24 horas.</div>'}
          </div>
        </article>

        <article class="panel voice-admin-panel">
          <div class="panel-title"><div><span class="eyebrow">AUDITORIA</span><h3>Eventos recentes de voz</h3></div></div>
          <div class="voice-admin-events">
            ${events.map(event => `<div class="voice-admin-event ${event?.outcome === 'failed' ? 'failed' : ''}"><i></i><div><strong>${esc(event?.action === 'voice.transcribed' ? `${event?.provider || 'voz'} · ${event?.model || 'modelo'}` : 'Falha de transcrição')}</strong><small>${esc(formatDate(event?.created_at))}${event?.fallback ? ' · fallback' : ''}</small></div></div>`).join('') || '<div class="empty">Nenhum evento de voz registrado.</div>'}
          </div>
        </article>
      </div>

      <article class="panel voice-admin-test">
        <div><span class="eyebrow">TESTE OPERACIONAL</span><h3>Como confirmar qual IA foi usada</h3><p>Abra o DevPilVoz, grave uma frase curta e volte aqui. A caixa “Última transcrição” deve mostrar imediatamente o provedor e o modelo retornados pelo backend.</p></div>
        <code>POST /api/voice/transcriptions → provider + model → auditoria</code>
      </article>`;
  }

  function renderLoadState() {
    const target = document.querySelector('#voice-admin-content');
    if (!target) return null;
    target.innerHTML = '<article class="panel voice-admin-panel"><div class="empty">Carregando diagnóstico de voz…</div></article>';
    target.classList.add('loading');
    return target;
  }

  function renderError(target, error) {
    target.innerHTML = `
      <article class="panel voice-admin-panel" role="alert">
        <span class="eyebrow">DIAGNÓSTICO INDISPONÍVEL</span>
        <h3>Não foi possível carregar a administração de voz</h3>
        <p>${esc(error?.message || 'Falha inesperada ao consultar o backend.')}</p>
        <button class="primary" id="voice-admin-retry" type="button">Tentar novamente</button>
      </article>`;
    target.querySelector('#voice-admin-retry')?.addEventListener('click', load, {once: true});
  }

  async function load() {
    const target = renderLoadState();
    if (!target) return;
    try {
      render(await api('/api/super-admin/voice'));
    } catch (error) {
      renderError(target, error);
    } finally {
      target.classList.remove('loading');
    }
  }

  function loadSystemMapAssets() {
    if (!document.querySelector('link[data-super-admin-system-map]')) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = '/assets/super-admin-system-map.css';
      link.dataset.superAdminSystemMap = '1';
      document.head.appendChild(link);
    }
    if (!document.querySelector('script[data-super-admin-system-map]')) {
      const script = document.createElement('script');
      script.src = '/assets/super-admin-system-map.js';
      script.defer = true;
      script.dataset.superAdminSystemMap = '1';
      document.head.appendChild(script);
    }
  }

  async function boot() {
    if (!token() || !(await isSuperAdmin())) return;
    installShell();
    loadSystemMapAssets();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
