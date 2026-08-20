(() => {
  let taskRunGeneration = 0;
  const CORRECTION_COMPLETE_AT = 0.86;

  function ensureTaskFailureStyles() {
    if (document.getElementById('task-failure-styles')) return;
    const style = document.createElement('style');
    style.id = 'task-failure-styles';
    style.textContent = `
      .task-status-stack{display:flex;flex-direction:column;align-items:flex-start;gap:7px;min-width:150px}
      .task-failure-reason{display:block;max-width:300px;color:#f1a7b8;line-height:1.35;font-size:11px;white-space:normal;overflow-wrap:anywhere}
      .task-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
      .task-log-link{font-size:12px;font-weight:700;text-decoration:none;white-space:nowrap}
      #task-log-modal{width:min(940px,calc(100vw - 28px));max-width:calc(100vw - 28px);max-height:min(92dvh,900px);overflow:hidden}
      .task-log-modal-panel{width:100%;max-width:100%;min-width:0;max-height:min(92dvh,900px);overflow-y:auto;overflow-x:hidden;padding:28px;overscroll-behavior:contain;scrollbar-gutter:stable}
      .task-log-modal-panel>*{min-width:0;max-width:100%}
      .task-log-meta{margin:0 0 16px;color:var(--muted,#9aa8bd);font-size:12px;overflow-wrap:anywhere}
      .task-client-card{min-width:0;margin:0 0 16px;padding:18px;border:1px solid #24665d;border-radius:14px;background:linear-gradient(145deg,#0b201f,#0b1723);overflow:hidden}
      .task-client-card .eyebrow{display:block;margin-bottom:10px;color:#3be4d0}
      .task-client-report{min-width:0;max-width:100%;color:#eaf4ff;font-size:14px;line-height:1.65;overflow-wrap:anywhere;word-break:break-word}
      .task-client-report>*{min-width:0;max-width:100%}
      .task-client-report h3{margin:18px 0 6px;color:#fff;font-size:15px}
      .task-client-report h3:first-child{margin-top:0}
      .task-client-report p{margin:0 0 9px;color:#d7e2ef;white-space:normal;overflow-wrap:anywhere}
      .task-client-report ul{margin:4px 0 10px;padding-left:20px;color:#d7e2ef}
      .task-client-report li{margin:4px 0;overflow-wrap:anywhere}
      .task-technical-details{min-width:0;margin-top:12px;border:1px solid var(--line,#26364f);border-radius:12px;background:#07111d;overflow:hidden}
      .task-technical-details>summary{padding:13px 15px;cursor:pointer;color:#9eb1c8;font-weight:800;font-size:12px;user-select:none}
      .task-log-output{margin:0;width:100%;max-width:100%;max-height:48vh;overflow:auto;padding:16px;border-top:1px solid var(--line,#26364f);background:#050c17;color:#c7d5e8;font-size:11px;line-height:1.5;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word}
      .task-result-ok{color:#61e7ac;font-weight:800}
      .task-result-failed{color:#ff9eb0;font-weight:800}

      .task-correction-card{position:sticky;bottom:-1px;z-index:5;display:grid;gap:9px;margin:16px 0 4px;padding:15px 16px 13px;border:1px solid #29445f;border-radius:14px;background:linear-gradient(145deg,rgba(16,34,53,.98),rgba(8,21,34,.98));box-shadow:0 -14px 30px rgba(3,10,19,.52),0 14px 34px rgba(0,0,0,.24);backdrop-filter:blur(14px)}
      .task-correction-card[hidden]{display:none}
      .task-correction-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
      .task-correction-heading h3{margin:0;color:#f4f8ff;font-size:15px}
      .task-correction-heading p{margin:3px 0 0;color:#8fa4bd;font-size:11px;line-height:1.45}
      .task-correction-badge{flex:0 0 auto;padding:4px 8px;border:1px solid rgba(53,229,209,.3);border-radius:999px;color:#58ead8;background:rgba(53,229,209,.08);font-size:9px;font-weight:850;letter-spacing:.07em;text-transform:uppercase}
      .task-correction-slider{--correction-slide:0px;--correction-pct:0%;position:relative;width:100%;height:58px;border:1px solid #2b8590;border-radius:999px;overflow:hidden;background:#071522;box-shadow:inset 0 0 0 1px rgba(255,255,255,.02),0 0 0 2px rgba(53,229,209,.035),0 0 24px rgba(53,229,209,.08);touch-action:pan-y;user-select:none;-webkit-user-select:none;transition:border-color .2s ease,background .2s ease,box-shadow .2s ease}
      .task-correction-slider-fill{position:absolute;inset:0 auto 0 0;width:var(--correction-pct);pointer-events:none;background:linear-gradient(90deg,rgba(53,229,209,.48),rgba(72,185,248,.26));transition:width .08s linear,opacity .2s ease}
      .task-correction-slider-label{position:absolute;inset:0 62px 0 66px;display:flex;align-items:center;justify-content:center;color:#57ead8;font-size:12px;font-weight:900;letter-spacing:.025em;pointer-events:none;white-space:nowrap;text-align:center;transition:color .2s ease}
      .task-correction-slider-label::after{content:'✦';position:absolute;right:-40px;color:#43dfd1;font-size:16px}
      .task-correction-thumb{position:absolute;z-index:2;left:5px;top:5px;width:48px;height:48px;padding:0;border:0;border-radius:50%;display:grid;place-items:center;transform:translateX(var(--correction-slide));background:linear-gradient(135deg,#39e6d2,#48b9f8);color:#06111b;box-shadow:0 7px 20px rgba(53,229,209,.28);font-size:0;cursor:grab;touch-action:none;transition:transform .18s ease,background .2s ease,box-shadow .2s ease}
      .task-correction-thumb::before{content:'»';font-size:25px;font-weight:950;line-height:1;transform:translateY(-1px)}
      .task-correction-slider.dragging .task-correction-thumb{cursor:grabbing;transition:none}
      .task-correction-slider.dragging .task-correction-slider-fill{transition:none}
      .task-correction-slider.creating{border-color:#3ed8ca;box-shadow:0 0 0 3px rgba(53,229,209,.08),0 0 30px rgba(53,229,209,.14)}
      .task-correction-slider.created{border-color:#38dd8a;background:#09251c;box-shadow:0 0 0 3px rgba(56,221,138,.09),0 0 26px rgba(56,221,138,.12)}
      .task-correction-slider.created .task-correction-slider-fill{width:100%!important;background:linear-gradient(90deg,#24b979,#38dd8a);opacity:.55}
      .task-correction-slider.created .task-correction-slider-label{color:#d9ffea}
      .task-correction-slider.created .task-correction-slider-label::after{content:'✓';color:#74efae}
      .task-correction-slider.created .task-correction-thumb{background:linear-gradient(135deg,#39e391,#20b86e);color:#052014;box-shadow:0 7px 18px rgba(32,184,110,.28)}
      .task-correction-slider.created .task-correction-thumb::before{content:'✓';font-size:23px}
      .task-correction-slider.error{border-color:#ff6577;box-shadow:0 0 0 3px rgba(255,101,119,.08)}
      .task-correction-status{display:block;min-height:16px;color:#8297af;font-size:10px;text-align:center;overflow-wrap:anywhere}
      .task-correction-status.success{color:#72e7aa}
      .task-correction-status.error{color:#ff9eb0}

      @media (max-width:720px){
        #task-log-modal{width:calc(100vw - 16px);max-width:calc(100vw - 16px);max-height:94dvh}
        .task-failure-reason{max-width:190px}
        .task-log-modal-panel{width:100%;max-height:94dvh;padding:20px 14px}
        .task-client-card{padding:15px}
        .task-client-report{font-size:14px;line-height:1.6}
        .task-correction-card{margin-inline:-2px;padding:13px 12px 11px;border-radius:13px}
        .task-correction-heading{gap:8px}
        .task-correction-heading h3{font-size:14px}
        .task-correction-badge{display:none}
        .task-correction-slider{height:60px}
        .task-correction-thumb{width:50px;height:50px}
        .task-correction-slider-label{inset:0 58px 0 66px;font-size:11px}
      }
    `;
    document.head.appendChild(style);
  }

  function ensureTaskLogDialog() {
    let dialog = document.getElementById('task-log-modal');
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = 'task-log-modal';
    dialog.innerHTML = `
      <div class="modal task-log-modal-panel">
        <button class="close task-log-close" type="button" aria-label="Fechar">×</button>
        <span class="eyebrow">RESULTADO DA ANÁLISE</span>
        <h2 id="task-log-title">Detalhes da execução</h2>
        <p class="task-log-meta" id="task-log-meta"></p>
        <section class="task-client-card" id="task-client-card">
          <span class="eyebrow">PARA O CLIENTE</span>
          <div class="task-client-report" id="task-client-report"></div>
        </section>
        <section class="task-correction-card" id="task-correction-card" hidden aria-live="polite">
          <div class="task-correction-heading">
            <div>
              <h3>Gerar tarefa a partir desta análise</h3>
              <p>Cria uma tarefa de correção usando o diagnóstico exibido acima.</p>
            </div>
            <span class="task-correction-badge">AÇÃO SEGURA</span>
          </div>
          <div class="task-correction-slider" role="slider" aria-label="Deslize para gerar a tarefa de correção" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
            <span class="task-correction-slider-fill"></span>
            <span class="task-correction-slider-label">Deslize para corrigir</span>
            <button class="task-correction-thumb" type="button" aria-label="Arraste para a direita para gerar a tarefa de correção"></button>
          </div>
          <small class="task-correction-status">A tarefa será criada conforme as recomendações identificadas.</small>
        </section>
        <details class="task-technical-details">
          <summary>Ver detalhes técnicos</summary>
          <pre class="task-log-output" id="task-log-output"></pre>
        </details>
      </div>`;
    document.body.appendChild(dialog);
    dialog.querySelector('.task-log-close').onclick = () => dialog.close();
    dialog.addEventListener('click', event => {
      if (event.target === dialog) dialog.close();
    });
    bindCorrectionSlider(dialog);
    return dialog;
  }

  function collectMessageText(value, output) {
    if (!value) return;
    if (typeof value === 'string') {
      const text = value.trim();
      if (text) output.push(text);
      return;
    }
    if (Array.isArray(value)) {
      value.forEach(item => collectMessageText(item, output));
      return;
    }
    if (typeof value !== 'object') return;

    const type = String(value.type || '').toLowerCase();
    if (['agent_message', 'assistant_message', 'output_text'].includes(type)) {
      ['text', 'content', 'message', 'output_text'].forEach(key => {
        if (key in value) collectMessageText(value[key], output);
      });
      return;
    }
    ['item', 'message', 'response', 'output'].forEach(key => {
      if (value[key] && typeof value[key] === 'object') collectMessageText(value[key], output);
    });
  }

  function reportFromStdout(stdout) {
    const candidates = [];
    String(stdout || '').split(/\r?\n/).forEach(raw => {
      const line = raw.trim();
      if (!line.startsWith('{')) return;
      try {
        collectMessageText(JSON.parse(line), candidates);
      } catch (_) {
        // Linha técnica que não é JSON válido: permanece apenas nos detalhes técnicos.
      }
    });

    for (let index = candidates.length - 1; index >= 0; index -= 1) {
      const text = candidates[index].trim();
      if (text.length < 40) continue;
      if (/resumo para o cliente|o que encontramos|recomenda[cç][õo]es/i.test(text)) return text;
    }
    return candidates.length ? candidates[candidates.length - 1] : '';
  }

  function clientReport(data) {
    const logs = data?.logs && typeof data.logs === 'object' ? data.logs : {};
    const explicit = typeof logs.client_report === 'string' ? logs.client_report.trim() : '';
    if (explicit) return explicit;

    const extracted = reportFromStdout(logs.stdout || '');
    if (extracted) return extracted;

    const summary = String(data?.summary || '').trim();
    const generic = /read-only analysis completed|execution completed|isolated disposable worktree/i.test(summary);
    if (summary && !generic) return summary;

    if (String(data?.status || '').toLowerCase() === 'success') {
      return 'A análise foi concluída com sucesso. Esta execução foi gerada antes do novo formato de relatório para cliente. Execute uma nova análise para receber o diagnóstico organizado em resumo, impacto, recomendações e próximo passo.';
    }
    return 'A execução não foi concluída. Abra os detalhes técnicos abaixo para identificar a falha e execute novamente após a correção.';
  }

  function cleanHeading(line) {
    return line
      .replace(/^#{1,6}\s*/, '')
      .replace(/^\*\*(.+)\*\*:?$/, '$1')
      .replace(/:$/, '')
      .trim();
  }

  function isHeading(line) {
    const clean = cleanHeading(line).toLowerCase();
    return [
      'resumo para o cliente',
      'o que encontramos',
      'impacto',
      'recomendações',
      'recomendacoes',
      'próximo passo',
      'proximo passo',
    ].includes(clean) || /^#{1,6}\s+/.test(line);
  }

  function renderClientReport(target, value) {
    target.innerHTML = '';
    const lines = String(value || '').replace(/\r/g, '').split('\n');
    let list = null;

    const appendParagraph = text => {
      if (!text.trim()) return;
      const p = document.createElement('p');
      p.textContent = text.trim().replace(/^\*\*(.+)\*\*$/, '$1');
      target.appendChild(p);
    };

    lines.forEach(raw => {
      const line = raw.trim();
      if (!line) {
        list = null;
        return;
      }
      if (isHeading(line)) {
        list = null;
        const heading = document.createElement('h3');
        heading.textContent = cleanHeading(line);
        target.appendChild(heading);
        return;
      }
      if (/^[-*•]\s+/.test(line) || /^\d+[.)]\s+/.test(line)) {
        if (!list) {
          list = document.createElement('ul');
          target.appendChild(list);
        }
        const item = document.createElement('li');
        item.textContent = line.replace(/^[-*•]\s+/, '').replace(/^\d+[.)]\s+/, '');
        list.appendChild(item);
        return;
      }
      list = null;
      appendParagraph(line);
    });

    if (!target.childNodes.length) appendParagraph('Nenhum resumo para o cliente foi registrado.');
  }

  function formatTechnicalLog(data) {
    const parts = [];
    if (data.summary) parts.push(`RESUMO TÉCNICO\n${data.summary}`);
    if (data.logs && (typeof data.logs !== 'object' || Object.keys(data.logs).length)) {
      let logs = data.logs;
      if (logs && typeof logs === 'object') {
        logs = {...logs};
        delete logs.client_report;
      }
      const rendered = typeof logs === 'string' ? logs : JSON.stringify(logs, null, 2);
      parts.push(`LOG BRUTO\n${rendered}`);
    }
    if (data.commit_sha) parts.push(`COMMIT\n${data.commit_sha}`);
    if (data.pull_request_url) parts.push(`PULL REQUEST\n${data.pull_request_url}`);
    return parts.join('\n\n') || 'Nenhum detalhe técnico foi registrado nesta execução.';
  }

  function statusLabel(value) {
    const normalized = String(value || '').toLowerCase();
    if (normalized === 'success') return 'Concluído';
    if (normalized === 'failed') return 'Falhou';
    if (normalized === 'running') return 'Em execução';
    return value || '—';
  }

  function setCorrectionProgress(slider, px) {
    const thumb = slider?.querySelector('.task-correction-thumb');
    if (!slider || !thumb) return 0;
    const max = Math.max(0, slider.clientWidth - thumb.offsetWidth - 10);
    const value = Math.max(0, Math.min(max, px));
    const pct = max ? (value / max) * 100 : 0;
    slider.style.setProperty('--correction-slide', `${value}px`);
    slider.style.setProperty('--correction-pct', `${pct}%`);
    slider.setAttribute('aria-valuenow', String(Math.round(pct)));
    return max ? value / max : 0;
  }

  function resetCorrectionSlider(dialog) {
    const card = dialog?.querySelector('.task-correction-card');
    const slider = dialog?.querySelector('.task-correction-slider');
    const thumb = dialog?.querySelector('.task-correction-thumb');
    const label = dialog?.querySelector('.task-correction-slider-label');
    const status = dialog?.querySelector('.task-correction-status');
    if (!card || !slider || !thumb || !label || !status) return;
    slider.classList.remove('dragging', 'creating', 'created', 'error');
    slider.dataset.creating = '0';
    thumb.disabled = false;
    label.textContent = 'Deslize para corrigir';
    status.textContent = 'A tarefa será criada conforme as recomendações identificadas.';
    status.className = 'task-correction-status';
    setCorrectionProgress(slider, 0);
  }

  function correctionPriority(report) {
    const text = String(report || '');
    if (/cr[ií]tico|bloqueio|credencia(?:l|is)|seguran[cç]a/i.test(text)) return 90;
    if (/alto|importante|risco/i.test(text)) return 80;
    return 70;
  }

  function correctionTitle(task) {
    const project = state.projects.find(item => String(item.id) === String(task?.project_id));
    const projectName = project?.name || String(task?.title || 'projeto').replace(/^Análise técnica de\s+/i, '');
    return `Correção baseada na análise · ${projectName}`.slice(0, 240);
  }

  function correctionPrompt(task, data, report) {
    const marker = `[analysis-run:${data.id}]`;
    return [
      marker,
      'Implemente as correções recomendadas pela análise técnica abaixo.',
      '',
      `Análise de origem: ${task?.title || 'Análise técnica'}`,
      `Execução analisada: ${data.id}`,
      '',
      'Objetivo:',
      '- Corrigir os achados priorizados na análise, começando pelos itens críticos e de maior risco.',
      '- Preservar o comportamento válido existente e evitar mudanças fora do escopo do diagnóstico.',
      '- Implementar de forma incremental, auditável e reversível.',
      '- Executar testes relevantes e registrar claramente o que foi corrigido, o que ficou pendente e por quê.',
      '- Não expor credenciais, tokens, segredos ou dados sensíveis.',
      '',
      'ANÁLISE QUE ORIGINA ESTA TAREFA',
      String(report || '').trim(),
    ].join('\n').slice(0, 100000);
  }

  function existingCorrection(task, data) {
    const marker = `[analysis-run:${data.id}]`;
    return state.tasks.find(item => (
      String(item.project_id) === String(task?.project_id)
      && String(item.prompt || '').includes(marker)
    ));
  }

  async function createCorrectionTask(dialog) {
    const context = dialog?._correctionContext;
    const slider = dialog?.querySelector('.task-correction-slider');
    const thumb = dialog?.querySelector('.task-correction-thumb');
    const label = dialog?.querySelector('.task-correction-slider-label');
    const status = dialog?.querySelector('.task-correction-status');
    if (!context || !slider || !thumb || !label || !status) return;
    if (slider.dataset.creating === '1' || slider.classList.contains('created')) return;

    const duplicate = existingCorrection(context.task, context.data);
    if (duplicate) {
      slider.classList.remove('dragging', 'creating', 'error');
      slider.classList.add('created');
      const max = Math.max(0, slider.clientWidth - thumb.offsetWidth - 10);
      setCorrectionProgress(slider, max);
      label.textContent = 'Tarefa já criada';
      status.textContent = 'Esta análise já possui uma tarefa de correção vinculada.';
      status.className = 'task-correction-status success';
      thumb.disabled = true;
      return;
    }

    slider.dataset.creating = '1';
    slider.classList.remove('dragging', 'error');
    slider.classList.add('creating');
    const max = Math.max(0, slider.clientWidth - thumb.offsetWidth - 10);
    setCorrectionProgress(slider, max);
    label.textContent = 'Gerando tarefa…';
    status.textContent = 'Convertendo o diagnóstico em uma tarefa de desenvolvimento.';
    status.className = 'task-correction-status';
    thumb.disabled = true;

    try {
      const payload = {
        project_id: context.task.project_id,
        title: correctionTitle(context.task),
        prompt: correctionPrompt(context.task, context.data, context.report),
        source: 'dashboard',
        priority: correctionPriority(context.report),
        requires_approval: true,
      };
      await api('/tasks', {method: 'POST', body: JSON.stringify(payload)});
      slider.classList.remove('creating');
      slider.classList.add('created');
      label.textContent = 'Tarefa criada';
      status.textContent = 'Correção criada em Desenvolvimento. Revise e aprove antes da execução.';
      status.className = 'task-correction-status success';
      if (typeof toast === 'function') toast('Tarefa de correção criada a partir da análise');
      await load();
    } catch (error) {
      slider.dataset.creating = '0';
      slider.classList.remove('creating', 'created');
      slider.classList.add('error');
      label.textContent = 'Falhou · tente novamente';
      status.textContent = error?.message || 'Não foi possível gerar a tarefa de correção.';
      status.className = 'task-correction-status error';
      thumb.disabled = false;
      if (typeof toast === 'function') toast(error?.message || 'Falha ao gerar tarefa de correção');
      setTimeout(() => {
        if (dialog.open) resetCorrectionSlider(dialog);
      }, 1600);
    }
  }

  function bindCorrectionSlider(dialog) {
    const slider = dialog?.querySelector('.task-correction-slider');
    const thumb = dialog?.querySelector('.task-correction-thumb');
    if (!slider || !thumb || slider.dataset.bound === '1') return;
    slider.dataset.bound = '1';

    let pointerId = null;
    let startX = 0;
    let startSlide = 0;

    thumb.addEventListener('click', event => {
      event.preventDefault();
      event.stopImmediatePropagation();
    }, true);

    thumb.addEventListener('pointerdown', event => {
      if (thumb.disabled || slider.dataset.creating === '1' || slider.classList.contains('created')) return;
      pointerId = event.pointerId;
      startX = event.clientX;
      startSlide = parseFloat(getComputedStyle(slider).getPropertyValue('--correction-slide')) || 0;
      slider.classList.add('dragging');
      thumb.setPointerCapture?.(pointerId);
      event.preventDefault();
    });

    thumb.addEventListener('pointermove', event => {
      if (pointerId !== event.pointerId || !slider.classList.contains('dragging')) return;
      setCorrectionProgress(slider, startSlide + event.clientX - startX);
      event.preventDefault();
    });

    const finish = event => {
      if (pointerId === null || (event.pointerId != null && event.pointerId !== pointerId)) return;
      const ratio = setCorrectionProgress(
        slider,
        parseFloat(getComputedStyle(slider).getPropertyValue('--correction-slide')) || 0,
      );
      slider.classList.remove('dragging');
      pointerId = null;
      if (ratio >= CORRECTION_COMPLETE_AT) createCorrectionTask(dialog);
      else resetCorrectionSlider(dialog);
    };

    thumb.addEventListener('pointerup', finish);
    thumb.addEventListener('pointercancel', finish);
    thumb.addEventListener('keydown', event => {
      if (event.key === 'End' || event.key === 'ArrowRight') {
        event.preventDefault();
        const max = Math.max(0, slider.clientWidth - thumb.offsetWidth - 10);
        setCorrectionProgress(slider, max);
        createCorrectionTask(dialog);
      }
    });
  }

  function configureCorrection(dialog, task, data, report) {
    const card = dialog.querySelector('.task-correction-card');
    dialog._correctionContext = null;
    resetCorrectionSlider(dialog);
    const usableReport = String(report || '').trim();
    const canCreate = Boolean(task?.project_id && data?.id && usableReport.length >= 40);
    card.hidden = !canCreate;
    if (!canCreate) return;
    dialog._correctionContext = {task, data, report: usableReport};

    const duplicate = existingCorrection(task, data);
    if (duplicate) {
      const slider = dialog.querySelector('.task-correction-slider');
      const thumb = dialog.querySelector('.task-correction-thumb');
      const label = dialog.querySelector('.task-correction-slider-label');
      const status = dialog.querySelector('.task-correction-status');
      slider.classList.add('created');
      const max = Math.max(0, slider.clientWidth - thumb.offsetWidth - 10);
      setCorrectionProgress(slider, max);
      label.textContent = 'Tarefa já criada';
      status.textContent = 'Esta análise já possui uma tarefa de correção vinculada.';
      status.className = 'task-correction-status success';
      thumb.disabled = true;
    }
  }

  async function openTaskLog(runId, task) {
    const dialog = ensureTaskLogDialog();
    const title = dialog.querySelector('#task-log-title');
    const meta = dialog.querySelector('#task-log-meta');
    const report = dialog.querySelector('#task-client-report');
    const output = dialog.querySelector('#task-log-output');
    const details = dialog.querySelector('.task-technical-details');
    const correction = dialog.querySelector('.task-correction-card');

    dialog._correctionContext = null;
    correction.hidden = true;
    resetCorrectionSlider(dialog);
    title.textContent = task?.title || 'Resultado da análise';
    meta.textContent = 'Preparando resultado…';
    report.textContent = 'Carregando análise…';
    output.textContent = '';
    details.open = false;
    if (!dialog.open) dialog.showModal();

    try {
      const data = await api(`/task-runs/${runId}`);
      const started = data.started_at ? new Date(data.started_at).toLocaleString('pt-BR') : '—';
      const failed = String(data.status || '').toLowerCase() === 'failed';
      const reportText = clientReport(data);
      meta.innerHTML = `<span class="${failed ? 'task-result-failed' : 'task-result-ok'}">${esc(statusLabel(data.status))}</span> · tentativa ${esc(data.attempt || 1)} · início ${esc(started)}`;
      renderClientReport(report, reportText);
      output.textContent = formatTechnicalLog(data);
      configureCorrection(dialog, task, data, reportText);
    } catch (error) {
      meta.textContent = 'Falha ao carregar o resultado';
      renderClientReport(report, error.message || 'Não foi possível consultar esta execução.');
      output.textContent = error.message || 'Não foi possível consultar esta execução.';
      correction.hidden = true;
    }
  }

  async function hydrateTaskRunDetails(generation) {
    try {
      const details = await api('/task-runs/latest?limit=500');
      if (generation !== taskRunGeneration) return;
      const byTask = new Map(details.map(item => [item.task_id, item]));
      state.tasks.forEach(task => {
        const row = document.querySelector(`#tasks-table tr[data-task-id="${CSS.escape(task.id)}"]`);
        if (!row) return;
        const detail = byTask.get(task.id);
        const reason = row.querySelector('.task-failure-reason');
        const logTarget = row.querySelector('.task-log-action');

        if (reason) {
          const text = detail?.failure_reason || 'Falha registrada sem mensagem detalhada.';
          reason.textContent = text;
          reason.title = text;
        }

        if (logTarget) {
          logTarget.innerHTML = '';
          if (detail?.has_log && detail.run_id) {
            const link = document.createElement('a');
            link.className = 'link task-log-link';
            link.href = detail.log_url || `/api/task-runs/${detail.run_id}`;
            link.textContent = task.status === 'failed' ? 'Ver diagnóstico' : 'Ver análise';
            link.onclick = event => {
              event.preventDefault();
              openTaskLog(detail.run_id, task);
            };
            logTarget.appendChild(link);
          } else if (task.status === 'failed') {
            const unavailable = document.createElement('small');
            unavailable.textContent = 'Sem diagnóstico';
            logTarget.appendChild(unavailable);
          }
        }
      });
    } catch (_) {
      if (generation !== taskRunGeneration) return;
      document.querySelectorAll('.task-failure-reason').forEach(node => {
        node.textContent = 'Detalhe indisponível';
      });
    }
  }

  ensureTaskFailureStyles();

  renderTasks = function renderTasksWithFailureDetails() {
    const table = $('#tasks-table');
    table.innerHTML = state.tasks.map(task => {
      const failure = task.status === 'failed'
        ? '<small class="task-failure-reason">Carregando motivo…</small>'
        : '';
      const approval = task.status === 'awaiting_approval'
        ? `<button class="primary approve" data-id="${task.id}">Aprovar</button>`
        : '';
      return `<tr data-task-id="${esc(task.id)}"><td><strong>${esc(task.title)}</strong><br><small>${new Date(task.created_at).toLocaleString('pt-BR')}</small></td><td>${esc(task.source)}</td><td><div class="task-status-stack">${status(task.status)}${failure}</div></td><td>${task.priority}</td><td><div class="task-actions">${approval}<span class="task-log-action"></span></div></td></tr>`;
    }).join('') || '<tr><td colspan="5" class="empty">Nenhuma tarefa registrada.</td></tr>';

    $$('.approve').forEach(button => {
      button.onclick = async () => {
        try {
          await api(`/tasks/${button.dataset.id}/approve`, {method: 'POST'});
          toast('Tarefa aprovada e enfileirada');
          load();
        } catch (error) {
          toast(error.message);
        }
      };
    });

    const generation = ++taskRunGeneration;
    hydrateTaskRunDetails(generation);
  };
})();
