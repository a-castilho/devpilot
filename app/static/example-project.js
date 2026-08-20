(() => {
  const NAV_LABEL = 'Exemplo de projeto';
  const FALLBACK_URL = '/examples/repeatai/index.html';

  function liveUrl() {
    if (window.location.protocol === 'https:') return null;
    const host = window.location.hostname || '127.0.0.1';
    return `http://${host}:8091/`;
  }

  function injectStyles() {
    if (document.getElementById('example-project-styles')) return;
    const style = document.createElement('style');
    style.id = 'example-project-styles';
    style.textContent = `
      #project-example-view{padding:0}
      .example-project-stage{
        position:relative;
        margin-top:16px;
        min-height:calc(100vh - 150px);
        overflow:hidden;
        border:1px solid var(--line);
        border-radius:14px;
        background:#0b0f14;
        box-shadow:var(--shadow)
      }
      .example-project-frame{
        display:block;
        width:100%;
        height:calc(100vh - 150px);
        min-height:640px;
        border:0;
        background:#0b0f14
      }
      .example-project-loading{
        position:absolute;
        inset:0;
        z-index:1;
        display:grid;
        place-items:center;
        color:var(--muted);
        font-size:13px;
        background:#0b0f14
      }
      .example-project-loading[hidden]{display:none}
      @media(max-width:760px){
        .example-project-stage{margin-top:10px;min-height:calc(100vh - 132px);border-radius:10px}
        .example-project-frame{height:calc(100vh - 132px);min-height:620px}
      }
    `;
    document.head.appendChild(style);
  }

  function buildNav() {
    const navRoot = document.querySelector('.sidebar nav');
    if (!navRoot) return null;

    let button = navRoot.querySelector('[data-example-project="repeatai"]');
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

  function buildView() {
    let view = document.getElementById('project-example-view');
    if (view) return view;

    view = document.createElement('section');
    view.className = 'view';
    view.id = 'project-example-view';
    view.innerHTML = `
      <div class="example-project-stage">
        <div class="example-project-loading" id="repeatai-loading">Abrindo RepetAI…</div>
        <iframe
          class="example-project-frame"
          id="repeatai-frame"
          title="RepetAI — exemplo de projeto"
          referrerpolicy="no-referrer"
          hidden
        ></iframe>
      </div>`;

    document.querySelector('main')?.appendChild(view);
    return view;
  }

  async function probe(url) {
    if (!url) return false;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 1600);
    try {
      await fetch(url, {
        method: 'GET',
        mode: 'no-cors',
        cache: 'no-store',
        signal: controller.signal,
      });
      return true;
    } catch (_) {
      return false;
    } finally {
      window.clearTimeout(timer);
    }
  }

  async function loadRepetAI(view, force = false) {
    const frame = view.querySelector('#repeatai-frame');
    const loading = view.querySelector('#repeatai-loading');
    if (!frame || frame.dataset.loading === '1') return;
    if (!force && frame.dataset.ready === '1') return;

    frame.dataset.loading = '1';
    frame.dataset.ready = '0';
    frame.hidden = true;
    loading.hidden = false;
    loading.textContent = 'Abrindo RepetAI…';

    const local = liveUrl();
    const useLive = await probe(local);
    const target = useLive ? local : FALLBACK_URL;

    const onLoad = () => {
      frame.hidden = false;
      frame.dataset.loading = '0';
      frame.dataset.ready = '1';
      frame.dataset.source = useLive ? 'local' : 'compilado';
      loading.hidden = true;
      frame.removeEventListener('load', onLoad);
    };

    frame.addEventListener('load', onLoad);
    frame.src = force ? `${target}${target.includes('?') ? '&' : '?'}t=${Date.now()}` : target;
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
    if (title) title.textContent = 'Exemplo de projeto · RepetAI';

    loadRepetAI(view);
  }

  injectStyles();
  const navButton = buildNav();
  navButton?.addEventListener('click', () => showExample(navButton));
})();