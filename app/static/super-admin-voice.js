(() => {
  const token = () => localStorage.getItem('devpilot-token') || '';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const list = value => Array.isArray(value) ? value : [];
  const num = value => Number.isFinite(Number(value)) ? Number(value) : 0;

  async function api(path, options = {}) {
    const method = options.method || 'GET';
    const headers = {Authorization: `Bearer ${token()}`};
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: 'no-store',
    });
    if (response.status === 204) return {};
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha ao executar a operação de voz');
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
          <h2>Central operacional de voz</h2>
          <p>Saúde da transcrição, uso por provedor, fallback, auditoria e gestão das conexões em uma única tela.</p>
        </div>
        <button class="primary" id="voice-admin-refresh" type="button">Atualizar dados</button>
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

  function usageTotal(usage) {
    return usage.reduce((sum, item) => sum + num(item?.requests), 0);
  }

  function renderUsageChart(usage) {
    const total = usageTotal(usage);
    if (!usage.length || !total) {
      return '<div class="voice-admin-empty-chart"><strong>Sem tráfego nas últimas 24h</strong><span>O gráfico será preenchido assim que novas transcrições forem registradas.</span></div>';
    }
    const maximum = Math.max(...usage.map(item => num(item?.requests)), 1);
    return `
      <div class="voice-admin-bars" role="img" aria-label="Uso por provedor e modelo nas últimas 24 horas">
        ${usage.map(item => {
          const requests = num(item?.requests);
          const width = Math.max(5, Math.round((requests / maximum) * 100));
          return `<div class="voice-admin-bar-row">
            <div class="voice-admin-bar-label"><strong>${esc(item?.provider || '—')}</strong><span>${esc(item?.model || '—')}</span><b>${requests}</b></div>
            <div class="voice-admin-bar-track"><i style="--voice-bar:${width}%"></i></div>
          </div>`;
        }).join('')}
      </div>`;
  }

  function renderOutcomeChart(events) {
    const success = events.filter(event => event?.outcome !== 'failed' && event?.action === 'voice.transcribed').length;
    const failed = events.filter(event => event?.outcome === 'failed' || event?.action === 'voice.transcription_failed').length;
    const total = success + failed;
    const successRate = total ? Math.round((success / total) * 100) : 0;
    const failureRate = total ? 100 - successRate : 0;
    return `
      <div class="voice-admin-outcome">
        <div class="voice-admin-donut" style="--success-rate:${successRate}%" role="img" aria-label="${successRate}% de sucesso na amostra de eventos">
          <div><strong>${total ? `${successRate}%` : '—'}</strong><span>sucesso</span></div>
        </div>
        <div class="voice-admin-legend">
          <div><i class="success"></i><span>Sucesso</span><strong>${success}</strong></div>
          <div><i class="failed"></i><span>Falha</span><strong>${failed}</strong></div>
          <div><i class="neutral"></i><span>Amostra</span><strong>${total}</strong></div>
          <small>${total ? `${failureRate}% de falhas na amostra retornada pela auditoria.` : 'Ainda não há eventos suficientes para calcular a taxa.'}</small>
        </div>
      </div>`;
  }

  function renderRoute(chain) {
    if (!chain.length) return '<div class="empty">Nenhuma rota de transcrição configurada.</div>';
    return `<div class="voice-admin-route">
      ${chain.map((item, index) => `
        <div class="voice-admin-route-node ${item?.configured ? 'ready' : 'missing'}">
          <span>${esc(item?.order ?? index + 1)}</span>
          <div><small>${esc(item?.role || 'etapa')}</small><strong>${esc(item?.label || item?.provider || 'Provedor')}</strong><em>${esc(item?.model || 'modelo não informado')}</em></div>
          ${statusPill(Boolean(item?.configured), item?.configured ? 'pronto' : 'sem credencial')}
        </div>
        ${index < chain.length - 1 ? '<div class="voice-admin-route-link"><i></i><span>fallback</span></div>' : ''}
      `).join('')}
    </div>`;
  }

  function renderConnections(connections) {
    if (!connections.length) return '<div class="empty">Nenhuma conexão cadastrada.</div>';
    return `<div class="voice-admin-connection-list">
      ${connections.map(item => {
        const id = esc(item?.id || '');
        const models = list(item?.models);
        return `<article class="voice-admin-connection-card" data-connection-id="${id}">
          <div class="voice-admin-connection-main">
            <div class="voice-admin-provider-mark">${esc(String(item?.provider || '?').slice(0, 2).toUpperCase())}</div>
            <div class="voice-admin-connection-copy">
              <div class="voice-admin-connection-title"><strong>${esc(item?.label || item?.provider || 'Provedor')}</strong>${statusPill(Boolean(item?.enabled), item?.enabled ? 'ativo' : 'pausado')}</div>
              <span>${esc(item?.provider || '—')} · ${models.length} modelo(s)</span>
              <small>${esc(models.join(', ') || 'sem modelos selecionados')}</small>
            </div>
          </div>
          <div class="voice-admin-connection-flags">
            ${statusPill(Boolean(item?.used_by_voice_transcription), item?.used_by_voice_transcription ? 'usado no STT' : 'fora do STT')}
          </div>
          <div class="voice-admin-connection-actions">
            <button class="ghost voice-admin-edit" type="button" data-action="edit">Editar</button>
            <button class="ghost voice-admin-toggle" type="button" data-action="toggle" data-enabled="${item?.enabled ? 'true' : 'false'}">${item?.enabled ? 'Pausar' : 'Ativar'}</button>
            <button class="ghost danger voice-admin-delete" type="button" data-action="delete">Excluir</button>
          </div>
          <div class="voice-admin-editor" hidden>
            <label>Modelos da conexão</label>
            <textarea rows="3" data-models>${esc(models.join('\n'))}</textarea>
            <div class="voice-admin-editor-help">Um modelo por linha ou separado por vírgula. A credencial nunca é exibida nesta tela.</div>
            <div class="voice-admin-editor-actions">
              <button class="primary voice-admin-save-models" type="button" data-action="save">Salvar alterações</button>
              <button class="ghost voice-admin-cancel" type="button" data-action="cancel">Cancelar</button>
            </div>
          </div>
        </article>`;
      }).join('')}
    </div>`;
  }

  function renderRecentEvents(events) {
    const visible = events.slice(0, 6);
    if (!visible.length) return '<div class="empty">Nenhum evento de voz registrado.</div>';
    return `<div class="voice-admin-event-strip">
      ${visible.map(event => {
        const failed = event?.outcome === 'failed' || event?.action === 'voice.transcription_failed';
        const title = failed ? 'Falha de transcrição' : `${event?.provider || 'voz'} · ${event?.model || 'modelo'}`;
        return `<div class="voice-admin-event ${failed ? 'failed' : ''}"><i></i><div><strong>${esc(title)}</strong><small>${esc(formatDate(event?.created_at))}${event?.fallback ? ' · fallback' : ''}</small></div></div>`;
      }).join('')}
    </div>`;
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
    const total24h = usageTotal(usage);
    const activeConnections = connections.filter(item => item?.enabled).length;
    const sttConnections = connections.filter(item => item?.used_by_voice_transcription && item?.enabled).length;
    const successes = events.filter(event => event?.outcome !== 'failed' && event?.action === 'voice.transcribed').length;
    const failures = events.filter(event => event?.outcome === 'failed' || event?.action === 'voice.transcription_failed').length;
    const eventTotal = successes + failures;
    const successRate = eventTotal ? Math.round((successes / eventTotal) * 100) : null;
    const fallbackCount = events.filter(event => Boolean(event?.fallback)).length;
    const lastText = last ? `${esc(last.provider || '—')} · ${esc(last.model || '—')}` : 'Nenhuma transcrição registrada';
    const lastMeta = last ? `${formatDate(last.created_at)} · ${last.fallback ? 'fallback acionado' : 'provedor principal'}` : 'Fale com o DevPilVoz para gerar o primeiro diagnóstico.';

    target.innerHTML = `
      ${warnings.length ? `<div class="voice-admin-alerts">${warnings.map(warning => `<div><b>!</b><span>${esc(warning)}</span></div>`).join('')}</div>` : ''}

      <div class="voice-admin-last-status">
        <div><span>Última transcrição</span><strong>${lastText}</strong><small>${esc(lastMeta)}</small></div>
        ${last ? statusPill(true, last.fallback ? 'fallback' : 'principal') : statusPill(false, 'aguardando voz')}
      </div>

      <div class="voice-admin-metrics">
        <article><span>Transcrições · 24h</span><strong>${total24h}</strong><small>requisições registradas</small></article>
        <article><span>Taxa de sucesso</span><strong>${successRate === null ? '—' : `${successRate}%`}</strong><small>${eventTotal} evento(s) na amostra</small></article>
        <article><span>Conexões ativas</span><strong>${activeConnections}/${connections.length}</strong><small>${sttConnections} participando do STT</small></article>
        <article><span>Fallback recente</span><strong>${fallbackCount}</strong><small>evento(s) auditado(s)</small></article>
      </div>

      <div class="voice-admin-charts">
        <article class="panel voice-admin-panel voice-admin-chart-panel">
          <div class="panel-title"><div><span class="eyebrow">TRÁFEGO · 24H</span><h3>Uso por provedor e modelo</h3></div><span class="voice-admin-total">${total24h} total</span></div>
          ${renderUsageChart(usage)}
        </article>
        <article class="panel voice-admin-panel voice-admin-chart-panel">
          <div class="panel-title"><div><span class="eyebrow">CONFIABILIDADE</span><h3>Resultado das transcrições</h3></div></div>
          ${renderOutcomeChart(events)}
        </article>
      </div>

      <article class="panel voice-admin-panel voice-admin-route-panel">
        <div class="panel-title"><div><span class="eyebrow">ROTEAMENTO REAL</span><h3>Cadeia de transcrição e fallback</h3></div><span class="voice-admin-total">${chain.filter(item => item?.configured).length}/${chain.length} prontas</span></div>
        ${renderRoute(chain)}
      </article>

      <div class="voice-admin-lower-grid">
        <article class="panel voice-admin-panel voice-admin-management">
          <div class="panel-title"><div><span class="eyebrow">GERENCIAMENTO</span><h3>Conexões de IA</h3><p>Edite modelos, pause/ative ou exclua conexões sem expor segredos.</p></div></div>
          ${renderConnections(connections)}
        </article>
        <article class="panel voice-admin-panel voice-admin-audit">
          <div class="panel-title"><div><span class="eyebrow">AUDITORIA</span><h3>Eventos recentes</h3></div><span class="voice-admin-total">${events.length} carregados</span></div>
          ${renderRecentEvents(events)}
          <div class="voice-admin-operational-note"><strong>Teste operacional</strong><span>Grave uma frase no DevPilVoz e clique em “Atualizar dados”. O provedor e o modelo devem aparecer no topo e na auditoria.</span><code>POST /api/voice/transcriptions</code></div>
        </article>
      </div>`;

    bindDataControls(target);
  }

  function parseModels(value) {
    return [...new Set(String(value || '').split(/[\n,]+/).map(item => item.trim()).filter(Boolean))];
  }

  async function withBusy(button, label, operation) {
    if (!button || button.disabled) return;
    const previous = button.textContent;
    button.disabled = true;
    button.textContent = label;
    try {
      await operation();
    } catch (error) {
      window.toast?.(error?.message || 'Falha ao executar a operação.');
      button.disabled = false;
      button.textContent = previous;
      return;
    }
    await load();
  }

  function bindDataControls(target) {
    target.querySelectorAll('.voice-admin-connection-card').forEach(card => {
      const id = card.dataset.connectionId || '';
      const editor = card.querySelector('.voice-admin-editor');
      const edit = card.querySelector('.voice-admin-edit');
      const cancel = card.querySelector('.voice-admin-cancel');
      const toggle = card.querySelector('.voice-admin-toggle');
      const remove = card.querySelector('.voice-admin-delete');
      const save = card.querySelector('.voice-admin-save-models');
      const textarea = card.querySelector('[data-models]');

      edit?.addEventListener('click', () => {
        editor.hidden = false;
        edit.setAttribute('aria-expanded', 'true');
        textarea?.focus();
      });
      cancel?.addEventListener('click', () => {
        editor.hidden = true;
        edit?.setAttribute('aria-expanded', 'false');
      });
      toggle?.addEventListener('click', () => {
        const enabled = toggle.dataset.enabled === 'true';
        withBusy(toggle, enabled ? 'Pausando…' : 'Ativando…', () => api(`/api/providers/${encodeURIComponent(id)}/enabled`, {
          method: 'PATCH',
          body: {enabled: !enabled},
        }));
      });
      remove?.addEventListener('click', () => {
        if (!window.confirm('Excluir esta conexão de IA? Esta ação remove a credencial salva.')) return;
        withBusy(remove, 'Excluindo…', () => api(`/api/providers/${encodeURIComponent(id)}`, {method: 'DELETE'}));
      });
      save?.addEventListener('click', () => {
        const models = parseModels(textarea?.value);
        if (!models.length) {
          window.toast?.('Informe ao menos um modelo antes de salvar.');
          textarea?.focus();
          return;
        }
        withBusy(save, 'Salvando…', () => api(`/api/providers/${encodeURIComponent(id)}/models`, {
          method: 'PATCH',
          body: {models},
        }));
      });
    });
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
