(() => {
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
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
    return data;
  };

  if (!document.querySelector('#devpilot-linux-style')) {
    const style = document.createElement('style');
    style.id = 'devpilot-linux-style';
    style.textContent = `
      #linux-view.active{display:block!important;min-width:0}
      .linux-shell{display:grid;gap:14px}
      .linux-status-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}
      .linux-stat{padding:14px;border:1px solid var(--line);border-radius:14px;background:var(--surface2,#101b2b);min-width:0}
      .linux-stat small{display:block;color:var(--muted);margin-bottom:6px}.linux-stat strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .linux-terminal-card{border:1px solid var(--line);border-radius:16px;overflow:hidden;background:#05080d}
      .linux-terminal-toolbar{display:flex;align-items:center;gap:8px;padding:10px;border-bottom:1px solid #253143;background:#0d1520;flex-wrap:wrap}
      .linux-terminal-toolbar .linux-spacer{flex:1}.linux-terminal-state{font-size:12px;color:var(--muted)}
      .linux-terminal-output{margin:0;min-height:330px;max-height:56vh;overflow:auto;padding:14px;background:#05080d;color:#d8f7dd;font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;white-space:pre-wrap;overflow-wrap:anywhere}
      .linux-terminal-entry{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;padding:10px;background:#0a111b;border-top:1px solid #253143}
      .linux-terminal-entry textarea{min-height:42px;max-height:120px;resize:vertical;background:#05080d;color:#eef7ff;border:1px solid #2a3b50;border-radius:10px;padding:10px;font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}
      .linux-info{padding:10px 12px;border:1px solid rgba(70,210,145,.35);border-radius:12px;background:rgba(70,210,145,.08);font-size:12px}
      @media(max-width:900px){.linux-status-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:780px){.linux-terminal-output{min-height:260px;max-height:48vh}.linux-terminal-entry{grid-template-columns:1fr}.linux-terminal-entry button{width:100%}}
    `;
    document.head.appendChild(style);
  }

  const markup = () => `
    <div class="section-head"><p>Seu ambiente Linux privado para trabalhar nos projetos do DevPilot.</p></div>
    <div class="linux-shell">
      <div class="linux-status-grid">
        <article class="linux-stat"><small>Linux Agent</small><strong id="linux-agent-status">Consultando…</strong></article>
        <article class="linux-stat"><small>Workspace</small><strong id="linux-workspace">—</strong></article>
        <article class="linux-stat"><small>Host</small><strong id="linux-hostname">—</strong></article>
        <article class="linux-stat"><small>Memória</small><strong id="linux-memory">—</strong></article>
        <article class="linux-stat"><small>Load 1m</small><strong id="linux-load">—</strong></article>
      </div>
      <div class="linux-info">Cada usuário autenticado recebe um workspace Linux isolado. Sessões e terminal ficam vinculados ao perfil autenticado.</div>
      <article class="linux-terminal-card">
        <div class="linux-terminal-toolbar">
          <button class="primary" id="linux-terminal-start" type="button">Abrir meu Linux</button>
          <button class="ghost" id="linux-terminal-stop" type="button" disabled>Encerrar</button>
          <button class="ghost" id="linux-terminal-clear" type="button">Limpar tela</button>
          <span class="linux-spacer"></span><span class="linux-terminal-state" id="linux-terminal-state">sem sessão</span>
        </div>
        <pre class="linux-terminal-output" id="linux-terminal-output" aria-live="polite"></pre>
        <div class="linux-terminal-entry">
          <textarea id="linux-terminal-input" spellcheck="false" placeholder="Digite um comando Linux. Enter envia; Shift+Enter quebra linha." disabled></textarea>
          <button class="primary" id="linux-terminal-send" type="button" disabled>Enviar</button>
        </div>
      </article>
    </div>`;

  let view = null;
  let nav = null;
  let sessionId = null;
  let lastSequence = 0;
  let pollTimer = null;
  let visible = false;
  let sending = false;

  const setText = (selector, value) => {
    const element = view?.querySelector(selector) || document.querySelector(selector);
    if (element) element.textContent = value;
  };

  const ensureUI = () => {
    nav = document.querySelector('.sidebar nav .nav[data-view="linux"]') || document.querySelector('.sidebar nav .nav[data-linux-view="1"]');
    if (!nav) {
      nav = document.createElement('button');
      nav.className = 'nav';
      nav.textContent = 'Linux';
      document.querySelector('.sidebar nav')?.appendChild(nav);
    }
    nav.dataset.view = 'linux';
    nav.dataset.linuxView = '1';

    const views = [...document.querySelectorAll('#linux-view')];
    view = views.find(item => item.isConnected) || null;
    if (!view) {
      view = document.createElement('section');
      view.className = 'view';
      view.id = 'linux-view';
      document.querySelector('main')?.appendChild(view);
    }
    for (const duplicate of views) {
      if (duplicate !== view) duplicate.remove();
    }
    if (!view.querySelector('.linux-shell')) view.innerHTML = markup();
    bindControls();
    return view;
  };

  const bindOnce = (selector, event, key, handler) => {
    const element = view?.querySelector(selector);
    if (!element || element.dataset[key] === '1') return;
    element.dataset[key] = '1';
    element.addEventListener(event, handler);
  };

  const bindControls = () => {
    bindOnce('#linux-terminal-start', 'click', 'linuxBound', createSession);
    bindOnce('#linux-terminal-stop', 'click', 'linuxBound', closeSession);
    bindOnce('#linux-terminal-clear', 'click', 'linuxBound', () => {
      const output = view?.querySelector('#linux-terminal-output');
      if (output) output.textContent = '';
    });
    bindOnce('#linux-terminal-send', 'click', 'linuxBound', sendInput);
    const input = view?.querySelector('#linux-terminal-input');
    if (input && input.dataset.linuxKeyBound !== '1') {
      input.dataset.linuxKeyBound = '1';
      input.addEventListener('keydown', event => {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault();
          sendInput();
        }
      });
    }
  };

  const bytes = value => {
    if (value == null) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let current = Number(value), index = 0;
    while (current >= 1024 && index < units.length - 1) { current /= 1024; index += 1; }
    return `${current.toFixed(index >= 2 ? 1 : 0)} ${units[index]}`;
  };

  const setTerminalEnabled = enabled => {
    const input = view?.querySelector('#linux-terminal-input');
    const send = view?.querySelector('#linux-terminal-send');
    const stop = view?.querySelector('#linux-terminal-stop');
    if (input) input.disabled = !enabled;
    if (send) send.disabled = !enabled;
    if (stop) stop.disabled = !enabled;
  };

  const appendOutput = text => {
    const output = view?.querySelector('#linux-terminal-output');
    if (!output || !text) return;
    output.textContent += text;
    if (output.textContent.length > 800000) output.textContent = output.textContent.slice(-600000);
    output.scrollTop = output.scrollHeight;
  };

  async function refreshStatus() {
    ensureUI();
    try {
      const status = await api('/api/linux/status');
      const system = status.system || {};
      const profile = status.profile || {};
      setText('#linux-agent-status', status.connected ? 'conectado' : (status.error || 'offline'));
      setText('#linux-workspace', profile.workspace_key ? `perfil ${profile.workspace_key.slice(0, 8)}` : '—');
      setText('#linux-hostname', system.hostname || '—');
      const mem = system.memory || {};
      setText('#linux-memory', mem.used != null && mem.total != null ? `${bytes(mem.used)} / ${bytes(mem.total)}` : '—');
      setText('#linux-load', system.load && system.load['1m'] != null ? Number(system.load['1m']).toFixed(2) : '—');
    } catch (error) {
      setText('#linux-agent-status', error.message);
    }
  }

  async function createSession() {
    ensureUI();
    if (sessionId) return;
    try {
      const session = await api('/api/linux/terminal/sessions', {method: 'POST', body: JSON.stringify({columns: 120, rows: 34})});
      sessionId = session.id;
      lastSequence = 0;
      setTerminalEnabled(true);
      setText('#linux-terminal-state', `seu workspace · sessão ${sessionId.slice(0, 8)} · PID ${session.pid}`);
      view?.querySelector('#linux-terminal-input')?.focus();
      startPolling();
    } catch (error) {
      appendOutput(`\n[erro] ${error.message}\n`);
    }
  }

  async function closeSession() {
    if (!sessionId) return;
    const id = sessionId;
    try { await api(`/api/linux/terminal/sessions/${id}`, {method: 'DELETE'}); }
    catch (error) { appendOutput(`\n[erro ao encerrar] ${error.message}\n`); }
    finally {
      sessionId = null;
      setTerminalEnabled(false);
      setText('#linux-terminal-state', 'sessão encerrada');
      stopPolling();
    }
  }

  async function sendInput() {
    if (!sessionId || sending) return;
    const input = view?.querySelector('#linux-terminal-input');
    const raw = input?.value || '';
    if (!raw.trim()) return;
    sending = true;
    try {
      await api(`/api/linux/terminal/sessions/${sessionId}/input`, {method: 'POST', body: JSON.stringify({data: `${raw}\n`})});
      if (input) input.value = '';
    } catch (error) {
      appendOutput(`\n[erro] ${error.message}\n`);
    } finally {
      sending = false;
      input?.focus();
    }
  }

  async function pollOutput() {
    if (!visible || !sessionId) return;
    try {
      const data = await api(`/api/linux/terminal/sessions/${sessionId}/output?after=${lastSequence}`);
      for (const chunk of data.chunks || []) {
        appendOutput(chunk.text);
        lastSequence = Math.max(lastSequence, Number(chunk.sequence) || 0);
      }
      if (data.session?.state === 'closed') {
        setText('#linux-terminal-state', `encerrada · código ${data.session.exit_code ?? '—'}`);
        sessionId = null;
        setTerminalEnabled(false);
        stopPolling();
      }
    } catch (error) {
      appendOutput(`\n[agent] ${error.message}\n`);
      stopPolling();
    }
  }

  function startPolling() {
    stopPolling();
    if (!visible || !sessionId) return;
    pollOutput();
    pollTimer = window.setInterval(pollOutput, 700);
  }

  function stopPolling() {
    if (pollTimer) window.clearInterval(pollTimer);
    pollTimer = null;
  }

  function show() {
    ensureUI();
    if (!view || !nav) return;
    visible = true;
    document.querySelectorAll('.view').forEach(item => item.classList.toggle('active', item === view));
    view.hidden = false;
    view.classList.add('active');
    view.style.setProperty('display', 'block', 'important');
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === nav));
    const title = document.querySelector('#page-title');
    if (title) title.textContent = 'Meu Linux';
    refreshStatus();
    if (sessionId) startPolling();
  }

  document.addEventListener('click', event => {
    const linuxNav = event.target.closest?.('.nav[data-view="linux"], .nav[data-linux-view="1"]');
    if (linuxNav) {
      window.setTimeout(show, 0);
      return;
    }
    if (!visible) return;
    const otherNav = event.target.closest?.('.nav');
    if (otherNav) {
      visible = false;
      stopPolling();
    }
  }, true);

  const boot = () => api('/api/auth/me').then(() => ensureUI()).catch(() => {});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();