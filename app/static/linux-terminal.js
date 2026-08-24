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
      .linux-shell{display:grid;gap:14px;max-width:1180px}
      .linux-welcome{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:18px;align-items:center;padding:18px;border:1px solid var(--line);border-radius:18px;background:linear-gradient(135deg,var(--surface),var(--surface2))}
      .linux-welcome h2{margin:3px 0 6px;font-size:22px}.linux-welcome p{margin:0;color:var(--muted);max-width:760px}
      .linux-voice-button{min-height:48px;white-space:nowrap}
      .linux-status-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}
      .linux-stat{padding:14px;border:1px solid var(--line);border-radius:14px;background:var(--surface2,#101b2b);min-width:0}
      .linux-stat small{display:block;color:var(--muted);margin-bottom:6px}.linux-stat strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .linux-guide{padding:16px;border:1px solid var(--line);border-radius:16px;background:var(--surface,#0d1928)}
      .linux-guide-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}.linux-guide h3{margin:0 0 3px}.linux-guide p{margin:0;color:var(--muted);font-size:12px}
      .linux-quick-actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}
      .linux-quick{display:grid;gap:3px;text-align:left;padding:12px;border:1px solid var(--line);border-radius:12px;background:var(--surface2);color:var(--text);cursor:pointer}
      .linux-quick:hover{border-color:var(--cyan)}.linux-quick strong{font-size:13px}.linux-quick small{color:var(--muted);font-size:11px;line-height:1.35}
      .linux-guide-message{display:flex;gap:9px;align-items:flex-start;margin-top:12px;padding:11px 12px;border-radius:12px;background:#071522;color:#cfe8df;font-size:12px;line-height:1.45}.linux-guide-message b{color:var(--cyan);white-space:nowrap}
      .linux-info{padding:10px 12px;border:1px solid rgba(70,210,145,.35);border-radius:12px;background:rgba(70,210,145,.08);font-size:12px}
      .linux-terminal-card{border:1px solid var(--line);border-radius:16px;overflow:hidden;background:#05080d}
      .linux-terminal-toolbar{display:flex;align-items:center;gap:8px;padding:10px;border-bottom:1px solid #253143;background:#0d1520;flex-wrap:wrap}
      .linux-terminal-toolbar .linux-spacer{flex:1}.linux-terminal-state{font-size:12px;color:var(--muted)}
      .linux-terminal-help{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:9px 12px;background:#07111b;border-bottom:1px solid #1c2c3c;color:#9db1c5;font-size:11px}
      .linux-terminal-help button{padding:6px 10px;font-size:11px}
      .linux-terminal-output{margin:0;min-height:300px;max-height:50vh;overflow:auto;padding:14px;background:#05080d;color:#d8f7dd;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;white-space:pre-wrap;overflow-wrap:anywhere}
      .linux-terminal-entry{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;padding:10px;background:#0a111b;border-top:1px solid #253143}
      .linux-terminal-entry textarea{min-height:46px;max-height:120px;resize:vertical;background:#05080d;color:#eef7ff;border:1px solid #2a3b50;border-radius:10px;padding:10px;font:13px/1.4 ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}
      @media(max-width:900px){.linux-status-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.linux-quick-actions{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:780px){.linux-welcome{grid-template-columns:1fr}.linux-welcome .linux-voice-button{width:100%}.linux-terminal-output{min-height:260px;max-height:44vh}.linux-terminal-entry{grid-template-columns:1fr}.linux-terminal-entry button{width:100%}.linux-terminal-help{align-items:flex-start;flex-direction:column}.linux-guide-head{display:block}}
      @media(max-width:480px){.linux-status-grid,.linux-quick-actions{grid-template-columns:1fr}.linux-shell{gap:11px}.linux-terminal-output{font-size:12px}}
    `;
    document.head.appendChild(style);
  }

  const markup = () => `
    <div class="linux-shell">
      <section class="linux-welcome">
        <div><span class="eyebrow">LINUX COM AJUDA DO DEVPILOT</span><h2>Você não precisa saber comandos para começar.</h2><p>Escolha uma ação simples abaixo ou converse por voz. O DevPilot explica o que será feito, mostra o comando e ajuda a entender o resultado.</p></div>
        <button class="primary linux-voice-button" id="linux-voice-help" type="button">● Falar com DevPilot</button>
      </section>

      <div class="linux-status-grid">
        <article class="linux-stat"><small>Linux Agent</small><strong id="linux-agent-status">Consultando…</strong></article>
        <article class="linux-stat"><small>Workspace</small><strong id="linux-workspace">—</strong></article>
        <article class="linux-stat"><small>Host</small><strong id="linux-hostname">—</strong></article>
        <article class="linux-stat"><small>Memória</small><strong id="linux-memory">—</strong></article>
        <article class="linux-stat"><small>Uso do sistema</small><strong id="linux-load">—</strong></article>
      </div>

      <section class="linux-guide" aria-label="Ações Linux guiadas">
        <div class="linux-guide-head"><div><span class="eyebrow">MODO GUIADO</span><h3>O que você quer fazer?</h3><p>Estas ações são somente de consulta: não apagam nem alteram arquivos.</p></div></div>
        <div class="linux-quick-actions">
          <button class="linux-quick" type="button" data-linux-command="pwd" data-linux-explain="Mostra em qual pasta você está agora."><strong>📍 Onde estou?</strong><small>Descobrir a pasta atual</small></button>
          <button class="linux-quick" type="button" data-linux-command="ls -lah" data-linux-explain="Lista arquivos e pastas, incluindo ocultos, com tamanhos legíveis."><strong>📁 Ver meus arquivos</strong><small>Listar o conteúdo desta pasta</small></button>
          <button class="linux-quick" type="button" data-linux-command="free -h" data-linux-explain="Mostra quanta memória RAM está sendo usada e quanto ainda está disponível."><strong>🧠 Ver memória</strong><small>Conferir RAM disponível</small></button>
          <button class="linux-quick" type="button" data-linux-command="df -h" data-linux-explain="Mostra quanto espaço existe e quanto está ocupado nos discos."><strong>💾 Ver espaço</strong><small>Conferir armazenamento</small></button>
          <button class="linux-quick" type="button" data-linux-command="git status --short --branch" data-linux-explain="Mostra a branch do Git e se existem arquivos modificados, sem alterar nada."><strong>🌿 Status do projeto</strong><small>Ver situação atual do Git</small></button>
          <button class="linux-quick" type="button" data-linux-command="curl -s http://127.0.0.1:8080/health && echo" data-linux-explain="Pergunta ao DevPilot local se o serviço está funcionando."><strong>✓ Testar DevPilot</strong><small>Checar saúde da aplicação</small></button>
        </div>
        <div class="linux-guide-message" id="linux-guide-message"><b>DevPilot ensina:</b><span>Escolha uma ação. Antes de executar, eu mostro em linguagem simples para que ela serve.</span></div>
      </section>

      <div class="linux-info">Seu terminal pertence ao perfil autenticado. Para usuários comuns o workspace é isolado; o Super Admin pode operar o host conforme as permissões do usuário Linux.</div>

      <article class="linux-terminal-card">
        <div class="linux-terminal-toolbar">
          <button class="primary" id="linux-terminal-start" type="button">Abrir meu Linux</button>
          <button class="ghost" id="linux-terminal-stop" type="button" disabled>Encerrar</button>
          <button class="ghost" id="linux-terminal-clear" type="button">Limpar tela</button>
          <span class="linux-spacer"></span><span class="linux-terminal-state" id="linux-terminal-state">sem sessão</span>
        </div>
        <div class="linux-terminal-help"><span>Terminal avançado — use quando quiser digitar comandos diretamente.</span><button class="ghost" id="linux-explain-output" type="button">✦ Explicar esta saída</button></div>
        <pre class="linux-terminal-output" id="linux-terminal-output" aria-live="polite">Abra seu Linux ou escolha uma ação guiada acima.\n</pre>
        <div class="linux-terminal-entry">
          <textarea id="linux-terminal-input" spellcheck="false" placeholder="Digite um comando ou use as ações guiadas acima. Enter envia; Shift+Enter quebra linha." disabled></textarea>
          <button class="primary" id="linux-terminal-send" type="button" disabled>Executar</button>
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

  const stripAnsi = value => String(value || '')
    .replace(/\u001b\][^\u0007]*(?:\u0007|\u001b\\)/g, '')
    .replace(/\u001b\[[0-?]*[ -\/]*[@-~]/g, '')
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001a\u001c-\u001f\u007f]/g, '');

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

  const openVoiceHelp = ({explainOutput = false} = {}) => {
    const modal = document.querySelector('#voice-modal');
    const transcript = modal?.querySelector('#voice-transcript');
    const status = modal?.querySelector('#voice-status');
    if (!modal) {
      if (typeof window.toast === 'function') window.toast('Assistente de voz ainda não está disponível.');
      return;
    }
    if (explainOutput && transcript) {
      const terminal = stripAnsi(view?.querySelector('#linux-terminal-output')?.textContent || '').trim().slice(-5000);
      transcript.value = `Estou aprendendo Linux no DevPilot. Explique esta saída em português simples, diga se existe algum problema e qual seria o próximo passo seguro:\n\n${terminal}`;
      transcript.dispatchEvent(new Event('input', {bubbles: true}));
    } else if (transcript) {
      transcript.value = '';
      transcript.placeholder = 'Pergunte por voz: “como vejo meus arquivos?”, “o que significa isso?”, “me ensine Linux passo a passo”…';
      transcript.dispatchEvent(new Event('input', {bubbles: true}));
    }
    if (status) status.textContent = 'Assistente Linux: fale normalmente. O DevPilot explica em linguagem simples.';
    if (!modal.open) modal.showModal();
    if (!explainOutput) window.setTimeout(() => modal.querySelector('#voice-start')?.click(), 250);
  };

  const setGuide = (command, explanation) => {
    const message = view?.querySelector('#linux-guide-message span');
    if (message) message.textContent = `${explanation} Comando usado: ${command}`;
  };

  const bindControls = () => {
    bindOnce('#linux-terminal-start', 'click', 'linuxBound', createSession);
    bindOnce('#linux-terminal-stop', 'click', 'linuxBound', closeSession);
    bindOnce('#linux-terminal-clear', 'click', 'linuxBound', () => {
      const output = view?.querySelector('#linux-terminal-output');
      if (output) output.textContent = 'Tela limpa. Nenhum arquivo foi apagado.\n';
    });
    bindOnce('#linux-terminal-send', 'click', 'linuxBound', sendInput);
    bindOnce('#linux-voice-help', 'click', 'linuxBound', () => openVoiceHelp());
    bindOnce('#linux-explain-output', 'click', 'linuxBound', () => openVoiceHelp({explainOutput: true}));

    view?.querySelectorAll('[data-linux-command]').forEach(button => {
      if (button.dataset.linuxQuickBound === '1') return;
      button.dataset.linuxQuickBound = '1';
      button.addEventListener('click', () => runSafeCommand(button.dataset.linuxCommand, button.dataset.linuxExplain));
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
    const clean = stripAnsi(text);
    if (!output || !clean) return;
    output.textContent += clean;
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
      setText('#linux-workspace', profile.mode === 'full-host-access' ? 'host completo' : (profile.workspace_key ? `perfil ${profile.workspace_key.slice(0, 8)}` : 'isolado'));
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
    if (sessionId) return true;
    try {
      const session = await api('/api/linux/terminal/sessions', {method: 'POST', body: JSON.stringify({columns: 120, rows: 34})});
      sessionId = session.id;
      lastSequence = 0;
      setTerminalEnabled(true);
      setText('#linux-terminal-state', `sessão ${sessionId.slice(0, 8)} · PID ${session.pid}`);
      appendOutput(`\n[DevPilot] Linux aberto. Você pode usar os botões guiados ou digitar um comando.\n`);
      view?.querySelector('#linux-terminal-input')?.focus();
      startPolling();
      return true;
    } catch (error) {
      appendOutput(`\n[erro] ${error.message}\n`);
      return false;
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

  async function sendRaw(raw) {
    if (!sessionId || sending || !String(raw || '').trim()) return false;
    sending = true;
    try {
      await api(`/api/linux/terminal/sessions/${sessionId}/input`, {method: 'POST', body: JSON.stringify({data: `${raw}\n`})});
      return true;
    } catch (error) {
      appendOutput(`\n[erro] ${error.message}\n`);
      return false;
    } finally {
      sending = false;
    }
  }

  async function runSafeCommand(command, explanation) {
    ensureUI();
    setGuide(command, explanation);
    if (!sessionId) {
      const opened = await createSession();
      if (!opened) return;
    }
    appendOutput(`\n[DevPilot] ${explanation}\n$ ${command}\n`);
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
