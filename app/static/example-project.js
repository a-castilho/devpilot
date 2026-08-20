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
        .example-project-frame{height:72vh;min-height:560px}
      }
      @media(max-width:560px){
        .example-project-head{padding:16px}
        .example-project-frame{height:68vh;min-height:520px}
        .example-project-actions{width:100%}
        .example-project-actions .primary,.example-project-actions .ghost{flex:1}
      }
    `;
    document.head.appendChild(style);
  }

  function buildView() {
    let view = document.getElementById('project-example-view');
    if (view) return view;
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
    view.querySelector('#repeatai-reload')?.addEventListener('click', () => {
      const frame = view.querySelector('#repeatai-frame');
      if (frame) frame.src = `${EXAMPLE_URL}?t=${Date.now()}`;
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
    buildView();
    document.querySelectorAll('.view').forEach(view => {
      view.classList.toggle('active', view.id === 'project-example-view');
    });
    document.querySelectorAll('.nav').forEach(button => {
      button.classList.toggle('active', button === navButton);
    });
    const title = document.getElementById('page-title');
    if (title) title.textContent = NAV_LABEL;
  }

  injectStyles();
  const view = buildView();
  const navButton = buildNav();
  navButton?.addEventListener('click', () => showExample(navButton));

  window.addEventListener('resize', () => {
    if (!view.classList.contains('active')) return;
    const frame = view.querySelector('#repeatai-frame');
    if (frame) frame.style.minHeight = window.innerWidth < 560 ? '520px' : '620px';
  });
})();