(() => {
  const form = document.querySelector('#task-form');
  const context = document.querySelector('#task-context');
  const submit = document.querySelector('#task-submit');
  if (!form || !context || !submit) return;

  const MAX_IMAGES = 3;
  const MAX_BYTES = 8 * 1024 * 1024;
  const ACCEPTED_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);
  let files = [];
  let previewUrls = [];

  const style = document.createElement('style');
  style.id = 'devpilot-task-image-style';
  style.textContent = `
    #task-modal .task-image-panel{display:grid;gap:10px;padding:13px;border:1px solid #24445f;border-radius:13px;background:linear-gradient(145deg,rgba(7,20,35,.96),rgba(9,28,44,.82))}
    #task-modal .task-image-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
    #task-modal .task-image-head strong{font-size:12px;color:#dbeafe}
    #task-modal .task-image-head span{font-size:9px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#65f4df;border:1px solid rgba(101,244,223,.32);border-radius:999px;padding:4px 8px}
    #task-modal .task-image-drop{width:100%;min-height:86px;display:flex;align-items:center;gap:12px;text-align:left;padding:13px 15px;border:1px dashed #315b79;border-radius:12px;background:#071423;color:#d7e7f7;cursor:pointer;transition:border-color .16s ease,background .16s ease,transform .16s ease}
    #task-modal .task-image-drop:hover,#task-modal .task-image-drop.is-dragging{border-color:#35e5d1;background:#091b2d;transform:translateY(-1px)}
    #task-modal .task-image-icon{width:40px;height:40px;display:grid;place-items:center;flex:0 0 40px;border-radius:11px;background:#12354b;color:#68f4e2;font-size:20px}
    #task-modal .task-image-copy{display:grid;gap:2px;min-width:0}
    #task-modal .task-image-copy strong{font-size:12px}
    #task-modal .task-image-copy small{font-size:10px;color:#7795b3;font-weight:500;line-height:1.4}
    #task-modal .task-image-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
    #task-modal .task-image-item{position:relative;min-width:0;display:grid;grid-template-columns:54px minmax(0,1fr);gap:8px;align-items:center;padding:7px;border:1px solid #203e58;border-radius:10px;background:#081727}
    #task-modal .task-image-item img{width:54px;height:54px;object-fit:cover;border-radius:8px;background:#030b13}
    #task-modal .task-image-meta{min-width:0;display:grid;gap:3px}
    #task-modal .task-image-meta strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px;color:#cfe0ef}
    #task-modal .task-image-meta small{font-size:9px;color:#728da9}
    #task-modal .task-image-remove{position:absolute;top:4px;right:4px;width:22px;height:22px;padding:0;border:1px solid #35516b;border-radius:7px;background:#0a1c2d;color:#b7cadb;cursor:pointer;line-height:1}
    #task-modal .task-image-remove:hover{border-color:#ff6b81;color:#ff9aaa}
    #task-modal .task-image-note{margin:0;color:#6f8aa5;font-size:9px;line-height:1.4}
    @media(max-width:640px){#task-modal .task-image-list{grid-template-columns:1fr}#task-modal .task-image-drop{min-height:76px}}
  `;
  if (!document.querySelector(`#${style.id}`)) document.head.appendChild(style);

  const panel = document.createElement('section');
  panel.className = 'task-image-panel';
  panel.innerHTML = `
    <div class="task-image-head">
      <strong>Imagem para análise</strong>
      <span>Opcional · até ${MAX_IMAGES}</span>
    </div>
    <button type="button" class="task-image-drop" id="task-image-drop">
      <span class="task-image-icon" aria-hidden="true">▧</span>
      <span class="task-image-copy">
        <strong>Clique ou arraste uma foto aqui</strong>
        <small>Use prints de tela, erros visuais ou referências. PNG, JPG ou WEBP, até 8 MB por imagem.</small>
      </span>
    </button>
    <input id="task-image-input" type="file" accept="image/png,image/jpeg,image/webp" multiple hidden>
    <div class="task-image-list" id="task-image-list" hidden></div>
    <p class="task-image-note">A imagem será anexada à mesma tarefa e enviada ao analisador junto com o contexto e o repositório.</p>
  `;

  const assistCard = form.querySelector('.task-assist-card');
  if (assistCard) assistCard.insertAdjacentElement('beforebegin', panel);
  else context.closest('label')?.insertAdjacentElement('afterend', panel);

  const drop = panel.querySelector('#task-image-drop');
  const input = panel.querySelector('#task-image-input');
  const list = panel.querySelector('#task-image-list');

  function readableSize(bytes) {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function clearPreviews() {
    previewUrls.forEach(url => URL.revokeObjectURL(url));
    previewUrls = [];
  }

  function render() {
    clearPreviews();
    if (!files.length) {
      list.hidden = true;
      list.innerHTML = '';
      return;
    }

    list.hidden = false;
    list.innerHTML = files.map((file, index) => {
      const url = URL.createObjectURL(file);
      previewUrls.push(url);
      const safeName = String(file.name || `imagem-${index + 1}`)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
      return `
        <div class="task-image-item">
          <img src="${url}" alt="Prévia da imagem ${index + 1}">
          <div class="task-image-meta">
            <strong title="${safeName}">${safeName}</strong>
            <small>${readableSize(file.size)}</small>
          </div>
          <button type="button" class="task-image-remove" data-image-index="${index}" aria-label="Remover imagem">×</button>
        </div>`;
    }).join('');

    list.querySelectorAll('[data-image-index]').forEach(button => {
      button.addEventListener('click', () => {
        files.splice(Number(button.dataset.imageIndex), 1);
        render();
      });
    });
  }

  function acceptFiles(incoming) {
    for (const file of incoming) {
      if (files.length >= MAX_IMAGES) {
        toast(`Você pode anexar no máximo ${MAX_IMAGES} imagens`);
        break;
      }
      if (!ACCEPTED_TYPES.has(file.type)) {
        toast('Use apenas imagens PNG, JPG ou WEBP');
        continue;
      }
      if (!file.size) {
        toast('A imagem selecionada está vazia');
        continue;
      }
      if (file.size > MAX_BYTES) {
        toast(`A imagem ${file.name} ultrapassa 8 MB`);
        continue;
      }
      files.push(file);
    }
    input.value = '';
    render();
  }

  drop.addEventListener('click', () => input.click());
  input.addEventListener('change', () => acceptFiles([...input.files]));
  ['dragenter', 'dragover'].forEach(name => drop.addEventListener(name, event => {
    event.preventDefault();
    drop.classList.add('is-dragging');
  }));
  ['dragleave', 'drop'].forEach(name => drop.addEventListener(name, event => {
    event.preventDefault();
    drop.classList.remove('is-dragging');
  }));
  drop.addEventListener('drop', event => acceptFiles([...event.dataTransfer.files]));

  async function uploadImage(file) {
    const body = new FormData();
    body.append('image', file, file.name);
    return api('/task-images', {method: 'POST', body});
  }

  async function cleanupUploads(uploaded) {
    await Promise.allSettled(uploaded.map(item => api(`/task-images/${encodeURIComponent(item.id)}`, {
      method: 'DELETE'
    })));
  }

  form.addEventListener('submit', async event => {
    if (!files.length) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    const snapshot = new FormData(form);
    const queuedFiles = [...files];
    const originalText = submit.textContent;
    const uploaded = [];
    submit.disabled = true;
    submit.textContent = queuedFiles.length === 1 ? 'Enviando imagem…' : 'Enviando imagens…';

    try {
      for (const file of queuedFiles) {
        uploaded.push(await uploadImage(file));
      }

      const markers = uploaded.map(item => item.marker).join('\n');
      const basePrompt = String(snapshot.get('prompt') || '').trim();
      const payload = {
        project_id: snapshot.get('project_id'),
        title: snapshot.get('title'),
        prompt: `${basePrompt}\n\nImagens anexadas para análise:\n${markers}`,
        priority: Number(snapshot.get('priority')),
        requires_approval: snapshot.get('requires_approval') === 'on',
        source: 'dashboard'
      };

      await api('/tasks', {method: 'POST', body: JSON.stringify(payload)});
      form.closest('dialog').close();
      form.reset();
      files = [];
      render();
      toast(uploaded.length === 1
        ? 'Tarefa registrada com imagem para análise'
        : `Tarefa registrada com ${uploaded.length} imagens para análise`);
      load();
    } catch (error) {
      if (uploaded.length) await cleanupUploads(uploaded);
      toast(error.message || 'Não foi possível anexar a imagem');
    } finally {
      submit.disabled = false;
      submit.textContent = originalText;
    }
  }, true);

  form.addEventListener('reset', () => {
    files = [];
    window.setTimeout(render, 0);
  });
})();

/*
 * Execuções V40 · estabilizador de renderer.
 * task-failures.js é carregado antes deste arquivo e ainda substitui renderTasks
 * por um renderer legado de 5 colunas. Este adaptador preserva o diagnóstico
 * daquele módulo, normaliza o DOM para o contrato visual atual e impede que
 * Atualizar/Detalhes voltem a comprimir a tela.
 */
(() => {
  'use strict';

  if (window.__devpilotTasksRenderStabilityV40) return;
  window.__devpilotTasksRenderStabilityV40 = true;

  const STYLE_ID = 'devpilot-tasks-render-stability-v40';

  function injectStabilityStyle() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #tasks-view #tasks-table > tr.tasks-render-stable-v40 > td{min-width:0!important;word-break:normal!important;overflow-wrap:break-word!important}
      #tasks-view #tasks-table > tr.tasks-render-stable-v40 .tasks-v9-title{display:block;max-width:100%;white-space:normal!important;word-break:normal!important;overflow-wrap:break-word!important;line-height:1.35}
      #tasks-view #tasks-table > tr.tasks-v9-recovery-row{border-color:rgba(157,114,255,.34)!important;background:linear-gradient(145deg,rgba(25,18,54,.78),rgba(7,22,36,.97))!important}
      #tasks-view #tasks-table > tr.tasks-v9-recovery-row .tasks-v9-source{color:#c7b5ff!important}
      #tasks-view #tasks-table > tr.tasks-v9-recovery-row .task-kind-badge.recovery{border-color:rgba(157,114,255,.34)!important;color:#d5c9ff!important;background:rgba(157,114,255,.10)!important}

      @media (min-width:901px) and (max-width:1280px){
        #tasks-view #tasks-table > tr.tasks-render-stable-v40{
          display:grid!important;
          grid-template-columns:minmax(0,1fr) minmax(180px,280px)!important;
          gap:10px 18px!important;
          width:100%!important;
          margin-bottom:12px!important;
          padding:16px!important;
          border:1px solid rgba(80,150,204,.24)!important;
          border-radius:16px!important;
          background:linear-gradient(145deg,rgba(12,29,46,.96),rgba(8,22,36,.96))!important;
          overflow:hidden!important;
        }
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 > td{display:block!important;width:auto!important;padding:0!important;border:0!important;background:transparent!important;box-shadow:none!important}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 > td:nth-child(1){grid-column:1/-1!important;grid-row:1!important}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 > td:nth-child(2){grid-column:1!important;grid-row:2!important;align-self:center!important;white-space:nowrap!important}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 > td:nth-child(3){grid-column:2!important;grid-row:2/span 2!important;align-self:start!important;justify-self:end!important;max-width:280px!important}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 > td:nth-child(4){grid-column:1!important;grid-row:3!important;align-self:center!important;white-space:nowrap!important}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 > td:nth-child(5){grid-column:2!important;grid-row:4!important;justify-self:end!important;width:100%!important}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 .tasks-v9-source::before{content:'ORIGEM · ';color:#607f98;font-size:8px;font-weight:900;letter-spacing:.08em}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 .tasks-v9-priority::before{content:'PRIORIDADE · ';color:#607f98;font-size:8px;font-weight:900;letter-spacing:.08em}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 .tasks-v9-actions .task-actions,
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 .tasks-v9-actions .task-operational-actions{display:flex!important;justify-content:flex-end!important;gap:8px!important;flex-wrap:wrap!important}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 .task-status-stack{min-width:0!important;max-width:280px!important}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 .task-failure-reason{max-width:280px!important;overflow-wrap:break-word!important;word-break:normal!important}
      }

      @media (max-width:900px){
        #tasks-view #tasks-table > tr.tasks-render-stable-v40{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:10px!important;width:100%!important;padding:14px!important;border:1px solid rgba(80,150,204,.24)!important;border-radius:14px!important;background:linear-gradient(145deg,rgba(12,29,46,.96),rgba(8,22,36,.96))!important}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 > td{grid-column:1!important;grid-row:auto!important;display:block!important;width:100%!important;max-width:100%!important;padding:0!important;border:0!important;background:transparent!important}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 .task-status-stack,#tasks-view #tasks-table > tr.tasks-render-stable-v40 .task-failure-reason{max-width:100%!important}
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 .tasks-v9-actions .task-actions,
        #tasks-view #tasks-table > tr.tasks-render-stable-v40 .tasks-v9-actions .task-operational-actions{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:8px!important;width:100%!important}
      }
    `;
    document.head.appendChild(style);
  }

  function currentTasks() {
    return typeof state !== 'undefined' && Array.isArray(state.tasks) ? state.tasks : [];
  }

  function taskForRow(row) {
    const id = String(row?.dataset?.taskId || '');
    return currentTasks().find(task => String(task.id) === id) || null;
  }

  function normalizeRow(row) {
    if (!(row instanceof HTMLTableRowElement) || !row.dataset.taskId) return;
    const cells = Array.from(row.children).filter(cell => cell instanceof HTMLTableCellElement);
    if (cells.length < 3) return;

    row.classList.add('task-main-row', 'tasks-v9-row', 'tasks-render-stable-v40');

    if (cells.length >= 5) {
      cells[0].classList.add('tasks-v9-main');
      cells[1].classList.add('tasks-v9-source');
      cells[2].classList.add('tasks-v9-state');
      cells[3].classList.add('tasks-v9-priority');
      cells[4].classList.add('tasks-v9-actions');
      cells[0].querySelector('strong')?.classList.add('tasks-v9-title');
    }

    const task = taskForRow(row);
    const recoveryTask = String(task?.source || '').toLowerCase() === 'failure-recovery';
    row.classList.toggle('tasks-v9-recovery-row', recoveryTask);

    if (recoveryTask) {
      const source = row.querySelector('.tasks-v9-source');
      if (source) source.textContent = 'Recuperação';
      const kind = row.querySelector('.task-kind-badge');
      if (kind) {
        kind.classList.remove('analysis', 'execution');
        kind.classList.add('recovery');
        kind.textContent = 'Recuperação';
      }
    }
  }

  function normalizeRows({emit = true} = {}) {
    const rows = Array.from(document.querySelectorAll('#tasks-table > tr[data-task-id]'));
    rows.forEach(normalizeRow);

    if (emit) {
      document.dispatchEvent(new CustomEvent('devpilot:tasks-rendered', {
        detail:{count:rows.length, stabilityV40:true},
      }));
    }

    document.querySelectorAll('#tasks-table .tasks-v9-recovery-row .task-recovery-action')
      .forEach(button => button.remove());
  }

  function installRendererGuard() {
    let upstream = null;
    try { upstream = typeof renderTasks === 'function' ? renderTasks : null; } catch (_) {}
    if (!upstream && typeof window.renderTasks === 'function') upstream = window.renderTasks;
    if (!upstream || upstream.__devpilotStabilityV40) return;

    const stableRender = function stableRenderTasksV40(...args) {
      const result = upstream.apply(this, args);
      normalizeRows();
      window.requestAnimationFrame(() => normalizeRows({emit:false}));
      return result;
    };
    stableRender.__devpilotStabilityV40 = true;
    stableRender.__devpilotUpstream = upstream;

    window.renderTasks = stableRender;
    try { renderTasks = stableRender; } catch (_) {}
  }

  injectStabilityStyle();
  installRendererGuard();
  normalizeRows();

  document.addEventListener('devpilot:tasks-rendered', event => {
    if (event.detail?.stabilityV40) return;
    normalizeRows();
  });
})();