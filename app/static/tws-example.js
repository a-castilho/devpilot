(() => {
  const EXAMPLE_ID = 'tws';
  const VIEW_ID = 'tws-example-view';
  const FRAME_URL = '/examples/tws/index.html';

  function injectStyles() {
    if (document.getElementById('tws-example-styles')) return;
    const style = document.createElement('style');
    style.id = 'tws-example-styles';
    style.textContent = `
      #${VIEW_ID}{padding:0}
      .tws-example-head{display:flex;align-items:center;justify-content:space-between;gap:14px;margin:14px 0 10px;padding:14px 16px;border:1px solid var(--line);border-radius:14px;background:linear-gradient(145deg,#101b2a,#0b141f);box-shadow:var(--shadow)}
      .tws-example-brand{display:flex;align-items:center;gap:11px;min-width:0}
      .tws-example-mark{width:38px;height:38px;border-radius:11px;display:grid;place-items:center;background:linear-gradient(135deg,#4dd7bf,#6da7ff);color:#06111c;font-weight:950}
      .tws-example-brand strong{display:block;color:var(--text);font-size:15px}.tws-example-brand small{display:block;color:var(--muted);font-size:10px;margin-top:2px;letter-spacing:.08em}
      .tws-example-badges{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.tws-example-badges span{padding:6px 8px;border:1px solid var(--line);border-radius:999px;color:var(--muted);font-size:9px;font-weight:850}
      .tws-example-stage{position:relative;min-height:calc(100vh - 150px);overflow:hidden;border:1px solid var(--line);border-radius:14px;background:#07111f;box-shadow:var(--shadow)}
      .tws-example-frame{display:block;width:100%;height:calc(100vh - 150px);min-height:650px;border:0;background:#07111f}
      .tws-example-loading{position:absolute;inset:0;display:grid;place-items:center;color:var(--muted);background:#07111f;z-index:1}.tws-example-loading[hidden]{display:none}
      .tws-example-error{position:absolute;inset:0;z-index:2;display:grid;place-items:center;align-content:center;gap:10px;padding:24px;text-align:center;background:linear-gradient(145deg,#0b1726,#07111f)}.tws-example-error h3{margin:0;color:var(--text);font-size:18px}.tws-example-error p{margin:0;max-width:460px;color:var(--muted)}.tws-example-error button{margin-top:4px}
      @media(max-width:760px){.tws-example-head{margin-top:9px;border-radius:11px;padding:12px}.tws-example-badges{display:none}.tws-example-stage{min-height:calc(100vh - 120px);border-radius:10px}.tws-example-frame{height:calc(100vh - 120px);min-height:640px}}
    `;
    document.head.appendChild(style);
  }

  function buildNav() {
    const navRoot = document.querySelector('.sidebar nav');
    if (!navRoot) return null;
    let button = navRoot.querySelector(`[data-example-project="${EXAMPLE_ID}"]`);
    if (button) return button;

    button = document.createElement('button');
    button.className = 'nav';
    button.type = 'button';
    button.dataset.exampleProject = EXAMPLE_ID;
    button.textContent = 'Exemplo TWS';

    const repeatai = navRoot.querySelector('[data-example-project="repeatai"]');
    if (repeatai?.nextSibling) navRoot.insertBefore(button, repeatai.nextSibling);
    else navRoot.appendChild(button);
    return button;
  }

  function buildView() {
    let view = document.getElementById(VIEW_ID);
    if (view) return view;

    view = document.createElement('section');
    view.className = 'view';
    view.id = VIEW_ID;
    view.innerHTML = `
      <div class="tws-example-head">
        <div class="tws-example-brand">
          <span class="tws-example-mark">T</span>
          <div><strong>TWS · telas de exemplo</strong><small>PAINEL · OPERAÇÃO · TAREFAS · MONITORAMENTO</small></div>
        </div>
        <div class="tws-example-badges"><span>RESPONSIVO</span><span>MOBILE</span><span>DESKTOP</span></div>
      </div>
      <div class="tws-example-stage">
        <div class="tws-example-loading" id="tws-example-loading">Abrindo exemplo TWS…</div>
        <iframe class="tws-example-frame" id="tws-example-frame" title="TWS — telas de exemplo" referrerpolicy="no-referrer" hidden></iframe>
      </div>`;
    document.querySelector('main')?.appendChild(view);
    return view;
  }

  function showFrameError(view, message) {
    const stage = view.querySelector('.tws-example-stage');
    const frame = view.querySelector('#tws-example-frame');
    const loading = view.querySelector('#tws-example-loading');
    if (!stage || !frame || !loading) return;

    frame.hidden = true;
    loading.hidden = true;

    let error = stage.querySelector('.tws-example-error');
    if (!error) {
      error = document.createElement('div');
      error.className = 'tws-example-error';
      error.innerHTML = `
        <h3>Exemplo TWS indisponível</h3>
        <p></p>
        <button class="btn primary" type="button">Tentar novamente</button>
      `;
      stage.appendChild(error);
    }
    error.querySelector('p').textContent = message;
    error.querySelector('button').onclick = () => {
      error.remove();
      loadFrame(view, true);
    };
  }

  async function loadFrame(view, force = false) {
    const frame = view.querySelector('#tws-example-frame');
    const loading = view.querySelector('#tws-example-loading');
    if (!frame || !loading || frame.dataset.loading === '1') return;
    if (!force && frame.dataset.ready === '1') return;

    frame.dataset.loading = '1';
    frame.dataset.ready = '0';
    frame.hidden = true;
    loading.hidden = false;
    loading.textContent = 'Carregando exemplo TWS…';

    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 3500);

    try {
      const separator = FRAME_URL.includes('?') ? '&' : '?';
      const response = await fetch(`${FRAME_URL}${separator}v=${Date.now()}`, {
        credentials: 'same-origin',
        cache: 'no-store',
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const html = await response.text();
      if (!/<(?:!doctype html|html)/i.test(html)) throw new Error('resposta inválida');

      const baseUrl = new URL(FRAME_URL, window.location.href).href;
      const baseTag = `<base href="${baseUrl.replace(/"/g, '&quot;')}">`;
      const srcdoc = html.replace(/<head>/i, match => `${match}${baseTag}`);

      await new Promise((resolve, reject) => {
        const onLoad = () => {
          frame.removeEventListener('error', onError);
          resolve();
        };
        const onError = () => {
          frame.removeEventListener('load', onLoad);
          reject(new Error('iframe indisponível'));
        };
        frame.addEventListener('load', onLoad, {once: true});
        frame.addEventListener('error', onError, {once: true});
        frame.srcdoc = srcdoc;
      });

      frame.dataset.loading = '0';
      frame.dataset.ready = '1';
      frame.dataset.source = 'embedded';
      frame.hidden = false;
      loading.hidden = true;
    } catch (error) {
      frame.dataset.loading = '0';
      frame.dataset.ready = '0';
      showFrameError(view, 'O servidor respondeu, mas o conteúdo do exemplo não pôde ser carregado. Tente novamente.');
      console.warn('[DevPilot] falha ao carregar exemplo TWS', error);
    } finally {
      window.clearTimeout(timer);
    }
  }

  function show(navButton) {
    const view = buildView();
    document.querySelectorAll('.view').forEach(item => item.classList.toggle('active', item.id === VIEW_ID));
    document.querySelectorAll('.nav').forEach(button => button.classList.toggle('active', button === navButton));
    const title = document.getElementById('page-title');
    if (title) title.textContent = 'Exemplo de projeto · TWS';
    loadFrame(view);
  }

  injectStyles();
  const navButton = buildNav();
  navButton?.addEventListener('click', () => show(navButton));
})();