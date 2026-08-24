(() => {
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
  const CHAT_MODES = {
    planning: {
      label: 'Planejamento',
      profile: 'DevPilot Planejador',
      description: 'Somente análise e plano. Nenhuma execução é criada.',
    },
    build: {
      label: 'Construir',
      profile: 'DevPilot Construtor',
      description: 'Prepara uma tarefa real, auditada e aguardando aprovação.',
    },
  };

  if (!modal || !panel || !transcript || !sendButton || !stage || !statusNode) return;
  if (panel.dataset.voiceChatgptLayout === '6') return;
  panel.dataset.voiceChatgptLayout = '6';
  panel.classList.add('voice-ui-polished');

  if (!document.querySelector('link[data-voice-ui-polish]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/assets/voice-ui-polish.css?v=20260823-1';
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

  const conversation = document.createElement('section');
  conversation.id = 'voice-visible-conversation';
  conversation.className = 'voice-visible-conversation';
  conversation.setAttribute('aria-live', 'polite');
  conversation.setAttribute('aria-label', 'Conversa com o DevPilot');
  conversation.innerHTML = '<div class="voice-visible-empty">Converse com o DevPilot por texto ou voz.</div>';

  const statusWrapper = stage.querySelector('.voice-chatgpt-status');
  if (statusWrapper) {
    stage.insertBefore(modeSwitch, statusWrapper);
    stage.insertBefore(profileBanner, statusWrapper);
    stage.insertBefore(conversation, statusWrapper);
  } else {
    stage.append(modeSwitch, profileBanner, conversation);
  }

  if (!document.querySelector('style[data-voice-visible-conversation]')) {
    const style = document.createElement('style');
    style.dataset.voiceVisibleConversation = '1';
    style.textContent = `
      #voice-chat-preview{display:none!important}
      .voice-chat-mode-switch{width:min(100%,720px);display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:2px auto 4px;padding:4px;border:1px solid rgba(148,163,184,.18);border-radius:16px;background:rgba(15,23,42,.54)}
      .voice-chat-mode-button{min-width:0;border:1px solid transparent;border-radius:12px;background:transparent;color:#aab8c2;padding:9px 12px;display:grid;gap:2px;text-align:left;cursor:pointer;transition:background .16s ease,border-color .16s ease,color .16s ease,transform .16s ease}
      .voice-chat-mode-button:hover{transform:translateY(-1px);color:#edf7f7;background:rgba(148,163,184,.08)}
      .voice-chat-mode-button span{font-weight:750;font-size:.88rem;line-height:1.1}
      .voice-chat-mode-button small{font-size:.68rem;opacity:.72;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .voice-chat-mode-button[data-active="1"][data-chat-mode="planning"]{color:#e8f5ff;border-color:rgba(96,165,250,.5);background:rgba(59,130,246,.18)}
      .voice-chat-mode-button[data-active="1"][data-chat-mode="build"]{color:#ebfff7;border-color:rgba(52,211,153,.5);background:rgba(16,185,129,.18)}
      .voice-chat-profile-banner{width:min(100%,720px);margin:0 auto 2px;padding:7px 11px;border-radius:10px;color:#a7b5bd;background:rgba(15,23,42,.38);font-size:.74rem;line-height:1.35}
      .voice-chat-profile-banner strong{color:#e7f7f5}
      .voice-visible-conversation{width:min(100%,720px);display:flex;flex-direction:column;gap:10px;max-height:min(44vh,420px);overflow:auto;padding:8px 4px 10px;scrollbar-width:thin;overscroll-behavior:contain}
      .voice-visible-empty{align-self:center;color:#91a0aa;font-size:.9rem;padding:10px 14px;text-align:center}
      .voice-visible-turn{max-width:88%;display:grid;gap:4px;padding:10px 13px;border-radius:16px;line-height:1.42;word-break:break-word;white-space:pre-wrap}
      .voice-visible-turn strong{font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;opacity:.68}
      .voice-visible-turn p{margin:0;color:inherit;font:inherit}
      .voice-visible-turn[data-role="user"]{align-self:flex-end;background:rgba(79,91,101,.34);color:#eef4f7;border-bottom-right-radius:5px}
      .voice-visible-turn[data-role="assistant"]{align-self:flex-start;background:rgba(0,197,176,.11);border:1px solid rgba(37,238,211,.18);color:#e7fffb;border-bottom-left-radius:5px}
      .voice-visible-turn[data-error="1"]{background:rgba(160,65,65,.16);border-color:rgba(255,124,124,.22);color:#ffdede}
      .voice-visible-thinking{align-self:flex-start;display:flex;gap:5px;padding:11px 14px;border-radius:16px;background:rgba(0,197,176,.08)}
      .voice-visible-thinking i{width:6px;height:6px;border-radius:50%;background:currentColor;opacity:.45;animation:voiceThinking 1s infinite ease-in-out}
      .voice-visible-thinking i:nth-child(2){animation-delay:.14s}.voice-visible-thinking i:nth-child(3){animation-delay:.28s}
      @keyframes voiceThinking{0%,70%,100%{transform:translateY(0);opacity:.35}35%{transform:translateY(-4px);opacity:1}}
      @media(max-width:640px){.voice-chat-mode-switch{gap:5px}.voice-chat-mode-button{padding:8px}.voice-chat-mode-button small{font-size:.62rem}.voice-visible-conversation{max-height:36vh;padding-inline:2px}.voice-visible-turn{max-width:92%;font-size:.94rem}}
    `;
    document.head.appendChild(style);
  }

  const resize = () => {
    transcript.style.height = 'auto';
    transcript.style.height = `${Math.min(Math.max(transcript.scrollHeight, 28), 112)}px`;
    transcript.style.overflow = 'hidden';
    panel.classList.toggle('voice-has-text', Boolean(transcript.value.trim()));
  };

  transcript.addEventListener('input', resize);
  transcript.addEventListener('focus', resize);
  resize();

  let history = [];
  let requestInFlight = false;
  let requestSequence = 0;

  const normalize = (value) => String(value || '').trim().replace(/\s+/g, ' ');
  const normalizeProjectId = (value) => String(value ?? '').trim();
  const normalizeMode = (value) => Object.prototype.hasOwnProperty.call(CHAT_MODES, value) ? value : 'planning';

  const activeChatMode = () => normalizeMode(localStorage.getItem(CHAT_MODE_STORAGE_KEY) || 'planning');

  const scrollConversation = () => {
    conversation.scrollTop = conversation.scrollHeight;
  };

  const appendTurn = (role, text, error = false) => {
    conversation.querySelector('.voice-visible-empty')?.remove();
    const item = document.createElement('article');
    item.className = 'voice-visible-turn';
    item.dataset.role = role;
    if (error) item.dataset.error = '1';

    const author = document.createElement('strong');
    author.textContent = role === 'assistant' ? 'DevPilot' : 'Você';
    const body = document.createElement('p');
    body.textContent = String(text || '').trim();
    item.append(author, body);
    conversation.appendChild(item);
    scrollConversation();
    return item;
  };

  const showThinking = () => {
    conversation.querySelector('.voice-visible-empty')?.remove();
    conversation.querySelector('.voice-visible-thinking')?.remove();
    const thinking = document.createElement('div');
    thinking.className = 'voice-visible-thinking';
    thinking.setAttribute('aria-label', 'DevPilot está pensando');
    thinking.innerHTML = '<i></i><i></i><i></i>';
    conversation.appendChild(thinking);
    scrollConversation();
    return thinking;
  };

  const projectOptionExists = (projectId) => {
    if (!projectSelect) return false;
    const expected = normalizeProjectId(projectId);
    return [...projectSelect.options].some((option) => normalizeProjectId(option.value) === expected);
  };

  const projectLabel = (projectId) => {
    if (!projectSelect) return '';
    const expected = normalizeProjectId(projectId);
    return [...projectSelect.options].find(
      (option) => normalizeProjectId(option.value) === expected,
    )?.textContent?.trim() || '';
  };

  const storeActiveProject = (projectId) => {
    const value = normalizeProjectId(projectId);
    localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, value);
    window.dispatchEvent(new CustomEvent('devpilot:active-project-changed', {
      detail: {project_id: value || null},
    }));
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

  const modeSummary = () => {
    const mode = activeChatMode();
    const config = CHAT_MODES[mode];
    profileBanner.innerHTML = `<strong>${config.profile}</strong> · ${config.description}`;
    modeSwitch.querySelectorAll('[data-chat-mode]').forEach((button) => {
      const active = button.dataset.chatMode === mode;
      button.dataset.active = active ? '1' : '0';
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    panel.dataset.chatMode = mode;
    return config;
  };

  const resetConversation = (message) => {
    requestSequence += 1;
    requestInFlight = false;
    history = [];
    conversation.querySelector('.voice-visible-thinking')?.remove();
    conversation.innerHTML = '<div class="voice-visible-empty">Converse com o DevPilot por texto ou voz.</div>';
    try {
      window.speechSynthesis?.cancel?.();
    } catch (_) {
      // Best effort only.
    }
    statusNode.textContent = message;
  };

  const resetConversationForProject = (projectId) => {
    const label = projectLabel(projectId);
    const config = modeSummary();
    resetConversation(projectId
      ? `Projeto ativo: ${label || projectId}. ${config.profile} está selecionado.`
      : `Conversa geral ativa. ${config.profile} está selecionado.`);
  };

  const setChatMode = (nextMode) => {
    const next = normalizeMode(nextMode);
    const previous = activeChatMode();
    localStorage.setItem(CHAT_MODE_STORAGE_KEY, next);
    const config = modeSummary();
    if (previous !== next) {
      resetConversation(`${config.label} ativo. ${config.description}`);
      window.dispatchEvent(new CustomEvent('devpilot:chat-mode-changed', {
        detail: {mode: next, profile: config.profile},
      }));
    }
    return next;
  };

  modeSwitch.querySelectorAll('[data-chat-mode]').forEach((button) => {
    button.addEventListener('click', () => setChatMode(button.dataset.chatMode));
  });

  if (!localStorage.getItem(CHAT_MODE_STORAGE_KEY)) {
    localStorage.setItem(CHAT_MODE_STORAGE_KEY, 'planning');
  }
  modeSummary();

  if (projectSelect) {
    projectSelect.addEventListener('change', () => {
      const previous = localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
      const next = storeActiveProject(projectSelect.value);
      if (normalizeProjectId(previous) !== next) resetConversationForProject(next);
    });

    new MutationObserver(() => {
      restoreActiveProject();
    }).observe(projectSelect, {childList: true, subtree: true});

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
      if (previous !== value) resetConversationForProject(value);
      return true;
    },
  };

  window.devpilotChatMode = {
    getMode: () => activeChatMode(),
    getProfile: () => CHAT_MODES[activeChatMode()].profile,
    setMode: (mode) => setChatMode(mode),
  };

  const speakReply = (text) => {
    if (!('speechSynthesis' in window) || !window.SpeechSynthesisUtterance) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = 'pt-BR';
      const voiceMode = outputModeSelect?.value || 'human';
      if (voiceMode === 'male') {
        utterance.pitch = 0.82;
        utterance.rate = 0.96;
      } else if (voiceMode === 'female') {
        utterance.pitch = 1.12;
        utterance.rate = 1;
      } else if (voiceMode === 'machine') {
        utterance.pitch = 0.62;
        utterance.rate = 0.86;
      } else {
        utterance.pitch = 1;
        utterance.rate = 0.98;
      }
      window.speechSynthesis.speak(utterance);
    } catch (_) {
      // A resposta visual nunca depende da síntese de voz.
    }
  };

  async function submitVisibleConversation() {
    const text = normalize(transcript.value);
    if (!text || requestInFlight) return;
    if (typeof api !== 'function') {
      const message = 'API de conversa indisponível.';
      appendTurn('assistant', message, true);
      statusNode.textContent = message;
      return;
    }

    requestInFlight = true;
    const sequence = ++requestSequence;
    const mode = activeChatMode();
    const modeConfig = CHAT_MODES[mode];
    const projectId = activeProjectId();

    if (mode === 'build' && !projectId) {
      requestInFlight = false;
      const message = 'Selecione um projeto antes de usar Construir.';
      appendTurn('assistant', message, true);
      statusNode.textContent = message;
      return;
    }

    appendTurn('user', text);
    const thinking = showThinking();
    statusNode.textContent = `${modeConfig.profile} está pensando…`;

    const requestHistory = history.slice(-12);

    try {
      const data = await api('/chat', {
        method: 'POST',
        body: JSON.stringify({
          transcript: text,
          project_id: projectId || null,
          history: requestHistory,
          mode,
        }),
      });
      if (sequence !== requestSequence) return;

      const reply = normalize(data?.reply);
      if (!reply) throw new Error('O DevPilot não retornou uma resposta.');

      thinking.remove();
      history.push({role: 'user', text}, {role: 'assistant', text: reply});
      history = history.slice(-12);
      appendTurn('assistant', reply);

      const taskId = data?.execution?.task_id;
      if (mode === 'build' && taskId) {
        statusNode.textContent = `Construção preparada. Tarefa ${taskId} aguardando aprovação.`;
        window.dispatchEvent(new CustomEvent('devpilot:build-task-staged', {
          detail: {task_id: taskId, project_id: projectId, status: data?.execution?.status},
        }));
      } else if (data?.fallback_used) {
        statusNode.textContent = `${data?.profile || modeConfig.profile} respondeu usando fallback.`;
      } else {
        statusNode.textContent = `${data?.profile || modeConfig.profile} respondeu.`;
      }
      speakReply(reply);
    } catch (error) {
      if (sequence !== requestSequence) return;
      thinking.remove();
      const message = error?.message || 'Não foi possível conversar com o DevPilot.';
      appendTurn('assistant', message, true);
      statusNode.textContent = message;
      if (typeof toast === 'function') toast(message);
    } finally {
      if (sequence === requestSequence) requestInFlight = false;
      scrollConversation();
    }
  }

  // Voz e texto compartilham a mesma sessão, projeto e modo. Cada mensagem
  // transporta explicitamente planning/build para que o backend aplique o
  // perfil correto e impeça execução quando Planejamento estiver ativo.
  window.devpilotVoiceConversationSubmit = submitVisibleConversation;

  modal.addEventListener('close', () => {
    transcript.style.height = 'auto';
    panel.classList.remove('voice-has-text');
    requestSequence += 1;
    requestInFlight = false;
    history = [];
    conversation.innerHTML = '<div class="voice-visible-empty">Converse com o DevPilot por texto ou voz.</div>';
    try {
      window.speechSynthesis?.cancel?.();
    } catch (_) {
      // Best effort only.
    }
  });

  const modalProjectObserver = new MutationObserver(() => {
    if (!modal.open) return;
    restoreActiveProject();
    modeSummary();
  });
  modalProjectObserver.observe(modal, {attributes: true, attributeFilter: ['open']});
})();
