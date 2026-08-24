(() => {
  const token = () => localStorage.getItem('devpilot-token') || '';
  if (!token()) return;

  const authHeaders = () => ({Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json'});
  async function api(path, options = {}) {
    const response = await fetch(path, {...options, headers: {...authHeaders(), ...(options.headers || {})}});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
    return data;
  }

  const style = document.createElement('style');
  style.textContent = `
    #linux-view.active{display:block!important;min-width:0}.linux-shell{display:grid;gap:14px}
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

  let nav = null, view = null, sessionId = null, lastSequence = 0, pollTimer = null, visible = false, sending = false;

  function bytes(value) {
    if (value === null || value === undefined) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB']; let current = Number(value), i = 0;
    while (current >= 1024 && i < units.length - 1) { current /= 1024; i += 1; }
    return `${current.toFixed(i >= 2 ? 1 : 0)} ${units[i]}`;
  }

  function ensureUI() {
    if (view && nav) return;
    nav = document.querySelector('.sidebar nav .nav[data-linux-view="1"]');
    if (!nav) {
      nav = document.createElement('button'); nav.className = 'nav'; nav.dataset.linuxView = '1'; nav.textContent = 'Linux';
      document.querySelector('.sidebar nav')?.appendChild(nav);
    }
    nav.dataset.view = 'linux'; nav.dataset.linuxView = '1';

    view = document.querySelector('#linux-view');
    if (!view) {
      view = document.createElement('section'); view.className = 'view'; view.id = 'linux-view';
      view.innerHTML = `
        <div class="section-head"><p>Seu ambiente Linux privado para trabalhar nos projetos do DevPilot.</p></div>
        <div class="linux-shell">
          <div class="linux-status-grid">
            <article class="linux-stat"><small>Linux Agent</small><strong id="linux-agent-status">Consultando…</strong></article>
            <article class="linux-stat"><small>Workspace</small><strong id="linux-workspace">—</strong></article>
            <article class="linux-stat"><small>Host</small><strong id="linux-hostname">—</strong></article>
            <article class="linux-stat"><small>Memória</small><strong id="linux-memory">—</strong></article>
            <article class="linux-stat"><small>Load 1m</small><strong id="linux-load">—</strong></article>
          </div>
          <div class="linux-info">Cada usuário autenticado recebe um workspace Linux isolado. Sessões, diretório inicial e acesso ao terminal são vinculados ao perfil do usuário; outro usuário não pode operar sua sessão.</div>
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
      document.querySelector('main')?.appendChild(view);
    }
    nav.addEventListener('click', show);
    document.querySelector('#linux-terminal-start')?.addEventListener('click', createSession);
    document.querySelector('#linux-terminal-stop')?.addEventListener('click', closeSession);
    document.querySelector('#linux-terminal-clear')?.addEventListener('click', () => { const output = document.querySelector('#linux-terminal-output'); if (output) output.textContent = ''; });
    document.querySelector('#linux-terminal-send')?.addEventListener('click', sendInput);
    document.querySelector('#linux-terminal-input')?.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendInput(); } });
  }

  function setTerminalEnabled(enabled) {
    const input = document.querySelector('#linux-terminal-input'), send = document.querySelector('#linux-terminal-send'), stop = document.querySelector('#linux-terminal-stop');
    if (input) input.disabled = !enabled; if (send) send.disabled = !enabled; if (stop) stop.disabled = !enabled;
  }
  function appendOutput(text) {
    const output = document.querySelector('#linux-terminal-output'); if (!output || !text) return;
    output.textContent += text; if (output.textContent.length > 800000) output.textContent = output.textContent.slice(-600000); output.scrollTop = output.scrollHeight;
  }

  async function refreshStatus() {
    try {
      const status = await api('/api/linux/status'), system = status.system || {}, profile = status.profile || {};
      document.querySelector('#linux-agent-status').textContent = status.connected ? 'conectado' : (status.error || 'offline');
      document.querySelector('#linux-workspace').textContent = profile.workspace_key ? `perfil ${profile.workspace_key.slice(0, 8)}` : '—';
      document.querySelector('#linux-hostname').textContent = system.hostname || '—';
      const mem = system.memory || {};
      document.querySelector('#linux-memory').textContent = mem.used != null && mem.total != null ? `${bytes(mem.used)} / ${bytes(mem.total)}` : '—';
      document.querySelector('#linux-load').textContent = system.load && system.load['1m'] != null ? Number(system.load['1m']).toFixed(2) : '—';
    } catch (error) { const el = document.querySelector('#linux-agent-status'); if (el) el.textContent = error.message; }
  }

  async function createSession() {
    if (sessionId) return;
    try {
      const session = await api('/api/linux/terminal/sessions', {method: 'POST', body: JSON.stringify({columns: 120, rows: 34})});
      sessionId = session.id; lastSequence = 0; setTerminalEnabled(true);
      document.querySelector('#linux-terminal-state').textContent = `seu workspace · sessão ${sessionId.slice(0, 8)} · PID ${session.pid}`;
      document.querySelector('#linux-terminal-input')?.focus(); startPolling();
    } catch (error) { window.toast ? window.toast(error.message) : appendOutput(`\n[erro] ${error.message}\n`); }
  }

  async function closeSession() {
    if (!sessionId) return; const id = sessionId;
    try { await api(`/api/linux/terminal/sessions/${id}`, {method: 'DELETE'}); }
    catch (error) { appendOutput(`\n[erro ao encerrar] ${error.message}\n`); }
    finally { sessionId = null; setTerminalEnabled(false); document.querySelector('#linux-terminal-state').textContent = 'sessão encerrada'; stopPolling(); }
  }

  async function sendInput() {
    if (!sessionId || sending) return; const input = document.querySelector('#linux-terminal-input'), raw = input?.value || ''; if (!raw.trim()) return;
    sending = true;
    try { await api(`/api/linux/terminal/sessions/${sessionId}/input`, {method: 'POST', body: JSON.stringify({data: `${raw}\n`})}); input.value = ''; }
    catch (error) { appendOutput(`\n[erro] ${error.message}\n`); }
    finally { sending = false; input?.focus(); }
  }

  async function pollOutput() {
    if (!visible || !sessionId) return;
    try {
      const data = await api(`/api/linux/terminal/sessions/${sessionId}/output?after=${lastSequence}`);
      for (const chunk of data.chunks || []) { appendOutput(chunk.text); lastSequence = Math.max(lastSequence, Number(chunk.sequence) || 0); }
      if (data.session?.state === 'closed') { document.querySelector('#linux-terminal-state').textContent = `encerrada · código ${data.session.exit_code ?? '—'}`; sessionId = null; setTerminalEnabled(false); stopPolling(); }
    } catch (error) { appendOutput(`\n[agent] ${error.message}\n`); stopPolling(); }
  }
  function startPolling() { stopPolling(); if (!visible || !sessionId) return; pollOutput(); pollTimer = window.setInterval(pollOutput, 700); }
  function stopPolling() { if (pollTimer) window.clearInterval(pollTimer); pollTimer = null; }
  function show() {
    if (!view || !nav) return; visible = true;
    document.querySelectorAll('.view').forEach(item => { item.classList.toggle('active', item === view); if (item !== view) item.style.removeProperty('display'); });
    view.hidden = false; view.classList.add('active'); view.style.setProperty('display', 'block', 'important');
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === nav));
    const title = document.querySelector('#page-title'); if (title) title.textContent = 'Meu Linux'; refreshStatus(); if (sessionId) startPolling();
  }
  document.addEventListener('click', event => { if (!view || !visible) return; const clickedNav = event.target.closest?.('.nav'); if (clickedNav && clickedNav !== nav) { visible = false; view.style.removeProperty('display'); stopPolling(); } }, true);

  api('/api/auth/me').then(() => ensureUI()).catch(() => {});
})();