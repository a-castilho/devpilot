(() => {
  const token = () => localStorage.getItem('devpilot-token') || '';

  const api = async path => {
    const response = await fetch(path, {
      headers: {Authorization: `Bearer ${token()}`},
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
    return data;
  };

  const gitStatusCommand = [
    'if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then',
    '  git status --short --branch;',
    'else',
    "  printf 'GitHub: integrado pela credencial cadastrada em Clouds.\\n';",
    "  if command -v gh >/dev/null 2>&1; then gh auth status -h github.com 2>&1 | head -6; fi;",
    "  printf '\\nNenhum repositório aberto. Entre na pasta de um projeto para ver o status Git.\\n';",
    'fi',
  ].join(' ');

  let decorating = false;

  const decorate = async () => {
    if (!token() || decorating) return;
    const view = document.querySelector('#linux-view');
    if (!view) return;

    const button = [...view.querySelectorAll('[data-linux-command]')]
      .find(item => String(item.dataset.linuxCommand || '').includes('git status'));
    if (button) {
      button.textContent = 'Git';
      button.dataset.linuxCommand = gitStatusCommand;
      button.dataset.linuxHint = 'Git usa automaticamente a credencial GitHub cadastrada em Clouds.';
    }

    decorating = true;
    try {
      const status = await api('/api/linux/status');
      const git = status?.profile?.git_cloud;
      const label = view.querySelector('#linux-access-label');
      if (!label || !git) return;

      const base = String(label.textContent || '').replace(/ · GitHub.*$/, '');
      if (git.ready) {
        const scope = git.scope ? ` (${git.scope})` : '';
        label.textContent = `${base} · GitHub integrado via Clouds${scope}.`;
        view.dataset.gitCloudReady = '1';
      } else if (git.configured && !git.enabled) {
        label.textContent = `${base} · GitHub cadastrado em Clouds, mas desativado.`;
        view.dataset.gitCloudReady = '0';
      } else {
        label.textContent = `${base} · GitHub ainda não cadastrado em Clouds.`;
        view.dataset.gitCloudReady = '0';
      }
    } catch (_) {
      // O terminal continua funcional mesmo se o indicador não puder ser atualizado.
    } finally {
      decorating = false;
    }
  };

  const waitForLinux = () => {
    if (document.querySelector('#linux-view')) {
      decorate();
      return;
    }
    window.setTimeout(waitForLinux, 250);
  };

  document.addEventListener('click', event => {
    if (event.target?.closest?.('[data-view="linux"], [data-linux-view="1"]')) {
      window.setTimeout(decorate, 40);
    }
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', waitForLinux, {once: true});
  else waitForLinux();
})();
