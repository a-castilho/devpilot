(() => {
  const TABLE_ID = 'tasks-table';
  const COMPLETE_AT = 0.88;
  const PREVIEW_DIALOG_ID = 'approval-correction-preview';

  function injectStyles() {
    if (document.getElementById('approval-slider-styles')) return;
    const style = document.createElement('style');
    style.id = 'approval-slider-styles';
    style.textContent = `
      .approval-slider{
        --slide:0px;
        --slide-pct:0%;
        position:relative;
        width:100%;
        min-width:0;
        max-width:260px;
        height:48px;
        box-sizing:border-box;
        border:1px solid #29445f;
        border-radius:999px;
        overflow:hidden;
        background:#081522;
        box-shadow:inset 0 0 0 1px rgba(255,255,255,.02);
        touch-action:pan-y;
        user-select:none;
        -webkit-user-select:none;
        transition:border-color .2s ease,background .2s ease,box-shadow .2s ease
      }
      .approval-slider-fill{
        position:absolute;
        inset:0 auto 0 0;
        width:var(--slide-pct);
        pointer-events:none;
        background:linear-gradient(90deg,#18b89c,#35df94);
        opacity:.35;
        transition:width .08s linear,opacity .2s ease
      }
      .approval-slider-label{
        position:absolute;
        inset:0 8px 0 50px;
        min-width:0;
        overflow:hidden;
        text-overflow:ellipsis;
        display:flex;
        align-items:center;
        justify-content:center;
        color:#a8bbcf;
        font-size:10px;
        font-weight:850;
        letter-spacing:.04em;
        text-transform:uppercase;
        pointer-events:none;
        white-space:nowrap;
        transition:color .2s ease
      }
      .approval-slider .approve{
        position:absolute!important;
        z-index:2;
        left:5px!important;
        top:5px!important;
        width:38px!important;
        min-width:38px!important;
        max-width:38px!important;
        height:38px!important;
        min-height:38px!important;
        padding:0!important;
        margin:0!important;
        border:0!important;
        border-radius:50%!important;
        display:grid!important;
        place-items:center!important;
        transform:translateX(var(--slide));
        background:linear-gradient(135deg,#38e0d2,#45aef8)!important;
        color:#06111b!important;
        box-shadow:0 7px 18px rgba(40,187,223,.28)!important;
        font-size:0!important;
        cursor:grab!important;
        touch-action:none!important;
        transition:transform .18s ease,background .2s ease,box-shadow .2s ease
      }
      .approval-slider .approve::before{
        content:'›';
        font-size:28px;
        font-weight:900;
        line-height:1;
        transform:translateY(-1px)
      }
      .approval-slider.dragging .approve{
        cursor:grabbing!important;
        transition:none
      }
      .approval-slider.dragging .approval-slider-fill{transition:none}
      .approval-slider.approved{
        border-color:#38dd8a;
        background:#09251c;
        box-shadow:0 0 0 3px rgba(56,221,138,.09),0 0 24px rgba(56,221,138,.12)
      }
      .approval-slider.approved .approval-slider-fill{
        width:100%!important;
        opacity:.6
      }
      .approval-slider.approved .approval-slider-label{
        inset:0 64px 0 16px;
        color:#d9ffea
      }
      .approval-slider.approved .approve{
        background:linear-gradient(135deg,#39e391,#20b86e)!important;
        color:#052014!important;
        box-shadow:0 7px 18px rgba(32,184,110,.28)!important
      }
      .approval-slider.approved .approve::before{
        content:'✓';
        font-size:23px
      }
      .approval-slider.error{
        border-color:#ff6577;
        box-shadow:0 0 0 3px rgba(255,101,119,.08)
      }
      .task-actions:has(.approval-slider){width:100%;max-width:260px;min-width:0;overflow:visible}
      .approval-preview-button{
        width:100%;
        max-width:260px;
        min-height:40px;
        margin:0 0 9px;
        padding:9px 12px;
        border:1px solid #35536f;
        border-radius:11px;
        background:#0b1b2b;
        color:#c9d8e8;
        font:inherit;
        font-size:10px;
        font-weight:850;
        letter-spacing:.045em;
        text-transform:uppercase;
        cursor:pointer;
        transition:border-color .18s ease,color .18s ease,background .18s ease
      }
      .approval-preview-button:hover,.approval-preview-button:focus-visible{
        border-color:#43d7c5;
        color:#6debdc;
        background:#0e2635;
        outline:none
      }
      #${PREVIEW_DIALOG_ID}{
        width:min(720px,calc(100vw - 24px));
        max-width:calc(100vw - 24px);
        max-height:min(88vh,760px);
        padding:0;
        border:1px solid #29445f;
        border-radius:18px;
        background:#07111c;
        color:#edf6ff;
        box-shadow:0 24px 80px rgba(0,0,0,.72)
      }
      #${PREVIEW_DIALOG_ID}::backdrop{background:rgba(0,0,0,.76);backdrop-filter:blur(3px)}
      .approval-preview-panel{display:grid;grid-template-rows:auto minmax(0,1fr) auto;max-height:min(88vh,760px);min-width:0}
      .approval-preview-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding:18px 18px 14px;border-bottom:1px solid #20364b}
      .approval-preview-eyebrow{display:block;margin-bottom:6px;color:#6fe9d9;font-size:10px;font-weight:900;letter-spacing:.09em;text-transform:uppercase}
      .approval-preview-head h3{margin:0;color:#f3f8ff;font-size:18px;line-height:1.3;overflow-wrap:anywhere}
      .approval-preview-close{width:40px;height:40px;flex:0 0 40px;padding:0;border:1px solid #31485f;border-radius:11px;background:#0c1a28;color:#dce8f5;font-size:22px;cursor:pointer}
      .approval-preview-body{min-width:0;overflow:auto;padding:16px 18px 20px}
      .approval-preview-section{padding:13px 14px;border:1px solid #203a51;border-radius:12px;background:#091725}
      .approval-preview-section+.approval-preview-section{margin-top:12px}
      .approval-preview-section strong{display:block;margin-bottom:7px;color:#8fa6be;font-size:10px;font-weight:900;letter-spacing:.07em;text-transform:uppercase}
      .approval-preview-section pre{margin:0;color:#e7f0fa;font:inherit;font-size:13px;line-height:1.55;white-space:pre-wrap;overflow-wrap:anywhere}
      .approval-preview-empty{margin:0;color:#91a4b8;font-size:13px;line-height:1.5}
      .approval-preview-note{margin:12px 2px 0;color:#758ba2;font-size:10px;line-height:1.45}
      .approval-preview-footer{display:flex;justify-content:flex-end;padding:13px 18px;border-top:1px solid #20364b}
      .approval-preview-footer button{min-height:40px;padding:9px 15px;border:1px solid #31536e;border-radius:10px;background:#102337;color:#dceafa;font:inherit;font-size:11px;font-weight:800;cursor:pointer}
      @media(max-width:1100px) and (min-width:821px){
        .approval-slider,.approval-preview-button{max-width:180px}
        .approval-slider{height:44px}
        .approval-slider .approve{width:34px!important;min-width:34px!important;max-width:34px!important;height:34px!important;min-height:34px!important}
        .approval-slider-label{inset:0 6px 0 44px;font-size:8px;letter-spacing:.02em}
        .approval-preview-button{font-size:8px}
      }
      @media(max-width:820px){
        .approval-slider,.approval-preview-button{width:100%;max-width:100%}
        .task-actions:has(.approval-slider){max-width:100%}
        .approval-slider{height:58px}
        .approval-slider .approve{width:48px!important;min-width:48px!important;max-width:48px!important;height:48px!important;min-height:48px!important}
        .approval-slider-label{inset:0 12px 0 66px;font-size:11px}
        .approval-preview-button{min-height:46px;margin-bottom:10px;font-size:11px}
        .approval-preview-head{padding:16px 14px 12px}.approval-preview-body{padding:14px}.approval-preview-footer{padding:12px 14px}
      }
    `;
    document.head.appendChild(style);
  }

  function setProgress(slider, px) {
    const thumb = slider.querySelector('.approve');
    if (!thumb) return 0;
    const max = Math.max(0, slider.clientWidth - thumb.offsetWidth - 10);
    const value = Math.max(0, Math.min(max, px));
    const pct = max ? (value / max) * 100 : 0;
    slider.style.setProperty('--slide', `${value}px`);
    slider.style.setProperty('--slide-pct', `${pct}%`);
    slider.setAttribute('aria-valuenow', String(Math.round(pct)));
    return max ? value / max : 0;
  }

  function reset(slider) {
    slider.classList.remove('dragging', 'approved', 'error');
    slider.dataset.approving = '0';
    const label = slider.querySelector('.approval-slider-label');
    if (label) label.textContent = 'Deslize para aprovar';
    setProgress(slider, 0);
  }

  async function approve(slider) {
    if (slider.dataset.approving === '1') return;
    const button = slider.querySelector('.approve');
    const id = button?.dataset.id;
    if (!button || !id) return reset(slider);

    slider.dataset.approving = '1';
    slider.classList.remove('dragging', 'error');
    slider.classList.add('approved');
    const max = Math.max(0, slider.clientWidth - button.offsetWidth - 10);
    setProgress(slider, max);
    const label = slider.querySelector('.approval-slider-label');
    if (label) label.textContent = 'Aprovando…';
    button.disabled = true;

    try {
      if (typeof window.api !== 'function') throw new Error('API de aprovação indisponível');
      await window.api(`/tasks/${id}/approve`, {method:'POST'});
      if (label) label.textContent = 'Aprovado';
      if (typeof window.toast === 'function') window.toast('Tarefa aprovada e enfileirada');
      await new Promise(resolve => setTimeout(resolve, 350));
      if (typeof window.load === 'function') await window.load();
    } catch (error) {
      slider.classList.remove('approved');
      slider.classList.add('error');
      if (label) label.textContent = 'Falhou · tente novamente';
      button.disabled = false;
      if (typeof window.toast === 'function') window.toast(error?.message || 'Falha ao aprovar tarefa');
      setTimeout(() => reset(slider), 1300);
    }
  }

  function previewDialog() {
    let dialog = document.getElementById(PREVIEW_DIALOG_ID);
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.id = PREVIEW_DIALOG_ID;
    dialog.innerHTML = `
      <div class="approval-preview-panel">
        <header class="approval-preview-head">
          <div><span class="approval-preview-eyebrow">ANTES DE APROVAR</span><h3 id="approval-preview-title">Correção proposta</h3></div>
          <button type="button" class="approval-preview-close" aria-label="Fechar">×</button>
        </header>
        <div class="approval-preview-body" id="approval-preview-body"></div>
        <footer class="approval-preview-footer"><button type="button" class="approval-preview-ok">Fechar</button></footer>
      </div>`;
    document.body.appendChild(dialog);
    const close = () => dialog.close();
    dialog.querySelector('.approval-preview-close').addEventListener('click', close);
    dialog.querySelector('.approval-preview-ok').addEventListener('click', close);
    dialog.addEventListener('click', event => { if (event.target === dialog) close(); });
    return dialog;
  }

  async function resolveTask(id) {
    if (!id) return null;
    try {
      if (typeof state !== 'undefined' && Array.isArray(state.tasks)) {
        const local = state.tasks.find(item => String(item.id) === String(id));
        if (local) return local;
      }
    } catch (_) {}
    try {
      if (typeof window.api !== 'function') return null;
      const tasks = await window.api('/tasks?limit=500');
      return Array.isArray(tasks) ? tasks.find(item => String(item.id) === String(id)) || null : null;
    } catch (_) {
      return null;
    }
  }

  function splitCorrectionPrompt(prompt) {
    const raw = String(prompt || '').trim();
    if (!raw) return {instructions:'', diagnosis:''};
    const cleaned = raw.replace(/^\[analysis-run:[^\]]+\]\s*/i, '').trim();
    const marker = /\n\s*DIAGN[ÓO]STICO:\s*\n/i;
    const match = cleaned.match(marker);
    if (!match || match.index == null) return {instructions:cleaned, diagnosis:''};
    return {
      instructions: cleaned.slice(0, match.index).trim(),
      diagnosis: cleaned.slice(match.index + match[0].length).trim(),
    };
  }

  async function showCorrectionPreview(button) {
    const id = button.dataset.id;
    const dialog = previewDialog();
    const title = dialog.querySelector('#approval-preview-title');
    const body = dialog.querySelector('#approval-preview-body');
    title.textContent = 'Carregando correção…';
    body.innerHTML = '<p class="approval-preview-empty">Buscando a descrição real da tarefa.</p>';
    if (!dialog.open) dialog.showModal();

    const task = await resolveTask(id);
    if (!task) {
      title.textContent = 'Correção indisponível';
      body.innerHTML = '<p class="approval-preview-empty">Não foi possível carregar esta tarefa. Nenhuma correção foi inventada.</p>';
      return;
    }

    const parts = splitCorrectionPrompt(task.prompt);
    title.textContent = task.title || 'Correção proposta';
    const sections = [];
    if (parts.instructions) sections.push(`<section class="approval-preview-section"><strong>O que será feito</strong><pre></pre></section>`);
    if (parts.diagnosis) sections.push(`<section class="approval-preview-section"><strong>Diagnóstico que orienta a correção</strong><pre></pre></section>`);
    body.innerHTML = sections.join('') || '<p class="approval-preview-empty">Esta tarefa não possui descrição de correção registrada. Revise a origem antes de aprovar.</p>';
    const pres = body.querySelectorAll('pre');
    let index = 0;
    if (parts.instructions && pres[index]) pres[index++].textContent = parts.instructions;
    if (parts.diagnosis && pres[index]) pres[index].textContent = parts.diagnosis;
    if (sections.length) {
      const note = document.createElement('p');
      note.className = 'approval-preview-note';
      note.textContent = 'Conteúdo exibido a partir da tarefa registrada. A aprovação abaixo autoriza a execução desta correção.';
      body.appendChild(note);
    }
  }

  function addPreviewButton(slider, approveButton) {
    if (!slider || !approveButton || slider.parentNode?.querySelector?.(`.approval-preview-button[data-id="${approveButton.dataset.id}"]`)) return;
    const preview = document.createElement('button');
    preview.type = 'button';
    preview.className = 'approval-preview-button';
    preview.dataset.id = approveButton.dataset.id || '';
    preview.textContent = 'Ver qual correção será feita';
    preview.setAttribute('aria-label', 'Ver detalhes da correção antes de aprovar');
    preview.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      showCorrectionPreview(preview);
    });
    slider.parentNode.insertBefore(preview, slider);
  }

  function bind(slider) {
    if (slider.dataset.bound === '1') return;
    slider.dataset.bound = '1';
    const button = slider.querySelector('.approve');
    if (!button) return;

    let pointerId = null;
    let startX = 0;
    let startSlide = 0;

    button.setAttribute('aria-label', 'Arraste para a direita para aprovar a tarefa');
    button.title = 'Arraste para aprovar';

    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopImmediatePropagation();
    }, true);

    button.addEventListener('pointerdown', event => {
      if (slider.dataset.approving === '1') return;
      pointerId = event.pointerId;
      startX = event.clientX;
      const current = parseFloat(getComputedStyle(slider).getPropertyValue('--slide')) || 0;
      startSlide = current;
      slider.classList.add('dragging');
      button.setPointerCapture?.(pointerId);
      event.preventDefault();
    });

    button.addEventListener('pointermove', event => {
      if (pointerId !== event.pointerId || !slider.classList.contains('dragging')) return;
      setProgress(slider, startSlide + event.clientX - startX);
      event.preventDefault();
    });

    const finish = event => {
      if (pointerId === null || (event.pointerId != null && event.pointerId !== pointerId)) return;
      const ratio = setProgress(slider, parseFloat(getComputedStyle(slider).getPropertyValue('--slide')) || 0);
      slider.classList.remove('dragging');
      pointerId = null;
      if (ratio >= COMPLETE_AT) approve(slider);
      else reset(slider);
    };

    button.addEventListener('pointerup', finish);
    button.addEventListener('pointercancel', finish);

    if ('ResizeObserver' in window) {
      const resizeObserver = new ResizeObserver(() => {
        const current = parseFloat(getComputedStyle(slider).getPropertyValue('--slide')) || 0;
        setProgress(slider, slider.classList.contains('approved') ? Number.MAX_SAFE_INTEGER : current);
      });
      resizeObserver.observe(slider);
    }

    button.addEventListener('keydown', event => {
      if (event.key === 'End' || event.key === 'ArrowRight') {
        event.preventDefault();
        const max = Math.max(0, slider.clientWidth - button.offsetWidth - 10);
        setProgress(slider, max);
        approve(slider);
      }
    });
  }

  function enhance() {
    const table = document.getElementById(TABLE_ID);
    if (!table) return;

    table.querySelectorAll('button.approve').forEach(button => {
      let slider = button.closest('.approval-slider');
      if (!slider) {
        slider = document.createElement('div');
        slider.className = 'approval-slider';
        slider.setAttribute('role', 'slider');
        slider.setAttribute('aria-label', 'Confirmação de aprovação');
        slider.setAttribute('aria-valuemin', '0');
        slider.setAttribute('aria-valuemax', '100');
        slider.setAttribute('aria-valuenow', '0');

        const fill = document.createElement('span');
        fill.className = 'approval-slider-fill';
        const label = document.createElement('span');
        label.className = 'approval-slider-label';
        label.textContent = 'Deslize para aprovar';

        button.parentNode.insertBefore(slider, button);
        slider.append(fill, label, button);
        bind(slider);
      }
      addPreviewButton(slider, button);
    });
  }

  injectStyles();
  enhance();

  const table = document.getElementById(TABLE_ID);
  if (table) {
    new MutationObserver(enhance).observe(table, {childList:true, subtree:true});
  }

  document.addEventListener('click', event => {
    if (event.target.closest?.('[data-view="tasks"]')) setTimeout(enhance, 0);
  }, {passive:true});
})();
