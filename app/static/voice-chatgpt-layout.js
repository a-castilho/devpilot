(() => {
  const modal = document.querySelector('#voice-modal');
  const panel = modal?.querySelector('.voice-modal-enhanced');
  const transcript = panel?.querySelector('#voice-transcript');
  const sendButton = panel?.querySelector('#voice-chat-send');
  const stage = panel?.querySelector('.voice-chatgpt-stage');

  if (!modal || !panel || !transcript || !sendButton || !stage) return;
  if (panel.dataset.voiceChatgptLayout === '3') return;
  panel.dataset.voiceChatgptLayout = '3';
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

  const resize = () => {
    transcript.style.height = 'auto';
    transcript.style.height = `${Math.min(Math.max(transcript.scrollHeight, 28), 112)}px`;
    transcript.style.overflow = 'hidden';
    panel.classList.toggle('voice-has-text', Boolean(transcript.value.trim()));
  };

  transcript.addEventListener('input', resize);
  transcript.addEventListener('focus', resize);
  resize();

  modal.addEventListener('close', () => {
    transcript.style.height = 'auto';
    panel.classList.remove('voice-has-text');
  });
})();
