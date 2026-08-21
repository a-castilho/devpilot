(() => {
  const FRAME_ID = 'repeatai-frame';
  const DASHBOARD_ID = 'repeatai-full-graphs';
  const STYLE_ID = 'devpilot-repeatai-full-graphs-style';
  const WINDOW_SECONDS = 30;
  const MOUSE_SAMPLE_MS = 100;
  const MAX_MOUSE_POINTS = 160;
  const MAX_CLICK_POINTS = 80;
  const MAX_INTERVALS = 40;
  const HEAT_COLS = 6;
  const HEAT_ROWS = 4;

  const keyLabels = {
    character: 'texto',
    number: 'número',
    navigation: 'navegação',
    modifier: 'modificador',
    function: 'função',
    editing: 'edição',
    enter: 'enter',
    escape: 'escape',
    space: 'espaço',
    tab: 'tab',
    other: 'outra',
  };

  function blankBucket() {
    return {mouse: 0, click: 0, scroll: 0, key: 0};
  }

  function blankData() {
    return {
      timeline: Array.from({length: WINDOW_SECONDS}, blankBucket),
      current: blankBucket(),
      mousePoints: [],
      clickPoints: [],
      heat: Array(HEAT_COLS * HEAT_ROWS).fill(0),
      keyCounts: {},
      scrollUp: 0,
      scrollDown: 0,
      scrollUpDistance: 0,
      scrollDownDistance: 0,
      intervals: [],
      lastInteractionAt: 0,
      lastMouseSampleAt: 0,
    };
  }

  function frameDocument(frame) {
    try {
      return frame?.contentDocument || frame?.contentWindow?.document || null;
    } catch (_) {
      return null;
    }
  }

  function isRecording(doc) {
    const stop = doc?.getElementById('stop');
    return Boolean(stop && !stop.disabled);
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function normalized(value, max) {
    return max > 0 ? clamp(value / max, 0, 1) : 0;
  }

  function category(event) {
    const key = String(event.key || '');
    if (/^[a-zA-Z]$/.test(key)) return 'character';
    if (/^[0-9]$/.test(key)) return 'number';
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageUp', 'PageDown'].includes(key)) return 'navigation';
    if (['Control', 'Shift', 'Alt', 'Meta'].includes(key)) return 'modifier';
    if (/^F[0-9]+$/.test(key)) return 'function';
    if (['Backspace', 'Delete', 'Insert'].includes(key)) return 'editing';
    if (key === 'Enter') return 'enter';
    if (key === 'Escape') return 'escape';
    if (key === ' ') return 'space';
    if (key === 'Tab') return 'tab';
    return 'other';
  }

  function injectStyles(doc) {
    if (!doc?.head || doc.getElementById(STYLE_ID)) return;
    const style = doc.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #${DASHBOARD_ID}{margin-top:12px}
      .rp-full-head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:12px}
      .rp-full-head h2{margin:0;color:var(--text);font-size:14px}.rp-full-head p{margin:3px 0 0;color:var(--muted);font-size:9px;letter-spacing:.05em}.rp-full-head span{color:#3be4d0;font-size:9px;font-weight:850;white-space:nowrap}
      .rp-full-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
      .rp-full-card{min-width:0;padding:12px;border:1px solid #20374f;border-radius:11px;background:#071421;overflow:hidden}
      .rp-full-card.wide{grid-column:1/-1}
      .rp-full-card-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:9px}.rp-full-card-head strong{font-size:11px;color:#edf6ff}.rp-full-card-head small{font-size:8px;color:#7890a9;white-space:nowrap}
      .rp-full-svg{display:block;width:100%;height:170px;border-radius:8px;background:#06101b}
      .rp-full-gridline{stroke:#173047;stroke-width:1}.rp-full-axis{fill:#617b96;font:8px system-ui}.rp-full-line-mouse{fill:none;stroke:#3be4d0;stroke-width:2}.rp-full-line-click{fill:none;stroke:#67a3ff;stroke-width:2}.rp-full-line-scroll{fill:none;stroke:#ffbf69;stroke-width:2}.rp-full-line-key{fill:none;stroke:#df8cff;stroke-width:2}.rp-full-dot{fill:#b8fff6}
      .rp-full-legend{display:flex;gap:9px;flex-wrap:wrap;margin-top:8px;color:#8098b1;font-size:8px}.rp-full-legend span{display:inline-flex;align-items:center;gap:4px}.rp-full-legend i{width:7px;height:7px;border-radius:50%;display:inline-block}.rp-full-legend .mouse{background:#3be4d0}.rp-full-legend .click{background:#67a3ff}.rp-full-legend .scroll{background:#ffbf69}.rp-full-legend .key{background:#df8cff}
      .rp-full-donut-layout{display:grid;grid-template-columns:128px minmax(0,1fr);gap:12px;align-items:center;min-height:170px}.rp-full-donut{--a:0deg;--b:0deg;--c:0deg;width:122px;height:122px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(#3be4d0 0 var(--a),#67a3ff var(--a) var(--b),#ffbf69 var(--b) var(--c),#df8cff var(--c) 360deg);box-shadow:inset 0 0 0 1px #24425f}.rp-full-donut:before{content:'';grid-area:1/1;width:70px;height:70px;border-radius:50%;background:#081522;box-shadow:inset 0 0 0 1px #243d55}.rp-full-donut-center{grid-area:1/1;z-index:1;text-align:center;color:#7e97af;font-size:8px}.rp-full-donut-center b{display:block;color:#f0f7ff;font-size:21px;line-height:1.05}
      .rp-full-stats{display:grid;gap:6px}.rp-full-stat{display:grid;grid-template-columns:8px minmax(0,1fr) auto;gap:6px;align-items:center;color:#8da4bc;font-size:8px}.rp-full-stat i{width:7px;height:7px;border-radius:50%}.rp-full-stat b{color:#dbe8f5;font-size:9px;font-variant-numeric:tabular-nums}.rp-full-stat .mouse{background:#3be4d0}.rp-full-stat .click{background:#67a3ff}.rp-full-stat .scroll{background:#ffbf69}.rp-full-stat .key{background:#df8cff}
      .rp-full-heat{display:grid;grid-template-columns:repeat(${HEAT_COLS},1fr);gap:3px;height:170px;padding:8px;border:1px solid #132b40;border-radius:8px;background:#06101b}.rp-full-heat span{display:grid;place-items:center;border-radius:4px;background:rgba(59,228,208,var(--heat-alpha,.04));box-shadow:inset 0 0 0 1px rgba(59,228,208,.08);color:#d5fffa;font-size:7px;min-width:0}
      .rp-full-bars{display:grid;gap:7px;min-height:170px;align-content:center}.rp-full-bar{display:grid;grid-template-columns:72px minmax(0,1fr) 28px;gap:7px;align-items:center}.rp-full-bar label{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#8ea3bc;font-size:8px}.rp-full-bar-track{height:12px;border-radius:4px;background:#0a1b2a;box-shadow:inset 0 0 0 1px #173047;overflow:hidden}.rp-full-bar-fill{display:block;height:100%;min-width:2px;border-radius:4px;background:linear-gradient(90deg,#3be4d0,#67a3ff)}.rp-full-bar b{color:#e9f4ff;text-align:right;font-size:9px;font-variant-numeric:tabular-nums}
      .rp-full-scroll{display:grid;grid-template-columns:1fr 1fr;gap:8px;min-height:170px;align-items:end}.rp-full-scroll-col{display:grid;grid-template-rows:minmax(18px,1fr) auto auto;gap:5px;align-items:end;text-align:center}.rp-full-scroll-bar{width:min(72px,72%);justify-self:center;min-height:4px;border-radius:7px 7px 3px 3px;background:linear-gradient(180deg,#3be4d0,#287e80)}.rp-full-scroll-col.down .rp-full-scroll-bar{background:linear-gradient(180deg,#67a3ff,#2e5f9d)}.rp-full-scroll-col b{font-size:16px;color:#eef7ff}.rp-full-scroll-col span{font-size:8px;color:#8199b1}
      .rp-full-map{position:relative;height:170px;border:1px solid #132b40;border-radius:8px;background:linear-gradient(90deg,transparent 49.7%,#173047 50%,transparent 50.3%),linear-gradient(transparent 49.7%,#173047 50%,transparent 50.3%),#06101b;overflow:hidden}.rp-full-map-path{position:absolute;inset:0;width:100%;height:100%}.rp-full-map-path polyline{fill:none;stroke:#3be4d0;stroke-width:1.7;vector-effect:non-scaling-stroke;opacity:.85}.rp-full-click-dot{position:absolute;width:8px;height:8px;margin:-4px 0 0 -4px;border-radius:50%;background:#67a3ff;box-shadow:0 0 0 3px rgba(103,163,255,.16)}
      .rp-full-rhythm-note{display:flex;justify-content:space-between;gap:8px;margin-top:7px;color:#70889f;font-size:8px}.rp-full-rhythm-note b{color:#d7e8f7}
      @media(max-width:700px){.rp-full-grid{grid-template-columns:1fr}.rp-full-card.wide{grid-column:auto}.rp-full-donut-layout{grid-template-columns:112px minmax(0,1fr)}.rp-full-donut{width:108px;height:108px}.rp-full-donut:before{width:62px;height:62px}}
      @media(max-width:480px){.rp-full-card{padding:10px}.rp-full-svg,.rp-full-heat,.rp-full-map{height:145px}.rp-full-donut-layout{min-height:145px}.rp-full-bars,.rp-full-scroll{min-height:145px}.rp-full-bar{grid-template-columns:64px minmax(0,1fr) 24px}}
    `;
    doc.head.appendChild(style);
  }

  function dashboardMarkup() {
    return `
      <article class="panel" id="${DASHBOARD_ID}" data-repeatai-graphs="full">
        <div class="rp-full-head">
          <div><h2>Painel gráfico RepetAI</h2><p>VISUALIZAÇÃO COMPLETA DOS SINAIS ORIGINAIS · SEM BIBLIOTECAS EXTERNAS</p></div>
          <span id="rp-full-live">aguardando captura</span>
        </div>
        <div class="rp-full-grid">
          <section class="rp-full-card wide">
            <div class="rp-full-card-head"><strong>Linha do tempo por evento</strong><small>últimos 30 s</small></div>
            <svg id="rp-timeline" class="rp-full-svg" viewBox="0 0 700 170" preserveAspectRatio="none" aria-label="Linha do tempo de eventos"></svg>
            <div class="rp-full-legend"><span><i class="mouse"></i>mouse</span><span><i class="click"></i>cliques</span><span><i class="scroll"></i>scroll</span><span><i class="key"></i>teclado</span></div>
          </section>
          <section class="rp-full-card">
            <div class="rp-full-card-head"><strong>Distribuição dos eventos</strong><small>sessão atual</small></div>
            <div id="rp-event-mix" class="rp-full-donut-layout"></div>
          </section>
          <section class="rp-full-card">
            <div class="rp-full-card-head"><strong>Mapa de calor</strong><small>mouse + cliques</small></div>
            <div id="rp-heatmap" class="rp-full-heat" aria-label="Mapa de calor de interação"></div>
          </section>
          <section class="rp-full-card">
            <div class="rp-full-card-head"><strong>Trajetória e cliques</strong><small>coordenadas normalizadas</small></div>
            <div id="rp-pointer-map" class="rp-full-map" aria-label="Trajetória de mouse e cliques"></div>
          </section>
          <section class="rp-full-card">
            <div class="rp-full-card-head"><strong>Categorias de teclado</strong><small>conteúdo nunca armazenado</small></div>
            <div id="rp-key-bars" class="rp-full-bars"></div>
          </section>
          <section class="rp-full-card">
            <div class="rp-full-card-head"><strong>Scroll por direção</strong><small>eventos + intensidade</small></div>
            <div id="rp-scroll-balance" class="rp-full-scroll"></div>
          </section>
          <section class="rp-full-card">
            <div class="rp-full-card-head"><strong>Ritmo de interação</strong><small>intervalo entre ações</small></div>
            <svg id="rp-rhythm" class="rp-full-svg" viewBox="0 0 350 170" preserveAspectRatio="none" aria-label="Ritmo de interação"></svg>
            <div id="rp-rhythm-note" class="rp-full-rhythm-note"></div>
          </section>
        </div>
      </article>`;
  }

  function ensureDashboard(doc) {
    let dashboard = doc.getElementById(DASHBOARD_ID);
    if (dashboard) return dashboard;
    const activity = doc.getElementById('chart')?.closest('article.panel');
    if (!activity) return null;
    const holder = doc.createElement('div');
    holder.innerHTML = dashboardMarkup().trim();
    dashboard = holder.firstElementChild;
    activity.insertAdjacentElement('afterend', dashboard);
    return dashboard;
  }

  function pointFromEvent(doc, event) {
    const win = doc.defaultView;
    return {
      x: normalized(Number(event.clientX) || 0, win?.innerWidth || doc.documentElement.clientWidth || 1),
      y: normalized(Number(event.clientY) || 0, win?.innerHeight || doc.documentElement.clientHeight || 1),
    };
  }

  function addHeat(data, point, weight = 1) {
    const col = clamp(Math.floor(point.x * HEAT_COLS), 0, HEAT_COLS - 1);
    const row = clamp(Math.floor(point.y * HEAT_ROWS), 0, HEAT_ROWS - 1);
    data.heat[row * HEAT_COLS + col] += weight;
  }

  function recordInteraction(data) {
    const now = performance.now();
    if (data.lastInteractionAt) {
      data.intervals.push(Math.max(0, now - data.lastInteractionAt));
      if (data.intervals.length > MAX_INTERVALS) data.intervals.shift();
    }
    data.lastInteractionAt = now;
  }

  function resetData(state) {
    state.data = blankData();
    renderAll(state, true);
  }

  function pathFor(values, width, height, pad, maxValue) {
    if (!values.length) return '';
    const usableW = width - pad * 2;
    const usableH = height - pad * 2;
    const max = Math.max(1, maxValue || Math.max(...values));
    return values.map((value, index) => {
      const x = pad + (values.length === 1 ? 0 : index * usableW / (values.length - 1));
      const y = height - pad - (value / max) * usableH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  }

  function renderTimeline(doc, data) {
    const svg = doc.getElementById('rp-timeline');
    if (!svg) return;
    const width = 700;
    const height = 170;
    const pad = 22;
    const rows = data.timeline;
    const max = Math.max(4, ...rows.flatMap(row => [row.mouse, row.click, row.scroll, row.key]));
    let grid = '';
    for (let index = 0; index < 4; index += 1) {
      const y = pad + index * (height - pad * 2) / 3;
      grid += `<line class="rp-full-gridline" x1="${pad}" y1="${y.toFixed(1)}" x2="${width - pad}" y2="${y.toFixed(1)}"/>`;
    }
    const series = [
      ['mouse', 'rp-full-line-mouse'],
      ['click', 'rp-full-line-click'],
      ['scroll', 'rp-full-line-scroll'],
      ['key', 'rp-full-line-key'],
    ].map(([name, className]) => `<polyline class="${className}" points="${pathFor(rows.map(row => row[name]), width, height, pad, max)}"/>`).join('');
    svg.innerHTML = `${grid}${series}<text class="rp-full-axis" x="${pad}" y="${height - 5}">30 s atrás</text><text class="rp-full-axis" x="${width - 45}" y="${height - 5}">agora</text>`;
  }

  function renderMix(doc, data) {
    const target = doc.getElementById('rp-event-mix');
    if (!target) return;
    const totals = {
      mouse: data.timeline.reduce((sum, row) => sum + row.mouse, 0) + data.current.mouse,
      click: data.timeline.reduce((sum, row) => sum + row.click, 0) + data.current.click,
      scroll: data.timeline.reduce((sum, row) => sum + row.scroll, 0) + data.current.scroll,
      key: data.timeline.reduce((sum, row) => sum + row.key, 0) + data.current.key,
    };
    const total = totals.mouse + totals.click + totals.scroll + totals.key;
    const pct = value => total ? value / total : 0;
    const a = pct(totals.mouse) * 360;
    const b = a + pct(totals.click) * 360;
    const c = b + pct(totals.scroll) * 360;
    target.innerHTML = `
      <div class="rp-full-donut" style="--a:${a.toFixed(2)}deg;--b:${b.toFixed(2)}deg;--c:${c.toFixed(2)}deg"><div class="rp-full-donut-center"><span>Total</span><b>${total}</b><span>eventos</span></div></div>
      <div class="rp-full-stats">
        <div class="rp-full-stat"><i class="mouse"></i><span>mouse</span><b>${totals.mouse}</b></div>
        <div class="rp-full-stat"><i class="click"></i><span>cliques</span><b>${totals.click}</b></div>
        <div class="rp-full-stat"><i class="scroll"></i><span>scroll</span><b>${totals.scroll}</b></div>
        <div class="rp-full-stat"><i class="key"></i><span>teclado</span><b>${totals.key}</b></div>
      </div>`;
  }

  function renderHeatmap(doc, data) {
    const target = doc.getElementById('rp-heatmap');
    if (!target) return;
    const max = Math.max(1, ...data.heat);
    target.innerHTML = data.heat.map(value => {
      const alpha = value ? (0.08 + (value / max) * 0.82) : 0.03;
      return `<span style="--heat-alpha:${alpha.toFixed(2)}" title="${value} amostra(s)">${value || ''}</span>`;
    }).join('');
  }

  function renderPointerMap(doc, data) {
    const target = doc.getElementById('rp-pointer-map');
    if (!target) return;
    const trajectory = data.mousePoints.map(point => `${(point.x * 100).toFixed(2)},${(point.y * 100).toFixed(2)}`).join(' ');
    const clicks = data.clickPoints.slice(-MAX_CLICK_POINTS).map(point => `<span class="rp-full-click-dot" style="left:${(point.x * 100).toFixed(2)}%;top:${(point.y * 100).toFixed(2)}%"></span>`).join('');
    target.innerHTML = `<svg class="rp-full-map-path" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polyline points="${trajectory}"></polyline></svg>${clicks}`;
  }

  function renderKeys(doc, data) {
    const target = doc.getElementById('rp-key-bars');
    if (!target) return;
    const rows = Object.entries(data.keyCounts).sort((a, b) => b[1] - a[1]).slice(0, 7);
    if (!rows.length) {
      target.innerHTML = '<div class="empty">Digite durante a captura para visualizar categorias protegidas.</div>';
      return;
    }
    const max = Math.max(1, ...rows.map(([, value]) => value));
    target.innerHTML = rows.map(([name, value]) => `<div class="rp-full-bar"><label title="${keyLabels[name] || name}">${keyLabels[name] || name}</label><span class="rp-full-bar-track"><span class="rp-full-bar-fill" style="width:${Math.max(3, value / max * 100).toFixed(1)}%"></span></span><b>${value}</b></div>`).join('');
  }

  function renderScroll(doc, data) {
    const target = doc.getElementById('rp-scroll-balance');
    if (!target) return;
    const max = Math.max(1, data.scrollUpDistance, data.scrollDownDistance);
    const upHeight = Math.max(3, data.scrollUpDistance / max * 100);
    const downHeight = Math.max(3, data.scrollDownDistance / max * 100);
    target.innerHTML = `
      <div class="rp-full-scroll-col"><div class="rp-full-scroll-bar" style="height:${upHeight.toFixed(1)}%"></div><b>${data.scrollUp}</b><span>↑ para cima · ${Math.round(data.scrollUpDistance)} px</span></div>
      <div class="rp-full-scroll-col down"><div class="rp-full-scroll-bar" style="height:${downHeight.toFixed(1)}%"></div><b>${data.scrollDown}</b><span>↓ para baixo · ${Math.round(data.scrollDownDistance)} px</span></div>`;
  }

  function renderRhythm(doc, data) {
    const svg = doc.getElementById('rp-rhythm');
    const note = doc.getElementById('rp-rhythm-note');
    if (!svg || !note) return;
    const values = data.intervals.slice(-MAX_INTERVALS);
    const width = 350;
    const height = 170;
    const pad = 20;
    const max = Math.max(250, ...values);
    let grid = '';
    for (let index = 0; index < 4; index += 1) {
      const y = pad + index * (height - pad * 2) / 3;
      grid += `<line class="rp-full-gridline" x1="${pad}" y1="${y.toFixed(1)}" x2="${width - pad}" y2="${y.toFixed(1)}"/>`;
    }
    const points = pathFor(values, width, height, pad, max);
    svg.innerHTML = `${grid}<polyline class="rp-full-line-click" points="${points}"/>${values.length ? `<circle class="rp-full-dot" cx="${width - pad}" cy="${(height - pad - (values[values.length - 1] / max) * (height - pad * 2)).toFixed(1)}" r="3"/>` : ''}<text class="rp-full-axis" x="${pad}" y="${height - 5}">ações anteriores</text><text class="rp-full-axis" x="${width - 38}" y="${height - 5}">agora</text>`;
    const avg = values.length ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length) : 0;
    const min = values.length ? Math.round(Math.min(...values)) : 0;
    note.innerHTML = `<span>média <b>${avg ? `${avg} ms` : '—'}</b></span><span>mais rápido <b>${min ? `${min} ms` : '—'}</b></span>`;
  }

  function renderAll(state, force = false) {
    const {doc, data, dashboard} = state;
    if (!doc?.body || !dashboard) return;
    if (!force && state.observer && !state.visible) return;
    renderTimeline(doc, data);
    renderMix(doc, data);
    renderHeatmap(doc, data);
    renderPointerMap(doc, data);
    renderKeys(doc, data);
    renderScroll(doc, data);
    renderRhythm(doc, data);
    const live = doc.getElementById('rp-full-live');
    if (live) live.textContent = isRecording(doc) ? '● ao vivo · 1 s' : 'sessão pausada';
  }

  function rollSecond(state) {
    state.data.timeline.push({...state.data.current});
    state.data.timeline.shift();
    state.data.current = blankBucket();
    renderAll(state);
  }

  function bindObserver(state) {
    const win = state.doc.defaultView;
    if (!win || !('IntersectionObserver' in win)) {
      state.visible = true;
      return;
    }
    state.observer?.disconnect();
    state.observer = new win.IntersectionObserver(entries => {
      state.visible = entries.some(entry => entry.isIntersecting);
      if (state.visible) renderAll(state, true);
    }, {threshold: 0.05});
    state.observer.observe(state.dashboard);
  }

  function bindEvents(state) {
    const {doc} = state;
    if (doc.documentElement.dataset.repeataiFullGraphsBound === '1') return;
    doc.documentElement.dataset.repeataiFullGraphsBound = '1';

    doc.addEventListener('mousemove', event => {
      if (!isRecording(doc)) return;
      const now = performance.now();
      if (now - state.data.lastMouseSampleAt < MOUSE_SAMPLE_MS) return;
      state.data.lastMouseSampleAt = now;
      const point = pointFromEvent(doc, event);
      state.data.mousePoints.push(point);
      if (state.data.mousePoints.length > MAX_MOUSE_POINTS) state.data.mousePoints.shift();
      addHeat(state.data, point, 1);
      state.data.current.mouse += 1;
    }, {passive: true});

    doc.addEventListener('click', event => {
      if (!isRecording(doc)) return;
      const point = pointFromEvent(doc, event);
      state.data.clickPoints.push(point);
      if (state.data.clickPoints.length > MAX_CLICK_POINTS) state.data.clickPoints.shift();
      addHeat(state.data, point, 4);
      state.data.current.click += 1;
      recordInteraction(state.data);
    }, {passive: true});

    doc.addEventListener('wheel', event => {
      if (!isRecording(doc)) return;
      const delta = Number(event.deltaY) || 0;
      if (delta < 0) {
        state.data.scrollUp += 1;
        state.data.scrollUpDistance += Math.abs(delta);
      } else if (delta > 0) {
        state.data.scrollDown += 1;
        state.data.scrollDownDistance += Math.abs(delta);
      }
      state.data.current.scroll += 1;
      recordInteraction(state.data);
    }, {passive: true});

    doc.addEventListener('keydown', event => {
      if (!isRecording(doc)) return;
      const type = category(event);
      state.data.keyCounts[type] = (state.data.keyCounts[type] || 0) + 1;
      state.data.current.key += 1;
      recordInteraction(state.data);
    }, {passive: true});

    doc.getElementById('start')?.addEventListener('click', () => {
      window.setTimeout(() => {
        if (isRecording(doc)) {
          resetData(state);
          const live = doc.getElementById('rp-full-live');
          if (live) live.textContent = '● ao vivo · 1 s';
        }
      }, 0);
    });

    doc.getElementById('reset')?.addEventListener('click', () => window.setTimeout(() => resetData(state), 0));
    doc.getElementById('stop')?.addEventListener('click', () => window.setTimeout(() => renderAll(state, true), 0));
  }

  function install(frame) {
    const doc = frameDocument(frame);
    if (!doc?.body) return false;
    injectStyles(doc);
    const dashboard = ensureDashboard(doc);
    if (!dashboard) return false;

    const existing = frame.__repeataiFullGraphState;
    if (existing?.doc === doc) {
      renderAll(existing, true);
      return true;
    }

    if (existing?.timer) clearInterval(existing.timer);
    existing?.observer?.disconnect?.();

    const state = {
      doc,
      dashboard,
      data: blankData(),
      visible: true,
      observer: null,
      timer: null,
    };
    frame.__repeataiFullGraphState = state;
    bindEvents(state);
    bindObserver(state);
    state.timer = window.setInterval(() => rollSecond(state), 1000);
    renderAll(state, true);
    return true;
  }

  function bindFrame(frame) {
    if (!frame || frame.dataset.fullGraphsPrepared === '1') return;
    frame.dataset.fullGraphsPrepared = '1';
    frame.addEventListener('load', () => window.setTimeout(() => install(frame), 40));
    install(frame);
  }

  function prepare() {
    const frame = document.getElementById(FRAME_ID);
    if (!frame) return false;
    bindFrame(frame);
    return true;
  }

  if (!prepare()) {
    const observer = new MutationObserver(() => {
      if (prepare()) observer.disconnect();
    });
    observer.observe(document.documentElement, {childList: true, subtree: true});
  }

  document.addEventListener('click', event => {
    if (!event.target.closest?.('[data-example-project="repeatai"]')) return;
    window.setTimeout(prepare, 0);
  }, {passive: true});
})();
