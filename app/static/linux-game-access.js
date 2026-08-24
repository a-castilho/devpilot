(() => {
  'use strict';

  const token = () => localStorage.getItem('devpilot-token') || '';
  if (!token()) return;

  const apiRequest = async (path, options = {}) => {
    const response = await fetch(path, {
      ...options,
      headers: {
        Authorization: `Bearer ${token()}`,
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`;
      throw new Error(detail);
    }
    return data;
  };

  const escapeHtml = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const cleanOutput = value => String(value || '')
    .replace(/\u001b\][^\u0007]*(?:\u0007|\u001b\\)/g, '')
    .replace(/\u001b\[[0-?]*[ -\/]*[@-~]/g, '')
    .replace(/\r/g, '')
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, '');

  const ensureStyle = () => {
    if (document.querySelector('#linux-game-access-style')) return;
    const style = document.createElement('style');
    style.id = 'linux-game-access-style';
    style.textContent = `
      .linux-game-access{display:grid;gap:10px;padding:14px 16px;border:1px solid rgba(255,205,64,.28);border-radius:16px;background:linear-gradient(135deg,rgba(69,52,8,.27),rgba(9,22,34,.96))}
      .linux-game-access.unlocked{border-color:rgba(72,220,157,.38);background:linear-gradient(135deg,rgba(28,95,70,.25),rgba(9,22,34,.96))}
      .linux-game-access.admin{border-color:rgba(95,224,255,.38);background:linear-gradient(135deg,rgba(20,73,98,.3),rgba(9,22,34,.96))}
      .linux-game-access-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap}
      .linux-game-access h3{margin:2px 0 4px}.linux-game-access p{margin:0;color:var(--muted);font-size:12px}
      .linux-game-badge{display:inline-flex;align-items:center;gap:6px;padding:5px 9px;border:1px solid currentColor;border-radius:999px;font-size:10px;font-weight:900;letter-spacing:.06em;color:#ffd34d}
      .linux-game-access.unlocked .linux-game-badge{color:#6ce5af}.linux-game-access.admin .linux-game-badge{color:#6fe5ff}
      .linux-game-meter{height:8px;overflow:hidden;border-radius:999px;background:rgba(255,255,255,.07)}
      .linux-game-meter i{display:block;height:100%;background:linear-gradient(90deg,#ffd34d,#6ce5af);border-radius:inherit}
      .linux-game-meta{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap;font-size:11px;color:var(--muted)}
      .linux-game-admin-sessions{display:grid;gap:8px}
      .linux-admin-session{display:grid;gap:8px;padding:11px;border:1px solid var(--line);border-radius:12px;background:rgba(0,0,0,.18)}
      .linux-admin-session-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;flex-wrap:wrap}
      .linux-admin-session-head strong{font-size:12px}.linux-admin-session-head small{display:block;margin-top:3px;color:var(--muted);overflow-wrap:anywhere}
      .linux-admin-session-actions{display:flex;gap:7px;flex-wrap:wrap}.linux-admin-session-actions button{padding:7px 10px}
      .linux-admin-command{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:7px}.linux-admin-command input{min-width:0}
      .linux-admin-output{display:none;max-height:220px;overflow:auto;margin:0;padding:10px;border-radius:10px;background:#04080d;color:#d8f7dd;font:11px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}.linux-admin-output.open{display:block}
      .linux-game-locked #linux-terminal-start,.linux-game-locked #linux-terminal-send,.linux-game-locked #linux-terminal-input,.linux-game-locked [data-linux-command],.linux-game-locked #linux-beginner-coach{pointer-events:none;opacity:.42}
      @media(max-width:620px){.linux-admin-command{grid-template-columns:1fr}.linux-admin-session-actions button{flex:1}.linux-game-meta{align-items:flex-start;flex-direction:column}}
    `;
    document.head.appendChild(style);
  };

  const linuxView = () => document.querySelector('#linux-view');

  const ensureCard = () => {
    const view = linuxView();
    const shell = view?.querySelector('.linux-shell');
    if (!view || !shell) return null;
    let card = view.querySelector('#linux-game-access');
    if (!card) {
      card = document.createElement('section');
      card.id = 'linux-game-access';
      card.className = 'linux-game-access';
      const head = shell.querySelector('.linux-simple-head');
      if (head) head.insertAdjacentElement('afterend', card);
      else shell.prepend(card);
    }
    return card;
  };

  const applyTerminalLock = locked => {
    const view = linuxView();
    if (!view) return;
    view.classList.toggle('linux-game-locked', Boolean(locked));
    view.querySelectorAll('#linux-terminal-start,#linux-terminal-send,#linux-terminal-input,[data-linux-command]').forEach(element => {
      if (locked) element.setAttribute('aria-disabled', 'true');
      else element.removeAttribute('aria-disabled');
    });
  };

  const openGame = () => {
    const game = document.querySelector('.nav[data-view="build-game"]');
    if (game) game.click();
  };

  const renderRegular = (card, profile) => {
    const bonus = profile.terminal_bonus || {};
    const unlocked = Boolean(bonus.unlocked);
    const eligible = Boolean(bonus.eligible);
    const earned = Number(bonus.earned_xp || 0);
    const required = Math.max(1, Number(bonus.required_xp || 360));
    const percent = Math.max(0, Math.min(100, Math.round(earned / required * 100)));
    card.className = `linux-game-access ${unlocked ? 'unlocked' : ''}`;

    if (unlocked) {
      card.innerHTML = `
        <div class="linux-game-access-head">
          <div><span class="eyebrow">🎁 BÔNUS DO JOGO</span><h3>Terminal Linux desbloqueado</h3><p>Seu prêmio abre um workspace Linux isolado somente para o seu usuário. Outros jogadores não acessam sua sessão.</p></div>
          <span class="linux-game-badge">LIBERADO · ${escapeHtml(earned)} XP</span>
        </div>
        <div class="linux-game-meta"><span>Escopo: workspace Linux próprio e isolado</span><span>Fases concluídas: ${escapeHtml((bonus.completed_phases || []).join(', ') || '—')}</span></div>`;
      applyTerminalLock(false);
      return;
    }

    card.innerHTML = `
      <div class="linux-game-access-head">
        <div><span class="eyebrow">🎁 BÔNUS DO JOGO</span><h3>${eligible ? 'Terminal Linux ainda bloqueado' : 'Terminal Linux indisponível para este perfil'}</h3><p>${escapeHtml(bonus.message || 'Conclua as fases exigidas do Jogo de construção para liberar o terminal.')}</p></div>
        <span class="linux-game-badge">${eligible ? `${escapeHtml(earned)}/${escapeHtml(required)} XP` : 'SOMENTE LEITURA'}</span>
      </div>
      ${eligible ? `<div class="linux-game-meter" aria-label="${percent}% do bônus"><i style="width:${percent}%"></i></div>` : ''}
      <div class="linux-game-meta">
        <span>${eligible ? 'Desbloqueio: fases 1, 2 e 3 concluídas · 360 XP' : 'VIEWER não recebe shell executável.'}</span>
        ${eligible ? '<button type="button" class="primary" data-linux-game-open>Ir para o Jogo</button>' : ''}
      </div>`;
    card.querySelector('[data-linux-game-open]')?.addEventListener('click', openGame);
    applyTerminalLock(true);
  };

  const sessionLabel = session => {
    const actor = String(session.actor || 'usuário');
    const linuxUser = String(session.linux_user || 'linux');
    return `${actor} · ${linuxUser}`;
  };

  const renderAdminSessions = (host, sessions = []) => {
    if (!sessions.length) {
      host.innerHTML = '<div class="empty">Nenhuma sessão Linux ativa agora.</div>';
      return;
    }
    host.innerHTML = sessions.map(session => `
      <article class="linux-admin-session" data-linux-admin-session="${escapeHtml(session.id)}">
        <div class="linux-admin-session-head">
          <div><strong>${escapeHtml(sessionLabel(session))}</strong><small>${escapeHtml(session.cwd || '—')} · ${escapeHtml(session.state || 'running')}</small></div>
          <div class="linux-admin-session-actions">
            <button type="button" class="ghost" data-linux-admin-action="output">Ver saída</button>
            <button type="button" class="ghost" data-linux-admin-action="close">Encerrar</button>
          </div>
        </div>
        <div class="linux-admin-command">
          <input maxlength="100000" placeholder="Executar comando nesta sessão…" data-linux-admin-command>
          <button type="button" class="primary" data-linux-admin-action="run">Executar</button>
        </div>
        <pre class="linux-admin-output" data-linux-admin-output></pre>
      </article>`).join('');
  };

  const refreshAdminSessions = async () => {
    const host = document.querySelector('#linux-admin-sessions');
    if (!host) return;
    try {
      const data = await apiRequest('/api/linux/terminal/sessions');
      renderAdminSessions(host, data.items || []);
    } catch (error) {
      host.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
    }
  };

  const readSessionOutput = async (sessionId, article) => {
    const output = article.querySelector('[data-linux-admin-output]');
    if (!output) return;
    output.classList.add('open');
    output.textContent = 'Carregando saída…';
    try {
      const data = await apiRequest(`/api/linux/terminal/sessions/${encodeURIComponent(sessionId)}/output?after=0`);
      output.textContent = cleanOutput((data.chunks || []).map(chunk => chunk.text || '').join('')) || 'Sem saída registrada.';
      output.scrollTop = output.scrollHeight;
    } catch (error) {
      output.textContent = error.message;
    }
  };

  const runAdminCommand = async (sessionId, article) => {
    const input = article.querySelector('[data-linux-admin-command]');
    const command = String(input?.value || '').trim();
    if (!command) return;
    try {
      await apiRequest(`/api/linux/terminal/sessions/${encodeURIComponent(sessionId)}/input`, {
        method: 'POST',
        body: JSON.stringify({data: `${command}\n`}),
      });
      if (input) input.value = '';
      window.setTimeout(() => readSessionOutput(sessionId, article), 120);
    } catch (error) {
      const output = article.querySelector('[data-linux-admin-output]');
      if (output) {
        output.classList.add('open');
        output.textContent = error.message;
      }
    }
  };

  const closeAdminSession = async sessionId => {
    await apiRequest(`/api/linux/terminal/sessions/${encodeURIComponent(sessionId)}`, {method: 'DELETE'});
    await refreshAdminSessions();
  };

  const bindAdmin = card => {
    if (card.dataset.linuxAdminBound === '1') return;
    card.dataset.linuxAdminBound = '1';
    card.addEventListener('click', async event => {
      const button = event.target.closest('[data-linux-admin-action]');
      if (!button) return;
      const article = button.closest('[data-linux-admin-session]');
      const sessionId = article?.dataset.linuxAdminSession;
      if (!article || !sessionId) return;
      button.disabled = true;
      try {
        if (button.dataset.linuxAdminAction === 'output') await readSessionOutput(sessionId, article);
        else if (button.dataset.linuxAdminAction === 'run') await runAdminCommand(sessionId, article);
        else if (button.dataset.linuxAdminAction === 'close') await closeAdminSession(sessionId);
      } catch (error) {
        const output = article.querySelector('[data-linux-admin-output]');
        if (output) {
          output.classList.add('open');
          output.textContent = error.message;
        }
      } finally {
        if (button.isConnected) button.disabled = false;
      }
    });
  };

  const renderAdmin = card => {
    card.className = 'linux-game-access admin unlocked';
    card.innerHTML = `
      <div class="linux-game-access-head">
        <div><span class="eyebrow">🛡️ SUPER ADMIN</span><h3>Acesso total aos terminais DevPilot</h3><p>Você pode ver, operar e encerrar qualquer sessão Linux gerenciada pelo DevPilot. As ações ficam vinculadas ao ator da sessão e são auditadas.</p></div>
        <span class="linux-game-badge">ACESSO TOTAL</span>
      </div>
      <div class="linux-game-meta"><span>Seu próprio terminal continua usando a conta Linux dedicada do DevPilot.</span><button type="button" class="ghost" id="linux-admin-refresh">Atualizar sessões</button></div>
      <div class="linux-game-admin-sessions" id="linux-admin-sessions"><div class="empty">Consultando sessões…</div></div>`;
    applyTerminalLock(false);
    bindAdmin(card);
    card.querySelector('#linux-admin-refresh')?.addEventListener('click', refreshAdminSessions);
    void refreshAdminSessions();
  };

  let lastRole = '';
  let lastUnlocked = null;
  let statusTimer = null;
  let adminTimer = null;

  const refresh = async () => {
    const card = ensureCard();
    if (!card) return false;
    try {
      const status = await apiRequest('/api/linux/status');
      const profile = status.profile || {};
      const role = String(profile.role || '').toUpperCase();
      const unlocked = Boolean(profile.terminal_bonus?.unlocked);
      const changed = role !== lastRole || unlocked !== lastUnlocked;
      lastRole = role;
      lastUnlocked = unlocked;
      if (role === 'SUPER_ADMIN') {
        if (changed || !card.querySelector('#linux-admin-sessions')) renderAdmin(card);
      } else {
        renderRegular(card, profile);
      }
      return true;
    } catch (error) {
      card.className = 'linux-game-access';
      card.innerHTML = `<div class="linux-game-access-head"><div><span class="eyebrow">LINUX</span><h3>Não foi possível validar o acesso</h3><p>${escapeHtml(error.message)}</p></div></div>`;
      applyTerminalLock(true);
      return false;
    }
  };

  const startTimers = () => {
    if (!statusTimer) statusTimer = window.setInterval(refresh, 2500);
    if (!adminTimer) adminTimer = window.setInterval(() => {
      const view = linuxView();
      if (lastRole === 'SUPER_ADMIN' && view?.classList.contains('active')) void refreshAdminSessions();
    }, 5000);
  };

  const boot = async () => {
    ensureStyle();
    const ready = await refresh();
    if (!ready && !linuxView()) {
      window.setTimeout(boot, 350);
      return;
    }
    startTimers();
  };

  document.addEventListener('click', event => {
    if (event.target.closest?.('.nav[data-view="linux"],.nav[data-linux-view="1"]')) {
      window.setTimeout(refresh, 80);
    }
  }, true);

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) void refresh();
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else void boot();
})();
