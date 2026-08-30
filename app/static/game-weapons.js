/* DevPilot Build Game: task creation becomes weapon development while the game view is active. */
(() => {
  'use strict';

  const GAME_VIEW_SELECTOR = '#build-game-view.active';
  const TASK_MODAL_SELECTOR = '#task-modal';
  const TASK_BUTTON_SELECTOR = '[data-open="task-modal"]';
  const STYLE_ID = 'devpilot-game-weapons-style';
  const originalButtonText = new WeakMap();
  let syncQueued = false;

  const weaponModes = {
    'analysis-read-only': {
      option: '📡 Radar de análise · analisar / diagnosticar',
      title: 'Radar de análise',
      text: 'Varre o repositório em modo somente leitura para localizar riscos, falhas, evidências e oportunidades antes de qualquer disparo de implementação.'
    },
    develop: {
      option: '⚡ Laser construtor · desenvolver / implementar',
      title: 'Laser construtor',
      text: 'Transforma um objetivo aprovado em código real, reaproveitando o que já existe e construindo somente o que estiver faltando.'
    },
    fix: {
      option: '🎯 Canhão de correção · corrigir / depurar',
      title: 'Canhão de correção',
      text: 'Mira na causa raiz, aplica uma correção mínima e valida regressões antes de considerar o alvo atingido.'
    },
    review: {
      option: '📡 Radar de análise · revisar / validar',
      title: 'Radar de revisão',
      text: 'Reforça a defesa do projeto revisando regressões, segurança, testes e inconsistências sem implementar mudanças automaticamente.'
    }
  };

  const originalModal = {
    eyebrow: 'NOVA TAREFA',
    title: 'O que você quer que a IA faça?',
    description: 'Informe o contexto com suas próprias palavras. O DevPilot organiza a instrução e combina o texto com as regras do projeto antes da análise.',
    modeLabel: 'Modo',
    titleLabel: 'Título',
    contextLabel: 'Contexto para análise',
    placeholder: 'Cole aqui o problema, comportamento observado, requisitos, regras de negócio ou qualquer contexto que a IA deve considerar...',
    options: {
      'analysis-read-only': 'Analisar / diagnosticar',
      develop: 'Desenvolver / implementar',
      fix: 'Corrigir / depurar',
      review: 'Revisar / validar'
    }
  };

  const gameActive = () => Boolean(document.querySelector(GAME_VIEW_SELECTOR));

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #task-modal.game-weapons-mode .task-modal-form {
        border-color: rgba(104, 240, 187, .34);
        box-shadow: 0 24px 70px rgba(0, 0, 0, .62), inset 0 1px 0 rgba(104, 240, 187, .08);
      }
      #task-modal.game-weapons-mode .task-modal-heading .eyebrow { color: #68f0bb; }
      #task-modal.game-weapons-mode .task-assist-card { border-color: rgba(88, 216, 255, .28); }
      #task-modal.game-weapons-mode #task-submit::before { content: '⚔ '; }
    `;
    document.head.appendChild(style);
  }

  function setLabelText(label, text) {
    if (!label) return;
    const node = [...label.childNodes].find(child => child.nodeType === Node.TEXT_NODE && child.textContent.trim());
    if (node) node.textContent = `${text}\n        `;
  }

  function modalParts() {
    const modal = document.querySelector(TASK_MODAL_SELECTOR);
    const form = modal?.querySelector('#task-form');
    const heading = modal?.querySelector('.task-modal-heading');
    const mode = modal?.querySelector('#task-mode');
    return {
      modal,
      form,
      mode,
      eyebrow: heading?.querySelector('.eyebrow'),
      title: heading?.querySelector('h2'),
      description: heading?.querySelector('p'),
      modeLabel: mode?.closest('label'),
      titleLabel: form?.querySelector('input[name="title"]')?.closest('label'),
      titleInput: form?.querySelector('input[name="title"]'),
      contextLabel: form?.querySelector('#task-context')?.closest('label'),
      context: form?.querySelector('#task-context'),
      assistTitle: form?.querySelector('#task-assist-title'),
      assistText: form?.querySelector('#task-assist-text'),
      submit: form?.querySelector('#task-submit')
    };
  }

  function syncButtons(active) {
    document.querySelectorAll(TASK_BUTTON_SELECTOR).forEach(button => {
      if (!originalButtonText.has(button)) originalButtonText.set(button, button.textContent);
      const original = originalButtonText.get(button) || '';
      const isTaskButton = original.toLocaleLowerCase('pt-BR').includes('nova tarefa');
      if (!isTaskButton) return;
      button.textContent = active ? '⚔ Desenvolver armas' : original;
      button.setAttribute('aria-label', active ? 'Desenvolver armas da nave' : original.trim());
      button.title = active ? 'Desenvolver armas da nave' : '';
    });
  }

  function syncModal(active) {
    const parts = modalParts();
    if (!parts.modal || !parts.form || !parts.mode) return;

    parts.modal.classList.toggle('game-weapons-mode', active);

    if (!active) {
      if (parts.eyebrow) parts.eyebrow.textContent = originalModal.eyebrow;
      if (parts.title) parts.title.textContent = originalModal.title;
      if (parts.description) parts.description.textContent = originalModal.description;
      setLabelText(parts.modeLabel, originalModal.modeLabel);
      setLabelText(parts.titleLabel, originalModal.titleLabel);
      setLabelText(parts.contextLabel, originalModal.contextLabel);
      if (parts.titleInput) parts.titleInput.placeholder = 'Ex.: Auditoria técnica da arquitetura';
      if (parts.context) parts.context.placeholder = originalModal.placeholder;
      [...parts.mode.options].forEach(option => {
        if (originalModal.options[option.value]) option.textContent = originalModal.options[option.value];
      });
      parts.mode.dispatchEvent(new Event('change', {bubbles: false}));
      return;
    }

    if (parts.eyebrow) parts.eyebrow.textContent = 'ARSENAL DA NAVE';
    if (parts.title) parts.title.textContent = 'Desenvolver armas';
    if (parts.description) {
      parts.description.textContent = 'No modo Jogo, cada análise ou ação vira uma arma de desenvolvimento. Escolha o mecanismo, defina o alvo e prepare o próximo disparo; segurança, testes, deploy e Linux também entram no arsenal pela classificação da oficina.';
    }
    setLabelText(parts.modeLabel, 'Tipo de arma');
    setLabelText(parts.titleLabel, 'Nome da arma');
    setLabelText(parts.contextLabel, 'Alvo / contexto');
    if (parts.titleInput) parts.titleInput.placeholder = 'Ex.: Radar de segurança do login';
    if (parts.context) parts.context.placeholder = 'Descreva o alvo, comportamento observado, resultado esperado, regras e evidências que esta arma deve considerar...';

    [...parts.mode.options].forEach(option => {
      const weapon = weaponModes[option.value];
      if (weapon) option.textContent = weapon.option;
    });

    const weapon = weaponModes[parts.mode.value] || weaponModes['analysis-read-only'];
    if (parts.assistTitle) parts.assistTitle.textContent = weapon.title;
    if (parts.assistText) parts.assistText.textContent = weapon.text;
    if (parts.submit) parts.submit.textContent = 'Desenvolver arma';
  }

  function sync() {
    syncQueued = false;
    const active = gameActive();
    syncButtons(active);
    syncModal(active);
  }

  function scheduleSync() {
    if (syncQueued) return;
    syncQueued = true;
    queueMicrotask(sync);
  }

  ensureStyle();
  document.addEventListener('click', event => {
    if (event.target.closest(TASK_BUTTON_SELECTOR) || event.target.closest('[data-view]') || event.target.closest('[data-project-build-game]')) {
      window.setTimeout(scheduleSync, 0);
    }
  }, true);

  document.querySelector('#task-mode')?.addEventListener('change', () => window.setTimeout(scheduleSync, 0));

  /*
   * Somente eventos do próprio jogo.
   * Nenhum observer no document.body.
   */
  document.addEventListener(
    'devpilot:game:standalone-ready',
    scheduleSync
  );

  document.addEventListener(
    'devpilot:view-changed',
    scheduleSync
  );

  document.querySelector('#task-modal')
    ?.addEventListener(
      'close',
      scheduleSync
    );

  sync();
})();
