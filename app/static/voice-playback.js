(() => {
  const modal = document.querySelector('#voice-modal');
  const transcript = document.querySelector('#voice-transcript');
  const statusNode = document.querySelector('#voice-status');
  const actions = modal?.querySelector('.hero-actions');
  if (!modal || !transcript || !statusNode || !actions) return;
  if (modal.querySelector('#voice-output-mode')) return;

  const wrapper = document.createElement('section');
  wrapper.className = 'voice-playback-controls';
  wrapper.innerHTML = `
    <div class="voice-playback-head">
      <div>
        <span class="eyebrow">SAÍDA DE VOZ</span>
        <strong>Ouvir a transcrição</strong>
      </div>
      <select id="voice-output-mode" aria-label="Escolher voz para reprodução">
        <option value="human">Humana</option>
        <option value="male">Homem</option>
        <option value="female">Mulher</option>
        <option value="machine">Máquina</option>
        <option value="chatgpt">ChatGPT</option>
      </select>
    </div>
    <button type="button" class="voice voice-playback-button" id="voice-playback">▶ Ouvir transcrição</button>
    <small id="voice-playback-hint">Vozes Humana, Homem, Mulher e Máquina usam o sintetizador do aparelho. ChatGPT usa a conexão OpenAI configurada no DevPilot.</small>
  `;
  actions.parentNode.insertBefore(wrapper, actions);

  const button = wrapper.querySelector('#voice-playback');
  const modeSelect = wrapper.querySelector('#voice-output-mode');
  const hint = wrapper.querySelector('#voice-playback-hint');

  const style = document.createElement('style');
  style.textContent = `
    .voice-playback-controls{display:grid;gap:12px;padding:14px 0 4px}
    .voice-playback-head{display:flex;gap:12px;align-items:end;justify-content:space-between}
    .voice-playback-head>div{display:grid;gap:3px;min-width:0}
    .voice-playback-head strong{font-size:1rem}
    #voice-output-mode{min-width:150px;max-width:52%;background:#08182a;color:#eef8ff;border:1px solid rgba(72,214,207,.35);border-radius:12px;padding:11px 12px;font:inherit}
    .voice-playback-button{width:100%;min-height:48px}
    #voice-playback-hint{color:#9fb2c7;line-height:1.35}
    @media (max-width:640px){
      .voice-playback-head{align-items:stretch;flex-direction:column}
      #voice-output-mode{max-width:none;width:100%;min-width:0}
    }
  `;
  document.head.appendChild(style);

  let activeAudio = null;
  let objectUrl = '';

  const localVoiceNames = {
    male: ['felipe', 'ricardo', 'daniel', 'antonio', 'carlos', 'joao', 'jorge', 'male', 'man', 'homem'],
    female: ['luciana', 'maria', 'helena', 'fernanda', 'camila', 'paulina', 'samantha', 'victoria', 'female', 'woman', 'mulher'],
  };

  function stopPlayback() {
    try {
      window.speechSynthesis?.cancel?.();
    } catch (_) {
      // Best effort only.
    }
    if (activeAudio) {
      try {
        activeAudio.pause();
        activeAudio.currentTime = 0;
      } catch (_) {
        // Best effort only.
      }
      activeAudio = null;
    }
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = '';
    }
    button.dataset.speaking = '0';
    button.textContent = '▶ Ouvir transcrição';
  }

  function fail(message) {
    stopPlayback();
    statusNode.textContent = message;
    if (typeof toast === 'function') toast(message);
  }

  function portugueseVoices() {
    const voices = window.speechSynthesis?.getVoices?.() || [];
    const pt = voices.filter(voice => String(voice.lang || '').toLowerCase().startsWith('pt'));
    return pt.length ? pt : voices;
  }

  function chooseVoice(mode) {
    const voices = portugueseVoices();
    if (!voices.length) return null;
    if (!localVoiceNames[mode]) return voices[0];
    const names = localVoiceNames[mode];
    return voices.find(voice => {
      const value = `${voice.name || ''} ${voice.voiceURI || ''}`.toLowerCase();
      return names.some(name => value.includes(name));
    }) || voices[0];
  }

  function speakLocal(text, mode) {
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
      fail('Este navegador não possui síntese de voz local. Escolha ChatGPT.');
      return;
    }

    stopPlayback();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'pt-BR';
    utterance.voice = chooseVoice(mode);
    utterance.volume = 1;

    if (mode === 'male') {
      utterance.pitch = 0.78;
      utterance.rate = 0.95;
    } else if (mode === 'female') {
      utterance.pitch = 1.16;
      utterance.rate = 1.0;
    } else if (mode === 'machine') {
      utterance.pitch = 0.58;
      utterance.rate = 0.82;
    } else {
      utterance.pitch = 1.0;
      utterance.rate = 0.98;
    }

    utterance.onstart = () => {
      button.dataset.speaking = '1';
      button.textContent = '■ Parar voz';
      statusNode.textContent = `Reproduzindo transcrição: ${modeSelect.options[modeSelect.selectedIndex].text}.`;
    };
    utterance.onend = () => {
      stopPlayback();
      statusNode.textContent = 'Transcrição pronta. Revise antes de enviar.';
    };
    utterance.onerror = () => fail('Não foi possível reproduzir esta voz no aparelho.');
    window.speechSynthesis.speak(utterance);
  }

  async function errorMessage(response) {
    try {
      const data = await response.json();
      if (typeof data?.detail === 'string') return data.detail;
    } catch (_) {
      // Non-JSON audio errors fall back to the generic message.
    }
    return 'Não foi possível gerar a voz ChatGPT.';
  }

  async function speakChatGPT(text) {
    stopPlayback();
    button.disabled = true;
    button.textContent = 'Gerando voz ChatGPT…';
    statusNode.textContent = 'Gerando voz ChatGPT para a transcrição…';

    try {
      const token = localStorage.getItem('devpilot-token') || '';
      const response = await fetch('/api/voice/speech', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({text, voice: 'coral'}),
      });

      if (!response.ok) throw new Error(await errorMessage(response));
      const blob = await response.blob();
      if (!blob.size) throw new Error('A voz ChatGPT retornou um áudio vazio.');

      objectUrl = URL.createObjectURL(blob);
      activeAudio = new Audio(objectUrl);
      activeAudio.onplay = () => {
        button.dataset.speaking = '1';
        button.textContent = '■ Parar voz';
        statusNode.textContent = 'Reproduzindo transcrição com voz ChatGPT.';
      };
      activeAudio.onended = () => {
        stopPlayback();
        statusNode.textContent = 'Transcrição pronta. Revise antes de enviar.';
      };
      activeAudio.onerror = () => fail('O navegador não conseguiu reproduzir o áudio ChatGPT.');
      await activeAudio.play();
    } catch (error) {
      fail(error?.message || 'Não foi possível gerar a voz ChatGPT.');
    } finally {
      button.disabled = false;
      if (button.dataset.speaking !== '1') button.textContent = '▶ Ouvir transcrição';
    }
  }

  button.addEventListener('click', async () => {
    if (button.dataset.speaking === '1') {
      stopPlayback();
      statusNode.textContent = 'Reprodução interrompida.';
      return;
    }

    const text = transcript.value.trim();
    if (!text) {
      fail('Grave ou digite uma transcrição antes de ouvir.');
      return;
    }

    const mode = modeSelect.value;
    if (mode === 'chatgpt') {
      await speakChatGPT(text);
      return;
    }
    speakLocal(text, mode);
  });

  modeSelect.addEventListener('change', () => {
    stopPlayback();
    hint.textContent = modeSelect.value === 'chatgpt'
      ? 'ChatGPT usa gpt-4o-mini-tts com a credencial OpenAI já cadastrada no DevPilot.'
      : 'Esta opção usa a síntese de voz do próprio aparelho e não consome API.';
  });

  modal.addEventListener('close', stopPlayback);
})();
