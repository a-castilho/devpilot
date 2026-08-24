(() => {
  if (!document.querySelector('script[data-linux-git-cloud]')) {
    const script = document.createElement('script');
    script.src = '/assets/linux-git-cloud.js';
    script.dataset.linuxGitCloud = '1';
    document.head.appendChild(script);
  }

  if (!document.querySelector('script[data-linux-game-access]')) {
    const script = document.createElement('script');
    script.src = '/assets/linux-game-access.js?v=20260824-1';
    script.async = false;
    script.dataset.linuxGameAccess = '1';
    document.head.appendChild(script);
  }

  const waitForLinux = () => {
    const view = document.querySelector('#linux-view');
    if (!view || !view.querySelector('.linux-shell')) {
      window.setTimeout(waitForLinux, 250);
      return;
    }
    if (view.querySelector('#linux-beginner-coach')) return;

    const style = document.createElement('style');
    style.textContent = `
      .linux-beginner-coach{display:grid;gap:12px;padding:16px;border:1px solid var(--line);border-radius:16px;background:var(--surface,#0d1928)}
      .linux-beginner-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap}
      .linux-beginner-head h3{margin:2px 0 4px}.linux-beginner-head p{margin:0;color:var(--muted);font-size:12px;max-width:760px}
      .linux-learning-steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
      .linux-learning-step{border:1px solid var(--line);border-radius:12px;padding:11px;background:var(--surface2,#101b2b);cursor:pointer;text-align:left;color:var(--text)}
      .linux-learning-step strong{display:block;margin-bottom:4px;font-size:12px}.linux-learning-step small{color:var(--muted);line-height:1.35}
      .linux-learning-step.done{border-color:rgba(70,210,145,.55);background:rgba(70,210,145,.08)}
      .linux-beginner-note{font-size:12px;color:var(--muted)}
      @media(max-width:900px){.linux-learning-steps{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:520px){.linux-learning-steps{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);

    const coach = document.createElement('section');
    coach.id = 'linux-beginner-coach';
    coach.className = 'linux-beginner-coach';
    coach.innerHTML = `
      <div class="linux-beginner-head">
        <div>
          <span class="eyebrow">PRIMEIROS PASSOS</span>
          <h3>Aprenda fazendo, sem decorar comandos.</h3>
          <p>Use estes quatro passos. O DevPilot abre a sessão quando necessário e envia somente comandos de consulta ou navegação.</p>
        </div>
        <button type="button" class="primary" data-linux-learn="start">Começar agora</button>
      </div>
      <div class="linux-learning-steps">
        <button type="button" class="linux-learning-step" data-linux-learn="where"><strong>1. Descobrir onde estou</strong><small>Executa pwd e mostra a pasta atual.</small></button>
        <button type="button" class="linux-learning-step" data-linux-learn="files"><strong>2. Ver arquivos</strong><small>Lista o conteúdo da pasta sem alterar nada.</small></button>
        <button type="button" class="linux-learning-step" data-linux-learn="projects"><strong>3. Encontrar projetos</strong><small>Vai para ~/Documents e lista os projetos disponíveis.</small></button>
        <button type="button" class="linux-learning-step" data-linux-learn="devpilot"><strong>4. Abrir DevPilot</strong><small>Entra no projeto devpilot e mostra o status do Git.</small></button>
      </div>
      <div class="linux-beginner-note" id="linux-beginner-note">Dica: você também pode usar “Falar com DevPilot” e perguntar o que quer fazer em linguagem normal.</div>
    `;

    const guide = view.querySelector('.linux-guide');
    if (guide) guide.before(coach); else view.querySelector('.linux-shell')?.prepend(coach);

    const input = () => view.querySelector('#linux-terminal-input');
    const send = () => view.querySelector('#linux-terminal-send');
    const start = () => view.querySelector('#linux-terminal-start');
    const note = text => { const el = view.querySelector('#linux-beginner-note'); if (el) el.textContent = text; };

    const ensureSession = async () => {
      const field = input();
      if (field && !field.disabled) return true;
      start()?.click();
      for (let i = 0; i < 30; i += 1) {
        await new Promise(resolve => setTimeout(resolve, 150));
        if (input() && !input().disabled) return true;
      }
      note('Não consegui abrir a sessão automaticamente. Clique em “Abrir meu Linux” e tente novamente.');
      return false;
    };

    const run = async (command, explanation, button) => {
      if (!(await ensureSession())) return;
      const field = input();
      if (!field) return;
      field.value = command;
      field.dispatchEvent(new Event('input', {bubbles: true}));
      note(`${explanation} Comando: ${command}`);
      send()?.click();
      button?.classList.add('done');
    };

    const actions = {
      where: ['pwd', 'Mostrando a pasta em que você está agora.'],
      files: ['ls -lah', 'Listando arquivos e pastas da localização atual.'],
      projects: ['cd ~/Documents && printf "Pasta: " && pwd && ls -lah', 'Indo para a pasta Documents, onde normalmente ficam seus projetos.'],
      devpilot: ['cd ~/Documents/devpilot && printf "Projeto: " && pwd && git status --short --branch', 'Entrando no projeto DevPilot e mostrando a situação atual do Git.'],
    };

    coach.addEventListener('click', async event => {
      const button = event.target.closest('[data-linux-learn]');
      if (!button) return;
      const action = button.dataset.linuxLearn;
      if (action === 'start') {
        note('Vamos começar abrindo seu Linux e descobrindo onde você está.');
        const first = coach.querySelector('[data-linux-learn="where"]');
        const [command, explanation] = actions.where;
        await run(command, explanation, first);
        return;
      }
      const item = actions[action];
      if (!item) return;
      await run(item[0], item[1], button);
    });
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', waitForLinux, {once: true});
  else waitForLinux();
})();
