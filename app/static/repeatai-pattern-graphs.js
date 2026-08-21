(() => {
  const FRAME_ID = 'repeatai-frame';
  const STYLE_ID = 'devpilot-repeatai-pattern-graphs-style';
  const MAX_BARS = 7;

  function iframeDocument(frame) {
    try {
      return frame?.contentDocument || null;
    } catch (_) {
      return null;
    }
  }

  function injectStyles(doc) {
    if (!doc || doc.getElementById(STYLE_ID)) return;
    const style = doc.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      .pattern-dashboard-subtitle{margin:4px 0 0;color:var(--muted);font-size:10px;line-height:1.4}
      .pattern-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:0 0 12px}
      .pattern-kpi{min-width:0;padding:12px;border:1px solid #29425d;border-radius:11px;background:linear-gradient(145deg,#0b1827,#0b1420)}
      .pattern-kpi span{display:block;color:#8ea3bc;font-size:9px;text-transform:uppercase;letter-spacing:.08em}
      .pattern-kpi strong{display:block;margin-top:5px;color:#f2f8ff;font-size:20px;line-height:1.1}
      .pattern-kpi small{display:block;margin-top:4px;color:#718aa4;font-size:9px}
      .pattern-kpi.accent{border-color:#2d776f;background:linear-gradient(145deg,#0c2827,#0a1821)}
      .pattern-kpi.accent strong{color:#63edd8}
      .pattern-dashboard-grid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(210px,.8fr);gap:11px;align-items:stretch}
      .pattern-chart-card{min-width:0;padding:13px;border:1px solid #223a53;border-radius:11px;background:#081421}
      .pattern-chart-head{display:flex;align-items:center;justify-content:space-between;gap:9px;margin-bottom:12px}
      .pattern-chart-head strong{color:#eef6ff;font-size:12px}
      .pattern-chart-head span{padding:4px 7px;border-radius:999px;background:#102238;color:#8fa7c0;font-size:8px;white-space:nowrap}
      .pattern-bars{display:grid;gap:9px}
      .pattern-bar-row{display:grid;grid-template-columns:minmax(104px,1.05fr) minmax(120px,2fr) 28px;gap:8px;align-items:center;min-width:0}
      .pattern-bar-label{min-width:0;color:#d9e8f8;font-size:9px;font-weight:750;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .pattern-bar-track{position:relative;height:15px;border-radius:4px;background:#0b1b2a;overflow:hidden;box-shadow:inset 0 0 0 1px #173047}
      .pattern-bar-fill{display:block;height:100%;min-width:3px;border-radius:4px;background:linear-gradient(90deg,#28bba8,#47e5d2);box-shadow:0 0 14px rgba(59,228,208,.15)}
      .pattern-bar-value{color:#f4f8ff;font-size:10px;font-weight:900;text-align:right;font-variant-numeric:tabular-nums}
      .pattern-axis{display:grid;grid-template-columns:minmax(104px,1.05fr) minmax(120px,2fr) 28px;gap:8px;margin-top:9px;color:#627b96;font-size:8px}
      .pattern-axis-scale{display:flex;justify-content:space-between;border-top:1px solid #183047;padding-top:5px}
      .pattern-donut-wrap{display:grid;place-items:center;margin:4px 0 10px}
      .pattern-donut{--down:0deg;--up:0deg;width:134px;height:134px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(#38d8c3 0 var(--down),#4e8ff5 var(--down) var(--up),#d59b54 var(--up) 360deg);box-shadow:inset 0 0 0 1px #24425f,0 10px 25px #0005}
      .pattern-donut::before{content:'';grid-area:1/1;width:76px;height:76px;border-radius:50%;background:#0a1725;box-shadow:inset 0 0 0 1px #263c54}
      .pattern-donut-center{z-index:1;grid-area:1/1;text-align:center;color:#869db6;font-size:8px}
      .pattern-donut-center strong{display:block;color:#f2f8ff;font-size:23px;line-height:1.05}
      .pattern-legend{display:grid;gap:7px;margin-top:8px}
      .pattern-legend-row{display:grid;grid-template-columns:10px minmax(0,1fr) auto;gap:6px;align-items:center;color:#9cb0c5;font-size:9px}
      .pattern-legend-row b{color:#dce9f7;font-size:9px;font-variant-numeric:tabular-nums}
      .pattern-legend-dot{width:8px;height:8px;border-radius:50%}.pattern-legend-dot.down{background:#38d8c3}.pattern-legend-dot.up{background:#4e8ff5}.pattern-legend-dot.other{background:#d59b54}
      .pattern-insight{margin-top:11px;padding:10px;border:1px solid #286e68;border-radius:9px;background:#0a2525;color:#a8dbd5;font-size:9px;line-height:1.45}
      .pattern-insight strong{display:block;margin-bottom:3px;color:#4ee5d1}
      .pattern-dashboard-footer{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-top:10px;color:#70879f;font-size:8px}
      @media(max-width:700px){.pattern-dashboard-grid{grid-template-columns:1fr}.pattern-bar-row,.pattern-axis{grid-template-columns:minmax(94px,.9fr) minmax(100px,1.7fr) 26px}}
      @media(max-width:480px){.pattern-kpis{grid-template-columns:1fr}.pattern-chart-card{padding:10px}.pattern-bar-row,.pattern-axis{grid-template-columns:86px minmax(90px,1fr) 24px}.pattern-bar-label{font-size:8px}}
    `;
    doc.head.appendChild(style);
  }

  function sequenceLabel(raw) {
    const sequence = String(raw || '').trim();
    if (!sequence) return 'padrão';
    const parts = sequence.split(/\s*→\s*/).map(item => item.trim()).filter(Boolean);
    if (parts.length > 1 && parts.every(item => item === parts[0])) {
      return `${parts[0]} ×${parts.length}`;
    }
    if (sequence.length <= 32) return sequence;
    return `${sequence.slice(0, 29)}…`;
  }

  function parseRow(row) {
    const strong = String(row.querySelector('strong')?.textContent || '');
    const small = String(row.querySelector('small')?.textContent || '');
    const occurrenceMatch = small.match(/(\d+)\s+ocorr(?:ê|e)ncia/i);
    const confidenceMatch = small.match(/confian(?:ç|c)a\s+(\d+)%/i);
    const scoreMatch = strong.match(/(\d+)%\s+potencial/i);
    const rawSequence = small.split('·')[0].trim();
    const tokens = rawSequence.split(/\s*→\s*/).map(item => item.trim()).filter(Boolean);
    return {
      label: sequenceLabel(rawSequence),
      rawSequence,
      tokens,
      occurrences: Number(occurrenceMatch?.[1] || 0),
      confidence: Number(confidenceMatch?.[1] || 0),
      score: Number(scoreMatch?.[1] || 0),
      trajectory: /trajet[oó]ria/i.test(strong),
    };
  }

  function distribution(patterns) {
    const result = {down: 0, up: 0, other: 0};
    for (const pattern of patterns) {
      const tokens = pattern.tokens;
      if (tokens.length && tokens.every(token => token === 'scroll_down')) result.down += pattern.occurrences;
      else if (tokens.length && tokens.every(token => token === 'scroll_up')) result.up += pattern.occurrences;
      else result.other += pattern.occurrences;
    }
    return result;
  }

  function pct(value, total) {
    if (!total) return 0;
    return Math.round((value / total) * 1000) / 10;
  }

  function renderDashboard(doc, rows) {
    const summary = doc.getElementById('analysisSummary');
    const patternsTarget = doc.getElementById('patterns');
    const panel = patternsTarget?.closest('.panel.patterns');
    if (!summary || !patternsTarget || !panel || !rows.length) return;

    const parsed = rows.map(parseRow).filter(item => item.occurrences > 0);
    if (!parsed.length) return;

    const visible = parsed.slice(0, MAX_BARS);
    const maxOccurrence = Math.max(1, ...visible.map(item => item.occurrences));
    const confidence = Math.round(visible.reduce((total, item) => total + item.confidence, 0) / visible.length);
    const dist = distribution(visible);
    const totalOccurrences = dist.down + dist.up + dist.other;
    const downPct = pct(dist.down, totalOccurrences);
    const upPct = pct(dist.up, totalOccurrences);
    const otherPct = Math.max(0, Math.round((100 - downPct - upPct) * 10) / 10);
    const downDeg = (downPct / 100) * 360;
    const upDeg = downDeg + (upPct / 100) * 360;

    const head = panel.querySelector('.panel-head > div');
    if (head && !head.querySelector('.pattern-dashboard-subtitle')) {
      const subtitle = doc.createElement('p');
      subtitle.className = 'pattern-dashboard-subtitle';
      subtitle.textContent = 'Visualização gráfica dos padrões de automação identificados';
      head.appendChild(subtitle);
    }

    summary.innerHTML = `
      <div class="pattern-kpis">
        <div class="pattern-kpi"><span>Maior ocorrência</span><strong>${maxOccurrence}</strong><small>ocorrências no padrão líder</small></div>
        <div class="pattern-kpi accent"><span>Confiança média</span><strong>${confidence}%</strong><small>nos padrões exibidos</small></div>
        <div class="pattern-kpi"><span>Padrões listados</span><strong>${visible.length}</strong><small>no gráfico atual</small></div>
      </div>`;

    const bars = visible.map(pattern => {
      const width = Math.max(3, (pattern.occurrences / maxOccurrence) * 100);
      const title = `${pattern.rawSequence} · ${pattern.occurrences} ocorrências · ${pattern.confidence}% confiança · ${pattern.score}% automação`;
      return `<div class="pattern-bar-row" title="${title.replaceAll('"', '&quot;')}">
        <span class="pattern-bar-label">${pattern.label}</span>
        <span class="pattern-bar-track"><span class="pattern-bar-fill" style="width:${width.toFixed(1)}%"></span></span>
        <strong class="pattern-bar-value">${pattern.occurrences}</strong>
      </div>`;
    }).join('');

    const legend = [
      ['down', 'scroll_down', dist.down, downPct],
      ['up', 'scroll_up', dist.up, upPct],
      ['other', 'outros', dist.other, otherPct],
    ].filter(item => item[2] > 0).map(item => `
      <div class="pattern-legend-row"><span class="pattern-legend-dot ${item[0]}"></span><span>${item[1]}</span><b>${item[2]} (${String(item[3]).replace('.', ',')}%)</b></div>`).join('');

    const dominant = [
      {label: 'scroll_down', value: dist.down, percent: downPct},
      {label: 'scroll_up', value: dist.up, percent: upPct},
      {label: 'outros padrões', value: dist.other, percent: otherPct},
    ].sort((a, b) => b.value - a.value)[0];

    patternsTarget.innerHTML = `
      <div class="pattern-dashboard-grid">
        <section class="pattern-chart-card">
          <div class="pattern-chart-head"><strong>Ocorrências por padrão</strong><span>Top ${visible.length}</span></div>
          <div class="pattern-bars">${bars}</div>
          <div class="pattern-axis"><span></span><span class="pattern-axis-scale"><span>0</span><span>${Math.ceil(maxOccurrence / 2)}</span><span>${maxOccurrence}</span></span><span></span></div>
        </section>
        <section class="pattern-chart-card">
          <div class="pattern-chart-head"><strong>Resumo visual</strong><span>Distribuição</span></div>
          <div class="pattern-donut-wrap">
            <div class="pattern-donut" style="--down:${downDeg.toFixed(2)}deg;--up:${upDeg.toFixed(2)}deg">
              <div class="pattern-donut-center"><span>Total</span><strong>${totalOccurrences}</strong><span>ocorrências</span></div>
            </div>
          </div>
          <div class="pattern-legend">${legend}</div>
          <div class="pattern-insight"><strong>✦ Insight</strong>${dominant.label} representa ${String(dominant.percent).replace('.', ',')}% das ocorrências exibidas.</div>
        </section>
      </div>
      <div class="pattern-dashboard-footer"><span>Análise baseada nos padrões detectados nesta sessão</span><span>gráfico atualizado automaticamente</span></div>`;
  }

  function installInFrame(frame) {
    const doc = iframeDocument(frame);
    if (!doc?.body) return;
    injectStyles(doc);

    const target = doc.getElementById('patterns');
    if (!target || target.dataset.graphObserverBound === '1') return;
    target.dataset.graphObserverBound = '1';

    let scheduled = false;
    const refresh = () => {
      scheduled = false;
      const rows = [...target.querySelectorAll('.pattern-row')];
      if (!rows.length) return;
      const hasAnalysis = rows.some(row => /potencial de automa[cç][aã]o/i.test(row.textContent || ''));
      if (!hasAnalysis) return;
      renderDashboard(doc, rows);
    };

    const schedule = () => {
      if (scheduled) return;
      scheduled = true;
      frame.ownerDocument.defaultView.requestAnimationFrame(refresh);
    };

    const observer = new MutationObserver(schedule);
    observer.observe(target, {childList: true, subtree: true});
    schedule();
  }

  function bindFrame(frame) {
    if (!frame || frame.dataset.patternGraphsBound === '1') return;
    frame.dataset.patternGraphsBound = '1';
    frame.addEventListener('load', () => installInFrame(frame));
    if (frame.dataset.ready === '1') installInFrame(frame);
  }

  function locateFrame() {
    const frame = document.getElementById(FRAME_ID);
    if (!frame) return false;
    bindFrame(frame);
    return true;
  }

  if (!locateFrame()) {
    const observer = new MutationObserver(() => {
      if (locateFrame()) observer.disconnect();
    });
    observer.observe(document.documentElement, {childList: true, subtree: true});
  }
})();
