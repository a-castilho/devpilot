(() => {
  const modal = document.querySelector('#voice-modal');
  const panel = modal?.querySelector('.voice-modal');
  const project = modal?.querySelector('#voice-project');
  const transcript = modal?.querySelector('#voice-transcript');
  const statusNode = modal?.querySelector('#voice-status');
  const startButton = modal?.querySelector('#voice-start');
  const sendButton = modal?.querySelector('#voice-send');
  const modeSelect = modal?.querySelector('#voice-output-mode');
  const playbackButton = modal?.querySelector('#voice-playback');
  const playbackHint = modal?.querySelector('#voice-playback-hint');
  const playbackSection = modal?.querySelector('.voice-playback-controls');
  const actions = modal?.querySelector('.hero-actions');

  if (!modal || !panel || !project || !transcript || !statusNode || !startButton || !sendButton || !actions) return;
  if (panel.dataset.voiceEnhancedUi === '1') return;
  panel.dataset.voiceEnhancedUi = '1';

  if (!document.querySelector('link[data-voice-enhanced-ui]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/assets/voice-enhanced-ui.css?v=20260821-1';
    link.dataset.voiceEnhancedUi = '1';
    document.head.appendChild(link);
  }

  panel.classList.add('voice-modal-enhanced');
  statusNode.setAttribute('aria-live', 'polite');
  transcript.setAttribute('aria-label', 'Transcrição do comando');
  project.setAttribute('aria-label', 'Projeto do comando de voz');
  startButton.setAttribute('title', 'Iniciar ou parar gravação');
  sendButton.textContent = 'Revisar comando →';

  const eyebrow = panel.querySelector(':scope > .eyebrow');
  const title = panel.querySelector(':scope > h2');
  if (eyebrow && title) {
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

  const composer = document.createElement('div');
  composer.className = 'voice-composer';
  composer.setAttribute('aria-label', 'Controles do assistente de voz');

  const uploadButton = document.createElement('button');
  uploadButton.type = 'button';
  uploadButton.id = 'voice-upload';
  uploadButton.className = 'voice-composer-button voice-upload-button';
  uploadButton.textContent = '+ Áudio';
  uploadButton.title = 'Gravar pelo dispositivo ou selecionar um arquivo de áudio';

  const uploadInput = document.createElement('input');
  uploadInput.type = 'file';
  uploadInput.id = 'voice-upload-input';
  uploadInput.accept = 'audio/*,.webm,.ogg,.m4a,.mp4,.mp3,.wav,.aac,.3gp,.3g2';
  uploadInput.setAttribute('capture', 'microphone');
  uploadInput.hidden = true;
  uploadInput.tabIndex = -1;

  const outputControl = document.createElement('label');
  outputControl.className = 'voice-output-control';
  outputControl.innerHTML = '<span>Voz</span>';
  if (modeSelect) outputControl.appendChild(modeSelect);

  composer.append(uploadButton, outputControl);
  if (playbackButton) {
    playbackButton.classList.add('voice-composer-button');
    composer.appendChild(playbackButton);
  }
  startButton.classList.add('voice-composer-button', 'voice-record-button');
  composer.appendChild(startButton);

  actions.parentNode.insertBefore(composer, actions);
  composer.after(uploadInput);

  if (playbackHint) {
    playbackHint.classList.add('voice-enhanced-hint');
    composer.after(playbackHint);
  }
  playbackSection?.remove();

  if (!actions.querySelector('#voice-clear')) {
    const clearButton = document.createElement('button');
    clearButton.type = 'button';
    clearButton.id = 'voice-clear';
    clearButton.className = 'ghost voice-clear-button';
    clearButton.textContent = 'Limpar';
    actions.insertBefore(clearButton, sendButton);

    clearButton.addEventListener('click', () => {
      try {
        window.speechSynthesis?.cancel?.();
      } catch (_) {
        // Best effort only.
      }
      transcript.value = '';
      statusNode.textContent = 'Pronto para um novo comando.';
      transcript.focus();
    });
  }

  actions.classList.add('voice-enhanced-actions');

  const savedMode = localStorage.getItem('devpilot-voice-output-mode');
  if (modeSelect && savedMode && [...modeSelect.options].some((option) => option.value === savedMode)) {
    modeSelect.value = savedMode;
    modeSelect.dispatchEvent(new Event('change'));
  }
  modeSelect?.addEventListener('change', () => {
    localStorage.setItem('devpilot-voice-output-mode', modeSelect.value);
  });

  function normalizedAudioType(file) {
    const aliases = {
      'audio/x-m4a': 'audio/mp4',
      'audio/m4a': 'audio/mp4',
      'audio/x-wav': 'audio/wav',
      'video/3gpp': 'audio/3gpp',
      'video/3gpp2': 'audio/3gpp2',
      'application/octet-stream': '',
    };
    const byExtension = {
      webm: 'audio/webm', ogg: 'audio/ogg', oga: 'audio/ogg', m4a: 'audio/mp4',
      mp4: 'audio/mp4', mp3: 'audio/mpeg', wav: 'audio/wav', aac: 'audio/aac',
      '3gp': 'audio/3gpp', '3g2': 'audio/3gpp2',
    };
    const raw = String(file?.type || '').split(';', 1)[0].toLowerCase();
    const normalized = Object.prototype.hasOwnProperty.call(aliases, raw) ? aliases[raw] : raw;
    if (normalized.startsWith('audio/')) return normalized;
    const extension = String(file?.name || '').split('.').pop()?.toLowerCase();
    return byExtension[extension] || 'audio/webm';
  }

  async function transcribeFile(file) {
    if (!file?.size) return;
    uploadButton.disabled = true;
    startButton.disabled = true;
    statusNode.textContent = 'Transcrevendo áudio…';

    const mime = normalizedAudioType(file);
    const sourceType = String(file.type || '').split(';', 1)[0].toLowerCase();
    const blob = sourceType === mime ? file : new Blob([file], { type: mime });
    const form = new FormData();
    form.append('audio', blob, file.name || 'voice.webm');

    try {
      if (typeof api !== 'function') throw new Error('API de transcrição indisponível.');
      const data = await api('/voice/transcriptions', { method: 'POST', body: form });
      transcript.value = String(data?.text || '').trim();
      statusNode.textContent = transcript.value
        ? 'Transcrição pronta. Revise, ouça e envie quando estiver correta.'
        : 'Nenhuma fala foi reconhecida neste áudio.';
      transcript.focus();
    } catch (error) {
      statusNode.textContent = error?.message || 'Falha ao transcrever o áudio.';
      if (typeof toast === 'function') toast(statusNode.textContent);
    } finally {
      uploadButton.disabled = false;
      startButton.disabled = false;
      uploadInput.value = '';
    }
  }

  uploadButton.addEventListener('click', () => {
    uploadInput.value = '';
    uploadInput.click();
  });
  uploadInput.addEventListener('change', () => transcribeFile(uploadInput.files?.[0]));

  transcript.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      sendButton.click();
    }
  });

  modal.addEventListener('close', () => {
    uploadInput.value = '';
  });
})();
