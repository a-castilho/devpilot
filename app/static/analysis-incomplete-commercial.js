(() => {
  const STYLE_ID = 'devpilot-analysis-incomplete-commercial-style';
  const HOURLY_MIN = 180;
  const HOURLY_MAX = 280;
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
    render(dialog);
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
