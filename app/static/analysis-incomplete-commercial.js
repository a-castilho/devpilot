(() => {
  const STYLE_ID = 'devpilot-analysis-incomplete-commercial-style';
  const HOURLY_MIN = 180;
  const HOURLY_MAX = 280;
  const RETRY_COMPLETE_AT = 0.86;
  let scheduled = false;

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .analysis-incomplete-commercial{display:grid;gap:12px;margin-top:4px;padding-top:14px;border-top:1px solid #29445f}
      .analysis-incomplete-commercial-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
      .analysis-incomplete-commercial-head strong{display:block;color:#edf7ff;font-size:13px}
      .analysis-incomplete-commercial-head small{display:block;margin-top:3px;color:#839bb3;font-size:10px;line-height:1.4}
      .analysis-incomplete-commercial-source{padding:8px 10px;border:1px solid #1e5d59;border-radius:9px;background:#0b2627;color:#82d9cf;font-size:10px;line-height:1.4}
      .analysis-incomplete-commercial .analysis-price-summary{margin:0}
      .analysis-incomplete-commercial .analysis-proposal-meta{margin:0}
      .analysis-incomplete-commercial .analysis-proposal-note{margin:0}
      .analysis-incomplete-actions.has-auto-retry-slider{width:100%}
      .analysis-auto-retry-slider{--retry-slide:0px;--retry-progress:0%;position:relative;flex:1 0 100%;width:100%;height:64px;overflow:hidden;box-sizing:border-box;border:1px solid #246d63;border-radius:18px;background:linear-gradient(135deg,#071c1e,#0a1724);box-shadow:inset 0 0 0 1px #ffffff05,0 10px 26px #0004;touch-action:pan-y;user-select:none;-webkit-user-select:none;transition:border-color .2s ease,box-shadow .2s ease,background .2s ease}
      .analysis-auto-retry-fill{position:absolute;inset:0 auto 0 0;width:var(--retry-progress);pointer-events:none;background:linear-gradient(90deg,#14b89d,#39df89);opacity:.3;transition:width .08s linear,opacity .2s ease}
      .analysis-auto-retry-label{position:absolute;inset:0 16px 0 74px;display:flex;align-items:center;justify-content:center;gap:9px;min-width:0;color:#b7cad8;font-size:11px;font-weight:850;letter-spacing:.035em;text-transform:uppercase;pointer-events:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transition:color .2s ease}
      .analysis-auto-retry-label strong{display:inline-grid;place-items:center;min-width:42px;height:24px;padding:0 8px;border:1px solid #2d8e7f;border-radius:999px;background:#0e342e;color:#61ecd5;font-size:9px;letter-spacing:.08em}
      .analysis-auto-retry-slider .analysis-retry-task{position:absolute!important;z-index:2;left:5px!important;top:5px!important;width:54px!important;min-width:54px!important;max-width:54px!important;height:54px!important;min-height:54px!important;padding:0!important;margin:0!important;border:0!important;border-radius:14px!important;display:grid!important;place-items:center!important;transform:translateX(var(--retry-slide));background:linear-gradient(135deg,#35e4d1,#3da8f5)!important;color:#06131b!important;box-shadow:0 8px 20px #25bfc34d!important;font-size:0!important;cursor:grab!important;touch-action:none!important;transition:transform .16s ease,background .2s ease,box-shadow .2s ease}
      .analysis-auto-retry-slider .analysis-retry-task::before{content:'›';font-size:34px;font-weight:950;line-height:1;transform:translateY(-1px)}
      .analysis-auto-retry-slider.dragging .analysis-retry-task{cursor:grabbing!important;transition:none}
      .analysis-auto-retry-slider.dragging .analysis-auto-retry-fill{transition:none}
      .analysis-auto-retry-slider.ready,.analysis-auto-retry-slider.running{border-color:#39dc88;background:#09251c;box-shadow:0 0 0 3px #39dc8816,0 10px 26px #0004}
      .analysis-auto-retry-slider.ready .analysis-auto-retry-fill,.analysis-auto-retry-slider.running .analysis-auto-retry-fill{opacity:.58}
      .analysis-auto-retry-slider.ready .analysis-auto-retry-label,.analysis-auto-retry-slider.running .analysis-auto-retry-label{color:#dcffea}
      .analysis-auto-retry-slider.ready .analysis-retry-task,.analysis-auto-retry-slider.running .analysis-retry-task{background:linear-gradient(135deg,#42e594,#20b86f)!important;box-shadow:0 8px 20px #20b86f45!important}
      .analysis-auto-retry-slider.ready .analysis-retry-task::before,.analysis-auto-retry-slider.running .analysis-retry-task::before{content:'✓';font-size:24px}
      .analysis-auto-retry-slider.retry-error{border-color:#ff6577;box-shadow:0 0 0 3px #ff657714}
      @media(max-width:640px){.analysis-auto-retry-slider{height:70px;border-radius:17px}.analysis-auto-retry-slider .analysis-retry-task{width:60px!important;min-width:60px!important;max-width:60px!important;height:60px!important;min-height:60px!important}.analysis-auto-retry-label{inset:0 10px 0 78px;gap:7px;font-size:10px}.analysis-auto-retry-label strong{min-width:38px;height:22px;font-size:8px}}
    `;
    document.head.appendChild(style);
  }

  function normalize(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .trim();
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function money(value) {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
      maximumFractionDigits: 0,
    }).format(Math.max(0, Math.round(value)));
  }

  function hashText(text) {
    let hash = 5381;
    for (let index = 0; index < text.length; index += 1) hash = ((hash << 5) + hash) ^ text.charCodeAt(index);
    return String(hash >>> 0);
  }

  function reportText(dialog) {
    return dialog.querySelector('#task-client-report')?.innerText?.trim()
      || dialog.querySelector('#task-client-card')?.innerText?.trim()
      || '';
  }

  function recommendation(text) {
    const lines = String(text || '').replace(/\r/g, '').split('\n').map(line => line.trim());
    const start = lines.findIndex(line => /^recomenda[cç][oõ]es?[:.]?$/i.test(line));
    if (start < 0) return '';
    const collected = [];
    for (let index = start + 1; index < lines.length; index += 1) {
      const line = lines[index];
      if (!line) continue;
      if (/^(impacto|riscos?|evid[eê]ncias?|pr[oó]ximos passos|detalhes?)[:.]?$/i.test(line)) break;
      collected.push(line.replace(/^[-*•\d.)\s]+/, '').trim());
      if (collected.join(' ').length > 180) break;
    }
    return collected.join(' ').trim();
  }

  function category(text) {
    const match = text.match(/categoria\s+(?:identificada\s*)?:\s*([a-z0-9_.-]+)/i);
    return match ? match[1].replace(/[.,;:]+$/, '').toLowerCase() : '';
  }

  function profile(text) {
    const cat = category(text);
    const source = `${cat}\n${text}`;
    if (/github_auth|credencia(?:l|is).*github|acesso.*reposit[oó]rio/i.test(source)) {
      return {
        label: 'Acesso GitHub',
        minHours: 2,
        maxHours: 5,
        titles: ['Acesso', 'Validação', 'Retomada'],
        defaults: [
          'Corrigir a autorização ou credencial GitHub indicada no diagnóstico.',
          'Validar que o DevPilot consegue acessar e ler o repositório.',
          'Retomar a mesma análise e confirmar o resultado para o cliente.',
        ],
      };
    }
    if (/deploy|pipeline|workflow|build|vercel|render/i.test(source)) {
      return {
        label: 'Deploy / CI',
        minHours: 4,
        maxHours: 10,
        titles: ['Diagnóstico', 'Correção', 'Validação'],
        defaults: [
          'Isolar o bloqueio de build, pipeline ou implantação indicado no diagnóstico.',
          'Aplicar a correção técnica necessária para liberar o fluxo.',
          'Validar a execução e registrar evidências da retomada.',
        ],
      };
    }
    if (/autentica[cç][aã]o|autoriza[cç][aã]o|rbac|seguran[cç]a|permiss[aã]o/i.test(source)) {
      return {
        label: 'Autorização / Segurança',
        minHours: 6,
        maxHours: 14,
        titles: ['Contenção', 'Correção', 'Validação'],
        defaults: [
          'Tratar o bloqueio de acesso ou autorização identificado.',
          'Aplicar a correção de segurança necessária para prosseguir.',
          'Validar permissões e retomar a análise técnica.',
        ],
      };
    }
    return {
      label: cat ? cat.replace(/[_-]+/g, ' ') : 'Diagnóstico parcial',
      minHours: 4,
      maxHours: 10,
      titles: ['Desbloqueio', 'Correção', 'Retomada'],
      defaults: [
        'Resolver o bloqueio técnico descrito no diagnóstico atual.',
        'Aplicar o ajuste necessário para permitir a continuidade da análise.',
        'Retomar a execução e validar o resultado obtido.',
      ],
    };
  }

  function setRetryProgress(slider, px) {
    const thumb = slider.querySelector('.analysis-retry-task');
    if (!thumb) return 0;
    const max = Math.max(0, slider.clientWidth - thumb.offsetWidth - 10);
    const value = Math.max(0, Math.min(max, px));
    const ratio = max ? value / max : 0;
    slider.style.setProperty('--retry-slide', `${value}px`);
    slider.style.setProperty('--retry-progress', `${ratio * 100}%`);
    slider.setAttribute('aria-valuenow', String(Math.round(ratio * 100)));
    return ratio;
  }

  function setRetryLabel(slider, text) {
    const value = slider.querySelector('.analysis-auto-retry-label span');
    if (value) value.textContent = text;
  }

  function resetRetrySlider(slider, message = 'Deslize para repetir procedimento') {
    if (!slider || slider.dataset.running === '1') return;
    slider.classList.remove('dragging', 'ready', 'running', 'retry-error');
    setRetryLabel(slider, message);
    setRetryProgress(slider, 0);
  }

  function monitorRetryOutcome(slider, button) {
    window.setTimeout(function check() {
      if (!slider.isConnected) return;
      const dialog = slider.closest('dialog');
      if (!dialog?.open) return;
      if (button.disabled) {
        window.setTimeout(check, 300);
        return;
      }
      slider.dataset.running = '0';
      slider.classList.remove('running', 'ready');
      slider.classList.add('retry-error');
      setRetryLabel(slider, 'Falhou · deslize para tentar novamente');
      setRetryProgress(slider, 0);
    }, 400);
  }

  function activateRetry(slider) {
    if (!slider || slider.dataset.running === '1') return;
    const button = slider.querySelector('.analysis-retry-task');
    if (!button || button.disabled) return resetRetrySlider(slider);

    slider.dataset.running = '1';
    slider.classList.remove('dragging', 'retry-error');
    slider.classList.add('ready', 'running');
    const max = Math.max(0, slider.clientWidth - button.offsetWidth - 10);
    setRetryProgress(slider, max);
    setRetryLabel(slider, 'Repetindo procedimento…');

    button.dataset.autoRetryArmed = '1';
    button.click();
    button.dataset.autoRetryArmed = '0';
    monitorRetryOutcome(slider, button);
  }

  function bindRetrySlider(slider) {
    if (!slider || slider.dataset.bound === '1') return;
    slider.dataset.bound = '1';
    const button = slider.querySelector('.analysis-retry-task');
    if (!button) return;

    let pointerId = null;
    let startX = 0;
    let startSlide = 0;

    button.setAttribute('aria-label', 'Arraste para a direita para repetir o procedimento automaticamente');
    button.title = 'Arraste até o fim para repetir o procedimento';

    button.addEventListener('click', event => {
      if (button.dataset.autoRetryArmed === '1') return;
      event.preventDefault();
      event.stopImmediatePropagation();
    }, true);

    button.addEventListener('pointerdown', event => {
      if (slider.dataset.running === '1' || button.disabled) return;
      pointerId = event.pointerId;
      startX = event.clientX;
      startSlide = parseFloat(getComputedStyle(slider).getPropertyValue('--retry-slide')) || 0;
      slider.classList.remove('retry-error');
      slider.classList.add('dragging');
      button.setPointerCapture?.(pointerId);
      event.preventDefault();
    });

    button.addEventListener('pointermove', event => {
      if (pointerId !== event.pointerId || !slider.classList.contains('dragging')) return;
      setRetryProgress(slider, startSlide + event.clientX - startX);
      event.preventDefault();
    });

    const finish = event => {
      if (pointerId === null || (event.pointerId != null && event.pointerId !== pointerId)) return;
      const current = parseFloat(getComputedStyle(slider).getPropertyValue('--retry-slide')) || 0;
      const ratio = setRetryProgress(slider, current);
      slider.classList.remove('dragging');
      pointerId = null;
      if (ratio >= RETRY_COMPLETE_AT) activateRetry(slider);
      else resetRetrySlider(slider);
    };

    button.addEventListener('pointerup', finish);
    button.addEventListener('pointercancel', finish);
    button.addEventListener('keydown', event => {
      if (event.key === 'Home' || event.key === 'ArrowLeft') {
        event.preventDefault();
        resetRetrySlider(slider);
      }
      if (event.key === 'End' || event.key === 'ArrowRight') {
        event.preventDefault();
        activateRetry(slider);
      }
    });
  }

  function enhanceRetrySlider(dialog) {
    const actions = dialog?.querySelector('.analysis-incomplete-actions');
    const button = actions?.querySelector(':scope > .analysis-retry-task');
    if (!actions || !button || button.closest('.analysis-auto-retry-slider')) return;

    actions.classList.add('has-auto-retry-slider');
    const slider = document.createElement('div');
    slider.className = 'analysis-auto-retry-slider';
    slider.setAttribute('role', 'slider');
    slider.setAttribute('aria-label', 'Repetir procedimento automaticamente');
    slider.setAttribute('aria-valuemin', '0');
    slider.setAttribute('aria-valuemax', '100');
    slider.setAttribute('aria-valuenow', '0');
    slider.innerHTML = '<span class="analysis-auto-retry-fill"></span><span class="analysis-auto-retry-label"><strong>AUTO</strong><span>Deslize para repetir procedimento</span></span>';

    button.parentNode.insertBefore(slider, button);
    slider.appendChild(button);
    bindRetrySlider(slider);
  }

  function render(dialog) {
    const proposal = dialog.querySelector('.analysis-proposal-card.analysis-incomplete');
    const content = proposal?.querySelector('.analysis-proposal-content');
    if (!proposal || !content) return;

    const text = reportText(dialog);
    if (!text || text.length < 20) return;
    const hash = hashText(text);
    if (content.querySelector(`[data-incomplete-commercial-source="${hash}"]`)) return;

    const p = profile(text);
    const rec = recommendation(text);
    const minimum = p.minHours * HOURLY_MIN;
    const maximum = p.maxHours * HOURLY_MAX;
    const average = Math.round(((minimum + maximum) / 2) / 100) * 100;
    const scopes = [...p.defaults];
    if (rec) scopes[0] = rec;
    const shares = [0.4, 0.35, 0.25];

    const eyebrow = proposal.querySelector('.analysis-proposal-head .eyebrow');
    const title = proposal.querySelector('.analysis-proposal-head h3');
    const badge = proposal.querySelector('.analysis-review-badge');
    if (eyebrow) eyebrow.textContent = 'PROPOSTA COMERCIAL';
    if (title) title.textContent = 'Investimento baseado no diagnóstico';
    if (badge) badge.textContent = 'DIAGNÓSTICO PARCIAL';

    const existingNote = content.querySelector('.analysis-incomplete-note');
    if (existingNote) existingNote.textContent = 'A proposta abaixo usa somente o diagnóstico disponível ao lado e será recalculada automaticamente quando a análise técnica completa for concluída.';

    const section = document.createElement('section');
    section.className = 'analysis-incomplete-commercial';
    section.dataset.incompleteCommercialSource = hash;
    section.innerHTML = `
      <div class="analysis-incomplete-commercial-head"><div><strong>Escopo comercial do bloqueio atual</strong><small>Valores proporcionais ao problema identificado, sem usar um pacote genérico de projeto.</small></div></div>
      <div class="analysis-incomplete-commercial-source">Fonte: diagnóstico exibido ao lado · ${escapeHtml(p.label)}</div>
      <div class="analysis-price-summary">
        <div class="analysis-price-item"><span>Faixa mínima</span><strong>${money(minimum)}</strong></div>
        <div class="analysis-price-item featured"><span>Valor médio</span><strong>${money(average)}</strong></div>
        <div class="analysis-price-item"><span>Faixa máxima</span><strong>${money(maximum)}</strong></div>
      </div>
      <div class="analysis-proposal-meta"><span>${p.minHours}–${p.maxHours} horas</span><span>${money(HOURLY_MIN)}–${money(HOURLY_MAX)}/h</span><span>${escapeHtml(p.label)}</span></div>
      <div class="analysis-proposal-phases">
        ${p.titles.map((phaseTitle, index) => `<div class="analysis-proposal-phase"><b>${String(index + 1).padStart(2, '0')}</b><div><strong>${escapeHtml(phaseTitle)}</strong><small>${escapeHtml(scopes[index])}</small></div><strong>${money(average * shares[index])}</strong></div>`).join('')}
      </div>
      <p class="analysis-proposal-note">Orçamento preliminar vinculado ao diagnóstico atual. Após a retomada, horas, escopo e valores são recalculados com base na análise completa.</p>`;
    content.appendChild(section);
  }

  function run() {
    scheduled = false;
    const dialog = document.getElementById('task-log-modal');
    if (!dialog?.open) return;
    enhanceRetrySlider(dialog);
    render(dialog);
    enhanceRetrySlider(dialog);
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(run);
  }

  injectStyles();
  new MutationObserver(schedule).observe(document.documentElement, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['open', 'class']});
  document.addEventListener('click', () => {
    schedule();
    window.setTimeout(schedule, 180);
    window.setTimeout(schedule, 500);
    window.setTimeout(schedule, 1100);
  }, true);
  schedule();
})();
