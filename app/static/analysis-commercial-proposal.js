(() => {
  const STYLE_ID = 'devpilot-analysis-commercial-proposal-style';
  const HOURLY_MIN = 180;
  const HOURLY_MAX = 280;
  let scheduled = false;

  const SECTION_HEADINGS = [
    'resumo para o cliente',
    'o que encontramos',
    'impacto',
    'recomendações',
    'recomendacoes',
    'próximos passos',
    'proximos passos',
    'riscos',
    'evidências',
    'evidencias',
    'estimativa',
  ];

  const PROFILES = [
    {
      id: 'github_auth',
      label: 'Acesso GitHub',
      test: /github_auth|credencia(?:l|is).*github|github.*credencia(?:l|is)|acesso.*reposit[oó]rio|reposit[oó]rio.*acesso/i,
      minHours: 2,
      maxHours: 5,
      titles: ['Acesso', 'Validação', 'Retomada'],
      defaults: [
        'Corrigir a autorização ou credencial GitHub indicada no diagnóstico.',
        'Validar o acesso ao repositório e confirmar a leitura pelo DevPilot.',
        'Retomar a mesma análise e registrar o resultado para o cliente.',
      ],
    },
    {
      id: 'deploy_ci',
      label: 'Deploy / CI',
      test: /deploy|pipeline|ci\/cd|workflow|build|vercel|render|homologa[cç][aã]o/i,
      minHours: 6,
      maxHours: 16,
      titles: ['Diagnóstico', 'Correção', 'Homologação'],
      defaults: [
        'Isolar a causa da falha de build, pipeline ou implantação apontada na análise.',
        'Aplicar a correção técnica priorizada e ajustar a automação afetada.',
        'Executar homologação, evidências e validação final do fluxo.',
      ],
    },
    {
      id: 'security_auth',
      label: 'Segurança / Autorização',
      test: /rbac|autoriza[cç][aã]o|autentica[cç][aã]o|seguran[cç]a|tenant|permiss[aã]o|access control/i,
      minHours: 12,
      maxHours: 28,
      titles: ['Contenção', 'Correção', 'Validação'],
      defaults: [
        'Tratar os riscos críticos de acesso e autorização identificados na análise.',
        'Implementar os ajustes de segurança e isolamento necessários.',
        'Validar permissões, cenários de regressão e evidências de segurança.',
      ],
    },
    {
      id: 'database',
      label: 'Banco de dados',
      test: /postgres|mysql|sql|banco de dados|database|migra[cç][aã]o|schema|constraint|índice|indice/i,
      minHours: 10,
      maxHours: 26,
      titles: ['Diagnóstico', 'Correção', 'Validação'],
      defaults: [
        'Reproduzir e isolar o problema de persistência ou estrutura apontado na análise.',
        'Aplicar a correção de schema, consulta ou migração priorizada.',
        'Validar integridade, regressão e operação após a mudança.',
      ],
    },
    {
      id: 'performance',
      label: 'Performance',
      test: /performance|lentid[aã]o|travando|mem[oó]ria|cpu|timeout|lat[eê]ncia|carregamento/i,
      minHours: 8,
      maxHours: 22,
      titles: ['Medição', 'Otimização', 'Validação'],
      defaults: [
        'Medir o gargalo descrito na análise e estabelecer uma linha de base.',
        'Aplicar as otimizações de maior impacto técnico.',
        'Comparar resultados, validar regressão e documentar ganhos.',
      ],
    },
    {
      id: 'ui',
      label: 'Interface',
      test: /css|layout|interface|responsiv|mobile|scroll|bot[aã]o|tela|ux|ui\b/i,
      minHours: 5,
      maxHours: 14,
      titles: ['Ajuste', 'Refino', 'Validação'],
      defaults: [
        'Corrigir os comportamentos de interface identificados na análise.',
        'Refinar responsividade, estados e consistência visual do fluxo.',
        'Validar desktop, mobile e regressões da experiência.',
      ],
    },
  ];

  function injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .analysis-proposal-source{display:flex;align-items:center;gap:7px;margin:-4px 0 12px;padding:8px 10px;border:1px solid #1e5d59;border-radius:9px;background:#0b2627;color:#82d9cf;font-size:10px;line-height:1.4}
      .analysis-proposal-source::before{content:'↔';display:grid;place-items:center;width:20px;height:20px;border-radius:6px;background:#164b4b;color:#66ead8;font-weight:900;flex:0 0 auto}
      .analysis-proposal-context{margin:0 0 12px;padding:9px 10px;border-left:3px solid #2f8177;border-radius:0 8px 8px 0;background:#091a25;color:#9fb5ca;font-size:10px;line-height:1.45}
      .analysis-proposal-context strong{color:#dcecff}
      .analysis-proposal-card[data-analysis-linked="true"] .analysis-review-badge{border-color:#2e8f80;background:#10332e;color:#63edd7}
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

  function formatMoney(value) {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
      maximumFractionDigits: 0,
    }).format(Math.max(0, Math.round(value)));
  }

  function sourceHash(text) {
    let hash = 5381;
    for (let i = 0; i < text.length; i += 1) hash = ((hash << 5) + hash) ^ text.charCodeAt(i);
    return String(hash >>> 0);
  }

  function reportText(dialog) {
    const visible = dialog.querySelector('#task-client-report')?.innerText?.trim();
    if (visible) return visible;
    const card = dialog.querySelector('#task-client-card')?.innerText?.trim();
    return card || '';
  }

  function extractCategory(text) {
    const match = text.match(/categoria\s+(?:identificada\s*)?:\s*([a-z0-9_.-]+)/i);
    return match ? match[1].replace(/[.,;:]+$/, '').toLowerCase() : '';
  }

  function profileFor(text, category) {
    const source = `${category}\n${text}`;
    return PROFILES.find(profile => profile.test.test(source)) || {
      id: category || 'general',
      label: category ? category.replace(/[_-]+/g, ' ') : 'Análise técnica',
      minHours: 6,
      maxHours: 18,
      titles: ['Correção', 'Implementação', 'Validação'],
      defaults: [
        'Tratar o principal problema técnico identificado na análise.',
        'Implementar as melhorias priorizadas pelo diagnóstico.',
        'Executar testes, validação técnica e entrega assistida.',
      ],
    };
  }

  function explicitHourRange(text) {
    const lines = String(text || '').replace(/\r/g, '').split('\n');
    const pattern = /(\d{1,3})\s*(?:–|—|-)\s*(\d{1,3})\s*(?:h\b|horas?\b)/i;
    const total = lines.find(line => /\btotal\b/i.test(line) && pattern.test(line));
    if (total) {
      const match = total.match(pattern);
      return [Number(match[1]), Number(match[2])];
    }
    const ranges = [];
    const seen = new Set();
    for (const line of lines) {
      const match = line.match(pattern);
      if (!match) continue;
      const key = `${match[1]}-${match[2]}`;
      if (seen.has(key)) continue;
      seen.add(key);
      ranges.push([Number(match[1]), Number(match[2])]);
      if (ranges.length >= 6) break;
    }
    if (!ranges.length) return null;
    return [
      ranges.reduce((sum, range) => sum + Math.min(...range), 0),
      ranges.reduce((sum, range) => sum + Math.max(...range), 0),
    ];
  }

  function sectionLines(text, headingNames) {
    const lines = String(text || '').replace(/\r/g, '').split('\n').map(line => line.trim());
    const wanted = headingNames.map(normalize);
    const start = lines.findIndex(line => wanted.some(name => normalize(line).replace(/[:.]+$/, '') === name));
    if (start < 0) return [];
    const output = [];
    for (let index = start + 1; index < lines.length; index += 1) {
      const line = lines[index];
      if (!line) continue;
      const normalized = normalize(line).replace(/[:.]+$/, '');
      if (SECTION_HEADINGS.includes(normalized)) break;
      output.push(line);
    }
    return output;
  }

  function cleanItem(value) {
    return String(value || '')
      .replace(/^[-*•\d.)\s]+/, '')
      .replace(/\*\*/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function itemize(lines) {
    const items = [];
    for (const line of lines) {
      const chunks = line.split(/\s*[;•]\s*|(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÃÕÇ])/u);
      for (const chunk of chunks) {
        const item = cleanItem(chunk);
        if (item.length < 12) continue;
        if (!items.some(existing => normalize(existing) === normalize(item))) items.push(item);
        if (items.length >= 5) return items;
      }
    }
    return items;
  }

  function severityAdjustment(text) {
    const critical = (text.match(/\bcr[ií]tic[oa]s?\b/gi) || []).length;
    const high = (text.match(/\balt[oa]s?\b/gi) || []).length;
    if (critical >= 2) return 1.65;
    if (critical === 1) return 1.35;
    if (high >= 2) return 1.25;
    if (high === 1) return 1.12;
    return 1;
  }

  function estimate(text) {
    const category = extractCategory(text);
    const profile = profileFor(text, category);
    const explicit = explicitHourRange(text);
    const recommendations = itemize(sectionLines(text, ['recomendações', 'recomendacoes', 'próximos passos', 'proximos passos']));
    const findings = itemize(sectionLines(text, ['o que encontramos', 'riscos']));
    const impact = itemize(sectionLines(text, ['impacto']));

    let minHours;
    let maxHours;
    if (explicit) {
      [minHours, maxHours] = explicit;
    } else {
      const adjustment = severityAdjustment(text);
      const breadth = Math.min(1.45, 1 + Math.max(0, recommendations.length - 1) * 0.08 + Math.max(0, findings.length - 1) * 0.05);
      minHours = Math.ceil(profile.minHours * adjustment * breadth);
      maxHours = Math.ceil(profile.maxHours * adjustment * breadth);
    }

    minHours = Math.max(2, Math.min(240, minHours));
    maxHours = Math.max(minHours, Math.min(360, maxHours));

    const minimum = minHours * HOURLY_MIN;
    const maximum = maxHours * HOURLY_MAX;
    const average = Math.round(((minimum + maximum) / 2) / 100) * 100;
    const sourceItems = recommendations.length ? recommendations : findings.length ? findings : impact;
    const scope = profile.defaults.map((fallback, index) => sourceItems[index] || fallback);

    return {
      category,
      profile,
      minHours,
      maxHours,
      minimum,
      maximum,
      average,
      scope,
      recommendationCount: recommendations.length,
      findingCount: findings.length,
      explicitHours: Boolean(explicit),
    };
  }

  function render(dialog) {
    const proposal = dialog.querySelector('.analysis-proposal-card');
    const target = proposal?.querySelector('.analysis-proposal-content');
    if (!proposal || !target || proposal.classList.contains('analysis-incomplete')) return;

    const text = reportText(dialog);
    if (!text || text.length < 20) return;

    const hash = sourceHash(text);
    if (target.querySelector(`[data-analysis-source="${hash}"]`)) return;

    const e = estimate(text);
    const headTitle = proposal.querySelector('.analysis-proposal-head h3');
    const badge = proposal.querySelector('.analysis-review-badge');
    if (headTitle) headTitle.textContent = 'Investimento baseado na análise';
    if (badge) badge.textContent = 'BASEADA NA ANÁLISE';
    proposal.dataset.analysisLinked = 'true';

    const shares = [0.4, 0.35, 0.25];
    const phases = e.profile.titles.map((title, index) => ({
      number: String(index + 1).padStart(2, '0'),
      title,
      scope: e.scope[index],
      value: e.average * shares[index],
    }));

    const basis = e.explicitHours
      ? 'A própria análise informou a faixa de horas usada no cálculo.'
      : `Estimativa calibrada pelo tipo de problema (${e.profile.label}) e pela criticidade encontrada.`;
    const evidence = [
      e.category ? `categoria ${e.category}` : '',
      e.recommendationCount ? `${e.recommendationCount} recomendação(ões)` : '',
      e.findingCount ? `${e.findingCount} achado(s)` : '',
    ].filter(Boolean).join(' · ');

    target.innerHTML = `
      <div class="analysis-proposal-source" data-analysis-source="${hash}">Proposta vinculada ao diagnóstico exibido ao lado${evidence ? ` · ${escapeHtml(evidence)}` : ''}.</div>
      <div class="analysis-price-summary">
        <div class="analysis-price-item"><span>Faixa mínima</span><strong>${formatMoney(e.minimum)}</strong></div>
        <div class="analysis-price-item featured"><span>Valor médio</span><strong>${formatMoney(e.average)}</strong></div>
        <div class="analysis-price-item"><span>Faixa máxima</span><strong>${formatMoney(e.maximum)}</strong></div>
      </div>
      <div class="analysis-proposal-meta">
        <span>${e.minHours}–${e.maxHours} horas</span>
        <span>${formatMoney(HOURLY_MIN)}–${formatMoney(HOURLY_MAX)}/h</span>
        <span>${escapeHtml(e.profile.label)}</span>
      </div>
      <p class="analysis-proposal-context"><strong>Base do orçamento:</strong> ${escapeHtml(basis)}</p>
      <div class="analysis-proposal-phases">
        ${phases.map(phase => `<div class="analysis-proposal-phase"><b>${phase.number}</b><div><strong>${escapeHtml(phase.title)}</strong><small>${escapeHtml(String(phase.scope).slice(0, 180))}</small></div><strong>${formatMoney(phase.value)}</strong></div>`).join('')}
      </div>
      <p class="analysis-proposal-note">Escopo e valores são recalculados sempre que a análise ao lado muda. Revise premissas contratuais antes do envio ao cliente.</p>
      <div class="analysis-proposal-actions"><button type="button" class="ghost analysis-proposal-print">Imprimir proposta</button></div>`;

    const print = target.querySelector('.analysis-proposal-print');
    if (print) print.onclick = () => window.print();
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
  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['open']});
  document.addEventListener('click', schedule, true);
  document.addEventListener('devpilot:task-run-loaded', schedule);
  schedule();
})();
