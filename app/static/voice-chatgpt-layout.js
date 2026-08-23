(() => {
  const modal = document.querySelector('#voice-modal');
  const panel = modal?.querySelector('.voice-modal-enhanced');
  const transcript = panel?.querySelector('#voice-transcript');
  const sendButton = panel?.querySelector('#voice-chat-send');

  if (!modal || !panel || !transcript || !sendButton) return;
  if (panel.dataset.voiceChatgptLayout === '2') return;
  panel.dataset.voiceChatgptLayout = '2';

  const resize = () => {
    transcript.style.height = 'auto';
    transcript.style.height = `${Math.min(Math.max(transcript.scrollHeight, 28), 112)}px`;
    transcript.style.overflow = 'hidden';
  };

  transcript.addEventListener('input', resize);
  transcript.addEventListener('focus', resize);
  resize();

  modal.addEventListener('close', () => {
    transcript.style.height = 'auto';
  });
})();
