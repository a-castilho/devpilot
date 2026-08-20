(() => {
  const LOCAL_UPDATE_PATTERNS = [
    /^(?:atualizar|atualize|atualiza|sincronizar|sincronize)\s+(?:o\s+)?(?:devpilot\s+)?local(?:\s+(?:no\s+)?linux)?$/i,
    /^(?:atualizar|atualize|atualiza)\s+(?:o\s+)?linux(?:\s+local)?$/i,
  ];

  const normalize = (value) => String(value || '').trim().replace(/\s+/g, ' ');
  const isLocalUpdate = (value) => LOCAL_UPDATE_PATTERNS.some((pattern) => pattern.test(normalize(value)));
  const startButton = document.querySelector('#voice-start');
  const sendButton = document.querySelector('#voice-send');
  const transcriptInput = document.querySelector('#voice-transcript');
  const statusNode = document.querySelector('#voice-status');
  const modal = document.querySelector('#voice-modal');

  if (!startButton || !sendButton || !transcriptInput || !statusNode || !modal) return;

  const originalSend = sendButton.onclick;
  let dispatching = false;
  let recognition = null;

  async function dispatchLocalUpdate(transcript, automatic = false) {
    if (dispatching) return;
    if (typeof isSuperAdmin === 'function' && !isSuperAdmin()) {
      toast('Atualização local por voz é exclusiva do Super Admin');
      return;
    }

    dispatching = true;
    startButton.disabled = true;
    sendButton.disabled = true;
    statusNode.textContent = automatic
      ? 'Comando reconhecido. Atualizando o Linux automaticamente…'
      : 'Enviando atualização local ao Linux…';

    try {
      const data = await api('/voice/system-actions', {
        method: 'POST',
        body: JSON.stringify({ transcript: normalize(transcript), project_id: null }),
      });
      modal.close();
      toast(data.message || 'Atualização local enviada ao Linux');
      if ('speechSynthesis' in window) {
        speechSynthesis.cancel();
        speechSynthesis.speak(new SpeechSynthesisUtterance('Atualização local enviada ao Linux.'));
      }
      if (typeof load === 'function') load();
    } catch (error) {
      statusNode.textContent = 'Falha ao iniciar atualização local.';
      toast(error.message || 'Falha ao iniciar atualização local');
    } finally {
      dispatching = false;
      startButton.disabled = false;
      sendButton.disabled = false;
    }
  }

  sendButton.onclick = async (event) => {
    const transcript = normalize(transcriptInput.value);
    if (isLocalUpdate(transcript)) {
      event?.preventDefault?.();
      await dispatchLocalUpdate(transcript, false);
      return;
    }
    if (typeof originalSend === 'function') return originalSend.call(sendButton, event);
  };

  startButton.onclick = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      toast('Reconhecimento de voz indisponível neste navegador');
      return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = 'pt-BR';
    recognition.interimResults = true;
    recognition.continuous = false;
    statusNode.textContent = 'Ouvindo…';

    recognition.onresult = (event) => {
      transcriptInput.value = [...event.results].map((result) => result[0].transcript).join(' ');
    };

    recognition.onend = async () => {
      const transcript = normalize(transcriptInput.value);
      if (isLocalUpdate(transcript)) {
        await dispatchLocalUpdate(transcript, true);
        return;
      }
      statusNode.textContent = 'Transcrição pronta. Revise antes de enviar.';
    };

    recognition.onerror = () => {
      statusNode.textContent = 'Falha no reconhecimento de voz.';
      toast('Não foi possível capturar o áudio');
    };

    recognition.start();
  };
})();
