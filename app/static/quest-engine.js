(() => {
  const token = localStorage.getItem('devpilot-token');
  if (!token || document.querySelector('#devpilot-quest-launcher')) return;

  const api = async (path, options = {}) => {
    const response = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(options.headers || {}),
      },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || 'Falha no Quest Engine');
    return body;
  };

  const escapeHtml = value => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

  const launcher = document.createElement('button');
  launcher.id = 'devpilot-quest-launcher';
  launcher.type = 'button';
  launcher.textContent = '⚔ Jornada';
  launcher.setAttribute('aria-label', 'Abrir Jornada DevPilot');

  const panel = document.createElement('aside');
  panel.id = 'devpilot-quest-panel';
  panel.setAttribute('aria-hidden', 'true');
  panel.innerHTML = '<div class="quest-loading">Carregando jornada...</div>';

  document.body.append(launcher, panel);

  async function action(path) {
    try {
      await api(path, {method: 'POST', body: '{}'});
      await render();
    } catch (error) {
      const box = panel.querySelector('.quest-error');
      if (box) box.textContent = error.message;
    }
  }

  async function render() {
    try {
      const [profile, missions] = await Promise.all([api('/api/quests/me'), api('/api/quests/missions')]);
      const rewards = profile.rewards || {};
      const missionHtml = missions.length ? missions.map(mission => {
        const assignedToMe = mission.user_id === profile.user_id;
        const canAccept = !mission.user_id && mission.status !== 'completed';
        const canComplete = assignedToMe && mission.status !== 'completed';
        return `<article class="quest-mission" data-risk="${mission.risk_level}">
          <div class="quest-mission-head"><strong>${escapeHtml(mission.title)}</strong><span>${escapeHtml(mission.risk_label)}</span></div>
          <p>${escapeHtml(mission.description)}</p>
          <div class="quest-reward">+${mission.reward.xp} XP · ⭐ ${mission.reward.stars} · 🌙 ${mission.reward.moons} · ⚔ ${mission.reward.swords}</div>
          <div class="quest-actions">
            ${canAccept ? `<button data-accept="${mission.id}">Aceitar missão</button>` : ''}
            ${canComplete ? `<button data-complete="${mission.id}">Validar conclusão</button>` : ''}
            ${mission.status === 'completed' ? '<span class="quest-done">Concluída ✓</span>' : ''}
          </div>
        </article>`;
      }).join('') : '<div class="quest-empty">Ainda não há missões. Elas são criadas a partir de tarefas reais do projeto.</div>';

      panel.innerHTML = `<header class="quest-header">
        <div><span class="quest-kicker">DEV PILOT QUEST ENGINE</span><h2>Jornada do Desenvolvimento</h2></div>
        <button id="quest-close" type="button" aria-label="Fechar">×</button>
      </header>
      <section class="quest-profile">
        <div><span>Nível ${profile.level}</span><strong>${escapeHtml(profile.rank)}</strong></div>
        <div class="quest-xp">${profile.xp} XP</div>
        <div class="quest-trophies"><span>⭐ ${rewards.stars || 0}</span><span>🌙 ${rewards.moons || 0}</span><span>⚔ ${rewards.swords || 0}</span></div>
      </section>
      <p class="quest-security">🔐 ${escapeHtml(profile.security.message)}</p>
      <div class="quest-error" role="alert"></div>
      <section class="quest-missions"><h3>Problemas reais</h3>${missionHtml}</section>`;

      panel.querySelector('#quest-close').onclick = closePanel;
      panel.querySelectorAll('[data-accept]').forEach(button => button.onclick = () => action(`/api/quests/missions/${button.dataset.accept}/accept`));
      panel.querySelectorAll('[data-complete]').forEach(button => button.onclick = () => action(`/api/quests/missions/${button.dataset.complete}/complete`));
    } catch (error) {
      panel.innerHTML = `<div class="quest-error quest-fatal">${escapeHtml(error.message)}</div>`;
    }
  }

  function openPanel() {
    panel.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
    render();
  }

  function closePanel() {
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
  }

  launcher.onclick = openPanel;
})();
