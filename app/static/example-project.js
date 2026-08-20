(() => {
  const NAV_LABEL = 'Exemplo de projeto';
  const EXAMPLE_URL = '/examples/repeatai/index.html';

  function injectStyles() {
    if (document.getElementById('example-project-styles')) return;
    const style = document.createElement('style');
    style.id = 'example-project-styles';
    style.textContent = `
      .example-project-shell{display:grid;gap:18px;margin-top:24px}
      .example-project-head{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;padding:22px;border:1px solid var(--line);border-radius:16px;background:linear-gradient(145deg,var(--surface),#0a1624)}
      .example-project-head h2{margin:4px 0 6px;font-size:28px}
      .example-project-head p{margin:0;color:var(--muted);max-width:760px}
      .example-project-actions{display:flex;gap:10px;flex-wrap:wrap}
      .example-project-frame-wrap{overflow:hidden;border:1px solid var(--line);border-radius:18px;background:#050b14;box-shadow:var(--shadow)}
      .example-project-frame{display:block;width:100%;height:min(76vh,820px);min-height:620px;border:0;background:#08111d}
      .example-project-note{display:flex;gap:10px;align-items:flex-start;color:var(--muted);font-size:12px}
      .example-project-note b{color:var(--cyan)}
      @media(max-width:900px){
        .example-project-head{display:grid}
        .example-project-frame{height:76vh;min-height:620px}
      }
      @media(max-width:560px){
        .example-project-head{padding:16px}
        .example-project-frame{height:74vh;min-height:580px}
        .example-project-actions{width:100%}
        .example-project-actions .primary,.example-project-actions .ghost{flex:1}
      }
    `;
    document.head.appendChild(style);
  }

  function keepRepetAIMenuVisible(frame) {
    try {
      const doc = frame.contentDocument;
      if (!doc?.head || !doc.body) return;
      let style = doc.getElementById('devpilot-repeatai-menu-fix');
      if (!style) {
        style = doc.createElement('style');
        style.id = 'devpilot-repeatai-menu-fix';
        style.textContent = `
          @media(max-width:920px){
            .app{grid-template-columns:1fr!important}
            .side{display:flex!important;position:sticky!important;top:0!important;z-index:50!important;flex-direction:row!important;align-items:center!important;gap:12px!important;padding:10px 14px!important;border-right:0!important;border-bottom:1px solid var(--line)!important;background:#081321f7!important;backdrop-filter:blur(10px)!important;overflow-x:auto!important;overflow-y:hidden!important;scrollbar-width:thin!important}
            .side .brand{flex:0 0 auto!important}
            .side .nav{display:flex!important;grid-template-columns:none!important;gap:6px!important;flex:1 0 auto!important;min-width:max-content!important}
            .side .nav button{display:inline-flex!important;align-items:center!important;justify-content:center!important;white-space:nowrap!important;padding:9px 12px!important}
            .side .privacy{display:none!important}
            main{min-width:0!important}
          }
          @media(max-width:560px){
            .side{position:sticky!important;display:grid!important;grid-template-columns:1fr!important;align-items:stretch!important;gap:8px!important;padding:10px!important}
            .side .brand{padding:0 4px!important}
            .side .nav{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;min-width:0!important;width:100%!important}
            .side .nav button{width:100%!important;text-align:center!important;white-space:normal!important;min-height:38px!important}
          }
        `;
        doc.head.appendChild(style);
      }
      const nav = doc.querySelector('.side .nav');
      if (nav) nav.setAttribute('aria-label', 'Menu completo do RepetAI');
    } catch (error) {
      console.warn('Não foi possível ajustar o menu do RepetAI', error);
    }
  }

  function wireFrame(frame) {
    if (!frame || frame.dataset.menuFixBound === '1') return;
    frame.dataset.menuFixBound = '1';
    frame.addEventListener('load', () => keepRepetAIMenuVisible(frame));
    if (frame.contentDocument?.readyState === 'complete') keepRepetAIMenuVisible(frame);
  }

  function buildView() {
    let view = document.getElementById('project-example-view');
    if (view) {
      wireFrame(view.querySelector('#repeatai-frame'));
      return view;
    }
    view = document.createElement('section');
    view.className = 'view';
    view.id = 'project-example-view';
    view.innerHTML = `
      <div class="example-project-shell">
        <div class="example-project-head">
          <div>
            <span class="eyebrow">PROJETO COMPILADO · EXEMPLO EXECUTÁVEL</span>
            <h2>RepetAI</h2>
            <p>Um projeto completo embutido no DevPilot para demonstrar captura privada de interação, métricas técnicas, padrões repetitivos e atualização em tempo real — sem registrar o conteúdo digitado.</p>
          </div>
          <div class="example-project-actions">
            <button class="ghost" type="button" id="repeatai-reload">Recarregar</button>
            <a class="primary" id="repeatai-open" href="${EXAMPLE_URL}" target="_blank" rel="noopener">Tela cheia</a>
          </div>
        </div>
        <div class="example-project-note"><b>✓</b><span>O RepetAI roda como pacote estático autocontido dentro do DevPilot. A demonstração usa apenas dados locais da página e não expõe teclas ou texto digitado.</span></div>
        <div class="example-project-frame-wrap">
          <iframe class="example-project-frame" id="repeatai-frame" src="${EXAMPLE_URL}" title="RepetAI — exemplo de projeto"></iframe>
        </div>
      </div>`;
    document.querySelector('main')?.appendChild(view);
    const frame = view.querySelector('#repeatai-frame');
    wireFrame(frame);
    view.querySelector('#repeatai-reload')?.addEventListener('click', () => {
      const currentFrame = view.querySelector('#repeatai-frame');
      if (currentFrame) currentFrame.src = `${EXAMPLE_URL}?t=${Date.now()}`;
    });
    return view;
  }

  function buildNav() {
    const navRoot = document.querySelector('.sidebar nav');
    if (!navRoot) return null;
    let button = navRoot.querySelector('[data-example-project]');
    if (button) return button;
    button = document.createElement('button');
    button.className = 'nav';
    button.type = 'button';
    button.dataset.exampleProject = 'repeatai';
    button.textContent = NAV_LABEL;
    const projects = navRoot.querySelector('.nav[data-view="projects"]');
    if (projects?.nextSibling) navRoot.insertBefore(button, projects.nextSibling);
    else navRoot.appendChild(button);
    return button;
  }

  function showExample(navButton) {
    const view = buildView();
    document.querySelectorAll('.view').forEach(item => {
      item.classList.toggle('active', item.id === 'project-example-view');
    });
    document.querySelectorAll('.nav').forEach(button => {
      button.classList.toggle('active', button === navButton);
    });
    const title = document.getElementById('page-title');
    if (title) title.textContent = NAV_LABEL;
    keepRepetAIMenuVisible(view.querySelector('#repeatai-frame'));
  }

  injectStyles();
  const view = buildView();
  const navButton = buildNav();
  navButton?.addEventListener('click', () => showExample(navButton));

  window.addEventListener('resize', () => {
    if (!view.classList.contains('active')) return;
    const frame = view.querySelector('#repeatai-frame');
    if (!frame) return;
    frame.style.minHeight = window.innerWidth < 560 ? '580px' : '620px';
    keepRepetAIMenuVisible(frame);
  });
})();