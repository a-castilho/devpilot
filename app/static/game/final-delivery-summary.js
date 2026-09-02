/* DevPilot Build Game final delivery summary: show what the mission actually produced. */
(() => {
  'use strict';

  const GAME_MARKER = '[DEVPILOT_BUILD_GAME_V1]';
  const VERIFIER_MARKER = '[DEVPILOT_DELIVERY_VERIFIER_V1]';
  const PROJECT_KEY = 'devpilot-build-game-project';
  const MISSION_KEY = 'devpilot-build-game-mission';

  const escapeHtml = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const promptValue = (task, label) => {
    const escaped = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = String(task?.prompt || '').match(new RegExp(`^${escaped}:\\s*(.+)$`, 'mi'));
    return match?.[1]?.trim() || '';
  };

  const phaseFromTask = task => Number(promptValue(task, 'FASE').split('/')[0]) || 0;
  const missionFromTask = task => promptValue(task, 'PARTIDA');
  const isGameTask = task => String(task?.prompt || '').includes(GAME_MARKER);
  const isVerifier = task => String(task?.prompt || '').includes(VERIFIER_MARKER) || String(task?.title || '').startsWith('[Jogo] Gate');
  const normalize = value => String(value || '').trim().toLowerCase().replaceAll(' ', '_');

  const styles = () => {
    if (document.querySelector('#game-final-summary-style')) return;
    const style = document.createElement('style');
    style.id = 'game-final-summary-style';
    style.textContent = `
      .game-final-summary{display:grid;gap:12px;margin-top:14px;padding:15px;border:1px solid rgba(139,233,253,.22);border-radius:14px;background:rgba(4,14,26,.72)}
      .game-final-summary h4{margin:0;font-size:1rem}.game-final-summary p{margin:0;color:var(--muted,#9eacc2)}
      .game-final-summary-grid{display:grid;gap:8px}.game-final-summary-item{padding:10px 12px;border:1px solid rgba(255,255,255,.08);border-radius:10px;background:rgba(255,255,255,.025)}
      .game-final-summary-item strong{display:block;margin-bottom:4px}.game-final-summary-meta{font-size:.76rem;color:var(--muted,#9eacc2)}
      .game-final-summary-ok{color:#72efc5}.game-final-summary-pending{color:#ffc56e}.game-final-summary-url{overflow-wrap:anywhere;color:#8be9fd}
    `;
    document.head.appendChild(style);
  };

  const ensureHost = panel => {
    let host = panel.querySelector('.game-final-summary');
    if (!host) {
      host = document.createElement('section');
      host.className = 'game-final-summary';
      panel.appendChild(host);
    }
    return host;
  };

  const phaseRows = tasks => {
    const rows = [];
    for (let phase = 1; phase <= 7; phase += 1) {
      const phaseTasks = tasks.filter(task => phaseFromTask(task) === phase);
      const implementation = phaseTasks.find(task => !isVerifier(task));
      const verifier = phaseTasks.find(task => isVerifier(task));
      const verified = normalize(verifier?.status) === 'completed';
      rows.push({phase, implementation, verifier, verified});
    }
    return rows;
  };

  const render = (panel, tasks, delivery) => {
    styles();
    const host = ensureHost(panel);
    const first = tasks.find(task => promptValue(task, 'OBJETIVO'));
    const goal = promptValue(first, 'OBJETIVO') || 'Objetivo da partida';
    const rows = phaseRows(tasks);
    const checks = Array.isArray(delivery?.checks) ? delivery.checks : [];
    const url = String(delivery?.url || '').trim();

    host.innerHTML = `
      <span class="eyebrow">📦 O QUE FOI ENTREGUE</span>
      <h4>${escapeHtml(goal)}</h4>
      <p>Resumo gerado pelo próprio sistema a partir das tarefas e verificações desta partida.</p>
      <div class="game-final-summary-grid">
        ${rows.map(row => `
          <div class="game-final-summary-item">
            <strong>Fase ${row.phase}: ${escapeHtml(row.implementation?.title || 'sem tarefa registrada')}</strong>
            <span class="game-final-summary-meta ${row.verified ? 'game-final-summary-ok' : 'game-final-summary-pending'}">
              ${row.verified ? '✓ entrega verificada' : '• verificação pendente'}
            </span>
          </div>
        `).join('')}
      </div>
      ${checks.length ? `
        <div class="game-final-summary-grid">
          ${checks.map(check => `
            <div class="game-final-summary-item">
              <strong>${escapeHtml(check.name || check.provider || 'verificação')}</strong>
              <span class="game-final-summary-meta ${check.ok ? 'game-final-summary-ok' : 'game-final-summary-pending'}">
                ${check.ok ? '✓ aprovado' : '• pendente'}${check.status_code ? ` · HTTP ${escapeHtml(check.status_code)}` : ''}
              </span>
            </div>
          `).join('')}
        </div>
      ` : ''}
      ${url ? `<div class="game-final-summary-item"><strong>URL entregue</strong><a class="game-final-summary-url" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a></div>` : ''}
    `;
  };

  const hydrate = async panel => {
    if (panel.dataset.gameFinalSummaryLoading === '1') return;
    const projectId = String(localStorage.getItem(PROJECT_KEY) || '').trim();
    const missionId = String(localStorage.getItem(MISSION_KEY) || '').trim();
    if (!projectId || !missionId || typeof api !== 'function') return;
    panel.dataset.gameFinalSummaryLoading = '1';
    try {
      const [allTasks, delivery] = await Promise.all([
        api(`/tasks?project_id=${encodeURIComponent(projectId)}&limit=500`),
        api(`/projects/${encodeURIComponent(projectId)}/delivery`),
      ]);
      const tasks = (Array.isArray(allTasks) ? allTasks : [])
        .filter(task => isGameTask(task) && missionFromTask(task) === missionId)
        .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
      render(panel, tasks, delivery || {});
    } catch (error) {
      const host = ensureHost(panel);
      host.innerHTML = `<span class="eyebrow">📦 ENTREGA</span><p>Não foi possível carregar o resumo agora: ${escapeHtml(error?.message || 'erro desconhecido')}.</p>`;
    } finally {
      panel.dataset.gameFinalSummaryLoading = '0';
    }
  };

  const scan = () => {
    const panel = document.querySelector('#build-game-view .build-game-victory');
    if (!panel || panel.dataset.gameFinalSummaryBound === '1') return;
    panel.dataset.gameFinalSummaryBound = '1';
    void hydrate(panel);
  };

  const boot = () => {
    scan();
    const root = document.querySelector('#build-game-view') || document.body;
    if (!root || root.dataset.gameFinalSummaryObserved === '1') return;
    root.dataset.gameFinalSummaryObserved = '1';
    new MutationObserver(scan).observe(root, {childList: true, subtree: true});
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once: true});
  else boot();
  window.setTimeout(boot, 700);
})();
