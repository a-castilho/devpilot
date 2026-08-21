(() => {
  const STYLE_ID = 'devpilot-consolidated-ui-styles';
  const CORRECTION_COMPLETE_AT = 0.86;
  const context = {taskId: null, runId: null, enhancing: false};

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      :root,html[data-workspace-tone="night"]{--workspace-glow:#12345455;--workspace-sidebar:#081321ee}
      html[data-workspace-tone="black"]{--bg:#000;--surface:#080808;--surface2:#111;--line:#292929;--workspace-glow:#0000;--workspace-sidebar:#050505f5}
      html[data-workspace-tone="graphite"]{--bg:#101214;--surface:#181b1f;--surface2:#22262b;--line:#353b43;--workspace-glow:#4a556822;--workspace-sidebar:#121519f2}
      html[data-workspace-tone="deep-blue"]{--bg:#050b18;--surface:#0a1425;--surface2:#10203a;--line:#203a5c;--workspace-glow:#194f8a4d;--workspace-sidebar:#07101ff2}
      body{background:radial-gradient(circle at 80% 0,var(--workspace-glow,#12345455),transparent 30%),var(--bg);transition:background-color .2s ease,color .2s ease}
      .sidebar{background:var(--workspace-sidebar,#081321ee)}
      .workspace-tone-picker{position:fixed;top:18px;right:18px;z-index:60;display:flex;align-items:center;gap:8px}
      .workspace-tone-toggle{width:44px;height:44px;padding:0;border:1px solid var(--line);border-radius:13px;background:var(--surface2);color:var(--text);cursor:pointer;box-shadow:0 12px 32px #0006}
      .workspace-tone-toggle:hover,.workspace-tone-toggle[aria-expanded="true"]{color:var(--cyan);border-color:var(--cyan)}
      .workspace-tone-menu{display:none;gap:8px;align-items:center;padding:8px;border:1px solid var(--line);border-radius:14px;background:var(--surface);box-shadow:0 16px 42px #0009}
      .workspace-tone-picker.open .workspace-tone-menu{display:flex}
      .workspace-tone-option{width:34px;height:34px;padding:0;border:2px solid transparent;border-radius:50%;cursor:pointer;box-shadow:inset 0 0 0 1px #ffffff24}
      .workspace-tone-option[data-tone="black"]{background:#000}.workspace-tone-option[data-tone="graphite"]{background:#171a1e}.workspace-tone-option[data-tone="night"]{background:#07111f}.workspace-tone-option[data-tone="deep-blue"]{background:#07142a}
      .workspace-tone-option[aria-pressed="true"]{border-color:var(--cyan);box-shadow:0 0 0 3px #35e5d126}

      html{scrollbar-width:thin;scrollbar-color:#31506a #081421}
      *{scrollbar-width:thin;scrollbar-color:#31506a transparent}
      *::-webkit-scrollbar{width:9px;height:9px}
      *::-webkit-scrollbar-track{background:rgba(8,20,33,.65);border-radius:999px}
      *::-webkit-scrollbar-thumb{background:linear-gradient(180deg,#254b63,#2d766f);border:2px solid rgba(8,20,33,.65);border-radius:999px}
      *::-webkit-scrollbar-thumb:hover{background:linear-gradient(180deg,#2d607e,#35a596)}
      *::-webkit-scrollbar-corner{background:transparent}

      #task-log-modal{width:min(1180px,calc(100vw - 28px));max-width:calc(100vw - 28px);max-height:min(92dvh,900px);overflow:hidden}
      #task-log-modal .task-log-modal-panel{width:100%;max-width:100%;min-width:0;max-height:min(92dvh,900px);overflow-y:auto;overflow-x:hidden;padding:28px;overscroll-behavior:contain;scrollbar-gutter:stable}
      .analysis-enhanced-layout{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(340px,.92fr);gap:16px;align-items:start;min-width:0}
      .analysis-enhanced-left{min-width:0;display:grid;gap:14px}
      .analysis-enhanced-left .task-client-card{margin:0;min-width:0;max-height:62vh;overflow:auto}
      .analysis-command-card,.analysis-proposal-card,.analysis-correction-card{min-width:0;padding:16px;border:1px solid #29445f;border-radius:14px;background:linear-gradient(145deg,#0d1d2e,#081522)}
      .analysis-command-card[hidden],.analysis-correction-card[hidden]{display:none}
      .analysis-command-head,.analysis-proposal-head,.analysis-correction-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}
      .analysis-command-head .eyebrow,.analysis-proposal-head .eyebrow{margin:0}
      .analysis-command-copy{padding:7px 11px;border:1px solid #345b82;border-radius:9px;background:#10283f;color:#dcecff;font:inherit;font-size:11px;font-weight:800;cursor:pointer}
      .analysis-command-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(120px,.35fr);gap:10px}
      .analysis-command-field{min-width:0;padding:10px 12px;border-radius:10px;background:#050d17}.analysis-command-field.wide{grid-column:1/-1}
      .analysis-command-label{display:block;margin-bottom:5px;color:#7f93aa;font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
      .analysis-command-value{display:block;color:#e8f2ff;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;line-height:1.45;white-space:pre-wrap;overflow-wrap:anywhere}
      .analysis-proposal-card{position:sticky;top:0}
      .analysis-proposal-head h3,.analysis-correction-head h3{margin:3px 0 0;color:#f4f8ff;font-size:16px}
      .analysis-review-badge{padding:5px 8px;border:1px solid #2b7b70;border-radius:999px;color:#65ead4;background:#12342f;font-size:9px;font-weight:850;white-space:nowrap}
      .analysis-price-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-bottom:14px}
      .analysis-price-item{padding:11px;border:1px solid #253e57;border-radius:10px;background:#081421}.analysis-price-item span{display:block;color:#8da3bc;font-size:9px;text-transform:uppercase;letter-spacing:.08em}.analysis-price-item strong{display:block;margin-top:5px;color:#edf8ff;font-size:15px;overflow-wrap:anywhere}.analysis-price-item.featured{border-color:#2e8f80;background:linear-gradient(145deg,#10332e,#0a2024)}.analysis-price-item.featured strong{color:#63edd7}
      .analysis-proposal-meta{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}.analysis-proposal-meta span{padding:6px 8px;border-radius:8px;background:#102337;color:#a9bfd5;font-size:10px}
      .analysis-proposal-phases{display:grid;gap:8px}.analysis-proposal-phase{display:grid;grid-template-columns:28px minmax(0,1fr) auto;gap:9px;align-items:start;padding:10px;border-top:1px solid #22384e}.analysis-proposal-phase b{display:grid;place-items:center;width:26px;height:26px;border-radius:8px;background:#164b4b;color:#62ead7;font-size:11px}.analysis-proposal-phase strong,.analysis-proposal-phase small{display:block}.analysis-proposal-phase small{margin-top:3px;color:#849bb4;line-height:1.35}.analysis-proposal-phase>strong{color:#dceafa;font-size:11px;white-space:nowrap}
      .analysis-proposal-note{margin:13px 0 0;color:#7890aa;font-size:10px;line-height:1.45}.analysis-proposal-actions{display:flex;justify-content:flex-end;margin-top:12px}.analysis-proposal-print{padding:8px 11px;font-size:11px}
      .analysis-correction-card{position:sticky;bottom:-1px;z-index:5;margin-top:16px;box-shadow:0 -14px 30px rgba(3,10,19,.52),0 14px 34px rgba(0,0,0,.24);backdrop-filter:blur(14px)}
      .analysis-correction-head{margin-bottom:9px}.analysis-correction-head p{margin:3px 0 0;color:#8fa4bd;font-size:11px;line-height:1.45}
      .analysis-correction-slider{--slide:0px;--pct:0%;position:relative;width:100%;height:58px;border:1px solid #2b8590;border-radius:999px;overflow:hidden;background:#071522;box-shadow:0 0 24px rgba(53,229,209,.08);touch-action:pan-y;user-select:none;-webkit-user-select:none}
      .analysis-correction-fill{position:absolute;inset:0 auto 0 0;width:var(--pct);background:linear-gradient(90deg,rgba(53,229,209,.48),rgba(72,185,248,.26));pointer-events:none}.analysis-correction-label{position:absolute;inset:0 62px 0 66px;display:flex;align-items:center;justify-content:center;color:#57ead8;font-size:12px;font-weight:900;pointer-events:none;white-space:nowrap}.analysis-correction-label::after{content:'✦';position:absolute;right:-40px;color:#43dfd1;font-size:16px}
      .analysis-correction-thumb{position:absolute;z-index:2;left:5px;top:5px;width:48px;height:48px;padding:0;border:0;border-radius:50%;display:grid;place-items:center;transform:translateX(var(--slide));background:linear-gradient(135deg,#39e6d2,#48b9f8);color:#06111b;box-shadow:0 7px 20px rgba(53,229,209,.28);font-size:0;cursor:grab;touch-action:none}.analysis-correction-thumb::before{content:'»';font-size:25px;font-weight:950}.analysis-correction-slider.created{border-color:#38dd8a;background:#09251c}.analysis-correction-slider.created .analysis-correction-fill{width:100%!important;background:linear-gradient(90deg,#24b979,#38dd8a)}.analysis-correction-slider.created .analysis-correction-label{color:#d9ffea}.analysis-correction-slider.created .analysis-correction-label::after{content:'✓'}.analysis-correction-slider.created .analysis-correction-thumb{background:linear-gradient(135deg,#39e391,#20b86e)}.analysis-correction-slider.created .analysis-correction-thumb::before{content:'✓';font-size:23px}.analysis-correction-slider.error{border-color:#ff6577}
      .analysis-correction-status{display:block;min-height:16px;margin-top:8px;color:#8297af;font-size:10px;text-align:center;overflow-wrap:anywhere}.analysis-correction-status.success{color:#72e7aa}.analysis-correction-status.error{color:#ff9eb0}
      @media(max-width:900px){.workspace-tone-picker{top:12px;right:12px}.workspace-tone-toggle{width:40px;height:40px}.workspace-tone-menu{position:absolute;top:48px;right:0}.analysis-enhanced-layout{grid-template-columns:1fr}.analysis-enhanced-left .task-client-card{max-height:none;overflow:visible}.analysis-proposal-card{position:static}}
      @media(max-width:720px){#task-log-modal{width:calc(100vw - 16px);max-width:calc(100vw - 16px);max-height:94dvh}#task-log-modal .task-log-modal-panel{padding:20px 14px;max-height:94dvh}.analysis-command-grid{grid-template-columns:1fr}.analysis-command-field.wide{grid-column:auto}.analysis-price-summary{grid-template-columns:1fr}.analysis-correction-slider{height:60px}.analysis-correction-thumb{width:50px;height:50px}.analysis-correction-label{inset:0 58px 0 66px;font-size:11px}}
    `;
    document.head.appendChild(style);
  }

  function installToneSelector() {
    if (document.querySelector('.workspace-tone-picker')) return;
    const tones = [
      {id:'black', label:'Preto absoluto'},
      {id:'graphite', label:'Grafite'},
      {id:'night', label:'Azul noturno'},
      {id:'deep-blue', label:'Azul profundo'},
    ];
    const storageKey = 'devpilot-workspace-tone';
    const saved = localStorage.getItem(storageKey);
    const initial = tones.some(t => t.id === saved) ? saved : 'black';
    const picker = document.createElement('div');
    picker.className = 'workspace-tone-picker';
    picker.innerHTML = `<div class="workspace-tone-menu" role="group" aria-label="Tons do fundo">${tones.map(t => `<button type="button" class="workspace-tone-option" data-tone="${t.id}" aria-label="${t.label}" title="${t.label}" aria-pressed="false"></button>`).join('')}</div><button type="button" class="workspace-tone-toggle" aria-label="Escolher tom do fundo" title="Tons do fundo" aria-expanded="false">◐</button>`;
    document.body.appendChild(picker);
    const toggle = picker.querySelector('.workspace-tone-toggle');
    const apply = tone => {
      document.documentElement.dataset.workspaceTone = tone;
      localStorage.setItem(storageKey, tone);
      picker.querySelectorAll('.workspace-tone-option').forEach(option => option.setAttribute('aria-pressed', String(option.dataset.tone === tone)));
    };
    const setOpen = open => { picker.classList.toggle('open', open); toggle.setAttribute('aria-expanded', String(open)); };
    toggle.onclick = event => { event.stopPropagation(); setOpen(!picker.classList.contains('open')); };
    picker.querySelectorAll('.workspace-tone-option').forEach(option => option.onclick = () => { apply(option.dataset.tone); setOpen(false); if (typeof toast === 'function') toast(`Fundo alterado para ${option.getAttribute('aria-label')}`); });
    document.addEventListener('click', event => { if (!picker.contains(event.target)) setOpen(false); });
    document.addEventListener('keydown', event => { if (event.key === 'Escape') setOpen(false); });
    apply(initial);
  }

  function runIdFromLink(link) {
    const match = String(link?.getAttribute('href') || '').match(/task-runs\/([^/?#]+)/);
    return match ? match[1] : null;
  }

  function ensureAnalysisStructure(dialog) {
    const panel = dialog?.querySelector('.task-log-modal-panel');
    const clientCard = dialog?.querySelector('#task-client-card');
    const details = dialog?.querySelector('.task-technical-details');
    if (!panel || !clientCard || !details) return null;

    let layout = panel.querySelector('.analysis-enhanced-layout');
    if (!layout) {
      layout = document.createElement('div');
      layout.className = 'analysis-enhanced-layout';
      const left = document.createElement('div');
      left.className = 'analysis-enhanced-left';
      clientCard.parentNode.insertBefore(layout, clientCard);
      layout.appendChild(left);
      left.appendChild(clientCard);

      const command = document.createElement('section');
      command.className = 'analysis-command-card';
      command.hidden = true;
      command.innerHTML = `<div class="analysis-command-head"><span class="eyebrow">COMANDO EXECUTADO</span><button class="analysis-command-copy" type="button">Copiar comando</button></div><div class="analysis-command-grid"></div>`;
      left.appendChild(command);

      const proposal = document.createElement('aside');
      proposal.className = 'analysis-proposal-card';
      proposal.innerHTML = `<div class="analysis-proposal-head"><div><span class="eyebrow">PROPOSTA COMERCIAL</span><h3>Investimento recomendado</h3></div><span class="analysis-review-badge">REVISÃO AUTOMÁTICA</span></div><div class="analysis-proposal-content">Aguardando dados da análise…</div>`;
      layout.appendChild(proposal);

      const correction = document.createElement('section');
      correction.className = 'analysis-correction-card';
      correction.hidden = true;
      correction.innerHTML = `<div class="analysis-correction-head"><div><h3>Gerar tarefa a partir desta análise</h3><p>Cria uma tarefa de correção com base no diagnóstico acima.</p></div><span class="analysis-review-badge">AÇÃO SEGURA</span></div><div class="analysis-correction-slider" role="slider" aria-label="Deslize para corrigir" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><span class="analysis-correction-fill"></span><span class="analysis-correction-label">Deslize para corrigir</span><button class="analysis-correction-thumb" type="button" aria-label="Arraste para gerar a tarefa de correção"></button></div><small class="analysis-correction-status">A tarefa será criada conforme as recomendações identificadas.</small>`;
      panel.insertBefore(correction, details);
      bindCorrectionSlider(correction);
    }
    return layout;
  }

  function firstValue(sources, keys) {
    for (const source of sources) {
      if (!source || typeof source !== 'object') continue;
      for (const key of keys) {
        const value = source[key];
        if (value !== undefined && value !== null && String(value).trim() !== '') return value;
      }
    }
    return '';
  }

  function commandData(data) {
    const logs = data?.logs && typeof data.logs === 'object' ? data.logs : {};
    const nested = logs.command && typeof logs.command === 'object' ? logs.command : {};
    const sources = [nested, logs, data];
    return {
      command: firstValue(sources, ['command', 'command_text', 'executed_command', 'cmd']),
      cwd: firstValue(sources, ['cwd', 'working_directory', 'workdir']),
      shell: firstValue(sources, ['shell']),
      exitCode: firstValue(sources, ['exit_code', 'return_code', 'returncode']),
      capturedAt: firstValue(sources, ['captured_at', 'executed_at', 'finished_at']),
    };
  }

  function renderCommand(dialog, data) {
    const card = dialog.querySelector('.analysis-command-card');
    const grid = card?.querySelector('.analysis-command-grid');
    const copy = card?.querySelector('.analysis-command-copy');
    if (!card || !grid || !copy) return;
    const command = commandData(data);
    const entries = [
      ['Comando', command.command, true], ['Diretório', command.cwd, true], ['Shell', command.shell, false], ['Código de saída', command.exitCode, false], ['Registrado em', command.capturedAt, true],
    ].filter(([, value]) => value !== '');
    grid.innerHTML = '';
    card.hidden = !entries.length;
    card.dataset.command = command.command ? String(command.command) : '';
    entries.forEach(([label, value, wide]) => {
      const field = document.createElement('div');
      field.className = `analysis-command-field${wide ? ' wide' : ''}`;
      field.innerHTML = `<span class="analysis-command-label"></span><code class="analysis-command-value"></code>`;
      field.querySelector('.analysis-command-label').textContent = label;
      field.querySelector('.analysis-command-value').textContent = String(value);
      grid.appendChild(field);
    });
    copy.onclick = async () => {
      if (!card.dataset.command) return;
      try { await navigator.clipboard.writeText(card.dataset.command); copy.textContent = 'Copiado'; setTimeout(() => { copy.textContent = 'Copiar comando'; }, 1400); }
      catch (_) { if (typeof toast === 'function') toast('Não foi possível copiar o comando'); }
    };
  }

  function formatMoney(value) {
    return new Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL', maximumFractionDigits:0}).format(Math.max(0, Math.round(value)));
  }

  function commercialEstimate(reportText) {
    const text = String(reportText || '');
    const lines = text.replace(/\r/g, '').split('\n');
    const rangePattern = /(\d{1,4})\s*(?:–|—|-)\s*(\d{1,4})\s*h\b/i;
    const ranges = [];
    const totalLine = lines.find(line => /\btotal\b/i.test(line) && rangePattern.test(line));
    if (totalLine) {
      const m = totalLine.match(rangePattern); ranges.push([Number(m[1]), Number(m[2])]);
    } else {
      const seen = new Set();
      lines.forEach(line => { const m = line.match(rangePattern); if (!m || ranges.length >= 8) return; const key = m[0].replace(/\s/g,'').toLowerCase(); if (seen.has(key)) return; seen.add(key); ranges.push([Number(m[1]), Number(m[2])]); });
    }
    let minHours; let maxHours;
    if (ranges.length) {
      minHours = ranges.reduce((sum, r) => sum + Math.min(...r), 0); maxHours = ranges.reduce((sum, r) => sum + Math.max(...r), 0);
    } else {
      const count = re => (text.match(re) || []).length;
      const critical = count(/\bcr[ií]tic[oa]s?\b/gi); const high = count(/\balto?s?\b|\balta?s?\b/gi); const medium = count(/\bm[eé]di[oa]s?\b/gi); const low = count(/\bbaixo?s?\b|\bbaixa?s?\b/gi);
      minHours = 24 + critical * 28 + high * 18 + medium * 10 + low * 5; maxHours = 44 + critical * 52 + high * 34 + medium * 20 + low * 10;
    }
    minHours = Math.max(32, Math.min(600, minHours)); maxHours = Math.max(minHours, Math.min(900, maxHours));
    const hourlyMin = 180; const hourlyMax = 280; const minimum = minHours * hourlyMin; const maximum = maxHours * hourlyMax; const average = Math.round(((minimum + maximum) / 2) / 100) * 100;
    const scope = lines.filter(line => /^\s*[-*•]\s+/.test(line)).map(line => line.replace(/^\s*[-*•]\s+/, '').replace(/\*\*/g, '').trim()).filter(Boolean).slice(0, 3);
    return {minHours,maxHours,hourlyMin,hourlyMax,minimum,maximum,average,scope};
  }

  function renderProposal(dialog, reportText) {
    const target = dialog.querySelector('.analysis-proposal-content');
    if (!target) return;
    const e = commercialEstimate(reportText);
    const defaults = ['Correção dos riscos críticos e estabilização da operação','Implementação das melhorias priorizadas na análise','Testes, validação técnica e entrega assistida'];
    const scopes = defaults.map((fallback, index) => e.scope[index] || fallback);
    const phases = [['01','Estabilização',scopes[0],.45],['02','Evolução',scopes[1],.35],['03','Validação',scopes[2],.20]];
    target.innerHTML = `<div class="analysis-price-summary"><div class="analysis-price-item"><span>Faixa mínima</span><strong>${formatMoney(e.minimum)}</strong></div><div class="analysis-price-item featured"><span>Valor médio</span><strong>${formatMoney(e.average)}</strong></div><div class="analysis-price-item"><span>Faixa máxima</span><strong>${formatMoney(e.maximum)}</strong></div></div><div class="analysis-proposal-meta"><span>${e.minHours}–${e.maxHours} horas</span><span>${formatMoney(e.hourlyMin)}–${formatMoney(e.hourlyMax)}/h</span><span>3 fases de entrega</span></div><div class="analysis-proposal-phases">${phases.map(([number,title,scope,share]) => `<div class="analysis-proposal-phase"><b>${number}</b><div><strong>${title}</strong><small>${String(scope).slice(0,120)}</small></div><strong>${formatMoney(e.average * share)}</strong></div>`).join('')}</div><p class="analysis-proposal-note">Estimativa produzida a partir das horas, criticidade e escopo encontrados na análise. Revise premissas e detalhes contratuais antes de enviar ao cliente.</p><div class="analysis-proposal-actions"><button type="button" class="ghost analysis-proposal-print">Imprimir proposta</button></div>`;
    target.querySelector('.analysis-proposal-print').onclick = () => window.print();
  }

  function reportTextFrom(data, dialog) {
    const logs = data?.logs && typeof data.logs === 'object' ? data.logs : {};
    if (typeof logs.client_report === 'string' && logs.client_report.trim()) return logs.client_report.trim();
    const visible = dialog.querySelector('#task-client-report')?.innerText?.trim();
    if (visible) return visible;
    return String(data?.summary || '').trim();
  }

  function correctionPriority(report) {
    if (/cr[ií]tico|bloqueio|credencia(?:l|is)|seguran[cç]a/i.test(report)) return 90;
    if (/alto|importante|risco/i.test(report)) return 80;
    return 70;
  }

  async function resolveTask(taskId) {
    if (typeof state !== 'undefined') {
      const direct = state.tasks?.find(item => String(item.id) === String(taskId));
      if (direct) return direct;
    }
    try {
      const tasks = await api('/tasks?limit=500');
      return tasks.find(item => String(item.id) === String(taskId)) || null;
    } catch (_) { return null; }
  }

  async function createCorrection(card) {
    if (!context.runId || card.dataset.creating === '1') return;
    const slider = card.querySelector('.analysis-correction-slider');
    const label = card.querySelector('.analysis-correction-label');
    const status = card.querySelector('.analysis-correction-status');
    const thumb = card.querySelector('.analysis-correction-thumb');
    card.dataset.creating = '1'; thumb.disabled = true; label.textContent = 'Criando tarefa…'; status.textContent = 'Validando diagnóstico e evitando duplicidade…';
    try {
      const dialog = document.querySelector('#task-log-modal');
      const data = await api(`/task-runs/${encodeURIComponent(context.runId)}`);
      const task = await resolveTask(context.taskId || data.task_id);
      if (!task?.project_id) throw new Error('Projeto da análise não encontrado');
      const report = reportTextFrom(data, dialog);
      const marker = `[analysis-run:${data.id}]`;
      const tasks = await api(`/tasks?project_id=${encodeURIComponent(task.project_id)}&limit=500`);
      const existing = tasks.find(item => String(item.prompt || '').includes(marker));
      if (existing) {
        slider.classList.add('created'); label.textContent = 'Tarefa já criada'; status.textContent = `Tarefa existente: ${existing.title}`; status.className = 'analysis-correction-status success'; card.dataset.creating = '0'; return;
      }
      const project = (typeof state !== 'undefined' ? state.projects?.find(item => String(item.id) === String(task.project_id)) : null);
      const projectName = project?.name || String(task.title || 'projeto').replace(/^Análise técnica de\s+/i, '');
      const payload = {
        project_id: task.project_id,
        title: `Correção baseada na análise · ${projectName}`.slice(0,240),
        prompt: `${marker}\nImplemente as correções recomendadas pela análise técnica abaixo. Priorize riscos críticos, preserve compatibilidade, execute testes relevantes e registre claramente o que foi alterado. Não repita a análise; transforme o diagnóstico em implementação verificável.\n\nDIAGNÓSTICO:\n${report}`.slice(0,100000),
        source: 'dashboard', priority: correctionPriority(report), requires_approval: true,
      };
      const created = await api('/tasks', {method:'POST', body:JSON.stringify(payload)});
      slider.classList.add('created');
      const max = Math.max(0, slider.clientWidth - thumb.offsetWidth - 10); setProgress(slider, max);
      label.textContent = 'Tarefa criada'; status.textContent = `${created.title} · aguardando aprovação`; status.className = 'analysis-correction-status success';
      if (typeof toast === 'function') toast('Tarefa de correção criada a partir da análise');
      if (typeof load === 'function') setTimeout(() => load(), 250);
    } catch (error) {
      slider.classList.add('error'); label.textContent = 'Falhou · tente novamente'; status.textContent = error?.message || 'Falha ao criar tarefa'; status.className = 'analysis-correction-status error'; thumb.disabled = false; card.dataset.creating = '0';
    }
  }

  function setProgress(slider, px) {
    const thumb = slider.querySelector('.analysis-correction-thumb');
    const max = Math.max(0, slider.clientWidth - thumb.offsetWidth - 10);
    const value = Math.max(0, Math.min(max, px)); const pct = max ? value / max * 100 : 0;
    slider.style.setProperty('--slide', `${value}px`); slider.style.setProperty('--pct', `${pct}%`); slider.setAttribute('aria-valuenow', String(Math.round(pct))); return max ? value / max : 0;
  }

  function resetSlider(card) {
    const slider = card.querySelector('.analysis-correction-slider'); const label = card.querySelector('.analysis-correction-label'); const thumb = card.querySelector('.analysis-correction-thumb'); const status = card.querySelector('.analysis-correction-status');
    slider.classList.remove('error'); label.textContent = 'Deslize para corrigir'; status.textContent = 'A tarefa será criada conforme as recomendações identificadas.'; status.className = 'analysis-correction-status'; thumb.disabled = false; card.dataset.creating = '0'; setProgress(slider, 0);
  }

  function bindCorrectionSlider(card) {
    if (card.dataset.bound === '1') return; card.dataset.bound = '1';
    const slider = card.querySelector('.analysis-correction-slider'); const thumb = card.querySelector('.analysis-correction-thumb'); let pointerId = null; let startX = 0; let startSlide = 0;
    thumb.addEventListener('click', event => { event.preventDefault(); event.stopImmediatePropagation(); }, true);
    thumb.addEventListener('pointerdown', event => { if (card.dataset.creating === '1' || slider.classList.contains('created')) return; pointerId = event.pointerId; startX = event.clientX; startSlide = parseFloat(getComputedStyle(slider).getPropertyValue('--slide')) || 0; thumb.setPointerCapture?.(pointerId); event.preventDefault(); });
    thumb.addEventListener('pointermove', event => { if (pointerId !== event.pointerId) return; setProgress(slider, startSlide + event.clientX - startX); event.preventDefault(); });
    const finish = event => { if (pointerId === null || (event.pointerId != null && event.pointerId !== pointerId)) return; const ratio = setProgress(slider, parseFloat(getComputedStyle(slider).getPropertyValue('--slide')) || 0); pointerId = null; if (ratio >= CORRECTION_COMPLETE_AT) createCorrection(card); else resetSlider(card); };
    thumb.addEventListener('pointerup', finish); thumb.addEventListener('pointercancel', finish);
    thumb.addEventListener('keydown', event => { if (event.key === 'End' || event.key === 'ArrowRight') { event.preventDefault(); const max = Math.max(0, slider.clientWidth - thumb.offsetWidth - 10); setProgress(slider,max); createCorrection(card); } });
  }

  async function enhanceOpenDialog() {
    if (context.enhancing || !context.runId) return;
    const dialog = document.querySelector('#task-log-modal');
    if (!dialog?.open) return;
    const layout = ensureAnalysisStructure(dialog); if (!layout) return;
    context.enhancing = true;
    try {
      const data = await api(`/task-runs/${encodeURIComponent(context.runId)}`);
      const report = reportTextFrom(data, dialog);
      renderCommand(dialog, data); renderProposal(dialog, report);
      const correction = dialog.querySelector('.analysis-correction-card');
      if (correction) { correction.hidden = String(data.status || '').toLowerCase() !== 'success'; resetSlider(correction); }
      const eyebrow = dialog.querySelector('#task-client-card > .eyebrow'); if (eyebrow) eyebrow.textContent = 'ANÁLISE DE IA · GERADA E REVISADA';
    } catch (_) {
      const proposal = dialog.querySelector('.analysis-proposal-content'); if (proposal) proposal.textContent = 'Proposta indisponível até que a análise seja carregada.';
    } finally { context.enhancing = false; }
  }

  injectStyles();
  installToneSelector();

  document.addEventListener('click', event => {
    const link = event.target.closest?.('.task-log-link');
    if (!link) return;
    context.taskId = link.closest('tr[data-task-id]')?.dataset.taskId || null;
    context.runId = runIdFromLink(link);
    setTimeout(enhanceOpenDialog, 80);
  }, true);

  new MutationObserver(() => {
    const dialog = document.querySelector('#task-log-modal');
    if (dialog?.open && context.runId) setTimeout(enhanceOpenDialog, 30);
  }).observe(document.body, {subtree:true, childList:true, attributes:true, attributeFilter:['open']});
})();
