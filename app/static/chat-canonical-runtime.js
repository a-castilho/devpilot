(() => {
  'use strict';

  const modal = document.querySelector('#voice-modal');
  const panel = modal?.querySelector('.voice-modal-enhanced');
  const stage = panel?.querySelector('.voice-chatgpt-stage');
  const conversation = panel?.querySelector('#voice-visible-conversation');
  const projectSelect = panel?.querySelector('#voice-project');
  if (!modal || !panel || !stage || !conversation) return;
  if (panel.dataset.canonicalChat === '1') return;
  panel.dataset.canonicalChat = '1';

  const STORAGE_PROJECT = 'devpilot-chat-active-project-id';
  const STORAGE_MODE = 'devpilot-chat-mode';
  const STORAGE_PREFIX = 'devpilot-chat-canonical-v1';
  const MAX_STORED = 60;
  const MAX_REQUEST = 12;
  const MODES = {
    planning: {label: 'Planejamento', profile: 'DevPilot Planejador', description: 'Analisa, consulta projeto, documentação e RAG.'},
    build: {label: 'Construir', profile: 'DevPilot Construtor', description: 'Prepara uma execução real para o projeto selecionado.'},
  };

  const style = document.createElement('style');
  style.dataset.canonicalChat = '1';
  style.textContent = `
    #voice-modal[open]{box-sizing:border-box;max-width:none!important;max-height:none!important;width:100vw!important;height:100dvh!important;margin:0!important;padding:0!important;background:rgba(2,10,17,.98)!important}
    #voice-modal .voice-modal-enhanced{box-sizing:border-box!important;width:100%!important;max-width:980px!important;height:100dvh!important;max-height:100dvh!important;margin:0 auto!important;padding:clamp(10px,2vw,18px)!important;display:flex!important;flex-direction:column!important;overflow:hidden!important}
    #voice-modal .voice-chatgpt-stage{flex:1 1 auto!important;min-height:0!important;max-height:none!important;display:flex!important;flex-direction:column!important;overflow:hidden!important;padding-bottom:4px!important}
    #voice-modal .voice-chatgpt-orb{flex:0 0 auto!important;margin:0 auto 4px!important;transform:scale(.72);transform-origin:center center}
    #voice-modal .voice-chat-mode-switch{flex:0 0 auto!important;position:relative!important;z-index:3!important}
    #voice-modal .voice-chat-mode-button{pointer-events:auto!important;touch-action:manipulation!important}
    #voice-modal .voice-chat-profile-banner{flex:0 0 auto!important}
    #voice-modal #voice-visible-conversation{flex:1 1 auto!important;min-height:120px!important;max-height:none!important;width:min(100%,820px)!important;overflow-y:auto!important;overflow-x:hidden!important;scroll-behavior:smooth!important;overscroll-behavior:contain!important;padding:12px 5px 24px!important;scrollbar-gutter:stable}
    #voice-modal .voice-visible-turn{max-width:88%!important;font-size:clamp(.94rem,2.8vw,1.04rem)!important;line-height:1.52!important}
    #voice-modal .voice-visible-turn[data-role="assistant"]{width:auto!important;max-width:94%!important}
    #voice-modal .voice-chatgpt-status{flex:0 0 auto!important;min-height:24px!important;padding:2px 5px!important}
    #voice-modal .voice-chatgpt-composer{flex:0 0 auto!important;position:relative!important;bottom:auto!important;margin-top:4px!important;z-index:20!important;padding-bottom:max(4px,env(safe-area-inset-bottom))!important}
    #voice-modal #voice-transcript{max-height:120px!important;overflow-y:auto!important;resize:none!important}
    #voice-modal .voice-record-button[data-recording="1"]{box-shadow:0 0 0 4px rgba(248,113,113,.18)!important;background:rgba(127,29,29,.85)!important}
    #voice-modal .canonical-context{display:flex;flex-wrap:wrap;gap:6px;margin:2px auto 5px;width:min(100%,820px);font-size:.7rem;color:#a9bbc5}
    #voice-modal .canonical-context span{border:1px solid rgba(94,234,212,.18);border-radius:999px;padding:3px 7px;background:rgba(15,23,42,.55)}
    #voice-modal .canonical-sources{display:flex;flex-wrap:wrap;gap:5px;margin-top:7px}
    #voice-modal .canonical-source{font-size:.66rem;color:#a8c8c5;border:1px solid rgba(45,212,191,.18);border-radius:999px;padding:2px 7px;background:rgba(13,148,136,.08)}
    #voice-modal .canonical-typing{opacity:.78;font-style:italic}
    @media(max-width:640px){
      #voice-modal .voice-modal-enhanced{padding:8px 10px 6px!important}
      #voice-modal .voice-chatgpt-orb{transform:scale(.56);margin-top:-12px!important;margin-bottom:-10px!important}
      #voice-modal .voice-chat-profile-banner{font-size:.72rem!important;padding:6px 8px!important}
      #voice-modal #voice-visible-conversation{padding-top:6px!important;padding-bottom:12px!important;gap:10px!important}
      #voice-modal .voice-visible-turn{max-width:94%!important;padding:10px 12px!important}
      #voice-modal .voice-visible-turn[data-role="assistant"]{max-width:98%!important}
      #voice-modal .voice-chat-mode-button{min-height:52px!important}
    }
    @media(max-height:720px){#voice-modal .voice-chatgpt-orb{display:none!important}}
  `;
  document.head.appendChild(style);

  const $ = (selector, root = panel) => root.querySelector(selector);
  const clean = (value) => String(value ?? '').replace(/\r\n?/g, '\n').trim();
  const projectId = () => clean(projectSelect?.value || localStorage.getItem(STORAGE_PROJECT) || '');
  const projectName = () => projectSelect?.selectedOptions?.[0]?.textContent?.trim() || 'Geral';
  const mode = () => (localStorage.getItem(STORAGE_MODE) === 'build' ? 'build' : 'planning');
  const sessionKey = () => `${STORAGE_PREFIX}:${projectId() || 'general'}`;
  let turns = [];
  let busy = false;
  let recorder = null;
  let stream = null;
  let chunks = [];
  let recording = false;

  const statusNode = $('#voice-status');
  const profileBanner = $('.voice-chat-profile-banner');
  const profileCopy = profileBanner?.querySelector('span');

  const replaceInteractive = (node) => {
    if (!node) return null;
    const clone = node.cloneNode(true);
    node.replaceWith(clone);
    return clone;
  };

  // Remove todos os listeners legados exatamente nos controles que este runtime passa a possuir.
  let transcript = replaceInteractive($('#voice-transcript'));
  let sendButton = replaceInteractive($('#voice-chat-send'));
  let micButton = replaceInteractive($('#voice-start'));
  let newButton = replaceInteractive($('.voice-chat-new-button'));
  const modeButtons = [...panel.querySelectorAll('.voice-chat-mode-button')].map(replaceInteractive).filter(Boolean);

  const contextRow = document.createElement('div');
  contextRow.className = 'canonical-context';
  profileBanner?.after(contextRow);

  const setStatus = (message) => { if (statusNode) statusNode.textContent = message; };
  const save = () => {
    turns = turns.slice(-MAX_STORED);
    try { sessionStorage.setItem(sessionKey(), JSON.stringify(turns)); } catch (_) {}
  };
  const load = () => {
    try {
      const parsed = JSON.parse(sessionStorage.getItem(sessionKey()) || '[]');
      turns = Array.isArray(parsed) ? parsed.filter(item => ['user','assistant'].includes(item?.role) && clean(item?.text)).slice(-MAX_STORED) : [];
    } catch (_) { turns = []; }
  };
  const scrollBottom = (behavior = 'smooth') => requestAnimationFrame(() => conversation.scrollTo({top: conversation.scrollHeight, behavior}));

  const renderContext = (knowledge = null) => {
    contextRow.replaceChildren();
    const project = document.createElement('span');
    project.textContent = `Projeto: ${projectName()}`;
    const activeMode = document.createElement('span');
    activeMode.textContent = `Modo: ${MODES[mode()].label}`;
    contextRow.append(project, activeMode);
    if (knowledge) {
      const memory = document.createElement('span');
      memory.textContent = knowledge.rag_used ? `RAG: ${knowledge.sources?.length || 0} fonte(s)` : `Contexto: ${knowledge.mode || 'LIVE'}`;
      contextRow.append(memory);
    }
  };

  const renderTurn = (turn, index) => {
    const article = document.createElement('article');
    article.className = 'voice-visible-turn';
    article.dataset.role = turn.role;
    if (turn.error) article.dataset.error = '1';
    const who = document.createElement('strong');
    who.textContent = turn.role === 'user' ? 'Você' : 'DevPilot';
    const body = document.createElement('div');
    body.className = 'voice-message-body';
    const lines = clean(turn.text).split('\n');
    lines.forEach((line, lineIndex) => {
      if (!line && lineIndex !== lines.length - 1) {
        body.appendChild(document.createElement('br'));
        return;
      }
      const p = document.createElement('p');
      p.textContent = line;
      body.appendChild(p);
    });
    article.append(who, body);
    if (turn.sources?.length) {
      const sources = document.createElement('div');
      sources.className = 'canonical-sources';
      turn.sources.slice(0, 6).forEach(source => {
        const item = document.createElement('span');
        item.className = 'canonical-source';
        item.textContent = source.source_path || source.source_id || 'documentação';
        sources.appendChild(item);
      });
      article.appendChild(sources);
    }
    article.dataset.turnIndex = String(index);
    return article;
  };

  const render = () => {
    conversation.replaceChildren();
    if (!turns.length) {
      const empty = document.createElement('div');
      empty.className = 'voice-visible-empty';
      empty.textContent = projectId()
        ? `Converse normalmente. Estou usando informações, documentação e memória do projeto ${projectName()}.`
        : 'Converse normalmente ou escolha um projeto no botão + para ativar contexto e documentação.';
      conversation.appendChild(empty);
    } else turns.forEach((turn, index) => conversation.appendChild(renderTurn(turn, index)));
    scrollBottom('auto');
  };

  const refreshMode = () => {
    const selected = mode();
    modeButtons.forEach(button => {
      const active = button.dataset.chatMode === selected;
      button.dataset.active = active ? '1' : '0';
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    if (profileCopy) {
      profileCopy.replaceChildren();
      const strong = document.createElement('strong');
      strong.textContent = MODES[selected].profile;
      profileCopy.append(strong, document.createTextNode(` · ${MODES[selected].description}`));
    }
    panel.dataset.chatMode = selected;
    renderContext();
  };

  modeButtons.forEach(button => button.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();
    const selected = button.dataset.chatMode === 'build' ? 'build' : 'planning';
    localStorage.setItem(STORAGE_MODE, selected);
    refreshMode();
    setStatus(`${MODES[selected].label} ativo.`);
    transcript?.focus();
  }, true));

  const requestHistory = () => turns.slice(-MAX_REQUEST).map(({role, text}) => ({role, text: clean(text).slice(0, 4000)}));

  async function send(textOverride = '') {
    const text = clean(textOverride || transcript?.value);
    if (!text || busy) return;
    busy = true;
    if (transcript) transcript.value = '';
    if (sendButton) sendButton.disabled = true;
    turns.push({role: 'user', text});
    save();
    render();
    const waiting = document.createElement('div');
    waiting.className = 'voice-visible-thinking canonical-typing';
    waiting.textContent = 'DevPilot está pensando…';
    conversation.appendChild(waiting);
    scrollBottom();
    setStatus('Consultando projeto, documentação e provedores de IA…');
    try {
      const data = await api('/chat', {
        method: 'POST',
        body: JSON.stringify({
          transcript: text,
          project_id: projectId() || null,
          history: requestHistory().slice(0, -1),
          mode: mode(),
          response_style: 'chat',
        }),
      });
      turns.push({
        role: 'assistant',
        text: clean(data?.reply || 'Resposta vazia.'),
        sources: Array.isArray(data?.knowledge?.sources) ? data.knowledge.sources : [],
      });
      save();
      renderContext(data?.knowledge || null);
      const execution = data?.execution;
      if (mode() === 'build' && execution?.task_id) {
        setStatus(`Construção preparada · tarefa ${String(execution.task_id).slice(0, 8)} · ${execution.status || 'pronta'}`);
      } else {
        setStatus(data?.notice || `Pronto · ${data?.provider || 'IA'} ${data?.model ? '· ' + data.model : ''}`);
      }
    } catch (error) {
      turns.push({role: 'assistant', text: clean(error?.message || 'Não foi possível responder.'), error: true});
      save();
      setStatus(error?.message || 'Falha ao conversar com o DevPilot.');
    } finally {
      busy = false;
      if (sendButton) sendButton.disabled = !clean(transcript?.value);
      render();
      transcript?.focus();
    }
  }

  const resize = () => {
    if (!transcript) return;
    transcript.style.height = 'auto';
    transcript.style.height = `${Math.min(Math.max(transcript.scrollHeight, 28), 120)}px`;
    if (sendButton) sendButton.disabled = busy || !clean(transcript.value);
  };
  transcript?.addEventListener('input', resize);
  transcript?.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      void send();
    }
  });
  sendButton?.addEventListener('click', event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    void send();
  }, true);

  const cleanupStream = () => {
    try { stream?.getTracks?.().forEach(track => track.stop()); } catch (_) {}
    stream = null;
    recorder = null;
    chunks = [];
  };

  async function transcribe(blob) {
    const type = String(blob.type || 'audio/webm').split(';')[0] || 'audio/webm';
    const ext = type.includes('ogg') ? 'ogg' : type.includes('mp4') ? 'm4a' : 'webm';
    const form = new FormData();
    form.append('audio', new Blob([blob], {type}), `chat.${ext}`);
    const data = await api('/voice/transcriptions', {method: 'POST', body: form});
    return clean(data?.text);
  }

  async function stopRecording() {
    if (!recording || !recorder) return;
    recording = false;
    micButton.dataset.recording = '0';
    micButton.setAttribute('aria-pressed', 'false');
    setStatus('Processando áudio…');
    const active = recorder;
    await new Promise(resolve => {
      active.addEventListener('stop', resolve, {once: true});
      try { active.stop(); } catch (_) { resolve(); }
    });
    const blob = new Blob(chunks, {type: active.mimeType || 'audio/webm'});
    cleanupStream();
    try {
      const text = await transcribe(blob);
      if (!text) throw new Error('Não consegui reconhecer fala nesse áudio.');
      setStatus(`Ouvi: “${text.slice(0, 90)}${text.length > 90 ? '…' : ''}”`);
      await send(text);
    } catch (error) {
      setStatus(error?.message || 'Falha ao transcrever áudio.');
    }
  }

  async function startRecording() {
    if (recording) return stopRecording();
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!Recognition) {
        setStatus('Este navegador não disponibilizou captura de voz.');
        return;
      }
      const recognition = new Recognition();
      recognition.lang = 'pt-BR';
      recognition.interimResults = false;
      recognition.continuous = false;
      recognition.onresult = event => void send(clean(event.results?.[0]?.[0]?.transcript));
      recognition.onerror = event => setStatus(`Microfone: ${event.error || 'falha de reconhecimento'}.`);
      recognition.onstart = () => { micButton.dataset.recording = '1'; setStatus('Ouvindo…'); };
      recognition.onend = () => { micButton.dataset.recording = '0'; };
      recognition.start();
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}, video: false});
      const preferred = ['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus'].find(type => MediaRecorder.isTypeSupported?.(type));
      recorder = preferred ? new MediaRecorder(stream, {mimeType: preferred}) : new MediaRecorder(stream);
      chunks = [];
      recorder.addEventListener('dataavailable', event => { if (event.data?.size) chunks.push(event.data); });
      recorder.addEventListener('error', () => { recording = false; cleanupStream(); setStatus('Falha durante a gravação.'); });
      recorder.start(250);
      recording = true;
      micButton.dataset.recording = '1';
      micButton.setAttribute('aria-pressed', 'true');
      setStatus('Ouvindo… toque novamente no microfone para enviar.');
    } catch (error) {
      cleanupStream();
      const denied = error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError';
      setStatus(denied ? 'Permissão do microfone negada pelo navegador.' : 'Não foi possível abrir o microfone.');
    }
  }

  micButton?.addEventListener('click', event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    void (recording ? stopRecording() : startRecording());
  }, true);

  newButton?.addEventListener('click', event => {
    event.preventDefault();
    event.stopImmediatePropagation();
    turns = [];
    try { sessionStorage.removeItem(sessionKey()); } catch (_) {}
    render();
    setStatus('Nova conversa iniciada.');
    transcript?.focus();
  }, true);

  projectSelect?.addEventListener('change', () => {
    const value = clean(projectSelect.value);
    localStorage.setItem(STORAGE_PROJECT, value);
    load();
    render();
    renderContext();
    setStatus(value ? `Contexto alterado para ${projectName()}.` : 'Chat geral ativo.');
  });

  // Abertura/teclado móvel: mantém a mensagem mais recente e o composer visíveis.
  const fitViewport = () => {
    const height = window.visualViewport?.height;
    if (height && modal.open) panel.style.height = `${Math.round(height)}px`;
    scrollBottom('auto');
  };
  window.visualViewport?.addEventListener('resize', fitViewport);
  window.visualViewport?.addEventListener('scroll', fitViewport);
  modal.addEventListener('close', () => {
    if (recording) void stopRecording();
    panel.style.height = '';
  });
  document.addEventListener('devpilot:chat-opened', () => {
    fitViewport();
    transcript?.focus();
  });

  load();
  refreshMode();
  render();
  resize();
  setStatus('Pronto. Digite uma mensagem ou use o microfone.');
})();
