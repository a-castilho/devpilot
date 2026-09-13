(() => {
  'use strict';

  if (window.__devpilotSuperAdminDiagnosticsV2) return;
  window.__devpilotSuperAdminDiagnosticsV2 = true;

  const ROLE = 'SUPER_ADMIN';
  const FAILURE_STATUSES = new Set(['failed', 'blocked']);
  const isSuperAdmin = () => String((typeof state !== 'undefined' && state.currentUser?.role) || '').toUpperCase() === ROLE;
  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

  function normalizeStatus(value) {
    const normalized = String(value || '').split('.').pop().trim().toLowerCase().replaceAll(' ', '_');
    return ({
      falhou: 'failed',
      falha: 'failed',
      bloqueada: 'blocked',
      bloqueado: 'blocked',
    })[normalized] || normalized;
  }

  function ensureStyles() {
    if (document.getElementById('super-admin-diagnostics-v2-style')) return;
    const style = document.createElement('style');
    style.id = 'super-admin-diagnostics-v2-style';
    style.textContent = `
      .repair-shell{display:grid;gap:16px}.repair-hero{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:18px;align-items:center;padding:20px;border:1px solid rgba(58,209,196,.24);border-radius:20px;background:linear-gradient(135deg,rgba(12,45,65,.95),rgba(5,18,31,.98))}.repair-hero h2{margin:4px 0 8px;font-size:clamp(1.55rem,4vw,2.35rem)}.repair-hero p{margin:0;color:#9db0c1;max-width:760px;line-height:1.55}.repair-main{min-height:56px;padding:12px 20px;border:0;border-radius:13px;background:linear-gradient(135deg,#52ead7,#43bdf5);color:#03131c;font-weight:950;cursor:pointer}.repair-main:disabled{opacity:.55;cursor:wait}.repair-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.repair-metric{padding:14px;border:1px solid #213a50;border-radius:14px;background:#071827}.repair-metric small{display:block;color:#7890a4;font-weight:800}.repair-metric strong{display:block;margin-top:5px;color:#fff;font-size:1.2rem}.repair-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(300px,.85fr);gap:14px}.repair-checks,.repair-actions{display:grid;gap:9px}.repair-check{display:grid;grid-template-columns:28px minmax(0,1fr);gap:10px;padding:12px;border:1px solid #21384d;border-radius:12px;background:#081827}.repair-check i{display:grid;place-items:center;width:26px;height:26px;border-radius:999px;font-style:normal;font-weight:950;background:#ffffff0b}.repair-check.ok i{color:#59e7c1}.repair-check.fail i{color:#ff6f7f}.repair-check small{display:block;margin-top:3px;color:#8195a8}.repair-action{width:100%;min-height:52px;padding:11px;border:1px solid #28506c;border-radius:12px;background:#0a2134;color:#eaf4fb;font-weight:900;text-align:left;cursor:pointer}.repair-action span{display:block;margin-top:3px;color:#88a0b4;font-size:.78rem;font-weight:600}.repair-log{max-height:280px;overflow:auto;margin:0;padding:12px;border-radius:12px;background:#04111d;color:#9eb4c6;font-size:.78rem;line-height:1.45;white-space:pre-wrap;overflow-wrap:anywhere}.repair-status{padding:11px 13px;border-radius:12px;background:#0b2434;color:#acd0d8}.repair-status.success{border:1px solid rgba(71,225,181,.32);color:#8ff0cf}.repair-status.fail{border:1px solid rgba(255,101,120,.34);color:#ffc1c9}.local-test-compact{display:flex;gap:8px;flex-wrap:wrap}.local-test-compact button{min-height:42px}
      .execution-repair-diagnostic{white-space:normal!important;line-height:1.15!important;text-align:center!important}
      @media(max-width:850px){.repair-hero,.repair-grid{grid-template-columns:1fr}.repair-main{width:100%}.repair-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:520px){.repair-metrics{grid-template-columns:1fr}.repair-hero{padding:16px}.repair-grid{gap:10px}}
      @media(max-width:900px){
        .mobile-simple-sheet{left:8px!important;right:8px!important;width:auto!important;max-width:none!important;max-height:min(78dvh,680px)!important;overflow:hidden!important}
        .mobile-simple-list{display:grid!important;grid-template-columns:minmax(0,1fr)!important;align-items:stretch!important;gap:5px!important;width:100%!important;min-width:0!important;padding:10px!important;overflow-y:auto!important;overflow-x:hidden!important;box-sizing:border-box!important}
        .mobile-simple-row{display:grid!important;grid-template-columns:38px minmax(0,1fr) 24px!important;align-items:center!important;gap:10px!important;width:100%!important;min-width:0!important;max-width:none!important;min-height:54px!important;height:auto!important;margin:0!important;padding:8px 12px!important;box-sizing:border-box!important;text-align:left!important;white-space:normal!important}
        .mobile-simple-row>.mobile-simple-icon{display:grid!important;width:36px!important;min-width:36px!important;height:36px!important;place-items:center!important}
        .mobile-simple-row>span:nth-child(2){display:block!important;min-width:0!important;width:auto!important;max-width:100%!important;white-space:normal!important;word-break:normal!important;overflow-wrap:break-word!important;line-height:1.25!important}
        .mobile-simple-row>.mobile-simple-arrow{display:block!important;width:24px!important;min-width:24px!important;text-align:right!important}
        .tasks-v9-actions .execution-repair-diagnostic{min-height:44px!important;padding:8px 10px!important}
      }
    `;
    document.head.appendChild(style);
  }

  function openView(button, section, title) {
    if (!isSuperAdmin()) return window.toast?.('Acesso exclusivo do Super Admin');
    document.querySelectorAll('.view').forEach(view => {
      const active = view === section;
      view.classList.toggle('active', active);
      view.hidden = !active;
      view.setAttribute('aria-hidden', active ? 'false' : 'true');
    });
    section.hidden = false;
    section.setAttribute('aria-hidden', 'false');
    document.querySelectorAll('.nav').forEach(item => item.classList.toggle('active', item === button));
    button.setAttribute('aria-current', 'page');
    document.documentElement.dataset.devpilotView = 'pipeline-repair';
    const heading = document.getElementById('page-title');
    if (heading) heading.textContent = title;
  }

  function renderRepair(data = {}) {
    const queue = data.queue || {};
    const metrics = document.getElementById('repair-metrics');
    const checks = document.getElementById('repair-checks');
    const log = document.getElementById('repair-log');
    const status = document.getElementById('repair-status');
    if (!metrics || !checks || !log || !status) return;

    metrics.innerHTML = `
      <div class="repair-metric"><small>NA FILA</small><strong>${Number(queue.queued || 0)}</strong></div>
      <div class="repair-metric"><small>EXECUTANDO</small><strong>${Number(queue.running || 0)}</strong></div>
      <div class="repair-metric"><small>COM FALHA</small><strong>${Number(queue.failed || 0)}</strong></div>
      <div class="repair-metric"><small>ÚLTIMO RUN</small><strong>${esc(data.latest_run?.status || '—')}</strong></div>`;

    const items = Array.isArray(data.checks) ? data.checks : [];
    checks.innerHTML = items.map(item => `
      <div class="repair-check ${item.ok ? 'ok' : 'fail'}"><i>${item.ok ? '✓' : '!'}</i><div><strong>${esc(item.label)}</strong><small>${esc(item.detail || '')}</small></div></div>
    `).join('') || '<div class="empty">Sem diagnóstico disponível.</div>';

    const repair = data.latest_repair || {};
    log.textContent = String(repair.detail || 'Nenhum reparo executado ainda.');
    const repairStatus = String(repair.status || 'ready').toLowerCase();
    status.className = `repair-status ${repairStatus === 'completed' ? 'success' : repairStatus === 'failed' ? 'fail' : ''}`;
    status.textContent = repairStatus === 'completed' ? 'Último reparo concluído' : repairStatus === 'failed' ? 'Último reparo falhou' : repairStatus === 'pending' || repairStatus === 'running' ? 'Reparo em andamento' : 'Pronto para analisar';
  }

  async function loadRepair() {
    if (!isSuperAdmin()) return;
    try { renderRepair(await api('/admin/pipeline-repair')); }
    catch (error) { window.toast?.(error?.message || 'Falha ao carregar diagnóstico da esteira.'); }
  }

  async function runRepair() {
    if (!isSuperAdmin()) return;
    const button = document.getElementById('pipeline-repair-run');
    if (button) { button.disabled = true; button.textContent = 'Executando reparo…'; }
    try {
      const accepted = await api('/admin/pipeline-repair/run', {method:'POST'});
      window.toast?.(`Reparo enviado: ${accepted.action_id || 'fila do host'}`);
      await loadRepair();
      let attempts = 0;
      const poll = window.setInterval(async () => {
        attempts += 1;
        try {
          const data = await api('/admin/pipeline-repair');
          renderRepair(data);
          const value = String(data.latest_repair?.status || '').toLowerCase();
          if (['completed','failed'].includes(value) || attempts >= 20) {
            window.clearInterval(poll);
            if (button?.isConnected) { button.disabled = false; button.textContent = '▶ Executar reparo completo'; }
          }
        } catch (_) {}
      }, 3000);
    } catch (error) {
      window.toast?.(error?.message || 'Falha ao solicitar reparo.');
      if (button?.isConnected) { button.disabled = false; button.textContent = '▶ Executar reparo completo'; }
    }
  }

  async function runLocalTest() {
    const button = document.getElementById('local-test-compact-run');
    if (button) { button.disabled = true; button.textContent = 'Testando…'; }
    try {
      const result = await api('/admin/local-test/run', {method:'POST'});
      window.toast?.(result.ok ? `Teste local aprovado ${result.passed}/${result.total}` : `Teste local com atenção ${result.passed}/${result.total}`);
    } catch (error) { window.toast?.(error?.message || 'Falha no teste local.'); }
    finally { if (button?.isConnected) { button.disabled = false; button.textContent = 'Executar teste local/mobile'; } }
  }

  function taskForRow(taskId) {
    const tasks = typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks : [];
    return tasks.find(item => String(item?.id || '') === String(taskId || '')) || null;
  }

  function statusForRow(row, task) {
    const taskStatus = normalizeStatus(task?.status);
    if (taskStatus) return taskStatus;
    const chip = row.querySelector('.tasks-v9-status');
    if (!chip) return '';
    if (chip.classList.contains('failed')) return 'failed';
    if (chip.classList.contains('blocked')) return 'blocked';
    return normalizeStatus(chip.textContent);
  }

  function decorateExecutionRepairButtons() {
    if (!isSuperAdmin()) return;
    document.querySelectorAll('#tasks-table .tasks-v9-row[data-task-id], #tasks-table .task-main-row[data-task-id]').forEach(row => {
      const taskId = String(row.dataset.taskId || '').trim();
      if (!taskId) return;
      const task = taskForRow(taskId);
      const source = String(task?.source || '').trim().toLowerCase();
      const failed = source !== 'failure-recovery' && FAILURE_STATUSES.has(statusForRow(row, task));
      const actions = row.querySelector('.tasks-v9-actions, .task-actions') || row.lastElementChild;
      const existing = actions?.querySelector('.task-recovery-action');

      if (!failed) {
        if (existing?.classList.contains('execution-repair-diagnostic')) existing.remove();
        return;
      }
      if (!actions) return;

      const button = existing || document.createElement('button');
      button.type = 'button';
      button.classList.add('task-recovery-action', 'execution-repair-diagnostic');
      button.dataset.taskRecovery = taskId;
      button.textContent = 'Diagnóstico / reparo';
      button.title = 'Analisar a causa, executar autocorreção e retestar esta execução';
      if (!existing) actions.prepend(button);
    });
  }

  function syncMobileMenuAfterAdminNavChange() {
    document.dispatchEvent(new CustomEvent('devpilot:page-ready', {detail:{source:'super-admin-diagnostics'}}));
  }

  function ensurePanel() {
    if (!isSuperAdmin()) return;
    ensureStyles();
    if (document.getElementById('pipeline-repair-view')) {
      decorateExecutionRepairButtons();
      return;
    }
    const nav = document.querySelector('.sidebar nav');
    const main = document.querySelector('main');
    if (!nav || !main) return;

    const button = document.createElement('button');
    button.className = 'nav';
    button.type = 'button';
    button.dataset.view = 'pipeline-repair';
    button.dataset.pipelineRepairNav = '1';
    button.dataset.superAdmin = 'true';
    button.textContent = '🛠 Reparo & Diagnóstico';
    nav.appendChild(button);

    const section = document.createElement('section');
    section.className = 'view';
    section.id = 'pipeline-repair-view';
    section.innerHTML = `
      <div class="repair-shell">
        <section class="repair-hero">
          <div><span class="eyebrow">SUPER ADMIN · OPERAÇÃO CONTROLADA</span><h2>Reparo da Esteira</h2><p>Analisa fila, execuções e saúde do worker. O reparo é uma ação pré-definida: recria somente o worker, reconecta à rede Compose e valida DNS e PostgreSQL sem aceitar comandos livres.</p></div>
          <button class="repair-main" type="button" id="pipeline-repair-run">▶ Executar reparo completo</button>
        </section>
        <div id="repair-metrics" class="repair-metrics"></div>
        <div class="repair-grid">
          <article class="panel"><div class="panel-title"><div><span class="eyebrow">DIAGNÓSTICO</span><h3>Verificações</h3></div><button class="ghost" id="pipeline-repair-refresh" type="button">Atualizar análise</button></div><div id="repair-status" class="repair-status">Carregando…</div><div id="repair-checks" class="repair-checks" style="margin-top:12px"></div></article>
          <article class="panel"><div class="panel-title"><div><span class="eyebrow">RESULTADO TÉCNICO</span><h3>Último reparo</h3></div></div><pre id="repair-log" class="repair-log">Carregando…</pre><div class="repair-actions" style="margin-top:10px"><button class="repair-action" type="button" id="local-test-compact-run">Executar teste local/mobile<span>Valida API, assets e acesso pela rede local.</span></button></div></article>
        </div>
      </div>`;
    main.appendChild(section);
    button.addEventListener('click', () => { openView(button, section, 'Reparo & Diagnóstico'); void loadRepair(); });
    section.querySelector('#pipeline-repair-run')?.addEventListener('click', runRepair);
    section.querySelector('#pipeline-repair-refresh')?.addEventListener('click', loadRepair);
    section.querySelector('#local-test-compact-run')?.addEventListener('click', runLocalTest);
    syncMobileMenuAfterAdminNavChange();
    decorateExecutionRepairButtons();
  }

  const boot = () => {
    ensurePanel();
    window.setTimeout(ensurePanel, 700);
    window.setTimeout(ensurePanel, 1800);
    document.addEventListener('devpilot:page-ready', ensurePanel);
    document.addEventListener('devpilot:feature-ready', ensurePanel);
    document.addEventListener('devpilot:tasks-rendered', () => {
      decorateExecutionRepairButtons();
      window.setTimeout(decorateExecutionRepairButtons, 80);
    });
    document.addEventListener('devpilot:view-changed', event => {
      if (event.detail?.view !== 'tasks') return;
      window.setTimeout(decorateExecutionRepairButtons, 40);
      window.setTimeout(decorateExecutionRepairButtons, 240);
    });
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();
})();
