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

  const style = document.createElement('style');
  style.id = 'devpilot-linux-style';
  style.textContent = `
    #linux-view.active{display:block!important;min-width:0}
    .linux-shell{display:grid;gap:12px;max-width:1040px}
    .linux-simple-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 16px;border:1px solid var(--line);border-radius:16px;background:var(--surface2,#101b2b)}
    .linux-simple-head h2{margin:0;font-size:18px}.linux-simple-head p{margin:3px 0 0;color:var(--muted);font-size:12px}
    .linux-connection{display:flex;align-items:center;gap:8px;white-space:nowrap;font-size:12px}.linux-dot{width:9px;height:9px;border-radius:50%;background:#6f7d8e}.linux-dot.online{background:#35d99a;box-shadow:0 0 0 4px rgba(53,217,154,.12)}
    .linux-actions{display:flex;gap:8px;flex-wrap:wrap}.linux-action{border:1px solid var(--line);border-radius:12px;background:var(--surface2);color:var(--text);padding:10px 13px;cursor:pointer;font-weight:700}.linux-action:hover{border-color:var(--cyan)}
    .linux-hint{padding:10px 12px;border-radius:12px;background:rgba(53,217,154,.08);border:1px solid rgba(53,217,154,.22);font-size:12px;color:#cfe8df}
    .linux-terminal-card{border:1px solid var(--line);border-radius:16px;overflow:hidden;background:#05080d}
    .linux-terminal-toolbar{display:flex;align-items:center;gap:8px;padding:9px 10px;border-bottom:1px solid #253143;background:#0d1520;flex-wrap:wrap}
    .linux-terminal-toolbar .linux-spacer{flex:1}.linux-terminal-state{font-size:11px;color:var(--muted)}
    .linux-terminal-output{margin:0;min-height:290px;max-height:54vh;overflow:auto;padding:14px;background:#05080d;color:#d8f7dd;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;white-space:pre-wrap;overflow-wrap:anywhere}
    .linux-terminal-entry{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;padding:10px;background:#0a111b;border-top:1px solid #253143}
    .linux-terminal-entry textarea{min-height:44px;max-height:110px;resize:vertical;background:#071018;color:#eef7ff;border:1px solid #2a3b50;border-radius:10px;padding:10px;font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}
    .linux-more{display:none;gap:8px;flex-wrap:wrap}.linux-more.open{display:flex}
    @media(max-width:780px){.linux-simple-head{align-items:flex-start;flex-direction:column}.linux-actions{display:grid;grid-template-columns:1fr 1fr;width:100%}.linux-action{width:100%}.linux-terminal-output{min-height:250px;max-height:48vh}.linux-terminal-entry{grid-template-columns:1fr}.linux-terminal-entry button{width:100%}}
    @media(max-width:480px){.linux-actions{grid-template-columns:1fr}.linux-shell{gap:9px}.linux-terminal-output{font-size:12px}}
  `;
  document.querySelector('#devpilot-linux-style')?.remove();
  document.head.appendChild(style);

  const markup = () => `
    <div class="linux-shell">
      <section class="linux-simple-head">
        <div>
          <h2>Meu Linux</h2>
          <p id="linux-access-label">Conectando ao seu ambiente…</p>
        </div>
        <div class="linux-connection"><span class="linux-dot" id="linux-dot"></span><strong id="linux-agent-status">verificando</strong></div>
      </section>

      <div class="linux-actions" aria-label="Ações rápidas">
        <button class="linux-action" type="button" data-linux-command="pwd" data-linux-hint="Mostra a pasta em que você está.">Onde estou?</button>
        <button class="linux-action" type="button" data-linux-command="ls -lah" data-linux-hint="Mostra os arquivos da pasta atual.">Ver arquivos</button>
        <button class="linux-action" type="button" data-linux-command="find ~/Documents -maxdepth 2 -type d 2>/dev/null | head -40" data-linux-hint="Procura pastas de projetos dentro de Documents.">Meus projetos</button>
        <button class="linux-action" id="linux-more-toggle" type="button">Mais</button>
      </div>

      <div class="linux-more" id="linux-more-actions">
        <button class="linux-action" type="button" data-linux-command="git status --short --branch" data-linux-hint="Mostra a situação do Git sem alterar arquivos.">Status Git</button>
        <button class="linux-action" type="button" data-linux-command="free -h" data-linux-hint="Mostra o uso de memória RAM.">Memória</button>
        <button class="linux-action" type="button" data-linux-command="df -h /" data-linux-hint="Mostra o espaço disponível no disco principal.">Disco</button>
      </div>

      <div class="linux-hint" id="linux-hint">Escolha uma ação acima ou abra o terminal para digitar um comando.</div>

      <article class="linux-terminal-card">
        <div class="linux-terminal-toolbar">
          <button class="primary" id="linux-terminal-start" type="button">Abrir Linux</button>
          <button class="ghost" id="linux-terminal-stop" type="button" disabled>Encerrar</button>
          <button class="ghost" id="linux-terminal-clear" type="button">Limpar</button>
          <span class="linux-spacer"></span>
          <span class="linux-terminal-state" id="linux-terminal-state">fechado</span>
        </div>
        <pre class="linux-terminal-output" id="linux-terminal-output" aria-live="polite">Pronto para usar.\n</pre>
        <div class="linux-terminal-entry">
          <textarea id="linux-terminal-input" spellcheck="false" placeholder="Digite um comando…" disabled></textarea>
          <button class="primary" id="linux-terminal-send" type="button" disabled>Executar</button>
        </div>
      </article>
    </div>`;

  let view = null;
  let nav = null;
  let sessionId = null;
  let lastSequence = 0;
  let pollTimer = null;
  let sending = false;

  const cleanOutput = value => String(value || '')
    .replace(/\u001b\][^\u0007]*(?:\u0007|\u001b\\)/g, '')
    .replace(/\u001b\[[0-?]*[ -\/]*[@-~]/g, '')
    .replace(/\r/g, '')
    .split('\n')
    .filter(line => !line.includes('DEVPILOT_CAPTURE_'))
    .filter(line => !/^\s*\[\d+\][+-]?\s+Done\b/.test(line))
    .join('\n')
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001a\u001c-\u001f\u007f]/g, '');

  const setText = (selector, value) => {
    const el = view?.querySelector(selector) || document.querySelector(selector);
    if (el) el.textContent = value;
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
    for (const duplicate of views) if (duplicate !== view) duplicate.remove();
    if (!view.querySelector('.linux-shell') || !view.querySelector('#linux-access-label')) view.innerHTML = markup();
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
      if (output) output.textContent = 'Tela limpa.\n';
    });
    bindOnce('#linux-terminal-send', 'click', 'linuxBound', sendInput);
    bindOnce('#linux-more-toggle', 'click', 'linuxBound', () => {
      view?.querySelector('#linux-more-actions')?.classList.toggle('open');
    });

    view?.querySelectorAll('[data-linux-command]').forEach(button => {
      if (button.dataset.linuxQuickBound === '1') return;
      button.dataset.linuxQuickBound = '1';
      button.addEventListener('click', () => runQuick(button.dataset.linuxCommand, button.dataset.linuxHint));
    });

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

  const setTerminalEnabled = enabled => {
    const input = view?.querySelector('#linux-terminal-input');
    const send = view?.querySelector('#linux-terminal-send');
    const stop = view?.querySelector('#linux-terminal-stop');
    const start = view?.querySelector('#linux-terminal-start');
    if (input) input.disabled = !enabled;
    if (send) send.disabled = !enabled;
    if (stop) stop.disabled = !enabled;
    if (start) start.disabled = enabled;
  };

  const appendOutput = text => {
    const output = view?.querySelector('#linux-terminal-output');
    const clean = cleanOutput(text);
    if (!output || !clean) return;
    output.textContent += clean;
    if (output.textContent.length > 250000) output.textContent = output.textContent.slice(-180000);
    output.scrollTop = output.scrollHeight;
  };

  async function refreshStatus() {
    ensureUI();
    try {
      const status = await api('/api/linux/status');
      const profile = status.profile || {};
      setText('#linux-agent-status', status.connected ? 'conectado' : 'offline');
      const dot = view?.querySelector('#linux-dot');
      dot?.classList.toggle('online', Boolean(status.connected));
      let access = 'Ambiente Linux isolado do seu perfil.';
      if (profile.mode === 'dedicated-linux-user') {
        access = profile.linux_user_ready
          ? `Conta Linux isolada: ${profile.linux_user || 'devpilot'}.`
          : 'Conta Linux dedicada ainda não está pronta.';
      }
      setText('#linux-access-label', access);
      if (!status.connected && status.error) setText('#linux-hint', status.error);
    } catch (error) {
      setText('#linux-agent-status', 'offline');
      setText('#linux-hint', error.message);
    }
  }

  async function createSession() {
    ensureUI();
    if (sessionId) {
      startPolling();
      return true;
    }
    try {
      const session = await api('/api/linux/terminal/sessions', {
        method: 'POST',
        body: JSON.stringify({columns: 120, rows: 34}),
      });
      sessionId = session.id;
      lastSequence = 0;
      setTerminalEnabled(true);
      setText('#linux-terminal-state', session.linux_user ? `aberto · ${session.linux_user}` : 'aberto');
      setText('#linux-hint', session.linux_user
        ? `Linux aberto como ${session.linux_user}. Escolha uma ação ou digite um comando.`
        : 'Linux aberto. Escolha uma ação ou digite um comando.');
      const output = view?.querySelector('#linux-terminal-output');
      if (output) output.textContent = '';
      view?.querySelector('#linux-terminal-input')?.focus();
      startPolling();
      return true;
    } catch (error) {
      setText('#linux-hint', `Não foi possível abrir o Linux: ${error.message}`);
      return false;
    }
  }

  async function closeSession() {
    if (!sessionId) return;
    const id = sessionId;
    try { await api(`/api/linux/terminal/sessions/${id}`, {method: 'DELETE'}); }
    catch (error) { setText('#linux-hint', error.message); }
    finally {
      sessionId = null;
      setTerminalEnabled(false);
      setText('#linux-terminal-state', 'fechado');
      setText('#linux-hint', 'Sessão encerrada. Você pode abrir novamente quando precisar.');
      stopPolling();
    }
  }

  async function sendRaw(raw) {
    if (!sessionId || sending || !String(raw || '').trim()) return false;
    sending = true;
    try {
      await api(`/api/linux/terminal/sessions/${sessionId}/input`, {
        method: 'POST',
        body: JSON.stringify({data: `${raw}\n`}),
      });
      startPolling();
      window.setTimeout(pollOutput, 60);
      return true;
    } catch (error) {
      setText('#linux-hint', error.message);
      return false;
    } finally {
      sending = false;
    }
  }

  async function runQuick(command, hint) {
    ensureUI();
    setText('#linux-hint', hint || 'Executando…');
    if (!sessionId && !(await createSession())) return;
    await sendRaw(command);
  }

  async function sendInput() {
    if (!sessionId || sending) return;
    const input = view?.querySelector('#linux-terminal-input');
    const raw = input?.value || '';
    if (!raw.trim()) return;
    const ok = await sendRaw(raw);
    if (ok && input) input.value = '';
    input?.focus();
  }

  async function pollOutput() {
    if (!sessionId) return;
    try {
      const data = await api(`/api/linux/terminal/sessions/${sessionId}/output?after=${lastSequence}`);
      for (const chunk of data.chunks || []) {
        appendOutput(chunk.text);
        lastSequence = Math.max(lastSequence, Number(chunk.sequence) || 0);
      }
      if (data.session?.state === 'closed') {
        sessionId = null;
        setTerminalEnabled(false);
        setText('#linux-terminal-state', 'fechado');
        stopPolling();
      }
    } catch (error) {
      setText('#linux-hint', error.message);
      stopPolling();
    }
  }

  function startPolling() {
    if (!sessionId || pollTimer) return;
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
    document.querySelectorAll('.view').forEach(item => item.classList.toggle('active', item === view));
    view.hidden = false;
    view.classList.add('active');
    view.style.setProperty('display', 'block', 'important');
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === nav));
    const title = document.querySelector('#page-title');
    if (title) title.textContent = 'Linux';
    refreshStatus();
    if (sessionId) startPolling();
  }

  document.addEventListener('click', event => {
    const linuxNav = event.target.closest?.('.nav[data-view="linux"], .nav[data-linux-view="1"]');
    if (linuxNav) window.setTimeout(show, 0);
  }, true);

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopPolling();
    } else if (sessionId) {
      startPolling();
    }
  });

  const boot = () => api('/api/auth/me').then(() => ensureUI()).catch(() => {});
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
})();
