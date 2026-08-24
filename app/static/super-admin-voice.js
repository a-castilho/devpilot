(() => {
  const token = () => localStorage.getItem('devpilot-token') || '';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  async function api(path) {
    const response = await fetch(path, {headers: {Authorization: `Bearer ${token()}`}});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha ao carregar o painel de voz');
    return data;
  }

  async function isSuperAdmin() {
    try {
      const me = await api('/api/auth/me');
      return String(me.role || '').toUpperCase() === 'SUPER_ADMIN';
    } catch (_) {
      return false;
    }
  }

  function installShell() {
    if (document.querySelector('[data-view="voice-admin"]')) return;
    const nav = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!nav || !main) return;

    const button = document.createElement('button');
    button.className = 'nav';
    button.type = 'button';
    button.dataset.view = 'voice-admin';
    button.innerHTML = '<span class="voice-admin-nav-dot"></span> Admin Voz';
    nav.appendChild(button);

    const section = document.createElement('section');
    section.className = 'view voice-admin-view';
    section.id = 'voice-admin-view';
    section.innerHTML = `
      <div class="voice-admin-hero">
        <div>
          <span class="eyebrow">SUPER ADMIN · DEVPILVOZ</span>
          <h2>Operação de voz em tempo real</h2>
          <p>Confirme qual provedor transcreveu a última fala, a ordem de fallback, conexões cadastradas e uso das últimas 24 horas.</p>
        </div>
        <button class="primary" id="voice-admin-refresh" type="button">Atualizar diagnóstico</button>
      </div>
      <div id="voice-admin-content"><div class="empty">Carregando diagnóstico…</div></div>`;
    main.appendChild(section);

    button.addEventListener('click', () => {
      document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v === section));
      document.querySelectorAll('.nav').forEach(v => v.classList.toggle('active', v === button));
      const title = document.querySelector('#page-title');
      if (title) title.textContent = 'Administração de voz';
      load();
    });
    section.querySelector('#voice-admin-refresh').addEventListener('click', load);
  }

  function statusPill(ok, text) {
    return `<span class="voice-admin-pill ${ok ? 'ok' : 'warn'}">${ok ? '✓' : '!'} ${esc(text)}</span>`;
  }

  function render(data) {
    const target = document.querySelector('#voice-admin-content');
    if (!target) return;
    const last = data.last_transcription;
    const lastText = last
      ? `${esc(last.provider || '—')} · ${esc(last.model || '—')}`
      : 'Nenhuma transcrição registrada';
    const lastMeta = last
      ? `${new Date(last.created_at).toLocaleString('pt-BR')} · ${last.fallback ? 'fallback acionado' : 'provedor principal'}`
      : 'Fale com o DevPilVoz para gerar o primeiro diagnóstico.';

    target.innerHTML = `
      ${data.warnings?.length ? `<div class="voice-admin-alerts">${data.warnings.map(w => `<div><b>!</b><span>${esc(w)}</span></div>`).join('')}</div>` : ''}

      <div class="voice-admin-metrics">
        <article><span>Última transcrição</span><strong>${lastText}</strong><small>${esc(lastMeta)}</small></article>
        <article><span>Conexões cadastradas</span><strong>${data.connections.length}</strong><small>${data.connections.filter(x => x.enabled).length} ativas</small></article>
        <article><span>Transcrições 24h</span><strong>${data.usage_24h.reduce((sum, x) => sum + Number(x.requests || 0), 0)}</strong><small>registradas pelo backend</small></article>
      </div>

      <div class="voice-admin-grid">
        <article class="panel voice-admin-panel">
          <div class="panel-title"><div><span class="eyebrow">ROTEAMENTO</span><h3>Cadeia real de transcrição</h3></div></div>
          <div class="voice-admin-chain">
            ${data.chain.map((item, index) => `
              <div class="voice-admin-chain-row">
                <div class="voice-admin-order">${item.order}</div>
                <div><strong>${esc(item.label)}</strong><small>${esc(item.role)} · ${esc(item.model)}</small></div>
                ${statusPill(item.configured, item.configured ? 'Configurado' : 'Sem credencial')}
              </div>${index < data.chain.length - 1 ? '<div class="voice-admin-arrow">↓ falha / limite</div>' : ''}
            `).join('')}
          </div>
        </article>

        <article class="panel voice-admin-panel">
          <div class="panel-title"><div><span class="eyebrow">PROVEDORES</span><h3>Conexões e participação na voz</h3></div></div>
          <div class="voice-admin-connections">
            ${data.connections.map(item => `
              <div class="voice-admin-connection">
                <div><strong>${esc(item.label)}</strong><small>${esc(item.provider)} · ${esc(item.models.join(', ') || 'sem modelos selecionados')}</small></div>
                <div class="voice-admin-badges">
                  ${statusPill(item.enabled, item.enabled ? 'Ativo' : 'Pausado')}
                  ${statusPill(item.used_by_voice_transcription, item.used_by_voice_transcription ? 'Usado no STT' : 'Fora do STT')}
                </div>
              </div>`).join('') || '<div class="empty">Nenhuma conexão cadastrada.</div>'}
          </div>
        </article>
      </div>

      <div class="voice-admin-grid">
        <article class="panel voice-admin-panel">
          <div class="panel-title"><div><span class="eyebrow">ÚLTIMAS 24 HORAS</span><h3>Uso por provedor/modelo</h3></div></div>
          <div class="voice-admin-usage">
            ${data.usage_24h.map(item => `<div><strong>${esc(item.provider)}</strong><span>${esc(item.model)}</span><b>${item.requests} requisição(ões)</b></div>`).join('') || '<div class="empty">Ainda não há uso registrado nas últimas 24 horas.</div>'}
          </div>
        </article>

        <article class="panel voice-admin-panel">
          <div class="panel-title"><div><span class="eyebrow">AUDITORIA</span><h3>Eventos recentes de voz</h3></div></div>
          <div class="voice-admin-events">
            ${data.recent_events.map(event => `<div class="voice-admin-event ${event.outcome === 'failed' ? 'failed' : ''}"><i></i><div><strong>${esc(event.action === 'voice.transcribed' ? `${event.provider || 'voz'} · ${event.model || 'modelo'}` : 'Falha de transcrição')}</strong><small>${new Date(event.created_at).toLocaleString('pt-BR')}${event.fallback ? ' · fallback' : ''}</small></div></div>`).join('') || '<div class="empty">Nenhum evento de voz registrado.</div>'}
          </div>
        </article>
      </div>

      <article class="panel voice-admin-test">
        <div><span class="eyebrow">TESTE OPERACIONAL</span><h3>Como confirmar qual IA foi usada</h3><p>Abra o DevPilVoz, grave uma frase curta e volte aqui. A caixa “Última transcrição” deve mostrar imediatamente o provedor e o modelo retornados pelo backend.</p></div>
        <code>POST /api/voice/transcriptions → provider + model → auditoria</code>
      </article>`;
  }

  async function load() {
    const target = document.querySelector('#voice-admin-content');
    if (target) target.classList.add('loading');
    try {
      render(await api('/api/super-admin/voice'));
    } catch (error) {
      if (target) target.innerHTML = `<div class="empty">${esc(error.message)}</div>`;
    } finally {
      if (target) target.classList.remove('loading');
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
