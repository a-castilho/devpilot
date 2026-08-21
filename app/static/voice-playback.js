(() => {
  const modal = document.querySelector('#voice-modal');
  const transcript = document.querySelector('#voice-transcript');
  const statusNode = document.querySelector('#voice-status');
  const projectSelect = document.querySelector('#voice-project');
  const actions = modal?.querySelector('.hero-actions');
  if (!modal || !transcript || !statusNode || !actions) return;
  if (modal.querySelector('#voice-output-mode')) return;

  // A conversa por voz continua automática, mas o cliente também pode ouvir
  // novamente o texto atual da transcrição antes de prosseguir.
  modal.querySelector('#voice-send')?.remove();

  const wrapper = document.createElement('section');
  wrapper.className = 'voice-playback-controls voice-conversation-controls';
  wrapper.innerHTML = `
    <div class="voice-playback-head">
      <div>
        <span class="eyebrow">CONVERSA POR VOZ</span>
        <strong>DevPilot fala com você</strong>
      </div>
      <select id="voice-output-mode" aria-label="Escolher voz do DevPilot">
        <option value="human">Humana</option>
        <option value="male">Homem</option>
        <option value="female">Mulher</option>
        <option value="machine">Máquina</option>
        <option value="chatgpt">ChatGPT</option>
      </select>
    </div>
    <button type="button" class="voice voice-playback-button" id="voice-playback">▶ Ouvir transcrição</button>
    <div id="voice-chat-log" class="voice-chat-log" aria-live="polite">
      <div class="voice-chat-empty">Grave sua mensagem. O DevPilot responderá automaticamente em voz.</div>
    </div>
    <small id="voice-playback-hint">Voz local usa o aparelho e, quando o navegador não possui síntese funcional, usa o motor local do DevPilot sem consumir API.</small>
  `;
  actions.parentNode.insertBefore(wrapper, actions);

  const button = wrapper.querySelector('#voice-playback');
  const modeSelect = wrapper.querySelector('#voice-output-mode');
  const hint = wrapper.querySelector('#voice-playback-hint');
  const chatLog = wrapper.querySelector('#voice-chat-log');

  const style = document.createElement('style');
  style.textContent = `
    .voice-conversation-controls{display:grid;gap:12px;padding:14px 0 4px}
    .voice-playback-head{display:flex;gap:12px;align-items:end;justify-content:space-between}
    .voice-playback-head>div{display:grid;gap:3px;min-width:0}
    .voice-playback-head strong{font-size:1rem}
    #voice-output-mode{min-width:150px;max-width:52%;background:#08182a;color:#eef8ff;border:1px solid rgba(72,214,207,.35);border-radius:12px;padding:11px 12px;font:inherit}
    #voice-playback-hint{color:#9fb2c7;line-height:1.35}
    .voice-playback-button{min-height:44px}
    .voice-chat-log{display:grid;gap:8px;max-height:210px;overflow:auto;padding:2px}
    .voice-chat-empty{padding:12px;border:1px dashed rgba(159,178,199,.24);border-radius:12px;color:#9fb2c7;font-size:.9rem}
    .voice-chat-turn{display:grid;gap:4px;padding:10px 12px;border-radius:13px;border:1px solid rgba(159,178,199,.16);background:rgba(8,24,42,.72)}
    .voice-chat-turn[data-role="assistant"]{border-color:rgba(72,214,207,.30);background:rgba(20,80,86,.18)}
    .voice-chat-turn strong{font-size:.75rem;letter-spacing:.07em;text-transform:uppercase;color:#9fb2c7}
    .voice-chat-turn p{margin:0;line-height:1.42;color:#eef8ff}
    @media (max-width:640px){
      .voice-playback-head{align-items:stretch;flex-direction:column}
      #voice-output-mode{max-width:none;width:100%;min-width:0}
      .voice-chat-log{max-height:180px}
    }
  `;
  document.head.appendChild(style);

  let activeAudio = null;
  let objectUrl = '';
  let activeUtterance = null;
  let processing = false;
  let history = [];
  let lastProcessedText = '';
  let lastProcessedAt = 0;

  const localVoiceNames = {
    male: ['felipe', 'ricardo', 'daniel', 'antonio', 'carlos', 'joao', 'jorge', 'male', 'man', 'homem'],
    female: ['luciana', 'maria', 'helena', 'fernanda', 'camila', 'paulina', 'samantha', 'victoria', 'female', 'woman', 'mulher'],
  };

  function setButtonSpeaking(speaking) {
    button.dataset.speaking = speaking ? '1' : '0';
    button.textContent = speaking ? '■ Parar voz' : '▶ Ouvir transcrição';
  }

  function stopPlayback() {
    activeUtterance = null;
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
    setButtonSpeaking(false);
  }

  function fail(message) {
    stopPlayback();
    statusNode.textContent = message;
    if (typeof toast === 'function') toast(message);
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[char]));
  }

  function appendTurn(role, text) {
    chatLog.querySelector('.voice-chat-empty')?.remove();
    const item = document.createElement('div');
    item.className = 'voice-chat-turn';
    item.dataset.role = role;
    item.innerHTML = `<strong>${role === 'assistant' ? 'DevPilot' : 'Você'}</strong><p>${escapeHtml(text)}</p>`;
    chatLog.appendChild(item);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function availableVoices() {
    return window.speechSynthesis?.getVoices?.() || [];
  }

  async function waitForVoices(timeoutMs = 900) {
    const current = availableVoices();
    if (current.length) return current;
    if (!window.speechSynthesis?.addEventListener) return current;

    return new Promise((resolve) => {
      let finished = false;
      const finish = () => {
        if (finished) return;
        finished = true;
        window.speechSynthesis.removeEventListener('voiceschanged', onVoicesChanged);
        resolve(availableVoices());
      };
      const onVoicesChanged = () => finish();
      window.speechSynthesis.addEventListener('voiceschanged', onVoicesChanged, {once: true});
      setTimeout(finish, timeoutMs);
    });
  }

  function portugueseVoices(voices) {
    const pt = voices.filter((voice) => String(voice.lang || '').toLowerCase().startsWith('pt'));
    return pt.length ? pt : voices;
  }

  function chooseVoice(mode, voices) {
    const candidates = portugueseVoices(voices);
    if (!candidates.length) return null;
    if (!localVoiceNames[mode]) return candidates[0];
    const names = localVoiceNames[mode];
    return candidates.find((voice) => {
      const value = `${voice.name || ''} ${voice.voiceURI || ''}`.toLowerCase();
      return names.some((name) => value.includes(name));
    }) || candidates[0];
  }

  async function speakBrowserLocal(text, mode) {
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) {
      throw new Error('Síntese de voz do navegador indisponível.');
    }

    const voices = await waitForVoices();
    if (!voices.length) {
      throw new Error('Nenhuma voz local foi carregada pelo navegador.');
    }

    stopPlayback();
    const utterance = new SpeechSynthesisUtterance(text);
    const voice = chooseVoice(mode, voices);
    if (voice) {
      utterance.voice = voice;
      utterance.lang = voice.lang || 'pt-BR';
    } else {
      utterance.lang = 'pt-BR';
    }
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

    activeUtterance = utterance;
    return new Promise((resolve, reject) => {
      utterance.onstart = () => {
        setButtonSpeaking(true);
        statusNode.textContent = `Reproduzindo com voz ${modeSelect.options[modeSelect.selectedIndex].text}.`;
      };
      utterance.onend = () => {
        activeUtterance = null;
        setButtonSpeaking(false);
        resolve();
      };
      utterance.onerror = (event) => {
        activeUtterance = null;
        setButtonSpeaking(false);
        const code = String(event?.error || 'synthesis-failed');
        reject(new Error(`Falha na síntese local do navegador: ${code}.`));
      };
      window.speechSynthesis.speak(utterance);
    });
  }

  async function errorMessage(response, fallback) {
    try {
      const data = await response.json();
      if (typeof data?.detail === 'string') return data.detail;
    } catch (_) {
      // Non-JSON errors fall back to the supplied message.
    }
    return fallback;
  }

  async function playAudioResponse(response, playingMessage) {
    const blob = await response.blob();
    if (!blob.size) throw new Error('O serviço de voz retornou um áudio vazio.');

    await new Promise(async (resolve, reject) => {
      objectUrl = URL.createObjectURL(blob);
      activeAudio = new Audio(objectUrl);
      activeAudio.onplay = () => {
        setButtonSpeaking(true);
        statusNode.textContent = playingMessage;
      };
      activeAudio.onended = () => {
        stopPlayback();
        resolve();
      };
      activeAudio.onerror = () => reject(new Error('O navegador não conseguiu reproduzir o áudio gerado.'));
      try {
        await activeAudio.play();
      } catch (error) {
        reject(error);
      }
    });
  }

  async function speakServerLocal(text, mode) {
    stopPlayback();
    statusNode.textContent = 'Preparando voz local do DevPilot…';
    const token = localStorage.getItem('devpilot-token') || '';
    const response = await fetch('/api/voice/speech/local', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({text, voice: mode}),
    });
    if (!response.ok) {
      throw new Error(await errorMessage(response, 'Não foi possível gerar a voz local.'));
    }
    await playAudioResponse(
      response,
      `Reproduzindo com voz local ${modeSelect.options[modeSelect.selectedIndex].text}.`,
    );
  }

  async function speakLocal(text, mode) {
    try {
      await speakBrowserLocal(text, mode);
    } catch (browserError) {
      try {
        await speakServerLocal(text, mode);
        if (typeof toast === 'function') {
          toast('Voz do navegador indisponível; usando voz local do DevPilot.');
        }
      } catch (serverError) {
        const browserReason = browserError?.message ? ` ${browserError.message}` : '';
        throw new Error(`${serverError?.message || 'Não foi possível reproduzir a voz local.'}${browserReason}`);
      }
    }
  }

  async function speakChatGPT(text) {
    stopPlayback();
    statusNode.textContent = 'Gerando a voz ChatGPT…';
    const token = localStorage.getItem('devpilot-token') || '';
    const response = await fetch('/api/voice/speech', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({text, voice: 'coral'}),
    });

    if (!response.ok) {
      throw new Error(await errorMessage(response, 'Não foi possível gerar a voz ChatGPT.'));
    }

    await playAudioResponse(response, 'DevPilot está falando com voz ChatGPT.');
  }

  async function speakSelected(text, mode) {
    if (mode !== 'chatgpt') {
      await speakLocal(text, mode);
      return;
    }
    try {
      await speakChatGPT(text);
    } catch (error) {
      await speakLocal(text, 'human');
      if (typeof toast === 'function') toast('Voz ChatGPT indisponível; usando voz local.');
    }
  }

  async function processTranscript() {
    if (processing) return;
    const text = transcript.value.trim();
    if (!text) return;

    const now = Date.now();
    if (text === lastProcessedText && now - lastProcessedAt < 1500) return;
    lastProcessedText = text;
    lastProcessedAt = now;
    processing = true;

    appendTurn('user', text);
    statusNode.textContent = 'DevPilot está pensando…';

    try {
      if (typeof api !== 'function') throw new Error('API de conversa indisponível.');
      const data = await api('/voice/chat', {
        method: 'POST',
        body: JSON.stringify({
          transcript: text,
          project_id: projectSelect?.value || null,
          history: history.slice(-12),
        }),
      });
      const reply = String(data?.reply || '').trim();
      if (!reply) throw new Error('O DevPilot não retornou uma resposta.');

      history.push({role: 'user', text}, {role: 'assistant', text: reply});
      history = history.slice(-12);
      appendTurn('assistant', reply);
      await speakSelected(reply, modeSelect.value);
      statusNode.textContent = 'DevPilot respondeu. Toque em Gravar para continuar a conversa.';
    } catch (error) {
      fail(error?.message || 'Não foi possível conversar com o DevPilot.');
    } finally {
      processing = false;
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

    button.disabled = true;
    try {
      await speakSelected(text, modeSelect.value);
      statusNode.textContent = 'Transcrição reproduzida.';
    } catch (error) {
      fail(error?.message || 'Não foi possível reproduzir a transcrição.');
    } finally {
      button.disabled = false;
      if (button.dataset.speaking !== '1') setButtonSpeaking(false);
    }
  });

  const observer = new MutationObserver(() => {
    const value = String(statusNode.textContent || '').trim().toLowerCase();
    if (value.startsWith('transcrição pronta')) {
      queueMicrotask(processTranscript);
    }
  });
  observer.observe(statusNode, {childList: true, characterData: true, subtree: true});

  transcript.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      processTranscript();
    }
  });

  const savedMode = localStorage.getItem('devpilot-voice-output-mode');
  if (savedMode && [...modeSelect.options].some((option) => option.value === savedMode)) {
    modeSelect.value = savedMode;
  }
  modeSelect.addEventListener('change', () => {
    stopPlayback();
    localStorage.setItem('devpilot-voice-output-mode', modeSelect.value);
    hint.textContent = modeSelect.value === 'chatgpt'
      ? 'As respostas usam a voz ChatGPT pela conexão OpenAI configurada no DevPilot.'
      : 'Primeiro usamos a voz do aparelho. Se o navegador falhar, o DevPilot gera a voz localmente sem consumir API.';
  });

  modal.addEventListener('close', () => {
    stopPlayback();
    history = [];
    chatLog.innerHTML = '<div class="voice-chat-empty">Grave sua mensagem. O DevPilot responderá automaticamente em voz.</div>';
  });

  window.devpilotVoiceConversationSubmit = processTranscript;
})();