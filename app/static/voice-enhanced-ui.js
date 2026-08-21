(() => {
  const modal = document.querySelector('#voice-modal');
  const panel = modal?.querySelector('.voice-modal');
  const project = modal?.querySelector('#voice-project');
  const transcript = modal?.querySelector('#voice-transcript');
  const statusNode = modal?.querySelector('#voice-status');
  const startButton = modal?.querySelector('#voice-start');
  const modeSelect = modal?.querySelector('#voice-output-mode');
  const playbackButton = modal?.querySelector('#voice-playback');
  const actions = modal?.querySelector('.hero-actions');

  if (!modal || !panel || !project || !transcript || !statusNode || !startButton || !actions) return;
  if (panel.dataset.voiceEnhancedUi === '4') return;
  panel.dataset.voiceEnhancedUi = '4';

  // O áudio é capturado somente pelo botão Gravar. Não existe mais botão para
  // selecionar/enviar arquivo de áudio nem botão manual para enviar a fala.
  // "Ouvir transcrição" permanece disponível para revisar o texto por voz.
  modal.querySelector('#voice-upload')?.remove();
  modal.querySelector('#voice-upload-input')?.remove();
  modal.querySelector('#voice-send')?.remove();

  if (!document.querySelector('link[data-voice-enhanced-ui]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/assets/voice-enhanced-ui.css?v=20260821-3';
    link.dataset.voiceEnhancedUi = '1';
    document.head.appendChild(link);
  }

  panel.classList.add('voice-modal-enhanced');
  statusNode.setAttribute('aria-live', 'polite');
  transcript.setAttribute('aria-label', 'Transcrição da conversa');
  project.setAttribute('aria-label', 'Projeto da conversa de voz');
  startButton.setAttribute('title', 'Iniciar ou parar gravação');
  playbackButton?.setAttribute('title', 'Ouvir o texto atual da transcrição');
  statusNode.textContent = 'Toque em Gravar e fale. O DevPilot responderá automaticamente em voz.';

  const eyebrow = panel.querySelector(':scope > .eyebrow');
  const title = panel.querySelector(':scope > h2');
  if (eyebrow && title && !panel.querySelector('.voice-enhanced-heading')) {
    const heading = document.createElement('div');
    heading.className = 'voice-enhanced-heading';
    heading.append(eyebrow, title);
    panel.insertBefore(heading, project);
  }

  if (!project.closest('.voice-project-control')) {
    const projectControl = document.createElement('label');
    projectControl.className = 'voice-project-control';
    projectControl.innerHTML = '<span>Projeto</span>';
    project.parentNode.insertBefore(projectControl, project);
    projectControl.appendChild(project);
  }

  if (!transcript.closest('.voice-transcript-control')) {
    const transcriptControl = document.createElement('label');
    transcriptControl.className = 'voice-transcript-control';
    transcriptControl.innerHTML = '<span>Transcrição</span>';
    transcript.parentNode.insertBefore(transcriptControl, transcript);
    transcriptControl.appendChild(transcript);
  }

  let composer = panel.querySelector('.voice-composer');
  if (!composer) {
    composer = document.createElement('div');
    composer.className = 'voice-composer';
    composer.setAttribute('aria-label', 'Controles do assistente de voz');
    actions.parentNode.insertBefore(composer, actions);
  } else {
    composer.innerHTML = '';
  }

  if (modeSelect) {
    const outputControl = document.createElement('label');
    outputControl.className = 'voice-output-control';
    outputControl.innerHTML = '<span>Voz do DevPilot</span>';
    outputControl.appendChild(modeSelect);
    composer.appendChild(outputControl);
  }

  if (playbackButton) {
    playbackButton.classList.add('voice-composer-button', 'voice-playback-button');
    composer.appendChild(playbackButton);
  }

  startButton.classList.add('voice-composer-button', 'voice-record-button');
  startButton.textContent = startButton.textContent.includes('Parar') ? '■ Parar' : '● Gravar';
  composer.appendChild(startButton);

  let clearButton = actions.querySelector('#voice-clear');
  if (!clearButton) {
    clearButton = document.createElement('button');
    clearButton.type = 'button';
    clearButton.id = 'voice-clear';
    clearButton.className = 'ghost voice-clear-button';
    clearButton.textContent = 'Limpar conversa';
    actions.appendChild(clearButton);
  }

  clearButton.addEventListener('click', () => {
    try {
      window.speechSynthesis?.cancel?.();
    } catch (_) {
      // Best effort only.
    }
    transcript.value = '';
    const log = modal.querySelector('#voice-chat-log');
    if (log) {
      log.innerHTML = '<div class="voice-chat-empty">Grave sua mensagem. O DevPilot responderá automaticamente em voz.</div>';
    }
    statusNode.textContent = 'Pronto. Toque em Gravar para conversar com o DevPilot.';
    transcript.focus();
  });

  actions.classList.add('voice-enhanced-actions');

  const savedMode = localStorage.getItem('devpilot-voice-output-mode');
  if (modeSelect && savedMode && [...modeSelect.options].some((option) => option.value === savedMode)) {
    modeSelect.value = savedMode;
  }
  modeSelect?.addEventListener('change', () => {
    localStorage.setItem('devpilot-voice-output-mode', modeSelect.value);
  });

  transcript.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      window.devpilotVoiceConversationSubmit?.();
    }
  });

  // Chromium/Brave can expose SpeechRecognition but fail when its remote speech
  // service is unavailable. voice-local-update.js already records and sends the
  // audio to the DevPilot transcription endpoint when its compatible mode is
  // activated. Detect the native failure and activate that mode automatically,
  // without forcing the user to press Gravar a second time.
  const autoFallbackMessages = [
    'o serviço de voz do navegador falhou',
    'o reconhecimento pt-br do navegador não está disponível',
    'o reconhecimento nativo não iniciou',
    'o reconhecimento nativo falhou',
  ];
  let autoFallbackPending = false;
  let autoFallbackTimer = null;

  const needsAutomaticFallback = () => {
    const message = String(statusNode.textContent || '').trim().toLowerCase();
    return autoFallbackMessages.some((fragment) => message.includes(fragment));
  };

  const scheduleAutomaticFallback = () => {
    if (!modal.open || autoFallbackPending || !needsAutomaticFallback()) return;
    if (/parar/i.test(startButton.textContent || '')) return;

    autoFallbackPending = true;
    statusNode.textContent = 'Serviço nativo indisponível. Ativando modo compatível automaticamente…';

    if (autoFallbackTimer) window.clearTimeout(autoFallbackTimer);
    autoFallbackTimer = window.setTimeout(() => {
      autoFallbackTimer = null;
      autoFallbackPending = false;
      if (!modal.open) return;

      if (startButton.disabled) {
        scheduleAutomaticFallback();
        return;
      }

      startButton.click();
    }, 260);
  };

  const fallbackObserver = new MutationObserver(scheduleAutomaticFallback);
  fallbackObserver.observe(statusNode, {childList: true, characterData: true, subtree: true});

  modal.addEventListener('close', () => {
    autoFallbackPending = false;
    if (autoFallbackTimer) {
      window.clearTimeout(autoFallbackTimer);
      autoFallbackTimer = null;
    }
  });
})();