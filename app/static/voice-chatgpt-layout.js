(() => {
  'use strict';

  const modal = document.querySelector('#voice-modal');
  const panel = modal?.querySelector('.voice-modal-enhanced');
  const transcript = panel?.querySelector('#voice-transcript');
  const sendButton = panel?.querySelector('#voice-chat-send');
  const stage = panel?.querySelector('.voice-chatgpt-stage');
  const statusNode = panel?.querySelector('#voice-status');
  const projectSelect = panel?.querySelector('#voice-project');
  const outputModeSelect = panel?.querySelector('#voice-output-mode');

  const ACTIVE_PROJECT_STORAGE_KEY = 'devpilot-chat-active-project-id';
  const CHAT_MODE_STORAGE_KEY = 'devpilot-chat-mode';
  const CHAT_SESSION_PREFIX = 'devpilot-chat-session-v2';
  const MAX_STORED_TURNS = 40;
  const MAX_REQUEST_TURNS = 12;
  const MAX_HISTORY_TEXT = 4000;
  const CHAT_MODES = {
    planning: {
      label: 'Planejamento',
      profile: 'DevPilot Planejador',
      description: 'Analisa e planeja sem executar alterações.',
    },
    build: {
      label: 'Construir',
      profile: 'DevPilot Construtor',
      description: 'Prepara uma tarefa real, auditada e aguardando aprovação.',
    },
  };

  if (!modal || !panel || !transcript || !sendButton || !stage || !statusNode) return;
  if (panel.dataset.voiceChatgptLayout === '7') return;
  panel.dataset.voiceChatgptLayout = '7';
  panel.classList.add('voice-ui-polished');

  if (!document.querySelector('link[data-voice-ui-polish]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/assets/voice-ui-polish.css?v=20260829-chat7';
    link.dataset.voiceUiPolish = '1';
    document.head.appendChild(link);
  }

  if (!stage.querySelector('.voice-chatgpt-orb')) {
    const visual = document.createElement('div');
    visual.className = 'voice-visual voice-chatgpt-orb';
    visual.setAttribute('aria-hidden', 'true');
    visual.innerHTML = '<div class="pulse-orb listening"><span></span></div>';
    stage.prepend(visual);
  }

  const legacyPreview = stage.querySelector('#voice-chat-preview');
  if (legacyPreview) legacyPreview.hidden = true;

  const modeSwitch = document.createElement('div');
  modeSwitch.className = 'voice-chat-mode-switch';
  modeSwitch.setAttribute('role', 'group');
  modeSwitch.setAttribute('aria-label', 'Modo do chat DevPilot');
  modeSwitch.innerHTML = `
    <button type="button" class="voice-chat-mode-button" data-chat-mode="planning" aria-pressed="false">
      <span>Planejamento</span>
      <small>analisar e planejar</small>
    </button>
    <button type="button" class="voice-chat-mode-button" data-chat-mode="build" aria-pressed="false">
      <span>Construir</span>
      <small>preparar execução</small>
    </button>
  `;

  const profileBanner = document.createElement('div');
  profileBanner.className = 'voice-chat-profile-banner';
  profileBanner.setAttribute('aria-live', 'polite');

  const profileCopy = document.createElement('span');
  const newChatButton = document.createElement('button');
  newChatButton.type = 'button';
  newChatButton.className = 'voice-chat-new-button';
  newChatButton.textContent = 'Nova conversa';
  newChatButton.setAttribute('aria-label', 'Iniciar nova conversa');
  profileBanner.append(profileCopy, newChatButton);

  const conversation = document.createElement('section');
  conversation.id = 'voice-visible-conversation';
  conversation.className = 'voice-visible-conversation';
  conversation.setAttribute('aria-live', 'polite');
  conversation.setAttribute('aria-label', 'Conversa com o DevPilot');

  const statusWrapper = stage.querySelector('.voice-chatgpt-status');
  if (statusWrapper) {
    stage.insertBefore(modeSwitch, statusWrapper);
    stage.insertBefore(profileBanner, statusWrapper);
    stage.insertBefore(conversation, statusWrapper);
  } else {
    stage.append(modeSwitch, profileBanner, conversation);
  }

  if (!document.querySelector('style[data-voice-visible-conversation="7"]')) {
    const style = document.createElement('style');
    style.dataset.voiceVisibleConversation = '7';
    style.textContent = `
      #voice-chat-preview{display:none!important}
      .voice-chat-mode-switch{width:min(100%,820px);display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:2px auto 4px;padding:4px;border:1px solid rgba(148,163,184,.18);border-radius:16px;background:rgba(15,23,42,.54)}
      .voice-chat-mode-button{min-width:0;border:1px solid transparent;border-radius:12px;background:transparent;color:#aab8c2;padding:9px 12px;display:grid;gap:2px;text-align:left;cursor:pointer;transition:background .16s ease,border-color .16s ease,color .16s ease,transform .16s ease}
      .voice-chat-mode-button:hover{transform:translateY(-1px);color:#edf7f7;background:rgba(148,163,184,.08)}
      .voice-chat-mode-button span{font-weight:750;font-size:.88rem;line-height:1.1}
      .voice-chat-mode-button small{font-size:.68rem;opacity:.72;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .voice-chat-mode-button[data-active="1"][data-chat-mode="planning"]{color:#e8f5ff;border-color:rgba(96,165,250,.5);background:rgba(59,130,246,.18)}
      .voice-chat-mode-button[data-active="1"][data-chat-mode="build"]{color:#ebfff7;border-color:rgba(52,211,153,.5);background:rgba(16,185,129,.18)}
      .voice-chat-profile-banner{width:min(100%,820px);margin:0 auto 2px;padding:7px 10px 7px 12px;border-radius:10px;color:#a7b5bd;background:rgba(15,23,42,.38);font-size:.74rem;line-height:1.35;display:flex;align-items:center;justify-content:space-between;gap:10px}
      .voice-chat-profile-banner strong{color:#e7f7f5}
      .voice-chat-new-button,.voice-message-action,.voice-code-copy,.voice-chat-stop{border:1px solid rgba(148,163,184,.2);background:rgba(15,23,42,.52);color:#c8d4da;border-radius:9px;padding:5px 8px;font:inherit;cursor:pointer}
      .voice-chat-new-button:hover,.voice-message-action:hover,.voice-code-copy:hover,.voice-chat-stop:hover{background:rgba(148,163,184,.12);color:#f3fbfd}
      .voice-visible-conversation{width:min(100%,820px);display:flex;flex-direction:column;gap:14px;max-height:min(54vh,560px);overflow:auto;padding:10px 4px 14px;scrollbar-width:thin;overscroll-behavior:contain}
      .voice-visible-empty{align-self:center;color:#91a0aa;font-size:.9rem;padding:18px 14px;text-align:center}
      .voice-visible-turn{max-width:94%;display:grid;gap:6px;padding:11px 14px;border-radius:16px;line-height:1.52;word-break:break-word}
      .voice-visible-turn>strong{font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;opacity:.68}
      .voice-visible-turn[data-role="user"]{align-self:flex-end;background:rgba(79,91,101,.34);color:#eef4f7;border-bottom-right-radius:5px;white-space:pre-wrap}
      .voice-visible-turn[data-role="assistant"]{align-self:flex-start;width:min(94%,780px);background:rgba(0,197,176,.08);border:1px solid rgba(37,238,211,.14);color:#e7fffb;border-bottom-left-radius:5px}
      .voice-visible-turn[data-error="1"]{background:rgba(160,65,65,.16);border-color:rgba(255,124,124,.22);color:#ffdede}
      .voice-message-body{min-width:0;overflow-wrap:anywhere}
      .voice-message-body p{margin:.45em 0}.voice-message-body p:first-child{margin-top:0}.voice-message-body p:last-child{margin-bottom:0}
      .voice-message-body h2,.voice-message-body h3,.voice-message-body h4{margin:.8em 0 .35em;line-height:1.25;color:#f2fffd}.voice-message-body h2{font-size:1.12rem}.voice-message-body h3{font-size:1.02rem}.voice-message-body h4{font-size:.96rem}
      .voice-message-body ul,.voice-message-body ol{margin:.45em 0;padding-left:1.35rem}.voice-message-body li{margin:.22em 0}
      .voice-message-body blockquote{margin:.5em 0;padding:.2em .8em;border-left:3px solid rgba(45,212,191,.45);color:#bed0d3}
      .voice-message-body code{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;background:rgba(2,6,23,.55);border-radius:5px;padding:.08em .3em;font-size:.9em}
      .voice-code-block{margin:.65em 0;border:1px solid rgba(148,163,184,.2);border-radius:12px;background:#0b0f14;overflow:hidden}
      .voice-code-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:6px 9px;background:rgba(148,163,184,.08);color:#95a8b1;font-size:.7rem}
      .voice-code-block pre{margin:0;padding:12px 14px;overflow:auto;white-space:pre;tab-size:2}.voice-code-block pre code{background:none;padding:0;border-radius:0;font-size:.82rem;color:#e5edf0}
      .voice-message-actions{display:flex;gap:6px;flex-wrap:wrap;min-height:26px}.voice-message-action{font-size:.7rem;padding:4px 7px}
      .voice-visible-thinking{align-self:flex-start;display:flex;align-items:center;gap:7px;padding:11px 14px;border-radius:16px;background:rgba(0,197,176,.08)}
      .voice-visible-thinking i{width:6px;height:6px;border-radius:50%;background:currentColor;opacity:.45;animation:voiceThinking 1s infinite ease-in-out}
      .voice-visible-thinking i:nth-child(2){animation-delay:.14s}.voice-visible-thinking i:nth-child(3){animation-delay:.28s}.voice-chat-stop{margin-left:7px;font-size:.7rem}
      @keyframes voiceThinking{0%,70%,100%{transform:translateY(0);opacity:.35}35%{transform:translateY(-4px);opacity:1}}
      @media(max-width:640px){.voice-chat-mode-switch{gap:5px}.voice-chat-mode-button{padding:8px}.voice-chat-mode-button small{font-size:.62rem}.voice-chat-profile-banner{align-items:flex-start}.voice-visible-conversation{max-height:48vh;padding-inline:2px}.voice-visible-turn{max-width:96%;font-size:.94rem;padding:10px 12px}.voice-visible-turn[data-role="assistant"]{width:96%}.voice-code-block pre{font-size:.78rem}}
    `;
    document.head.appendChild(style);
  }

  const cleanText = (value) => String(value ?? '').replace(/\r\n?/g, '\n').trim();
  const normalizeProjectId = (value) => String(value ?? '').trim();
  const normalizeMode = (value) => Object.prototype.hasOwnProperty.call(CHAT_MODES, value) ? value : 'planning';
  const activeChatMode = () => normalizeMode(localStorage.getItem(CHAT_MODE_STORAGE_KEY) || 'planning');
  const currentUserKey = () => {
    try {
      if (typeof state !== 'undefined' && state?.currentUser?.id) return String(state.currentUser.id);
    } catch (_) {
      // A sessão continua isolada por projeto/modo mesmo se a identidade ainda não estiver disponível.
    }
    return 'authenticated';
  };
  const projectOptionExists = (projectId) => {
    if (!projectSelect) return false;
    const expected = normalizeProjectId(projectId);
    return [...projectSelect.options].some((option) => normalizeProjectId(option.value) === expected);
  };
  const projectLabel = (projectId) => {
    if (!projectSelect) return '';
    const expected = normalizeProjectId(projectId);
    return [...projectSelect.options].find((option) => normalizeProjectId(option.value) === expected)?.textContent?.trim() || '';
  };
  const storeActiveProject = (projectId) => {
    const value = normalizeProjectId(projectId);
    localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, value);
    window.dispatchEvent(new CustomEvent('devpilot:active-project-changed', {detail: {project_id: value || null}}));
    return value;
  };
  const restoreActiveProject = () => {
    if (!projectSelect) return '';
    const storedRaw = localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
    if (storedRaw !== null) {
      const stored = normalizeProjectId(storedRaw);
      if (projectOptionExists(stored)) {
        projectSelect.value = stored;
        return stored;
      }
    }
    const selected = normalizeProjectId(projectSelect.value);
    if (projectOptionExists(selected)) {
      localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, selected);
      return selected;
    }
    const firstProject = [...projectSelect.options].find((option) => normalizeProjectId(option.value));
    if (firstProject) {
      projectSelect.value = firstProject.value;
      localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, normalizeProjectId(firstProject.value));
      return normalizeProjectId(firstProject.value);
    }
    return '';
  };
  const activeProjectId = () => restoreActiveProject();
  const sessionKey = () => `${CHAT_SESSION_PREFIX}:${currentUserKey()}:${activeProjectId() || 'general'}:${activeChatMode()}`;

  let history = [];
  let requestInFlight = false;
  let requestSequence = 0;
  let activeController = null;
  let pendingRawInput = '';

  const loadHistory = () => {
    try {
      const parsed = JSON.parse(sessionStorage.getItem(sessionKey()) || '[]');
      history = Array.isArray(parsed)
        ? parsed.filter((turn) => ['user', 'assistant'].includes(turn?.role) && cleanText(turn?.text)).slice(-MAX_STORED_TURNS).map((turn) => ({role: turn.role, text: cleanText(turn.text)}))
        : [];
    } catch (_) {
      history = [];
    }
    return history;
  };
  const saveHistory = () => {
    history = history.slice(-MAX_STORED_TURNS);
    try {
      sessionStorage.setItem(sessionKey(), JSON.stringify(history));
    } catch (_) {
      // Falha de quota do navegador não pode interromper o chat.
    }
  };
  const scrollConversation = () => { conversation.scrollTop = conversation.scrollHeight; };

  function appendInline(target, text) {
    const source = String(text || '');
    const tokenPattern = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^\]\n]+\]\(https?:\/\/[^)\s]+\))/g;
    let cursor = 0;
    for (const match of source.matchAll(tokenPattern)) {
      if (match.index > cursor) target.appendChild(document.createTextNode(source.slice(cursor, match.index)));
      const token = match[0];
      if (token.startsWith('**')) {
        const strong = document.createElement('strong');
        strong.textContent = token.slice(2, -2);
        target.appendChild(strong);
      } else if (token.startsWith('`')) {
        const code = document.createElement('code');
        code.textContent = token.slice(1, -1);
        target.appendChild(code);
      } else {
        const parts = /^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/.exec(token);
        if (parts) {
          const anchor = document.createElement('a');
          anchor.textContent = parts[1];
          anchor.href = parts[2];
          anchor.target = '_blank';
          anchor.rel = 'noopener noreferrer';
          target.appendChild(anchor);
        } else {
          target.appendChild(document.createTextNode(token));
        }
      }
      cursor = match.index + token.length;
    }
    if (cursor < source.length) target.appendChild(document.createTextNode(source.slice(cursor)));
  }

  function renderRichText(target, text) {
    const lines = cleanText(text).split('\n');
    let index = 0;
    const paragraph = (values) => {
      const node = document.createElement('p');
      appendInline(node, values.join(' '));
      target.appendChild(node);
    };
    while (index < lines.length) {
      const line = lines[index];
      if (!line.trim()) {
        index += 1;
        continue;
      }
      const fence = /^```([^\s`]*)\s*$/.exec(line.trim());
      if (fence) {
        const language = fence[1] || 'código';
        index += 1;
        const codeLines = [];
        while (index < lines.length && !/^```\s*$/.test(lines[index].trim())) {
          codeLines.push(lines[index]);
          index += 1;
        }
        if (index < lines.length) index += 1;
        const wrapper = document.createElement('div');
        wrapper.className = 'voice-code-block';
        const head = document.createElement('div');
        head.className = 'voice-code-head';
        const label = document.createElement('span');
        label.textContent = language;
        const copy = document.createElement('button');
        copy.type = 'button';
        copy.className = 'voice-code-copy';
        copy.textContent = 'Copiar código';
        const codeText = codeLines.join('\n');
        copy.addEventListener('click', async () => {
          try {
            await navigator.clipboard.writeText(codeText);
            copy.textContent = 'Copiado';
            window.setTimeout(() => { copy.textContent = 'Copiar código'; }, 1400);
          } catch (_) {
            if (typeof toast === 'function') toast('Não foi possível copiar o código.');
          }
        });
        head.append(label, copy);
        const pre = document.createElement('pre');
        const code = document.createElement('code');
        code.textContent = codeText;
        pre.appendChild(code);
        wrapper.append(head, pre);
        target.appendChild(wrapper);
        continue;
      }
      const heading = /^(#{1,3})\s+(.+)$/.exec(line.trim());
      if (heading) {
        const node = document.createElement(heading[1].length === 1 ? 'h2' : heading[1].length === 2 ? 'h3' : 'h4');
        appendInline(node, heading[2]);
        target.appendChild(node);
        index += 1;
        continue;
      }
      if (/^[-*]\s+/.test(line.trim())) {
        const list = document.createElement('ul');
        while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
          const item = document.createElement('li');
          appendInline(item, lines[index].trim().replace(/^[-*]\s+/, ''));
          list.appendChild(item);
          index += 1;
        }
        target.appendChild(list);
        continue;
      }
      if (/^\d+[.)]\s+/.test(line.trim())) {
        const list = document.createElement('ol');
        while (index < lines.length && /^\d+[.)]\s+/.test(lines[index].trim())) {
          const item = document.createElement('li');
          appendInline(item, lines[index].trim().replace(/^\d+[.)]\s+/, ''));
          list.appendChild(item);
          index += 1;
        }
        target.appendChild(list);
        continue;
      }
      if (/^>\s?/.test(line.trim())) {
        const quote = document.createElement('blockquote');
        appendInline(quote, line.trim().replace(/^>\s?/, ''));
        target.appendChild(quote);
        index += 1;
        continue;
      }
      const paragraphLines = [];
      while (index < lines.length && lines[index].trim() && !/^```/.test(lines[index].trim()) && !/^(#{1,3})\s+/.test(lines[index].trim()) && !/^[-*]\s+/.test(lines[index].trim()) && !/^\d+[.)]\s+/.test(lines[index].trim()) && !/^>\s?/.test(lines[index].trim())) {
        paragraphLines.push(lines[index].trim());
        index += 1;
      }
      paragraph(paragraphLines);
    }
  }

  const copyText = async (text, button) => {
    try {
      await navigator.clipboard.writeText(text);
      if (button) {
        const old = button.textContent;
        button.textContent = 'Copiado';
        window.setTimeout(() => { button.textContent = old; }, 1400);
      }
    } catch (_) {
      if (typeof toast === 'function') toast('Não foi possível copiar a resposta.');
    }
  };

  const appendTurn = (role, text, {error = false, index = null} = {}) => {
    conversation.querySelector('.voice-visible-empty')?.remove();
    const item = document.createElement('article');
    item.className = 'voice-visible-turn';
    item.dataset.role = role;
    if (error) item.dataset.error = '1';
    const author = document.createElement('strong');
    author.textContent = role === 'assistant' ? 'DevPilot' : 'Você';
    const body = document.createElement('div');
    body.className = 'voice-message-body';
    if (role === 'assistant' && !error) renderRichText(body, text);
    else body.textContent = cleanText(text);
    item.append(author, body);

    if (role === 'assistant' && !error) {
      const actions = document.createElement('div');
      actions.className = 'voice-message-actions';
      const copy = document.createElement('button');
      copy.type = 'button';
      copy.className = 'voice-message-action';
      copy.textContent = 'Copiar';
      copy.addEventListener('click', () => void copyText(cleanText(text), copy));
      actions.appendChild(copy);
      if (Number.isInteger(index)) {
        const regenerate = document.createElement('button');
        regenerate.type = 'button';
        regenerate.className = 'voice-message-action';
        regenerate.textContent = 'Regenerar';
        regenerate.addEventListener('click', () => void regenerateAnswer(index));
        actions.appendChild(regenerate);
      }
      item.appendChild(actions);
    }
    conversation.appendChild(item);
    scrollConversation();
    return item;
  };

  const renderConversation = () => {
    conversation.replaceChildren();
    if (!history.length) {
      const empty = document.createElement('div');
      empty.className = 'voice-visible-empty';
      empty.textContent = 'Converse com o DevPilot por texto ou voz. O histórico desta sessão é preservado ao fechar e reabrir.';
      conversation.appendChild(empty);
      return;
    }
    history.forEach((turn, index) => appendTurn(turn.role, turn.text, {index}));
    scrollConversation();
  };

  const showThinking = () => {
    conversation.querySelector('.voice-visible-empty')?.remove();
    conversation.querySelector('.voice-visible-thinking')?.remove();
    const thinking = document.createElement('div');
    thinking.className = 'voice-visible-thinking';
    thinking.setAttribute('aria-label', 'DevPilot está pensando');
    thinking.innerHTML = '<i></i><i></i><i></i>';
    const stop = document.createElement('button');
    stop.type = 'button';
    stop.className = 'voice-chat-stop';
    stop.textContent = 'Parar';
    stop.addEventListener('click', () => activeController?.abort());
    thinking.appendChild(stop);
    conversation.appendChild(thinking);
    scrollConversation();
    return thinking;
  };

  const modeSummary = () => {
    const mode = activeChatMode();
    const config = CHAT_MODES[mode];
    profileCopy.replaceChildren();
    const strong = document.createElement('strong');
    strong.textContent = config.profile;
    profileCopy.append(strong, document.createTextNode(` · ${config.description}`));
    modeSwitch.querySelectorAll('[data-chat-mode]').forEach((button) => {
      const active = button.dataset.chatMode === mode;
      button.dataset.active = active ? '1' : '0';
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    panel.dataset.chatMode = mode;
    return config;
  };

  const switchSession = (message = '') => {
    requestSequence += 1;
    activeController?.abort();
    activeController = null;
    requestInFlight = false;
    loadHistory();
    renderConversation();
    const config = modeSummary();
    statusNode.textContent = message || `${config.profile} pronto${activeProjectId() ? ` · ${projectLabel(activeProjectId()) || 'projeto selecionado'}` : ' · conversa geral'}.`;
  };

  const setChatMode = (nextMode) => {
    const next = normalizeMode(nextMode);
    const previous = activeChatMode();
    localStorage.setItem(CHAT_MODE_STORAGE_KEY, next);
    modeSummary();
    if (previous !== next) switchSession(`${CHAT_MODES[next].label} ativo. ${CHAT_MODES[next].description}`);
    return next;
  };

  modeSwitch.querySelectorAll('[data-chat-mode]').forEach((button) => button.addEventListener('click', () => setChatMode(button.dataset.chatMode)));
  if (!localStorage.getItem(CHAT_MODE_STORAGE_KEY)) localStorage.setItem(CHAT_MODE_STORAGE_KEY, 'planning');

  if (projectSelect) {
    projectSelect.addEventListener('change', () => {
      const previous = normalizeProjectId(localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY));
      const next = storeActiveProject(projectSelect.value);
      if (previous !== next) switchSession(next ? `Projeto ativo: ${projectLabel(next) || next}.` : 'Conversa geral ativa.');
    });
    projectSelect.addEventListener('focus', restoreActiveProject);
    restoreActiveProject();
  }

  window.devpilotChatProjectContext = {
    getProjectId: () => activeProjectId() || null,
    setProjectId: (projectId) => {
      if (!projectSelect) return false;
      const value = normalizeProjectId(projectId);
      if (!projectOptionExists(value)) return false;
      const previous = activeProjectId();
      projectSelect.value = value;
      storeActiveProject(value);
      if (previous !== value) switchSession(`Projeto ativo: ${projectLabel(value) || value}.`);
      return true;
    },
  };
  window.devpilotChatMode = {
    getMode: () => activeChatMode(),
    getProfile: () => CHAT_MODES[activeChatMode()].profile,
    setMode: (mode) => setChatMode(mode),
  };

  const resize = () => {
    transcript.style.height = 'auto';
    transcript.style.height = `${Math.min(Math.max(transcript.scrollHeight, 28), 140)}px`;
    transcript.style.overflow = transcript.scrollHeight > 140 ? 'auto' : 'hidden';
    panel.classList.toggle('voice-has-text', Boolean(cleanText(transcript.value)));
  };
  transcript.addEventListener('input', resize);
  transcript.addEventListener('focus', resize);
  resize();

  const speechText = (text) => cleanText(text)
    .replace(/```[\s\S]*?```/g, ' Trecho de código omitido na leitura. ')
    .replace(/^#{1,3}\s+/gm, '')
    .replace(/^[-*]\s+/gm, '')
    .replace(/^\d+[.)]\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\(https?:\/\/[^)]+\)/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
  const speakReply = (text) => {
    if (!('speechSynthesis' in window) || !window.SpeechSynthesisUtterance) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(speechText(text));
      utterance.lang = 'pt-BR';
      const voiceMode = outputModeSelect?.value || 'human';
      if (voiceMode === 'male') { utterance.pitch = 0.82; utterance.rate = 0.96; }
      else if (voiceMode === 'female') { utterance.pitch = 1.12; utterance.rate = 1; }
      else if (voiceMode === 'machine') { utterance.pitch = 0.62; utterance.rate = 0.86; }
      else { utterance.pitch = 1; utterance.rate = 0.98; }
      window.speechSynthesis.speak(utterance);
    } catch (_) {
      // A resposta visual nunca depende da síntese de voz.
    }
  };

  async function sendConversation(text, {appendUser = true, baseHistory = null} = {}) {
    const message = cleanText(text);
    if (!message || requestInFlight) return;
    if (typeof api !== 'function') {
      appendTurn('assistant', 'API de conversa indisponível.', {error: true});
      return;
    }

    const mode = activeChatMode();
    const modeConfig = CHAT_MODES[mode];
    const projectId = activeProjectId();
    if (mode === 'build' && !projectId) {
      const warning = 'Selecione um projeto antes de usar Construir.';
      appendTurn('assistant', warning, {error: true});
      statusNode.textContent = warning;
      return;
    }

    const priorHistory = Array.isArray(baseHistory) ? baseHistory : history.slice();
    if (appendUser) {
      history.push({role: 'user', text: message});
      saveHistory();
      renderConversation();
    }

    requestInFlight = true;
    const sequence = ++requestSequence;
    activeController = new AbortController();
    const thinking = showThinking();
    const responseStyle = panel.classList.contains('voice-session-active') ? 'voice' : 'chat';
    statusNode.textContent = `${modeConfig.profile} está pensando…`;

    const requestHistory = priorHistory.slice(-MAX_REQUEST_TURNS).map((turn) => ({
      role: turn.role,
      text: cleanText(turn.text).slice(0, MAX_HISTORY_TEXT),
    }));

    try {
      const data = await api('/chat', {
        method: 'POST',
        signal: activeController.signal,
        body: JSON.stringify({
          transcript: message,
          project_id: projectId || null,
          history: requestHistory,
          mode,
          response_style: responseStyle,
        }),
      });
      if (sequence !== requestSequence) return;
      const reply = cleanText(data?.reply);
      if (!reply) throw new Error('O DevPilot não retornou uma resposta.');

      history.push({role: 'assistant', text: reply});
      saveHistory();
      renderConversation();

      const taskId = data?.execution?.task_id;
      const modelInfo = [data?.provider, data?.model].filter(Boolean).join(' · ');
      if (mode === 'build' && taskId) {
        statusNode.textContent = `Construção preparada · tarefa ${taskId} aguardando aprovação${modelInfo ? ` · ${modelInfo}` : ''}.`;
        window.dispatchEvent(new CustomEvent('devpilot:build-task-staged', {detail: {task_id: taskId, project_id: projectId, status: data?.execution?.status}}));
      } else if (data?.fallback_used) {
        statusNode.textContent = `${data?.profile || modeConfig.profile} respondeu usando fallback${modelInfo ? ` · ${modelInfo}` : ''}.`;
      } else {
        statusNode.textContent = `${data?.profile || modeConfig.profile} respondeu${modelInfo ? ` · ${modelInfo}` : ''}.`;
      }
      if (responseStyle === 'voice') speakReply(reply);
    } catch (error) {
      if (sequence !== requestSequence) return;
      thinking.remove();
      if (error?.name === 'AbortError') {
        statusNode.textContent = 'Resposta interrompida. A sua mensagem foi preservada.';
        return;
      }
      const errorMessage = error?.message || 'Não foi possível conversar com o DevPilot.';
      appendTurn('assistant', errorMessage, {error: true});
      statusNode.textContent = errorMessage;
      if (typeof toast === 'function') toast(errorMessage);
    } finally {
      if (sequence === requestSequence) {
        requestInFlight = false;
        activeController = null;
        conversation.querySelector('.voice-visible-thinking')?.remove();
      }
      scrollConversation();
    }
  }

  async function submitVisibleConversation() {
    const raw = cleanText(pendingRawInput || transcript.value);
    pendingRawInput = '';
    if (!raw || requestInFlight) return;
    await sendConversation(raw);
  }

  async function regenerateAnswer(assistantIndex) {
    if (requestInFlight || !Number.isInteger(assistantIndex)) return;
    const userIndex = assistantIndex - 1;
    if (userIndex < 0 || history[userIndex]?.role !== 'user') return;
    const message = history[userIndex].text;
    const baseHistory = history.slice(0, userIndex);
    history = history.slice(0, userIndex + 1);
    saveHistory();
    renderConversation();
    await sendConversation(message, {appendUser: false, baseHistory});
  }

  newChatButton.addEventListener('click', () => {
    if (requestInFlight) activeController?.abort();
    history = [];
    try { sessionStorage.removeItem(sessionKey()); } catch (_) { /* best effort */ }
    renderConversation();
    statusNode.textContent = `${CHAT_MODES[activeChatMode()].profile} pronto para uma nova conversa.`;
    transcript.focus({preventScroll: true});
  });

  // O módulo de captura de voz lê o textarea sincronicamente. Em envio por texto,
  // guardamos o valor cru antes que o módulo de voz o normalize, preservando
  // quebras de linha, prompts e código colado pelo usuário.
  sendButton.addEventListener('click', () => {
    if (!requestInFlight) pendingRawInput = transcript.value;
  }, true);

  window.devpilotVoiceConversationSubmit = submitVisibleConversation;

  modal.addEventListener('close', () => {
    transcript.style.height = 'auto';
    panel.classList.remove('voice-has-text');
    pendingRawInput = '';
    try { window.speechSynthesis?.cancel?.(); } catch (_) { /* best effort */ }
    saveHistory();
  });

  document.addEventListener('devpilot:active-project-changed', () => {
    if (!modal.open) return;
    switchSession();
  });

  modeSummary();
  loadHistory();
  renderConversation();
  statusNode.textContent = `${CHAT_MODES[activeChatMode()].profile} pronto.`;
})();
