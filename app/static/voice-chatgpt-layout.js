(() => {
  const modal = document.querySelector('#voice-modal');
  const panel = modal?.querySelector('.voice-modal-enhanced');
  const composer = panel?.querySelector('.voice-composer');
  const project = panel?.querySelector('#voice-project');
  const transcript = panel?.querySelector('#voice-transcript');
  const modeSelect = panel?.querySelector('#voice-output-mode');
  const playbackButton = panel?.querySelector('#voice-playback');
  const startButton = panel?.querySelector('#voice-start');
  const actions = panel?.querySelector('.voice-enhanced-actions');
  const clearButton = panel?.querySelector('#voice-clear');

  if (!modal || !panel || !composer || !project || !transcript || !startButton) return;
  if (panel.dataset.voiceChatgptLayout === '1') return;
  panel.dataset.voiceChatgptLayout = '1';

  transcript.rows = 1;
  transcript.placeholder = 'Fale ou digite com o DevPilot';
  transcript.setAttribute('autocomplete', 'off');
  transcript.setAttribute('enterkeyhint', 'send');

  const projectControl = project.closest('.voice-project-control');
  const transcriptControl = transcript.closest('.voice-transcript-control');
  const outputControl = modeSelect?.closest('.voice-output-control');

  const optionsButton = document.createElement('button');
  optionsButton.type = 'button';
  optionsButton.className = 'voice-chatgpt-options-button';
  optionsButton.setAttribute('aria-label', 'Opções da conversa');
  optionsButton.setAttribute('title', 'Opções da conversa');
  optionsButton.setAttribute('aria-expanded', 'false');
  optionsButton.textContent = '+';

  const options = document.createElement('div');
  options.className = 'voice-chatgpt-options';
  options.hidden = true;
  options.setAttribute('aria-label', 'Opções da conversa de voz');

  if (projectControl) options.appendChild(projectControl);
  if (outputControl) options.appendChild(outputControl);
  if (clearButton) options.appendChild(clearButton);

  panel.insertBefore(options, composer);
  composer.prepend(optionsButton);

  if (transcriptControl) {
    const anchor = playbackButton || startButton;
    composer.insertBefore(transcriptControl, anchor);
  }

  playbackButton?.setAttribute('aria-label', 'Ouvir resposta');
  startButton.setAttribute('aria-label', 'Falar com o DevPilot');

  if (actions && !actions.children.length) actions.remove();

  const closeOptions = () => {
    options.hidden = true;
    optionsButton.setAttribute('aria-expanded', 'false');
  };

  optionsButton.addEventListener('click', (event) => {
    event.stopPropagation();
    const willOpen = options.hidden;
    options.hidden = !willOpen;
    optionsButton.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
  });

  options.addEventListener('click', (event) => event.stopPropagation());
  document.addEventListener('click', closeOptions);
  modal.addEventListener('close', closeOptions);

  const resizeTranscript = () => {
    transcript.style.height = 'auto';
    transcript.style.height = `${Math.min(transcript.scrollHeight, 116)}px`;
  };

  transcript.addEventListener('input', resizeTranscript);
  transcript.addEventListener('focus', resizeTranscript);
  resizeTranscript();

  transcript.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    const value = transcript.value.trim();
    if (!value) {
      startButton.click();
      return;
    }
    window.devpilotVoiceConversationSubmit?.();
  });

  const transcriptObserver = new MutationObserver(resizeTranscript);
  transcriptObserver.observe(transcript, {attributes: true, attributeFilter: ['value']});
})();
